# PRIVATE LIBRARIES
import threading
from frontendio import *
from timestamp import *

# OTHER MODULES
import sys
from pyvisa import attributes

# MATPLOTLIB
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# TKINTER
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter.ttk import *
 
# CONSTANTS
RETURN_ERROR = 1
RETURN_SUCCESS = 0
CHUNK_SIZE_DEF = 20480     # Default byte count to read when issuing viRead
CHUNK_SIZE_MIN = 1024
CHUNK_SIZE_MAX = 1048576  # Max chunk size allowed
TIMEOUT_DEF = 2000        # Default VISA timeout value
TIMEOUT_MIN = 1000        # Minimum VISA timeout value
TIMEOUT_MAX = 25000       # Maximum VISA timeout value

class FrontEnd():
    def __init__(self, root):
        """Initializes the top level tkinter interface
        """
        # Generate thread to handle live data plot in background
        self.t1 = threading.Thread(target=self.initAnalyzerDisplay, daemon=TRUE)

        # CONSTANTS
        self.SELECT_TERM_VALUES = ['Line Feed - \\n', 'Carriage Return - \\r']

        # VARIABLES
        self.timeout = TIMEOUT_DEF           # VISA timeout value
        self.chunkSize = CHUNK_SIZE_DEF      # Bytes to read from buffer
        self.instrument = ''                 # ID of the currently open instrument. Used only in resetWidgetValues method
        self.analyzerKillFlag = TRUE

        # TKINTER VARIABLES
        self.sendEnd = BooleanVar()
        self.sendEnd.set(TRUE)
        self.enableTerm = BooleanVar()
        self.enableTerm.set(FALSE)
        
        self.root = root
        self.root.title('RF-DFS')
        self.Vi = VisaControl()
        self.Vi.openRsrcManager()

        oFile = DataManagement()
        tabControl = ttk.Notebook(root) 
  
        self.tab1 = ttk.Frame(tabControl) 
        self.tab2 = ttk.Frame(tabControl) 

        tabControl.add(self.tab1, text ='Control') 
        tabControl.add(self.tab2, text ='Config') 
        tabControl.bind('<Button-1>', lambda event: self.resetWidgetValues(event))
        tabControl.pack(expand = 1, fill ="both") 

        self.controlTab()
        self.updateOutput( oFile, root )
        self.configTab()
        self.root.after(1000, self.update_time )
    
    def on_closing( self ):
        """ Ask to close serial communication when 'X' button is pressed """
        SaveCheck = messagebox.askokcancel( title = "Window closing", message = "Do you want to close communication to the motor?" )
        if SaveCheck is True:      
            while (self.motor.ser.is_open):
                self.motor.CloseSerial()
        else:
            pass
    
        self.root.quit()

    def configTab(self):
        """Generates the SCPI communication interface on the developer's tab of choice at tabSelect
        """
        tabSelect = self.tab2                # Select which tab this interface should be placed

        def onConnectPress():
            """Connect to the resource and update the string in self.instrument
            """
            if self.Vi.connectToRsrc(self.instrSelectBox.get()) == RETURN_SUCCESS:
                self.instrument = self.instrSelectBox.get()
                self.scpiApplyConfig(self.timeoutWidget.get(), self.chunkSizeWidget.get())
        def onRefreshPress():
            """Update the values in the SCPI instrument selection box
            """
            print('Searching for resources...')
            self.instrSelectBox['values'] = self.Vi.rm.list_resources()
        def onEnableTermPress():
            if self.enableTerm.get():
                self.selectTermWidget.config(state='readonly')
            else:
                self.selectTermWidget.config(state='disabled')  


        # INSTRUMENT SELECTION FRAME & GRID
        # ISSUE: Apply changes should only be pressable when changes are detected
        ttk.Label(tabSelect, text = "Select a SCPI instrument:", 
          font = ("Times New Roman", 10)).grid(column = 0, 
          row = 0, padx = 5, pady = 25) 
        self.instrSelectBox = ttk.Combobox(tabSelect, values = self.Vi.rm.list_resources(), width=40)
        self.instrSelectBox.grid(row = 0, column = 1, padx = 10 , pady = 10)
        self.refreshButton = tk.Button(tabSelect, text = "Refresh", command = lambda:onRefreshPress())
        self.refreshButton.grid(row = 0, column = 2, padx=5)
        self.confirmButton = tk.Button(tabSelect, text = "Connect", command = lambda:onConnectPress())
        self.confirmButton.grid(row = 0, column = 3, padx=5)
        # VISA CONFIGURATION FRAME
        self.configFrame = ttk.LabelFrame(tabSelect, borderwidth = 2, text = "VISA Configuration")
        self.configFrame.grid(row = 1, column = 0, padx=20, pady=10, sticky=tk.N)
        self.timeoutLabel = ttk.Label(self.configFrame, text = 'Timeout (ms)')
        self.timeoutWidget = ttk.Spinbox(self.configFrame, from_=TIMEOUT_MIN, to=TIMEOUT_MAX, increment=100)
        self.timeoutWidget.set(self.timeout)
        self.chunkSizeLabel = ttk.Label(self.configFrame, text = 'Chunk size (Bytes)')
        self.chunkSizeWidget = ttk.Spinbox(self.configFrame, from_=CHUNK_SIZE_MIN, to=CHUNK_SIZE_MAX, increment=10240)
        self.chunkSizeWidget.set(self.chunkSize)
        self.applyButton = tk.Button(self.configFrame, text = "Apply Changes", command = lambda:self.scpiApplyConfig(self.timeoutWidget.get(), self.chunkSizeWidget.get()))
        # VISA CONFIGURATION GRID
        self.timeoutLabel.grid(row = 0, column = 0, pady=5)
        self.timeoutWidget.grid(row = 1, column = 0, padx=20, pady=5, columnspan=2)
        self.chunkSizeLabel.grid(row = 2, column = 0, pady=5)
        self.chunkSizeWidget.grid(row = 3, column = 0, padx=20, pady=5, columnspan=2)
        self.applyButton.grid(row = 7, column = 0, columnspan=2, pady=10)
        # VISA TERMINATION FRAME
        self.termFrame = ttk.LabelFrame(tabSelect, borderwidth=2, text = 'Termination Methods')
        self.termFrame.grid(row = 1, column = 1, padx = 5, pady = 10, sticky=tk.N+tk.W)
        self.sendEndWidget = ttk.Checkbutton(self.termFrame, text = 'Send \'End or Identify\' on write', variable=self.sendEnd)
        self.selectTermWidget = ttk.Combobox(self.termFrame, text='Termination Character', values=self.SELECT_TERM_VALUES, state='disabled')
        self.enableTermWidget = ttk.Checkbutton(self.termFrame, text = 'Enable Termination Character', variable=self.enableTerm, command=lambda:onEnableTermPress())
        # VISA TERMINATION GRID
        self.sendEndWidget.grid(row = 0, column = 0, pady = 5)
        self.enableTermWidget.grid(row = 1, column = 0, pady = 5)
        self.selectTermWidget.grid(row = 2, column = 0, pady = 5)
    

    def resetWidgetValues(self, event):
        """Event handler to reset widget values to their respective variables

        Args:
            event (event): Argument passed by tkinter event (Varies for each event)
        """
        # These widgets values are stored in variables and will be reset to the variable on function call
        try:
            self.timeoutWidget.set(self.timeout)
            self.chunkSizeWidget.set(self.chunkSize)
            self.instrSelectBox.set(self.instrument)
        except:
            pass
        # These widget values are retrieved from self.Vi.openRsrc and will be reset depending on the values returned
        try:
            self.sendEnd.set(self.Vi.openRsrc.send_end)
            readTerm = repr(self.Vi.openRsrc.read_termination)
            if readTerm == repr(''):
                self.enableTerm.set(FALSE)
                self.selectTermWidget.set('')
            elif readTerm == repr('\n'):
                self.enableTerm.set(TRUE)
                self.selectTermWidget.set(self.SELECT_TERM_VALUES[0])
            elif readTerm == repr('\r'):
                self.enableTerm.set(TRUE)
                self.selectTermWidget.set(self.SELECT_TERM_VALUES[1])
            if self.enableTerm.get():
                self.selectTermWidget.config(state='readonly')
            else:
                self.selectTermWidget.config(state='disabled')  
        except:
            pass
        
    def scpiApplyConfig(self, timeoutArg, chunkSizeArg):
        """Issues VISA commands to set config and applies changes made in the SCPI configuration frame to variables timeout and chunkSize (for resetWidgetValues)

        Args:
            timeoutArg (string): Argument received from timeout widget which will be tested for type int and within range
            chunkSizeArg (string): Argument received from chunkSize widget which will be tested for type int and within range

        Raises:
            TypeError: ttk::spinbox get() does not return type int or integer out of range for respective variable

        Returns:
            0: On success
            1: On error
        """
        # Get the termination character from selectTermWidget
        termSelectIndex = self.selectTermWidget.current()
        if termSelectIndex == 0:
            termChar = '\n'
        elif termSelectIndex == 1:
            termChar = '\r'
        else:
            termChar = ''
        # Get timeout and chunk size values from respective widgets
        try:
            timeoutArg = int(timeoutArg)
            chunkSizeArg = int(chunkSizeArg)
        except:
            raise TypeError('ttk::spinbox get() did not return type int')
        # Test timeout and chunk size for within range
        if timeoutArg < TIMEOUT_MIN or timeoutArg > TIMEOUT_MAX:
            raise TypeError(f'int timeout out of range. Min: {TIMEOUT_MIN}, Max: {TIMEOUT_MAX}')
        if chunkSizeArg < CHUNK_SIZE_MIN or chunkSizeArg > CHUNK_SIZE_MAX:
            raise TypeError(f'int chunkSize out of range. Min: {CHUNK_SIZE_MIN}, Max: {CHUNK_SIZE_MAX}')
        # Call self.Vi.setConfig and if successful, print output and set variables for resetWidgetValues
        if self.Vi.setConfig(timeoutArg, chunkSizeArg, self.sendEnd.get(), self.enableTerm.get(), termChar) == RETURN_SUCCESS:
            self.timeout = timeoutArg
            self.chunkSize = chunkSizeArg
            print(f'Timeout: {self.Vi.openRsrc.timeout}, Chunk size: {self.Vi.openRsrc.chunk_size}, Send EOI: {self.Vi.openRsrc.send_end}, Termination: {repr(self.Vi.openRsrc.write_termination)}')
            return RETURN_SUCCESS
        else:
            return RETURN_ERROR
    
    def controlTab(self):
        """Generates the serial communication interface on the developer's tab of choice at tabSelect
        """

        tabSelect = self.tab1   # Select which tab this interface should be placed
        tabSelect.rowconfigure(0, weight=1)
        tabSelect.rowconfigure(1, weight=1)
        tabSelect.columnconfigure(0, weight=1)
        tabSelect.columnconfigure(1, weight=1)
        tabSelect.columnconfigure(2, weight=10)

        # TKINTER VARIABLES
        spanType = StringVar()
        rbwType = StringVar()
        vbwType = StringVar()
        bwRatioType = StringVar()
        rbwFilterShape = StringVar()
        rbwFilterType = StringVar()
        attenType = StringVar()

        self.motor = MotorControl( 0 , 0 )
        
        # COLUMN 0 WIDGETS
        ports                   = list( serial.tools.list_ports.comports() ) 
        self.port_selection     = ttk.Combobox( tabSelect , values = ports )
        self.port_selection.grid(row = 0, column = 0 , padx = 20 , pady = 10, sticky=(NW, E))

        self.positions          = tk.LabelFrame( tabSelect, text = "Antenna Position" )
        self.positions.grid( row = 1, column = 0 , padx = 20 , pady = 10, sticky=(NSEW))
        self.boxFrame           = tk.Frame( self.positions )
        self.boxFrame.pack( pady = 10 )

        self.azimuth_label      = tk.Label( self.boxFrame , text = "Azimuth" )
        self.elevation_label    = tk.Label( self.boxFrame , text = "Elevation")
        self.inputAzimuth       = tk.Entry( self.boxFrame, width= 10 )
        self.inputElevation     = tk.Entry( self.boxFrame, width= 10 )

        self.azimuth_label.grid( row = 0, column = 0, padx = 10 )
        self.elevation_label.grid( row = 1, column = 0, padx = 10 )
        self.inputAzimuth.grid( row = 0, column = 2, padx = 10 )
        self.inputElevation.grid( row = 1, column = 2, padx = 10 )

        self.printbutton        = tk.Button( self.positions, text = "Enter", command = self.input )
        self.printbutton.pack( padx = 20, pady = 10, side = 'right' )

        # COLUMN 1 WIDGETS
        self.clock_label        = tk.Label( tabSelect, font= ('Arial', 14))
        self.clock_label.grid(row = 0, column = 1, padx = 20 , pady = 10, sticky=(NW, E))
        self.quickButton        = tk.Frame( tabSelect )
        self.quickButton.grid(row = 1, column = 1, padx = 20, pady = 10, sticky=(S))
        self.EmargencyStop      = tk.Button(self.quickButton, text = "Emargency Stop", font = ('Arial', 16 ) , bg = 'red', fg = 'white', command= self.Estop, width=15)
        self.Park               = tk.Button(self.quickButton, text = "Park", font = ('Arial', 16) , bg = 'blue', fg = 'white', command = self.park, width=15)
        self.openFreeWriting    = tk.Button(self.quickButton, text = "Open Free Writing" ,font = ('Arial', 16 ), command= self.freewriting, width=15)
       
        self.EmargencyStop.pack( pady = 5 )
        self.Park.pack( pady = 5 )
        self.openFreeWriting.pack( pady = 5 )

        # COLUMN 2 WIDGETS (Framed)
        self.spectrumFrame = tk.LabelFrame(tabSelect, text = "Placeholder Text")
        self.spectrumFrame.grid(row = 0, column = 2, padx = 20, pady = 10, sticky=(NSEW), rowspan=2)
        self.spectrumFrame.rowconfigure(0, weight=1)
        self.spectrumFrame.rowconfigure(1, weight=1)
        self.spectrumFrame.columnconfigure(0, weight=1)
        self.spectrumFrame.columnconfigure(1, weight=1)

        # MATPLOTLIB GRAPH
        fig, self.ax = plt.subplots()
        self.spectrumDisplay = FigureCanvasTkAgg(fig, master=self.spectrumFrame)
        self.spectrumDisplay.get_tk_widget().grid(row = 0, column = 0)
        self.setAnalyzerPlotLimits(xmin = 0, xmax=20e9)

        # MEASUREMENT COMMANDS
        self.measurementTab = ttk.Notebook(self.spectrumFrame)
        tab1 = ttk.Frame(self.measurementTab)
        tab2 = ttk.Frame(self.measurementTab)
        tab3 = ttk.Frame(self.measurementTab)
        self.measurementTab.add(tab1, text="Freq")
        self.measurementTab.add(tab2, text="BW")
        self.measurementTab.add(tab3, text="Amp")
        self.measurementTab.grid(row=0, column=1, sticky=NSEW)

        # MEASUREMENT TAB 1 (FREQUENCY)
        centerFreqFrame = ttk.LabelFrame(tab1, text="Center Frequency")
        centerFreqFrame.grid(row=0, column=0)
        centerFreqEntry = ttk.Entry(centerFreqFrame)
        centerFreqEntry.pack()

        spanFrame = ttk.LabelFrame(tab1, text="Span")
        spanFrame.grid(row=1, column=0)
        spanEntry = ttk.Entry(spanFrame)
        spanEntry.pack()
        spanSweptButton = ttk.Radiobutton(spanFrame, variable=spanType, text = "Swept Span", value='swept')
        spanSweptButton.pack(anchor=W)
        spanZeroButton = ttk.Radiobutton(spanFrame, variable=spanType, text = "Zero Span", value='zero')
        spanZeroButton.pack(anchor=W)
        spanFullButton = ttk.Button(spanFrame, text = "Full Span")
        spanFullButton.pack(anchor=S, fill=BOTH)

        startFreqFrame = ttk.LabelFrame(tab1, text="Start Frequency")
        startFreqFrame.grid(row=2, column=0)
        startFreqEntry = ttk.Entry(startFreqFrame)
        startFreqEntry.pack()

        stopFreqFrame = ttk.LabelFrame(tab1, text="Stop Frequency")
        stopFreqFrame.grid(row=3, column=0)
        stopFreqEntry = ttk.Entry(stopFreqFrame)
        stopFreqEntry.pack()

        # MEASUREMENT TAB 2 (BANDWIDTH)
        rbwFrame = ttk.LabelFrame(tab2, text="Res BW")
        rbwFrame.grid(row=0, column=0)
        rbwEntry = ttk.Entry(rbwFrame)
        rbwEntry.pack()
        rbwAutoButton = ttk.Radiobutton(rbwFrame, variable=rbwType, text="Auto", value='auto')
        rbwAutoButton.pack(anchor=W)
        rbwManButton = ttk.Radiobutton(rbwFrame, variable=rbwType, text="Manual", value='manual')
        rbwManButton.pack(anchor=W)
        
        vbwFrame = ttk.LabelFrame(tab2, text="Video BW")
        vbwFrame.grid(row=1, column=0)
        vbwEntry = ttk.Entry(vbwFrame)
        vbwEntry.pack()
        vbwAutoButton = ttk.Radiobutton(vbwFrame, variable=vbwType, text="Auto", value='auto')
        vbwAutoButton.pack(anchor=W)
        vbwManButton = ttk.Radiobutton(vbwFrame, variable=vbwType, text="Manual", value='manual')
        vbwManButton.pack(anchor=W)

        bwRatioFrame = ttk.LabelFrame(tab2, text="VBW:RBW")
        bwRatioFrame.grid(row=2, column=0)
        bwRatioEntry = ttk.Entry(bwRatioFrame)
        bwRatioEntry.pack()
        bwRatioAutoButton = ttk.Radiobutton(bwRatioFrame, variable=bwRatioType, text="Auto", value='auto')
        bwRatioAutoButton.pack(anchor=W)
        bwRatioManButton = ttk.Radiobutton(bwRatioFrame, variable=bwRatioType, text="Manual", value='manual')
        bwRatioManButton.pack(anchor=W)

        rbwFilterShapeFrame = ttk.LabelFrame(tab2, text="RBW Filter Shape")
        rbwFilterShapeFrame.grid(row=3, column=0)
        rbwFilterShapeCombo = ttk.Combobox(rbwFilterShapeFrame, textvariable=rbwFilterShape, values = ["Gaussian", "Flattop"])
        rbwFilterShapeCombo.pack(anchor=W)

        rbwFilterTypeFrame = ttk.LabelFrame(tab2, text="RBW Filter Type")
        rbwFilterTypeFrame.grid(row=4, column=0)
        rbwFilterTypeCombo = ttk.Combobox(rbwFilterTypeFrame, textvariable=rbwFilterType, values = ["-3 dB (Normal)", "-6 dB", "Impulse", "Noise"])
        rbwFilterTypeCombo.pack(anchor=W)

        # MEASUREMENT TAB 3 (AMPLITUDE)
        refLevelFrame = ttk.LabelFrame(tab3, text="Ref Level")
        refLevelFrame.grid(row=0, column=0)
        refLevelEntry = ttk.Entry(refLevelFrame)
        refLevelEntry.pack()

        yScaleFrame = ttk.LabelFrame(tab3, text="Scale/Division")
        yScaleFrame.grid(row=1, column=0)
        yScaleEntry = ttk.Entry(yScaleFrame)
        yScaleEntry.pack()

        numDivFrame = ttk.LabelFrame(tab3, text="Number of Divisions")
        numDivFrame.grid(row=2, column=0)
        numDivEntry = ttk.Entry(numDivFrame)
        numDivEntry.pack()

        attenFrame = ttk.LabelFrame(tab3, text="Mech Atten")
        attenFrame.grid(row=3, column=0)
        attenEntry = ttk.Entry(attenFrame)
        attenEntry.pack()
        attenAutoButton = ttk.Radiobutton(attenFrame, variable=attenType, text="Auto", value='auto')
        attenAutoButton.pack(anchor=W)
        attenManButton = ttk.Radiobutton(attenFrame, variable=attenType, text="Manual", value='manual')
        attenManButton.pack(anchor=W)


        # TOGGLE BUTTON
        self.placeholder = tk.Button(self.spectrumFrame, text="Placeholder Text", command=lambda:self.t1.start())
        self.placeholder.grid(row=1, column=0, sticky=NSEW)
        self.spectrumToggle = tk.Button(self.spectrumFrame, text="Toggle Analyzer", command=lambda:self.toggleAnalyzerDisplay())
        self.spectrumToggle.grid(row=1, column=1, sticky=NSEW)

    def initAnalyzerPlotLimits(self):
        if self.Vi.isSessionOpen == FALSE:
            print("Error: Session to the analyzer is not open.")
            return RETURN_ERROR
        startFreq =         self.Vi.openRsrc.query_ascii_values(":SENS:FREQ:START?")
        stopFreq =          self.Vi.openRsrc.query_ascii_values(":SENS:FREQ:STOP?")
        centerFreq =        self.Vi.openRsrc.query_ascii_values(":SENS:FREQ:CENTER?")
        span =              self.Vi.openRsrc.query_ascii_values(":SENS:FREQ:SPAN?")
        rbw =               self.Vi.openRsrc.query_ascii_values(":SENS:BANDWIDTH:RESOUTION?")
        vbw =               self.Vi.openRsrc.query_ascii_values(":SENS:BANDWIDTH:VIDEO?")
        ref =               self.Vi.openRsrc.query_ascii_values(":DISP:WINDOW:TRACE:Y:RLEVEL?")
        numDivisions =      self.Vi.openRsrc.query_ascii_values(":DISP:WINDOW:TRACE:Y:NDIV?")
        scalePerDivision =  self.Vi.openRsrc.query_ascii_values(":DISP:WINDOW:TRACE:Y:PDIV?")

        self.setAnalyzerPlotLimits(xmin=startFreq, xmax=stopFreq, ymin=ref-numDivisions*scalePerDivision, ymax=ref)

    def setAnalyzerPlotLimits(self, **kwargs):
        if kwargs.get("xmin") in kwargs.values() and kwargs["xmax"]:
            self.ax.set_xlim(kwargs["xmin"], kwargs["xmax"])
        if kwargs.get("ymin") in kwargs.values() and kwargs.get("ymax") in kwargs.values():
            self.ax.set_ylim(kwargs["ymin"], kwargs["ymax"])
        self.ax.margins(0, 0.05)
        self.ax.grid(visible=TRUE, which='major', axis='both', linestyle='-.')
        print("set values")
        return RETURN_SUCCESS

    def initAnalyzerDisplay(self):
        if self.Vi.isSessionOpen == FALSE:
            print("Error: Session to the analyzer is not open.")
            return RETURN_ERROR
        # Reset analyzer state
        self.Vi.openRsrc.write("*RST")
        self.Vi.openRsrc.write("*WAI")
        # is buffer large enough?
        self.Vi.openRsrc.write(":INIT:CONT OFF")
        self.Vi.openRsrc.write(":FETCh:SAN?")
        buffer = self.Vi.openRsrc.read_ascii_values()
        statusCode = self.Vi.openRsrc.last_status
        print(f"Buffer size: {sys.getsizeof(buffer)} bytes")
        print(f"Status byte: {hex(statusCode)}.")
        # PyVISA reads until a termination is received, not specified bytes like NI-VISA unless resource.read_bytes() is called.
        # As a result, this test may not be necessary but edge cases for the maximum return value of resource.read() must be tested.
        if (statusCode == constants.VI_SUCCESS_MAX_CNT or statusCode == constants.VI_SUCCESS_TERM_CHAR):
            print(f"Error {hex(statusCode)}: viRead did not return termination character or END indicated. Increase read bytes to fix.")
            self.Vi.openRsrc.flush(constants.VI_READ_BUF)
            return RETURN_ERROR
        # Set widget values (WIP)

        # read stuff...
        while (TRUE):
            self.ax.clear()
            buffer = self.Vi.openRsrc.query_ascii_values(":READ:SAN?")
            xAxis = buffer[::2]
            yAxis = buffer[1::2]
            self.ax.plot(xAxis, yAxis)
            self.spectrumDisplay.draw()
            time.sleep(0.5)

        # wait for response
        # read/log
        # loop
        print("end of loop")
        return
    
    def toggleAnalyzerDisplay(self):
        """Checks if thread t1 is alive. 
        If yes, sets analyzerKillFlag TRUE so initAnalyzerDisplay returns and t1 can be joined. 
        If no, sets analyzerKillFlag FALSE and starts t1 which calls initAnalyzerDisplay.

        Returns:
            Literal: 0 on success, 1 on error
        """
        if self.t1.is_alive():
            print("Disabling spectrum display.")
            self.analyzerKillFlag = TRUE
            self.t1.join()
            if self.t1.is_alive():
                print("Error: thread.join() timed out. Thread target initAnalyzerDisplay() still active.")
                return RETURN_ERROR
            else:
                print("Spectrum display successfully disabled.")
                return RETURN_SUCCESS
        else:
            print("Starting spectrum display.")
            self.analyzerKillFlag = FALSE
            self.t1.start()
            return RETURN_SUCCESS
            

    def update_time( self ):
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.clock_label.config(text=current_time)
        self.root.after(1000, self.update_time)

    def freewriting(self):
        """Frexible serial communication Window
        """
        if self.motor.port != self.port_selection.get()[:4]: 
            portName = self.port_selection.get()
            self.motor.port = portName[:4]
            self.motor.OpenSerial()
        self.motor.freeInput()

    def Estop(self):
        
        if self.motor.port != self.port_selection.get()[:4]: 
            portName = self.port_selection.get()
            self.motor.port = portName[:4]
            self.motor.OpenSerial()
        self.motor.EmargencyStop()
    
    def park( self ):
        if self.motor.port != self.port_selection.get()[:4]: 
            portName = self.port_selection.get()
            self.motor.port = portName[:4]
            self.motor.OpenSerial()
        self.motor.Park()

    def input(self):
        if self.motor.port != self.port_selection.get()[:4]: 
            portName = self.port_selection.get()
            self.motor.port = portName[:4]
            self.motor.OpenSerial()
        self.motor.userAzi = self.inputAzimuth.get()
        self.motor.userEle = self.inputElevation.get()
        self.motor.readUserInput()      


    def quit(self):
        self.motor.CloseSerial()
        self.root.destroy()

    def updateOutput( self, oFile, root ):
        def saveData():
            # position information is not updated now, path from motor servo is needed. 
            newData = [time.strftime("%Y-%m-%d %H:%M:%S") , 0 , 0]
            #

            oFile.add( newData )
            newData = []
        
        buttonFrame = tk.Frame( root )
        buttonFrame.pack( side = 'right')
        saveButton = tk.Button( buttonFrame , text = "Save", font = ('Arial', 10), width=10, command = saveData )
        saveButton.pack()
        get_logfile = tk.Button( buttonFrame, text = "Get Log File", font = ('Arial', 10),width=10, command = oFile.printData )
        get_logfile.pack()


root = tk.Tk()                  # Root tkinter interface (contains DFS_Window and standard output console)
DFS_Window = FrontEnd(root)     #

# Generate textbox to print standard output/error
stdoutFrame = tk.Frame(root)
stdoutFrame.pack(fill=BOTH)
stdoutFrame.rowconfigure(0, weight=1)
stdoutFrame.columnconfigure(0, weight=1)
console = tk.Text(stdoutFrame, height=20)
console.grid(column=0, row=0, sticky=(N, S, E, W))

def redirector(inputStr):
    console.insert(INSERT, inputStr)

# When sys.std***.write is called (such as on print), call redirector to print in textbox
sys.stdout.write = redirector
sys.stderr.write = redirector

# Limit window size to the minimum size on generation
root.update()
root.minsize(root.winfo_width(), root.winfo_height())
root.protocol("WM_DELETE_WINDOW", DFS_Window.on_closing )

root.mainloop()
