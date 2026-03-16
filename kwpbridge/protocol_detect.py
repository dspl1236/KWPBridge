"""
kwpbridge/protocol_detect.py — Automatic ECU protocol detection.

VCDS-style protocol negotiation: try protocols from oldest to newest,
fall back on failure, report what worked.

Detection order (matching VCDS behaviour):
  1. KWP1281  — 5-baud slow init, 10400 baud
                Most pre-2002 VAG ECUs (7A, AAH, M2.3.2, Digifant, Motronic 1.x/2.x)
  2. KWP2000  — ISO 14230 fast init, 10400 baud
                Bosch ME7.x, MED7.x, Siemens Simos, post-2001 VAG

Each step gets `max_attempts` tries before moving on. On success the
detected protocol name and a live connection object are returned so
the server can start polling immediately without reconnecting.

Usage:
    from kwpbridge.protocol_detect import detect_protocol, PROTO_KWP1281, PROTO_KWP2000

    result = detect_protocol(port="COM3", cable_type=CABLE_AUTO)
    if result.success:
        print(f"Detected {result.protocol}: {result.ecu_id.part_number}")
        # result.connection is ready to use (already connected)
    else:
        print(f"No ECU found: {result.errors}")

    # Or force a specific protocol:
    result = detect_protocol(port="COM3", force_protocol=PROTO_KWP2000)
"""

import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

PROTO_AUTO    = "auto"
PROTO_KWP1281 = "kwp1281"
PROTO_KWP2000 = "kwp2000"

PROTOCOL_ORDER = [PROTO_KWP1281, PROTO_KWP2000]

# How long to wait between retries and protocol switches
_RETRY_DELAY_S   = 1.0
_PROTOCOL_GAP_S  = 2.0   # extra settle time before trying next protocol


@dataclass
class DetectResult:
    """Result of a protocol detection attempt."""
    success:      bool
    protocol:     str                     = ""        # PROTO_* constant
    connection:   object                  = None      # KWP1281 or KWP2000 instance
    ecu_id:       object                  = None      # ECUIdentification
    errors:       dict[str, list[str]]    = field(default_factory=dict)
    # errors[proto] = [error messages tried]
    attempts:     dict[str, int]          = field(default_factory=dict)
    # attempts[proto] = number of attempts made

    @property
    def tried_protocols(self) -> list[str]:
        return list(self.attempts.keys())

    def summary(self) -> str:
        if self.success:
            pn = self.ecu_id.part_number if self.ecu_id else "?"
            return f"Connected via {self.protocol}  [{pn}]"
        parts = []
        for proto, msgs in self.errors.items():
            n = self.attempts.get(proto, 0)
            last = msgs[-1] if msgs else "failed"
            parts.append(f"{proto} ×{n}: {last}")
        return "No ECU found — " + "  |  ".join(parts)


class ProtocolDetector:
    """
    Tries KWP1281 then KWP2000 (or a forced protocol) on a serial port.

    Parameters
    ----------
    port            : serial port string (COM3, /dev/ttyUSB0, etc.)
    cable_type      : CABLE_AUTO / CABLE_ROSS_TECH / CABLE_FTDI / CABLE_CH340
    force_protocol  : PROTO_AUTO (try all) / PROTO_KWP1281 / PROTO_KWP2000
    ecu_address     : ECU K-line address (default 0x01 = engine)
    max_attempts    : retries per protocol before moving to next (default 2)
    on_status       : optional callback(str) for status updates to UI
    """

    def __init__(
        self,
        port:           str,
        cable_type:     str   = "auto",
        force_protocol: str   = PROTO_AUTO,
        ecu_address:    int   = 0x01,
        max_attempts:   int   = 2,
        on_status:      object = None,
    ):
        self.port           = port
        self.cable_type     = cable_type
        self.force_protocol = force_protocol
        self.ecu_address    = ecu_address
        self.max_attempts   = max_attempts
        self._on_status     = on_status

    def run(self) -> DetectResult:
        """
        Run protocol detection and return a DetectResult.

        If force_protocol is PROTO_AUTO, tries PROTOCOL_ORDER in sequence.
        If force_protocol is set, tries only that protocol.
        """
        if self.force_protocol in (PROTO_KWP1281, PROTO_KWP2000):
            protos = [self.force_protocol]
        else:
            protos = list(PROTOCOL_ORDER)

        result = DetectResult(success=False)

        for i, proto in enumerate(protos):
            if i > 0:
                # Give K-line time to settle between protocol attempts
                self._status(f"Waiting {_PROTOCOL_GAP_S:.0f}s before trying {proto}…")
                time.sleep(_PROTOCOL_GAP_S)

            self._status(f"Trying {proto}…")
            result.attempts[proto] = 0
            result.errors[proto]   = []

            for attempt in range(1, self.max_attempts + 1):
                result.attempts[proto] = attempt
                self._status(
                    f"  {proto}  attempt {attempt}/{self.max_attempts}…")
                try:
                    conn, ecu_id = self._try_protocol(proto)
                    result.success    = True
                    result.protocol   = proto
                    result.connection = conn
                    result.ecu_id     = ecu_id
                    self._status(
                        f"✓ {proto}  {ecu_id.part_number}  {ecu_id.component}")
                    return result

                except Exception as e:
                    msg = str(e)
                    result.errors[proto].append(msg)
                    log.debug(f"  {proto} attempt {attempt} failed: {msg}")
                    self._status(f"  ✗ {proto} attempt {attempt}: {msg}")
                    if attempt < self.max_attempts:
                        time.sleep(_RETRY_DELAY_S)

        self._status(f"No ECU found after trying: {protos}")
        return result

    def _try_protocol(self, proto: str):
        """
        Attempt a single connection with the given protocol.
        Returns (connection_object, ecu_id) on success, raises on failure.
        """
        if proto == PROTO_KWP1281:
            from .protocol import KWP1281
            kwp = KWP1281(port=self.port, cable_type=self.cable_type)
            ecu_id = kwp.connect(self.ecu_address)
            return kwp, ecu_id

        elif proto == PROTO_KWP2000:
            from .kwp2000 import KWP2000
            kwp = KWP2000(
                port=self.port,
                cable_type=self.cable_type,
            )
            ecu_id = kwp.connect(self.ecu_address)
            return kwp, ecu_id

        else:
            raise ValueError(f"Unknown protocol: {proto!r}")

    def _status(self, msg: str):
        log.info(msg)
        if self._on_status:
            try:
                self._on_status(msg)
            except Exception:
                pass


def detect_protocol(
    port:           str,
    cable_type:     str  = "auto",
    force_protocol: str  = PROTO_AUTO,
    ecu_address:    int  = 0x01,
    max_attempts:   int  = 2,
    on_status:      object = None,
) -> DetectResult:
    """
    Convenience wrapper around ProtocolDetector.

    Returns a DetectResult. On success, result.connection is a live
    KWP1281 or KWP2000 object ready for read_group() calls.
    """
    return ProtocolDetector(
        port           = port,
        cable_type     = cable_type,
        force_protocol = force_protocol,
        ecu_address    = ecu_address,
        max_attempts   = max_attempts,
        on_status      = on_status,
    ).run()
