# PRIVATE LIBRARIES
import threading
import defaultconfig
from frontendio import *
from timestamp import *
from opcodes import *
from loggingsetup import *

# OTHER MODULES
import sys
import os
from pyvisa import attributes
import numpy as np
import logging
import decimal
import traceback
import webbrowser
import tomllib
from pathlib import Path

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
from tkinter import font
from tkinter.ttk import *
from ttkthemes import ThemedTk

# CONSTANTS
IDLE_DELAY = 1.0
ANALYZER_LOOP_DELAY = 0.5
MOTOR_LOOP_DELAY = 0.5
RETURN_ERROR = 1
RETURN_SUCCESS = 0
ENABLE = 1
DISABLE = 0
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
ROOT_PADX = 5
ROOT_PADY = 5
COLOR_GREEN = '#00ff00'

# STATE CONSTANTS
class state:
    IDLE = 0
    INIT = 1
    LOOP = 2

# TOML CONFIGURATION
try:
    missingHeaders = []
    missingKeys = []
    file = open(Path(__file__).parent.absolute() / 'config.toml', "rb")
    cfg = tomllib.load(file)

    for header in defaultconfig.cfg:
        if str(header) not in cfg:
            missingHeaders.append(header)
            continue
        for key in defaultconfig.cfg[header]:
            if str(key) not in cfg[header]:
                missingKeys.append(header + '.' + key)
except Exception as e:
    cfg_error = e
finally:
    if missingHeaders or missingKeys or 'cfg_error' in locals():
        cfg = defaultconfig.cfg

# ENCODER CONSTANTS (HOME AND COUNTS PER DEGREE)
X_HOME = cfg['calibration']['x_enc_home']
Y_HOME = cfg['calibration']['y_enc_home']
X_CPD = cfg['calibration']['x_countsperrotation'] / 360
Y_CPD = cfg['calibration']['y_countsperrotation'] / 360

# THREADING EVENTS
visaLock = threading.RLock()        # For VISA resources
motorLock = threading.RLock()       # For motor controller
plcLock = threading.RLock()         # For PLC
specPlotLock = threading.RLock()    # For matplotlib spectrum plot
bearingPlotLock = threading.RLock() # For matplotlib antenna direction plot

# SPECTRUM ANALYZER PARAMETERS
class Parameter:
    instances = []
    def __init__(self, name, command, log = True):
        """Spectrum analyzer parameter and associated SCPI command.

        Args:
            name (string): Full name to be used in trace csv.
            command (string): SCPI command used to query/set parameter.
            log (bool): Determines whether or not to save the parameter to trace csv. Defaults to True.
        """
        Parameter.instances.append(self)
        self.name = name
        self.command = command
        self.log = log
        self.arg = None
        self.widget = None
        self.value = None

    def update(self, arg = None, widget = None, value=None):
        """Update the argument/value and tkinter widget associated with the parameter.

        Args:
            arg (any, optional): Parameter argument. Defaults to None.
            widget (ttk.Widget or Tkinter_variable, optional): Associated tkinter widget. Defaults to None.
            value(any, optional): Parameter value. Defaults to None.
        """
        if arg is not None:
            self.arg = arg
        if widget is not None:
            self.widget = widget
        if value is not None:
            self.value = value

CenterFreq      = Parameter('Center Frequency', ':SENS:FREQ:CENTER', log=False)
Span            = Parameter('Span', ':SENS:FREQ:SPAN', log=False)
StartFreq       = Parameter('Start Frequency', ':SENS:FREQ:START')
StopFreq        = Parameter('Stop Frequency', ':SENS:FREQ:STOP')
SweepTime       = Parameter('Sweep Time', ':SWE:TIME')
Rbw             = Parameter('RBW', ':SENS:BANDWIDTH:RESOLUTION')
Vbw             = Parameter('VBW', ':SENS:BANDWIDTH:VIDEO')
BwRatio         = Parameter('VBW:3 dB RBW', ':SENS:BANDWIDTH:VIDEO:RATIO', log=False)
Ref             = Parameter('Ref Level', ':DISP:WINDOW:TRACE:Y:RLEVEL', log=False)
NumDiv          = Parameter('Number of Divisions', ':DISP:WINDOW:TRACE:Y:NDIV', log=False)
YScale          = Parameter('Scale/Div', ':DISP:WINDOW:TRACE:Y:PDIV', log=False)
Atten           = Parameter('Attenuation', ':SENS:POWER:RF:ATTENUATION')
SpanType        = Parameter('Swept Span', ':SENS:FREQ:SPAN', log=False)
SweepType       = Parameter('Auto Sweep Time', ':SWE:TIME:AUTO', log=False)
RbwType         = Parameter('Auto RBW', ':SENS:BAND:RES:AUTO', log=False)
VbwType         = Parameter('Auto VBW', ':SENS:BAND:VID:AUTO', log=False)
BwRatioType     = Parameter('Auto VBW:RBW Ratio', ':SENS:BAND:VID:RATIO', log=False)
RbwFilterShape  = Parameter('RBW Filter', ':SENS:BAND:SHAP')
RbwFilterType   = Parameter('RBW Filter BW', ':SENS:BAND:TYPE')
AttenType       = Parameter('Auto Attenuateion', ':SENS:POWER:ATT:AUTO', log=False)
YAxisUnit       = Parameter('Y Axis Units', ':UNIT:POW')

# real code starts here
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
    try:
        id = widget.winfo_id()
    except:
        id = widget
    logging.debug(f"clearAndSetWidget received widget {id} and argument {arg}")
    # Set radiobutton widgets
    if isinstance(widget, (BooleanVar, IntVar, StringVar)):
        try:
            arg = bool(arg[0])
            widget.set(arg)
        except:
            widget.set(arg)
        finally:
            logging.debug(f"clearAndSetWidget passed argument {arg} ({type(arg)}) to {id} ({type(widget)})")
    # Set entry/combobox widgets
    if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox)):
        state = widget.cget("state")
        if state != NORMAL:
            widget.configure(state=NORMAL)
        widget.delete(0, END)
        # Try to convert string in list to engineering notation
        try:
            arg = float(arg[0])
            x = decimal.Decimal(arg)
            x = x.normalize().to_eng_string()
            widget.insert(0, x)
            logging.debug(f"clearAndSetWidget passed argument {x} ({type(x)}) to {id} ({type(widget)}).")
        except:
            widget.insert(0, arg)
            logging.debug(f"clearAndSetWidget passed argument {arg} ({type(arg)}) to {id} ({type(widget)}).")
        widget.configure(state=state)

def disableChildren(parent):
    for child in parent.winfo_children():
        wtype = child.winfo_class()
        if wtype not in ('Frame', 'LabelFrame', 'TFrame', 'TLabelframe'):
            child.configure(state='disable')
        else:
            disableChildren(child)

def enableChildren(parent):
    for child in parent.winfo_children():
        wtype = child.winfo_class()
        if wtype not in ('Frame', 'LabelFrame', 'TFrame', 'TLabelframe'):
            try:
                child.configure(state='enable')
            except:
                child.configure(state='normal')
        else:
            enableChildren(child)


