# PRIVATE LIBRARIES
import threading
from frontendio import *
from timestamp import *

# OTHER MODULES
import sys
from pyvisa import attributes
import re
import logging
import decimal

# MATPLOTLIB
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# TKINTER
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import colorchooser
from tkinter.ttk import *
from ttkthemes import ThemedTk
 
# CONSTANTS
RETURN_ERROR = 1
RETURN_SUCCESS = 0
CHUNK_SIZE_DEF = 20480     # Default byte count to read when issuing viRead
CHUNK_SIZE_MIN = 1024
CHUNK_SIZE_MAX = 1048576  # Max chunk size allowed
TIMEOUT_DEF = 2000        # Default VISA timeout value
TIMEOUT_MIN = 1000        # Minimum VISA timeout value
TIMEOUT_MAX = 25000       # Maximum VISA timeout value
AUTO = 1
MANUAL = 0
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
    
def clearAndSetWidget(widget, arg):
    """Clear the ttk::widget passed in 'widget' and replace it with 'arg' in engineering notation if possible.
    The N9040B and other instruments will return queries in square brackets which python interprets as a list.

    Args:
        widget (ttk.Widget or Tkinter_variable): Widget to clear/set.
        arg (list, str): Value in 'arg[0]' will be taken to set the widget in engineering notation. If that fails, attempt to set the widget to 'arg'.
    """
    logging.debug(f"clearAndSetWidget received widget {widget} and argument {arg}")
    # Set radiobutton widgets
    if isinstance(widget, (BooleanVar, IntVar, StringVar)):
        try:
            arg = bool(arg[0])
            widget.set(arg)
        except:
            widget.set(arg)
        finally:
            logging.debug(f"clearAndSetWidget passed argument {arg} ({type(arg)}) to {widget} ({type(widget)})")
    # Set entry/combobox widgets
    if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox)):
        widget.delete(0, END)
        # Try to convert string in list to engineering notation
        try:
            arg = float(arg[0])
            x = decimal.Decimal(arg)
            x = x.normalize().to_eng_string()
            widget.insert(0, x)
            logging.debug(f"clearAndSetWidget passed argument {x} ({type(x)}) to {widget} ({type(widget)}).")
        except:
            widget.insert(0, arg)
            logging.debug(f"clearAndSetWidget passed argument {arg} ({type(arg)}) to {widget} ({type(widget)}).")


