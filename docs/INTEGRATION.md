# KWPBridge Integration Guide

How to add live ECU data to a ROM editing tool (HachiROM, ME7Tuner, etc.).

---

## Overview

KWPBridge is a separate process that owns the serial port and broadcasts
live ECU data over TCP on `localhost:50266`. ROM tools connect as clients —
they never touch the serial port directly.

```
KWPBridge GUI  ←→  K-line  ←→  ECU
     ↓
  TCP :50266  (JSON lines)
     ↓
  ROM tool (client) — enables features when bridge is running
```

**The safety rule:** A ROM tool must verify the connected ECU part number
matches the loaded ROM before enabling any editing features.

---

## Minimal Integration (3 steps)

### Step 1 — Add dependency

```toml
# pyproject.toml
[project.optional-dependencies]
kwp = ["kwpbridge>=0.1.0"]
```

Or just copy `kwpbridge/client.py` — it has no dependencies beyond stdlib.

### Step 2 — Detect KWPBridge on startup

```python
from kwpbridge.client import is_running, KWPClient

# In your app's startup / ROM load handler:
if is_running():
    self._kwp = KWPClient()
    self._kwp.on_connect(self._on_kwp_connect)
    self._kwp.on_state(self._on_kwp_state)
    self._kwp.on_disconnect(self._on_kwp_disconnect)
    self._kwp.connect(auto_reconnect=True)
    self._enable_live_features(True)
else:
    self._enable_live_features(False)
```

### Step 3 — Gate editing on ECU match

```python
def _on_kwp_connect(self):
    pass  # wait for first state

def _on_kwp_state(self, state: dict):
    if not state.get('connected'):
        self._enable_editing(False)
        return

    ecu_pn = state.get('ecu_id', {}).get('part_number', '')
    rom_pn = self.loaded_rom.variant.part_number  # from your ROM tool

    if ecu_pn == rom_pn:
        self._enable_editing(True)
        self._update_live_display(state)
    else:
        self._enable_editing(False)
        self._show_mismatch_warning(ecu_pn, rom_pn)

def _on_kwp_disconnect(self):
    self._enable_editing(False)
    self._clear_live_display()
```

---

## Data Format

KWPBridge broadcasts JSON lines on the TCP socket.

### State message

```json
{
  "type": "state",
  "data": {
    "connected": true,
    "ecu_id": {
      "part_number": "893906266D",
      "component":   "2.3 20V MOTRONIC"
    },
    "groups": {
      "0": {
        "group": 0,
        "timestamp": 1741234567.123,
        "cells": [
          {"index": 1, "label": "Kühlmitteltemperatur", "value": 87.0,  "unit": "°C",  "display": "87.0 °C"},
          {"index": 2, "label": "Motorlast",            "value": 128.0, "unit": "",    "display": "128"},
          {"index": 3, "label": "Motordrehzahl",        "value": 3200.0,"unit": "RPM", "display": "3200 RPM"},
          {"index": 8, "label": "Lambdaregelung",       "value": 128.0, "unit": "",    "display": "128"}
        ]
      }
    },
    "faults":      [],
    "fault_count": 0,
    "timestamp":   1741234567.123
  }
}
```

### Commands (client → server)

```json
{"cmd": "read_faults"}
{"cmd": "clear_faults"}
{"cmd": "basic_setting", "group": 8}
{"cmd": "set_groups", "groups": [0, 1, 2]}
{"cmd": "get_state"}
```

---

## Getting Values

```python
# Quick helper — no need to parse the full state dict manually
client = KWPClient()

# After connecting:
rpm     = client.get_value(group=0, cell=3)   # Motordrehzahl
coolant = client.get_value(group=0, cell=1)   # Kühlmitteltemperatur
load    = client.get_value(group=0, cell=2)   # Motorlast
lambda_ = client.get_value(group=0, cell=8)   # Lambdaregelung
```

---

## ECU Part Number → Group Numbers

Different ECU generations use different group numbering:

| ECU family | Groups | Notes |
|-----------|--------|-------|
| 7A MMS-04B / MMS05C (266B, 266D) | 0 | Single group, 10 cells |
| AAH MMS100 (4A0906266) | 0, 1, 2 | Multiple groups |
| ME7.x (later Bosch) | 1, 2, 3... | 1-based, more groups |
| Motronic 2.3/2.3.2 | 0, 1... | Varies by variant |

KWPBridge reads the groups defined in the `.lbl` file for the connected ECU,
so the group numbers are handled automatically.

---

## Safety Gate Pattern

Always use this pattern before enabling any ROM editing:

```python
def editing_allowed(self) -> bool:
    """True only when a verified matching ECU is connected."""
    if not self._kwp or not self._kwp.connected:
        return False
    state = self._kwp.state
    if not state or not state.get('connected'):
        return False
    ecu_pn = state.get('ecu_id', {}).get('part_number', '')
    if not ecu_pn:
        return False
    if not self.loaded_rom:
        return False
    return ecu_pn.upper() == self.loaded_rom.variant.part_number.upper()
```