class FrontEnd():
    def __init__(self, root, Vi, Motor, PLC):
        """Initializes the top level tkinter interface

        Args:
            root (Tk or ThemedTk): Root tkinter window.
            Vi (VisaIO): Object of VisaIO that contains methods for VISA communication and an opened resource manager.
            Motor (MotorIO): Object of MotorIO that contains methods for serial motor communication.
            PLC (SerialIO): Object of SerialIO that contains methods for serial PLC communication.
        """
        # CONSTANTS
        self.SELECT_TERM_VALUES = ('Line Feed - \\n', 'Carriage Return - \\r')
        # VARIABLES
        self.timeout = TIMEOUT_DEF           # VISA timeout value
        self.chunkSize = CHUNK_SIZE_DEF      # Bytes to read from buffer
        self.instrument = ''                 # ID of the currently open instrument.
        self.motorPort = ''
        self.plcPort = ''
        # TKINTER VARIABLES
        self.sendEnd = BooleanVar()
        self.sendEnd.set(TRUE)
        self.enableTerm = BooleanVar()
        self.enableTerm.set(FALSE)
        # OBJECTS
        self.Vi = Vi
        self.motor = Motor
        self.PLC = PLC
        # STYLING
        self.SELECT_BACKGROUND = cfg['theme']['select_background']
        self.DEFAULT_BACKGROUND = root.cget('bg')
        CLOCK_FONT = cfg['theme']['clock_font']
        FONT = cfg['theme']['font']
        FRAME_PADX = 5
        FRAME_PADY = 5
        BUTTON_PADX = 5
        BUTTON_PADY = 5

        # Root resizing
        root.rowconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        root.columnconfigure(1, weight=1)
        # Root frames
        plotFrame = ttk.Frame(root)
        plotFrame.grid(row=0, column=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY) 
        controlFrame = tk.Frame(root)
        controlFrame.grid(row=0, column=0, rowspan=2, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY) 
        for i in range(5):
            controlFrame.rowconfigure(i, weight=1)
        for j in range(2):
            controlFrame.columnconfigure(j, uniform=True)
        # Frames for other objects
        self.directionFrame = tk.LabelFrame(plotFrame, text = "Antenna Position")  # Frame that holds matplotlib azimuth/elevation plot
        self.spectrumFrame = tk.LabelFrame(plotFrame, text = "Spectrum Analyzer")   # Frame that holds matplotlib spectrum plot
        self.directionFrame.grid(row = 0, column = 0, sticky = NSEW)
        self.spectrumFrame.grid(row = 0, column = 1, sticky=NSEW)
        plotFrame.rowconfigure(0, weight=1)
        plotFrame.columnconfigure(0, weight=1)
        plotFrame.columnconfigure(1, weight=1)
        # Clock
        self.clockLabel = tk.Label(controlFrame, font=CLOCK_FONT)
        self.clockLabel.grid(row=0, column=0, columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        # Drive Status
        azStatusFrame = tk.LabelFrame(controlFrame, text='Azimuth Drive')
        azStatusFrame.grid(row=1, column=0, sticky=(N, E, W), padx=FRAME_PADX, pady=FRAME_PADY)
        azStatusFrame.columnconfigure(0, weight=1)
        self.azStatus = tk.Button(azStatusFrame, text='STOPPED', font=FONT, state=DISABLED, width=6)
        self.azStatus.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        elStatusFrame = tk.LabelFrame(controlFrame, text='Elevation Drive')
        elStatusFrame.grid(row=1, column=1, sticky=(N, E, W), padx=FRAME_PADX, pady=FRAME_PADY)
        elStatusFrame.columnconfigure(0, weight=1)
        self.elStatus = tk.Button(elStatusFrame, text='STOPPED', font=FONT, state=DISABLED, width=6)
        self.elStatus.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        # PLC Operations
        chainFrame = tk.LabelFrame(controlFrame, text='PLC Operations')
        chainFrame.grid(row=2, column=0, sticky=(N, E, W), columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        for i in range(2):
            chainFrame.columnconfigure(i, weight=1, uniform=True)
        self.initP1Button = tk.Button(chainFrame, font=FONT, text='INIT', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.P1_INIT.value,), {'delay': 15.0}))
        self.initP1Button.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.killP1Button = tk.Button(chainFrame, font=FONT, text='DISABLE', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.P1_DISABLE.value,), {'delay': 10.0}))
        self.killP1Button.grid(row=0, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.sleepP1Button = tk.Button(chainFrame, font=FONT, text='SLEEP', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.SLEEP.value,)))
        self.sleepP1Button.grid(row=1, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.returnP1Button = tk.Button(chainFrame, font=FONT, text='RETURN', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.RETURN_OPCODES.value,)))
        self.returnP1Button.grid(row=1, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.dfs1Button = tk.Button(chainFrame, font=FONT, text='DFS1', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.DFS_CHAIN1.value,)))
        self.dfs1Button.grid(row=2, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.ems1Button = tk.Button(chainFrame, font=FONT, text='EMS1', command=lambda:self.PLC.threadHandler(self.PLC.query, (opcodes.EMS_CHAIN1.value,)))
        self.ems1Button.grid(row=2, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.PLC_OUTPUTS_LIST = (self.sleepP1Button, self.dfs1Button, self.ems1Button)              # Mutually exclusive buttons for which only one should be selected
        # Mode
        modeFrame = tk.LabelFrame(controlFrame, text='Mode')
        modeFrame.grid(row=3, column=0, sticky=(N, E, W), columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        modeFrame.columnconfigure(0, weight=1)
        self.standbyButton = tk.Button(modeFrame, text='Standby', font=FONT, bg=self.SELECT_BACKGROUND)
        self.standbyButton.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.manualButton = tk.Button(modeFrame, text='Manual', font=FONT, bg=self.DEFAULT_BACKGROUND)
        self.manualButton.grid(row=1, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.autoButton = tk.Button(modeFrame, text='Auto', font=FONT, bg=self.DEFAULT_BACKGROUND, state=DISABLED)
        self.autoButton.grid(row=2, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.MODE_BUTTONS_LIST = (self.standbyButton, self.manualButton, self.autoButton)
        # Connection Status
        connectionsFrame = tk.LabelFrame(controlFrame, text='Connection Status')
        connectionsFrame.grid(row=4, column=0, sticky=(N, E, W), columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        for i in range(2):
            connectionsFrame.columnconfigure(i, weight=1)
        visaLabel = tk.Label(connectionsFrame, text='VISA:', font=FONT)
        visaLabel.grid(row=0, column=0, sticky=W, padx=BUTTON_PADX, pady=BUTTON_PADY)
        motorLabel = tk.Label(connectionsFrame, text='MOTOR:', font=FONT)
        motorLabel.grid(row=1, column=0, sticky=W, padx=BUTTON_PADX, pady=BUTTON_PADY)
        plcLabel = tk.Label(connectionsFrame, text='PLC:', font=FONT)
        plcLabel.grid(row=2, column=0, sticky=W, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.visaStatus = tk.Button(connectionsFrame, text='NC', font=FONT, state=DISABLED, width=12)
        self.visaStatus.grid(row=0, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.motorStatus = tk.Button(connectionsFrame, text='NC', font=FONT, state=DISABLED, width=12)
        self.motorStatus.grid(row=1, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.plcStatus = tk.Button(connectionsFrame, text='NC', font=FONT, state=DISABLED, width=12)
        self.plcStatus.grid(row=2, column=1, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        

        # TODO: deprecate
        self.quickButton        = tk.LabelFrame(controlFrame, text='Control')
        self.quickButton.grid(row = 5, column = 0, sticky=NSEW, columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        self.quickButton.columnconfigure(0, weight=0)
        self.EmargencyStop      = tk.Button(self.quickButton, text = "Emergency Stop", font = FONT, bg = 'red', fg = 'white', command = self.Estop)
        self.Park               = tk.Button(self.quickButton, text = "Park", font = FONT, bg = 'blue', fg = 'white', command = self.park)
        self.openFreeWriting    = tk.Button(self.quickButton, text = "Motor Terminal", font = FONT, command = self.freewriting)
       
        self.EmargencyStop.pack(expand=True, fill=BOTH, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.Park.pack(expand=True, fill=BOTH, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.openFreeWriting.pack(expand=True, fill=BOTH, padx=BUTTON_PADX, pady=BUTTON_PADY)

        # self.updateOutput( oFile, root )      # deprecate maybe

        root.after(1000, self.update_time )


    def initDevice(self, event, device, port):
        """Connects to the respective resource and updates the attribute which stores the resource name.

        Args:
            event (event): Event passed by tkinter
            device (string): Can be 'visa', 'motor', or 'plc'.
            port (string): Name of the VISA ID or COM port to connect to.
        """
        if device == 'visa':
            with visaLock:
                self.Vi.connectToRsrc(port)
                self.instrument = port
                self.scpiApplyConfig(self.timeoutWidget.get(), self.chunkSizeWidget.get())
                try:
                    idn = self.Vi.identify()
                    shortidn = str(idn[0]) + ', ' + str(idn[1]) + ', ' + str(idn[2])
                    self.spectrumFrame.configure(text=shortidn)
                except Exception as e:
                    logging.error(f'{type(e).__name__}: {e}')
                    return
        elif device == 'motor':
            self.motorPort = self.motorSelectBox.get()[:4]
            self.motor.openSerial(self.motorPort)
        elif device == 'plc':
            self.PLC.openSerial(port)
            self.PLC.threadHandler(self.PLC.queryStatus)
            self.plcPort = port

    def setStatus(self, widget, text=None, background=None):
        """Sets the text and background of a widget being used as a status indicator

        Args:
            widget (tk.Button): Tkinter widget being used as a status indicator. ttk.Button will NOT work.
            text (string, optional): Text to replace in the button widget. Defaults to None.
            background (string, optional): Color in any tkinter-compatible format, although ideally hex for compatibility. Defaults to None.
        """
        if text is not None:
            widget.configure(text=text)
        if background is not None:
            widget.configure(background=background)

    
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

    def openHelp(self):
        """Opens help menu on a new toplevel window.
        """
        continueCheck = messagebox.askokcancel(title='Open wiki', message='This will open a new web browser page. Continue?')
        if continueCheck:
            webbrowser.open('https://github.com/RomiFC/RF-DFS/wiki')
        

    def openConfig(self):
        """Opens configuration menu on a new toplevel window.
        """
        parent = Toplevel()

        def onRefreshPress():
            """Update the values in the SCPI instrument selection box
            """
            logging.info('Searching for resources...')
            self.instrSelectBox['values'] = self.Vi.rm.list_resources()
            self.motorSelectBox['values'] = list(serial.tools.list_ports.comports())
            self.plcSelectBox['values'] = list(serial.tools.list_ports.comports())
        def onEnableTermPress():
            if self.enableTerm.get():
                self.selectTermWidget.config(state='readonly')
            else:
                self.selectTermWidget.config(state='disabled')  
        def onDisconnectPress(device):
            match device:
                case 'visa':
                    self.Vi.closeSession()
                    self.instrument = ''
                    self.instrSelectBox.set('')
                case 'motor':
                    # TODO: Make this do something
                    self.motorPort = ''
                    self.motorSelectBox.set('')
                case 'plc':
                    self.PLC.close()
                    self.plcPort = ''
                    self.plcSelectBox.set('')



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
        self.motorSelectBox = ttk.Combobox(connectFrame, values = list(serial.tools.list_ports.comports()), width=40)
        self.motorSelectBox.grid(row = 1, column = 1, padx = 10, pady = 5)
        self.plcSelectBox = ttk.Combobox(connectFrame, values = list(serial.tools.list_ports.comports()), width=40)
        self.plcSelectBox.grid(row = 2, column = 1, padx = 10, pady = 5)
        instrCloseButton = ttk.Button(connectFrame, text = 'Disconnect', command=lambda: onDisconnectPress(device='visa'))
        instrCloseButton.grid(row = 0, column = 2, padx=5)
        motorCloseButton = ttk.Button(connectFrame, text = 'Disconnect', command=lambda: onDisconnectPress(device='motor'))
        motorCloseButton.grid(row = 1, column = 2, padx=5)
        plcCloseButton = ttk.Button(connectFrame, text = 'Disconnect', command=lambda: onDisconnectPress(device='plc'))
        plcCloseButton.grid(row = 2, column = 2, padx=5)
        self.instrSelectBox.set(self.instrument)
        self.motorSelectBox.set(self.motorPort)
        self.plcSelectBox.set(self.plcPort)

        self.instrSelectBox.bind("<<ComboboxSelected>>", lambda event: self.initDevice(event, device='visa', port=self.instrSelectBox.get()))
        self.motorSelectBox.bind("<<ComboboxSelected>>", lambda event: self.initDevice(event, device='motor', port=self.motorSelectBox.get()[:4]))
        self.plcSelectBox.bind("<<ComboboxSelected>>", lambda event: self.initDevice(event, device='plc', port=self.plcSelectBox.get()[:4]))

        # VISA CONFIGURATION FRAME
        configFrame = ttk.LabelFrame(parent, borderwidth = 2, text = "VISA Configuration")
        configFrame.grid(row = 1, column = 0, padx=20, pady=10, sticky=NSEW, rowspan=2)
        timeoutLabel = ttk.Label(configFrame, text = 'Timeout (ms)')
        timeoutLabel.grid(row = 0, column = 0, pady=5)
        self.timeoutWidget = ttk.Spinbox(configFrame, from_=TIMEOUT_MIN, to=TIMEOUT_MAX, increment=100, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.timeoutWidget.grid(row = 1, column = 0, padx=20, pady=5, columnspan=2)
        self.timeoutWidget.set(self.timeout)
        chunkSizeLabel = ttk.Label(configFrame, text = 'Chunk size (Bytes)')
        chunkSizeLabel.grid(row = 2, column = 0, pady=5)
        self.chunkSizeWidget = ttk.Spinbox(configFrame, from_=CHUNK_SIZE_MIN, to=CHUNK_SIZE_MAX, increment=10240, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.chunkSizeWidget.grid(row = 3, column = 0, padx=20, pady=5, columnspan=2)
        self.chunkSizeWidget.set(self.chunkSize)
        applyButton = ttk.Button(configFrame, text = "Apply Changes", command = lambda:self.scpiApplyConfig(self.timeoutWidget.get(), self.chunkSizeWidget.get()))
        applyButton.grid(row = 7, column = 0, columnspan=2, pady=10)
        # VISA TERMINATION FRAME
        termFrame = ttk.LabelFrame(parent, borderwidth=2, text = 'Termination Methods')
        termFrame.grid(row = 1, column = 1, padx = 5, pady = 10, sticky=(N, E, W), ipadx=5, ipady=5)
        self.sendEndWidget = ttk.Checkbutton(termFrame, text = 'Send \'End or Identify\' on write', variable=self.sendEnd)
        self.sendEndWidget.grid(row = 0, column = 0, pady = 5)
        self.selectTermWidget = ttk.Combobox(termFrame, text='Termination Character', values=self.SELECT_TERM_VALUES, state='disabled')
        self.selectTermWidget.grid(row = 2, column = 0, pady = 5)
        self.enableTermWidget = ttk.Checkbutton(termFrame, text = 'Enable Termination Character', variable=self.enableTerm, command=lambda:onEnableTermPress())
        self.enableTermWidget.grid(row = 1, column = 0, pady = 5)
        # REFRESH BUTTON
        self.refreshButton = ttk.Button(parent, text = "Refresh All", command = lambda:onRefreshPress())
        self.refreshButton.grid(row = 2, column = 1, padx=5)
    

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
    
    def plotInterface(self, parentWidget):
        """Generates the main control interface the root level. Also generates frames to contain objects for SpecAn and AziElePlot
        """
        # TODO: Deprecate with the new control interface

        # parent = parentWidget

        # styling
        # parent.rowconfigure(0, weight=1)
        # parent.rowconfigure(1, weight=1)
        # parent.rowconfigure(2, weight=1)
        # parent.rowconfigure(3, weight=1)
        # parent.columnconfigure(0, weight=0)
        # parent.columnconfigure(1, weight=1)
        # parent.columnconfigure(2, weight=1)
        
        # COLUMN 0 WIDGETS
        # antennaPosFrame          = ttk.LabelFrame( parent, text = "Antenna Position" )
        # antennaPosFrame.grid( row = 1, column = 0 , padx = 20 , pady = 10, sticky=(NSEW))

        # self.azimuth_label      = ttk.Label(antennaPosFrame, text = "Azimuth:")
        # self.elevation_label    = ttk.Label(antennaPosFrame, text = "Elevation:")
        # self.inputAzimuth       = ttk.Entry(antennaPosFrame)
        # self.inputElevation     = ttk.Entry(antennaPosFrame)

        # self.azimuth_label.grid( row = 0, column = 0, padx = 10, pady=5)
        # self.elevation_label.grid( row = 1, column = 0, padx = 10, pady=5)
        # self.inputAzimuth.grid( row = 0, column = 1, padx = 10)
        # self.inputElevation.grid( row = 1, column = 1, padx = 10)

        # self.printbutton        = tk.Button( antennaPosFrame, text = "Enter", command = self.input )
        # self.printbutton.grid(row = 2, column = 1, padx = 20, pady = 5, sticky=E)

        # clockFrame              = ttk.Frame(parent)
        # clockFrame.grid(row=0,column=0)
        # self.clock_label        = ttk.Label(clockFrame, font = ('Arial', 14))
        # self.clock_label.pack()
        # self.quickButton        = ttk.Frame( parent )
        # self.quickButton.grid(row = 2, column = 0, padx = 20, pady = 10, sticky=(S))
        # self.EmargencyStop      = tk.Button(self.quickButton, text = "Emergency Stop", font = ('Arial', 16 ), bg = 'red', fg = 'white', command= self.Estop, width=15)
        # self.Park               = tk.Button(self.quickButton, text = "Park", font = ('Arial', 16) , bg = 'blue', fg = 'white', command = self.park, width=15)
        # self.openFreeWriting    = tk.Button(self.quickButton, text = "Motor Terminal", font = ('Arial', 16 ), command= self.freewriting, width=15)
       
        # self.EmargencyStop.pack( pady = 5 )
        # self.Park.pack( pady = 5 )
        # self.openFreeWriting.pack( pady = 5 )
            
        # TODO: Cleanup boilerplate code below
    def getMotorPort(self):
        return self.motorSelectBox.get()

    def update_time(self):
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.clockLabel.config(text=current_time)
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
        Vi (class): Instance of VisaIO that contains methods for communicating with SCPI instruments.
        parentWidget (tk::LabelFrame, tk::Frame): Parent widget which will contain graph and control widgets.
    """
    def __init__(self, Vi, parentWidget):
        # FLAGS
        self.contSweepFlag = False
        self.singleSweepFlag = False
        # STATE VARIABLES
        self.loopState = state.IDLE
        # CONSTANTS
        self.RBW_FILTER_SHAPE_VALUES = ('Gaussian', 'Flattop')
        self.RBW_FILTER_SHAPE_VAL_ARGS = ('GAUS', 'FLAT')
        self.RBW_FILTER_TYPE_VALUES = ("-3 dB (Normal)", "-6 dB", "Impulse", "Noise")
        self.RBW_FILTER_TYPE_VAL_ARGS = ('DB3', 'DB6', 'IMP', 'NOISE')
        # TKINTER VARIABLES
        global tkSweepType, tkSpanType, tkRbwType, tkVbwType, tkBwRatioType, tkAttenType
        tkSweepType = BooleanVar()
        tkSpanType = BooleanVar()
        tkRbwType = BooleanVar()
        tkVbwType = BooleanVar()
        tkBwRatioType = BooleanVar()
        tkAttenType = BooleanVar()
        # PLOT PARAMETERS
        self.color = None
        self.marker = None
        self.linestyle = None
        self.linewidth = None
        self.markersize = None
        # VISA OBJECT
        self.Vi = Vi
        # PARENT
        spectrumFrame = parentWidget
        spectrumFrame.rowconfigure(0, weight=1)     # Allow this row to resize
        spectrumFrame.rowconfigure(1, weight=0)     # Prevent this row from resizing
        spectrumFrame.rowconfigure(2, weight=0)     # Prevent this row from resizing
        spectrumFrame.rowconfigure(3, weight=0)     # Prevent this row from resizing
        spectrumFrame.columnconfigure(0, weight=1)  # Allow this column to resize
        spectrumFrame.columnconfigure(1, weight=0)  # Prevent this column from resizing

        # MATPLOTLIB GRAPH
        self.fig = plt.figure(linewidth=0, edgecolor="#04253a")
        self.ax = self.fig.add_subplot()
        self.ax.set_title("Spectrum Plot")
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Power Spectral Density (dBm/RBW)")
        self.ax.autoscale(enable=False, tight=True)
        self.ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
        self.ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
        self.ax.xaxis.set_major_formatter(ticker.EngFormatter(unit=''))
        self.spectrumDisplay = FigureCanvasTkAgg(self.fig, master=spectrumFrame)
        self.spectrumDisplay.get_tk_widget().grid(row = 0, column = 0, sticky=NSEW, rowspan=4)

        # MEASUREMENT COMMANDS
        measurementTab = ttk.Notebook(spectrumFrame)
        self.tab1 = ttk.Frame(measurementTab)
        self.tab2 = ttk.Frame(measurementTab)
        self.tab3 = ttk.Frame(measurementTab)
        measurementTab.add(self.tab1, text="Freq")
        measurementTab.add(self.tab2, text="BW")
        measurementTab.add(self.tab3, text="Amp")
        measurementTab.grid(row=0, column=1, sticky=NSEW)

        # MEASUREMENT TAB 1 (FREQUENCY)
        centerFreqFrame = ttk.LabelFrame(self.tab1, text="Center Frequency")
        centerFreqFrame.grid(row=0, column=0, sticky=E)
        self.centerFreqEntry = ttk.Entry(centerFreqFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.centerFreqEntry.pack()

        spanFrame = ttk.LabelFrame(self.tab1, text="Span")
        spanFrame.grid(row=1, column=0, sticky=E)
        self.spanEntry = ttk.Entry(spanFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.spanEntry.pack()
        self.spanSweptButton = ttk.Radiobutton(spanFrame, variable=tkSpanType, text = "Swept Span", value=1)
        self.spanSweptButton.pack(anchor=W)
        self.spanZeroButton = ttk.Radiobutton(spanFrame, variable=tkSpanType, text = "Zero Span", value=0)
        self.spanZeroButton.pack(anchor=W)
        self.spanFullButton = ttk.Button(spanFrame, text = "Full Span")
        self.spanFullButton.pack(anchor=S, fill=BOTH)

        startFreqFrame = ttk.LabelFrame(self.tab1, text="Start Frequency")
        startFreqFrame.grid(row=2, column=0)
        self.startFreqEntry = ttk.Entry(startFreqFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.startFreqEntry.pack()

        stopFreqFrame = ttk.LabelFrame(self.tab1, text="Stop Frequency")
        stopFreqFrame.grid(row=3, column=0)
        self.stopFreqEntry = ttk.Entry(stopFreqFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.stopFreqEntry.pack()

        sweepTimeFrame = ttk.LabelFrame(self.tab1, text="Sweep Time")
        sweepTimeFrame.grid(row=4, column=0)
        self.sweepTimeEntry = ttk.Entry(sweepTimeFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.sweepTimeEntry.pack()
        self.sweepAutoButton = ttk.Radiobutton(sweepTimeFrame, variable=tkSweepType, text="Auto", value=AUTO)
        self.sweepAutoButton.pack(anchor=W)
        self.sweepManButton = ttk.Radiobutton(sweepTimeFrame, variable=tkSweepType, text="Manual", value=MANUAL)
        self.sweepManButton.pack(anchor=W)
        


        # MEASUREMENT TAB 2 (BANDWIDTH)
        rbwFrame = ttk.LabelFrame(self.tab2, text="Res BW")
        rbwFrame.grid(row=0, column=0)
        self.rbwEntry = ttk.Entry(rbwFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.rbwEntry.pack()
        self.rbwAutoButton = ttk.Radiobutton(rbwFrame, variable=tkRbwType, text="Auto", value=AUTO)
        self.rbwAutoButton.pack(anchor=W)
        self.rbwManButton = ttk.Radiobutton(rbwFrame, variable=tkRbwType, text="Manual", value=MANUAL)
        self.rbwManButton.pack(anchor=W)
        
        vbwFrame = ttk.LabelFrame(self.tab2, text="Video BW")
        vbwFrame.grid(row=1, column=0)
        self.vbwEntry = ttk.Entry(vbwFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.vbwEntry.pack()
        self.vbwAutoButton = ttk.Radiobutton(vbwFrame, variable=tkVbwType, text="Auto", value=AUTO)
        self.vbwAutoButton.pack(anchor=W)
        self.vbwManButton = ttk.Radiobutton(vbwFrame, variable=tkVbwType, text="Manual", value=MANUAL)
        self.vbwManButton.pack(anchor=W)

        bwRatioFrame = ttk.LabelFrame(self.tab2, text="VBW:RBW")
        bwRatioFrame.grid(row=2, column=0)
        self.bwRatioEntry = ttk.Entry(bwRatioFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.bwRatioEntry.pack()
        self.bwRatioAutoButton = ttk.Radiobutton(bwRatioFrame, variable=tkBwRatioType, text="Auto", value=AUTO)
        self.bwRatioAutoButton.pack(anchor=W)
        self.bwRatioManButton = ttk.Radiobutton(bwRatioFrame, variable=tkBwRatioType, text="Manual", value=MANUAL)
        self.bwRatioManButton.pack(anchor=W)

        rbwFilterShapeFrame = ttk.LabelFrame(self.tab2, text="RBW Filter Shape")
        rbwFilterShapeFrame.grid(row=3, column=0)
        self.rbwFilterShapeCombo = ttk.Combobox(rbwFilterShapeFrame, values = self.RBW_FILTER_SHAPE_VALUES)
        self.rbwFilterShapeCombo.pack(anchor=W)

        rbwFilterTypeFrame = ttk.LabelFrame(self.tab2, text="RBW Filter Type")
        rbwFilterTypeFrame.grid(row=4, column=0)
        self.rbwFilterTypeCombo = ttk.Combobox(rbwFilterTypeFrame, values = self.RBW_FILTER_TYPE_VALUES)
        self.rbwFilterTypeCombo.pack(anchor=W)

        # MEASUREMENT TAB 3 (AMPLITUDE)
        refLevelFrame = ttk.LabelFrame(self.tab3, text="Ref Level")
        refLevelFrame.grid(row=0, column=0)
        self.refLevelEntry = ttk.Entry(refLevelFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.refLevelEntry.pack()

        yScaleFrame = ttk.LabelFrame(self.tab3, text="Scale/Division")
        yScaleFrame.grid(row=1, column=0)
        self.yScaleEntry = ttk.Entry(yScaleFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.yScaleEntry.pack()

        numDivFrame = ttk.LabelFrame(self.tab3, text="Number of Divisions")
        numDivFrame.grid(row=2, column=0)
        self.numDivEntry = ttk.Entry(numDivFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.numDivEntry.pack()

        attenFrame = ttk.LabelFrame(self.tab3, text="Mech Atten")
        attenFrame.grid(row=3, column=0)
        self.attenEntry = ttk.Entry(attenFrame, validate="key", validatecommand=(isNumWrapper, '%P'))
        self.attenEntry.pack()
        self.attenAutoButton = ttk.Radiobutton(attenFrame, variable=tkAttenType, text="Auto", value=AUTO)
        self.attenAutoButton.pack(anchor=W)
        self.attenManButton = ttk.Radiobutton(attenFrame, variable=tkAttenType, text="Manual", value=MANUAL)
        self.attenManButton.pack(anchor=W)

        unitPowerFrame = ttk.LabelFrame(self.tab3, text="Unit (Power)")
        unitPowerFrame.grid(row=4, column=0)
        self.unitPowerEntry = ttk.Entry(unitPowerFrame, state="disabled")
        self.unitPowerEntry.pack()

        # SWEEP BUTTONS
        initButton = ttk.Button(spectrumFrame, text="Initialize", command=lambda:self.setState(state.INIT))
        initButton.grid(row=1, column=1, sticky=NSEW)
        self.singleSweepButton = ttk.Button(spectrumFrame, text="Single Sweep", command=lambda:self.singleSweep())
        self.singleSweepButton.grid(row=2, column=1, sticky=NSEW)
        self.continuousSweepButton = ttk.Button(spectrumFrame, text="Continuous", command=lambda:self.toggleAnalyzerDisplay())
        self.continuousSweepButton.grid(row=3, column=1, sticky=NSEW) 

        self.bindWidgets() 

        # PARAMETERS
        CenterFreq.update(widget=self.centerFreqEntry)
        Span.update(widget=self.spanEntry)
        StartFreq.update(widget=self.startFreqEntry)
        StopFreq.update(widget=self.stopFreqEntry)
        SweepTime.update(widget=self.sweepTimeEntry)
        Rbw.update(widget=self.rbwEntry)
        Vbw.update(widget=self.vbwEntry)
        BwRatio.update(widget=self.bwRatioEntry)
        Ref.update(widget=self.refLevelEntry)
        NumDiv.update(widget=self.numDivEntry)
        YScale.update(widget=self.yScaleEntry)
        Atten.update(widget=self.attenEntry)
        SpanType.update(widget=tkSpanType)
        SweepType.update(widget=tkSweepType)
        RbwType.update(widget=tkRbwType)
        VbwType.update(widget=tkVbwType)
        BwRatioType.update(widget=tkBwRatioType)
        RbwFilterShape.update(widget=self.rbwFilterShapeCombo)
        RbwFilterType.update(widget=self.rbwFilterTypeCombo)
        AttenType.update(widget=tkAttenType)
        YAxisUnit.update(widget=self.unitPowerEntry)

        # Generate thread to handle live data plot in background
        analyzerLoop = threading.Thread(target=self.analyzerDisplayLoop, daemon=True)
        analyzerLoop.start()

    def bindWidgets(self):
        """Binds tkinter events to the widgets' respective commands.
        """
        self.centerFreqEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, centerfreq = self.centerFreqEntry.get()))
        self.spanEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, span = self.spanEntry.get()))
        self.startFreqEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, startfreq = self.startFreqEntry.get()))
        self.stopFreqEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, stopfreq = self.stopFreqEntry.get()))
        self.sweepTimeEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, sweeptime = self.sweepTimeEntry.get()))
        self.rbwEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, rbw = self.rbwEntry.get()))
        self.vbwEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, vbw = self.vbwEntry.get()))
        self.bwRatioEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, bwratio = self.bwRatioEntry.get()))
        self.refLevelEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, ref = self.refLevelEntry.get()))
        self.yScaleEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, yscale = self.yScaleEntry.get()))
        self.numDivEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, numdiv = self.numDivEntry.get()))
        self.attenEntry.bind('<Return>', lambda event: self.setAnalyzerThreadHandler(event, atten = self.attenEntry.get()))

        self.sweepAutoButton.configure(command = lambda: self.setAnalyzerThreadHandler(sweeptype=AUTO))
        self.sweepManButton.configure(command = lambda: self.setAnalyzerThreadHandler(sweeptype=MANUAL))
        self.spanSweptButton.configure(command = lambda: self.setAnalyzerThreadHandler(spantype=10e9))
        self.spanZeroButton.configure(command = lambda: self.setAnalyzerThreadHandler(spantype=0))
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

    def toggleInputs(self, action):
        frames = (self.tab1, self.tab2, self.tab3)
        widgets = (self.singleSweepButton, self.continuousSweepButton)

        if action == ENABLE:
            for frame in frames:
                enableChildren(frame)
            for widget in widgets:
                widget.configure(state='enable')
        elif action == DISABLE:
            for frame in frames:
                disableChildren(frame)
            for widget in widgets:
                widget.configure(state='disable')

    def setAnalyzerPlotLimits(self, **kwargs):
        """Sets self.ax limits to parameters passed in **kwargs if they exist. If not, gets relevant widget values to set limits.

        Args:
            xmin (float, optional): Minimum X value
            xmax (float, optional): Maximum X value
            ymin (float, optional): Minimum Y value
            ymax (float, optional): Maximum Y value
        """
        if 'xmin' in kwargs and 'xmax' in kwargs:
            self.ax.set_xlim(kwargs["xmin"], kwargs["xmax"])
        else:
            if tkSpanType.get() == 0:
                xmin = 0
                xmax = round(float(self.sweepTimeEntry.get()), 5)
                self.ax.set_xlabel("Time (s)")
            else:
                xmin = float(self.startFreqEntry.get())
                xmax = float(self.stopFreqEntry.get())
                self.ax.set_xlabel("Frequency (Hz)")
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

    def setAnalyzerValue(self, centerfreq=None, span=None, startfreq=None, stopfreq=None, sweeptime=None, rbw=None, vbw=None, bwratio=None, ref=None, numdiv=None, yscale=None, atten=None, spantype=None, sweeptype=None, rbwtype=None, vbwtype=None, bwratiotype=None, rbwfiltershape=None, rbwfiltertype=None, attentype=None):
        """Issues command to spectrum analyzer with the value of kwarg as the argument and queries for widget values. If the value is None or if there are no kwargs, query the spectrum analyzer to set widget values instead.
        
        Args:
            centerfreq (float, optional): Center frequency in hertz. Defaults to None.
            span (float, optional): Frequency span in hertz. Defaults to None.
            startfreq (float, optional): Start frequency in hertz. Defaults to None.
            stopfreq (float, optional): Stop frequency in hertz. Defaults to None.
            sweeptime (float, optional): Estimated sweep time in seconds. Defaults to None.
            rbw (float, optional): Resolution bandwidth. Defaults to None.
            vbw (float, optional): Video bandwidth. Defaults to None.
            bwratio (float, optional): RBW:VBW ratio. Defaults to None.
            ref (float, optional): Reference level in dBm. Defaults to None.
            numdiv (float, optional): Number of yscale divisions. Defaults to None.
            yscale (float, optional): Scale per division in dB. Defaults to None.
            atten (float, optional): Mechanical attenuation in dB. Defaults to None.
            spantype (bool, optional): 1 for swept span, 0 for zero span (time domain). Defaults to None.
            rbwtype (bool, optional): 1 for auto, 0 for manual. Defaults to None.
            vbwtype (bool, optional): 1 for auto, 0 for manual. Defaults to None.
            bwratiotype (bool, optional): 1 for auto, 0 for manual. Defaults to None.
            rbwfiltershape (int, optional): Index of the combobox widget tied to RBW_FILTER_SHAPE_VAL_ARGS. Defaults to None.
            rbwfiltertype (int, optional): Index of the combobox widget tied to RBW_FILTER_TYPE_VAL_ARGS. Defaults to None.
            attentype (bool, optional): 1 for auto, 0 for manual. Defaults to None.
        """
        # TODO: Make sure all commands have full functionality
        global visaLock
        _list = Parameter.instances

        CenterFreq.update(arg=centerfreq)
        Span.update(arg=span)
        StartFreq.update(arg=startfreq)
        StopFreq.update(arg=stopfreq)
        SweepTime.update(arg=sweeptime)
        Rbw.update(arg=rbw)
        Vbw.update(arg=vbw)
        BwRatio.update(arg=bwratio)
        Ref.update(arg=ref)
        NumDiv.update(arg=numdiv)
        YScale.update(arg=yscale)
        Atten.update(arg=atten)
        SpanType.update(arg=spantype)
        SweepType.update(arg=sweeptype)
        RbwType.update(arg=rbwtype)
        VbwType.update(arg=vbwtype)
        BwRatioType.update(arg=bwratiotype)
        if rbwfiltershape is not None:
            RbwFilterShape.update(arg=self.RBW_FILTER_SHAPE_VAL_ARGS[rbwfiltershape])
        if rbwfiltertype is not None:
            RbwFilterType.update(arg=self.RBW_FILTER_TYPE_VAL_ARGS[rbwfiltertype])
        AttenType.update(arg=attentype)
        YAxisUnit.update(arg=None)

        # Sort the list so dictionaries with 'arg': None are placed (and executed) after write commands
        for index in range(len(_list)):
            if _list[index].arg is not None:
                _list.insert(0, _list.pop(index))


        # EXECUTE COMMANDS
        logging.debug(f"setAnalyzerValue generated list of dictionaries '_list' with value {_list}")
        with visaLock:
            for parameter in _list:
                # Issue command with argument
                if parameter.arg is not None:
                    self.Vi.openRsrc.write(f'{parameter.command} {parameter.arg}')
                # Set widgets without issuing a parameter to command
                try:
                    buffer = self.Vi.openRsrc.query_ascii_values(f'{parameter.command}?') # Default converter is float
                except:
                    buffer = self.Vi.openRsrc.query_ascii_values(f'{parameter.command}?', converter='s')
                logging.verbose(f"Command {parameter.command}? returned {buffer}")
                parameter.update(value=buffer)
                clearAndSetWidget(parameter.widget, buffer)
        # Set plot limits
        with specPlotLock:
            self.setAnalyzerPlotLimits()
        return
    
    def setState(self, val):
        self.loopState = val

    def analyzerDisplayLoop(self):
        global visaLock, specPlotLock

        while TRUE:
            match self.loopState:
                case state.IDLE:
                    # Prevent this thread from taking up too much utilization
                    self.toggleInputs(DISABLE)
                    time.sleep(IDLE_DELAY)
                    continue

                case state.INIT:
                    # Maintain this loop to prevent fatal error if the connected device is not a spectrum analyzer.
                    if self.Vi.isSessionOpen() == FALSE:
                        logging.error(f"Session to the analyzer is not open. Set up connection with Options > Configure..., then reinitialize.")
                        self.loopState = state.IDLE
                        continue
                    try:
                        visaLock.acquire()
                        self.Vi.resetAnalyzerState()
                        self.Vi.queryPowerUpErrors()
                        self.Vi.testBufferSize()
                        # Set widget values
                        self.setAnalyzerValue()
                        visaLock.release()
                        self.loopState = state.LOOP
                    except Exception as e:
                        logging.error(f'{type(e).__name__}: {e}')
                        try:
                            self.Vi.queryErrors()
                        except Exception as e:
                            pass
                            # logging.error(f'{type(e).__name__}: {e}. Could not query errors from device.')
                        self.toggleInputs(ENABLE)
                        visaLock.release()
                        self.loopState = state.IDLE

                case state.LOOP:
                    # Main analyzer loop
                    # TODO: variable time.sleep based on analyzer sweep time
                    if self.Vi.isSessionOpen() == FALSE:
                        logging.info(f"Lost connection to the analyzer.")
                        self.loopState = state.IDLE
                        continue
                    self.toggleInputs(ENABLE)
                    if self.contSweepFlag or self.singleSweepFlag:
                        visaLock.acquire()
                        try: # Check if the instrument is busy calibrating, settling, sweeping, or measuring 
                            if self.Vi.getOperationRegister() & 0b00011011:
                                continue 
                        except Exception as e:
                            logging.fatal(f'{type(e).__name__}: {e}')
                            logging.fatal("Could not retrieve information from Operation Status Register.")
                            visaLock.release()
                            self.contSweepFlag = False
                            continue
                        try:
                            with specPlotLock:
                                if 'lines' in locals():     # Remove previous plot if it exists
                                    lines.pop(0).remove()
                                buffer = self.Vi.openRsrc.query_ascii_values(":READ:SAN?")
                                xAxis = buffer[::2]
                                yAxis = buffer[1::2]
                                lines = self.ax.plot(xAxis, yAxis, color=self.color, marker=self.marker, linestyle=self.linestyle, linewidth=self.linewidth, markersize=self.markersize)
                                self.ax.grid(visible=True)
                                self.spectrumDisplay.draw()
                        except Exception as e:
                            logging.fatal(f'{type(e).__name__}: {e}')
                            self.contSweepFlag = False
                        visaLock.release()
                        self.singleSweepFlag = False
                        time.sleep(ANALYZER_LOOP_DELAY)
                    else:
                        # Prevent this thread from taking up too much utilization
                        time.sleep(IDLE_DELAY)

    def toggleAnalyzerDisplay(self):
        """sets contSweepFlag != contSweepFlag to control analyzerDisplayLoop()
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
        """Sets singleSweepFlag TRUE and contSweepFlag FALSE to control analyzerDisplayLoop()
        """
        if self.Vi.isSessionOpen() == FALSE:
            logging.error("Cannot initiate sweep, session to the analyzer is not open.")
            self.contSweepFlag = False
            return
        
        self.contSweepFlag = False
        self.singleSweepFlag = True

    def setPlotThreadHandler(self, color=None, marker=None, linestyle=None, linewidth=None, markersize=None):
        thread = threading.Thread(target=self.setPlotParam, daemon=True, args=(color, marker, linestyle, linewidth, markersize))
        thread.start()

    def setPlotParam(self, color=None, marker=None, linestyle=None, linewidth=None, markersize=None):
        global specPlotLock

        if color is None:
            if self.color is not None:
                color = colorchooser.askcolor(initialcolor=self.color)[1]
            else:
                color = colorchooser.askcolor(initialcolor='#1f77b4')[1]
        with specPlotLock:
            self.color = color
            self.marker = marker
            self.linestyle = linestyle
            self.linewidth = linewidth
            self.markersize = markersize
            
class AziElePlot(FrontEnd):
    """Generates tkinter-embedded matplotlib graph of spectrum analyzer. Requires an instance of FrontEnd to be constructed with the name Front_End.

    Args:
        Motor (class): Instance of MotorIO that contains methods for communicating with the Parker Hannifin Motor Controller.
        parentWidget (tk::LabelFrame, tk::Frame): Parent widget which will contain graph and control widgets.
    """
    def __init__(self, Motor, parentWidget):
        # MOTOR INSTANCE
        self.Motor = Motor

        # PARENT
        self.parent = parentWidget
        self.parent.rowconfigure(0, weight=1)
        self.parent.columnconfigure(0, weight=1)

        # STATE VARIABLES
        self.loopState = state.IDLE
        self.axis0 = False              # Keeps track of drive x and y states so they can be accessed by the main thread to update status buttons in class FrontEnd
        self.axis1 = False

        # VARIABLES
        self.azArrow = None
        self.elArrow = None

        # STYLE
        font = 'Courier 14'
        padx = 2
        pady = 2

        # PLOT
        fig, (self.azAxis, self.elAxis) = plt.subplots(1, 2, subplot_kw=dict(projection='polar'))
        fig.set_size_inches(fig.get_size_inches()[0], fig.get_size_inches()[1] * 0.8)      # Sets to minimum height since two plots can appear large in the root window
        self.azAxis.set_title("Azimuth", va='bottom', y=1.1)
        self.elAxis.set_title("Elevation", va='bottom', y=1.1)
        self.azAxis.set_rticks([0.25, 0.5, 0.75], labels=[])
        self.elAxis.set_rticks([0.25, 0.5, 0.75], labels=[])
        self.azAxis.set_theta_zero_location('N')
        self.azAxis.set_theta_direction(-1)
        self.elAxis.set_thetagrids([0, 30, 60, 90, 120])
        self.azAxis.autoscale(enable=False, tight=True)
        self.elAxis.autoscale(enable=False, tight=True)
        self.azAxis.set_facecolor('#d5de9c')
        self.elAxis.set_facecolor('#d5de9c')
        self.elAxis.axvspan(0, -240/180.*np.pi, facecolor='0.85')
        self.azAxis.grid(color='#316931')
        self.elAxis.grid(color='#316931')

        self.bearingDisplay = FigureCanvasTkAgg(fig, master=self.parent)
        self.bearingDisplay.get_tk_widget().grid(row = 0, column = 0, sticky=NSEW, columnspan=2)


        # CONTROL FRAME
        self.ctrlFrame = ttk.Frame(self.parent)
        self.ctrlFrame.grid(row=2, column=0, sticky=NSEW, columnspan=1)
        for x in range(4):
            self.ctrlFrame.columnconfigure(x, weight=1)
        # FEEDBACK
        azFrame = ttk.Labelframe(self.ctrlFrame, text='Azimuth Angle')
        azFrame.grid(row=0, column=0, sticky=NSEW, padx=padx, pady=pady)
        azCmdFrame = ttk.Labelframe(self.ctrlFrame, text='Last Command')
        azCmdFrame.grid(row=0, column=1, sticky=NSEW, padx=padx, pady=pady)
        elFrame = ttk.Labelframe(self.ctrlFrame, text='Elevation Angle')
        elFrame.grid(row=0, column=2, sticky=NSEW, padx=padx, pady=pady)
        elCmdFrame = ttk.Labelframe(self.ctrlFrame, text='Last Command')
        elCmdFrame.grid(row=0, column=3, sticky=NSEW, padx=padx, pady=pady)
        self.azLabel = ttk.Label(azFrame, font=font, text=f'--')
        self.azLabel.grid(row=0, column=0, sticky=NSEW)
        self.elLabel = ttk.Label(elFrame, font=font, text=f'--')
        self.elLabel.grid(row=0, column=0, sticky=NSEW)
        self.azCmdLabel = ttk.Label(azCmdFrame, font=font, text=f'--')
        self.azCmdLabel.grid(row=0, column=0, sticky=NSEW)
        self.elCmdLabel = ttk.Label(elCmdFrame, font=font, text=f'--')
        self.elCmdLabel.grid(row=0, column=0, sticky=NSEW)
        # CONTROLS
        self.azEntryFrame = ttk.Frame(self.ctrlFrame)
        self.azEntryFrame.grid(row=1, column=0, columnspan=2, sticky=NSEW)
        self.azEntryFrame.columnconfigure(1, weight=1)
        self.elEntryFrame = ttk.Frame(self.ctrlFrame)
        self.elEntryFrame.grid(row=1, column=2, columnspan=2, sticky=NSEW)
        self.elEntryFrame.columnconfigure(1, weight=1)
        azArrows = tk.Label(self.azEntryFrame, text='>>>')
        azArrows.grid(row=0, column=0)
        azEntry = tk.Entry(self.azEntryFrame, font=font, background=azArrows.cget('background'), borderwidth=0, validate="key", validatecommand=(isNumWrapper, '%P'))
        azEntry.grid(row=0, column=1, sticky=NSEW)
        elArrows = tk.Label(self.elEntryFrame, text='>>>')
        elArrows.grid(row=0, column=0)
        elEntry = tk.Entry(self.elEntryFrame, font=font, background=elArrows.cget('background'), borderwidth=0, validate="key", validatecommand=(isNumWrapper, '%P'))
        elEntry.grid(row=0, column=1, sticky=NSEW)

        # BIND ENTRY WIDGETS
        azEntry.bind('<Return>', lambda event: self.threadHandler(self.sendMoveCommand, event, value=azEntry.get(), axis='az'))
        elEntry.bind('<Return>', lambda event: self.threadHandler(self.sendMoveCommand, event, value=elEntry.get(), axis='el'))

        # Arrow demonstration
        self.drawArrow(self.azAxis, 0)
        self.drawArrow(self.elAxis, 90)

        # Generate thread to handle live data plot in background
        motorLoop = threading.Thread(target=self.bearingDisplayLoop, daemon=True)
        motorLoop.start()

    def drawArrow(self, axis, angle):
        """Draws arrow on the matplotlib axis from the origin at the angle specified. Intended for polar plots only.

        Args:
            axis (plt.subplots): Matplotlib axis
            angle (float): Angle in degrees
        """
        # Remove previous plot if it exists, then draw new arrow
        match axis:
            case self.azAxis:
                try:
                    self.azArrow.remove()
                except AttributeError:
                    pass
                self.azArrow = axis.arrow(angle/180.*np.pi, 0, 0, 0.8, alpha = 1, width = 0.03, edgecolor = 'blue', facecolor = 'blue', lw = 3, zorder = 5)
            case self.elAxis:
                try:
                    self.elArrow.remove()
                except AttributeError:
                    pass
                self.elArrow = axis.arrow(angle/180.*np.pi, 0, 0, 0.8, alpha = 1, width = 0.03, edgecolor = 'blue', facecolor = 'blue', lw = 3, zorder = 5)

        self.bearingDisplay.draw()

    def threadHandler(self, target, *event, **kwargs):
        """Generates a new thread to handle IO routines without blocking main thread. For most operations, this should be used instead of calling target methods directly.

        Args:
            event (event): tkinter event which initiates function call
            target (method): Callable object to be invoked by the run() method.
            kwargs (dict, optional): Dictionary of keyword arguments for target invocation. Defaults to {}.
        """
        if not hasattr(AziElePlot, target.__name__):
            logging.error(f'Class AziElePlot does not contain a method with identifier {target.__name__}')
            return
        thread = threading.Thread(target = target, kwargs = kwargs, daemon=True)
        thread.start()
    
    def sendMoveCommand(self, value=None, axis=None):
        """_summary_

        Args:
            value (float, optional): Value in degrees to send as argument to object of MotorIO. Defaults to None.
            axis (string, optional): Either 'az' or 'el' to determine which axis to move. Defaults to None.
        """
        value = float(value)

        if axis == 'az' and value is not None:
            with motorLock:
                self.Motor.write(f'jog inc x {value}')
                time.sleep(0.1)
                self.Motor.flushInput()
            self.azCmdLabel.configure(text = f'{value}{u'\N{DEGREE SIGN}'}')

        elif axis == 'el' and value is not None:
            with motorLock:
                self.Motor.write(f'jog inc y {value}')
                time.sleep(0.1)
                self.Motor.flushInput()
            self.elCmdLabel.configure(text = f'{value}{u'\N{DEGREE SIGN}'}')

        # Disable inputs. If done correctly, the loop thread should enable inputs when bit 516 is 0
        # self.toggleInputs(DISABLE)
        

    def toggleInputs(self, action):
        frames = (self.azEntryFrame, self.elEntryFrame)
        widgets = ()

        if action == ENABLE:
            for frame in frames:
                enableChildren(frame)
            for widget in widgets:
                widget.configure(state='normal')
        elif action == DISABLE:
            for frame in frames:
                disableChildren(frame)
            for widget in widgets:
                widget.configure(state='disable')

    def setState(self, val):
        self.loopState = val

    def bearingDisplayLoop(self):
        while TRUE:
            match self.loopState:
                case state.IDLE:
                    # Prevent this thread from taking up too much utilization
                    self.toggleInputs(DISABLE)
                    time.sleep(IDLE_DELAY)
                    continue

                case state.INIT:
                    self.toggleInputs(DISABLE)
                    try:
                        motorLock.acquire()
                        self.Motor.write('\n')
                        # Check program state and maybe output somewhere or automatically set to prog0
                        prog = self.Motor.query('Prog 0')
                        if 'P00' not in prog:
                            raise NotImplementedError(f'Unexpected response from motor controller: {prog}')
                        
                        self.Motor.write('DRIVE ON X Y')
                        # Check if drive responded correctly here and set status buttons.
                        drive = self.Motor.query('DRIVE X')
                        if 'ON' not in drive:
                            raise NotImplementedError(f'Unexpected response from AXIS0: {drive}')
                        self.axis0 = True
                        drive = self.Motor.query('DRIVE Y')
                        if 'ON' not in drive:
                            raise NotImplementedError(f'Unexpected response from AXIS1: {drive}')
                        self.axis1 = True

                        self.loopState = state.LOOP
                    except Exception as e:
                        logging.error(f'{type(e).__name__}: {e}')
                    # Check drive states and output to the buttons on the left hand panel. Enable buttons to allow user to toggle drives
                        self.loopState = state.IDLE
                    finally:
                        motorLock.release()

                case state.LOOP:
                    try:
                        motorLock.acquire()
                        # Check bit 516 (In motion) to determine whether or not to allow inputs
                        # TODO: Find out why bit 516 returns 0 even when moving
                        # response = self.Motor.query('PRINT P516').splitlines()
                        # for i in response:
                        #     match i:
                        #         case '0':
                        #             self.toggleInputs(ENABLE)
                        #         case '1':
                        #             self.toggleInputs(DISABLE)
                        # query P6144 (x) and P6160 (y) for encoder position
                        response = self.Motor.query('PRINT P6144').splitlines()
                        for i in response:
                            if 'P00' in i or 'PRINT' in i:
                                response.remove(i)
                        if len(response) > 1:
                            raise ValueError(f'Encoder query expected 1 line and returned {len(response)}: {response}')
                        xEnc = int(response[0])

                        response = self.Motor.query('PRINT P6160').splitlines()
                        for i in response:
                            if 'P00' in i or 'PRINT' in i:
                                response.remove(i)
                        if len(response) > 1:
                            raise ValueError(f'Encoder query expected 1 line and returned {len(response)}: {response}')
                        yEnc = int(response[0])

                        # Calculate position in degrees
                        xPos = round((xEnc - X_HOME) / X_CPD, 4)
                        yPos = round((yEnc - Y_HOME) / Y_CPD, 4)
                        # Draw arrows on respective axes
                        self.drawArrow(self.azAxis, xPos)
                        self.drawArrow(self.elAxis, yPos)
                        # Set readout widgets
                        self.azLabel.configure(text = f'{xPos}{u'\N{DEGREE SIGN}'}')
                        self.elLabel.configure(text = f'{yPos}{u'\N{DEGREE SIGN}'}')
                        # TODO: Check if motors are moving and enable/disable inputs
                    except Exception as e:
                        logging.error(f'{type(e).__name__}: {e}')
                        self.loopState = state.IDLE
                    finally:
                        motorLock.release()
                        time.sleep(MOTOR_LOOP_DELAY)
            

# Thread target to monitor IO connection status
def statusMonitor(FrontEnd, Vi, Motor, PLC, Azi_Ele):
    while True:
        # VISA
        try:
            Vi.openRsrc.session
            FrontEnd.setStatus(FrontEnd.visaStatus, text='Connected')
        except:
            FrontEnd.setStatus(FrontEnd.visaStatus, text='NC')

        # MOTOR
        if Motor.ser.is_open:
            FrontEnd.setStatus(FrontEnd.motorStatus, text='Connected')
        else: 
            FrontEnd.setStatus(FrontEnd.motorStatus, text='NC')
        match Azi_Ele.loopState:
            case state.IDLE:
                for button in FrontEnd.MODE_BUTTONS_LIST:
                    FrontEnd.setStatus(button, background=FrontEnd.DEFAULT_BACKGROUND)
                FrontEnd.setStatus(FrontEnd.standbyButton, background=FrontEnd.SELECT_BACKGROUND)
            case state.INIT:
                for button in FrontEnd.MODE_BUTTONS_LIST:
                    FrontEnd.setStatus(button, background=FrontEnd.DEFAULT_BACKGROUND)
            case state.LOOP:
                for button in FrontEnd.MODE_BUTTONS_LIST:
                    FrontEnd.setStatus(button, background=FrontEnd.DEFAULT_BACKGROUND)
                FrontEnd.setStatus(FrontEnd.manualButton, background=FrontEnd.SELECT_BACKGROUND)
        match Azi_Ele.axis0:
            case True:
                FrontEnd.setStatus(FrontEnd.azStatus, text='ENABLED')
            case False:
                FrontEnd.setStatus(FrontEnd.azStatus, text='STOPPED')
        match Azi_Ele.axis1:
            case True:
                FrontEnd.setStatus(FrontEnd.elStatus, text='ENABLED')
            case False:
                FrontEnd.setStatus(FrontEnd.elStatus, text='STOPPED')

        # PLC
        if PLC.serial.is_open:
            FrontEnd.setStatus(FrontEnd.plcStatus, text='Connected')
        else: 
            FrontEnd.setStatus(FrontEnd.plcStatus, text='NC')
        match PLC.status:
            case opcodes.SLEEP.value:
                for button in FrontEnd.PLC_OUTPUTS_LIST:
                    FrontEnd.setStatus(button, background=FrontEnd.DEFAULT_BACKGROUND)
                FrontEnd.setStatus(FrontEnd.sleepP1Button, background=FrontEnd.SELECT_BACKGROUND)
            case opcodes.P1_INIT.value:
                FrontEnd.setStatus(FrontEnd.initP1Button, background=FrontEnd.SELECT_BACKGROUND)
            case opcodes.P1_DISABLE.value:
                for button in FrontEnd.PLC_OUTPUTS_LIST:
                    FrontEnd.setStatus(button, background=FrontEnd.DEFAULT_BACKGROUND)
                FrontEnd.setStatus(FrontEnd.initP1Button, background=FrontEnd.DEFAULT_BACKGROUND)
            case opcodes.DFS_CHAIN1.value:
                for button in FrontEnd.PLC_OUTPUTS_LIST:
                    FrontEnd.setStatus(button, background=FrontEnd.DEFAULT_BACKGROUND)
                FrontEnd.setStatus(FrontEnd.dfs1Button, background=FrontEnd.SELECT_BACKGROUND)
            case opcodes.EMS_CHAIN1.value:
                for button in FrontEnd.PLC_OUTPUTS_LIST:
                    FrontEnd.setStatus(button, background=FrontEnd.DEFAULT_BACKGROUND)
                FrontEnd.setStatus(FrontEnd.ems1Button, background=FrontEnd.SELECT_BACKGROUND)
        time.sleep(0.2)

# Root tkinter interface (contains Front_End and standard output console)
root = ThemedTk(theme=cfg['theme']['ttk'])
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
stdioFrame = ttk.Frame(root)
stdioFrame.grid(row=1, column=1, sticky=NSEW, padx=ROOT_PADX, pady=ROOT_PADY)
stdioFrame.rowconfigure(0, weight=1)
font=cfg['theme']['terminal_font']
for x in range(5):
    stdioFrame.columnconfigure(x, weight=0)
stdioFrame.columnconfigure(1, weight=1)
consoleFrame = ttk.Frame(stdioFrame)    # So the scrollbar isn't stretched to the width of the rightmost widget in stdioFrame
consoleFrame.grid(column=0, row=0, sticky=NSEW, columnspan=5)
consoleFrame.rowconfigure(0, weight=1)
consoleFrame.columnconfigure(0, weight=1)
console = tk.Text(consoleFrame, height=15)
console.grid(column=0, row=0, sticky=(N, S, E, W))
console.config(state=DISABLED)
# Scrollbar
consoleScroll = ttk.Scrollbar(consoleFrame, orient=VERTICAL, command=console.yview)
console.configure(yscrollcommand=consoleScroll.set)
consoleScroll.grid(row=0, column=1, sticky=NSEW)
# Terminal input
debugLabel = tk.Label(stdioFrame, text='>>>', font=(font))
debugLabel.grid(row=1, column=0, sticky=NSEW)
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
    try:
        if execBool.get():
            exec(arg)
        else:
            if printBool.get():
                logging.terminal(f'{eval(arg)}')
            else:
                eval(arg)
    except Exception as e:
        logging.terminal(f'{type(e).__name__}: {e}')

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

def openSaveDialog(type):
    if type == 'trace':
        with specPlotLock:
            data = Spec_An.ax.lines[0].get_data()
            xdata = data[0]
            ydata = data[1]
            buffer = ''
        file = filedialog.asksaveasfile(initialdir = os.getcwd(), filetypes=(('Text File (Tab delimited)', '*.txt'), ('Comma separated variables', '*.csv'), ('All Files', '*.*')), defaultextension='.txt')
        if '.csv' in file.name:
            delimiter = ','
        else:
            delimiter = '\t'
        for index in range(len(data[0])):
            buffer = buffer + str(xdata[index]) + delimiter + str(ydata[index]) + '\n'
        if file is not None:
            file.write(buffer)
            file.close()
    elif type == 'log':
        file = filedialog.asksaveasfile(initialdir = os.getcwd(), filetypes=(('Text Files', '*.txt'), ('All Files', '*.*')), defaultextension='.txt')
        if file is not None:
            file.write(console.get('1.0', END))
            file.close()
    elif type == 'image':
        filename = filedialog.asksaveasfilename(initialdir = os.getcwd(), filetypes=(('JPEG', '*.jpg'), ('PNG', '*.png')), defaultextension='.jpg')
        if filename != '':
            with specPlotLock:
                Spec_An.fig.savefig(filename)

def generateConfigDialog():
    if messagebox.askokcancel(
        message="Would you like to generate the default configuration file loaded with this software version? This will overwrite any preexisting config.toml if present.",
        icon='question',
        title="Are you sure?"
        ):
        defaultconfig.generateConfig()


evalCheckbutton.configure(command=checkbuttonStateHandler)
execCheckbutton.configure(command=checkbuttonStateHandler)

# When sys.std***.write is called (such as on print), call redirector to print in textbox
sys.stdout.write = redirector
sys.stderr.write = redirector

# Check for initialization errors and print in the newly generated terminal window
if 'cfg_error' in globals():
    logging.warning(f'{type(cfg_error).__name__}: {cfg_error}')
if missingHeaders:
    for header in missingHeaders:
        logging.error(f'Missing header [{header}] in config.toml')
if missingKeys:
    for key in missingKeys:
        logging.error(f'Missing key [{key}] in config.toml')
if missingHeaders or missingKeys or 'cfg_error' in globals():
    logging.warning(f'Error loading config.toml, loading default configuration.')

# Generate objects within root window
Vi = VisaIO()
Motor = MotorIO(0, 0)
Relay = SerialIO()

Front_End = FrontEnd(root, Vi, Motor, Relay)
Spec_An = SpecAn(Vi, Front_End.spectrumFrame)
Azi_Ele = AziElePlot(Motor, Front_End.directionFrame)

statusMonitorThread = threading.Thread(target=statusMonitor, args = (Front_End, Vi, Motor, Relay, Azi_Ele), daemon=True)
statusMonitorThread.start()

# Bind FrontEnd buttons to AziEle methods
Front_End.standbyButton.configure(command = lambda: Azi_Ele.setState(state.IDLE))
Front_End.manualButton.configure(command = lambda: Azi_Ele.setState(state.INIT))

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
menuFile.add_command(label='Save trace', command = lambda: openSaveDialog(type='trace'))
menuFile.add_command(label='Save log', command = lambda: openSaveDialog(type='log'))
menuFile.add_command(label='Save image', command = lambda: openSaveDialog(type='image'))
menuFile.add_separator()
menuFile.add_command(label='Generate config.toml', command = generateConfigDialog)
menuFile.add_separator()
menuFile.add_command(label='Exit', command=Front_End.onExit)

# Options
tkLoggingLevel = IntVar()
tkLoggingLevel.set(1)
menuOptions.add_command(label='Configure...', command = Front_End.openConfig)
menuOptions.add_command(label='Change plot color', command = Spec_An.setPlotThreadHandler)
menuOptions.add_separator()
menuOptions.add_radiobutton(label='Logging: Standard', variable = tkLoggingLevel, command = lambda: loggingLevelHandler(tkLoggingLevel.get()), value = 1)
menuOptions.add_radiobutton(label='Logging: Verbose', variable = tkLoggingLevel, command = lambda: loggingLevelHandler(tkLoggingLevel.get()), value = 2)
menuOptions.add_radiobutton(label='Logging: Debug', variable = tkLoggingLevel, command = lambda: loggingLevelHandler(tkLoggingLevel.get()), value = 3)

# Help
menuHelp.add_command(label='Open wiki...', command=Front_End.openHelp)

root.protocol("WM_DELETE_WINDOW", Front_End.onExit)
root.mainloop()
