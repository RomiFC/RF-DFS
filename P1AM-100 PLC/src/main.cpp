/**
 * @file main.cpp
 * @author Remy Nguyen (rnguyen@nrao.edu)
 * @brief Code for the P1AM-100 PLC. This will continuously read and parse ASCII serial inputs for a valid opcode, then
 * initialize the finite state machine for return operations.
 * Hardware requirements include a P1-15TD2 discrete output module and a 24VDC power supply connected to the P1AM-100.
 * @date Last Modified: 2024-08-07
 * 
 * @copyright Copyright (c) 2024
 * 
 */

#include <Arduino.h>
#include <P1AM.h>
#include <opcodes.h>

// CONSTANTS
#define BUFFER_LENGTH           (8+2)     // Amount of bytes to accept from serial. Should be equal to the amount of ASCII bytes in the opcode plus 2 for CRLF
#define SLOT_DISCRETE_OUT_15    1         // Slot on the P1AM that the P1-15TD2 discrete output module is connected to.
#define ONE_SECOND              1000
#define ONE_MINUTE              60000

// OUTPUT CHANNELS
#define ALL_CHANNELS            0
#define CH_EMS_RF1              1
#define CH_EMS_RF2              2
#define CH_EMS_RF3              3
#define CH_EMS_RF4              4
#define CH_DFS_RF1              5
#define CH_DFS_RF2              6
#define CH_DFS_RF3              7
#define CH_DFS_RF4              8
#define CH_EMS_SELECT           9
#define CH_DFS_SELECT           10

// GLOBAL VARIABLES
bool returnOpCodes = false;               // Determines whether or not to Serial.print parsed opcodes
int status;


/**
 * @brief This function removes surplus characters from the serial buffer.
 * Otherwise, if more than the permitted number of characters have been entered during the call to Serial.readBytes(), the
 * surplus characters (after BUFFER_LENGTH) remain in the input buffer and will be wrongly accepted as input on the next
 * iteration of the loop.
 * 
 */
static inline void clearSerialBuffer()
{
	while (Serial.available()) {
        Serial.read();
    }
}

/**
 * @brief Takes BUFFER_LENGTH bytes from the serial buffer and searches for a binary number.
 * Calls clearSerialBuffer() if too many characters are found so as to not retain buffer characters on the next loop iteration.
 * If the buffer contains ASCII characters that are not 0 or 1 after a sequence of 0s and/or 1s, they will be ignored.
 * 
 * @return int binaryLiteral on success (Input successfully parsed as binary). If no valid conversion could be performed, a zero value is returned.
 * Note that it is possible for a zero value binaryLiteral to be successfully parsed and returned.
 */
int parseInput() {
    char* buffer = (char*)malloc(sizeof(char) * BUFFER_LENGTH);
    char* endPtr = NULL;
    int binaryLiteral;
    // Read BUFFER_LENGTH bytes into the buffer and test for success
    if (!Serial.readBytes(buffer, BUFFER_LENGTH)) {
        Serial.println("Read termination not found or buffer empty.");
        free(buffer);
        return 0;
    }
    // Get span until newline is found (To ensure correct buffer length)
    if (strcspn(buffer, "\n") <= 1 || strcspn(buffer, "\n") > BUFFER_LENGTH) {
        Serial.println("Too many characters in buffer or buffer empty.");
        free(buffer);
        clearSerialBuffer();
        return 0;
    }
    // Attempt to convert the string in buffer to a base 2 integer literal
    binaryLiteral = strtol(buffer, &endPtr, 2);
    if (buffer == endPtr) { // If a binary integer is not found, endPtr remains set to buffer
        Serial.println("No binary integer found");
        free(buffer);
        return 0;
    }
    free(buffer);
    return binaryLiteral;
    
    
}

/**
 * @brief Setup runs once during power on, initializes serial communication and PLC modules
 * 
 */
