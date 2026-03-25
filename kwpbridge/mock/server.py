"""
KWPBridge Mock Server — simulates a live KWPBridge process for testing.

Speaks the same TCP/JSON protocol as the real KWPBridge server on
localhost:50266, using hardcoded ECU data from ecu_7a.py / ecu_aah.py.

Usage:
    # In tests or dev:
    from kwpbridge.mock.server import MockServer

    server = MockServer(ecu="7a")
    server.start()
    # ... run your tests ...
    server.stop()

    # From the command line:
    python -m kwpbridge.mock --ecu 7a
    python -m kwpbridge.mock --ecu aah --port 50266
"""

import json
import logging
import socket
import threading
import time
from typing import Callable

from ..constants import DEFAULT_PORT
from .. import __version__

log = logging.getLogger(__name__)


# ── Message builders ──────────────────────────────────────────────────────────

def _make_welcome(part_number: str, component: str) -> bytes:
    return (json.dumps({
        "type":    "connected",
        "version": __version__,
        "mock":    True,
    }) + "\n").encode()


def _make_state(part_number: str, component: str,
                cells: list[dict], t: float,
                scenario_info: dict = None,
                extra_groups: dict = None) -> bytes:
    """Build a state message. extra_groups = {group_num: [cell_list]}."""
    groups_data = {
        "0": {
            "group":     0,
            "timestamp": t,
            "cells":     cells,
        }
    }
    if extra_groups:
        for grp_num, grp_cells in extra_groups.items():
            groups_data[str(grp_num)] = {
                "group":     grp_num,
                "timestamp": t,
                "cells":     grp_cells,
            }
    data = {
        "connected":   True,
        "mock":        True,
        "ecu_id": {
            "part_number": part_number,
            "component":   component,
            "coding":      "0010",
            "wsw":         "0000",
        },
        "groups":      groups_data,
        "faults":      [],
        "fault_count": 0,
        "timestamp":   t,
    }
    if scenario_info:
        data["scenario"] = scenario_info
    return (json.dumps({"type": "state", "data": data}) + "\n").encode()


def _make_faults(faults: list) -> bytes:
    return (json.dumps({
        "type":   "faults",
        "faults": faults,
        "count":  len(faults),
    }) + "\n").encode()


# ── Mock server ───────────────────────────────────────────────────────────────

