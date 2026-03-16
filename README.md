# KWPBridge

[![CI](https://github.com/dspl1236/KWPBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/dspl1236/KWPBridge/actions/workflows/ci.yml)
[![Download](https://img.shields.io/github/v/release/dspl1236/KWPBridge?label=Download&logo=windows)](https://github.com/dspl1236/KWPBridge/releases/latest/download/KWPBridge.exe)

**[⬇ Download KWPBridge.exe (Windows)](https://github.com/dspl1236/KWPBridge/releases/latest/download/KWPBridge.exe)**

---

K-Line diagnostic bridge for VAG vehicles. Connects to an ECU via a KKL or
Ross-Tech cable, reads live measuring blocks and fault codes, and broadcasts
everything over a local TCP socket so any number of tools can consume it
simultaneously — ROM editors, dashboards, data loggers — without each needing
their own cable connection.

Supports two protocols:

- **KWP1281** — pre-2002 VAG: Hitachi MMS (7A 20v, AAH V6), Digifant
  (G60/G40), Motronic 2.x (2.0 8v), Bosch M2.3.2 (AAN/ABY/ADU 20vT)
- **KWP2000 / ISO 14230** — ME7.x, MED7.x, and most post-2001 VAG

Protocol is **auto-detected by default** — KWPBridge tries KWP1281 first,
then KWP2000, exactly as VCDS does. You can override to force a specific
protocol if you already know what you have.

---

## Architecture

```
Vehicle ECU
  │  K-line (12 V)
KKL / Ross-Tech cable  (USB → virtual COM)
  │
KWPBridge  ──  python -m kwpbridge --port COM3
  │  TCP 127.0.0.1:50266  (newline-delimited JSON)
  │
  ├── HachiROM GUI      live overlay on Hitachi MMS maps
  ├── UrROM GUI         live overlay on Bosch M2.3.2 maps
  ├── KWPBridge GUI     gauges, fault codes, basic settings
  └── Any tool         kwpbridge.client.KWPClient
```

Client apps call `kwpbridge.client.is_running()` on startup. If `True`,
live features activate. If `False`, they stay hidden. KWPBridge owns the
serial port; clients just subscribe.

---

## Supported ECUs

### KWP1281 — pre-2002 VAG

| ECU | Platform | Engine | Notes |
|-----|----------|--------|-------|
| 893906266D | Hitachi MMS05C | 7A 2.3 20v | Late (4-connector, post 03/90) |
| 893906266B | Hitachi MMS-04B | 7A 2.3 20v | Early (2-connector, pre 03/90) |
| 4A0906266 | Hitachi MMS100 | AAH 2.8 V6 12v | Audi 100 / A6 / S4 |
| 8A0906266A | Hitachi MMS-200 | AAH/ACK V6 | Audi A6 / Coupe |
| 037906023 | Digifant 1 | G60 / G40 | VW Corrado / Golf / Polo |
| 037906025-ADY/AFT | Motronic 2.x | 2.0 8v | VW Golf / Jetta / Passat |
| 4A0907551AA/A | Bosch M2.3.2 | AAN 20vT 200hp | Audi 200 / UrS4 |
| 895907551A | Bosch M2.3.2 | ABY 20vT 230hp | Audi S2 Coupe/Avant |
| 4A0907551C | Bosch M2.3.2 | ADU 20vT 315hp | Audi RS2 |

### KWP2000 / ISO 14230 — post-2001 VAG

| ECU | Platform | Engine | Notes |
|-----|----------|--------|-------|
| 06A906032-BN/BH/BD/BG/BF/BE/BB/AY/AX/AS/GD/GC/KL/KN/HS/GF/GG/EB | Bosch ME7.5 | AWP/AUM/AUQ/BAM 1.8T | Audi TT, Golf 4, Jetta 4, New Beetle |

Additional ME7 part numbers are accepted via root PN lookup (`06A906032`).

---

## Supported Cables

| Cable | Type flag | Notes |
|-------|-----------|-------|
| Ross-Tech HEX+KKL (genuine) | `ross_tech` | **Recommended.** 5-baud / fast init handled in firmware. |
| FTDI-based KKL | `ftdi` | Software init. Usually reliable. |
| CH340-based KKL | `ch340` | Software init via serial break. May be unreliable. |
| Any | `auto` | Default — detects cable from USB VID/PID. |

---

## Quick Start

```bash
pip install kwpbridge

# List available serial ports
python -m kwpbridge --list-ports

# Scan: print ECU ID, group 1, faults, then exit
python -m kwpbridge --port COM3 --scan

# Run the bridge (broadcasts on localhost:50266)
python -m kwpbridge --port COM3

# ME7 / KWP2000 with Ross-Tech cable
python -m kwpbridge --port COM3 --cable ross_tech --protocol kwp2000

# ME7 boost and knock monitoring
python -m kwpbridge --port COM3 --protocol kwp2000 --groups 1 2 3 4 91 22 23

# Pre-2002 car, specific groups
python -m kwpbridge --port COM3 --protocol kwp1281 --groups 1 2 3 4 8
```

### Protocol flags

| Flag | Behaviour |
|------|-----------|
| `--protocol auto` | Try KWP1281 first, then KWP2000. **Default.** |
| `--protocol kwp1281` | Force KWP1281 (5-baud slow init). Pre-2002 cars. |
| `--protocol kwp2000` | Force KWP2000 (ISO14230 fast init). ME7+. |

`--detect-attempts N` sets retries per protocol before moving to the next
(default: 2). The GUI status bar streams detection progress live.

---

## Measuring Block Groups

### 7A 20v / AAH V6 (KWP1281)

| Group | Cell 1 | Cell 2 | Cell 3 | Cell 4 |
|-------|--------|--------|--------|--------|
| 1 | Engine Speed | Coolant Temp | Lambda Control | CO Pot ADC |
| 2 | Engine Speed | Engine Load | Injection Timing | MAF (G70) |
| 3 | Engine Speed | MAF (G70) | Throttle Angle | Ignition Timing |
| 4 | Engine Speed | Battery Voltage | Coolant Temp | Intake Air Temp |
| 5 | Engine Speed | Engine Load | Vehicle Speed | Load Status |
| 6 | Engine Speed | Engine Load | Intake Air Temp | Altitude Factor |
| 8 | Engine Speed | CO Pot ADC | CO Pot Status | CO Pot Trim |

**Group 8 Cell 4** should read `128` (0x80) when the CO pot is correctly
calibrated. This matches ROM scalar `0x0777`. The VCDS basic setting
procedure adjusts the pot until Cell 4 reads 128.

### Bosch M2.3.2 — AAN/ABY/ADU 20vT (KWP1281)

| Group | Cell 1 | Cell 2 | Cell 3 | Cell 4 |
|-------|--------|--------|--------|--------|
| 1 | Engine Speed | Coolant Temp | Lambda Factor | Ignition Timing |
| 2 | Engine Speed | Injector Duration | Battery Voltage | Atm. Pressure |
| 3 | Engine Speed | Engine Load | Throttle Angle | Intake Air Temp |
| 4 | Engine Speed | Engine Load | Vehicle Speed | Throttle Switches |
| 5 | Engine Speed | IAC Zero Point | IAC Duty Cycle | Load Switches |
| 6 | N75 Duty Cycle | N75 Request | MAP Actual (kPa) | MAP Request |
| 7 | Knock Sensor 1 | Knock Sensor 2 | Knock Sensor 3 | Knock Sensor 4 |
| 8 | Effective IPW | Injector Dead-time | Actual IPW | Injector Duty Cycle |

Groups 6–8 require prjmod / 034EFI firmware. Stock Bosch firmware does not
expose boost or knock channels.

### Bosch ME7.5 — AWP 1.8T (KWP2000)

| Group | Cell 1 | Cell 2 | Cell 3 | Cell 4 |
|-------|--------|--------|--------|--------|
| 1 | Engine Speed | Coolant Temp | Lambda Controller | Basic Setting Flags |
| 2 | Engine Speed | Engine Load % | Injection Timing ms | MAF g/s |
| 3 | Engine Speed | MAF g/s | Throttle Sensor 1 % | Ignition Timing ° |
| 4 | Engine Speed | Battery V | Coolant Temp | Intake Air Temp |
| 5 | Engine Speed | Engine Load % | Vehicle Speed | Load Status |
| 10 | Engine Speed | Engine Load % | Throttle Sensor 1 % | Ignition Timing ° |
| 22 | Engine Speed | Engine Load % | Cyl 1 KR ° | Cyl 2 KR ° |
| 23 | Engine Speed | Engine Load % | Cyl 3 KR ° | Cyl 4 KR ° |
| 32 | Lambda Idle Adapt % | Lambda Part Adapt % | — | — |
| 33 | Lambda Controller % | O2 Upstream V | — | — |
| 50 | Engine Speed | ST Fuel Trim % | LT Fuel Trim % | — |
| 60 | Throttle Sensor 1 % | Throttle Sensor 2 % | Learn Step | Result |
| 91 | Engine Speed | Engine Load % | N75 Duty Cycle % | Boost Pressure mbar |
| 94 | Engine Speed | Engine Load % | Ignition Actual ° | Knock Retard Total ° |

**Recommended:** `1 2 3 4 91` for daily monitoring. Add `22 23` when tuning
to watch per-cylinder knock retard. Add `32 33 50` to monitor fuel trim
and lambda adaptation.

---

## IPC Protocol

KWPBridge listens on `127.0.0.1:50266`. All messages are newline-delimited JSON.

### Server → Client

```json
{"type": "connected", "version": "0.9.2"}

{"type": "state", "data": {
  "connected": true,
  "protocol": "kwp2000",
  "detect_status": "✓ kwp2000  06A906032BN  1.8l T  ME7.5",
  "ecu_id": {
    "part_number": "06A906032BN",
    "component":   "1.8l T  ME7.5"
  },
  "groups": {
    "1": {
      "group": 1,
      "cells": [
        {"index": 1, "label": "Engine Speed",       "value": 820.0,  "unit": "RPM"},
        {"index": 2, "label": "Coolant Temp",       "value": 90.0,   "unit": "°C"},
        {"index": 3, "label": "Lambda Controller",  "value": 1.2,    "unit": "%"},
        {"index": 4, "label": "Basic Setting Flags","value": 127.0,  "unit": ""}
      ]
    },
    "91": {
      "group": 91,
      "cells": [
        {"index": 1, "label": "Engine Speed",    "value": 3500.0, "unit": "RPM"},
        {"index": 2, "label": "Engine Load",     "value": 42.3,   "unit": "%"},
        {"index": 3, "label": "N75 Duty Cycle",  "value": 22.0,   "unit": "%"},
        {"index": 4, "label": "Boost Pressure",  "value": 1120.0, "unit": "mbar"}
      ]
    }
  },
  "faults": [],
  "fault_count": 0,
  "cable_type": "ross_tech",
  "port": "COM3",
  "error": ""
}}
```

### Client → Server

```json
{"cmd": "read_faults"}
{"cmd": "clear_faults"}
{"cmd": "basic_setting", "group": 8}
{"cmd": "set_groups", "groups": [1, 2, 3, 91]}
{"cmd": "get_state"}
```

---

## Client Library

```python
from kwpbridge.client import KWPClient, is_running

# Check before showing live features in your app
if not is_running():
    print("Start: python -m kwpbridge --port COM3")

# Subscribe to state updates
client = KWPClient()
client.on_state(lambda s: print(
    f"RPM: {s['groups']['1']['cells'][0]['value']:.0f}  "
    f"Boost: {s['groups']['91']['cells'][3]['value']:.0f} mbar"
))
client.connect()

# Single snapshot
from kwpbridge.client import get_state
state = get_state()
if state:
    for cell in state['groups']['1']['cells']:
        print(f"  {cell['label']}: {cell['value']} {cell['unit']}")
```

---

## Mock ECU (development / testing)

KWPBridge includes realistic ECU simulators for all supported platforms.
No cable or vehicle needed — scenarios loop automatically.

```python
from kwpbridge.mock import mock_server

with mock_server(ecu="7a") as srv:       # 7A 20v — MMS05C    [KWP1281]
    ...
with mock_server(ecu="aah") as srv:      # AAH V6 — MMS100    [KWP1281]
    ...
with mock_server(ecu="digifant") as srv: # Digifant G60/G40   [KWP1281]
    ...
with mock_server(ecu="m232") as srv:     # AAN 20vT — M2.3.2  [KWP1281]
    ...
with mock_server(ecu="me7") as srv:      # AWP 1.8T — ME7.5   [KWP2000]
    ...
```

Each mock runs five scenarios — **Cold Start → Warm Idle → Cruise →
WOT/Boost → Decel** — in a continuous loop. All formula bytes are correctly
encoded (`[formula][A][B]`) so `kwpbridge.formula.decode_cell` produces
physically realistic values.

**ME7 mock scenarios (245 s loop):**

| Scenario | Duration | RPM | Load | Boost | Lambda |
|----------|----------|-----|------|-------|--------|
| Cold Start | 60 s | 1100 | 18 % | 970 mbar | 0.93 |
| Warm Idle | 60 s | 820 | 15 % | 960 mbar | 1.00 |
| Cruise | 60 s | 3500 | 40 % | 1100 mbar | 1.00 |
| Boost Pull | 35 s | → 6200 | 170 % | 1650 mbar | 0.88 |
| Decel | 30 s | → 2000 | 5 % | 950 mbar | 1.50 |

In the GUI, click **⚙ Mock ECU** and select the ECU. The protocol combo
auto-sets to KWP2000 when ME7 is selected.

---

## Protocol Auto-Detection

With `--protocol auto` (default), KWPBridge negotiates in the same order
as VCDS:

```
Trying kwp1281...
  kwp1281  attempt 1/2...
  ✗ kwp1281 attempt 1: 5-baud init timeout
  kwp1281  attempt 2/2...
  ✗ kwp1281 attempt 2: 5-baud init timeout
Waiting 2s before trying kwp2000...
Trying kwp2000...
  kwp2000  attempt 1/2...
✓ kwp2000  06A906032BN  1.8l T  ME7.5
```

Status messages stream to the GUI status bar in real time. On a bench setup
with a Ross-Tech cable, KWP1281 fails in ~5 s before falling through. Use
`--protocol kwp2000` to skip this when you already know the ECU.

```python
from kwpbridge import detect_protocol, PROTO_AUTO

result = detect_protocol(port="COM3", cable_type="ross_tech")
if result.success:
    print(f"Protocol: {result.protocol}")
    print(f"ECU:      {result.ecu_id.part_number}")
    # result.connection is live — ready for read_group() calls
    block = result.connection.read_group(1)
```

---

## Label Files

KWPBridge bundles **1,174 VCDS-format label files** covering the full VAG
catalogue. The matching label file loads automatically by part number on
connection, providing cell names, scaling formulas, and spec ranges.

Custom files can be added by placing `.lbl` files in a directory and passing
`--labels-path` to the CLI. The registry searches subdirectories and follows
`REDIRECT` directives.

Key bundled files for supported ECUs:

| File | ECU |
|------|-----|
| `labels/engine/893-906-266-D-EN.lbl` | 7A (late) — Groups 0–8, CO pot, coding |
| `labels/modules/4A0-907-551-AA.lbl` | M2.3.2 AAN/ABY — Groups 1–8, 29 fault codes |
| `labels/modules/4A0-907-551-C.lbl` | M2.3.2 ADU (RS2) — redirects to 551-AA |
| `labels/engine/06A-906-032-AWP.lbl` | ME7.5 AWP — full group set, basic setting |

---

## Development

```bash
git clone https://github.com/dspl1236/KWPBridge
cd KWPBridge
pip install -e ".[dev]"
pytest tests/          # 106 tests
```

Run the GUI without a cable:

```bash
python -m kwpbridge.gui    # use ⚙ Mock ECU to simulate any ECU
```

---

## Related Projects

- [HachiROM](https://github.com/dspl1236/HachiROM) — ROM editor for Hitachi MMS ECUs (7A, AAH). Live overlay via KWPBridge.
- [UrROM](https://github.com/dspl1236/UrROM) — ROM editor for Bosch M2.3.2 (AAN/ABY/ADU). Live overlay via KWPBridge.
- [DigiTool](https://github.com/dspl1236/DigiTool) — ROM editor for Digifant G60/G40.
- [audi90-teensy-ecu](https://github.com/dspl1236/audi90-teensy-ecu) — Teensy 4.1 EPROM emulator / map switcher for M2.3.2.

---

Built with [Claude](https://anthropic.com) (Anthropic) as development partner.
