"""
KWPBridge — KWP1281 / K-Line diagnostic bridge for VAG vehicles.

Connects to a vehicle ECU via a KKL or Ross-Tech cable, reads measuring
blocks, faults, and basic settings, then broadcasts live data over a
local TCP socket so other tools (HachiROM, digital dash, loggers) can
consume it without owning the serial port themselves.

Architecture:
  KWPBridge process  ←→  serial (K-line)  ←→  ECU
       ↓
  TCP server :50266
       ↓
  HachiROM / digital dash / logger (any number of clients)

Detection: client apps connect to localhost:50266 — if the connection
succeeds, KWPBridge is running. If refused, feature is unavailable.
"""

__version__ = "0.7.0"
__all__ = [
    "KWP1281",
    "KWPServer",
    "MeasuringBlock",
    "FaultCode",
    "ECU_7A_LATE",
    "ECU_7A_EARLY",
    "ECU_AAH",
    "DEFAULT_PORT",
    "FORMULA",
]

from .protocol   import KWP1281
from .server     import KWPServer
from .models     import MeasuringBlock, FaultCode
from .ecu_defs   import ECU_7A_LATE, ECU_7A_EARLY, ECU_AAH
from .formula    import FORMULA
from .lbl_parser import LBLRegistry, LBLFile, parse_lbl, decode_with_lbl
from .constants  import DEFAULT_PORT
