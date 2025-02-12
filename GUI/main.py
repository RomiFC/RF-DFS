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

# THREADING EVENTS
visaLock = threading.RLock()        # For VISA resources
motorLock = threading.RLock()       # For motor controller
plcLock = threading.RLock()         # For PLC
specPlotLock = threading.RLock()    # For matplotlib spectrum plot
bearingPlotLock = threading.RLock() # For matplotlib antenna direction plot


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
        # Clock
        self.clockLabel = tk.Label(controlFrame, font=CLOCK_FONT)
        self.clockLabel.grid(row=0, column=0, columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        # Drive Status
        azStatusFrame = tk.LabelFrame(controlFrame, text='Azimuth Drive')
        azStatusFrame.grid(row=1, column=0, sticky=NSEW, padx=FRAME_PADX, pady=FRAME_PADY)
        azStatusFrame.columnconfigure(0, weight=1)
        self.azStatus = tk.Button(azStatusFrame, text='STOPPED', font=FONT, state=DISABLED, width=6)
        self.azStatus.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        elStatusFrame = tk.LabelFrame(controlFrame, text='Elevation Drive')
        elStatusFrame.grid(row=1, column=1, sticky=NSEW, padx=FRAME_PADX, pady=FRAME_PADY)
        elStatusFrame.columnconfigure(0, weight=1)
        self.elStatus = tk.Button(elStatusFrame, text='STOPPED', font=FONT, state=DISABLED, width=6)
        self.elStatus.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        # PLC Operations
        chainFrame = tk.LabelFrame(controlFrame, text='PLC Operations')
        chainFrame.grid(row=2, column=0, sticky=NSEW, columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
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
        modeFrame.grid(row=3, column=0, sticky=NSEW, columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
        modeFrame.columnconfigure(0, weight=1)
        self.standbyButton = tk.Button(modeFrame, text='Standby', font=FONT, bg=self.SELECT_BACKGROUND)
        self.standbyButton.grid(row=0, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.manualButton = tk.Button(modeFrame, text='Manual', font=FONT, bg=self.DEFAULT_BACKGROUND)
        self.manualButton.grid(row=1, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.autoButton = tk.Button(modeFrame, text='Auto', font=FONT, bg=self.DEFAULT_BACKGROUND)
        self.autoButton.grid(row=2, column=0, sticky=NSEW, padx=BUTTON_PADX, pady=BUTTON_PADY)
        self.MODE_BUTTONS_LIST = (self.standbyButton, self.manualButton, self.autoButton)
        # Connection Status
        connectionsFrame = tk.LabelFrame(controlFrame, text='Connection Status')
        connectionsFrame.grid(row=4, column=0, sticky=NSEW, columnspan=2, padx=FRAME_PADX, pady=FRAME_PADY)
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

        # Generate thread to handle live data plot in background
        analyzerLoop = threading.Thread(target=self.loopAnalyzerDisplay, daemon=True)
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
        _list = []

        # if self.Vi.isSessionOpen() == FALSE:
        #     logging.error("Session to the Analyzer is not open.")
        #     return

        # Center Frequency
        _dict = {
            'command': ':SENS:FREQ:CENTER',
            'arg': centerfreq,
            'widget': self.centerFreqEntry
        }
        _list.append(_dict)
        # Span
        _dict = {
            'command': ':SENS:FREQ:SPAN',
            'arg': span,
            'widget': self.spanEntry
        }
        _list.append(_dict)
        # Start Frequency
        _dict = {
            'command': ':SENS:FREQ:START',
            'arg': startfreq,
            'widget': self.startFreqEntry
        }
        _list.append(_dict)
        # Stop Frequency
        _dict = {
            'command': ':SENS:FREQ:STOP',
            'arg': stopfreq,
            'widget': self.stopFreqEntry
        }
        _list.append(_dict)
        # Sweep Time
        _dict = {
            'command': ':SWE:TIME',
            'arg': sweeptime,
            'widget': self.sweepTimeEntry
        }
        _list.append(_dict)
        # Resolution Bandwidth
        _dict = {
            'command': ':SENS:BANDWIDTH:RESOLUTION',
            'arg': rbw,
            'widget': self.rbwEntry
        }
        _list.append(_dict)
        # Video Bandwidth
        _dict = {
            'command': ':SENS:BANDWIDTH:VIDEO',
            'arg': vbw,
            'widget': self.vbwEntry
        }
        _list.append(_dict)
        # VBW: 3 dB RBW
        _dict = {
            'command': ':SENS:BANDWIDTH:VIDEO:RATIO',
            'arg': bwratio,
            'widget': self.bwRatioEntry
        }
        _list.append(_dict)
        # Reference Level
        _dict = {
            'command': ':DISP:WINDOW:TRACE:Y:RLEVEL',
            'arg': ref,
            'widget': self.refLevelEntry
        }
        _list.append(_dict)
        # Number of divisions
        _dict = {
            'command': ':DISP:WINDOW:TRACE:Y:NDIV',
            'arg': numdiv,
            'widget': self.numDivEntry
        }
        _list.append(_dict)
        # Scale per division
        _dict = {
            'command': ':DISP:WINDOW:TRACE:Y:PDIV',
            'arg': yscale,
            'widget': self.yScaleEntry
        }
        _list.append(_dict)
        # Mechanical attenuation
        _dict = {
            'command': ':SENS:POWER:RF:ATTENUATION',
            'arg': atten,
            'widget': self.attenEntry
        }
        _list.append(_dict)
        # SPAN TYPE
        _dict = {
            'command': ':SENS:FREQ:SPAN',
            'arg': spantype,
            'widget': tkSpanType
        }
        _list.append(_dict)
        # SWEEP TYPE
        _dict = {
            'command': ':SWE:TIME:AUTO',
            'arg': sweeptype,
            'widget': tkSweepType
        }
        _list.append(_dict)
        # RBW TYPE
        _dict = {
            'command': ':SENS:BAND:RES:AUTO',
            'arg': rbwtype,
            'widget': tkRbwType
        }
        _list.append(_dict)
        # VBW TYPE
        _dict = {
            'command': ':SENS:BAND:VID:AUTO',
            'arg': vbwtype,
            'widget': tkVbwType
        }
        _list.append(_dict)
        # BW RATIO TYPE
        _dict = {
            'command': ':SENS:BAND:VID:RATIO',
            'arg': bwratiotype,
            'widget': tkBwRatioType
        }
        _list.append(_dict)
        # RBW FILTER SHAPE
        _dict = {
            'command': ':SENS:BAND:SHAP',
            'widget': self.rbwFilterShapeCombo,
            'arg': None,
        }
        if rbwfiltershape is not None:
            _dict.update({'arg': self.RBW_FILTER_SHAPE_VAL_ARGS[rbwfiltershape]})
        _list.append(_dict)
        # RBW FILTER TYPE
        _dict = {
            'command': ':SENS:BAND:TYPE',
            'widget': self.rbwFilterTypeCombo,
            'arg': None,
        }
        if rbwfiltertype is not None:
            _dict.update({'arg': self.RBW_FILTER_TYPE_VAL_ARGS[rbwfiltertype]})
        _list.append(_dict)
        # ATTENUATION TYPE
        _dict = {
            'command': ':SENS:POWER:ATT:AUTO',
            'arg': attentype,
            'widget': tkAttenType
        }
        _list.append(_dict)
        # UNIT OF POWER
        _dict = {
            'command': ':UNIT:POW',
            'arg': None,
            'widget': self.unitPowerEntry
        }
        _list.append(_dict)

        # Sort the list so dictionaries with 'arg': None are placed (and executed) after write commands
        for index in range(len(_list)):
            if _list[index]['arg'] is not None:
                _list.insert(0, _list.pop(index))


        # EXECUTE COMMANDS
        logging.debug(f"setAnalyzerValue generated list of dictionaries '_list' with value {_list}")
        with visaLock:
            for x in _list:
                # Issue command with argument
                if x['arg'] is not None:
                    self.Vi.openRsrc.write(f'{x['command']} {x['arg']}')
                # Set widgets without issuing a parameter to command
                try:
                    buffer = self.Vi.openRsrc.query_ascii_values(f'{x['command']}?') # Default converter is float
                except:
                    buffer = self.Vi.openRsrc.query_ascii_values(f'{x['command']}?', converter='s')
                logging.verbose(f"Command {x['command']}? returned {buffer}")
                clearAndSetWidget(x['widget'], buffer)
        # Set plot limits
        with specPlotLock:
            self.setAnalyzerPlotLimits()
        return
    
    def setState(self, val):
        self.loopState = val

    def loopAnalyzerDisplay(self):
        global visaLock, specPlotLock

        while TRUE:
            match self.loopState:
                case state.IDLE:
                    # Prevent this thread from taking up too much utilization
                    self.toggleInputs(DISABLE)
                    time.sleep(1)
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
                            # logging.warning(e)
                            # logging.warning(f'Could not query errors from device.')
                        visaLock.release()
                        self.toggleInputs(ENABLE)
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
                        time.sleep(0.5)
                    else:
                        # Prevent this thread from taking up too much utilization
                        time.sleep(1)

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

        # STYLE
        font = 'Courier 14'
        padx = 2
        pady = 2

        # PLOT
        fig, (azAxis, elAxis) = plt.subplots(1, 2, subplot_kw=dict(projection='polar'))
        fig.set_size_inches(fig.get_size_inches()[0], fig.get_size_inches()[1] * 0.8)      # Sets to minimum height since two plots can appear large in the root window
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
        self.bearingDisplay.get_tk_widget().grid(row = 0, column = 0, sticky=NSEW, columnspan=2)


        # CONTROL FRAME
        self.ctrlFrame = ttk.Frame(self.parent)
        self.ctrlFrame.grid(row=2, column=0, sticky=NSEW, columnspan=1)
        for x in range(4):
            self.ctrlFrame.columnconfigure(x, weight=1)
        # FEEDBACK
        azFrame = ttk.Labelframe(self.ctrlFrame, text='Azimuth Angle')
        azFrame.grid(row=0, column=0, sticky=NSEW, padx=padx, pady=pady)
        azCmdFrame = ttk.Labelframe(self.ctrlFrame, text='Command Angle')
        azCmdFrame.grid(row=0, column=1, sticky=NSEW, padx=padx, pady=pady)
        elFrame = ttk.Labelframe(self.ctrlFrame, text='Elevation Angle')
        elFrame.grid(row=0, column=2, sticky=NSEW, padx=padx, pady=pady)
        elCmdFrame = ttk.Labelframe(self.ctrlFrame, text='Command Angle')
        elCmdFrame.grid(row=0, column=3, sticky=NSEW, padx=padx, pady=pady)
        azLabel = ttk.Label(azFrame, font=font, text=f'0{u'\N{DEGREE SIGN}'}')
        azLabel.grid(row=0, column=0, sticky=NSEW)
        elLabel = ttk.Label(elFrame, font=font, text=f'90{u'\N{DEGREE SIGN}'}')
        elLabel.grid(row=0, column=0, sticky=NSEW)
        azCmdLabel = ttk.Label(azCmdFrame, font=font, text=f'0{u'\N{DEGREE SIGN}'}')
        azCmdLabel.grid(row=0, column=0, sticky=NSEW)
        elCmdLabel = ttk.Label(elCmdFrame, font=font, text=f'90{u'\N{DEGREE SIGN}'}')
        elCmdLabel.grid(row=0, column=0, sticky=NSEW)
        # CONTROLS
        azEntryFrame = ttk.Frame(self.ctrlFrame)
        azEntryFrame.grid(row=1, column=0, columnspan=2, sticky=NSEW)
        azEntryFrame.columnconfigure(1, weight=1)
        elEntryFrame = ttk.Frame(self.ctrlFrame)
        elEntryFrame.grid(row=1, column=2, columnspan=2, sticky=NSEW)
        elEntryFrame.columnconfigure(1, weight=1)
        azArrows = tk.Label(azEntryFrame, text='>>>')
        azArrows.grid(row=0, column=0)
        azEntry = tk.Entry(azEntryFrame, font=font, background=azArrows.cget('background'), borderwidth=0, validate="key", validatecommand=(isNumWrapper, '%P'))
        azEntry.grid(row=0, column=1, sticky=NSEW)
        elArrows = tk.Label(elEntryFrame, text='>>>')
        elArrows.grid(row=0, column=0)
        elEntry = tk.Entry(elEntryFrame, font=font, background=elArrows.cget('background'), borderwidth=0, validate="key", validatecommand=(isNumWrapper, '%P'))
        elEntry.grid(row=0, column=1, sticky=NSEW)

        # BIND ENTRY WIDGETS
        azEntry.bind('<Return>', lambda event: self.sendMoveCommand(event, value=azEntry.get(), axis='az'))
        elEntry.bind('<Return>', lambda event: self.sendMoveCommand(event, value=elEntry.get(), axis='el'))

        # Arrow demonstration
        self.drawArrow(azAxis, 0)
        self.drawArrow(elAxis, 90)

        # Generate thread to handle live data plot in background
        motorLoop = threading.Thread(target=self.loopDisplay, daemon=True)
        motorLoop.start()

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
            value (float, optional): Value in degrees to send as argument to object of MotorIO. Defaults to None.
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

    def toggleInputs(self, action):
        frames = (self.ctrlFrame,)
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

    def loopDisplay(self):
        while TRUE:
            match self.loopState:
                case state.IDLE:
                    # Prevent this thread from taking up too much utilization
                    self.toggleInputs(DISABLE)
                    time.sleep(1)
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

                        self.toggleInputs(ENABLE)
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

                        logging.motor(f'{xEnc}, {yEnc}')
                        # Update live text/plots
                        # Check if motors are moving and enable/disable inputs
                        time.sleep(1)
                    except Exception as e:
                        logging.error(f'{type(e).__name__}: {e}')
                        self.loopState = state.IDLE
                    motorLock.release()
            

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
                FrontEnd.setStatus(FrontEnd.manualButton, background=FrontEnd.DEFAULT_BACKGROUND)
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

# Limit window size to the minimum size on generation
root.update()
root.minsize(root.winfo_width(), root.winfo_height())

root.protocol("WM_DELETE_WINDOW", Front_End.onExit)
root.mainloop()
