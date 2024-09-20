# import tkinter as tk
# from tkinter import ttk
from tkinter import *
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import time
import pyvisa as visa
from pyvisa import constants
# from tkinter import tix
import astropy

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
 
    def __init__(self, Azimuth, Elevation, userAzi = 0, userEle = 0, Azi_bound = [0,360], Ele_bound = [-90,20] ): 
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
        self.breakCommand   = 'jog off x y' 
        self.commandGen     = 'jog abs'
        self.moveCommandX   = 'jog abs x ' 
        self.moveCommandY   = 'jog abs y '
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

    def sendCommand( self , command ):
        """Serial Communication, write in serial. Error pop up if fails. 
        """
        try: 
            
            # time.sleep(1)
            self.ser.write( str(command).encode('utf-8'))
            # time.sleep(1)
            self.readLine()
            # time.sleep(1)

            print("command sent \n")
        except:
            
            self.errorType = self.connectionError[0]
            self.errorMsg = self.connectionError[1]
            self.errorPopup()


    def readLine( self ):
        """Serial Commmunication, read until End Of Line charactor
        """
        msg = self.ser.readline()
        # message = msg.decode('utf-8') 
        print(msg)
        
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
            # self.commandToSend= self.moveCommandX + self.userAzi 
            # self.nextCommand = self.moveCommandY + self.userEle
            # self.commandToSend = self.commandGen + " x " + self.userAzi + " y " + self.userEle 
            self.sendCommand( self.commandGen + " x " + self.userAzi + " y " + self.userEle  )
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
                self.ser = serial.Serial(port= self.port, baudrate=9600 , bytesize= 8, parity='N', stopbits=1,xonxoff=0)
                time.sleep(1)
                # self.ser.write("\n")
                # self.ser.write( self.startCommand[0] )
                # # if self.readLine() = 
                # self.ser.write( self.startCommand[1] )
                # self.ser.write( "\n" ) 
                print( "communication to motor controller is ready" )
            except:
                 self.errorType = self.connectionError[0]
                 self.errorMsg = self.connectionError[1]
                 self.errorPopup()


    def CloseSerial( self ):
        try:
            if not(self.ser.is_open()):
                self.sendCommand( '' )
                self.ser.close()
        except: 
            pass


    def EmargencyStop( self ):
        self.commandToSend = self.breakCommand
        self.sendCommand( "jog off x y" )
     
    def Park( self ):
        # self.commandToSend = self.commandGen + " x " + str( self.homeAzi ) + " y " + str( self.homeEle )
        self.sendCommand( self.commandGen + " x " + str( self.homeAzi ) + " y " + str( self.homeEle ) )
    

    def freeInput( self ):
        def ReadandSend():

            line = inBox.get()
            self.sendCommand( line )
            update_text()
        
        def update_text(): 
            try:
                line = self.ser.readline()
                if line.decode != '':
                    self.returnLineBox.config(text = line.decode )
            except:
                self.errorType = self.connectionError[0]
                self.errorMsg = self.connectionError[1]
                self.errorPopup()

        freeWriting = tk.Tk() 
        freeWriting.title("Serial Communication")

        outputFrame     = tk.Frame( freeWriting )
        inputFrame      = tk.Frame( freeWriting )
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
        
        
#######################################################################################################################################
    # def MotorSetting( self ):
    #     settingWindow = tk.Tk()
    #     settingWindow.geometry('400x200')
    #     settingWindow.title('MotorSetting')

    #     # home is 1x2 (azimuth, elevation)
    #     home = []
    #     # bounds is 2x2 (lower and upper bound for each direction)
    #     bounds = []
      
    #     frame = tk.Frame( settingWindow )
    #     currName = tk.Label( frame, text = "Curent Default" )
    #     newName = tk.Label( frame, text = "New Default" )
    #     currAzi = tk.Label( frame, text = str( self.homeAzi ))
    #     currEle = tk.Label( frame, text = str( self.homeEle ))
    #     labelAzi = tk.Label( frame, text = "Azimuth ")
    #     labelEle = tk.Label( frame, text = " Elevatin ")
    #     newhomeAzi = tk.Entry( frame, width = 10 )
    #     newhomeEle = tk.Entry( frame, width = 10 )

    #     currName.grid(row = 0, column = 1, padx = 5, pady = 5)
    #     newName.grid(row = 0, column = 2, padx = 5, pady = 5)
        
    #     labelAzi.grid(row = 1, column = 0, padx = 5, pady = 5)
    #     currAzi.grid(row = 1, column = 1, padx = 5, pady = 5)
    #     newhomeAzi.grid(row = 1, column = 2, padx = 5, pady = 5)

    #     labelEle.grid(row = 2, column = 0, padx = 5, pady = 5)
    #     currEle.grid(row = 2, column = 1, padx = 5, pady = 5)
    #     newhomeEle.grid(row = 2, column = 2, padx = 5, pady = 5)
    #     frame.pack()

    #     enterButton = tk.Button( settingWindow, text = "Enter", command = self.updateValues )
    #     enterButton.pack()
    #     settingWindow.mainloop()

    #     # home = [newhomeAzi.get(),newhomeEle.get()]
    
    # def updateValues( self ):
    #     try:
    #         self.homeAzi = self.MotorSetting.newhomeAzi.get()
    #         # self.homeAzi = self.MotorSetting[0]
    #         # self.homeEle = self.MotorSetting[1]
    #         print( self.homeAzi , self.homeEle )
    #     except: 
    #         messagebox.showwarning( title = "Default update error", message= "Failed to update default value" )
        
