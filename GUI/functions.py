from tkinter import *
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import time
from timestamp import *
import pyvisa as visa
from pyvisa import constants
import sys
from data import *
import opcodes
 
# CONSTANTS
RETURN_ERROR = 1
RETURN_SUCCESS = 0
CHUNK_SIZE_DEF = 20480     # Default byte count to read when issuing viRead
CHUNK_SIZE_MIN = 1024
CHUNK_SIZE_MAX = 1048576  # Max chunk size allowed
TIMEOUT_DEF = 2000        # Default VISA timeout value
TIMEOUT_MIN = 1000        # Minimum VISA timeout value
TIMEOUT_MAX = 25000       # Maximum VISA timeout value

class MotorControl: 
 
    def __init__(self, Azimuth, Elevation, userAzi = 0, userEle = 0, Azi_bound = [0,360], Ele_bound = [-90,10] ): 
        self.Azimuth    = Azimuth
        self.Elevation  = Elevation
        self.userAzi    = userAzi
        self.userEle    = userEle
        self.Azi_bound  = Azi_bound
        self.Ele_bound  = Ele_bound
        self.homeAzi    = 0
        self.homeEle    = 0
        self.port       = ''
        self.ser        = serial.Serial()
        self.OpenSerial()

        # commands 
        self.commandToSend  = ""
        self.startCommand   = ['Prog 0', 'drive on x y']

        # error type
        self.errorType          = "" 
        self.errorMsg           = ""
        self.rangeError         = ["Range Error", "Input is out of Range \n Range: "]
        self.inputTypeError     = ["Input Type Error", "Inputs must be integers"]
        self.connectionError    = ["Connection Error", "Failed to connect/send command to controller"]
        self.eStopError         = ["Emargency Stop Error", "Failed to stop motor"]

    def errorPopup( self ):
        """Generate Error pop up window.
        """
        messagebox.showwarning( title= self.errorType , message= self.errorMsg )

    def sendCommand( self, command ):
        """Serial Communication, write in serial. Error pop up if fails. 
        """
        try: 
            
            self.ser.write( str(command).encode('utf-8')+'\r\n'.encode('utf-8') )
           
            # self.readLine()
        except:
            self.errorType = self.connectionError[0]
            self.errorMsg = self.connectionError[1]
            self.errorPopup()


    def readLine( self ):
        """Serial Commmunication, read until End Of Line charactor
        """
        try:
            while( self.ser.in_waiting > 0):
                print(self.ser.in_waiting)
                msg = self.ser.readline()
                print(msg)
                
        except:
            self.errorType = self.connectionError[0]
            self.errorMsg = self.connectionError[1]
            self.errorPopup()


    def is_convertible_to_integer(self, input_str):
        """
        Check if given string is convertivle to integer. (Positive int, Negative int, Zero) 

        Returns:
            True: String is convetible to integer
            False: String is not convertible to integer. 
        """
        try:
            int(input_str)
            return True
        except:
            return False
        

    def readUserInput( self ):
        """Check if both inputs are integers/NULL string. 
        Convert NULL string to current position values.
        If both inputs are integers/NULL string, call chechrange functioon, otherwise, error pop up. 
        """
        if self.userAzi == "":
            self.userAzi = str ( self.Azimuth )
        if self.userEle == "":
            self.userEle = str( self.Elevation )
        elif (self.is_convertible_to_integer(self.userAzi)) and (self.is_convertible_to_integer(self.userEle)):
            self.checkrange()
        else : 
            self.errorType = self.inputTypeError[0]
            self.errorMsg = self.inputTypeError[1]
            self.errorPopup()

    def checkrange( self ): 
        """Check if input value(s) are in range. Send command if both in range, error pop up if not. 
        """
        isInRange = True
        self.IntUserAzi = int(self.userAzi)
        self.IntUserEle = int(self.userEle)

        if self.IntUserAzi < self.Azi_bound[0] or self.IntUserAzi > self.Azi_bound[1]:
            isInRange = False
        if self.IntUserEle < self.Ele_bound[0] or self.IntUserEle > self.Ele_bound[1]:
            isInRange = False
        if isInRange:
            commandToSend = self.commandGen + " x " + self.userAzi + " y " + self.userEle 
            print("Raange Check cleared")
            self.sendCommand( commandToSend )
            self.readLine()
            self.Azimuth = self.userAzi
            self.Elevation = self.userEle
        else: 
            self.errorType = self.rangeError[0]
            self.errorMsg = self.rangeError[1] + "Azimuth: " + str(self.Azi_bound[0]) + "-" + str(self.Azi_bound[1]) + "\n" + "Elevation: " +  str(self.Ele_bound[0]) + "-" + str(self.Ele_bound[1])
            self.errorPopup()
   
    def OpenSerial( self ):
        """Open new serial connection
        """
        if self.port != '':
           
            if self.ser.is_open:
                self.ser.close()
            try:    
                self.ser = serial.Serial(port= self.port, baudrate=9600 , bytesize= 8, parity='N', stopbits=1,xonxoff=0, timeout = 1)
                
                print( self.ser.is_open )

                # while( self.ser.readline().isspace() ): 
                #     print( "waiting" )
        
                # if ( self.ser.readline() == b'SYS'  ):
                #     self.ser.write( 'prog 0' )
                # if ( self.ser.readline() == b'P00' ):
                #     self.ser.write( 'drive on x y' )      
                self.sendCommand('\n')
                time.sleep(3) #needed to let arduino to send it back 
                self.readLine()
                print( "communication to motor controller is ready" )
                
            except: 
                 self.errorType = self.connectionError[0]
                 self.errorMsg = self.connectionError[1]
                 self.errorPopup()


    def CloseSerial( self ):        
        self.sendCommand( 'drive off x y' )
        self.readLine()
        self.ser.close()


    def EmargencyStop( self ):
        self.sendCommand( "jog off x y" )
        self.readLine()


    def Park( self ):
        self.sendCommand( "jog abs" + " x " + str( self.homeAzi ) + " y " + str( self.homeEle ) )
        self.readLine()


    def freeInput( self ):
        def ReadandSend():

            line = inBox.get()
            self.sendCommand( line )
            update_text()
        
        def update_text(): 
            try:
                line = self.ser.readline()
                if line.decode('utf-8') != '':
                    self.returnLineBox.config(text = line.decode('utf-8') )
            except:
                self.errorType = self.connectionError[0]
                self.errorMsg = self.connectionError[1]
                self.errorPopup()

        freeWriting = tk.Tk() 
        freeWriting.title("Serial Communication")

        outputFrame     = tk.Frame( freeWriting )
        inputFrame      = tk.Frame( freeWriting )

        inputFrame.pack()
        outputFrame.pack()

        labelInput      = tk.Label( inputFrame, text= "Type Input: ")
        inBox           = tk.Entry( inputFrame , width= 50 )
        enterButton     = tk.Button( inputFrame , text = "Enter" , command = ReadandSend )
        self.returnLineBox   = tk.Label( outputFrame )

        labelInput.pack( padx = 10, pady = 5 )
        inBox.pack( side = 'left', padx = 10, pady = 5 )
        enterButton.pack( side = 'right' ,padx = 10, pady = 5)
        self.returnLineBox.pack( padx = 10, pady = 5 )
    
        freeWriting.after(1000, update_text)
        freeWriting.mainloop()
        
