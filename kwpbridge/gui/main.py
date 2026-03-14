"""
KWPBridge GUI — compact diagnostic interface.

Compact mode:  [●] ECU ID banner  [Connect] [Disconnect] [Gauges ▼]
               Status bar showing current values

Gauges mode:   Expands to show RPM gauge, coolant temp, intake temp,
               load bar, lambda, battery voltage, ignition timing.
               All values sourced from live measuring blocks via KWP1281.

Usage:
    python -m kwpbridge.gui --port COM3
    python -m kwpbridge.gui --port COM3 --cable ross_tech
"""

import sys
import time
import threading
import logging
import argparse
from pathlib import Path

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QFrame, QSizePolicy,
        QStatusBar, QAction, QFileDialog, QMessageBox, QProgressBar,
        QGridLayout, QGroupBox, QLineEdit, QSpinBox,
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt5.QtGui import QFont, QColor, QPalette
except ImportError:
    print("PyQt5 required: pip install PyQt5")
    sys.exit(1)

import serial.tools.list_ports

from ..constants  import DEFAULT_PORT, CABLE_AUTO, CABLE_ROSS_TECH, CABLE_FTDI, CABLE_CH340
from ..protocol   import KWP1281, KWPError
from ..lbl_parser import LBLRegistry, decode_with_lbl
from ..ecu_defs   import find_ecu_def
from ..server     import KWPServer
from .. import __version__

log = logging.getLogger(__name__)


def _vcds_label_paths() -> list[Path]:
    """Auto-discover VCDS Labels folder on common install paths."""
    candidates = []
    if sys.platform == "win32":
        for base in [
            Path("C:/Ross-Tech/VCDS/Labels"),
            Path("C:/VCDS/Labels"),
            Path(Path.home() / "Ross-Tech" / "VCDS" / "Labels"),
        ]:
            if base.exists():
                candidates.append(base)
    return candidates

# ── Colours ──────────────────────────────────────────────────────────────────
C_BG        = "#0e0e0e"
C_PANEL     = "#161616"
C_BORDER    = "#2a2a2a"
C_GREEN     = "#2dff6e"
C_AMBER     = "#ffaa00"
C_RED       = "#ff4444"
C_TEXT      = "#e0e0e0"
C_DIM       = "#555555"
C_BLUE      = "#4488ff"

COMPACT_H   = 110    # compact window height
GAUGE_H     = 480    # expanded window height
WINDOW_W    = 520


# ── Worker signals ────────────────────────────────────────────────────────────
class WorkerSignals(QObject):
    connected    = pyqtSignal(dict)    # ecu_id dict
    disconnected = pyqtSignal(str)     # reason string
    data_ready   = pyqtSignal(dict)    # {group: MeasuringBlock}
    error        = pyqtSignal(str)


# ── Connection worker ─────────────────────────────────────────────────────────
class ConnectionWorker(threading.Thread):
    """Background thread managing KWP1281 connection and polling."""

    def __init__(self, port, cable, groups, signals: WorkerSignals):
        super().__init__(daemon=True, name="kwp-worker")
        self.port    = port
        self.cable   = cable
        self.groups  = groups
        self.signals = signals
        self._stop   = threading.Event()
        self._kwp: KWP1281 | None = None

    def stop(self):
        self._stop.set()
        if self._kwp:
            try:
                self._kwp.disconnect()
            except Exception:
                pass

    def run(self):
        retry = 0
        max_retry = 3

        while not self._stop.is_set() and retry < max_retry:
            try:
                self._kwp = KWP1281(port=self.port, cable_type=self.cable)
                ecu_id = self._kwp.connect()
                self.signals.connected.emit(ecu_id.__dict__)
                retry = 0

                # Poll loop
                while not self._stop.is_set():
                    data = {}
                    for g in self.groups:
                        if self._stop.is_set():
                            break
                        try:
                            block = self._kwp.read_group(g)
                            data[g] = block
                        except KWPError as e:
                            log.warning(f"Group {g} read error: {e}")
                    if data:
                        self.signals.data_ready.emit(data)
                    time.sleep(0.3)

            except KWPError as e:
                retry += 1
                if retry < max_retry:
                    msg = f"Connection failed ({retry}/{max_retry}): {e} — retrying..."
                    self.signals.error.emit(msg)
                    time.sleep(2)
                else:
                    self.signals.disconnected.emit(str(e))
            except Exception as e:
                self.signals.disconnected.emit(str(e))
                break