########################################################################################################################################
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
    def __init__(self):
        """Initializes the top level tkinter interface
        """
        self.root = tk.Tk()
        self.root.title('DFS-control')

        vi = VisaControl()

        tabControl = ttk.Notebook(self.root) 
  
        self.tab1 = ttk.Frame(tabControl) 
        self.tab2 = ttk.Frame(tabControl) 

        tabControl.add(self.tab1, text ='Tab 1') 
        tabControl.add(self.tab2, text ='Tab 2') 
        tabControl.bind('<Button-1>', lambda event: self.resetWidgetValues(vi, event))
        tabControl.pack(expand = 1, fill ="both") 

        self.serialInterface()
        self.scpiInterface(vi)
        # self.PythonInterface()
        self.root.after(1000, self.update_time )
        self.root.mainloop()

    def scpiInterface(self, vi):
        """Generates the SCPI communication interface on the developer's tab of choice at tabSelect
        """
        # CONSTANTS
        self.SELECT_TERM_VALUES = ['Line Feed - \\n', 'Carriage Return - \\r']

        # VARIABLES
        tabSelect = self.tab2                # Select which tab this interface should be placed
        self.timeout = TIMEOUT_DEF           # VISA timeout value
        self.chunkSize = CHUNK_SIZE_DEF      # Bytes to read from buffer
        self.instrument = ''                 # ID of the currently open instrument. Used only in resetWidgetValues method

        # TKINTER VARIABLES
        self.sendEnd = BooleanVar()
        self.sendEnd.set(TRUE)
        self.enableTerm = BooleanVar()
        self.enableTerm.set(FALSE)

        vi.openRsrcManager()

        def onConnectPress():
            """Connect to the resource and update the string in self.instrument
            """
            if vi.connectToRsrc(self.instrSelectBox.get()) == RETURN_SUCCESS:
                self.instrument = self.instrSelectBox.get()
                self.scpiApplyConfig(vi, self.timeoutWidget.get(), self.chunkSizeWidget.get())
        def onRefreshPress():
            """Update the values in the SCPI instrument selection box
            """
            print('Searching for resources...')
            self.instrSelectBox['values'] = vi.rm.list_resources()
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
        self.instrSelectBox = ttk.Combobox(tabSelect, values = vi.rm.list_resources(), width=40)
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
        self.applyButton = tk.Button(self.configFrame, text = "Apply Changes", command = lambda:self.scpiApplyConfig(vi, self.timeoutWidget.get(), self.chunkSizeWidget.get()))
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
    
    # def PythonInterface( self ):
    #     """Generates the python console window 
    #     """ 
    #     pyWindow = tix.Tk()
    #     pyWindow.mainloop()

    def resetWidgetValues(self, vi, event):
        """Event handler to reset widget values to their respective variables

        Args:
            vi (VisaControl): VisaControl object to retrieve VISA values from
            event (event): Argument passed by tkinter event (Varies for each event)
        """
        # These widgets values are stored in variables and will be reset to the variable on function call
        try:
            self.timeoutWidget.set(self.timeout)
            self.chunkSizeWidget.set(self.chunkSize)
            self.instrSelectBox.set(self.instrument)
        except:
            pass
        # These widget values are retrieved from vi.openRsrc and will be reset depending on the values returned
        try:
            self.sendEnd.set(vi.openRsrc.send_end)
            readTerm = repr(vi.openRsrc.read_termination)
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
        
    def scpiApplyConfig(self, vi, timeoutArg, chunkSizeArg):
        """Issues VISA commands to set config and applies changes made in the SCPI configuration frame to variables timeout and chunkSize (for resetWidgetValues)

        Args:
            vi (VisaControl): Instance of class VisaControl to apply config to. Note some configs will be applied to all VISA attributes, not just the opened resource(s)
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
            timeoutArg = int(self.timeoutWidget.get())
            chunkSizeArg = int(self.chunkSizeWidget.get())
        except:
            raise TypeError('ttk::spinbox get() did not return type int')
        # Test timeout and chunk size for within range
        if timeoutArg < TIMEOUT_MIN or timeoutArg > TIMEOUT_MAX:
            raise TypeError(f'int timeout out of range. Min: {TIMEOUT_MIN}, Max: {TIMEOUT_MAX}')
        if chunkSizeArg < CHUNK_SIZE_MIN or chunkSizeArg > CHUNK_SIZE_MAX:
            raise TypeError(f'int chunkSize out of range. Min: {CHUNK_SIZE_MIN}, Max: {CHUNK_SIZE_MAX}')
        # Call vi.setConfig and if successful, print output and set variables for resetWidgetValues
        if vi.setConfig(timeoutArg, chunkSizeArg, self.sendEnd.get(), self.enableTerm.get(), termChar) == RETURN_SUCCESS:
            self.timeout = timeoutArg
            self.chunkSize = chunkSizeArg
            print(f'Timeout: {vi.openRsrc.timeout}, Chunk size: {vi.openRsrc.chunk_size}, Send EOI: {vi.openRsrc.send_end}, Termination: {repr(vi.openRsrc.write_termination)}')
            return RETURN_SUCCESS
        else:
            return RETURN_ERROR
    
    def serialInterface(self):
        """Generates the serial communication interface on the developer's tab of choice at tabSelect
        """

        tabSelect = self.tab1   # Select which tab this interface should be placed

        # create motor from class "Motorcontrol"
        self.motor = MotorControl( 0 , 0 )
        
        # port selection
        ports                   = list( serial.tools.list_ports.comports() ) 
        self.port_selection     = ttk.Combobox( tabSelect , values = ports )
        self.port_selection.grid(row = 0, column= 0 , padx = 20 , pady = 10)

        # time label 
        self.clock_label = tk.Label( tabSelect, font= ('Arial', 14))
        self.clock_label.grid( row= 0, column= 1, padx = 20 , pady = 10 )

        # box for asi ele information 
        self.positions      = tk.LabelFrame( tabSelect, text = "Antenna Position" )
        self.quickButton    = tk.Frame( tabSelect )
        self.positions.grid( row = 1, column = 0 , padx = 20 , pady = 10)
        self.quickButton.grid( row = 1, column= 1 , padx = 20 , pady = 10)


        # buttons : estop, park, free writing window, close
        self.EmargencyStop      = tk.Button( self.quickButton, text = "Emargency Stop", font = ('Arial', 16 ) , bg = 'red', fg = 'white' , command= self.Estop )
        self.Park               = tk.Button( self.quickButton, text = "Park", font = ('Arial', 16) , bg = 'blue', fg = 'white' , command = self.park )
        self.openFreeWriting    = tk.Button( self.quickButton, text = "Open Free Writing" ,font = ('Arial', 16 ), command= self.freewriting )
        # self.motorSettingButton = tk.Button( self.quickButton , text = "Motor Setting", font = ('Arial', 16 ), command = self.motor.MotorSetting )
        self.close              = tk.Button( self.quickButton, text = "Close Window",font = ('Arial', 16 ), command = self.closeWin )
        
        self.EmargencyStop.pack()
        self.Park.pack( pady = 10 )
        self.openFreeWriting.pack( pady = 10 )
        # self.motorSettingButton.pack( pady = 10)
        self.close.pack( pady = 20 )

        # azi,ele input boxes creation
        self.boxFrame           = tk.Frame( self.positions )
        self.boxFrame.pack( pady = 10)

        self.azimuth_label      = tk.Label( self.boxFrame , text = "Azimuth" )
        self.elevation_label    = tk.Label( self.boxFrame , text = "Elevation")
        # self.current_azimuth = tk.Label( self.boxFrame, text = self.motor.Azimuth )
        # self.current_elevation = tk.Label( self.boxFrame, text = self.motor.Elevation )
        self.inputAzimuth       = tk.Entry( self.boxFrame, width= 10 )
        self.inputElevation     = tk.Entry( self.boxFrame, width= 10 )

        self.azimuth_label.grid( row = 0, column = 0, padx = 10 )
        self.elevation_label.grid( row = 1, column = 0, padx = 10 )
        # self.current_azimuth.grid( row = 0, column = 1, padx = 10 )
        # self.current_elevation.grid( row = 1, column = 1, padx = 10 )
        self.inputAzimuth.grid( row = 0, column = 2, padx = 10 )
        self.inputElevation.grid( row = 1, column = 2, padx = 10 )

        # enter button creation
        self.printbutton        = tk.Button( self.positions, text = "Enter", command = self.input )
        self.printbutton.pack( padx = 20, pady = 10, side = 'right' )

    def update_time( self ):
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.clock_label.config(text=current_time)
        self.root.after(1000, self.update_time)


    def closeWin( self ):
        self.motor.CloseSerial()
        self.root.destroy()


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
        self.root.destroy()