class MockServer:
    """
    Fake KWPBridge TCP server.

    Starts a listener on localhost:{port}, accepts connections, sends
    a welcome message, then broadcasts live ECU state at ~3 Hz.

    Parameters
    ----------
    ecu       : "7a" or "aah" — which mock ECU dataset to use
    port      : TCP port (default DEFAULT_PORT = 50266)
    poll_hz   : state broadcast rate in Hz (default 3)
    on_command: optional callback(client_addr, cmd_dict) for received commands
    """

    def __init__(self,
                 ecu:        str = "7a",
                 port:       int = DEFAULT_PORT,
                 poll_hz:    float = 3.0,
                 on_command: Callable | None = None):
        self.ecu       = ecu.lower()
        self.port      = port
        self.poll_hz   = poll_hz
        self.on_command = on_command

        self._clients:  list[socket.socket] = []
        self._lock      = threading.Lock()
        self._running   = False
        self._server_sock: socket.socket | None = None
        self._accept_thread:    threading.Thread | None = None
        self._broadcast_thread: threading.Thread | None = None

        # Load ECU profile
        if self.ecu == "7a":
            from .ecu_7a import get_group_0, ECU_PART_NUMBER, ECU_COMPONENT, FAULT_CODES
        elif self.ecu == "aah":
            from .ecu_aah import get_group_0, ECU_PART_NUMBER, ECU_COMPONENT, FAULT_CODES
        elif self.ecu in ("digifant", "g60", "g40"):
            from .ecu_digifant import get_group_1 as get_group_0, \
                                      ECU_PART_NUMBER, ECU_COMPONENT, FAULT_CODES
        elif self.ecu in ("m232", "aan", "aby", "adu", "m2.3.2"):
            from .ecu_m232 import get_group_0, ECU_PART_NUMBER, ECU_COMPONENT, FAULT_CODES
        elif self.ecu in ("me7", "awp", "aum", "auq", "bam", "me7.5"):
            from .ecu_me7 import get_group_0, ECU_PART_NUMBER, ECU_COMPONENT, FAULT_CODES
        elif self.ecu in ("27t", "s4", "agb", "are", "bes", "me7.1"):
            from .ecu_27t import get_group_0, ECU_PART_NUMBER, ECU_COMPONENT, FAULT_CODES
        else:
            raise ValueError(
                f"Unknown mock ECU: {ecu!r}. Use '7a', 'aah', 'digifant', 'm232', or 'me7'.")

        self._get_group_0   = get_group_0
        self._part_number   = ECU_PART_NUMBER
        self._component     = ECU_COMPONENT
        self._fault_codes   = FAULT_CODES
        self._warmup_start  = None   # set on first broadcast

        # Multi-group broadcast — m232 broadcasts groups 1-8, me7 broadcasts 14 groups
        self._get_all_groups   = None
        self._broadcast_groups = list(range(1, 9))   # default (m232)
        if self.ecu in ("m232", "aan", "aby", "adu", "m2.3.2"):
            try:
                from .ecu_m232 import get_group as _get_group
                self._get_all_groups = _get_group
            except ImportError:
                pass
        elif self.ecu in ("me7", "awp", "aum", "auq", "bam", "me7.5"):
            try:
                from .ecu_me7 import get_group as _get_group
                self._get_all_groups   = _get_group
                self._broadcast_groups = [1, 2, 3, 4, 5, 10, 22, 23,
                                          32, 33, 50, 60, 91, 94]
            except ImportError:
                pass
        elif self.ecu in ("27t", "s4", "agb", "are", "bes", "me7.1"):
            try:
                from .ecu_27t import get_group as _get_group
                self._get_all_groups   = _get_group
                # 2.7T has dual-bank groups 034 and 051 in addition to ME7.5 groups
                self._broadcast_groups = [1, 2, 3, 4, 5, 10, 22, 23,
                                          32, 33, 34, 50, 51, 60, 91, 94]
            except ImportError:
                pass
        # scenario_info available on 7A, Digifant, and M2.3.2 mocks
        self._get_scenario_info = None
        if self.ecu in ("7a", "digifant", "g60", "g40", "m232", "aan", "aby", "adu", "m2.3.2",
                        "me7", "awp", "aum", "auq", "bam", "me7.5",
                        "27t", "s4", "agb", "are", "bes", "me7.1"):
            try:
                mod_map = {"7a": "ecu_7a", "digifant": "ecu_digifant",
                           "g60": "ecu_digifant", "g40": "ecu_digifant",
                           "me7": "ecu_me7", "awp": "ecu_me7", "aum": "ecu_me7",
                           "auq": "ecu_me7", "bam": "ecu_me7", "me7.5": "ecu_me7"}
                mod_name = mod_map.get(self.ecu, "ecu_m232")
                import importlib
                m = importlib.import_module(f".{mod_name}", package=__package__)
                self._get_scenario_info = m.get_scenario_info
            except (ImportError, AttributeError):
                pass

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """Start the mock server (non-blocking)."""
        if self._running:
            return
        self._running = True

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("127.0.0.1", self.port))
        self._server_sock.listen(8)
        self._server_sock.settimeout(1.0)

        self._accept_thread = threading.Thread(
            target=self._accept_loop, daemon=True, name="mock-accept")
        self._broadcast_thread = threading.Thread(
            target=self._broadcast_loop, daemon=True, name="mock-broadcast")

        self._accept_thread.start()
        self._broadcast_thread.start()
        log.info(f"MockServer started — ECU {self._part_number} on :{self.port}")

    def stop(self):
        """Stop the server and close all connections."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        with self._lock:
            for c in self._clients:
                try:
                    c.close()
                except Exception:
                    pass
            self._clients.clear()
        if self._accept_thread:
            self._accept_thread.join(timeout=2)
        if self._broadcast_thread:
            self._broadcast_thread.join(timeout=2)
        log.info("MockServer stopped")

    def is_running(self) -> bool:
        return self._running

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def inject_fault(self, code: int, description: str):
        """Add a fault code to simulate a fault condition."""
        with self._lock:
            self._fault_codes.append({
                "code": code, "description": description, "status": "stored"
            })

    def clear_faults(self):
        with self._lock:
            self._fault_codes.clear()

    def get_faults(self) -> list:
        """Thread-safe accessor — returns a copy of the fault list."""
        with self._lock:
            return list(self._fault_codes)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._server_sock.accept()
                log.debug(f"MockServer: client connected from {addr}")
                with self._lock:
                    self._clients.append(conn)
                # Send welcome immediately
                conn.sendall(_make_welcome(self._part_number, self._component))
                # Start a receive thread for this client
                threading.Thread(
                    target=self._recv_loop,
                    args=(conn, addr),
                    daemon=True,
                    name=f"mock-recv-{addr[1]}",
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _recv_loop(self, conn: socket.socket, addr):
        """Receive commands from a client."""
        buf = b""
        while self._running:
            try:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        cmd = json.loads(line)
                        self._handle_command(conn, cmd)
                    except json.JSONDecodeError:
                        pass
            except (OSError, ConnectionResetError):
                break
        with self._lock:
            if conn in self._clients:
                self._clients.remove(conn)
        log.debug(f"MockServer: client {addr} disconnected")

    def _handle_command(self, conn: socket.socket, cmd: dict):
        """Handle a command from a client."""
        verb = cmd.get("cmd", "")
        log.debug(f"MockServer: command {verb!r}")

        if verb == "read_faults":
            with self._lock:
                faults_copy = list(self._fault_codes)
            conn.sendall(_make_faults(faults_copy))
        elif verb == "clear_faults":
            with self._lock:
                self._fault_codes.clear()
            conn.sendall(_make_faults([]))
        elif verb == "get_state":
            t = time.time()
            cells = self._get_group_0(t)
            conn.sendall(_make_state(
                self._part_number, self._component, cells, t))

        if self.on_command:
            try:
                self.on_command(conn.getpeername(), cmd)
            except Exception:
                pass

    def _broadcast_loop(self):
        """Broadcast state to all clients at poll_hz."""
        interval = 1.0 / self.poll_hz
        while self._running:
            t = time.time()
            if self._warmup_start is None:
                self._warmup_start = t
            if self._clients:
                cells = self._get_group_0(t, self._warmup_start)
                sc_info = None
                if self._get_scenario_info:
                    sc_info = self._get_scenario_info(t, self._warmup_start)
                # For M2.3.2: broadcast all 8 groups so LiveValues can decode load/MAP
                extra = None
                if self._get_all_groups:
                    extra = {}
                    for grp in self._broadcast_groups:
                        try:
                            extra[grp] = self._get_all_groups(grp, t, self._warmup_start)
                        except Exception:
                            pass
                msg = _make_state(
                    self._part_number, self._component, cells, t, sc_info, extra)
                with self._lock:
                    dead = []
                    for c in self._clients:
                        try:
                            c.sendall(msg)
                        except OSError:
                            dead.append(c)
                    for c in dead:
                        self._clients.remove(c)
            time.sleep(interval)


# ── Context manager support ───────────────────────────────────────────────────

class mock_server:
    """Context manager — starts and stops a MockServer automatically.

    Usage:
        with mock_server(ecu="7a") as srv:
            # server is running
            client = KWPClient()
            client.connect()
            ...
        # server stopped automatically
    """

    def __init__(self, ecu: str = "7a", port: int = DEFAULT_PORT, **kwargs):
        self._srv = MockServer(ecu=ecu, port=port, **kwargs)

    def __enter__(self) -> MockServer:
        self._srv.start()
        time.sleep(0.1)   # give the socket a moment to bind
        return self._srv

    def __exit__(self, *_):
        self._srv.stop()
