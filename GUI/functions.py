# import tkinter as tk
# from tkinter import ttk
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import time
import pyvisa as visa

# CONSTANTS
RETURN_ERROR = 1
RETURN_SUCCESS = 0
READ_BYTES_DEF = 4096     # Default byte count to read when issuing viRead
READ_BYTES_MIN = 1024
READ_BYTES_MAX = 1048576  # Max read bytes allowed
TIMEOUT_DEF = 2500        # Default VISA timeout value
TIMEOUT_MIN = 1000        # Minimum VISA timeout value
TIMEOUT_MAX = 25000       # Maximum VISA timeout value

class MotorControl: 

    def __init__(self, Azimuth, Elevation, userAzi = 0, userEle = 0, Azi_bound = [0,360], Ele_bound = [0,120] ): 
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
        self.portConnection()

        # commands 
        self.commandToSend  = ""
        self.nextCommand    = ""
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
        messagebox.showwarning( title= self.errorType , message= self.errorMsg )

    def sendCommand( self ):
        try: 
            newline = '\r\n'
            self.commandToSend += newline
            # self.ser.write('print "asdf"\r\n'.encode('utf-8'))
            time.sleep(1)
            # self.readLine()
            time.sleep(1)
            # print(self.commandToSend)
            # self.ser.write( self.commandToSend+'\r\n'.encode('utf-8'))
           
            self.ser.write( self.commandToSend.encode('utf-8')+'\r\n'.encode('utf-8'))
           
            time.sleep(1)
            self.readLine()
            if self.nextCommand != "":
                self.ser.write( self.nextCommand.encode('utf-8'))
            time.sleep(1)
            # self.readLine()

            self.commandToSend = ""
            self.nextCommand = ""
            print("command sent")
            

        except:
            self.errorType = self.connectionError[0]
            self.errorMsg = self.connectionError[1]
            self.errorPopup()


    def readLine( self ):
        msg = self.ser.readline()
        # message = msg.decode('utf-8') 
        print(msg)
        
 

    def readUserInput( self ):
        if self.userAzi == "":
            self.userAzi = str ( self.Azimuth )
        if self.userEle == "":
            self.userEle = str( self.Elevation )
        elif ((self.userAzi).isdigit()) and ((self.userEle).isdigit()):
           self.checkrange()
        else : 
            self.errorType = self.inputTypeError[0]
            self.errorMsg = self.inputTypeError[1]
            self.errorPopup()

    def checkrange( self ): 
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
            self.commandToSend = self.commandGen + " x " + self.userAzi + " y " + self.userEle 
            self.sendCommand()
            self.Azimuth = self.userAzi
            self.Elevation = self.userEle
        else: 
            self.errorType = self.rangeError[0]
            self.errorMsg = self.rangeError[1] + "Azimuth: " + str(self.Azi_bound[0]) + "-" + str(self.Azi_bound[1]) + "\n" + "Elevation: " +  str(self.Ele_bound[0]) + "-" + str(self.Ele_bound[1])
            self.errorPopup()
   
    def portConnection( self ):
        if self.port != '':
           
            if self.ser.is_open:
                self.ser.close()
            try:    
                self.ser = serial.Serial(port= 'COM4', baudrate=9600 , bytesize= 8, parity='N', stopbits=1,xonxoff=0)
                # print( "typing in setting commands" )
                time.sleep(1)
                # self.ser.write("\n")
                # self.ser.write( self.startCommand[0] )
                # # if self.readLine() = 
                # self.ser.write( self.startCommand[1] )
                # self.ser.write( "\n" ) 
                print( "communication to motor controller is ready")
            except:
                 self.errorType = self.connectionError[0]
                 self.errorMsg = self.connectionError[1]
                 self.errorPopup() 

    def EmargencyStop( self ):
        self.commandToSend = self.breakCommand
        self.sendCommand()
     
    def Park( self ):
        self.commandToSend = self.commandGen + " x " + str( self.homeAzi ) + " y " + str( self.homeEle )
        self.sendCommand()
    

    def freeInput( self ):
        def ReadandSend():

            self.commandToSend = inBox.get()
            # print(inBox.get())
            self.sendCommand()
            # update()
        
        def update(): 
            # current = returnLineBox["Text"]
            print("current label" + returnLineBox["text"])
            try:
                line = self.ser.readline()
                if line.decode != '':
                    returnLineBox["text"] = line.decode('utf-8')
                print("new label" + returnLineBox["text"])
            except:
                self.errorType = self.connectionError[0]
                self.errorMsg = self.connectionError[1]
                self.errorPopup()

        freeWriting = tk.Tk() 
        freeWriting.title("Serial Communication")

        labelInput      = tk.Label( freeWriting, text= "Type Input: ")
        inBox           = tk.Entry( freeWriting , width= 50 )
        enterButton     = tk.Button( freeWriting , text = "Enter" , command = ReadandSend )
        returnLineBox   = tk.Label( freeWriting , text = 'hi')

        labelInput.pack( padx = 10, pady = 5 )
        inBox.pack( side = 'left', padx = 10, pady = 5 )
        enterButton.pack( side = 'right' ,padx = 10, pady = 5)
        returnLineBox.pack( padx = 10, pady = 5 )


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
    def __init__(self):
        self.instr = ''

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
    
    def connectToRsrc(self):
        """Opens a session to the resource ID located in self.instr

        Returns:
            0: On success
            1: On error
        """
        if self.instr != '':
            print('Connecting to resource: ' + self.instr)
            self.openRsrc = self.rm.open_resource(self.instr)
            if self.isError():
                print('Could not open a session to ' + self.instr)
                print('Error Code:' + self.rm.last_status)
                return RETURN_ERROR
            return RETURN_SUCCESS
        
    def isError(self):
        """Checks the last status code returned from an operation at the opened resource manager (self.rm)

        Returns:
            0: On success or warning (Operation succeeded)
            1: On error
        """
        if self.rm.last_status < 0:
            return RETURN_ERROR
        else:
            print('Success code:', hex(self.rm.last_status))
            return RETURN_SUCCESS
        

