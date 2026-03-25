"""
KWP2000 / ISO 14230 protocol implementation for Bosch ME7.x ECUs.

Handles the serial communication layer:
  - Fast init (K-line timing trick via DTR/RTS or break signal)
  - KWP2000 header framing (fmt + tgt + src + len + data + checksum)
  - 0x10 startDiagnosticSession (ME7 uses ecuDefault = 0x89)
  - 0x3E testerPresent keep-alive (background thread, every 1.5s)
  - 0x21 readDataByLocalIdentifier (measuring blocks 001-250)
  - 0x18 readDTCByStatus / 0x14 clearDiagnosticInfo
  - 0x1A readEcuIdentification (part number, SW version)

ME7 measuring block cell encoding (identical to KWP1281):
  Each response to 0x21 contains N cells of 3 bytes each:
    [formula_byte][value_high][value_low]
  Use formula.decode_cell(formula, a, b) — same table as KWP1281.

Cable notes:
  - Ross-Tech HEX+CAN / HEX+KKL: handles fast init in firmware.
    Just open 10400 baud and begin; cable asserts K-line timing.
  - FTDI / CH340 dumb cables: must bit-bang the fast init via
    serial break signal or set baud=5 + send byte 0x00 trick.
    We use setBreak(True) for 25ms then setBreak(False) as the
    cleanest portable approach.

References:
  - ISO 14230-3 (KWP2000 application layer)
  - NefMoto forums ME7 protocol documentation
  - VCDS and VagCom source community research
  - OpenDiag project (GPL) for timing constants
"""

import time
import threading
import logging
from typing import Optional

import serial

from .constants import (
    KWP_BAUD,
    BYTE_TIMEOUT,
    CABLE_ROSS_TECH, CABLE_AUTO,
    ADDR_ENGINE,
    KWP2000_START_SESSION, KWP2000_STOP_SESSION,
    KWP2000_TESTER_PRESENT, KWP2000_READ_DATA_LOCAL,
    KWP2000_READ_DTC_STATUS, KWP2000_CLEAR_DTC,
    KWP2000_READ_ECU_ID,
    KWP2000_SESSION_DEFAULT,
    KWP2000_POS_OFFSET, KWP2000_NEG_RESPONSE,
    KWP2000_TESTER_ADDR, KWP2000_ECU_ADDR,
    KWP2000_FMT_PHYSICAL,
    KWP2000_FAST_INIT_LOW_MS, KWP2000_FAST_INIT_HIGH_MS,
    KWP2000_FAST_INIT_WAIT_MS, KWP2000_KEEPALIVE_S,
    KWP2000_ID_ECU_PARTNUM,
)
from .models  import MeasuringBlock, MeasuringCell, FaultCode, ECUIdentification
from .formula import decode_cell
from .ecu_defs import find_ecu_def, get_cell_label, get_fault_description

log = logging.getLogger(__name__)


class KWP2000Error(Exception):
    """KWP2000 communication or protocol error."""


class NegativeResponseError(KWP2000Error):
    """ECU returned a negative response (0x7F)."""
    def __init__(self, service_id: int, nrc: int):
        self.service_id = service_id
        self.nrc        = nrc
        NRC_NAMES = {
            0x10: "generalReject",
            0x11: "serviceNotSupported",
            0x12: "subFunctionNotSupported",
            0x21: "busyRepeatRequest",
            0x22: "conditionsNotCorrect",
            0x31: "requestOutOfRange",
            0x33: "securityAccessDenied",
            0x35: "invalidKey",
            0x36: "exceededNumberOfAttempts",
            0x37: "requiredTimeDelayNotExpired",
        }
        name = NRC_NAMES.get(nrc, f"0x{nrc:02X}")
        super().__init__(
            f"Negative response to service 0x{service_id:02X}: {name}")


