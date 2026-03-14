# KWPBridge

[![CI](https://github.com/dspl1236/KWPBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/dspl1236/KWPBridge/actions/workflows/ci.yml)
[![Download](https://img.shields.io/github/v/release/dspl1236/KWPBridge?label=Download&logo=windows)](https://github.com/dspl1236/KWPBridge/releases/latest/download/KWPBridge.exe)

**[⬇ Download KWPBridge.exe (Windows)](https://github.com/dspl1236/KWPBridge/releases/latest/download/KWPBridge.exe)**

---

KWP1281 / K-Line diagnostic bridge for VAG vehicles — connects to a vehicle
ECU via a KKL or Ross-Tech cable, reads live measuring blocks and fault codes,
and broadcasts the data over a local TCP socket so other tools can consume it.

Built for Hitachi MMS-family ECUs (7A 20v, AAH V6) alongside the
[HachiROM](https://github.com/dspl1236/HachiROM) and
[audi90-teensy-ecu](https://github.com/dspl1236/audi90-teensy-ecu) projects.

---

## Architecture

```
Vehicle ECU
  | K-line (12V)
KKL / Ross-Tech cable (USB)
  | Virtual COM port
KWPBridge process  ← python -m kwpbridge --port COM3
  | TCP localhost:50266  (JSON lines)
  |
  +-- HachiROM GUI  (live data overlay on fuel/timing maps)
  +-- Digital dash  (future)
  +-- Data logger   (future)
  +-- Any tool that imports kwpbridge.client
```

**Detection pattern:** client apps call `kwpbridge.client.is_running()` on
startup. If `True`, KWP features are enabled. If `False`, they stay hidden.
No configuration needed — KWPBridge owns the serial port, clients just connect.

---

## Supported ECUs

| ECU | Platform | Address |
|-----|---------|---------|
| 893906266D | MMS05C (7A Late, 4-plug) | 0x01 |
| 893906266B | MMS-04B (7A Early, 2-plug) | 0x01 |
| 4A0906266 | MMS100 (AAH V6 12v) | 0x01 |
| 8A0906266A | MMS-200 (AAH/ACK V6) | 0x01 |

Any ECU at address 0x01 with KWP1281 should work — the above have known
measuring block label definitions built in.

---

## Supported Cables

| Cable | Type | Notes |
|-------|------|-------|
| Ross-Tech HEX+KKL (genuine) | `ross_tech` | **Recommended.** Handles 5-baud init in hardware. Most reliable. |
| FTDI-based KKL (generic) | `ftdi` | Software 5-baud init. Usually works. |
| CH340-based KKL (cheap) | `ch340` | Software 5-baud init via break. May be unreliable. |

Auto-detection from USB VID/PID is the default (`--cable auto`).

---

## Quick Start

```bash
pip install kwpbridge

# List serial ports (shows cable type hints)
python -m kwpbridge --list-ports

# Test connection — print ECU ID and group 1
python -m kwpbridge --port COM3 --scan

# Run bridge (broadcast to localhost:50266)
python -m kwpbridge --port COM3

# With specific options
python -m kwpbridge --port COM3 --cable ross_tech --groups 1 2 3 4 8 --poll-hz 5
```

---

## Measuring Block Groups (7A ECU)

| Group | Cell 1 | Cell 2 | Cell 3 | Cell 4 |
|-------|--------|--------|--------|--------|
| 1 | Engine Speed | Coolant Temp | Lambda Control | CO Pot ADC |
| 2 | Engine Speed | Engine Load | Injection Timing | MAF (G70) |
| 3 | Engine Speed | MAF (G70) | Throttle Angle | Ignition Timing |
| 4 | Engine Speed | Battery Voltage | Coolant Temp | Intake Air Temp |
| 5 | Engine Speed | Engine Load | Vehicle Speed | Load Status |
| 6 | Engine Speed | Engine Load | Intake Air Temp | Altitude Factor |
| 8 | Engine Speed | CO Pot ADC | CO Pot Status | CO Pot Trim |

**Group 8 — CO Pot calibration:**
Cell 4 should read `128` (0x80) when correctly calibrated. This matches
ROM scalar `0x0777` on the 266D/266B. The VCDS basic setting procedure
adjusts the pot until this reads 128.

---

## IPC Protocol

KWPBridge listens on `127.0.0.1:50266` (TCP). All messages are
newline-delimited JSON.

### Server → Client

```json
{"type": "connected", "version": "0.1.0", "port": 50266}

{"type": "state", "data": {
  "connected": true,
  "ecu_id": {"part_number": "893906266D", "component": "2.3 20V MOTRONIC"},
  "groups": {
    "1": {
      "group": 1,
      "timestamp": 1741234567.123,
      "cells": [
        {"index": 1, "label": "Engine Speed",  "value": 850.0,  "unit": "RPM",  "display": "850 RPM"},
        {"index": 2, "label": "Coolant Temp",  "value": 87.5,   "unit": "°C",   "display": "87.5 °C"},
        {"index": 3, "label": "Lambda Control","value": 0.9985, "unit": "λ",    "display": "0.9985 λ"},
        {"index": 4, "label": "CO Pot ADC",    "value": 128.0,  "unit": "",     "display": "128"}
      ]
    }
  },
  "faults": [],
  "fault_count": 0,
  "error": ""
}}
```

### Client → Server

```json
{"cmd": "read_faults"}
{"cmd": "clear_faults"}
{"cmd": "basic_setting", "group": 8}
{"cmd": "set_groups", "groups": [1, 2, 3]}
{"cmd": "get_state"}
```

---

## Client Library

```python
from kwpbridge.client import KWPClient, is_running

# Simple check
if not is_running():
    print("KWPBridge not running — start with: python -m kwpbridge --port COM3")

# Subscribe to live data
client = KWPClient()
client.on_state(lambda s: print(f"RPM: {s['groups']['1']['cells'][0]['value']}"))
client.connect()

# Single snapshot
from kwpbridge.client import get_state
state = get_state()
if state:
    rpm = state['groups']['1']['cells'][0]['value']
```

---

## Development

```bash
git clone https://github.com/dspl1236/KWPBridge
cd KWPBridge
pip install -e ".[dev]"
pytest tests/
```

Built with [Claude](https://anthropic.com) (Anthropic) as development partner.

---

## Related Projects

- [HachiROM](https://github.com/dspl1236/HachiROM) — ROM editor for Hitachi MMS ECUs
- [audi90-teensy-ecu](https://github.com/dspl1236/audi90-teensy-ecu) — Teensy 4.1 EPROM emulator
