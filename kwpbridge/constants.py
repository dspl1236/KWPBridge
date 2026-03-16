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

# ── KWP2000 / ISO 14230 service identifiers ──────────────────────────────────

# Service request IDs
KWP2000_START_SESSION       = 0x10   # startDiagnosticSession
KWP2000_STOP_SESSION        = 0x20   # stopDiagnosticSession
KWP2000_ECU_RESET           = 0x11   # ecuReset
KWP2000_SECURITY_ACCESS     = 0x27   # securityAccess (seed/key)
KWP2000_TESTER_PRESENT      = 0x3E   # testerPresent (keep-alive)
KWP2000_READ_DATA_LOCAL     = 0x21   # readDataByLocalIdentifier (measuring blocks)
KWP2000_READ_DTC_STATUS     = 0x18   # readDTCByStatus
KWP2000_CLEAR_DTC           = 0x14   # clearDiagnosticInfo
KWP2000_READ_ECU_ID         = 0x1A   # readEcuIdentification
KWP2000_READ_DATA_PID       = 0x22   # readDataByCommonIdentifier

# Session types (used with 0x10)
KWP2000_SESSION_DEFAULT     = 0x89   # ecuDefault — ME7 uses this, not 0x01
KWP2000_SESSION_EXTENDED    = 0x86   # extendedDiagnostic

# Positive response offset (response SID = request SID + 0x40)
KWP2000_POS_OFFSET          = 0x40

# Negative response service ID
KWP2000_NEG_RESPONSE        = 0x7F

# KWP2000 tester/ECU addresses
KWP2000_TESTER_ADDR         = 0xF1
KWP2000_ECU_ADDR            = 0x01   # engine ECU (same as KWP1281)

# Header format byte — ISO 14230
# 0x80 = physical addressing, no length in header
# 0xC0 = physical addressing, length in header
KWP2000_FMT_PHYSICAL        = 0x80
KWP2000_FMT_PHYSICAL_LEN    = 0xC0

# Fast init timing (seconds)
KWP2000_FAST_INIT_LOW_MS    = 0.025   # 25ms K-line low
KWP2000_FAST_INIT_HIGH_MS   = 0.025   # 25ms K-line high
KWP2000_FAST_INIT_WAIT_MS   = 0.300   # 300ms wait after init before first request

# Keep-alive interval
KWP2000_KEEPALIVE_S         = 1.5    # send testerPresent every 1.5s

# ME7 ECU local identifier for measuring blocks
# 0x21 [local_id] where local_id = block number (1-250)
KWP2000_LOCAL_ID_MEAS       = 0x00   # base — add block number

# ECU identification local IDs
KWP2000_ID_ECU_PARTNUM      = 0x9B   # ECU part number string
KWP2000_ID_ECU_SOFTNUM      = 0x9C   # software version number