class KWP2000:
    """
    KWP2000 / ISO 14230 protocol handler for Bosch ME7.x ECUs.

    Usage:
        kwp = KWP2000(port="COM3", cable_type=CABLE_ROSS_TECH)
        kwp.connect()
        block = kwp.read_group(1)
        faults = kwp.read_faults()
        kwp.disconnect()
    """

    def __init__(
        self,
        port:       str,
        cable_type: str   = CABLE_AUTO,
        baud:       int   = KWP_BAUD,
        timeout:    float = BYTE_TIMEOUT,
    ):
        self.port       = port
        self.cable_type = cable_type
        self.baud       = baud
        self.timeout    = timeout

        self._ser:        serial.Serial | None = None
        self._ecu_def                         = None
        self._ecu_id:     ECUIdentification | None = None
        self._connected:  bool  = False
        self._session_ok: bool  = False
        self._lock        = threading.Lock()

        # Keep-alive thread
        self._keepalive_thread: threading.Thread | None = None
        self._keepalive_stop    = threading.Event()

    # ── Public API ────────────────────────────────────────────────────────────

    def connect(self, address: int = ADDR_ENGINE) -> ECUIdentification:
        """
        Initialise K-line, start diagnostic session, identify ECU.

        Returns ECUIdentification with part number and component string.
        Raises KWP2000Error on failure.
        """
        self._ser = serial.Serial(
            port=self.port, baudrate=self.baud,
            bytesize=8, parity='N', stopbits=1,
            timeout=self.timeout,
        )

        self._fast_init()
        self._start_session()
        ecu_id = self._read_ecu_id()
        self._ecu_id = ecu_id
        self._ecu_def = find_ecu_def(ecu_id.part_number)
        self._connected  = True
        self._session_ok = True

        self._keepalive_stop.clear()
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop,
            daemon=True,
            name="kwp2000-keepalive",
        )
        self._keepalive_thread.start()
        log.info(f"KWP2000 connected: {ecu_id.part_number} — {ecu_id.component}")
        return ecu_id

    def disconnect(self):
        """End diagnostic session and close serial port."""
        self._keepalive_stop.set()
        if self._keepalive_thread:
            self._keepalive_thread.join(timeout=3)

        if self._ser and self._ser.is_open:
            try:
                self._send_request(KWP2000_STOP_SESSION)
            except Exception:
                pass
            try:
                self._ser.close()
            except Exception:
                pass

        self._connected  = False
        self._session_ok = False
        log.info("KWP2000 disconnected")

    @property
    def connected(self) -> bool:
        return self._connected and self._session_ok

    @property
    def ecu_id(self) -> Optional[ECUIdentification]:
        return self._ecu_id

    def read_group(self, group: int) -> MeasuringBlock:
        """
        Read a measuring block by group number (1-250).

        Returns a MeasuringBlock with decoded cells.
        """
        if not self.connected:
            raise KWP2000Error("Not connected")
        if not (1 <= group <= 250):
            raise KWP2000Error(f"Group number out of range: {group}")

        with self._lock:
            response = self._send_request(
                KWP2000_READ_DATA_LOCAL, data=[group])

        # Response: [0x61][group][n_cells × 3 bytes each]
        # Positive response SID = 0x21 + 0x40 = 0x61
        if not response or response[0] != (KWP2000_READ_DATA_LOCAL + KWP2000_POS_OFFSET):
            raise KWP2000Error(f"Unexpected response to group {group}: {response!r}")

        raw_cells = response[2:]   # skip 0x61 and echo of group byte
        cells = []
        for i in range(0, len(raw_cells) - 2, 3):
            formula = raw_cells[i]
            a       = raw_cells[i + 1]
            b       = raw_cells[i + 2]
            cell_idx = (i // 3) + 1

            value, unit, display = decode_cell(formula, a, b)
            label = (get_cell_label(self._ecu_def, group, cell_idx)
                     if self._ecu_def else f"Cell {cell_idx}")

            cells.append(MeasuringCell(
                index   = cell_idx,
                formula = formula,
                raw_a   = a,
                raw_b   = b,
                value   = value,
                unit    = unit,
                display = display,
                label   = label,
            ))

        return MeasuringBlock(group=group, cells=cells)

    def read_faults(self) -> list[FaultCode]:
        """Read stored fault codes (DTCs)."""
        if not self.connected:
            raise KWP2000Error("Not connected")

        with self._lock:
            # 0x18 0x82 0xFF 0xFF 0xFF — readDTCByStatus, all statuses
            response = self._send_request(
                KWP2000_READ_DTC_STATUS,
                data=[0x82, 0xFF, 0xFF, 0xFF],
            )

        if not response:
            return []
        # Response: [0x58][n_dtcs][dtc_high][dtc_low][status] × n_dtcs
        if response[0] != (KWP2000_READ_DTC_STATUS + KWP2000_POS_OFFSET):
            return []

        faults = []
        count  = response[1] if len(response) > 1 else 0
        for i in range(count):
            base = 2 + i * 3
            if base + 2 >= len(response):
                break
            dtc_hi  = response[base]
            dtc_lo  = response[base + 1]
            status  = response[base + 2]
            code    = (dtc_hi << 8) | dtc_lo
            desc    = (get_fault_description(self._ecu_def, code)
                       if self._ecu_def else f"DTC {code:04X}")
            faults.append(FaultCode(
                code=code, description=desc,
                status=status,
            ))

        return faults

    def clear_faults(self) -> bool:
        """Clear all stored fault codes."""
        if not self.connected:
            raise KWP2000Error("Not connected")
        with self._lock:
            response = self._send_request(
                KWP2000_CLEAR_DTC, data=[0xFF, 0xFF])
        return bool(response and
                    response[0] == (KWP2000_CLEAR_DTC + KWP2000_POS_OFFSET))

    # ── Connection internals ──────────────────────────────────────────────────

    def _fast_init(self):
        """
        Perform ISO 14230 fast init on the K-line.

        Ross-Tech genuine cable: handles this in firmware — just open
        the port and proceed. We still wait briefly for sync.

        FTDI/CH340 dumb cable: use serial break signal to pull K-line
        low for 25ms, then release for 25ms, then proceed at 10400 baud.
        The break signal is a clean portable way to generate the timing.
        """
        if not self._ser:
            raise KWP2000Error("Serial port not open")

        if self.cable_type == CABLE_ROSS_TECH:
            # Ross-Tech cable handles fast init in firmware
            # Just wait a moment for any prior session to clear
            time.sleep(0.050)
            return

        # FTDI/CH340 or AUTO: bit-bang fast init via break signal
        # setBreak(True) pulls TX/K-line low; setBreak(False) releases it
        log.debug("Fast init: K-line low 25ms")
        self._ser.setBreak(True)
        time.sleep(KWP2000_FAST_INIT_LOW_MS)

        log.debug("Fast init: K-line high 25ms")
        self._ser.setBreak(False)
        time.sleep(KWP2000_FAST_INIT_HIGH_MS)

        # Wait for ECU to respond
        time.sleep(KWP2000_FAST_INIT_WAIT_MS)
        self._ser.reset_input_buffer()
        log.debug("Fast init complete")

    def _start_session(self):
        """Send startDiagnosticSession (0x10 0x89) and verify response."""
        response = self._send_request(
            KWP2000_START_SESSION, data=[KWP2000_SESSION_DEFAULT])
        expected = KWP2000_START_SESSION + KWP2000_POS_OFFSET  # 0x50
        if not response or response[0] != expected:
            raise KWP2000Error(
                f"Session start failed. Response: {response!r}")
        log.debug("Diagnostic session started (ecuDefault 0x89)")

    def _read_ecu_id(self) -> ECUIdentification:
        """Read ECU identification string (local ID 0x9B)."""
        try:
            response = self._send_request(
                KWP2000_READ_ECU_ID, data=[KWP2000_ID_ECU_PARTNUM])
            # Response: [0x5A][0x9B][ASCII part number bytes...]
            if response and len(response) > 2:
                pn_bytes = bytes(response[2:]).decode('ascii', errors='replace').strip()
                pn_clean = pn_bytes.replace('\x00', '').strip()
            else:
                pn_clean = "UNKNOWN"
        except Exception as e:
            log.debug(f"ECU ID read failed: {e}")
            pn_clean = "UNKNOWN"

        ecu_def = find_ecu_def(pn_clean)
        component = ecu_def.name if ecu_def else "ME7.5 Engine ECU"

        return ECUIdentification(
            part_number=pn_clean,
            component=component,
            coding="",
            wsc="",
        )

    # ── Frame construction and I/O ────────────────────────────────────────────

    def _build_frame(self, service_id: int, data: list[int] = None) -> bytes:
        """
        Build a KWP2000 ISO 14230 request frame.

        Format: [fmt][tgt][src][len][sid][data...][checksum]
          fmt = 0x80 (physical addressing, no length in fmt byte)
          tgt = 0xF1 (tester)
          src = 0x01 (engine ECU)
          len = number of payload bytes (sid + data)
          checksum = sum of all bytes mod 256
        """
        payload = [service_id] + (data or [])
        # ISO 14230: [fmt][target][source][len][payload...]
        # Tester→ECU: target=ECU(0x01), source=Tester(0xF1)
        frame   = [KWP2000_FMT_PHYSICAL, KWP2000_ECU_ADDR,
                   KWP2000_TESTER_ADDR, len(payload)] + payload
        checksum = sum(frame) & 0xFF
        return bytes(frame + [checksum])

    def _send_request(self, service_id: int,
                      data: list[int] = None) -> list[int]:
        """
        Send a KWP2000 request and receive the response.

        Returns the response payload (after the header), or raises
        KWP2000Error / NegativeResponseError.
        """
        if not self._ser or not self._ser.is_open:
            raise KWP2000Error("Serial port closed")

        frame = self._build_frame(service_id, data)
        self._ser.reset_input_buffer()
        self._ser.write(frame)
        log.debug(f"TX: {frame.hex(' ')}")

        return self._recv_response(service_id)

    def _recv_response(self, request_sid: int) -> list[int]:
        """
        Read and validate a KWP2000 response frame.

        Returns the payload (SID + data bytes, no header/checksum).
        """
        # Read header: fmt + tgt + src + len
        header = self._ser.read(4)
        if len(header) < 4:
            raise KWP2000Error(
                f"Timeout reading response header (got {len(header)} bytes)")

        fmt, tgt, src, length = header
        log.debug(f"RX header: fmt=0x{fmt:02X} tgt=0x{tgt:02X} "
                  f"src=0x{src:02X} len={length}")

        # Read payload + checksum
        body = self._ser.read(length + 1)   # +1 for checksum
        if len(body) < length + 1:
            raise KWP2000Error(
                f"Timeout reading response body (expected {length+1}, got {len(body)})")

        payload  = list(body[:length])
        checksum = body[length]
        expected_cs = (sum(header) + sum(payload)) & 0xFF

        if checksum != expected_cs:
            raise KWP2000Error(
                f"Checksum mismatch: got 0x{checksum:02X}, "
                f"expected 0x{expected_cs:02X}")

        log.debug(f"RX payload: {bytes(payload).hex(' ')}")

        # Check for negative response
        if payload and payload[0] == KWP2000_NEG_RESPONSE:
            sid  = payload[1] if len(payload) > 1 else 0
            nrc  = payload[2] if len(payload) > 2 else 0
            raise NegativeResponseError(sid, nrc)

        return payload

    # ── Keep-alive loop ───────────────────────────────────────────────────────

    def _keepalive_loop(self):
        """Background thread: send testerPresent every KWP2000_KEEPALIVE_S."""
        while not self._keepalive_stop.is_set():
            self._keepalive_stop.wait(KWP2000_KEEPALIVE_S)
            if self._keepalive_stop.is_set():
                break
            if not self._connected or not self._ser or not self._ser.is_open:
                break
            try:
                with self._lock:
                    self._send_request(KWP2000_TESTER_PRESENT)
                log.debug("KWP2000 keep-alive sent")
            except Exception as e:
                log.warning(f"Keep-alive failed: {e}")
                self._session_ok = False
                # Attempt session restart
                try:
                    with self._lock:
                        self._start_session()
                    self._session_ok = True
                    log.info("KWP2000 session restarted after keep-alive failure")
                except Exception as e2:
                    log.error(f"Session restart failed: {e2}")
                    self._connected = False
                    break
