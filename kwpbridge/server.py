"""
KWPBridge TCP server — broadcasts live ECU data to connected clients.

Architecture:
  - KWP1281 polling loop runs in a background thread
  - State is serialised to JSON and broadcast to all TCP clients
  - Clients connect to localhost:50266 and receive newline-delimited JSON
  - Client apps just try to connect — if refused, KWPBridge isn't running

Protocol:
  Server → Client: JSON lines, one per update
    {"type": "state", "data": { ...BridgeState... }}
    {"type": "error", "message": "..."}
    {"type": "connected", "version": "0.1.0"}

  Client → Server: JSON lines (commands)
    {"cmd": "read_faults"}
    {"cmd": "clear_faults"}
    {"cmd": "basic_setting", "group": 8}
    {"cmd": "set_groups", "groups": [1, 2, 3]}
    {"cmd": "disconnect"}
    {"cmd": "reconnect"}
"""

import json
import socket
import threading
import time
import logging
from typing import Any

from .constants  import DEFAULT_PORT, IPC_UPDATE_HZ, ADDR_ENGINE, CABLE_AUTO
from .models     import BridgeState
from .protocol   import KWP1281, KWPError
from . import __version__

log = logging.getLogger(__name__)


class KWPServer:
    """
    KWPBridge server — manages the KWP1281 connection and IPC clients.

    Usage:
        server = KWPServer(
            serial_port="COM3",
            groups=[1, 2, 3, 4],
            cable_type=CABLE_ROSS_TECH,
        )
        server.start()   # blocks until Ctrl+C or server.stop()
    """

    def __init__(
        self,
        serial_port:  str,
        groups:       list[int]  = None,
        ecu_address:  int        = ADDR_ENGINE,
        cable_type:   str        = CABLE_AUTO,
        tcp_port:     int        = DEFAULT_PORT,
        poll_interval: float     = 1.0 / IPC_UPDATE_HZ,
    ):
        self.serial_port   = serial_port
        self.groups        = groups or [1, 2, 3, 4]
        self.ecu_address   = ecu_address
        self.cable_type    = cable_type
        self.tcp_port      = tcp_port
        self.poll_interval = poll_interval

        self._kwp:        KWP1281 | None  = None
        self._state       = BridgeState()
        self._clients:    list[socket.socket] = []
        self._client_lock = threading.Lock()
        self._running     = False
        self._poll_thread: threading.Thread | None = None
        self._tcp_thread:  threading.Thread | None = None
        self._tcp_server:  socket.socket | None   = None

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """Start server and block until stopped."""
        self._running = True

        # Start KWP polling thread
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="kwp-poll")
        self._poll_thread.start()

        # Start TCP server
        self._tcp_thread = threading.Thread(
            target=self._tcp_accept_loop, daemon=True, name="tcp-accept")
        self._tcp_thread.start()

        log.info(f"KWPBridge v{__version__} started — "
                 f"port {self.tcp_port}, serial {self.serial_port}")

        try:
            while self._running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            log.info("Interrupted — shutting down")
        finally:
            self.stop()

    def stop(self):
        """Stop server and disconnect from ECU."""
        self._running = False
        if self._kwp:
            try:
                self._kwp.disconnect()
            except Exception:
                pass
        if self._tcp_server:
            try:
                self._tcp_server.close()
            except Exception:
                pass
        log.info("KWPBridge stopped")

    def set_groups(self, groups: list[int]):
        """Update the list of measuring block groups to poll."""
        self.groups = groups
        log.info(f"Poll groups updated: {groups}")

    # ── KWP polling ───────────────────────────────────────────────────────────

    def _poll_loop(self):
        """Background thread — maintains KWP connection and polls groups."""
        reconnect_delay = 5.0

        while self._running:
            # ── Connect ───────────────────────────────────────────────────────
            if not (self._kwp and self._kwp.connected):
                try:
                    self._kwp = KWP1281(
                        port=self.serial_port,
                        cable_type=self.cable_type,
                    )
                    ecu_id = self._kwp.connect(self.ecu_address)
                    self._state.connected   = True
                    self._state.ecu_id      = ecu_id
                    self._state.ecu_address = self.ecu_address
                    self._state.error       = ""
                    self._state.cable_type  = self._kwp.cable_type
                    self._state.port        = self.serial_port
                    log.info(f"ECU connected: {ecu_id.part_number}")
                    self._broadcast_state()
                except KWPError as e:
                    self._state.connected = False
                    self._state.error = str(e)
                    log.warning(f"Connection failed: {e} — retry in {reconnect_delay}s")
                    self._broadcast_state()
                    time.sleep(reconnect_delay)
                    continue

            # ── Poll groups ───────────────────────────────────────────────────
            try:
                for group in self.groups:
                    if not self._running:
                        break
                    block = self._kwp.read_group(group)
                    self._state.groups[group] = block
                    self._state.timestamp = time.time()

                self._broadcast_state()
                time.sleep(self.poll_interval)

            except KWPError as e:
                log.warning(f"Poll error: {e}")
                self._state.connected = False
                self._state.error = str(e)
                self._broadcast_state()
                time.sleep(reconnect_delay)

    # ── TCP server ────────────────────────────────────────────────────────────

    def _tcp_accept_loop(self):
        """Accept incoming TCP client connections."""
        try:
            self._tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._tcp_server.bind(("127.0.0.1", self.tcp_port))
            self._tcp_server.listen(16)
            self._tcp_server.settimeout(1.0)
            log.info(f"TCP server listening on 127.0.0.1:{self.tcp_port}")

            while self._running:
                try:
                    conn, addr = self._tcp_server.accept()
                    log.info(f"Client connected from {addr}")
                    t = threading.Thread(
                        target=self._handle_client,
                        args=(conn,), daemon=True,
                        name=f"client-{addr[1]}")
                    t.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        log.error(f"Accept error: {e}")
        except Exception as e:
            log.error(f"TCP server error: {e}")

    def _handle_client(self, conn: socket.socket):
        """Handle a single TCP client — send state updates, receive commands."""
        with self._client_lock:
            self._clients.append(conn)

        try:
            # Send welcome + current state immediately
            self._send_to(conn, {"type": "connected", "version": __version__,
                                  "port": self.tcp_port})
            self._send_to(conn, {"type": "state", "data": self._state.as_dict()})

            conn.settimeout(0.1)
            buf = ""

            while self._running:
                try:
                    chunk = conn.recv(1024).decode("utf-8", errors="replace")
                    if not chunk:
                        break
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        self._handle_command(conn, line.strip())
                except socket.timeout:
                    continue
                except Exception:
                    break
        finally:
            with self._client_lock:
                if conn in self._clients:
                    self._clients.remove(conn)
            try:
                conn.close()
            except Exception:
                pass
            log.info("Client disconnected")

    def _handle_command(self, conn: socket.socket, line: str):
        """Process a command received from a client."""
        if not line:
            return
        try:
            msg = json.loads(line)
            cmd = msg.get("cmd", "")

            if cmd == "read_faults":
                if self._kwp and self._kwp.connected:
                    faults = self._kwp.read_faults()
                    self._state.faults = faults
                    self._state.fault_count = len(faults)
                    self._send_to(conn, {
                        "type": "faults",
                        "faults": [f.as_dict() for f in faults],
                    })

            elif cmd == "clear_faults":
                if self._kwp and self._kwp.connected:
                    ok = self._kwp.clear_faults()
                    self._send_to(conn, {"type": "clear_faults", "ok": ok})

            elif cmd == "basic_setting":
                group = msg.get("group", 8)
                if self._kwp and self._kwp.connected:
                    block = self._kwp.basic_setting(group)
                    self._send_to(conn, {
                        "type": "basic_setting",
                        "data": block.as_dict() if block else None,
                    })

            elif cmd == "set_groups":
                groups = msg.get("groups", self.groups)
                self.set_groups(groups)
                self._send_to(conn, {"type": "groups_set", "groups": groups})

            elif cmd == "get_state":
                self._send_to(conn, {
                    "type": "state",
                    "data": self._state.as_dict(),
                })

        except json.JSONDecodeError:
            log.warning(f"Invalid JSON from client: {line!r}")
        except Exception as e:
            log.error(f"Command error: {e}")
            self._send_to(conn, {"type": "error", "message": str(e)})

    def _send_to(self, conn: socket.socket, msg: dict):
        """Send a JSON message to a single client."""
        try:
            line = json.dumps(msg) + "\n"
            conn.sendall(line.encode("utf-8"))
        except Exception:
            pass

    def _broadcast_state(self):
        """Broadcast current state to all connected clients."""
        if not self._clients:
            return
        msg = json.dumps({"type": "state", "data": self._state.as_dict()}) + "\n"
        encoded = msg.encode("utf-8")
        with self._client_lock:
            dead = []
            for conn in self._clients:
                try:
                    conn.sendall(encoded)
                except Exception:
                    dead.append(conn)
            for conn in dead:
                self._clients.remove(conn)