# ── Gauge widget ──────────────────────────────────────────────────────────────
class GaugeWidget(QWidget):
    """Single gauge — label, big value, unit, optional bar."""

    def __init__(self, label: str, unit: str = "",
                 min_val: float = 0, max_val: float = 100,
                 show_bar: bool = False, parent=None):
        super().__init__(parent)
        self._min = min_val
        self._max = max_val
        self._show_bar = show_bar
        self.setStyleSheet(f"background:{C_PANEL}; border:1px solid {C_BORDER}; "
                           f"border-radius:4px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.lbl_name  = QLabel(label.upper())
        self.lbl_name.setStyleSheet(
            f"color:{C_DIM}; font-size:9px; letter-spacing:1px; border:none;")

        self.lbl_value = QLabel("—")
        self.lbl_value.setAlignment(Qt.AlignCenter)
        self.lbl_value.setStyleSheet(
            f"color:{C_TEXT}; font-size:26px; font-weight:bold; "
            f"font-family:Consolas; border:none;")

        self.lbl_unit  = QLabel(unit)
        self.lbl_unit.setAlignment(Qt.AlignCenter)
        self.lbl_unit.setStyleSheet(
            f"color:{C_DIM}; font-size:10px; border:none;")

        layout.addWidget(self.lbl_name)
        layout.addWidget(self.lbl_value, 1)
        layout.addWidget(self.lbl_unit)

        if show_bar:
            self.bar = QProgressBar()
            self.bar.setRange(0, 1000)
            self.bar.setValue(0)
            self.bar.setTextVisible(False)
            self.bar.setFixedHeight(4)
            self.bar.setStyleSheet(
                f"QProgressBar {{ background:{C_BORDER}; border:none; border-radius:2px; }}"
                f"QProgressBar::chunk {{ background:{C_GREEN}; border-radius:2px; }}")
            layout.addWidget(self.bar)

    def update_value(self, value: float | None, colour: str = C_TEXT):
        if value is None:
            self.lbl_value.setText("—")
            self.lbl_value.setStyleSheet(
                f"color:{C_DIM}; font-size:26px; font-weight:bold; "
                f"font-family:Consolas; border:none;")
        else:
            self.lbl_value.setText(f"{value:.1f}".rstrip('0').rstrip('.'))
            self.lbl_value.setStyleSheet(
                f"color:{colour}; font-size:26px; font-weight:bold; "
                f"font-family:Consolas; border:none;")
            if self._show_bar and hasattr(self, 'bar'):
                pct = max(0, min(1000, int(
                    (value - self._min) / max(1, self._max - self._min) * 1000)))
                self.bar.setValue(pct)


# ── Main window ───────────────────────────────────────────────────────────────
class KWPBridgeWindow(QMainWindow):

    def __init__(self, port: str = "", cable: str = CABLE_AUTO,
                 labels_path: str = "", groups: list[int] = None):
        super().__init__()
        self._port    = port
        self._cable   = cable
        self._groups  = groups or [0]   # 7A uses group 0
        self._worker: ConnectionWorker | None = None
        self._signals = WorkerSignals()
        self._lbl_registry = LBLRegistry()   # always includes bundled labels/
        if labels_path:
            self._lbl_registry.add_path(labels_path)
        # Auto-discover VCDS labels folder on Windows
        for candidate in _vcds_label_paths():
            self._lbl_registry.add_path(candidate)
        self._lbl: object = None    # loaded LBLFile for current ECU
        self._gauges_visible = False
        self._last_data: dict = {}
        self._current_ecu_id: dict = {}
        self._tcp_server = None
        self._mock_server = None
        self._mock_warmup_start = None
        # fault buttons initialised in _setup_ui, referenced here for type hints
        self.btn_read_faults:  QPushButton | None = None
        self.btn_clear_faults: QPushButton | None = None

        self._setup_ui()
        self._connect_signals()

        if port:
            # Auto-populate port combo
            for i in range(self.combo_port.count()):
                if self.combo_port.itemData(i) == port:
                    self.combo_port.setCurrentIndex(i)
                    break

    # ── UI build ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setWindowTitle(f"KWPBridge  v{__version__}")
        self.setFixedWidth(WINDOW_W)
        self.setMinimumHeight(COMPACT_H)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")

        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setContentsMargins(12, 12, 12, 8)
        main.setSpacing(8)

        # ── ECU banner ────────────────────────────────────────────────────────
        self.banner = QLabel("No ECU connected")
        self.banner.setStyleSheet(
            f"color:{C_DIM}; font-size:12px; font-family:Consolas;")
        main.addWidget(self.banner)

        # ── Controls row ──────────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        # Status dot
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{C_RED}; font-size:14px;")
        self.dot.setFixedWidth(18)
        ctrl.addWidget(self.dot)

        # Port selector
        self.combo_port = QComboBox()
        self.combo_port.setStyleSheet(
            f"QComboBox {{ background:{C_PANEL}; color:{C_TEXT}; "
            f"border:1px solid {C_BORDER}; border-radius:3px; "
            f"padding:3px 8px; font-size:11px; }}"
            f"QComboBox::drop-down {{ border:none; }}"
            f"QComboBox QAbstractItemView {{ background:{C_PANEL}; color:{C_TEXT}; }}")
        self._populate_ports()
        ctrl.addWidget(self.combo_port, 2)

        # Port refresh button
        btn_refresh = QPushButton("⟳")
        btn_refresh.setFixedWidth(28)
        btn_refresh.setToolTip("Refresh port list")
        btn_refresh.setStyleSheet(
            f"QPushButton {{ background:{C_PANEL}; color:{C_DIM}; "
            f"border:1px solid {C_BORDER}; border-radius:3px; font-size:14px; }}"
            f"QPushButton:hover {{ color:{C_TEXT}; }}")
        btn_refresh.clicked.connect(self._populate_ports)
        ctrl.addWidget(btn_refresh)

        # Cable selector
        self.combo_cable = QComboBox()
        self.combo_cable.setStyleSheet(self.combo_port.styleSheet())
        self.combo_cable.setFixedWidth(130)
        for key, label in [
            (CABLE_AUTO,       "Auto-detect"),
            (CABLE_ROSS_TECH,  "Ross-Tech"),
            (CABLE_FTDI,       "FTDI KKL"),
            (CABLE_CH340,      "CH340 KKL"),
        ]:
            self.combo_cable.addItem(label, key)
        ctrl.addWidget(self.combo_cable)

        main.addLayout(ctrl)

        # ── Button row ────────────────────────────────────────────────────────
        btns = QHBoxLayout()
        btns.setSpacing(6)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setStyleSheet(self._btn_style(C_GREEN))
        self.btn_connect.clicked.connect(self._on_connect)
        btns.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setStyleSheet(self._btn_style(C_RED))
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        btns.addWidget(self.btn_disconnect)

        self.btn_gauges = QPushButton("Gauges ▼")
        self.btn_gauges.setStyleSheet(self._btn_style(C_BLUE))
        self.btn_gauges.setEnabled(False)
        self.btn_gauges.clicked.connect(self._toggle_gauges)
        btns.addWidget(self.btn_gauges)

        self.btn_mock = QPushButton("⚙ Mock ECU")
        self.btn_mock.setStyleSheet(self._btn_style("#aa66ff"))
        self.btn_mock.setToolTip("Start a simulated ECU for development and testing")
        self.btn_mock.clicked.connect(self._toggle_mock)
        btns.addWidget(self.btn_mock)

        main.addLayout(btns)

        # ── Fault code row ────────────────────────────────────────────────────
        fault_row = QHBoxLayout()
        fault_row.setSpacing(6)

        self.btn_read_faults = QPushButton("Read Faults")
        self.btn_read_faults.setStyleSheet(self._btn_style(C_AMBER))
        self.btn_read_faults.setEnabled(False)
        self.btn_read_faults.clicked.connect(self._on_read_faults)
        fault_row.addWidget(self.btn_read_faults)

        self.btn_clear_faults = QPushButton("Clear Faults")
        self.btn_clear_faults.setStyleSheet(self._btn_style(C_RED))
        self.btn_clear_faults.setEnabled(False)
        self.btn_clear_faults.clicked.connect(self._on_clear_faults)
        fault_row.addWidget(self.btn_clear_faults)

        self.lbl_fault_count = QLabel("No faults read")
        self.lbl_fault_count.setStyleSheet(
            f"color:{C_DIM}; font-size:10px; font-family:Consolas;")
        fault_row.addWidget(self.lbl_fault_count, 1)

        main.addLayout(fault_row)

        # ── Fault list (hidden until faults found) ────────────────────────────
        self.fault_list = QLabel("")
        self.fault_list.setWordWrap(True)
        self.fault_list.setStyleSheet(
            f"background:#1a0a0a; color:{C_AMBER}; font-size:10px; "
            f"font-family:Consolas; padding:6px 8px; border-radius:3px;")
        self.fault_list.setVisible(False)
        main.addWidget(self.fault_list)

        # ── Status strip ──────────────────────────────────────────────────────
        self.status_strip = QLabel("  Ready")
        self.status_strip.setStyleSheet(
            f"background:{C_PANEL}; color:{C_DIM}; font-size:10px; "
            f"padding:3px 8px; border-radius:3px;")
        self.status_strip.setWordWrap(True)
        main.addWidget(self.status_strip)

        # ── Mock scenario strip (hidden until mock running) ─────────────────
        self.scenario_strip = QLabel("")
        self.scenario_strip.setStyleSheet(
            f"background:#1a0a2a; color:#aa66ff; font-size:10px; "
            f"font-family:Consolas; padding:3px 8px; border-radius:3px;")
        self.scenario_strip.setVisible(False)
        main.addWidget(self.scenario_strip)

        # ── Gauge panel (hidden by default) ───────────────────────────────────
        self.gauge_panel = QWidget()
        self.gauge_panel.setVisible(False)
        gauge_layout = QGridLayout(self.gauge_panel)
        gauge_layout.setContentsMargins(0, 4, 0, 0)
        gauge_layout.setSpacing(6)

        self.gauge_rpm     = GaugeWidget("RPM",      "rpm",  0, 7000, show_bar=True)
        self.gauge_coolant = GaugeWidget("Coolant",  "°C",  -10, 130)
        self.gauge_intake  = GaugeWidget("Intake",   "°C",  -20, 80)
        self.gauge_load    = GaugeWidget("Load",     "%",    0, 100,  show_bar=True)
        self.gauge_lambda  = GaugeWidget("Lambda",   "λ",    0.5, 1.5)
        self.gauge_timing  = GaugeWidget("Timing",   "°BTDC", -10, 45)
        self.gauge_battery = GaugeWidget("Battery",  "V",    10, 16)
        self.gauge_speed   = GaugeWidget("Speed",    "km/h", 0, 260,  show_bar=True)

        gauges = [
            (self.gauge_rpm,     0, 0),
            (self.gauge_coolant, 0, 1),
            (self.gauge_intake,  0, 2),
            (self.gauge_load,    0, 3),
            (self.gauge_lambda,  1, 0),
            (self.gauge_timing,  1, 1),
            (self.gauge_battery, 1, 2),
            (self.gauge_speed,   1, 3),
        ]
        for widget, row, col in gauges:
            gauge_layout.addWidget(widget, row, col)

        main.addWidget(self.gauge_panel)

        self.resize(WINDOW_W, COMPACT_H)

    def _btn_style(self, colour: str) -> str:
        return (
            f"QPushButton {{ background:{C_PANEL}; color:{colour}; "
            f"border:1px solid {colour}33; border-radius:3px; "
            f"padding:5px 14px; font-size:11px; }}"
            f"QPushButton:hover {{ background:{colour}22; }}"
            f"QPushButton:disabled {{ color:{C_DIM}; border-color:{C_BORDER}; }}")

    def _populate_ports(self):
        """Populate the port combo from available serial ports."""
        self.combo_port.clear()
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            self.combo_port.addItem("No ports found", "")
            return
        for p in ports:
            # Label shows port + cable hint
            vid = p.vid or 0
            pid = p.pid or 0
            if vid == 0x0403 and pid in (0xC33A, 0xC33B, 0xC33C, 0xFF00):
                hint = " ★ Ross-Tech"
            elif vid == 0x0403:
                hint = " FTDI"
            elif vid == 0x1A86:
                hint = " CH340"
            else:
                hint = ""
            self.combo_port.addItem(f"{p.device}{hint}", p.device)

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._signals.connected.connect(self._on_ecu_connected)
        self._signals.disconnected.connect(self._on_ecu_disconnected)
        self._signals.data_ready.connect(self._on_data)
        self._signals.error.connect(self._on_error)

        # Refresh timer for status strip
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_status_strip)
        self._timer.start(500)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_connect(self):
        port  = self.combo_port.currentData() or self.combo_port.currentText()
        cable = self.combo_cable.currentData()

        if not port:
            self._set_status("No port selected", C_AMBER)
            return

        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.dot.setStyleSheet(f"color:{C_AMBER}; font-size:14px;")
        self._set_status(f"Connecting to {port}…", C_AMBER)

        self._worker = ConnectionWorker(
            port=port, cable=cable,
            groups=self._groups,
            signals=self._signals)
        self._worker.start()

    def _on_disconnect(self):
        if self._worker:
            self._worker.stop()
            self._worker = None
        self._set_connected_state(False, "Disconnected")

    # ── Mock ECU ──────────────────────────────────────────────────────────────

    def _toggle_mock(self):
        """Start or stop the mock ECU server."""
        if self._mock_server and self._mock_server.is_running():
            self._stop_mock()
        else:
            self._start_mock_dialog()

    def _start_mock_dialog(self):
        """Show ECU picker and start mock server."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QRadioButton, \
                                    QDialogButtonBox, QButtonGroup

        dlg = QDialog(self)
        dlg.setWindowTitle("Start Mock ECU")
        dlg.setStyleSheet(f"background:{C_BG}; color:{C_TEXT};")
        dlg.setFixedWidth(320)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        lay.addWidget(QLabel(
            "Select ECU to simulate.\n"
            "Scenarios loop: Cold Start → Idle → Cruise → WOT → Decel",
        ))

        grp = QButtonGroup(dlg)
        rb_7a   = QRadioButton("7A 20v  (893906266D)  — MMS05C  [Audi 80/90 2.3 20v]")
        rb_7a.setChecked(True)
        rb_aah  = QRadioButton("AAH V6  (4A0906266)   — MMS100  [Audi 100/S4 2.8 V6]")
        rb_digi = QRadioButton("Digifant 1  (037906023) — G60/G40  [VW Corrado/Golf/Polo]")
        for rb in (rb_7a, rb_aah, rb_digi):
            rb.setStyleSheet(f"color:{C_TEXT};")
            grp.addButton(rb)
            lay.addWidget(rb)

        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setStyleSheet(f"color:{C_TEXT};")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)

        if dlg.exec_() != QDialog.Accepted:
            return

        if rb_7a.isChecked():    ecu = "7a"
        elif rb_aah.isChecked(): ecu = "aah"
        else:                    ecu = "digifant"
        self._start_mock(ecu)

    def _start_mock(self, ecu: str):
        """Start the mock server and auto-connect."""
        try:
            from ..mock.server import MockServer
            import time

            self._mock_server = MockServer(
                ecu=ecu, port=DEFAULT_PORT, poll_hz=3.0)
            self._mock_server.start()
            self._mock_warmup_start = time.time()

            self.btn_mock.setText("⚙ Stop Mock")
            self.btn_mock.setStyleSheet(self._btn_style("#ff6644"))
            self.scenario_strip.setVisible(True)
            self._set_status(f"Mock ECU running — {ecu.upper()} on :{DEFAULT_PORT}", "#aa66ff")

            # Auto-connect after a brief settle
            QTimer.singleShot(300, self._on_connect)

            # Scenario update timer
            self._scenario_timer = QTimer(self)
            self._scenario_timer.timeout.connect(self._update_scenario_strip)
            self._scenario_timer.start(500)

        except Exception as e:
            self._set_status(f"Mock start failed: {e}", C_RED)
            self._mock_server = None

    def _stop_mock(self):
        """Stop mock server and disconnect."""
        if hasattr(self, '_scenario_timer'):
            self._scenario_timer.stop()
        if self._mock_server:
            self._mock_server.stop()
            self._mock_server = None
        self._on_disconnect()
        self.btn_mock.setText("⚙ Mock ECU")
        self.btn_mock.setStyleSheet(self._btn_style("#aa66ff"))
        self.scenario_strip.setVisible(False)
        self._set_status("Mock ECU stopped", C_DIM)

    def _update_scenario_strip(self):
        """Update the scenario progress strip while mock is running."""
        if not self._mock_server or not self._mock_server.is_running():
            return
        try:
            import time
            mod = "ecu_7a" if getattr(self._mock_server, 'ecu', '7a') == "7a" else                   "ecu_digifant" if getattr(self._mock_server, 'ecu', '') in                       ("digifant", "g60", "g40") else None
            if mod is None:
                return
            import importlib
            _m = importlib.import_module(f"kwpbridge.mock.{mod}")
            get_scenario_info = _m.get_scenario_info
            SCENARIO_DURATION = _m.SCENARIO_DURATION
            if self._mock_warmup_start:
                t = time.time()
                info = get_scenario_info(t, self._mock_warmup_start)
                pct = int(info["progress"] * 100)
                loop_pct = int((info["loop_time"] / info["loop_total"]) * 100)
                bar_w = 20
                filled = int(bar_w * info["progress"])
                bar = "█" * filled + "░" * (bar_w - filled)
                self.scenario_strip.setText(
                    f"  ⚙ MOCK  [{bar}] {info['scenario']}  {pct}%  "
                    f"(loop {loop_pct}%)")
        except Exception:
            pass



    def _on_ecu_connected(self, ecu_id_dict: dict):
        pn   = ecu_id_dict.get('part_number', 'Unknown')
        comp = ecu_id_dict.get('component', '')
        self._current_ecu_id = ecu_id_dict   # stored for TCP broadcast

        # Load label file
        self._lbl = self._lbl_registry.get(pn)
        lbl_note  = f"  ✓ labels loaded" if self._lbl else "  (no label file)"

        self.banner.setText(f"{pn}  —  {comp}{lbl_note}")
        self.banner.setStyleSheet(
            f"color:{C_GREEN}; font-size:12px; font-family:Consolas;")

        # Update groups from LBL if available
        if self._lbl:
            self._groups = list(self._lbl.groups()) or [0]
            self._worker.groups = self._groups

        self._set_connected_state(True, f"Connected — {pn}")
        self.btn_gauges.setEnabled(True)
        self.btn_read_faults.setEnabled(True)
        self.btn_clear_faults.setEnabled(True)
        # Start TCP bridge server so HachiROM/other tools can connect
        if not hasattr(self, '_tcp_server') or not self._tcp_server:
            self._start_tcp_bridge()

    def _on_ecu_disconnected(self, reason: str):
        self._set_connected_state(False, f"Disconnected: {reason}")
        self.btn_gauges.setEnabled(False)
        self.btn_read_faults.setEnabled(False)
        self.btn_clear_faults.setEnabled(False)
        self.lbl_fault_count.setText("No faults read")
        self.fault_list.setVisible(False)
        self._clear_gauges()

    # ── Fault code handlers ───────────────────────────────────────────────────

    def _on_read_faults(self):
        """Request fault codes from connected ECU or mock server."""
        if self._mock_server and self._mock_server.is_running():
            # Read from mock directly
            faults = self._mock_server._fault_codes
            self._display_faults(faults)
            return
        if self._worker and hasattr(self._worker, '_kwp') and self._worker._kwp:
            try:
                from ..protocol import KWPError
                faults = self._worker._kwp.read_faults()
                self._display_faults([f.__dict__ for f in faults])
            except Exception as e:
                self._set_status(f"Read faults error: {e}", C_AMBER)

    def _on_clear_faults(self):
        """Clear stored fault codes."""
        if self._mock_server and self._mock_server.is_running():
            self._mock_server.clear_faults()
            self._display_faults([])
            self._set_status("Faults cleared (mock)", C_GREEN)
            return
        if self._worker and hasattr(self._worker, '_kwp') and self._worker._kwp:
            try:
                from ..protocol import KWPError
                self._worker._kwp.clear_faults()
                self._display_faults([])
                self._set_status("Faults cleared", C_GREEN)
            except Exception as e:
                self._set_status(f"Clear faults error: {e}", C_AMBER)

    def _display_faults(self, faults: list):
        """Update fault display area with fault list."""
        if not faults:
            self.lbl_fault_count.setText("✓  No faults stored")
            self.lbl_fault_count.setStyleSheet(
                f"color:{C_GREEN}; font-size:10px; font-family:Consolas;")
            self.fault_list.setVisible(False)
            return

        count = len(faults)
        self.lbl_fault_count.setText(
            f"⚠  {count} fault{'s' if count > 1 else ''} stored")
        self.lbl_fault_count.setStyleSheet(
            f"color:{C_AMBER}; font-size:10px; font-family:Consolas;")

        lines = []
        for f in faults:
            if isinstance(f, dict):
                code = f.get('code', f.get('code_str', '???'))
                desc = f.get('description', '')
                status = f.get('status', f.get('status_str', ''))
            else:
                code   = getattr(f, 'code_str', str(f))
                desc   = getattr(f, 'description', '')
                status = getattr(f, 'status_str', '')
            lines.append(f"  {code}  {desc}  [{status}]")

        self.fault_list.setText("\n".join(lines))
        self.fault_list.setVisible(True)

    def _on_data(self, data: dict):
        self._last_data = data
        self._update_gauges(data)
        # Broadcast to TCP clients if server is running
        if hasattr(self, '_tcp_server') and self._tcp_server:
            try:
                import json, time
                payload = {}
                for group, block in data.items():
                    payload[str(group)] = block.as_dict()
                msg = json.dumps({
                    "type": "state",
                    "data": {
                        "connected":   True,
                        "ecu_id":      self._current_ecu_id,
                        "groups":      payload,
                        "faults":      [],
                        "fault_count": 0,
                        "timestamp":   time.time(),
                    }
                }) + "\n"
                self._tcp_server._broadcast_raw(msg.encode())
            except Exception as e:
                log.debug(f"TCP broadcast error: {e}")

    def _start_tcp_bridge(self):
        """Start a minimal TCP bridge server for IPC with other tools."""
        try:
            from ..server import KWPServer
            import threading, socket, json

            class _MiniBridge:
                """Minimal TCP server — accepts clients and broadcasts state."""
                def __init__(self, port: int = DEFAULT_PORT):
                    self.port    = port
                    self._clients: list[socket.socket] = []
                    self._lock   = threading.Lock()
                    self._sock:  socket.socket | None = None
                    self._thread: threading.Thread | None = None
                    self._running = False

                def start(self):
                    self._running = True
                    self._thread = threading.Thread(
                        target=self._accept, daemon=True, name="kwp-mini-tcp")
                    self._thread.start()

                def stop(self):
                    self._running = False
                    if self._sock:
                        try: self._sock.close()
                        except Exception: pass

                def _accept(self):
                    try:
                        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        self._sock.bind(("127.0.0.1", self.port))
                        self._sock.listen(8)
                        self._sock.settimeout(1.0)
                        log.info(f"KWPBridge TCP bridge on port {self.port}")
                        while self._running:
                            try:
                                conn, _ = self._sock.accept()
                                with self._lock:
                                    self._clients.append(conn)
                                # Send welcome
                                welcome = json.dumps({
                                    "type": "connected",
                                    "version": __version__}) + "\n"
                                conn.sendall(welcome.encode())
                            except socket.timeout:
                                continue
                            except Exception:
                                break
                    except OSError as e:
                        log.warning(f"TCP bridge could not bind port {self.port}: {e}")

                def _broadcast_raw(self, data: bytes):
                    with self._lock:
                        dead = []
                        for c in self._clients:
                            try: c.sendall(data)
                            except Exception: dead.append(c)
                        for c in dead:
                            self._clients.remove(c)

            self._tcp_server = _MiniBridge(DEFAULT_PORT)
            self._tcp_server.start()
        except Exception as e:
            log.warning(f"Could not start TCP bridge: {e}")
            self._tcp_server = None

    def _on_error(self, msg: str):
        self._set_status(msg, C_AMBER)

    # ── Gauge logic ───────────────────────────────────────────────────────────

    def _toggle_gauges(self):
        self._gauges_visible = not self._gauges_visible
        self.gauge_panel.setVisible(self._gauges_visible)
        self.btn_gauges.setText("Gauges ▲" if self._gauges_visible else "Gauges ▼")
        self.setFixedHeight(GAUGE_H if self._gauges_visible else COMPACT_H)

    def _update_gauges(self, data: dict):
        """
        Map measuring block data to gauge widgets.
        Handles both MeasuringBlock objects (real KWP) and dicts (mock/TCP).
        Uses LBL formula when available for real KWP data.
        """
        for group, block in data.items():
            # Determine cell list — real object or dict
            if hasattr(block, 'cells'):
                # Real MeasuringBlock from ConnectionWorker
                for cell in block.cells:
                    raw_word = cell.raw_a * 256 + cell.raw_b
                    if self._lbl:
                        decoded, unit, _ = decode_with_lbl(
                            self._lbl, group, cell.index, float(raw_word))
                        label = self._lbl.get_label(group, cell.index).lower()
                    else:
                        decoded = cell.value
                        unit    = cell.unit
                        label   = cell.label.lower()
                    self._route_to_gauge(label, decoded, raw_word)
            elif isinstance(block, dict):
                # Dict from mock broadcast — already decoded by ecu_7a.py
                for cell in block.get('cells', []):
                    decoded = cell.get('value', 0)
                    label   = cell.get('label', '').lower()
                    raw     = cell.get('value', 0)  # already decoded
                    self._route_to_gauge(label, decoded, raw)

    def _route_to_gauge(self, label: str, decoded: float, raw: float):
        """Route a decoded value to the appropriate gauge by label keyword.
        Handles both umlaut and ASCII-fallback label variants.
        """
        kw = label.lower()
        # RPM — umlaut and ASCII variants
        if any(w in kw for w in ('drehzahl', 'rpm', 'motordrehzahl')):
            if decoded > 100:
                self.gauge_rpm.update_value(decoded,
                    C_RED if decoded > 6400 else C_GREEN)
        # Coolant — umlaut and ASCII variants
        elif any(w in kw for w in ('kühlmittel', 'kuehlmittel', 'coolant', 'kühl')):
            self.gauge_coolant.update_value(decoded,
                C_RED if decoded > 105 else C_AMBER if decoded < 70 else C_GREEN)
        # Intake air
        elif any(w in kw for w in ('ansaug', 'intake', 'lufttemperatur')):
            self.gauge_intake.update_value(decoded)
        # Load
        elif any(w in kw for w in ('motorlast', 'load', 'last')):
            pct = (decoded / 255) * 100 if decoded > 1 else decoded
            self.gauge_load.update_value(pct,
                C_RED if pct > 90 else C_GREEN)
        # Lambda — already decoded as λ value from LBL formula or LiveValues
        elif any(w in kw for w in ('lambda', 'lambdaregelung')):
            # If decoded is already λ (0.5-2.0 range), use directly
            # If it looks like raw (50-200), convert
            lam = decoded if decoded < 5.0 else decoded / 128.0
            self.gauge_lambda.update_value(lam,
                C_GREEN if 0.95 <= lam <= 1.05 else C_AMBER)
        # Ignition timing — umlaut and ASCII
        elif any(w in kw for w in ('zündwinkel', 'zuendwinkel', 'timing', 'ignition', 'ign')):
            self.gauge_timing.update_value(decoded)
        # Battery
        elif any(w in kw for w in ('batterie', 'battery', 'voltage', 'spannung')):
            self.gauge_battery.update_value(decoded,
                C_RED if decoded < 11.5 or decoded > 15 else C_GREEN)
        # Speed
        elif any(w in kw for w in ('geschwindigkeit', 'vehicle speed', 'km/h')):
            self.gauge_speed.update_value(decoded)

    def _clear_gauges(self):
        for g in (self.gauge_rpm, self.gauge_coolant, self.gauge_intake,
                  self.gauge_load, self.gauge_lambda, self.gauge_timing,
                  self.gauge_battery, self.gauge_speed):
            g.update_value(None)

    # ── Status helpers ────────────────────────────────────────────────────────

    def _set_connected_state(self, connected: bool, message: str):
        self.btn_connect.setEnabled(not connected)
        self.btn_disconnect.setEnabled(connected)
        colour = C_GREEN if connected else C_RED
        self.dot.setStyleSheet(f"color:{colour}; font-size:14px;")
        self._set_status(message, colour)

    def _set_status(self, message: str, colour: str = C_DIM):
        self.status_strip.setText(f"  {message}")
        self.status_strip.setStyleSheet(
            f"background:{C_PANEL}; color:{colour}; font-size:10px; "
            f"padding:3px 8px; border-radius:3px;")

    def _refresh_status_strip(self):
        """Update status strip with latest data summary.
        Handles both MeasuringBlock objects (real KWP) and dicts (mock/TCP).
        """
        if not self._last_data:
            return
        parts = []
        for group, block in self._last_data.items():
            cells = []
            if hasattr(block, 'cells'):
                # Real MeasuringBlock object
                cells = block.cells[:4]
                for cell in cells:
                    if getattr(cell, 'display', None) and cell.display != "—":
                        parts.append(f"{cell.label}: {cell.display}")
            elif isinstance(block, dict):
                # Dict from mock/TCP broadcast
                for cell in block.get('cells', [])[:4]:
                    d = cell.get('display', '')
                    l = cell.get('label', '')
                    if d and l:
                        parts.append(f"{l}: {d}")
        if parts:
            self._set_status("  ·  ".join(parts[:3]), C_DIM)

    def closeEvent(self, event):
        if self._worker:
            self._worker.stop()
        if hasattr(self, '_scenario_timer'):
            self._scenario_timer.stop()
        if self._mock_server:
            self._mock_server.stop()
        if hasattr(self, '_tcp_server') and self._tcp_server:
            self._tcp_server.stop()
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────

def run_gui(port: str = "", cable: str = CABLE_AUTO,
            labels_path: str = "", groups: list[int] = None):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(C_BG))
    pal.setColor(QPalette.WindowText,      QColor(C_TEXT))
    pal.setColor(QPalette.Base,            QColor(C_PANEL))
    pal.setColor(QPalette.AlternateBase,   QColor(C_PANEL))
    pal.setColor(QPalette.Text,            QColor(C_TEXT))
    pal.setColor(QPalette.Button,          QColor(C_PANEL))
    pal.setColor(QPalette.ButtonText,      QColor(C_TEXT))
    pal.setColor(QPalette.Highlight,       QColor(C_GREEN))
    pal.setColor(QPalette.HighlightedText, QColor("#000"))
    app.setPalette(pal)

    win = KWPBridgeWindow(port=port, cable=cable,
                          labels_path=labels_path, groups=groups)
    win.show()
    sys.exit(app.exec_())


def main():
    parser = argparse.ArgumentParser(prog="kwpbridge-gui")
    parser.add_argument("--port",   "-p", default="",      help="Serial port")
    parser.add_argument("--cable",  "-c", default=CABLE_AUTO)
    parser.add_argument("--labels", "-l", default="",
                        help="Path to additional label files directory")
    parser.add_argument("--vcds-labels", default="",
                        help="Path to VCDS Labels folder "
                             "(e.g. C:/Ross-Tech/VCDS/Labels). "
                             "Auto-detected on Windows if not specified.")
    parser.add_argument("--groups", "-g", nargs="+", type=int, default=[0],
                        help="Measuring block groups to poll")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S")

    run_gui(port=args.port, cable=args.cable,
            labels_path=args.labels or args.vcds_labels,
            groups=args.groups)


if __name__ == "__main__":
    main()
