"""Module that handles inputs/outputs of the Python Front End.
"""

# MISC LIBRARIES
import sys
import logging
from data import *
import opcodes
import threading

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

class MotorIO: 
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

class SerialIO:
    def __init__(self):
        """Contains methods for serial communication with the PLC. The attribute 'serial' can be used to directly manipulate the instance of serial.Serial().
        """
        self.serial = serial.Serial()
        self.serialLock = threading.RLock()
        self.TIMEOUT = 5.0                        # Default timeout between read and write commands in query call.

    def threadHandler(self, target, args=(), kwargs={}):
        """Generates a new thread to handle IO routines without blocking main thread. For most operations, this should be used instead of calling target methods directly.

        Args:
            target (method): Callable object to be invoked by the run() method.
            args (tuple, optional): List or tuple for target invocation. Defaults to ().
            kwargs (dict, optional): Dictionary of keyword arguments for target invocation. Defaults to {}.
        """
        if not hasattr(SerialIO, target.__name__):
            logging.error(f'Class SerialIO does not contain a method with identifier {target.__name__}')
            return
        thread = threading.Thread(target = target, args = args, kwargs = kwargs, daemon=True)
        thread.start()

    def openSerial(self, port, baud=115200, timeout=1):
        """Open serial communications with the object 'serial' at the port and baud rate specified.  If a port is already open, close it and open a new session.

        Args:
            port (string): Serial port (COM#).
            baud (int, optional): Baud rate. Defaults to 115200.
            timeout (int, optional): Timeout in seconds. Defaults to 1.
        """
        with self.serialLock:
            if self.serial.is_open:
                self.serial.close()
            self.serial = serial.Serial(port, baud, timeout=timeout)

    def close(self):
        """Closes serial communications.
        """
        self.serial.close()

    def query(self, msg, converter='bin', delay=None):
        """Writes message to the serial object at self.serial and logs the response after 'delay' seconds at level SERIAL. Due to the delay this should only be called by the thread handler to prevent blocking.

        Args:
            msg (string or int): Message to send. If msg is passed as an integer, it will be converted to a string in the format defined by 'converter'.
            converter (str, optional): Format to convert the message to if it is an integer. Can be 'bin' or 'int'. Defaults to 'bin'.
            delay (float, optional): Delay between read and write commands. Defaults to self.TIMEOUT.
        """
        if delay is None:
            delay = self.TIMEOUT
        self.write(msg, converter=converter)
        timer = time.time()
        while time.time() - timer < delay:
            self.read()

    def write(self, msg, converter='bin'):
        """Writes message to the serial object at self.serial appended with a newline character.

        Args:
            msg (string or int): Message to send. If msg is passed as an integer, it will be converted to a string in the format defined by 'converter'.
            converter (str, optional): Format to convert the message to if it is an integer. Can be 'bin' or 'int'. Defaults to 'bin'.
        """
        with self.serialLock:
            if type(msg) == str:
                if msg[-1] != '\n':
                    msg = msg + '\n'
                self.serial.write(msg.encode('utf-8'))
            elif type(msg) == int and converter == 'bin':
                msg = bin(msg)[2:] + '\n'
                self.serial.write(msg.encode('utf-8'))
            elif type(msg) == int and converter == 'int':
                msg = str(msg) + '\n'
                self.serial.write(msg.encode('utf-8'))
        logging.serial(f'>>> {repr(msg)}')


    def readLine(self):
        """Reads the serial buffer up to a newline character and logs it at level SERIAL.
        """
        with self.serialLock:
            logging.serial(self.serial.readline().decode('utf-8'))

    def read(self):
        """Reads the amount of bytes in the input buffer and logs it at level SERIAL. If a timeout is reached, log the remaining bytes in the serial buffer.
        """
        with self.serialLock:
            buffer = self.serial.read(self.serial.in_waiting).decode('utf-8')
            lines = buffer.splitlines()
            for i in lines:
                if i:   # Check if the string is empty
                    logging.serial(i)

    def flushInput(self):
        """Flush the input buffer, discarding all its contents.
        """
        with self.serialLock:
            self.serial.reset_input_buffer()

    def flushOutput(self):
        """Clear output buffer, aborting the current output and discarding all that is in the buffer.
        Note, for some USB serial adapters, this may only flush the buffer of the OS and not all the data that may be present in the USB part.
        """
        with self.serialLock:
            self.serial.reset_output_buffer()


class VisaIO():
    def __init__(self):
        """Opens the VISA resource manager on the default backend (NI-VISA). If the VISA library cannot be found, a path must be passed to pyvisa.highlevel.ResourceManager() constructor
        """
        logging.info('Initializing VISA Resource Manager...')
        self.rm = visa.ResourceManager()
        if self.isError():
            logging.error(f'Could not open a session to the resource manager, error code: {hex(self.rm.last_status)}')
            return    
        logging.info(f'Success code {hex(self.rm.last_status)}')
        return
    
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
    
    def identify(self):
        """Issues *IDN? to the open resource and returns a list of its response, split at each comma.

        Returns:
            list: List of strings of the device's response. Typically of the format ["Manufacturer", "Model", "Serial No.", "Software Revision"].
        """
        buffer = self.openRsrc.query_ascii_values("*IDN?", converter='s')
        try:    # N9040b returns string wrapped in brackets which python interprets as a list
            buffer = buffer.split(',')
        except:
            pass
        return buffer
    
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
            # logging.info(f'Success code: {hex(self.rm.last_status)}')
            return RETURN_SUCCESS
        
    def queryErrors(self):
        """Issues ':SYST:ERR?' to the open resource and logs response at level INFO
        """
        buffer = self.openRsrc.query_ascii_values(":SYST:ERR?", converter='s')
        # Conversion because this device returns string wrapped in brackets. Python interprets this as a list with a single string
        # if len(buffer[0]) > 1:
        #     try:
        #         buffer = buffer[0].strip("[]")
        #     except:
        #         pass
        logging.info(f'{buffer}')
        
    def queryPowerUpErrors(self):
        """Issues ':SYST:ERR:PUP?' to the open resource and logs response at level INFO
        """
        buffer = self.openRsrc.query_ascii_values(":SYST:ERR:PUP?", converter='s')
        if len(buffer[0]) > 1:
            try:
                buffer = buffer[0].strip("[]")
            except:
                pass
        logging.info(f'{buffer.strip("[]").strip()}')   # Remove brackets, leading and trailing whitespace, and newline characters

    def getEventRegister(self):
        """Issues '*ESR?' to the open resource and returns integer response

        Returns:
            Status (int): Integer sum of bits in Event Status Register
        """
        return self.openRsrc.query_ascii_values("*ESR?")

    def getOperationRegister(self):
        """Issues ':STAT:OPER:COND?' to the open resource and returns integer response

        Returns:
            Status (int): Integer sum of bits in Operation Status Condition Register
        """
        # Conversion because this device returns number wrapped in brackets. Python interprets this as a list with a single float
        buffer = self.openRsrc.query_ascii_values(":STAT:OPER:COND?")
        buffer = int(buffer[0])
        return buffer

    def getCalCondRegister(self):
        """Issues ':STAT:QUES:CAL:COND?' to the open resource and returns integer response

        Returns:
            Status (int): Integer sum of bits in Questionable Calibration Register
        """
        # Conversion because this device returns number wrapped in brackets. Python interprets this as a list with a single float
        buffer = self.openRsrc.query_ascii_values(":STAT:QUES:CAL:COND?")
        buffer = int(buffer[0])
        return buffer