class VisaControl():
    def openRsrcManager(self):
        """Opens the VISA resource manager on the default backend (NI-VISA). If the VISA library cannot be found, a path must be passed to pyvisa.highlevel.ResourceManager() constructor

        Returns:
            0: On success
            1: On error
        """
        print('Initializing VISA Resource Manager...')
        self.rm = visa.ResourceManager()
        if self.isError():
            print('Could not open a session to the resource manager, error code:', hex(self.rm.last_status))
            return RETURN_ERROR     
        return RETURN_SUCCESS
    
    def connectToRsrc(self, inputString):
        """Opens a session to the resource ID passed from inputString if it is not already connected

        Args:
            inputString (string): Name of the resource ID to attempt to connect to. 

        Returns:
            0: On success
            1: On error
        """
        try:
            self.openRsrc.session                           # Is a session open? (Will throw error if not open)
        except:
            pass                                            # If not open --> continue
        else:
            if self.openRsrc.resource_name == inputString:  # Is the open resource's ID the same as inputString?
                print('Device is already connected')
                return RETURN_SUCCESS                       # If yes --> return
        
        # If a session is not open or the open resource does not match inputString, attempt connection to inputString
        print('Connecting to resource: ' + inputString)
        self.openRsrc = self.rm.open_resource(inputString)
        if self.isError():
            print('Could not open a session to ' + inputString)
            print('Error Code:' + self.rm.last_status)
            return RETURN_ERROR
        return RETURN_SUCCESS
    
    def setConfig(self, timeout, chunkSize, sendEnd, enableTerm, termChar):
        """Applies VISA attributes passed in arguments to the open resource when called

        Args:
            timeout (int): VISA timeout value in milliseconds
            chunkSize (int): PyVISA chunk size in bytes (Read buffer size)

        Returns:
            0: On success
            1: On error
        """
        if self.isSessionOpen():
            try:
                self.openRsrc.timeout = timeout
                self.openRsrc.chunk_size = chunkSize
                self.openRsrc.send_end = sendEnd
                if enableTerm:
                    self.openRsrc.write_termination = termChar
                    self.openRsrc.read_termination = termChar
                else:
                    self.openRsrc.write_termination = ''
                    self.openRsrc.read_termination = ''
                return RETURN_SUCCESS
            except:
                print(f'An exception occurred. Error code: {self.rm.last_status}')
                return RETURN_ERROR
        else:
            print("Session to a resource is not open")
            return RETURN_ERROR
            
        
    def isSessionOpen(self):
        """Tests if a session is open to the variable openRsrc

        Returns:
            False: If session is closed
            True: If session is open
        """
        try:
            self.openRsrc.session                           # Is a session open? (Will throw error if not open)
        except:
            return False
        else:
            return True
        
    def isError(self):
        """Checks the last status code returned from an operation at the opened resource manager (self.rm)

        Returns:
            0: On success or warning (Operation succeeded)
            StatusCode: On error
        """
        if self.rm.last_status < constants.VI_SUCCESS:
            return self.rm.last_status
        else:
            print('Success code:', hex(self.rm.last_status))
            return RETURN_SUCCESS
        
        

