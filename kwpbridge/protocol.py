"""
KWP1281 protocol implementation.

Handles the serial communication layer:
  - Connection / slow init (or skip for Ross-Tech cable)
  - Block send / receive with checksums
  - High-level commands: read group, read faults, clear faults, basic setting

Cable notes:
  - Ross-Tech genuine cable:  handles 5-baud init in hardware.
    Open COM port at 10400 baud and send directly.
  - FTDI / CH340 dumb cables: require bit-banging the 5-baud init.
    We use a timing trick: set baud=5, write address byte, restore baud.
    This works on FTDI chips. CH340 may need a different approach.

References:
  - KWP1281 community docs: https://github.com/mnaberez/vwradio
  - NefMoto measuring block formulas
  - Ross-Tech VCDS documentation
"""

import time
import threading
import logging
from typing import Callable

import serial
import serial.tools.list_ports

from .constants  import (
    KWP_BAUD, INTER_BYTE_DELAY, INTER_BLOCK_DELAY,
    BYTE_TIMEOUT, INIT_TIMEOUT,
    BLK_ACK, BLK_NACK, BLK_READ_GROUP, BLK_MEAS_VALUE,
    BLK_READ_DTC, BLK_DTC_RESP, BLK_CLEAR_DTC,
    BLK_BASIC_SET, BLK_BASIC_RESP, BLK_END, BLK_ID,
    CABLE_ROSS_TECH, CABLE_FTDI, CABLE_CH340, CABLE_AUTO,
    ADDR_ENGINE,
)
from .models     import MeasuringBlock, MeasuringCell, FaultCode, ECUIdentification
from .formula    import decode_cell
from .ecu_defs   import find_ecu_def, get_cell_label, get_fault_description

log = logging.getLogger(__name__)


class KWPError(Exception):
    """KWP1281 communication error."""


