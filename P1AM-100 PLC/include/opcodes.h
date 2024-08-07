/**
 * @file opcodes.h
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
 * @date Last Modified: 2024-08-07
 * 
 * @copyright Copyright (c) 2024
 * 
 */


#define SLEEP           (0b10000000)
#define RETURN_OPCODES  (0b10000001)
#define GET_FW_VERSION  (0b10000010)
#define PRINT_MODULES   (0b10000011)
#define IS_BASE_ACTIVE  (0b10000100)
#define P1_INIT         (0b10000101)
#define P1_DISABLE      (0b10000110)
#define CHECK_24V_SL1   (0b10001001)
#define CHECK_24V_SL2   (0b10001010)
#define CHECK_24V_SL3   (0b10001011)
#define READ_STATUS_SL1 (0b10010001)
#define READ_STATUS_SL2 (0b10010010)
#define READ_STATUS_SL3 (0b10010011)
#define EMS_CHAIN1      (0b11000000)
#define EMS_CHAIN2      (0b11000001)
#define EMS_CHAIN3      (0b11000010)
#define EMS_CHAIN4      (0b11000011)
#define EMS_CHAIN5      (0b11000100)
#define EMS_CHAIN6      (0b11000101)
#define EMS_CHAIN7      (0b11000110)
#define EMS_CHAIN8      (0b11000111)
#define EMS_CHAIN9      (0b11001000)
#define EMS_CHAIN10     (0b11001001)
#define EMS_CHAIN11     (0b11001010)
#define EMS_CHAIN12     (0b11001011)
#define EMS_CHAIN13     (0b11001100)
#define EMS_CHAIN14     (0b11001101)
#define EMS_CHAIN15     (0b11001110)
#define EMS_CHAIN16     (0b11001111)
#define DFS_CHAIN1      (0b11010000)
#define DFS_CHAIN2      (0b11010001)
#define DFS_CHAIN3      (0b11010010)
#define DFS_CHAIN4      (0b11010011)
#define DFS_CHAIN5      (0b11010100)
#define DFS_CHAIN6      (0b11010101)
#define DFS_CHAIN7      (0b11010110)
#define DFS_CHAIN8      (0b11010111)
#define DFS_CHAIN9      (0b11011000)
#define DFS_CHAIN10     (0b11011001)
#define DFS_CHAIN11     (0b11011010)
#define DFS_CHAIN12     (0b11011011)
#define DFS_CHAIN13     (0b11011100)
#define DFS_CHAIN14     (0b11011101)
#define DFS_CHAIN15     (0b11011110)
#define DFS_CHAIN16     (0b11011111)