Show a clear indicator in the UI:
- 🔴 KWPBridge not running — editing available, no ECU verification
- 🟡 KWPBridge running, ECU part number mismatch — editing locked
- 🟢 KWPBridge running, ECU matches loaded ROM — editing + live data enabled

---

## TCP Port

KWPBridge always uses `localhost:50266`.

```python
from kwpbridge.constants import DEFAULT_PORT  # 50266
```

This port is fixed and documented so all tools can find it without
configuration. Do not make it user-configurable in consumer tools.

---

## Future: Flashing via KWPBridge

KWP1281 supports memory write commands (`writeMemByAddr`) used by some
flashing tools. When flash support is added to KWPBridge:

- Flash operations will require an **authenticated session** — KWPBridge
  will reject flash commands unless the ECU part number matches a verified
  ROM image
- Only **Ross-Tech genuine cables** will be supported for flashing —
  timing requirements for write cycles are too tight for CH340/FTDI dumb cables
- ROM tools send a `{"cmd": "flash", "image": "<base64>"}` command —
  KWPBridge handles all timing-critical byte-level operations

---

## Adding Support for a New ECU

1. Get a `.lbl` file for the ECU (from VCDS install or community)
2. Add it to `labels/` directory with the correct filename (`{part-number}.lbl`)
3. Add an `ECUDef` entry in `kwpbridge/ecu_defs.py` with group/cell labels
   and known fault codes
4. If the ECU uses a different KWP address, update `constants.py`
5. Test with `python -m kwpbridge --port COM3 --scan`

That's it — KWPBridge will automatically find the label file and use it
for any ROM tool that connects.


---

## Live Overlay Interface

ROM tools remain fully functional offline. When KWPBridge is running
and the connected ECU part number matches the loaded ROM, live data
is available as a **read-only overlay** on map tabs.

### Overlay States

```
🔴  KWPBridge not running       — ROM tool works normally, no overlay
🟡  KWPBridge running, mismatch — warn user, no overlay, editing locked
🟢  KWPBridge running, matched  — full overlay enabled, editing unlocked
```

### What the overlay shows

**On any 2D map tab (fuel, timing, knock):**

```
┌──────────────────────────────────────────────────────┐
│  Primary Fueling                    [🟢 LIVE · 2450 RPM · 43% load] │
├────────┬──────┬──────┬──────┬──────┬──────┬──────┤
│        │  750 │ 1000 │ 1500 │ 2000 │ 2500 │ ...  │
├────────┼──────┼──────┼──────┼──────┼══════╪──────┤  ← RPM cursor
│  20%   │  ... │  ... │  ... │  ... │ ░░░░ │  ... │  ← active cell
│  30%   │  ... │  ... │  ... │  ... │ ░░░░ │  ... │    (highlighted)
│  40%   │  ... │  ... │  ... │  ... │ ████ │  ... │  ← load cursor
│  50%   │  ... │  ... │  ... │  ... │ ░░░░ │  ... │
└──────────────────────────────────────────────────────┘
  λ 0.998 · ign 18.2°  ← live values for current operating point
```

- **Active cell** — bright border, colour tint based on lambda
  - Green tint: lambda 0.95–1.05 (at target)
  - Amber tint: lambda 0.85–0.95 or 1.05–1.15 (off target)
  - Red tint:   lambda < 0.85 or > 1.15 (significantly off)
- **RPM cursor** — vertical highlight line on nearest RPM axis column
- **Load cursor** — horizontal highlight line on nearest load axis row
- **Status strip** — live RPM, load, lambda, timing for current point

**Overview tab status banner:**
```
🟢 KWPBridge · 893906266D · 2450 RPM · 87°C · λ 0.998 · 18.2° ign
```

**Hardware tab — CO pot live value:**
```
CO Pot ADC:  [128] ████████████░░░░░░░░  target: 128  ✓ calibrated
```

### Implementation

```python
# Each MapTab subscribes to KWPBridge state
class MapTab(QWidget):
    def __init__(self, ...):
        self._kwp: KWPClient | None = None
        self._live_rpm:  float | None = None
        self._live_load: float | None = None
        self._live_lambda: float | None = None

    def attach_kwp(self, client: KWPClient):
        """Called by MainWindow when KWPBridge connects + ECU matches."""
        self._kwp = client
        self._kwp.on_state(self._on_kwp_state)

    def detach_kwp(self):
        self._kwp = None
        self._clear_overlay()

    def _on_kwp_state(self, state: dict):
        # Extract RPM and load from group 0 (7A) or group 1 (later ECUs)
        # Update overlay — never touches ROM data
        rpm  = _extract(state, group=0, cell=3)   # Motordrehzahl
        load = _extract(state, group=0, cell=2)   # Motorlast
        lam  = _extract(state, group=0, cell=8)   # Lambdaregelung → λ
        self._update_overlay(rpm, load, lam)

    def _update_overlay(self, rpm, load, lam):
        # Find nearest axis indices
        rpm_idx  = _nearest(self.map_def.rpm_axis,  rpm)
        load_idx = _nearest(self.map_def.load_axis, load)
        # Highlight active cell, draw cursor lines
        # Colour tint based on lambda
        ...
```