class KWP1281:
    """
    KWP1281 protocol handler.

    Usage:
        kwp = KWP1281(port="COM3", cable_type=CABLE_ROSS_TECH)
        kwp.connect(address=ADDR_ENGINE)
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
        self._ser:      serial.Serial | None = None
        self._counter:  int  = 0   # block counter, increments each block
        self._ecu_def            = None
        self._ecu_id:   ECUIdentification | None = None
        self._connected: bool    = False
        self._lock       = threading.Lock()

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, address: int = ADDR_ENGINE) -> ECUIdentification:
        """
        Connect to an ECU module.

        For Ross-Tech cables: opens port and sends normally (cable handles init).
        For dumb FTDI/CH340 cables: performs software 5-baud init.

        Returns ECUIdentification on success.
        Raises KWPError on failure.
        """
        with self._lock:
            if self._connected:
                self.disconnect()

            cable = self._detect_cable() if self.cable_type == CABLE_AUTO \
                    else self.cable_type

            log.info(f"Connecting to ECU 0x{address:02X} on {self.port} "
                     f"(cable={cable}, baud={self.baud})")

            try:
                if cable == CABLE_ROSS_TECH:
                    self._connect_ross_tech(address)
                else:
                    self._connect_dumb_cable(address, cable)

                self._ecu_id = self._read_identification()
                self._connected = True
                log.info(f"Connected: {self._ecu_id.part_number} — "
                         f"{self._ecu_id.component}")

                # Look up ECU definition
                self._ecu_def = find_ecu_def(self._ecu_id.part_number)

                return self._ecu_id

            except Exception as e:
                self._cleanup()
                raise KWPError(f"Connection failed: {e}") from e

    def _connect_ross_tech(self, address: int):
        """
        Open serial port for Ross-Tech cable.
        The cable handles 5-baud init internally — we just open and wait
        for the sync byte (0x55) then the two keyword bytes.
        """
        self._ser = serial.Serial(
            port=self.port, baudrate=self.baud,
            bytesize=8, parity=serial.PARITY_NONE,
            stopbits=1, timeout=self.timeout)

        # Some Ross-Tech cables need the port to be opened then the ECU
        # address sent — the cable firmware handles the 5-baud timing
        time.sleep(0.300)
        self._ser.reset_input_buffer()

        # Send ECU address byte (the cable converts this to 5-baud on K-line)
        self._ser.write(bytes([address]))
        self._ser.flush()

        # Wait for sync byte 0x55
        sync = self._read_byte_timeout(INIT_TIMEOUT)
        if sync != 0x55:
            raise KWPError(f"Expected sync 0x55, got 0x{sync:02X}")

        # Read two keyword bytes (should be 0x01 0x8A for KWP1281)
        kw1 = self._read_byte_timeout(INIT_TIMEOUT)
        kw2 = self._read_byte_timeout(INIT_TIMEOUT)
        log.debug(f"Keywords: 0x{kw1:02X} 0x{kw2:02X}")

        # Send complement of kw2
        time.sleep(INTER_BYTE_DELAY)
        self._ser.write(bytes([~kw2 & 0xFF]))
        self._ser.flush()

        self._counter = 0

    def _connect_dumb_cable(self, address: int, cable_type: str):
        """
        5-baud software init for dumb KKL cables (FTDI / CH340).

        Bit-bangs the address byte at 5 baud by toggling baud rate:
        1 bit = 200ms. Works reliably on FTDI; CH340 may vary.
        """
        log.info("Performing 5-baud software init (dumb cable)")

        # Open at 10400 first to configure the port
        self._ser = serial.Serial(
            port=self.port, baudrate=10400,
            bytesize=8, parity=serial.PARITY_NONE,
            stopbits=1, timeout=self.timeout)
        self._ser.close()

        # Re-open at 5 baud for the address byte
        # Not all USB-serial adapters support 5 baud — FTDI does via custom divisor
        try:
            self._ser = serial.Serial(
                port=self.port, baudrate=5,
                bytesize=8, parity=serial.PARITY_NONE,
                stopbits=1, timeout=INIT_TIMEOUT)
            self._ser.write(bytes([address]))
            self._ser.flush()
            # Wait for the full 10 bits at 5 baud = 2 seconds
            time.sleep(2.2)
        except Exception:
            # If 5 baud isn't supported, fall back to bit-bang via break
            log.warning("5-baud not supported on this adapter — trying break method")
            self._ser.close()
            self._ser = serial.Serial(
                port=self.port, baudrate=10400,
                bytesize=8, parity=serial.PARITY_NONE,
                stopbits=1, timeout=self.timeout)
            self._slow_init_break(address)

        # Switch to 10400 baud for normal comms
        self._ser.close()
        self._ser = serial.Serial(
            port=self.port, baudrate=self.baud,
            bytesize=8, parity=serial.PARITY_NONE,
            stopbits=1, timeout=self.timeout)

        # Same sync/keyword handshake as Ross-Tech
        sync = self._read_byte_timeout(INIT_TIMEOUT)
        if sync != 0x55:
            raise KWPError(f"Expected sync 0x55, got 0x{sync:02X} "
                           f"(dumb cable 5-baud init may have failed)")
        kw1 = self._read_byte_timeout(INIT_TIMEOUT)
        kw2 = self._read_byte_timeout(INIT_TIMEOUT)
        log.debug(f"Keywords: 0x{kw1:02X} 0x{kw2:02X}")
        time.sleep(INTER_BYTE_DELAY)
        self._ser.write(bytes([~kw2 & 0xFF]))
        self._ser.flush()
        self._counter = 0

    def _slow_init_break(self, address: int):
        """
        Alternative 5-baud init using serial break condition.
        Works on some CH340 adapters where baud=5 fails.
        """
        BIT_TIME = 0.200  # 200ms per bit at 5 baud
        # Start bit (low = break)
        self._ser.break_condition = True
        time.sleep(BIT_TIME)
        # Data bits LSB first
        for bit in range(8):
            if address & (1 << bit):
                self._ser.break_condition = False  # high = mark
            else:
                self._ser.break_condition = True   # low = space
            time.sleep(BIT_TIME)
        # Stop bit (high)
        self._ser.break_condition = False
        time.sleep(BIT_TIME)

    def disconnect(self):
        """Send end-of-communication block and close serial port."""
        with self._lock:
            if self._connected and self._ser and self._ser.is_open:
                try:
                    self._send_block(BLK_END, [])
                except Exception:
                    pass
            self._cleanup()
            log.info("Disconnected")

    def _cleanup(self):
        self._connected = False
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None
        self._counter = 0

    # ── Block I/O ─────────────────────────────────────────────────────────────

    def _send_block(self, block_type: int, data: list[int]):
        """
        Send a KWP1281 block.

        Block format:
          [length] [counter] [type] [data...] [checksum]

        Length = number of bytes including length and checksum.
        Checksum = XOR of all bytes except checksum itself.
        """
        self._counter = (self._counter + 1) & 0xFF
        length = len(data) + 4  # length + counter + type + data + checksum = len+3... 
        # Actually: length byte counts itself + counter + type + data
        # So length = 3 + len(data)
        # Then checksum byte added after
        block = [3 + len(data), self._counter, block_type] + data
        checksum = 0
        for b in block:
            checksum ^= b

        for i, byte in enumerate(block):
            self._ser.write(bytes([byte]))
            self._ser.flush()
            if i < len(block) - 1:  # no echo wait on last byte before checksum
                # For Ross-Tech cable, ECU echoes each byte — read and discard
                # For dumb cables, no echo — skip
                pass
            time.sleep(INTER_BYTE_DELAY)

        # Send checksum
        self._ser.write(bytes([checksum]))
        self._ser.flush()
        time.sleep(INTER_BLOCK_DELAY)

    def _receive_block(self) -> tuple[int, list[int]]:
        """
        Receive a KWP1281 block from the ECU.

        Returns (block_type, data_bytes).
        Raises KWPError on timeout or checksum failure.
        """
        length = self._read_byte_timeout(self.timeout)
        counter = self._read_byte_timeout(self.timeout)
        block_type = self._read_byte_timeout(self.timeout)

        # data_length = length - 3 (length byte, counter, type)
        data_length = length - 3
        data = []
        for _ in range(data_length):
            data.append(self._read_byte_timeout(self.timeout))

        checksum = self._read_byte_timeout(self.timeout)

        # Verify checksum
        expected = 0
        for b in [length, counter, block_type] + data:
            expected ^= b
        if checksum != expected:
            raise KWPError(f"Checksum error: got 0x{checksum:02X}, "
                           f"expected 0x{expected:02X}")

        # Send ACK (complement of last byte received before checksum)
        # KWP1281: send ~checksum to acknowledge
        time.sleep(INTER_BYTE_DELAY)
        self._ser.write(bytes([~checksum & 0xFF]))
        self._ser.flush()

        log.debug(f"RECV type=0x{block_type:02X} data={[f'{b:02X}' for b in data]}")
        return block_type, data

    def _read_byte_timeout(self, timeout: float) -> int:
        """Read a single byte, raise KWPError on timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            b = self._ser.read(1)
            if b:
                return b[0]
        raise KWPError(f"Timeout waiting for byte ({timeout:.1f}s)")

    # ── Identification ────────────────────────────────────────────────────────

    def _read_identification(self) -> ECUIdentification:
        """Read ECU identification strings after connection."""
        ident = ECUIdentification()
        strings = []

        for _ in range(10):  # read up to 10 identification blocks
            try:
                block_type, data = self._receive_block()
            except KWPError:
                break

            if block_type == BLK_ID:
                # Identification string block — data is ASCII
                s = bytes(data).decode('ascii', errors='replace').strip()
                strings.append(s)
                log.debug(f"ID string: {s!r}")
            elif block_type == BLK_ACK:
                break  # end of identification
            else:
                break

        # Parse strings into fields
        # Typical format:
        #   strings[0] = part number  "893906266D      "
        #   strings[1] = component    "2.3 20V MOTRONIC"
        #   strings[2] = extra info
        if len(strings) >= 1:
            ident.part_number = strings[0].strip()
        if len(strings) >= 2:
            ident.component = strings[1].strip()
        if len(strings) > 2:
            ident.extra = [s.strip() for s in strings[2:]]

        return ident

    # ── Commands ──────────────────────────────────────────────────────────────

    def read_group(self, group: int) -> MeasuringBlock:
        """
        Read one measuring block group.

        Returns a MeasuringBlock with decoded cell values and labels.
        Raises KWPError on communication failure.
        """
        with self._lock:
            if not self._connected:
                raise KWPError("Not connected")

            self._send_block(BLK_READ_GROUP, [group])
            block_type, data = self._receive_block()

            if block_type != BLK_MEAS_VALUE:
                raise KWPError(f"Expected meas value block 0xE7, "
                               f"got 0x{block_type:02X}")

            # Parse cells: each cell is 3 bytes [formula, A, B]
            cells = []
            for i in range(len(data) // 3):
                offset = i * 3
                formula = data[offset]
                a       = data[offset + 1]
                b       = data[offset + 2]
                value, unit, display = decode_cell(formula, a, b)
                label = get_cell_label(self._ecu_def, group, i + 1)
                cells.append(MeasuringCell(
                    index=i + 1, formula=formula,
                    raw_a=a, raw_b=b,
                    value=value, unit=unit, display=display,
                    label=label,
                ))

            return MeasuringBlock(group=group, cells=cells)

    def read_faults(self) -> list[FaultCode]:
        """
        Read all stored fault codes.

        Returns list of FaultCode objects.
        Returns empty list if no faults stored.
        """
        with self._lock:
            if not self._connected:
                raise KWPError("Not connected")

            self._send_block(BLK_READ_DTC, [])
            faults = []

            while True:
                block_type, data = self._receive_block()
                if block_type == BLK_ACK:
                    break
                if block_type != BLK_DTC_RESP:
                    break

                # Each fault is 3 bytes: [code_hi, code_lo, status]
                for i in range(len(data) // 3):
                    offset = i * 3
                    code   = (data[offset] << 8) | data[offset + 1]
                    status = data[offset + 2]
                    if code == 0xFFFF:
                        continue  # no fault placeholder
                    desc = get_fault_description(self._ecu_def, code)
                    faults.append(FaultCode(code=code, status=status,
                                            description=desc))

            return faults

    def clear_faults(self) -> bool:
        """
        Clear all stored fault codes.

        Returns True if successful.
        """
        with self._lock:
            if not self._connected:
                raise KWPError("Not connected")

            self._send_block(BLK_CLEAR_DTC, [])
            block_type, _ = self._receive_block()
            return block_type == BLK_ACK

    def basic_setting(self, group: int) -> MeasuringBlock | None:
        """
        Enter basic setting mode for a group.

        Group 8 = CO pot calibration (7A ECU).
        Returns the resulting measuring block, or None on failure.
        """
        with self._lock:
            if not self._connected:
                raise KWPError("Not connected")

            self._send_block(BLK_BASIC_SET, [group])
            block_type, data = self._receive_block()

            if block_type not in (BLK_BASIC_RESP, BLK_MEAS_VALUE):
                return None

            cells = []
            for i in range(len(data) // 3):
                offset = i * 3
                formula = data[offset]
                a, b    = data[offset + 1], data[offset + 2]
                value, unit, display = decode_cell(formula, a, b)
                label = get_cell_label(self._ecu_def, group, i + 1)
                cells.append(MeasuringCell(
                    index=i + 1, formula=formula,
                    raw_a=a, raw_b=b,
                    value=value, unit=unit, display=display,
                    label=label,
                ))

            return MeasuringBlock(group=group, cells=cells)

    def keep_alive(self):
        """
        Send ACK to keep the connection alive.

        KWP1281 requires periodic communication — call this if no
        other commands have been sent for >1 second.
        """
        with self._lock:
            if self._connected and self._ser and self._ser.is_open:
                try:
                    self._send_block(BLK_ACK, [])
                    self._receive_block()
                except KWPError:
                    self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def ecu_id(self) -> ECUIdentification | None:
        return self._ecu_id

    # ── Cable detection ───────────────────────────────────────────────────────

    def _detect_cable(self) -> str:
        """
        Detect cable type from USB VID/PID.

        Ross-Tech HEX+KKL: VID=0x0403, PID=0xC33A (or similar)
        FTDI generic:       VID=0x0403
        CH340:              VID=0x1A86, PID=0x7523
        """
        try:
            ports = serial.tools.list_ports.comports()
            for p in ports:
                if p.device == self.port:
                    vid = p.vid or 0
                    pid = p.pid or 0
                    log.debug(f"Cable VID={vid:#06x} PID={pid:#06x}")

                    # Ross-Tech genuine cables
                    if vid == 0x0403 and pid in (0xC33A, 0xC33B, 0xC33C):
                        return CABLE_ROSS_TECH
                    # Ross-Tech HEX-USB (older)
                    if vid == 0x0403 and pid == 0xFF00:
                        return CABLE_ROSS_TECH
                    # Generic FTDI
                    if vid == 0x0403:
                        return CABLE_FTDI
                    # CH340
                    if vid == 0x1A86:
                        return CABLE_CH340
        except Exception:
            pass

        log.warning(f"Could not detect cable type for {self.port}, "
                    "defaulting to FTDI")
        return CABLE_FTDI