class FrontEnd():
    def __init__(self, root):
        """Initializes the top level tkinter interface
        """
        # CONSTANTS
        self.SELECT_TERM_VALUES = ['Line Feed - \\n', 'Carriage Return - \\r']

        # VARIABLES
        self.timeout = TIMEOUT_DEF           # VISA timeout value
        self.chunkSize = CHUNK_SIZE_DEF      # Bytes to read from buffer
        self.instrument = ''                 # ID of the currently open instrument. Used only in resetWidgetValues method
        self.isAnalyzerOn = FALSE

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

        # MEASUREMENT COMMANDS
        self.measurementTab = ttk.Notebook(self.spectrumFrame)
        tab1 = ttk.Frame(self.measurementTab)
        tab2 = ttk.Frame(self.measurementTab)
        tab3 = ttk.Frame(self.measurementTab)
        self.measurementTab.add(tab1, text="Freq")
        self.measurementTab.add(tab2, text="BW")
        self.measurementTab.add(tab3, text="Amp")
        self.measurementTab.grid(row=0, column=1, sticky=NSEW)

        # TOGGLE BUTTON
        self.placeholder = tk.Button(self.spectrumFrame, text="Placeholder Text")
        self.placeholder.grid(row=0, column=0, sticky=NSEW)
        self.spectrumToggle = tk.Button(self.spectrumFrame, text="Toggle Analyzer", command=self.toggleAnalyzer())
        self.spectrumToggle.grid(row=1, column=1, sticky=NSEW)

    def toggleAnalyzer(self):
        if self.Vi.isSessionOpen == FALSE:
            print("Error: Session to the analyzer is not open")
            return
        if self.isAnalyzerOn:
            # turn it off
            self.isAnalyzerOn = FALSE
            return
        # turn it on
        # self.Vi.openRsrc.write_ascii_values("*RST")
        # # is buffer large enough?
        # self.Vi.openRsrc.write_ascii_values("*WAI")
        # clear buffer and continue...

        return

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

        