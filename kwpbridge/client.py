"""
KWPBridge client — consume live ECU data from KWPBridge server.

Designed to be imported by HachiROM, digital dash, or any other tool
that wants to display or log live ECU data.

Usage:
    from kwpbridge.client import KWPClient, is_running

    # Check if KWPBridge is running
    if is_running():
        client = KWPClient()
        client.on_state(lambda state: print(state))
        client.connect()

    # Or just poll once
    state = get_state()
    if state and state['connected']:
        rpm = state['groups']['1']['cells'][0]['value']
"""

import json
import socket
import threading
import time
import logging
from typing import Callable, Any

from .constants import DEFAULT_PORT
from . import __version__

log = logging.getLogger(__name__)


def is_running(port: int = DEFAULT_PORT, timeout: float = 0.2) -> bool:
    """
    Check if KWPBridge is running on the default port.

    Fast non-blocking check — returns True/False in < timeout seconds.
    Use this in app startup to decide whether to enable KWP features.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        return result == 0
    except Exception:
        return False


def get_state(port: int = DEFAULT_PORT, timeout: float = 1.0) -> dict | None:
    """
    Get a single state snapshot from KWPBridge.

    Connects, reads one state message, disconnects.
    Returns the state dict or None if KWPBridge isn't running.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(("127.0.0.1", port))
        buf = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            chunk = s.recv(4096).decode("utf-8", errors="replace")
            if not chunk:
                break
            buf += chunk
            for line in buf.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "state":
                        s.close()
                        return msg.get("data")
                except json.JSONDecodeError:
                    pass
        s.close()
    except Exception:
        pass
    return None


class KWPClient:
    """
    Persistent KWPBridge client with callbacks.

    Maintains a connection to KWPBridge and calls registered handlers
    whenever new state arrives.

    Usage:
        client = KWPClient()
        client.on_state(my_state_handler)
        client.on_disconnect(my_disconnect_handler)
        client.connect()
        # ... later ...
        client.disconnect()
    """

    def __init__(self, port: int = DEFAULT_PORT):
        self.port            = port
        self._socket:        socket.socket | None = None
        self._thread:        threading.Thread | None = None
        self._running        = False
        self._connected      = False
        self._state:         dict | None = None
        self._state_handlers:      list[Callable] = []
        self._connect_handlers:    list[Callable] = []
        self._disconnect_handlers: list[Callable] = []
        self._error_handlers:      list[Callable] = []

    # ── Event registration ────────────────────────────────────────────────────

    def on_state(self, fn: Callable[[dict], None]):
        """Register callback for state updates. Called with state dict."""
        self._state_handlers.append(fn)
        return self

    def on_connect(self, fn: Callable[[], None]):
        """Register callback when connection to KWPBridge is established."""
        self._connect_handlers.append(fn)
        return self

    def on_disconnect(self, fn: Callable[[], None]):
        """Register callback when KWPBridge connection is lost."""
        self._disconnect_handlers.append(fn)
        return self

    def on_error(self, fn: Callable[[str], None]):
        """Register callback for error messages."""
        self._error_handlers.append(fn)
        return self

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, auto_reconnect: bool = True):
        """
        Start background connection thread.

        If auto_reconnect=True, automatically reconnects if KWPBridge
        restarts or the connection drops.
        """
        self._running = True
        self._auto_reconnect = auto_reconnect
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="kwpbridge-client")
        self._thread.start()

    def disconnect(self):
        """Stop the client and close connection."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass

    def send_command(self, cmd: dict):
        """Send a command to KWPBridge."""
        if self._socket and self._connected:
            try:
                line = json.dumps(cmd) + "\n"
                self._socket.sendall(line.encode("utf-8"))
            except Exception as e:
                log.warning(f"Command send failed: {e}")

    def read_faults(self):
        """Request fault code read."""
        self.send_command({"cmd": "read_faults"})

    def clear_faults(self):
        """Request fault code clear."""
        self.send_command({"cmd": "clear_faults"})

    def basic_setting(self, group: int = 8):
        """Enter basic setting mode (default group 8 = CO pot cal)."""
        self.send_command({"cmd": "basic_setting", "group": group})

    def set_groups(self, groups: list[int]):
        """Update which measuring block groups to poll."""
        self.send_command({"cmd": "set_groups", "groups": groups})

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def state(self) -> dict | None:
        return self._state

    def get_value(self, group: int, cell: int) -> float | None:
        """
        Get a single decoded value from the last state.

        Returns None if no data available for the requested group/cell.
        """
        if not self._state:
            return None
        groups = self._state.get("groups", {})
        g = groups.get(str(group)) or groups.get(group)
        if not g:
            return None
        for c in g.get("cells", []):
            if c.get("index") == cell:
                return c.get("value")
        return None

    # ── Background thread ─────────────────────────────────────────────────────

    def _run(self):
        reconnect_delay = 3.0

        while self._running:
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(2.0)
                self._socket.connect(("127.0.0.1", self.port))
                self._socket.settimeout(0.5)
                self._connected = True
                log.info(f"Connected to KWPBridge on port {self.port}")
                for fn in self._connect_handlers:
                    try:
                        fn()
                    except Exception:
                        pass

                buf = ""
                while self._running:
                    try:
                        chunk = self._socket.recv(4096).decode(
                            "utf-8", errors="replace")
                        if not chunk:
                            break
                        buf += chunk
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            self._process_message(line.strip())
                    except socket.timeout:
                        continue
                    except Exception:
                        break

            except Exception as e:
                if self._running:
                    log.debug(f"KWPBridge not available: {e}")

            self._connected = False
            for fn in self._disconnect_handlers:
                try:
                    fn()
                except Exception:
                    pass

            if not self._running:
                break
            if self._auto_reconnect:
                time.sleep(reconnect_delay)
            else:
                break

    def _process_message(self, line: str):
        if not line:
            return
        try:
            msg = json.loads(line)
            msg_type = msg.get("type")

            if msg_type == "state":
                self._state = msg.get("data")
                for fn in self._state_handlers:
                    try:
                        fn(self._state)
                    except Exception as e:
                        log.error(f"State handler error: {e}")

            elif msg_type == "error":
                err = msg.get("message", "unknown error")
                log.warning(f"KWPBridge error: {err}")
                for fn in self._error_handlers:
                    try:
                        fn(err)
                    except Exception:
                        pass

            elif msg_type == "faults":
                # Faults response — clients can handle via on_state or direct
                pass

        except json.JSONDecodeError:
            pass
