"""Module that handles inputs/outputs of the Python Front End.
"""

# MISC LIBRARIES
import sys
import logging
from data import *

# TKINTER
import tkinter as tk
from tkinter import *
from tkinter import messagebox

# SERIAL
import serial
import serial.tools.list_ports

# TIMING
import time
from timestamp import *

# VISA
import pyvisa as visa
from pyvisa import constants

# CONSTANTS
RETURN_ERROR = 1
RETURN_SUCCESS = 0

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
                logging.info(f'{self.ser.in_waiting}')
                msg = self.ser.readline()
                logging.info(f'{msg}')
                
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
            logging.info("Raange Check cleared")
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
                
                logging.info(f'{self.ser.is_open}')

                # while( self.ser.readline().isspace() ): 
                #     logging.info( "waiting" )
        
                # if ( self.ser.readline() == b'SYS'  ):
                #     self.ser.write( 'prog 0' )
                # if ( self.ser.readline() == b'P00' ):
                #     self.ser.write( 'drive on x y' )      
                self.sendCommand('\n')
                time.sleep(3) #needed to let arduino to send it back 
                self.readLine()
                logging.info( "communication to motor controller is ready" )
                
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
            Literal (int): 0 on success, 1 on error.
        """
        logging.info('Initializing VISA Resource Manager...')
        self.rm = visa.ResourceManager()
        if self.isError():
            logging.error(f'Could not open a session to the resource manager, error code: {hex(self.rm.last_status)}')
            return RETURN_ERROR     
        return RETURN_SUCCESS
    
    def connectToRsrc(self, inputString):
        """Opens a session to the resource ID passed from inputString if it is not already connected

        Args:
            inputString (string): Name of the resource ID to attempt to connect to. 

        Returns:
            Literal (int): 0 on success, 1 on error.
        """
        try:
            self.openRsrc.session                           # Is a session open? (Will throw error if not open)
        except:
            pass                                            # If not open --> continue
        else:
            if self.openRsrc.resource_name == inputString:  # Is the open resource's ID the same as inputString?
                logging.info('Device is already connected')
                return RETURN_SUCCESS                       # If yes --> return
        
        # If a session is not open or the open resource does not match inputString, attempt connection to inputString
        logging.info(f'Connecting to resource: {inputString}')
        self.openRsrc = self.rm.open_resource(inputString)
        if self.isError():
            logging.error(f'Could not open a session to {inputString}')
            logging.error(f'Error Code: {self.rm.last_status}')
            return RETURN_ERROR
        return RETURN_SUCCESS
    
    def resetAnalyzerState(self):
        """Issues *RST, *WAI, and :INIT CONT OFF to the open resource.
        """
        self.openRsrc.write("*RST")
        self.openRsrc.write("*WAI")
        # Consider issuing sleep time or *OPC? here
        self.openRsrc.write(":INIT:CONT OFF")

    def testBufferSize(self):
        # PyVISA reads until a termination is received, not specified bytes like NI-VISA unless resource.read_bytes() is called.
        # As a result, this test may not be necessary but edge cases for the maximum return value of resource.read() must be tested.
        self.openRsrc.write(":FETCh:SAN?")
        buffer = self.openRsrc.read_ascii_values()
        statusCode = self.openRsrc.last_status
        # if (statusCode == constants.VI_SUCCESS_MAX_CNT or statusCode == constants.VI_SUCCESS_TERM_CHAR):
        #     logging.error(f"Error {hex(statusCode)}: viRead did not return termination character or END indicated. Increase read bytes to fix.")
        #     self.Vi.openRsrc.flush(constants.VI_READ_BUF)
        #     return RETURN_ERROR
        logging.info(f"Buffer size: {sys.getsizeof(buffer)} bytes")
        logging.info(f"Status byte: {hex(statusCode)}.")
    
    def setConfig(self, timeout, chunkSize, sendEnd, enableTerm, termChar):
        """Applies VISA attributes passed in arguments to the open resource when called

        Args:
            timeout (int): VISA timeout value in milliseconds.
            chunkSize (int): PyVISA chunk size in bytes (Read buffer size).
            sendEnd (bool): Determine whether or not to send EOI on VISA communications.
            enableTerm (bool): Determine whether or not to send a termination character on VISA communications.
            termChar (string): Termination character to send on VISA communications.

        Returns:
            Literal (int): 0 on success, 1 on error.
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
                logging.error(f'An exception occurred. Error code: {self.rm.last_status}')
                return RETURN_ERROR
        else:
            logging.error("Session to a resource is not open")
            return RETURN_ERROR
            
        
    def isSessionOpen(self):
        """Tests if a session is open to the variable openRsrc

        Returns:
            Literal (bool): FALSE if session is closed, TRUE if session is open.
        """
        try:
            self.openRsrc.session                           # Is a session open? (Will throw error if not open)
        except:
            return FALSE
        else:
            return TRUE
        
    def isError(self):
        """Checks the last status code returned from an operation at the opened resource manager (self.rm)

        Returns:
            Literal (int): 0 on success or warning (operation succeeded), StatusCode on error.
        """
        if self.rm.last_status < constants.VI_SUCCESS:
            return self.rm.last_status
        else:
            logging.info(f'Success code: {hex(self.rm.last_status)}')
            return RETURN_SUCCESS
        