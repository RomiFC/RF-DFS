"""
 * @file opcodes.py
 * @author Remy Nguyen (rnguyen@nrao.edu)
 * @brief Header file that contains opcode declarations for the P1AM-100 PLC.
 * 
 * Each opcode is an 8-bit binary number with the following syntax:
 * - Leading 1
 * - 1 for selection operation
 * - 2-bit antenna selection code (00 for EMS, 01 for DFS)
 * - 4-bit RF chain selection code
 * 
 * OR
 * 
 * - Leading 1
 * - 0 for config or sleep operation
 * - 6-bit config opcode
 *
 * Due to the way the PLC is written to parse inputs, each opcode MUST be terminated by a newline (\n) character.
 * 
 * @date Last Modified: 2024-08-07
 * 
 * @copyright Copyright (c) 2024
 * 
 """

from enum import Enum

class opcodes(Enum):
    SLEEP                  = (0b10000000)
    RETURN_OPCODES         = (0b10000001)
    GET_FW_VERSION         = (0b10000010)
    PRINT_MODULES          = (0b10000011)
    IS_BASE_ACTIVE         = (0b10000100)
    P1_INIT                = (0b10000101)
    P1_DISABLE             = (0b10000110)
    QUERY_STATUS           = (0b10000111)
    CHECK_24V_SL1          = (0b10001001)
    CHECK_24V_SL2          = (0b10001010)
    CHECK_24V_SL3          = (0b10001011)
    READ_STATUS_SL1        = (0b10010001)
    READ_STATUS_SL2        = (0b10010010)
    READ_STATUS_SL3        = (0b10010011)
    EMS_CHAIN1             = (0b11000000)
    EMS_CHAIN2             = (0b11000001)
    EMS_CHAIN3             = (0b11000010)
    EMS_CHAIN4             = (0b11000011)
    EMS_CHAIN5             = (0b11000100)
    EMS_CHAIN6             = (0b11000101)
    EMS_CHAIN7             = (0b11000110)
    EMS_CHAIN8             = (0b11000111)
    EMS_CHAIN9             = (0b11001000)
    EMS_CHAIN10            = (0b11001001)
    EMS_CHAIN11            = (0b11001010)
    EMS_CHAIN12            = (0b11001011)
    EMS_CHAIN13            = (0b11001100)
    EMS_CHAIN14            = (0b11001101)
    EMS_CHAIN15            = (0b11001110)
    EMS_CHAIN16            = (0b11001111)
    DFS_CHAIN1             = (0b11010000)
    DFS_CHAIN2             = (0b11010001)
    DFS_CHAIN3             = (0b11010010)
    DFS_CHAIN4             = (0b11010011)
    DFS_CHAIN5             = (0b11010100)
    DFS_CHAIN6             = (0b11010101)
    DFS_CHAIN7             = (0b11010110)
    DFS_CHAIN8             = (0b11010111)
    DFS_CHAIN9             = (0b11011000)
    DFS_CHAIN10            = (0b11011001)
    DFS_CHAIN11            = (0b11011010)
    DFS_CHAIN12            = (0b11011011)
    DFS_CHAIN13            = (0b11011100)
    DFS_CHAIN14            = (0b11011101)
    DFS_CHAIN15            = (0b11011110)
    DFS_CHAIN16            = (0b11011111)