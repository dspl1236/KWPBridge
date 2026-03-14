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
                cells: list[dict], t: float) -> bytes:
    return (json.dumps({
        "type": "state",
        "data": {
            "connected":   True,
            "mock":        True,
            "ecu_id": {
                "part_number": part_number,
                "component":   component,
                "coding":      "0010",
                "wsw":         "0000",
            },
            "groups": {
                "0": {
                    "group":     0,
                    "timestamp": t,
                    "cells":     cells,
                }
            },
            "faults":      [],
            "fault_count": 0,
            "timestamp":   t,
        }
    }) + "\n").encode()


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
        else:
            raise ValueError(f"Unknown mock ECU: {ecu!r}. Use '7a' or 'aah'.")

        self._get_group_0   = get_group_0
        self._part_number   = ECU_PART_NUMBER
        self._component     = ECU_COMPONENT
        self._fault_codes   = FAULT_CODES

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
        self._fault_codes.append({
            "code": code, "description": description, "status": "stored"
        })

    def clear_faults(self):
        self._fault_codes.clear()

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
            conn.sendall(_make_faults(self._fault_codes))
        elif verb == "clear_faults":
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
            if self._clients:
                cells = self._get_group_0(t)
                msg = _make_state(
                    self._part_number, self._component, cells, t)
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
