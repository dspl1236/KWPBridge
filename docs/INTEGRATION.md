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
