# PRIVATE LIBRARIES
import threading
from frontendio import *
from timestamp import *

# OTHER MODULES
import sys
from pyvisa import attributes
import re
import logging

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
AUTO = 'auto'
MANUAL = 'manual'
SWEPT = 'swept'
ZERO = 'zero'

# THREADING EVENTS
visaLock = threading.RLock()

# LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def isNumber(input):
    try:
        float(f"{input}0")
        return TRUE
    except:
        return FALSE
    
def clearAndSetEntry(widget, arg):
    """Clear the ttk::entry passed in 'widget' and replace it with 'arg' in scientific notation if possible.
    The N9040B and other instruments will return queries in square brackets which python interprets as a list.

    Args:
        widget (ttk.Entry): Widget to clear/set.
        arg (list): Value in 'arg[0]' will be taken to set the widget in scientific notation. If that fails, attempt to set the widget to 'arg'.
    """
    widget.delete(0, END)
    # Try to convert string in list to scientific notation
    try:
        arg = float(arg[0])
        widget.insert(0, "{:e}".format(arg))
        logging.debug(f"clearAndSetEntry passed argument {arg} to {widget}.")
    except:
        widget.insert(0, arg)
        logging.debug(f"Scientific notation conversion failed. clearAndSetEntry passed argument {arg} to {widget}.")