void setup() {
    Serial.begin(115200);
    while (!P1.init() && !Serial){}   //Wait for module and serial port to initialize
    delay(1000);
}

/**
 * @brief This loop runs continuously while the PLC is powered on.
 * 
 */
void loop() {
    int opCode;
    char outputStringBuffer[256];
    // Wait for information in serial buffer
    if (!Serial.available()) {
        return;
    }
    // If information is available, call parseInput() and ensure a nonzero (successful) return
    opCode = parseInput();
    if (!opCode) {
        return;
    }
    // Print the received opCode
    if (returnOpCodes && opCode != QUERY_STATUS) {
        sprintf(outputStringBuffer, "OpCode: 0x%02X (%d)", opCode, opCode);
        Serial.println(outputStringBuffer);
    }

    // Test opCode for valid commands
    switch (opCode) {
        case SLEEP:
            Serial.println("Sleep issued: all outputs disabled.");
            P1.writeDiscrete(0, SLOT_DISCRETE_OUT_15, 0);
            status = opCode;
            break;
        case RETURN_OPCODES:
            returnOpCodes = !returnOpCodes;
            if (returnOpCodes) Serial.println("Parsed OpCodes will be returned.");
            else Serial.println("OpCode returns disabled.");
            break;
        case GET_FW_VERSION:
            if (P1.isBaseActive()) {
                Serial.println(P1.getFwVersion());
            }
            break;
        case IS_BASE_ACTIVE:
            Serial.println(P1.isBaseActive());
            break;
        case PRINT_MODULES:
            if (P1.isBaseActive()) {
                P1.printModules();
            }
            break;
        case P1_INIT:
            Serial.println("Initializing...");
            while (!P1.init()){}
            status = SLEEP;
            break;
        case P1_DISABLE:
            Serial.println("Disabling P1AM-100 Module");
            P1.enableBaseController(false);
            status = opCode;
            break;
        case QUERY_STATUS:
            Serial.println(status);
            break;
        case EMS_CHAIN1:
            sprintf(outputStringBuffer, "EMS Chain 1 selected: writing to channels %d and %d.", CH_EMS_RF1, CH_EMS_SELECT);
            Serial.println(outputStringBuffer);
            P1.writeDiscrete(LOW, SLOT_DISCRETE_OUT_15, ALL_CHANNELS);
            P1.writeDiscrete(HIGH, SLOT_DISCRETE_OUT_15, CH_EMS_RF1);
            P1.writeDiscrete(HIGH, SLOT_DISCRETE_OUT_15, CH_EMS_SELECT);
            status = opCode;
            break;
        case EMS_CHAIN2:
            sprintf(outputStringBuffer, "EMS Chain 2 selected: writing to channels %d and %d.", CH_EMS_RF2, CH_EMS_SELECT);
            Serial.println(outputStringBuffer);
            P1.writeDiscrete(LOW, SLOT_DISCRETE_OUT_15, ALL_CHANNELS);
            P1.writeDiscrete(HIGH, SLOT_DISCRETE_OUT_15, CH_EMS_RF2);
            P1.writeDiscrete(HIGH, SLOT_DISCRETE_OUT_15, CH_EMS_SELECT);
            status = opCode;
            break;
        case DFS_CHAIN1:
            sprintf(outputStringBuffer, "DFS Chain 1 selected: writing to channels %d and %d.", CH_DFS_RF1, CH_DFS_SELECT);
            Serial.println(outputStringBuffer);
            P1.writeDiscrete(LOW, SLOT_DISCRETE_OUT_15, ALL_CHANNELS);
            P1.writeDiscrete(HIGH, SLOT_DISCRETE_OUT_15, CH_DFS_RF1);
            P1.writeDiscrete(HIGH, SLOT_DISCRETE_OUT_15, CH_DFS_SELECT);
            status = opCode;
            break;
        default:
            Serial.println("Unrecognized OpCode.");
            return;
    }
}

