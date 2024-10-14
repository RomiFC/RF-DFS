# PRIVATE LIBRARIES
import threading
from frontendio import *
from timestamp import *

# OTHER MODULES
import sys
import os
from pyvisa import attributes
import numpy as np
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
from tkinter import filedialog
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
    format="[%(asctime)s] %(levelname)-s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
def addLoggingLevel(levelName, levelNum, methodName=None):
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
        raise AttributeError("{} already defined in logging module".format(levelName))
    if hasattr(logging, methodName):
        raise AttributeError("{} already defined in logging module".format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
        raise AttributeError("{} already defined in logger class".format(methodName))

    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)

    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)
addLoggingLevel("TERMINAL", logging.INFO + 1)



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
    def __init__(self, root, Vi, Motor):
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
        self.motor = Motor

        oFile = DataManagement()
        controlFrame = ttk.Frame(root) 
  
        self.directionFrame = ttk.LabelFrame(controlFrame, text = "Antenna Position")  # Frame that holds matplotlib azimuth/elevation plot
        self.spectrumFrame = ttk.LabelFrame(controlFrame, text = "Placeholder Text")   # Frame that holds matplotlib spectrum plot

        controlFrame.pack(expand = True, fill=BOTH, side=TOP) 

        self.controlInterface(controlFrame)
        # self.updateOutput( oFile, root )

        root.after(1000, self.update_time )
    
    def onExit( self ):
        """ Ask to close serial communication when 'X' button is pressed """
        SaveCheck = messagebox.askokcancel( title = "Window closing", message = "Do you want to close communication to the motor?" )
        if SaveCheck is True:      
            while (self.motor.ser.is_open):
                self.motor.CloseSerial()
            root.quit()
            logging.info("Program executed with exit code: 0")
        else:
            pass

    def openConfig(self):
        """Opens configuration menu on a new toplevel window
        """
        parent = Toplevel()

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
        connectFrame = ttk.LabelFrame(parent, borderwidth = 2, text = "Instrument Connections")
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
        self.instrSelectBox.set(self.instrument)
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
        self.configFrame = ttk.LabelFrame(parent, borderwidth = 2, text = "VISA Configuration")
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
        self.termFrame = ttk.LabelFrame(parent, borderwidth=2, text = 'Termination Methods')
        self.termFrame.grid(row = 1, column = 1, padx = 5, pady = 10, sticky=tk.N+tk.W, ipadx=5, ipady=5)
        self.sendEndWidget = ttk.Checkbutton(self.termFrame, text = 'Send \'End or Identify\' on write', variable=self.sendEnd)
        self.selectTermWidget = ttk.Combobox(self.termFrame, text='Termination Character', values=self.SELECT_TERM_VALUES, state='disabled')
        self.enableTermWidget = ttk.Checkbutton(self.termFrame, text = 'Enable Termination Character', variable=self.enableTerm, command=lambda:onEnableTermPress())
        # VISA TERMINATION GRID
        self.sendEndWidget.grid(row = 0, column = 0, pady = 5)
        self.enableTermWidget.grid(row = 1, column = 0, pady = 5)
        self.selectTermWidget.grid(row = 2, column = 0, pady = 5)
    

    def resetConfigWidgets(self, *event):
        # DEPRECATED WITH THE REMOVAL OF CONTROL AND CONFIG TABS
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
    
    def controlInterface(self, parentWidget):
        """Generates the main control interface the root level. Also generates frames to contain objects for SpecAn and AziElePlot
        """

        parent = parentWidget
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)
        parent.rowconfigure(3, weight=1)
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, weight=1)
        
        # COLUMN 0 WIDGETS
        antennaPosFrame          = ttk.LabelFrame( parent, text = "Antenna Position" )
        antennaPosFrame.grid( row = 1, column = 0 , padx = 20 , pady = 10, sticky=(NSEW))

        self.azimuth_label      = ttk.Label(antennaPosFrame, text = "Azimuth:")
        self.elevation_label    = ttk.Label(antennaPosFrame, text = "Elevation:")
        self.inputAzimuth       = ttk.Entry(antennaPosFrame)
        self.inputElevation     = ttk.Entry(antennaPosFrame)

        self.azimuth_label.grid( row = 0, column = 0, padx = 10, pady=5)
        self.elevation_label.grid( row = 1, column = 0, padx = 10, pady=5)
        self.inputAzimuth.grid( row = 0, column = 1, padx = 10)
        self.inputElevation.grid( row = 1, column = 1, padx = 10)

        self.printbutton        = tk.Button( antennaPosFrame, text = "Enter", command = self.input )
        self.printbutton.grid(row = 2, column = 1, padx = 20, pady = 5, sticky=E)

        clockFrame              = ttk.Frame(parent)
        clockFrame.grid(row=0,column=0)
        self.clock_label        = ttk.Label(clockFrame, font= ('Arial', 14))
        self.clock_label.pack()
        self.quickButton        = ttk.Frame( parent )
        self.quickButton.grid(row = 2, column = 0, padx = 20, pady = 10, sticky=(S))
        self.EmargencyStop      = tk.Button(self.quickButton, text = "Emergency Stop", font = ('Arial', 16 ), bg = 'red', fg = 'white', command= self.Estop, width=15)
        self.Park               = tk.Button(self.quickButton, text = "Park", font = ('Arial', 16) , bg = 'blue', fg = 'white', command = self.park, width=15)
        self.openFreeWriting    = tk.Button(self.quickButton, text = "Motor Terminal", font = ('Arial', 16 ), command= self.freewriting, width=15)
       
        self.EmargencyStop.pack( pady = 5 )
        self.Park.pack( pady = 5 )
        self.openFreeWriting.pack( pady = 5 )

        # COLUMN 1 WIDGETS
        self.directionFrame.grid(row=0, column=1, padx = 20, pady = 10, sticky = NSEW, rowspan = 3)

        # COLUMN 2 WIDGETS
        self.spectrumFrame.grid(row = 0, column = 2, padx = 20, pady = 10, sticky=NSEW, rowspan=3)

    def openSaveDialog(self, type=None):
        print(os.getcwd())
        if type == 'trace':
            filename = filedialog.asksaveasfilename(initialdir = os.getcwd(), filetypes=(('Text File (Tab delimited)', '*.txt'), ('Comma Separated Variables', '*.csv')))
        elif type == 'log':
            filename = filedialog.asksaveasfilename(initialdir = os.getcwd(), filetypes=('Text Files', '*.txt'))
        elif type == 'image':
            filename = filedialog.asksaveasfilename(initialdir = os.getcwd(), filetypes=(('JPEG', '*.jpg'), ('PNG', '*.png')))
        else: return
        print(filename)

            
    # TODO: Cleanup boilerplate code below
    def getMotorPort(self):
        return self.motorSelectBox.get()

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

        # TODO: This isn't called anywhere? Delete?
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
    """Generates tkinter-embedded matplotlib graph of spectrum analyzer.

    Args:
        Vi (class): Instance of VisaControl that contains methods for communicating with SCPI instruments.
        parentWidget (tk::LabelFrame, tk::Frame): Parent widget which will contain graph and control widgets.
    """
    def __init__(self, Vi, parentWidget):
        # FLAGS
        self.contSweepFlag = False
        self.singleSweepFlag = False
        # CONSTANTS
        self.RBW_FILTER_SHAPE_VALUES = ('Gaussian', 'Flattop')
        self.RBW_FILTER_SHAPE_VAL_ARGS = ('GAUS', 'FLAT')
        self.RBW_FILTER_TYPE_VALUES = ("-3 dB (Normal)", "-6 dB", "Impulse", "Noise")
        self.RBW_FILTER_TYPE_VAL_ARGS = ('DB3', 'DB6', 'IMP', 'NOISE')
        # TKINTER VARIABLES
        # TODO: Why is this global
        global tkSpanType, tkRbwType, tkVbwType, tkBwRatioType, tkAttenType
        tkSpanType = StringVar()
        tkRbwType = BooleanVar()
        tkVbwType = BooleanVar()
        tkBwRatioType = BooleanVar()
        tkAttenType = BooleanVar()
        # VISA OBJECT
        self.Vi = Vi
        # PARENT
        spectrumFrame = parentWidget
        spectrumFrame.rowconfigure(0, weight=1)     # Allow this row to resize
        spectrumFrame.rowconfigure(1, weight=0)     # Prevent this row from resizing
        spectrumFrame.rowconfigure(2, weight=0)     # Prevent this row from resizing
        spectrumFrame.columnconfigure(0, weight=1)  # Allow this column to resize
        spectrumFrame.columnconfigure(1, weight=0)  # Prevent this column from resizing

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
        self.spectrumDisplay.get_tk_widget().grid(row = 0, column = 0, sticky=NSEW, rowspan=3)

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
        centerFreqFrame.grid(row=0, column=0, sticky=E)
        self.centerFreqEntry = ttk.Entry(centerFreqFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.centerFreqEntry.pack()

        spanFrame = ttk.LabelFrame(tab1, text="Span")
        spanFrame.grid(row=1, column=0, sticky=E)
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

        # SWEEP BUTTONS
        singleSweepButton = ttk.Button(spectrumFrame, text="Single Sweep", command=lambda:self.singleSweep())
        singleSweepButton.grid(row=1, column=1, sticky=NSEW)
        continuousSweepButton = ttk.Button(spectrumFrame, text="Continuous", command=lambda:self.toggleAnalyzerDisplay())
        continuousSweepButton.grid(row=2, column=1, sticky=NSEW) 

        self.bindWidgets() 

        # Generate thread to handle live data plot in background
        analyzerLoop = threading.Thread(target=self.loopAnalyzerDisplay, daemon=TRUE)
        analyzerLoop.start()

    def bindWidgets(self):
        """Binds tkinter events to the widgets' respective commands.
        """
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
        """Issues command to spectrum analyzer with the value of kwarg as the argument and queries for widget values. If the value is None or if there are no kwargs, query the spectrum analyzer to set widget values instead.
        
        Args:
            centerfreq (float, optional): Defaults to None.
            span (float, optional): Defaults to None.
            startfreq (float, optional): Defaults to None.
            stopfreq (float, optional): Defaults to None.
            rbw (float, optional): Defaults to None.
            vbw (float, optional): Defaults to None.
            bwratio (float, optional): Defaults to None.
            ref (float, optional): Reference level in dBm. Defaults to None.
            numdiv (float, optional): Defaults to None.
            yscale (float, optional): Scale per division in dB. Defaults to None.
            atten (float, optional): Mechanical attenuation in dB. Defaults to None.
            spantype (string, optional): WIP
            rbwtype (bool, optional): WIP
            vbwtype (bool, optional): WIP
            bwratiotype (bool, optional): WIP
            rbwfiltershape (int, optional): Index of the combobox widget tied to RBW_FILTER_SHAPE_VAL_ARGS. Defaults to None.
            rbwfiltertype (int, optional): Index of the combobox widget tied to RBW_FILTER_TYPE_VAL_ARGS. Defaults to None.
            attentype (bool, optional): WIP
        """
        # TODO: Make sure all command have full functionality
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
        _dict = {
            'command': ':SENS:BAND:SHAP',
            'widget': self.rbwFilterShapeCombo,
            'arg': None,
        }
        if 'rbwfiltershape' in kwargs:
            _dict.update({'arg': self.RBW_FILTER_SHAPE_VAL_ARGS[kwargs.get("rbwfiltershape")]})
        _list.append(_dict)
        # RBW FILTER TYPE
        _dict = {
            'command': ':SENS:BAND:TYPE',
            'widget': self.rbwFilterTypeCombo,
            'arg': None,
        }
        if 'rbwfiltertype' in kwargs:
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

        # Sort the list so dictionaries with 'arg': None are placed (and executed) after write commands
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
                logging.fatal(e)
                logging.fatal(f"VISA ERROR {hex(self.Vi.openRsrc.last_status)} IN SETANALYZERVALUE: ATTEMPTING TO RESET ANALYZER STATE")
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
                time.sleep(3)
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
                self.setAnalyzerValue()
                visaLock.release()
                errorFlag = FALSE
            except Exception as e:
                logging.error(e)
                logging.error(f"VISA error with status code {hex(self.Vi.openRsrc.last_status)}. Could not initialize analyzer state, retrying...")
                try:
                    self.Vi.queryErrors()
                except Exception as e:
                    logging.warning(e)
                    logging.warning(f'Could not query errors from device.')
                visaLock.release()
                time.sleep(8)

        # Main analyzer loop
        # TODO: variable time.sleep based on analyzer sweep time
        while TRUE:
            if self.contSweepFlag or self.singleSweepFlag:
                visaLock.acquire()
                try: # Check if the instrument is busy calibrating, settling, sweeping, or measuring 
                    if self.Vi.getOperationRegister() & 0b00011011:
                        continue 
                except Exception as e:
                    logging.fatal(e)
                    logging.fatal("Could not retrieve information from Operation Status Register. Retrying...")
                    visaLock.release()
                    time.sleep(8)
                    continue
                try:
                    if 'lines' in locals():     # Remove previous plot if it exists
                        lines.pop(0).remove()
                    buffer = self.Vi.openRsrc.query_ascii_values(":READ:SAN?")
                    xAxis = buffer[::2]
                    yAxis = buffer[1::2]
                    lines = self.ax.plot(xAxis, yAxis)
                    self.ax.grid(visible=True)
                    self.spectrumDisplay.draw()
                except Exception as e:
                    logging.fatal(e)
                    logging.fatal(f"Visa Status: {hex(self.Vi.openRsrc.last_status)}. Fatal error in call loopAnalyzerDisplay, attempting to reset analyzer state.")
                    self.Vi.queryErrors
                    self.Vi.resetAnalyzerState()
                    time.sleep(5)
                visaLock.release()
                self.singleSweepFlag = False
                time.sleep(0.5)
            else:
                # Prevent this thread from taking up too much utilization
                time.sleep(1)
                
        return

    def toggleAnalyzerDisplay(self):
        """sets contSweepFlag != contSweepFlag to control loopAnalyzerDisplay()
        """
        if self.Vi.isSessionOpen() == FALSE:
            logging.error("Cannot initiate sweep, session to the analyzer is not open.")
            self.contSweepFlag = False
            return
        
        if not self.contSweepFlag:
            logging.info("Starting spectrum display.")
            self.contSweepFlag = True
        else:
            logging.info("Disabling spectrum display.")
            self.contSweepFlag = False

    def singleSweep(self):
        """Sets singleSweepFlag TRUE and contSweepFlag FALSE to control loopAnalyzerDisplay()
        """
        if self.Vi.isSessionOpen() == FALSE:
            logging.error("Cannot initiate sweep, session to the analyzer is not open.")
            self.contSweepFlag = False
            return
        
        self.contSweepFlag = False
        self.singleSweepFlag = True

            
class AziElePlot(FrontEnd):
    """Generates tkinter-embedded matplotlib graph of spectrum analyzer. Requires an instance of FrontEnd to be constructed with the name Front_End.

    Args:
        Motor (class): Instance of MotorControl that contains methods for communicating with the Parker Hannifin Motor Controller.
        parentWidget (tk::LabelFrame, tk::Frame): Parent widget which will contain graph and control widgets.
    """
    def __init__(self, Motor, parentWidget):
        # MOTOR INSTANCE
        self.Motor = Motor

        # PARENT
        self.parent = parentWidget
        self.parent.rowconfigure(0, weight=1)
        self.parent.columnconfigure(0, weight=1)

        # PLOT
        fig, (azAxis, elAxis) = plt.subplots(1, 2, subplot_kw=dict(projection='polar'))
        azAxis.set_title("Azimuth", va='bottom')
        elAxis.set_title("Elevation", va='bottom')
        azAxis.set_rticks([0.25, 0.5, 0.75], labels=[])
        elAxis.set_rticks([0.25, 0.5, 0.75], labels=[])
        azAxis.set_theta_zero_location('N')
        elAxis.set_thetagrids([0, 30, 60, 90, 120])
        azAxis.autoscale(enable=False, tight=True)
        elAxis.autoscale(enable=False, tight=True)
        azAxis.set_facecolor('#d5de9c')
        elAxis.set_facecolor('#d5de9c')
        elAxis.axvspan(0, -240/180.*np.pi, facecolor='0.85')
        azAxis.grid(color='#316931')
        elAxis.grid(color='#316931')

        self.bearingDisplay = FigureCanvasTkAgg(fig, master=self.parent)
        self.bearingDisplay.get_tk_widget().grid(row = 0, column = 0, sticky=NSEW, columnspan=1)

        # CONTROLS
        ctrlFrame = ttk.Frame(self.parent)
        ctrlFrame.grid(row=1, column=0, sticky=NSEW)
        for x in range(4):
            ctrlFrame.columnconfigure(x, weight=1)
        enterAzLabel = ttk.Label(ctrlFrame, text="Enter Azimuth:")
        enterAzLabel.grid(row=0, column=0, sticky=W)
        enterElLabel = ttk.Label(ctrlFrame, text="Enter Elevation:")
        enterElLabel.grid(row=0, column=2, sticky=W)
        azEntry = ttk.Entry(ctrlFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        azEntry.grid(row=1, column=0, sticky=NSEW, columnspan=2)
        elEntry = ttk.Entry(ctrlFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        elEntry.grid(row=1, column=2, sticky=NSEW, columnspan=2)
        realAzLabel = ttk.Label(ctrlFrame, text = f'0{u'\N{DEGREE SIGN}'}')
        realAzLabel.grid(row = 0, column=1, sticky=E)
        realElLabel = ttk.Label(ctrlFrame, text = f'90{u'\N{DEGREE SIGN}'}')
        realElLabel.grid(row = 0, column=3, sticky=E)

        # BIND ENTRY WIDGETS
        azEntry.bind('<Return>', lambda event: self.sendMoveCommand(event, value=azEntry.get(), axis='az'))
        elEntry.bind('<Return>', lambda event: self.sendMoveCommand(event, value=elEntry.get(), axis='el'))

        # Arrow demonstration
        self.drawArrow(azAxis, 0)
        self.drawArrow(elAxis, 90)

    def drawArrow(self, axis, angle):
        """Draws arrow on the matplotlib axis from the origin at the angle specified. Intended for polar plots only.

        Args:
            axis (plt.subplots): Matplotlib axis
            angle (float): Angle in degrees
        """
        axis.arrow(angle/180.*np.pi, 0, 0, 0.8, alpha = 1, width = 0.03, edgecolor = 'blue', facecolor = 'blue', lw = 3, zorder = 5)
        self.bearingDisplay.draw()
        return
    
    def sendMoveCommand(self, event, value=None, axis=None):
        """_summary_

        Args:
            event (event): tkinter event which initiates function call
            value (float, optional): Value in degrees to send as argument to object of MotorControl. Defaults to None.
            axis (string, optional): Either 'az' or 'el' to determine which axis to move. Defaults to None.
        """
        if self.Motor.port != Front_End.getMotorPort()[:4]: 
            portName = Front_End.getMotorPort()
            self.Motor.port = portName[:4]
            self.Motor.OpenSerial()
        if axis == 'az' and value is not None:
            self.Motor.userAzi = value
            self.Motor.readUserInput()
        elif axis == 'el' and value is not None:
            self.Motor.userEle = value
            self.Motor.readUserInput()
            


# Root tkinter interface (contains Front_End and standard output console)
root = ThemedTk(theme="clearlooks")
root.title('RF-DFS')
isNumWrapper = root.register(isNumber)
# Change combobox highlight colors to match entry
dummy = ttk.Entry()
s = ttk.Style()
s.configure("TCombobox",
            selectbackground=dummy.cget('background'),
            selectforeground=dummy.cget('foreground'),
            activebackground=dummy.cget('background'))
dummy.destroy()

# Generate textbox to print standard output/error
stdioFrame = tk.Frame(root)
stdioFrame.pack(fill=BOTH, side=BOTTOM)
stdioFrame.rowconfigure(0, weight=1)
font='Courier 11'
for x in range(5):
    stdioFrame.columnconfigure(x, weight=0)
stdioFrame.columnconfigure(1, weight=1)
console = tk.Text(stdioFrame, height=20)
console.grid(column=0, row=0, sticky=(N, S, E, W), columnspan=5)
console.config(state=DISABLED)
# Terminal input
debugLabel = tk.Label(stdioFrame, text='>>>', font=(font))
debugLabel.grid(row=1, column=0)
consoleInput = tk.Entry(stdioFrame, font=(font), borderwidth=0, background=debugLabel.cget('background'))
consoleInput.grid(row=1, column=1, sticky=NSEW)
console.bind('<Button-1>', lambda event: focusHandler(event, consoleInput))
consoleInput.bind('<Return>', lambda event: executeHandler(event, consoleInput.get()))
consoleInput.bind('<Key-Up>', lambda event: commandListHandler(event, direction='up'))
consoleInput.bind('<Key-Down>', lambda event: commandListHandler(event, direction='down'))
# Terminal config
printBool = BooleanVar()
execBool = BooleanVar()
printCheckbutton = tk.Checkbutton(stdioFrame, font=(font), text='Print Return Value', variable=printBool)
printCheckbutton.grid(row=1, column=2)
evalCheckbutton = tk.Checkbutton(stdioFrame, font=(font), text='Evaluate', variable=execBool, onvalue=False, offvalue=True)
evalCheckbutton.grid(row=1, column=3)
execCheckbutton = tk.Checkbutton(stdioFrame, font=(font), text='Execute', variable=execBool)
execCheckbutton.grid(row=1, column=4)

# Helper functions
commandList = []
commandIndex = -1

def focusHandler(event, widget):
    widget.focus()
    return('break')     # Prevents class binding from firing (executing the normal event callback)

def commandListHandler(event, direction):
    global commandIndex

    consoleInput.delete(0, END)
    if direction == 'up' and commandIndex < len(commandList) - 1:
        commandIndex += 1
    elif direction== 'down' and commandIndex > 0:
        commandIndex -= 1
    consoleInput.insert(0, commandList[commandIndex])
        

def executeHandler(event, arg):
    global commandIndex, commandList

    commandIndex = -1               # Reset index so up/down arrows start at the last issued command
    consoleInput.delete(0, END)     # Clear the entry widget
    commandList.insert(0, arg)      # Save the issued command in list at index 0
    logging.terminal(f'>>> {arg}')
    if execBool.get():
        exec(arg)
    else:
        if printBool.get():
            logging.terminal(f'{eval(arg)}')
        else:
            eval(arg)

def redirector(inputStr):           # Redirect print/logging statements to the console textbox
    console.config(state=NORMAL)
    console.insert(INSERT, inputStr)
    console.yview(MOVETO, 1)
    console.config(state=DISABLED)

def checkbuttonStateHandler():
    if execBool.get():
        printCheckbutton.configure(state=DISABLED)
    else:
        printCheckbutton.configure(state=NORMAL)

evalCheckbutton.configure(command=checkbuttonStateHandler)
execCheckbutton.configure(command=checkbuttonStateHandler)

# When sys.std***.write is called (such as on print), call redirector to print in textbox
sys.stdout.write = redirector
sys.stderr.write = redirector

# Generate objects within root window
Vi = VisaControl()
Motor = MotorControl(0, 0)

Front_End = FrontEnd(root, Vi, Motor)
Spec_An = SpecAn(Vi, Front_End.spectrumFrame)
Azi_Ele = AziElePlot(Motor, Front_End.directionFrame)

# Generate menu bars
root.option_add('*tearOff', False)
menubar = Menu(root)
root['menu'] = menubar
menuFile = Menu(menubar)
menuOptions = Menu(menubar)
menuHelp = Menu(menubar)
menubar.add_cascade(menu=menuFile, label='File')
menubar.add_cascade(menu=menuOptions, label='Options')
menubar.add_cascade(menu=menuHelp, label='Help')

# File
menuFile.add_command(label='Save trace', command = lambda: Front_End.openSaveDialog(type='trace'))
menuFile.add_command(label='Save log', command = lambda: Front_End.openSaveDialog(type='log'))
menuFile.add_command(label='Save image', command = lambda: Front_End.openSaveDialog(type='image'))
menuFile.add_separator()
menuFile.add_command(label='Exit', command=Front_End.onExit)

# Options
menuOptions.add_command(label='Configure...', command=Front_End.openConfig)

# Limit window size to the minimum size on generation
root.update()
root.minsize(root.winfo_width(), root.winfo_height())

root.protocol("WM_DELETE_WINDOW", Front_End.onExit)
root.mainloop()
