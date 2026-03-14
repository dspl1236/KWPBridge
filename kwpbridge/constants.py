"""
KWPBridge constants.
"""

# TCP port for IPC — derived from ECU part number 266
DEFAULT_PORT = 50266

# K-line baud rate for KWP1281
KWP_BAUD = 10400

# ECU module addresses (KWP1281 logical IDs)
ADDR_ENGINE      = 0x01
ADDR_GEARBOX     = 0x02
ADDR_ABS         = 0x03
ADDR_AIRBAG      = 0x15
ADDR_INSTRUMENTS = 0x17
ADDR_IMMOBILISER = 0x25

# KWP1281 block types
BLK_ACK          = 0x09   # acknowledge
BLK_NACK         = 0x0A   # negative acknowledge  
BLK_READ_GROUP   = 0x29   # read measuring block
BLK_MEAS_VALUE   = 0xE7   # measuring value response
BLK_READ_DTC     = 0x07   # read fault codes
BLK_DTC_RESP     = 0xFC   # fault code response
BLK_CLEAR_DTC    = 0x05   # clear fault codes
BLK_BASIC_SET    = 0x28   # basic setting
BLK_BASIC_RESP   = 0xF4   # basic setting response
BLK_END          = 0x06   # end communication
BLK_ID           = 0xF6   # identification string

# Timing constants (seconds)
INTER_BYTE_DELAY  = 0.001   # 1ms between bytes within a block
INTER_BLOCK_DELAY = 0.010   # 10ms between blocks
BYTE_TIMEOUT      = 1.0     # timeout waiting for a byte
INIT_TIMEOUT      = 2.0     # timeout during slow init

# IPC update interval
IPC_UPDATE_HZ = 10          # target broadcast rate (actual may be lower)

# Cable types
CABLE_ROSS_TECH  = "ross_tech"   # genuine Ross-Tech HEX+KKL — handles 5-baud init
CABLE_FTDI       = "ftdi"        # FTDI-based dumb KKL cable
CABLE_CH340      = "ch340"       # CH340-based dumb KKL cable
CABLE_AUTO       = "auto"        # detect from USB VID/PID