---

## Future: Assisted Editing (Spitballing)

Ideas for using live data to help with ROM edits. None of this is
implemented — documenting the concepts while the architecture is fresh.

### 1. Cell trail logging

As the ECU moves through the map during a drive or dyno run, log
which cells were visited and the lambda/timing at each point.
After the session, the map tab shows a heat map of coverage —
cells visited frequently are brighter, unvisited cells are dim.

Useful for: identifying which cells actually need tuning vs which
are never hit in normal driving.

```python
# Accumulated during a KWPBridge session
cell_visits: dict[tuple[int,int], list[float]] = {}
# (rpm_idx, load_idx) → [lambda readings at that cell]
```

### 2. Lambda deviation overlay

For each visited cell, compare the live lambda reading to the
map value. Show the deviation as a colour gradient:

```
Cell value says λ 1.0 — ECU actually ran λ 0.92 (8% rich)
→ tint cell amber, show "-8%" annotation
```

After a full drive cycle, you'd have a deviation map showing
exactly which cells need enriching or leaning. The user still
makes the edit manually — the overlay just shows the direction
and magnitude.

### 3. Suggested corrections

More ambitious: accumulate enough lambda samples at a cell to
suggest a correction.

```
Cell [2500 RPM, 40% load]: visited 47 times
  Mean lambda: 0.918  (target: 1.000)
  Suggested correction: +9.5% fuel  (+12 raw counts)
  [Apply suggestion] [Skip] [Log only]
```

The user reviews and approves each suggestion. The ROM tool
applies the edit to the in-memory snapshot — never auto-commits
to the ROM. User still saves and burns manually.

Risks to document clearly:
- Lambda sensor accuracy — wideband more trustworthy than narrowband O2
- Transient enrichment can skew samples — need steady-state filtering
- Load calculation vs actual load — MAF-based ECUs can disagree with MAP
- Cell interpolation — ECU blends adjacent cells, corrections compound

### 4. Closed-loop assisted tuning (very long term)

The ECU already does closed-loop lambda correction internally
(the lambda control value in group 0 cell 8). If you can read
the long-term and short-term trim values, you know exactly how
much the ECU is already correcting for — and you can fold that
correction into the base map.

```
Short-term trim: +6%   (ECU adding fuel right now)
Long-term trim:  +4%   (ECU has learned to add fuel here)
→ Base map is 10% lean at this point
→ Suggested base map correction: +10%
```

This is essentially what professional ECU calibration software
does. The difference is that here the ROM is an EPROM that needs
to be physically burned — so the workflow is:
  1. Drive → collect data → review suggestions → approve
  2. Apply corrections to ROM snapshot
  3. Save → burn new chip → drive again → repeat

Not real-time closed-loop tuning, but assisted iterative tuning
with a physical chip swap between sessions. Until the Teensy
emulator is in the loop, at which point a new map could be loaded
to the SD card without removing the ECU.

### 5. Teensy + KWPBridge combined workflow (future)

When both are running:

```
KWPBridge reads live data from ECU via K-line
     ↓
HachiROM shows overlay + suggests corrections
     ↓
User approves correction set
     ↓
HachiROM writes updated ROM to Teensy SD card slot
     ↓
Teensy loads new ROM on next ignition cycle
     ↓
No chip burning required — iterate in minutes not hours
```

This is the end-game for the whole project stack. The EPROM
emulator removes the physical chip-swap bottleneck and makes
iterative tuning practical on a stock ECU without a dyno.

---

## Overlay API (planned, not yet implemented)

```python
# kwpbridge/overlay.py (future)

class MapOverlay:
    """
    Read-only live data overlay for ROM tool map tabs.
    Consumes KWPBridge state, never modifies ROM data.
    """

    def attach(self, client: KWPClient, map_def: MapDef,
               ecu_def: ECUDef): ...

    def detach(self): ...

    # State
    @property
    def active_cell(self) -> tuple[int, int] | None: ...
    @property
    def live_lambda(self) -> float | None: ...
    @property
    def live_timing(self) -> float | None: ...

    # Signals
    cell_changed    = Signal(int, int)   # (rpm_idx, load_idx)
    lambda_changed  = Signal(float)
    overlay_lost    = Signal()           # KWPBridge disconnected

    # Future
    def start_logging(self): ...
    def stop_logging(self) -> CellLog: ...
    def get_suggestions(self, log: CellLog) -> list[CellCorrection]: ...
```