class FrontEnd():
    def __init__(self):
        """Initializes the top level tkinter interface
        """
        self.root = tk.Tk()
        self.root.title('DFS-control')

        tabControl = ttk.Notebook(self.root) 
  
        self.tab1 = ttk.Frame(tabControl) 
        self.tab2 = ttk.Frame(tabControl) 

        tabControl.add(self.tab1, text ='Tab 1') 
        tabControl.add(self.tab2, text ='Tab 2') 
        tabControl.pack(expand = 1, fill ="both") 

        self.serialInterface()
        self.scpiInterface()
        self.root.mainloop()

    def scpiInterface(self):
        """Generates the SCPI communication interface on the developer's tab of choice at tabSelect
        """

        tabSelect = self.tab2           # Select which tab this interface should be placed
        self.timeout = TIMEOUT_DEF           # VISA timeout value
        self.readBytes = READ_BYTES_DEF      # Bytes to read from buffer
        vi = VisaControl()
        vi.openRsrcManager()
        instruments = vi.rm.list_resources()

        def updateInstruments():
            """Update the list of VISA resources stored in 'instruments'
            """
            global instruments  # List returned from vi.rm.list_resources()
            instruments = vi.rm.list_resources()

        def scpiConnectButtonPress():
            """Check if the current instrument ID is equivalent to the string in the combobox instrSelectBox. If yes, set instrument ID and call vi.connectToRsrc
            """
            if vi.instr != self.instrSelectBox.get():
                vi.instr = self.instrSelectBox.get()
                vi.connectToRsrc()

        # Instrument selection panel
        # ISSUE: Instrument list does not update
        # ISSUE: Apply changes should only be pressable when changes are detected
        ttk.Label(tabSelect, text = "Select a SCPI instrument:", 
          font = ("Times New Roman", 10)).grid(column = 0, 
          row = 0, padx = 10, pady = 25) 
        self.instrSelectBox = ttk.Combobox(tabSelect, values = instruments, width=60, postcommand = lambda:updateInstruments())
        self.instrSelectBox.grid(row = 0, column = 1, padx = 20 , pady = 10)
        self.confirmButton = tk.Button(tabSelect, text = "Connect", command = lambda:scpiConnectButtonPress())
        self.confirmButton.grid(row = 0, column = 3)

        self.configFrame = ttk.LabelFrame(tabSelect, borderwidth = 2, text = "Configuration")
        self.configFrame.grid(row = 1, column = 0, padx=20, pady=10)
        self.timeoutLabel = ttk.Label(self.configFrame, text = 'Timeout (ms)')
        self.timeoutWidget = ttk.Spinbox(self.configFrame, from_=TIMEOUT_MIN, to=TIMEOUT_MAX, textvariable=self.timeout)
        self.timeoutWidget.set(self.timeout)
        self.readBytesLabel = ttk.Label(self.configFrame, text = 'Bytes to read')
        self.readBytesWidget = ttk.Spinbox(self.configFrame, from_=READ_BYTES_MIN, to=READ_BYTES_MAX, textvariable=self.readBytes)
        self.readBytesWidget.set(self.readBytes)
        self.applyButton = tk.Button(self.configFrame, text = "Apply Changes", command = lambda:self.scpiApplyConfig())
        
        self.timeoutLabel.grid(row = 0, column = 0)
        self.timeoutWidget.grid(row = 1, column = 0, padx=20, columnspan=2)
        self.readBytesLabel.grid(row = 2, column = 0)
        self.readBytesWidget.grid(row = 3, column = 0, padx=20, columnspan=2)
        self.applyButton.grid(row = 4, column = 2)
    
    def scpiApplyConfig(self):
        """Applies changes made in the SCPI configuration frame to variables timeout and readBytes, Then issues VISA commands set config

        Raises:
            TypeError: ttk::spinbox get() does not return type int or integer out of range for respective variable

        Returns:
            0: On success
        """
        try:
            self.timeout = int(self.timeoutWidget.get())
            self.readBytes = int(self.readBytesWidget.get())
        except:
            raise TypeError('ttk::spinbox get() did not return type int')
        
        if self.timeout < TIMEOUT_MIN or self.timeout > TIMEOUT_MAX:
            raise TypeError(f'int timeout out of range. Min: {TIMEOUT_MIN}, Max: {TIMEOUT_MAX}')
        if self.readBytes < READ_BYTES_MIN or self.readBytes > READ_BYTES_MAX:
            raise TypeError(f'int readBytes out of range. Min: {READ_BYTES_MIN}, Max: {READ_BYTES_MAX}')
        
        print(f'Operation successful. Timeout: {self.timeout}, Read Bytes: {self.readBytes}')
        return RETURN_SUCCESS
    
    def serialInterface(self):
        """Generates the serial communication interface on the developer's tab of choice at tabSelect
        """

        tabSelect = self.tab1   # Select which tab this interface should be placed

         # create motor from class "Motorcontrol"
        self.motor = MotorControl( 0 , 90 )
        
        # box for asi ele information 
        self.positions      = tk.LabelFrame( tabSelect, text = "Antenna Position" )
        self.quickButton    = tk.Frame( tabSelect )

        self.positions.grid( row = 1, column = 0 , padx = 20 , pady = 10)
        self.quickButton.grid( row = 1, column= 1 , padx = 20 , pady = 10)

        # port selection
        ports                   = list( serial.tools.list_ports.comports() ) 
        self.port_selection     = ttk.Combobox( tabSelect , values = ports )
        self.port_selection.grid(row = 0, column= 0 , padx = 20 , pady = 10)

        # buttons : estop, park, free writing window
        self.EmargencyStop      = tk.Button( self.quickButton, text = "Emargency Stop", font = ('Arial', 16 ) , bg = 'red', fg = 'white' , command= self.Estop )
        self.Park               = tk.Button( self.quickButton, text = "Park", font = ('Arial', 16) , bg = 'blue', fg = 'white' , command = self.park )
        self.openFreeWriting    = tk.Button( self.quickButton, text = "Open Serial Communication" ,font = ('Arial', 16 ), command= self.freewriting )
        # self.motorSettingButton = tk.Button( self.quickButton , text = "Motor Setting", font = ('Arial', 16 ), command = self.motor.MotorSetting )
        
        self.EmargencyStop.pack()
        self.Park.pack( pady = 10 )
        self.openFreeWriting.pack( pady = 10 )
        # self.motorSettingButton.pack( pady = 10)

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


    def freewriting(self):
        self.motor.freeInput()

    def Estop(self):
        
        if self.motor.port != self.port_selection.get()[:4]: 
            portName = self.port_selection.get()
            self.motor.port = portName[:4]
            self.motor.portConnection()
       
        self.motor.EmargencyStop()
    
    def park( self ):
        if self.motor.port != self.port_selection.get()[:4]: 
            portName = self.port_selection.get()
            self.motor.port = portName[:4]
            self.motor.portConnection()
        self.motor.Park()

    def input(self):
    
        if self.motor.port != self.port_selection.get()[:4]: 
            portName = self.port_selection.get()
            self.motor.port = portName[:4]
            self.motor.portConnection()

        self.motor.userAzi = self.inputAzimuth.get()
        self.motor.userEle = self.inputElevation.get()
        self.motor.readUserInput()      


    def quit(self):
        self.root.destroy()