class FrontEnd():
    def __init__(self, root, Vi):
        """Initializes the top level tkinter interface
        """
        # CONSTANTS
        self.SELECT_TERM_VALUES = ('Line Feed - \\n', 'Carriage Return - \\r')
        # VARIABLES
        self.timeout = TIMEOUT_DEF           # VISA timeout value
        self.chunkSize = CHUNK_SIZE_DEF      # Bytes to read from buffer
        self.instrument = ''                 # ID of the currently open instrument. Used only in resetConfigWidgets method
        # TKINTER VARIABLES
        self.sendEnd = BooleanVar()
        self.sendEnd.set(TRUE)
        self.enableTerm = BooleanVar()
        self.enableTerm.set(FALSE)

        self.Vi = Vi
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

        def onConnectPress(*args):
            """Connect to the VISA resource and update the string in self.instrument
            """
            if self.Vi.connectToRsrc(self.instrSelectBox.get()) == RETURN_SUCCESS:
                self.instrument = self.instrSelectBox.get()
                self.scpiApplyConfig(self.timeoutWidget.get(), self.chunkSizeWidget.get())
        def onRefreshPress():
            """Update the values in the SCPI instrument selection box
            """
            logging.info('Searching for resources...')
            self.instrSelectBox['values'] = self.Vi.rm.list_resources()
            self.motorSelectBox['values'] = list(serial.tools.list_ports.comports())
        def onEnableTermPress():
            if self.enableTerm.get():
                self.selectTermWidget.config(state='readonly')
            else:
                self.selectTermWidget.config(state='disabled')  


        # INSTRUMENT SELECTION FRAME & GRID
        # ISSUE: Apply changes should only be pressable when changes are detected 
        connectFrame = ttk.LabelFrame(tabSelect, borderwidth = 2, text = "Instrument Connections")
        connectFrame.grid(column=0, row=0, padx=20, pady=20, columnspan=3, ipadx=5, ipady=5)
        ttk.Label(
            connectFrame, text = "SCPI:", font = ("Times New Roman", 10)).grid(
            column = 0, row = 0, padx = 5, sticky=W) 
        ttk.Label(
            connectFrame, text = "Motor:", font = ("Times New Roman", 10)).grid(
            column = 0, row = 1, padx = 5, sticky=W) 
        ttk.Label(
            connectFrame, text = "PLC:", font = ("Times New Roman", 10)).grid(
            column = 0, row = 2, padx = 5, sticky=W) 
        self.instrSelectBox = ttk.Combobox(connectFrame, values = self.Vi.rm.list_resources(), width=40)
        self.instrSelectBox.grid(row = 0, column = 1, padx = 10 , pady = 5)
        self.motorSelectBox = ttk.Combobox(connectFrame, values = list(serial.tools.list_ports.comports()), width=40)
        self.motorSelectBox.grid(row = 1, column = 1, padx = 10, pady = 5)
        self.plcSelectBox = ttk.Combobox(connectFrame, values = list(serial.tools.list_ports.comports()), width=40)
        self.plcSelectBox.grid(row = 2, column = 1, padx = 10, pady = 5)
        self.refreshButton = ttk.Button(connectFrame, text = "Refresh All", command = lambda:onRefreshPress())
        self.refreshButton.grid(row = 2, column = 2, padx=5)

        self.instrSelectBox.bind("<<ComboboxSelected>>", lambda event: onConnectPress(event))
        self.motorSelectBox.bind("<<ComboboxSelected>>", lambda event:'')
        self.plcSelectBox.bind("<<ComboboxSelected>>", lambda event:'')

        # VISA CONFIGURATION FRAME
        self.configFrame = ttk.LabelFrame(tabSelect, borderwidth = 2, text = "VISA Configuration")
        self.configFrame.grid(row = 1, column = 0, padx=20, pady=10, sticky=tk.N)
        self.timeoutLabel = ttk.Label(self.configFrame, text = 'Timeout (ms)')
        self.timeoutWidget = ttk.Spinbox(self.configFrame, from_=TIMEOUT_MIN, to=TIMEOUT_MAX, increment=100, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.timeoutWidget.set(self.timeout)
        self.chunkSizeLabel = ttk.Label(self.configFrame, text = 'Chunk size (Bytes)')
        self.chunkSizeWidget = ttk.Spinbox(self.configFrame, from_=CHUNK_SIZE_MIN, to=CHUNK_SIZE_MAX, increment=10240, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.chunkSizeWidget.set(self.chunkSize)
        self.applyButton = ttk.Button(self.configFrame, text = "Apply Changes", command = lambda:self.scpiApplyConfig(self.timeoutWidget.get(), self.chunkSizeWidget.get()))
        # VISA CONFIGURATION GRID
        self.timeoutLabel.grid(row = 0, column = 0, pady=5)
        self.timeoutWidget.grid(row = 1, column = 0, padx=20, pady=5, columnspan=2)
        self.chunkSizeLabel.grid(row = 2, column = 0, pady=5)
        self.chunkSizeWidget.grid(row = 3, column = 0, padx=20, pady=5, columnspan=2)
        self.applyButton.grid(row = 7, column = 0, columnspan=2, pady=10)
        # VISA TERMINATION FRAME
        self.termFrame = ttk.LabelFrame(tabSelect, borderwidth=2, text = 'Termination Methods')
        self.termFrame.grid(row = 1, column = 1, padx = 5, pady = 10, sticky=tk.N+tk.W, ipadx=5, ipady=5)
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
        global tkSpanType, tkRbwType, tkVbwType, tkBwRatioType, tkAttenType
        tkSpanType = StringVar()
        tkRbwType = BooleanVar()
        tkVbwType = BooleanVar()
        tkBwRatioType = BooleanVar()
        tkAttenType = BooleanVar()

        self.motor = MotorControl( 0 , 0 )
        
        # COLUMN 0 WIDGETS
        self.positions          = ttk.LabelFrame( tabSelect, text = "Antenna Position" )
        self.positions.grid( row = 1, column = 0 , padx = 20 , pady = 10, sticky=(NSEW))
        self.boxFrame           = ttk.Frame( self.positions )
        self.boxFrame.pack( pady = 10 )

        self.azimuth_label      = ttk.Label( self.boxFrame , text = "Azimuth" )
        self.elevation_label    = ttk.Label( self.boxFrame , text = "Elevation")
        self.inputAzimuth       = ttk.Entry( self.boxFrame, width= 10 )
        self.inputElevation     = ttk.Entry( self.boxFrame, width= 10 )

        self.azimuth_label.grid( row = 0, column = 0, padx = 10 )
        self.elevation_label.grid( row = 1, column = 0, padx = 10 )
        self.inputAzimuth.grid( row = 0, column = 2, padx = 10 )
        self.inputElevation.grid( row = 1, column = 2, padx = 10 )

        self.printbutton        = tk.Button( self.positions, text = "Enter", command = self.input )
        self.printbutton.pack( padx = 20, pady = 10, side = 'right' )

        # COLUMN 1 WIDGETS
        self.clock_label        = ttk.Label( tabSelect, font= ('Arial', 14))
        self.clock_label.grid(row = 0, column = 1, padx = 20 , pady = 10, sticky=(NW, E))
        self.quickButton        = ttk.Frame( tabSelect )
        self.quickButton.grid(row = 1, column = 1, padx = 20, pady = 10, sticky=(S))
        self.EmargencyStop      = tk.Button(self.quickButton, text = "Emargency Stop", font = ('Arial', 16 ) , bg = 'red', fg = 'white', command= self.Estop, width=15)
        self.Park               = tk.Button(self.quickButton, text = "Park", font = ('Arial', 16) , bg = 'blue', fg = 'white', command = self.park, width=15)
        self.openFreeWriting    = tk.Button(self.quickButton, text = "Open Free Writing" ,font = ('Arial', 16 ), command= self.freewriting, width=15)
       
        self.EmargencyStop.pack( pady = 5 )
        self.Park.pack( pady = 5 )
        self.openFreeWriting.pack( pady = 5 )

        # COLUMN 2 WIDGETS (Framed)



            
    # TODO: Cleanup boilerplate code below

    def update_time( self ):
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.clock_label.config(text=current_time)
        root.after(1000, self.update_time)

    def freewriting(self):
        """Frexible serial communication Window
        """
        if self.motor.port != self.motorSelectBox.get()[:4]: 
            portName = self.motorSelectBox.get()
            self.motor.port = portName[:4]
            self.motor.OpenSerial()
        self.motor.freeInput()

    def Estop(self):
        
        if self.motor.port != self.motorSelectBox.get()[:4]: 
            portName = self.motorSelectBox.get()
            self.motor.port = portName[:4]
            self.motor.OpenSerial()
        self.motor.EmargencyStop()
    
    def park( self ):
        if self.motor.port != self.motorSelectBox.get()[:4]: 
            portName = self.motorSelectBox.get()
            self.motor.port = portName[:4]
            self.motor.OpenSerial()
        self.motor.Park()

    def input(self):
        if self.motor.port != self.motorSelectBox.get()[:4]: 
            portName = self.motorSelectBox.get()
            self.motor.port = portName[:4]
            self.motor.OpenSerial()
        self.motor.userAzi = self.inputAzimuth.get()
        self.motor.userEle = self.inputElevation.get()
        self.motor.readUserInput()      


    def quit(self):
        self.motor.CloseSerial()
        root.destroy()

    # TODO: Figure out what this does or maybe deprecate it
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

class SpecAn(FrontEnd):
    def __init__(self, Vi, parentWidget):
        # FLAGS
        self.analyzerKillFlag = TRUE
        # CONSTANTS
        self.RBW_FILTER_SHAPE_VALUES = ('Gaussian', 'Flattop')
        self.RBW_FILTER_SHAPE_VAL_ARGS = ('GAUS', 'FLAT')
        self.RBW_FILTER_TYPE_VALUES = ("-3 dB (Normal)", "-6 dB", "Impulse", "Noise")
        self.RBW_FILTER_TYPE_VAL_ARGS = ('DB3', 'DB6', 'IMP', 'NOISE')
        # VISA OBJECT
        self.Vi = Vi

        # COLUMN 2 WIDGETS (Framed)
        spectrumFrame = ttk.LabelFrame(parentWidget, text = "Placeholder Text")
        spectrumFrame.grid(row = 0, column = 2, padx = 20, pady = 10, sticky=(NSEW), rowspan=2)
        spectrumFrame.rowconfigure(0, weight=1)
        spectrumFrame.rowconfigure(1, weight=1)
        spectrumFrame.columnconfigure(0, weight=1)
        spectrumFrame.columnconfigure(1, weight=1)

        # MATPLOTLIB GRAPH
        fig = plt.figure(linewidth=0, edgecolor="#04253a")
        self.ax = fig.add_subplot()
        self.ax.set_title("Spectrum Plot")
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Power Spectral Density (dBm/RBW)")
        self.ax.autoscale(enable=False, tight=True)
        self.ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
        self.ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
        self.ax.xaxis.set_major_formatter(ticker.EngFormatter(unit=''))
        self.spectrumDisplay = FigureCanvasTkAgg(fig, master=spectrumFrame)
        self.spectrumDisplay.get_tk_widget().grid(row = 0, column = 0)

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
        centerFreqFrame = ttk.LabelFrame(tab1, text="Center Frequency")
        centerFreqFrame.grid(row=0, column=0)
        self.centerFreqEntry = ttk.Entry(centerFreqFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.centerFreqEntry.pack()

        spanFrame = ttk.LabelFrame(tab1, text="Span")
        spanFrame.grid(row=1, column=0)
        self.spanEntry = ttk.Entry(spanFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.spanEntry.pack()
        self.spanSweptButton = ttk.Radiobutton(spanFrame, variable=tkSpanType, text = "Swept Span", value='swept')
        self.spanSweptButton.pack(anchor=W)
        self.spanZeroButton = ttk.Radiobutton(spanFrame, variable=tkSpanType, text = "Zero Span", value='zero')
        self.spanZeroButton.pack(anchor=W)
        self.spanFullButton = ttk.Button(spanFrame, text = "Full Span")
        self.spanFullButton.pack(anchor=S, fill=BOTH)

        startFreqFrame = ttk.LabelFrame(tab1, text="Start Frequency")
        startFreqFrame.grid(row=2, column=0)
        self.startFreqEntry = ttk.Entry(startFreqFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.startFreqEntry.pack()

        stopFreqFrame = ttk.LabelFrame(tab1, text="Stop Frequency")
        stopFreqFrame.grid(row=3, column=0)
        self.stopFreqEntry = ttk.Entry(stopFreqFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.stopFreqEntry.pack()

        # MEASUREMENT TAB 2 (BANDWIDTH)
        rbwFrame = ttk.LabelFrame(tab2, text="Res BW")
        rbwFrame.grid(row=0, column=0)
        self.rbwEntry = ttk.Entry(rbwFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.rbwEntry.pack()
        self.rbwAutoButton = ttk.Radiobutton(rbwFrame, variable=tkRbwType, text="Auto", value=AUTO)
        self.rbwAutoButton.pack(anchor=W)
        self.rbwManButton = ttk.Radiobutton(rbwFrame, variable=tkRbwType, text="Manual", value=MANUAL)
        self.rbwManButton.pack(anchor=W)
        
        vbwFrame = ttk.LabelFrame(tab2, text="Video BW")
        vbwFrame.grid(row=1, column=0)
        self.vbwEntry = ttk.Entry(vbwFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.vbwEntry.pack()
        self.vbwAutoButton = ttk.Radiobutton(vbwFrame, variable=tkVbwType, text="Auto", value=AUTO)
        self.vbwAutoButton.pack(anchor=W)
        self.vbwManButton = ttk.Radiobutton(vbwFrame, variable=tkVbwType, text="Manual", value=MANUAL)
        self.vbwManButton.pack(anchor=W)

        bwRatioFrame = ttk.LabelFrame(tab2, text="VBW:RBW")
        bwRatioFrame.grid(row=2, column=0)
        self.bwRatioEntry = ttk.Entry(bwRatioFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.bwRatioEntry.pack()
        self.bwRatioAutoButton = ttk.Radiobutton(bwRatioFrame, variable=tkBwRatioType, text="Auto", value=AUTO)
        self.bwRatioAutoButton.pack(anchor=W)
        self.bwRatioManButton = ttk.Radiobutton(bwRatioFrame, variable=tkBwRatioType, text="Manual", value=MANUAL)
        self.bwRatioManButton.pack(anchor=W)

        rbwFilterShapeFrame = ttk.LabelFrame(tab2, text="RBW Filter Shape")
        rbwFilterShapeFrame.grid(row=3, column=0)
        self.rbwFilterShapeCombo = ttk.Combobox(rbwFilterShapeFrame, values = self.RBW_FILTER_SHAPE_VALUES)
        self.rbwFilterShapeCombo.pack(anchor=W)

        rbwFilterTypeFrame = ttk.LabelFrame(tab2, text="RBW Filter Type")
        rbwFilterTypeFrame.grid(row=4, column=0)
        self.rbwFilterTypeCombo = ttk.Combobox(rbwFilterTypeFrame, values = self.RBW_FILTER_TYPE_VALUES)
        self.rbwFilterTypeCombo.pack(anchor=W)

        # MEASUREMENT TAB 3 (AMPLITUDE)
        refLevelFrame = ttk.LabelFrame(tab3, text="Ref Level")
        refLevelFrame.grid(row=0, column=0)
        self.refLevelEntry = ttk.Entry(refLevelFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.refLevelEntry.pack()

        yScaleFrame = ttk.LabelFrame(tab3, text="Scale/Division")
        yScaleFrame.grid(row=1, column=0)
        self.yScaleEntry = ttk.Entry(yScaleFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.yScaleEntry.pack()

        numDivFrame = ttk.LabelFrame(tab3, text="Number of Divisions")
        numDivFrame.grid(row=2, column=0)
        self.numDivEntry = ttk.Entry(numDivFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.numDivEntry.pack()

        attenFrame = ttk.LabelFrame(tab3, text="Mech Atten")
        attenFrame.grid(row=3, column=0)
        self.attenEntry = ttk.Entry(attenFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.attenEntry.pack()
        self.attenAutoButton = ttk.Radiobutton(attenFrame, variable=tkAttenType, text="Auto", value=AUTO)
        self.attenAutoButton.pack(anchor=W)
        self.attenManButton = ttk.Radiobutton(attenFrame, variable=tkAttenType, text="Manual", value=MANUAL)
        self.attenManButton.pack(anchor=W)

        # TOGGLE BUTTON
        spectrumToggle = ttk.Button(spectrumFrame, text="Toggle Analyzer", command=lambda:self.toggleAnalyzerDisplay())
        spectrumToggle.grid(row=1, column=1, sticky=NSEW)  

        # Generate thread to handle live data plot in background
        t1 = threading.Thread(target=self.loopAnalyzerDisplay, daemon=TRUE)
        t1.start()

    def bindWidgets(self):
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

        self.spanSweptButton.configure(command = lambda: self.setAnalyzerThreadHandler())
        self.spanZeroButton.configure(command = lambda: self.setAnalyzerThreadHandler())
        self.spanFullButton.bind("<Button-1>", lambda event: self.setAnalyzerThreadHandler(event, startfreq=0, stopfreq=50e9))
        self.rbwAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(rbwtype=AUTO))
        self.rbwManButton.configure(command = lambda: self.setAnalyzerThreadHandler(rbwtype=MANUAL))
        self.vbwAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(vbwtype=AUTO))
        self.vbwManButton.configure(command = lambda: self.setAnalyzerThreadHandler(vbwtype=MANUAL))
        self.bwRatioAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(bwratiotype=AUTO))
        self.bwRatioManButton.configure(command = lambda: self.setAnalyzerThreadHandler(bwratiotype=MANUAL))
        self.rbwFilterShapeCombo.bind("<<ComboboxSelected>>", lambda event: self.setAnalyzerThreadHandler(event, rbwfiltershape = self.rbwFilterShapeCombo.current()))
        self.rbwFilterTypeCombo.bind("<<ComboboxSelected>>", lambda event: self.setAnalyzerThreadHandler(event, rbwfiltertype = self.rbwFilterTypeCombo.current()))
        self.attenAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(attentype=AUTO))
        self.attenManButton.configure(command = lambda: self.setAnalyzerThreadHandler(attentype=MANUAL))

    def setAnalyzerPlotLimits(self, **kwargs):
        """Sets self.ax limits to parameters passed in **kwargs if they exist. If not, gets relevant widget values to set limits
        """
        if 'xmin' in kwargs and 'xmax' in kwargs:
            self.ax.set_xlim(kwargs["xmin"], kwargs["xmax"])
        else:
            xmin = float(self.startFreqEntry.get())
            xmax = float(self.stopFreqEntry.get())
            self.ax.set_xlim(xmin, xmax)
        if 'ymin' in kwargs and 'ymax' in kwargs:
            self.ax.set_ylim(kwargs["ymin"], kwargs["ymax"])
        else:
            ymax = float(self.refLevelEntry.get())
            ymin = ymax - float(self.numDivEntry.get()) * float(self.yScaleEntry.get())
            self.ax.set_ylim(ymin, ymax)
        self.ax.margins(0, 0.05)
        self.ax.grid(visible=TRUE, which='major', axis='both', linestyle='-.')

    def setAnalyzerThreadHandler(self, *event, **kwargs):
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
        # Center Frequency
        _dict = {
            'command': ':SENS:FREQ:CENTER',
            'arg': None,
            'widget': self.centerFreqEntry
        }
        if "centerfreq" in kwargs:
            _dict.update({'arg': kwargs.get("centerfreq")})
        _list.append(_dict)
        # Span
        _dict = {
            'command': ':SENS:FREQ:SPAN',
            'arg': None,
            'widget': self.spanEntry
        }
        if "span" in kwargs:
            _dict.update({'arg': kwargs.get("span")})
        _list.append(_dict)
        # Start Frequency
        _dict = {
            'command': ':SENS:FREQ:START',
            'arg': None,
            'widget': self.startFreqEntry
        }
        if "startfreq" in kwargs:
            _dict.update({'arg': kwargs.get("startfreq")})
        _list.append(_dict)
        # Stop Frequency
        _dict = {
            'command': ':SENS:FREQ:STOP',
            'arg': None,
            'widget': self.stopFreqEntry
        }
        if "stopfreq" in kwargs:
            _dict.update({'arg': kwargs.get("stopfreq")})
        _list.append(_dict)
        # Resolution Bandwidth
        _dict = {
            'command': ':SENS:BANDWIDTH:RESOLUTION',
            'arg': None,
            'widget': self.rbwEntry
        }
        if "rbw" in kwargs:
            _dict.update({'arg': kwargs.get("rbw")}),
        _list.append(_dict)
        # Video Bandwidth
        _dict = {
            'command': ':SENS:BANDWIDTH:VIDEO',
            'arg': None,
            'widget': self.vbwEntry
        }
        if "vbw" in kwargs:
            _dict.update({'arg': kwargs.get("vbw")})
        _list.append(_dict)
        # VBW: 3 dB RBW
        _dict = {
            'command': ':SENS:BANDWIDTH:VIDEO:RATIO',
            'arg': None,
            'widget': self.bwRatioEntry
        }
        if "bwratio" in kwargs:
            _dict.update({'arg': kwargs.get("bwratio")})
        _list.append(_dict)
        # Reference Level
        _dict = {
            'command': ':DISP:WINDOW:TRACE:Y:RLEVEL',
            'arg': None,
            'widget': self.refLevelEntry
        }
        if "ref" in kwargs:
            _dict.update({'arg': kwargs.get("ref")})
        _list.append(_dict)
        # Number of divisions
        _dict = {
            'command': ':DISP:WINDOW:TRACE:Y:NDIV',
            'arg': None,
            'widget': self.numDivEntry
        }
        if "numdiv" in kwargs:
            _dict.update({'arg': kwargs.get("numdiv")})
        _list.append(_dict)
        # Scale per division
        _dict = {
            'command': ':DISP:WINDOW:TRACE:Y:PDIV',
            'arg': None,
            'widget': self.yScaleEntry
        }
        if "yscale" in kwargs:
            _dict.update({'arg': kwargs.get("yscale")})
        _list.append(_dict)
        # Mechanical attenuation
        _dict = {
            'command': ':SENS:POWER:RF:ATTENUATION',
            'arg': None,
            'widget': self.attenEntry
        }
        if "atten" in kwargs:
            _dict.update({'arg': kwargs.get("atten")})
        _list.append(_dict)
        # TODO: make spantype do something
        # SPAN TYPE

        # RBW TYPE
        _dict = {
            'command': ':SENS:BAND:RES:AUTO',
            'arg': None,
            'widget': tkRbwType
        }
        if 'rbwtype' in kwargs:
            _dict.update({'arg': kwargs.get('rbwtype')})
        _list.append(_dict)
        # VBW TYPE
        _dict = {
            'command': ':SENS:BAND:VID:AUTO',
            'arg': None,
            'widget': tkVbwType
        }
        if 'vbwtype' in kwargs:
            _dict.update({'arg': kwargs.get('vbwtype')})
        _list.append(_dict)
        # BW RATIO TYPE
        _dict = {
            'command': ':SENS:BAND:VID:RATIO',
            'arg': None,
            'widget': tkBwRatioType
        }
        if 'bwratiotype' in kwargs:
            _dict.update({'arg': kwargs.get('bwratiotype')})
        _list.append(_dict)
        # RBW FILTER SHAPE
        if "rbwfiltershape" in kwargs:
            _dict = {
                'command': ':SENS:BAND:SHAP',
                'widget': self.rbwFilterShapeCombo,
            }
            if kwargs.get('rbwfiltershape') is None:
                _dict.update({'arg': None})
            else:
                _dict.update({'arg': self.RBW_FILTER_SHAPE_VAL_ARGS[kwargs.get("rbwfiltershape")]})
            _list.append(_dict)
        # RBW FILTER TYPE
        if "rbwfiltertype" in kwargs:
            _dict = {
                'command': ':SENS:BAND:TYPE',
                'widget': self.rbwFilterTypeCombo,
            }
            if kwargs.get('rbwfiltertype') is None:
                _dict.update({'arg': None})
            else:
                _dict.update({'arg': self.RBW_FILTER_TYPE_VAL_ARGS[kwargs.get("rbwfiltertype")]})
            _list.append(_dict)
        # ATTENUATION TYPE
        _dict = {
            'command': ':SENS:POWER:ATT:AUTO',
            'arg': None,
            'widget': tkAttenType
        }
        if 'attentype' in kwargs:
            _dict.update({'arg': kwargs.get('attentype')})
        _list.append(_dict)

        # Sort the list so dictionaries with 'arg': None are placed (and executed) after issued parameters
        for index in range(len(_list)):
            if _list[index]['arg'] is not None:
                _list.insert(0, _list.pop(index))

        # EXECUTE COMMANDS
        logging.debug(f"setAnalyzerValue generated list of dictionaries '_list' with value {_list}")
        for x in _list:
            try:
                # Issue command with argument
                if x['arg'] is not None:
                    self.Vi.openRsrc.write(f'{x['command']} {x['arg']}')
                # Set widgets without issuing a parameter to command
                try:
                    buffer = self.Vi.openRsrc.query_ascii_values(f'{x['command']}?') # Default converter is float
                except:
                    buffer = self.Vi.openRsrc.query_ascii_values(f'{x['command']}?', converter='s')
                logging.debug(f"Command {x['command']}? returned {buffer}")
                clearAndSetWidget(x['widget'], buffer)
            except Exception as e:
                logging.fatal(f"VISA ERROR {hex(self.Vi.openRsrc.last_status)} IN SETANALYZERVALUE: {e}. ATTEMPTING TO RESET ANALYZER STATE")
                self.Vi.queryErrors()
                self.Vi.resetAnalyzerState()
        # Set plot limits
        self.setAnalyzerPlotLimits()
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
                self.Vi.queryPowerUpErrors()
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
                    rbwfiltershape=None,
                    rbwfiltertype=None,
                )
                visaLock.release()
                errorFlag = FALSE
            except Exception as e:
                logging.warning(f"VISA error with status code {hex(self.Vi.openRsrc.last_status)}. {e}. Could not initialize analyzer state, retrying...")
                try:
                    self.Vi.queryErrors()
                except Exception as e:
                    logging.warning(f'Could not query errors from device. {e}')
                visaLock.release()
                time.sleep(8)

        # Main analyzer loop
        # TODO: variable time.sleep based on analyzer sweep time
        while TRUE:
            if not self.analyzerKillFlag:
                visaLock.acquire()
                try:
                    try:
                        lines.pop(0).remove()
                    except:
                        pass
                    buffer = self.Vi.openRsrc.query_ascii_values(":READ:SAN?")
                    xAxis = buffer[::2]
                    yAxis = buffer[1::2]
                    lines = self.ax.plot(xAxis, yAxis, )
                    self.ax.grid(visible=True)
                    self.spectrumDisplay.draw()
                except Exception as e:
                    logging.fatal(f"Visa Status: {hex(self.Vi.openRsrc.last_status)}. Fatal error in call loopAnalyzerDisplay: {e}. Attempting to reset analyzer state.")
                    self.Vi.queryErrors
                    self.Vi.resetAnalyzerState()
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



# Root tkinter interface (contains DFS_Window and standard output console)
root = ThemedTk(theme="clearlooks")
root.title('RF-DFS')
isNumWrapper = root.register(isNumber)
dummy = ttk.Entry()
s = ttk.Style()
s.configure("TCombobox",
            selectbackground=dummy.cget('background'),
            selectforeground=dummy.cget('foreground'),
            activebackground=dummy.cget('background'))
dummy.destroy()

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

Vi = VisaControl()
DFS_Window = FrontEnd(root, Vi)
sa = SpecAn(Vi, DFS_Window.tab1)
sa.bindWidgets()

# Limit window size to the minimum size on generation
root.update()
root.minsize(root.winfo_width(), root.winfo_height())
root.protocol("WM_DELETE_WINDOW", DFS_Window.on_closing )

root.mainloop()
