"""
KWPBridge — KWP1281 / KWP2000 diagnostic bridge for VAG vehicles.

Supports KWP1281 (pre-2002: 7A, AAH, M2.3.2, Digifant) and
KWP2000/ISO14230 (ME7.x, MED7.x, post-2001 VAG). Protocol is
auto-detected by default — tries KWP1281 then KWP2000.

Architecture:
  KWPBridge process  ←→  serial (K-line)  ←→  ECU
       ↓
  TCP server :50266
       ↓
  HachiROM / UrROM / digital dash / logger (any number of clients)
"""

__version__ = "0.9.4"
__all__ = [
    "KWP1281",
    "KWP2000",
    "KWPServer",
    "MeasuringBlock",
    "FaultCode",
    "ECU_7A_LATE",
    "ECU_7A_EARLY",
    "ECU_AAH",
    "DEFAULT_PORT",
    "FORMULA",
    "detect_protocol",
    "PROTO_AUTO",
    "PROTO_KWP1281",
    "PROTO_KWP2000",
]

from .protocol         import KWP1281
from .kwp2000          import KWP2000
from .server           import KWPServer
from .models           import MeasuringBlock, FaultCode
from .ecu_defs         import ECU_7A_LATE, ECU_7A_EARLY, ECU_AAH
from .formula          import FORMULA
from .constants        import DEFAULT_PORT
from .protocol_detect  import detect_protocol