class FrontEnd():
    def __init__(self, root):
        """Initializes the top level tkinter interface
        """

        # CONSTANTS
        self.SELECT_TERM_VALUES = ['Line Feed - \\n', 'Carriage Return - \\r']
        self.RBW_FILTER_SHAPE_VALUES = ['Gaussian', 'Flattop']
        self.RBW_FILTER_TYPE_VALUES = ["-3 dB (Normal)", "-6 dB", "Impulse", "Noise"]

        # VARIABLES
        self.timeout = TIMEOUT_DEF           # VISA timeout value
        self.chunkSize = CHUNK_SIZE_DEF      # Bytes to read from buffer
        self.instrument = ''                 # ID of the currently open instrument. Used only in resetConfigWidgets method

        # FLAGS
        self.analyzerKillFlag = TRUE

        # TKINTER VARIABLES
        self.sendEnd = BooleanVar()
        self.sendEnd.set(TRUE)
        self.enableTerm = BooleanVar()
        self.enableTerm.set(FALSE)

        # REGISTER CALLBACK FUNCTIONS
        self.isNumWrapper = root.register(isNumber)

        self.Vi = VisaControl()
        self.Vi.openRsrcManager()

        oFile = DataManagement()
        tabControl = ttk.Notebook(root) 
  
        self.tab1 = ttk.Frame(tabControl) 
        self.tab2 = ttk.Frame(tabControl) 

        tabControl.add(self.tab1, text ='Control') 
        tabControl.add(self.tab2, text ='Config') 
        tabControl.bind('<Button-1>', lambda event: self.resetConfigWidgets(event))
        tabControl.pack(expand = 1, fill ="both") 

        self.controlTab()
        self.updateOutput( oFile, root )
        self.configTab()

        # Generate thread to handle live data plot in background
        t1 = threading.Thread(target=self.loopAnalyzerDisplay, daemon=TRUE)
        t1.start()

        root.after(1000, self.update_time )
    
    def on_closing( self ):
        """ Ask to close serial communication when 'X' button is pressed """
        SaveCheck = messagebox.askokcancel( title = "Window closing", message = "Do you want to close communication to the motor?" )
        if SaveCheck is True:      
            while (self.motor.ser.is_open):
                self.motor.CloseSerial()
        else:
            pass
    
        root.quit()

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
            logging.info('Searching for resources...')
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
        self.timeoutWidget = ttk.Spinbox(self.configFrame, from_=TIMEOUT_MIN, to=TIMEOUT_MAX, increment=100, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.timeoutWidget.set(self.timeout)
        self.chunkSizeLabel = ttk.Label(self.configFrame, text = 'Chunk size (Bytes)')
        self.chunkSizeWidget = ttk.Spinbox(self.configFrame, from_=CHUNK_SIZE_MIN, to=CHUNK_SIZE_MAX, increment=10240, validate="key", validatecommand=(self.isNumWrapper, '%P'))
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
    

    def resetConfigWidgets(self, event):
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
        """Issues VISA commands to set config and applies changes made in the SCPI configuration frame to variables timeout and chunkSize (for resetConfigWidgets)

        Args:
            timeoutArg (string): Argument received from timeout widget which will be tested for type int and within range
            chunkSizeArg (string): Argument received from chunkSize widget which will be tested for type int and within range

        Raises:
            TypeError: ttk::spinbox get() does not return type int or integer out of range for respective variable

        Returns:
            Literal (int): 0 on success, 1 on error.
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
        # Call self.Vi.setConfig and if successful, print output and set variables for resetConfigWidgets
        if self.Vi.setConfig(timeoutArg, chunkSizeArg, self.sendEnd.get(), self.enableTerm.get(), termChar) == RETURN_SUCCESS:
            self.timeout = timeoutArg
            self.chunkSize = chunkSizeArg
            logging.info(f'Timeout: {self.Vi.openRsrc.timeout}, Chunk size: {self.Vi.openRsrc.chunk_size}, Send EOI: {self.Vi.openRsrc.send_end}, Termination: {repr(self.Vi.openRsrc.write_termination)}')
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
        spectrumFrame = tk.LabelFrame(tabSelect, text = "Placeholder Text")
        spectrumFrame.grid(row = 0, column = 2, padx = 20, pady = 10, sticky=(NSEW), rowspan=2)
        spectrumFrame.rowconfigure(0, weight=1)
        spectrumFrame.rowconfigure(1, weight=1)
        spectrumFrame.columnconfigure(0, weight=1)
        spectrumFrame.columnconfigure(1, weight=1)

        # MATPLOTLIB GRAPH
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot()
        self.ax.set_title("Spectrum Plot")
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Power Spectral Density (dBm/RBW)")
        self.spectrumDisplay = FigureCanvasTkAgg(self.fig, master=spectrumFrame)
        self.spectrumDisplay.get_tk_widget().grid(row = 0, column = 0)
        self.setAnalyzerPlotLimits(xmin = 0, xmax=20e9)

        # MEASUREMENT COMMANDS
        measurementTab = ttk.Notebook(spectrumFrame)
        tab1 = ttk.Frame(measurementTab)
        tab2 = ttk.Frame(measurementTab)
        tab3 = ttk.Frame(measurementTab)
        measurementTab.add(tab1, text="Freq")
        measurementTab.add(tab2, text="BW")
        measurementTab.add(tab3, text="Amp")
        measurementTab.grid(row=0, column=1, sticky=NSEW)

        # MEASUREMENT TAB 1 (FREQUENCY)
        self.centerFreqFrame = ttk.LabelFrame(tab1, text="Center Frequency")
        self.centerFreqFrame.grid(row=0, column=0)
        self.centerFreqEntry = ttk.Entry(self.centerFreqFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.centerFreqEntry.pack()

        self.spanFrame = ttk.LabelFrame(tab1, text="Span")
        self.spanFrame.grid(row=1, column=0)
        self.spanEntry = ttk.Entry(self.spanFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.spanEntry.pack()
        self.spanSweptButton = ttk.Radiobutton(self.spanFrame, variable=spanType, text = "Swept Span", value='swept')
        self.spanSweptButton.pack(anchor=W)
        self.spanZeroButton = ttk.Radiobutton(self.spanFrame, variable=spanType, text = "Zero Span", value='zero')
        self.spanZeroButton.pack(anchor=W)
        self.spanFullButton = ttk.Button(self.spanFrame, text = "Full Span")
        self.spanFullButton.pack(anchor=S, fill=BOTH)

        self.startFreqFrame = ttk.LabelFrame(tab1, text="Start Frequency")
        self.startFreqFrame.grid(row=2, column=0)
        self.startFreqEntry = ttk.Entry(self.startFreqFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.startFreqEntry.pack()

        self.stopFreqFrame = ttk.LabelFrame(tab1, text="Stop Frequency")
        self.stopFreqFrame.grid(row=3, column=0)
        self.stopFreqEntry = ttk.Entry(self.stopFreqFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.stopFreqEntry.pack()

        # MEASUREMENT TAB 2 (BANDWIDTH)
        self.rbwFrame = ttk.LabelFrame(tab2, text="Res BW")
        self.rbwFrame.grid(row=0, column=0)
        self.rbwEntry = ttk.Entry(self.rbwFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.rbwEntry.pack()
        self.rbwAutoButton = ttk.Radiobutton(self.rbwFrame, variable=rbwType, text="Auto", value=AUTO)
        self.rbwAutoButton.pack(anchor=W)
        self.rbwManButton = ttk.Radiobutton(self.rbwFrame, variable=rbwType, text="Manual", value=MANUAL)
        self.rbwManButton.pack(anchor=W)
        
        self.vbwFrame = ttk.LabelFrame(tab2, text="Video BW")
        self.vbwFrame.grid(row=1, column=0)
        self.vbwEntry = ttk.Entry(self.vbwFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.vbwEntry.pack()
        self.vbwAutoButton = ttk.Radiobutton(self.vbwFrame, variable=vbwType, text="Auto", value=AUTO)
        self.vbwAutoButton.pack(anchor=W)
        self.vbwManButton = ttk.Radiobutton(self.vbwFrame, variable=vbwType, text="Manual", value=MANUAL)
        self.vbwManButton.pack(anchor=W)

        self.bwRatioFrame = ttk.LabelFrame(tab2, text="VBW:RBW")
        self.bwRatioFrame.grid(row=2, column=0)
        self.bwRatioEntry = ttk.Entry(self.bwRatioFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.bwRatioEntry.pack()
        self.bwRatioAutoButton = ttk.Radiobutton(self.bwRatioFrame, variable=bwRatioType, text="Auto", value=AUTO)
        self.bwRatioAutoButton.pack(anchor=W)
        self.bwRatioManButton = ttk.Radiobutton(self.bwRatioFrame, variable=bwRatioType, text="Manual", value=MANUAL)
        self.bwRatioManButton.pack(anchor=W)

        self.rbwFilterShapeFrame = ttk.LabelFrame(tab2, text="RBW Filter Shape")
        self.rbwFilterShapeFrame.grid(row=3, column=0)
        self.rbwFilterShapeCombo = ttk.Combobox(self.rbwFilterShapeFrame, textvariable=rbwFilterShape, values = self.RBW_FILTER_SHAPE_VALUES)
        self.rbwFilterShapeCombo.pack(anchor=W)

        self.rbwFilterTypeFrame = ttk.LabelFrame(tab2, text="RBW Filter Type")
        self.rbwFilterTypeFrame.grid(row=4, column=0)
        self.rbwFilterTypeCombo = ttk.Combobox(self.rbwFilterTypeFrame, textvariable=rbwFilterType, values = self.RBW_FILTER_TYPE_VALUES)
        self.rbwFilterTypeCombo.pack(anchor=W)

        # MEASUREMENT TAB 3 (AMPLITUDE)
        self.refLevelFrame = ttk.LabelFrame(tab3, text="Ref Level")
        self.refLevelFrame.grid(row=0, column=0)
        self.refLevelEntry = ttk.Entry(self.refLevelFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.refLevelEntry.pack()

        self.yScaleFrame = ttk.LabelFrame(tab3, text="Scale/Division")
        self.yScaleFrame.grid(row=1, column=0)
        self.yScaleEntry = ttk.Entry(self.yScaleFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.yScaleEntry.pack()

        self.numDivFrame = ttk.LabelFrame(tab3, text="Number of Divisions")
        self.numDivFrame.grid(row=2, column=0)
        self.numDivEntry = ttk.Entry(self.numDivFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.numDivEntry.pack()

        self.attenFrame = ttk.LabelFrame(tab3, text="Mech Atten")
        self.attenFrame.grid(row=3, column=0)
        self.attenEntry = ttk.Entry(self.attenFrame, validate="key", validatecommand=(self.isNumWrapper, '%P'))
        self.attenEntry.pack()
        self.attenAutoButton = ttk.Radiobutton(self.attenFrame, variable=attenType, text="Auto", value=AUTO)
        self.attenAutoButton.pack(anchor=W)
        self.attenManButton = ttk.Radiobutton(self.attenFrame, variable=attenType, text="Manual", value=MANUAL)
        self.attenManButton.pack(anchor=W)

        # BIND WIDGETS
        self.centerFreqEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, centerfreq = self.centerFreqEntry.get()))
        self.spanEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, span = self.spanEntry.get()))
        self.startFreqEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, startfreq = self.startFreqEntry.get()))
        self.stopFreqEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, stopfreq = self.stopFreqEntry.get()))
        self.rbwEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, rbw = self.rbwEntry.get()))
        self.vbwEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, vbw = self.vbwEntry.get()))
        self.bwRatioEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, bwratio = self.bwRatioEntry.get()))
        self.refLevelEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, ref = self.refLevelEntry.get()))
        self.yScaleEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, yscale = self.yScaleEntry.get()))
        self.numDivEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, numdiv = self.numDivEntry.get()))
        self.attenEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, atten = self.attenEntry.get()))

        # TOGGLE BUTTON
        spectrumToggle = tk.Button(spectrumFrame, text="Toggle Analyzer", command=lambda:self.toggleAnalyzerDisplay())
        spectrumToggle.grid(row=1, column=1, sticky=NSEW)

    def initAnalyzerPlotLimits(self):
        if self.Vi.isSessionOpen() == FALSE:
            logging.error("Session to the analyzer is not open.")
            return RETURN_ERROR
        startFreq =         self.Vi.openRsrc.query_ascii_values(":SENS:FREQ:START?")
        stopFreq =          self.Vi.openRsrc.query_ascii_values(":SENS:FREQ:STOP?")
        # centerFreq =        self.Vi.openRsrc.query_ascii_values(":SENS:FREQ:CENTER?")
        # span =              self.Vi.openRsrc.query_ascii_values(":SENS:FREQ:SPAN?")
        # rbw =               self.Vi.openRsrc.query_ascii_values(":SENS:BANDWIDTH:RESOUTION?")
        # vbw =               self.Vi.openRsrc.query_ascii_values(":SENS:BANDWIDTH:VIDEO?")
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
        return RETURN_SUCCESS
    
    def setAnalyzerThreadHandler(self, event, **kwargs):
        _dict = {}
        for key in kwargs:
            _dict[key] = kwargs.get(key)
        thread = threading.Thread(target=self.setAnalyzerValue, kwargs=_dict)
        thread.start()
    
    def setAnalyzerValue(self, **kwargs):
        global visaLock
        _list = []

        if self.Vi.isSessionOpen() == FALSE:
            logging.error("Session to the Analyzer is not open.")
            return

        # Acquire thread lock
        # Wait for the analyzer display loop to complete so that visa commands from the loop do not interfere with ones sent in this method
        visaLock.acquire()

        if "centerfreq" in kwargs:
            _dict = {
                'command': ':SENS:FREQ:CENTER',
                'arg': kwargs.get("centerfreq"),
                'widget': self.centerFreqEntry
            }
            _list.append(_dict)
        if "span" in kwargs:
            _dict = {
                'command': ':SENS:FREQ:SPAN',
                'arg': kwargs.get("span"),
                'widget': self.spanEntry
            }
            _list.append(_dict)
        if "startfreq" in kwargs:
            _dict = {
                'command': ':SENS:FREQ:START',
                'arg': kwargs.get("startfreq"),
                'widget': self.startFreqEntry
            }
            _list.append(_dict)
        if "stopfreq" in kwargs:
            _dict = {
                'command': ':SENS:FREQ:STOP',
                'arg': kwargs.get("stopfreq"),
                'widget': self.stopFreqEntry
            }
            _list.append(_dict)
        if "rbw" in kwargs:
            _dict = {
                'command': ':SENS:BANDWIDTH:RESOLUTION',
                'arg': kwargs.get("rbw"),
                'widget': self.rbwEntry
            }
            _list.append(_dict)
        if "vbw" in kwargs:
            _dict = {
                'command': ':SENS:BANDWIDTH:VIDEO',
                'arg': kwargs.get("vbw"),
                'widget': self.vbwEntry
            }
            _list.append(_dict)
        if "bwratio" in kwargs:
            _dict = {
                'command': ':SENS:BANDWIDTH:VIDEO:RATIO',
                'arg': kwargs.get("bwratio"),
                'widget': self.bwRatioEntry
            }
            _list.append(_dict)
        if "ref" in kwargs:
            _dict = {
                'command': ':DISP:WINDOW:TRACE:Y:RLEVEL',
                'arg': kwargs.get("ref"),
                'widget': self.refLevelEntry
            }
            _list.append(_dict)
        if "numdiv" in kwargs:
            _dict = {
                'command': ':DISP:WINDOW:TRACE:Y:NDIV',
                'arg': kwargs.get("numdiv"),
                'widget': self.numDivEntry
            }
            _list.append(_dict)
        if "yscale" in kwargs:
            _dict = {
                'command': ':DISP:WINDOW:TRACE:Y:PDIV',
                'arg': kwargs.get("yscale"),
                'widget': self.yScaleEntry
            }
            _list.append(_dict)
        if "atten" in kwargs:
            _dict = {
                'command': ':SENS:POWER:RF:ATTENUATION',
                'arg': kwargs.get("atten"),
                'widget': self.attenEntry
            }

        # TODO: make these do something
        # SPAN TYPE
        if kwargs.get("spantype") == SWEPT:
            self.spanSweptButton.select()
        elif kwargs.get("spantype") == ZERO:
            self.spanZeroButton.select()
        # RBW TYPE
        if kwargs.get("rbwtype") == AUTO:
            self.rbwAutoButton.select()
        elif kwargs.get("rbwtype") == MANUAL:
            self.rbwManButton.select()
        # VBW TYPE
        if kwargs.get("vbwtype") == AUTO:
            self.vbwAutoButton.select()
        elif kwargs.get("vbwtype") == MANUAL:
            self.vbwManButton.select()
        # BW RATIO TYPE
        if kwargs.get("bwratiotype") == AUTO:
            self.bwRatioAutoButton.select()
        elif kwargs.get("bwratiotype") == MANUAL:
            self.bwRatioManButton.select()
        # RBW FILTER SHAPE
        if kwargs.get("rbwfiltershape") == self.RBW_FILTER_SHAPE_VALUES[0]:
            self.rbwFilterShapeCombo.set(self.RBW_FILTER_SHAPE_VALUES[0])
        elif kwargs.get("rbwfiltershape") == self.RBW_FILTER_SHAPE_VALUES[1]:
            self.rbwFilterShapeCombo.set(self.RBW_FILTER_SHAPE_VALUES[1])
        # RBW FILTER TYPE
        if kwargs.get("rbwfiltertype") == self.RBW_FILTER_TYPE_VALUES[0]:
            self.rbwFilterTypeCombo.set(self.RBW_FILTER_TYPE_VALUES[0])
        elif kwargs.get("rbwfiltertype") == self.RBW_FILTER_TYPE_VALUES[1]:
            self.rbwFilterTypeCombo.set(self.RBW_FILTER_TYPE_VALUES[1])
        # ATTENUATION TYPE
        if kwargs.get("attentype") == AUTO:
            self.attenAutoButton.select()
        elif kwargs.get("attentype") == MANUAL:
            self.attenManButton.select()

        # EXECUTE COMMANDS
        logging.debug(f"setAnalyzerValue generated list of dictionaries '_list' with value {_list}")
        for x in _list:
            try:
                # Set widgets without issuing a parameter to command
                if x['arg'] is None:
                    buffer = self.Vi.openRsrc.query_ascii_values(f'{x['command']}?')
                    logging.debug(f"Command {x['command']}? returned {buffer}")
                    clearAndSetEntry(x['widget'], buffer)
                # Issue a command with parameter and then query that parameter to set widget
                else:    
                    self.Vi.openRsrc.write(f'{x['command']} {x['arg']}')
                    buffer = self.Vi.openRsrc.query_ascii_values(f'{x['command']}?')
                    logging.debug(f"Command {x['command']}? returned {buffer}")
                    clearAndSetEntry(x['widget'], buffer)
            except:
                logging.fatal(f"VISA ERROR {hex(self.Vi.openRsrc.last_status)}. ATTEMPTING TO RESET ANALYZER STATE")
                self.Vi.resetAnalyzerState()
                logging.fatal("Analyzer state reset.")
        # Release thread lock
        visaLock.release()
        return

    def loopAnalyzerDisplay(self):
        global visaLock

        # Wait for user to open a session to the spectrum analyzer
        while TRUE:
            if self.Vi.isSessionOpen() == FALSE:
                # Prevent this thread from taking up too much utilization
                time.sleep(1)
                continue
            else:
                break

        # Maintain this loop to prevent fatal error if the connected device is not a spectrum analyzer.
        errorFlag = TRUE
        while errorFlag:
            try:
                visaLock.acquire()
                self.Vi.resetAnalyzerState()
                self.Vi.testBufferSize()
                # Set widget values
                self.setAnalyzerValue(
                    centerfreq=None,
                    span=None,
                    startfreq=None,
                    stopfreq=None,
                    rbw=None,
                    vbw=None,
                    bwratio=None,
                    ref=None,
                    numdiv=None,
                    yscale=None,
                    atten=None,
                )
                visaLock.release()
                errorFlag = FALSE
            except:
                logging.warning(f"VISA error with status code {hex(self.Vi.openRsrc.last_status)}. Attempting to reset analyzer state.")
                visaLock.release()
                time.sleep(8)

        # Main analyzer loop
        # TODO: variable time.sleep based on analyzer sweep time
        while TRUE:
            if not self.analyzerKillFlag:
                visaLock.acquire()
                try:
                    self.ax.clear()
                    buffer = self.Vi.openRsrc.query_ascii_values(":READ:SAN?")
                    xAxis = buffer[::2]
                    yAxis = buffer[1::2]
                    self.ax.plot(xAxis, yAxis)
                    self.ax.grid(visible=True)
                    self.spectrumDisplay.draw()
                except:
                    logging.fatal(f"VISA ERROR {hex(self.Vi.openRsrc.last_status)}. ATTEMPTING TO RESET ANALYZER STATE")
                    self.Vi.resetAnalyzerState()
                    logging.fatal("Analyzer state reset.")
                visaLock.release()
                time.sleep(0.5)
            else:
                # Prevent this thread from taking up too much utilization
                time.sleep(1)
                
        return
    
    def toggleAnalyzerDisplay(self):
        """sets analyzerKillFlag != analyzerKillFlag to control loopAnalyzerDisplay()
        """
        if self.Vi.isSessionOpen() == FALSE:
            logging.info("Error: Session to the analyzer is not open.")
            self.analyzerKillFlag = TRUE
            return
        
        if self.analyzerKillFlag:
            logging.info("Starting spectrum display.")
            self.analyzerKillFlag = FALSE
        else:
            logging.info("Disabling spectrum display.")
            self.analyzerKillFlag = TRUE
            
    # TODO: Cleanup boilerplate code below

    def update_time( self ):
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.clock_label.config(text=current_time)
        root.after(1000, self.update_time)

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
        root.destroy()

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
root.title('RF-DFS')

# Generate textbox to print standard output/error
stdoutFrame = tk.Frame(root)
stdoutFrame.pack(fill=BOTH, side=BOTTOM)
stdoutFrame.rowconfigure(0, weight=1)
stdoutFrame.columnconfigure(0, weight=1)
console = tk.Text(stdoutFrame, height=20)
console.grid(column=0, row=0, sticky=(N, S, E, W))

def redirector(inputStr):
    console.insert(INSERT, inputStr)
    console.yview(MOVETO, 1)

# When sys.std***.write is called (such as on print), call redirector to print in textbox
sys.stdout.write = redirector
sys.stderr.write = redirector

DFS_Window = FrontEnd(root)

# Limit window size to the minimum size on generation
root.update()
root.minsize(root.winfo_width(), root.winfo_height())
root.protocol("WM_DELETE_WINDOW", DFS_Window.on_closing )

root.mainloop()
