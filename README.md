# KWPBridge

[![CI](https://github.com/dspl1236/KWPBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/dspl1236/KWPBridge/actions/workflows/ci.yml)
[![Download](https://img.shields.io/github/v/release/dspl1236/KWPBridge?label=Download&logo=windows)](https://github.com/dspl1236/KWPBridge/releases/latest/download/KWPBridge.exe)

**[⬇ Download KWPBridge.exe (Windows)](https://github.com/dspl1236/KWPBridge/releases/latest/download/KWPBridge.exe)**

---

K-Line diagnostic bridge for VAG vehicles. Connects to an ECU via a KKL or Ross-Tech cable, auto-detects the protocol (KWP1281 for pre-2002, KWP2000 for ME7.x and later), reads live measuring blocks and fault codes, and broadcasts everything over a local TCP socket so companion tools can consume it without owning the serial port.

Part of a broader VAG ECU toolchain alongside [HachiROM](https://github.com/dspl1236/HachiROM), [UrROM](https://github.com/dspl1236/UrROM), and [audi90-teensy-ecu](https://github.com/dspl1236/audi90-teensy-ecu).

---

## Protocol support

| Protocol | Init | Baud | ECU families |
|----------|------|------|-------------|
| **KWP1281** | 5-baud slow init | 10400 | Hitachi MMS-04B/05C (7A, AAH), Bosch Motronic 2.x, M2.3.2 (AAN/ABY/ADU), Digifant 1 — pre-2002 |
| **KWP2000** / ISO 14230 | Fast init | 10400 | Bosch ME7.x, MED7.x, Siemens Simos — post-2001 |

**Auto-detection** (default `--protocol auto`) tries KWP1281 first, then KWP2000 — the same order VCDS uses. Each protocol gets two attempts; a 2-second K-line settle gap separates the two. Status messages stream to the GUI and CLI in real time:

```
Trying kwp1281...  attempt 1/2...
  ✗ kwp1281 attempt 1: 5-baud init timeout — no response from ECU
Waiting 2s before trying kwp2000...
Trying kwp2000...  attempt 1/2...
  ✓ kwp2000  06A906032BN  1.8l T  ME7.5
```

You can also force a specific protocol with `--protocol kwp1281` or `--protocol kwp2000`.

---

## Architecture

```
Vehicle ECU
  │ K-line (12V)
KKL / Ross-Tech cable (USB → virtual COM)
  │ 10400 baud
KWPBridge process        python -m kwpbridge --port COM3
  │ TCP 127.0.0.1:50266  (newline-delimited JSON)
  │
  ├── KWPBridge GUI  (gauges, fault codes, label-file decoded values)
  ├── HachiROM       (live overlay on 7A / AAH fuel & timing maps)
  ├── UrROM          (live overlay on M2.3.2 / ME7 fuel & boost maps)
  └── Any tool       kwpbridge.client.is_running() / KWPClient()
```

KWPBridge owns the serial port exclusively. Companion apps just connect to the TCP socket — they never touch the port themselves and can start or stop independently.

---

## Quick start

```bash
pip install kwpbridge

# List available serial ports with cable type hints
python -m kwpbridge --list-ports

# Identify the ECU and print group 1 (auto-detects protocol)
python -m kwpbridge --port COM3 --scan

# Force KWP2000 scan (ME7 bench setup)
python -m kwpbridge --port COM3 --protocol kwp2000 --cable ross_tech --scan

# Run the bridge (auto protocol, broadcasts on localhost:50266)
python -m kwpbridge --port COM3

# ME7.5 AWP — KWP2000, groups 1+2+3+91 (RPM/load/MAF + boost)
python -m kwpbridge --port COM3 --protocol kwp2000 --groups 1 2 3 91 --poll-hz 10

# KWP1281 with explicit cable type and groups
python -m kwpbridge --port COM3 --protocol kwp1281 --cable ross_tech --groups 1 2 3 4 8
```

### CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | *(required)* | Serial port — `COM3`, `/dev/ttyUSB0`, etc. |
| `--protocol` | `auto` | `auto` / `kwp1281` / `kwp2000` |
| `--cable` | `auto` | `auto` / `ross_tech` / `ftdi` / `ch340` |
| `--groups` | `1 2 3 4` | Measuring block groups to poll |
| `--poll-hz` | `10` | Target polling rate |
| `--detect-attempts` | `2` | Retries per protocol in auto mode |
| `--ecu-address` | `0x01` | K-line address (engine = 0x01) |
| `--tcp-port` | `50266` | IPC port for client tools |
| `--scan` | — | Connect, print ID + group 1, exit |
| `--list-ports` | — | List serial ports with cable hints, exit |

---

## Supported ECUs

### KWP1281  (pre-2002)

| Part number | ECU | Engine | Vehicle |
|-------------|-----|--------|---------|
| `893 906 266 D` | Hitachi MMS-05C | 7A 2.3 20v (late, 4-plug) | Audi 80/90 1988–1994 |
| `893 906 266 B` | Hitachi MMS-04B | 7A 2.3 20v (early, 2-plug) | Audi 80/90 1988–1990 |
| `4A0 906 266` | Hitachi MMS100 | AAH 2.8 V6 12v | Audi 100/A6/S4 1992–1997 |
| `8A0 906 266 A` | Hitachi MMS-200 | AAH/ACK V6 | Audi 100/A6 1994–1997 |
| `4A0 907 551 AA` | Bosch M2.3.2 | AAN 2.2 20vT (200hp) | Audi S2 Coupé/Avant, 200 Turbo, UrS4 |
| `4A0 907 551 A` | Bosch M2.3.2 | AAN (earlier PN) | as above |
| `895 907 551 A` | Bosch M2.3.2 | ABY 2.2 20vT (230hp) | Audi S2 Coupé/Avant 1992–1995 |
| `8A0 907 551 B` | Bosch M2.3.2 | ADU 2.2 20vT RS2 (315hp) | Audi RS2 Avant 1994–1995 |
| `037 906 023` | Digifant 1 | RV/PL G60/G40 | VW Corrado G60, Golf/Jetta 1990–1992 |
| `037 906 025 ADY` | Motronic 2.x | ADY 2.0 8v | VW Golf/Jetta/Cabrio 1993–1995 |

### KWP2000  (post-2001)

| Part numbers | ECU | Engine | Vehicle |
|--------------|-----|--------|---------|
| `06A 906 032 BN/BH/BD/BG/BF/...` (19 variants) | Bosch ME7.5 | AWP/AUM/AUQ/BAM 1.8T | Audi TT 8N, A4 B6, Golf 4, Jetta 4, Beetle 1.8T |

Any ECU that speaks KWP1281 or KWP2000 at address 0x01 will connect — the above have label files and named fault codes built in.

---

## Measuring blocks — key groups

### KWP1281 ECUs (7A, AAH, M2.3.2)

**7A 20v  — group 0 (single 10-cell block):**

| Cell | Parameter | Decode | Idle spec |
|------|-----------|--------|-----------|
| 1 | Coolant Temperature | raw − 50 = °C | 85–110 °C |
| 2 | Engine Load | raw (1–255) | 20–30 |
| 3 | Engine Speed | raw × 25 = RPM | 750–850 |
| 4–5 | Idle stabilisation (learned/auto) | 0–7 or 249–255 | 0–3 |
| 6 | Idle stab position | 128 = neutral | 126–130 |
| 7 | Switch inputs | manual = 24 | — |
| 8 | Lambda control | 128 = stoich | 118–138 |
| 9 | Distributor position | 0 = centre | 254/255/0/1/2 |
| 10 | Ignition angle | raw × 1.33 = °BTDC | 8–12° |

**Group 8 — CO pot basic setting:** Cell 4 should read `128` (0x80) when calibrated. Matches ROM scalar `0x0777`.

**M2.3.2 (AAN/ABY/ADU) — 8 groups, 4 cells each:**

| Group | Cell 1 | Cell 2 | Cell 3 | Cell 4 |
|-------|--------|--------|--------|--------|
| 1 | RPM (×40) | Coolant °C (−70) | Lambda (/128) | Ignition °BTDC |
| 2 | RPM | IPW ms (×0.52) | Battery V (×0.068) | Atmospheric kPa |
| 3 | RPM | Load (raw) | TPS % (×0.416) | IAT °C (−70) |
| 4 | RPM | Load | VSS km/h (×2) | Throttle switches |
| 5 | RPM | IAC zero point | IAC duty cycle | Load switches |
| 6 | N75 DC % | N75 req % | MAP kPa actual | MAP kPa req |
| 7 | Knock cyl 1–4 (×0.5 units each) | | | |
| 8 | IPW effective ms | Dead-time ms | Actual IPW ms | IDC % |

*Groups 6–8 available on prjmod / 034EFI firmware only.*

### KWP2000 ECUs (ME7.5)

Key groups for the AWP 1.8T:

| Group | Content |
|-------|---------|
| 1 | RPM, coolant °C, lambda controller %, basic setting flags |
| 2 | RPM, engine load %, injection timing ms, MAF g/s |
| 3 | RPM, MAF g/s, throttle angle %, ignition timing °BTDC |
| 4 | RPM, battery V, coolant °C, IAT °C |
| 5 | RPM, load %, VSS km/h, load status |
| 22/23 | RPM, load, knock retard cyl 1–2 / cyl 3–4 (°) |
| 32 | Lambda idle adaptation %, partial throttle adaptation % |
| 33 | Lambda controller %, upstream O2 sensor V |
| 50 | RPM, short-term fuel trim %, long-term fuel trim % |
| 60 | Throttle sensor 1 %, sensor 2 %, adaptation status |
| 91 | RPM, load %, N75 duty cycle %, boost pressure mbar |
| 94 | RPM, load %, ignition actual °BTDC, knock retard total ° |

---

## Cables

| Cable | `--cable` | Init method | Notes |
|-------|-----------|-------------|-------|
| Ross-Tech HEX+KKL (genuine) | `ross_tech` | Handled in firmware | **Recommended.** Most reliable, works with KWP1281 and KWP2000. |
| FTDI-based KKL (generic USB) | `ftdi` | Software break (setBreak) | Usually reliable. |
| CH340-based KKL (cheap clone) | `ch340` | Software break | May be unreliable at K-line timing. |
| Auto-detect from VID/PID | `auto` *(default)* | Per above | Ross-Tech VID 0x0403 PID 0xC33A/B/C auto-selected. |

For a bench setup with direct OBD connection, Ross-Tech HEX+KKL with `--cable ross_tech` is the safest choice. For dumb KKL cables the `setBreak(True/False)` approach works on most FTDI chips.

---

## IPC protocol

`127.0.0.1:50266` — TCP, newline-delimited JSON.

### Server → client

```json
{"type": "connected", "version": "0.9.2", "port": 50266}

{"type": "state", "data": {
  "connected": true,
  "protocol": "kwp2000",
  "ecu_id": {"part_number": "06A906032BN", "component": "1.8l T  ME7.5"},
  "groups": {
    "1": {"group": 1, "timestamp": 1741234567.1, "cells": [
      {"index": 1, "label": "Engine Speed",  "value": 3500.0,  "unit": "RPM",    "display": "3500 RPM"},
      {"index": 2, "label": "Coolant Temp",  "value": 92.0,    "unit": "°C",     "display": "92.0 °C"},
      {"index": 3, "label": "Lambda Factor", "value": 1.0,     "unit": "λ",      "display": "1.000 λ"},
      {"index": 4, "label": "Ignition Angle","value": 22.0,    "unit": "° BTDC", "display": "22.0 °BTDC"}
    ]},
    "91": {"group": 91, "cells": [
      {"index": 4, "label": "Boost Pressure Act", "value": 1620.0, "unit": "mbar", "display": "1620 mbar"}
    ]}
  },
  "faults": [],
  "fault_count": 0,
  "error": "",
  "detect_status": ""
}}
```

### Client → server

```json
{"cmd": "read_faults"}
{"cmd": "clear_faults"}
{"cmd": "set_groups", "groups": [1, 2, 3, 91]}
{"cmd": "get_state"}
{"cmd": "basic_setting", "group": 8}
```

---

## Client library

```python
from kwpbridge.client import KWPClient, is_running

# Check if KWPBridge is running
if not is_running():
    print("Start: python -m kwpbridge --port COM3")

# Subscribe to live data
client = KWPClient()
client.on_state(lambda s: print(
    f"RPM: {s['groups']['1']['cells'][0]['value']:.0f}  "
    f"Protocol: {s.get('protocol', '?')}"
))
client.connect()
```

For GUI integration see `urrom/kwp.py` (UrROM) and `hachirom/kwp.py` (HachiROM) — both implement `KWPMonitor` (Qt QObject with signals) and `LiveValues` with per-ECU decode logic and map overlay support.

---

## Protocol detection API

```python
from kwpbridge import detect_protocol, PROTO_AUTO, PROTO_KWP1281, PROTO_KWP2000

# Auto-detect — tries KWP1281 then KWP2000
result = detect_protocol(port="COM3", cable_type="ross_tech")
if result.success:
    print(f"Protocol: {result.protocol}")        # "kwp1281" or "kwp2000"
    print(f"ECU: {result.ecu_id.part_number}")   # "06A906032BN"
    block = result.connection.read_group(1)      # already connected, poll immediately

# Force a specific protocol
result = detect_protocol(
    port="COM3",
    force_protocol=PROTO_KWP2000,
    cable_type="ross_tech",
    max_attempts=3,
    on_status=print,                             # stream status to stdout
)
```

---

## Mock ECUs (development / testing)

All mock ECUs simulate realistic 5-scenario loops (Cold Start → Warm Idle → Cruise → WOT/Boost → Decel) and produce correctly-encoded protocol bytes.

| Mock | Part number | Engine | Protocol | Duration |
|------|-------------|--------|----------|----------|
| `7a` | 893906266D | 7A 2.3 20v | KWP1281 | 240 s |
| `aah` | 4A0906266 | AAH 2.8 V6 | KWP1281 | — |
| `digifant` | 037906023 | G60/G40 | KWP1281 | 240 s |
| `m232` | 4A0907551AA | AAN 2.2 20vT | KWP1281 | 255 s |
| `me7` | 06A906032BN | AWP 1.8T | KWP2000 | 245 s |

```bash
# Start mock and GUI side-by-side (development)
python -m kwpbridge.mock --ecu me7 &
python -m kwpbridge.gui

# Or use MockServer in tests
from kwpbridge.mock import MockServer
with MockServer(ecu="me7") as srv:
    # srv broadcasts on localhost:50266 at 3 Hz
    pass

# Direct data — no TCP needed
from kwpbridge.mock.ecu_me7 import get_group, get_scenario_info
cells = get_group(91, t=195.0)    # boost group mid-pull
# → N75=41%, boost=1336 mbar
```

The ME7 mock produces real KWP2000 formula-encoded bytes `[formula][A][B]` — correct for protocol testing. The GUI mock dialog auto-sets `--protocol kwp2000` when ME7 is selected.

---

## Label files

1,171 label files (87 engine, 1,084 modules) covering the full VAG KWP1281/KWP2000 model range. The parser handles Ross-Tech `.lbl` format including REDIRECT directives, scaling formulas (`Anzeige mal 25 = RPM`, `minus 50 = °C`, `mal 0.52 = ms`), and spec ranges.

Files relevant to supported ECUs:

| File | ECU | Content |
|------|-----|---------|
| `engine/893-906-266-D.lbl` | 7A Late | Group 0, coding (German original) |
| `engine/893-906-266-D-EN.lbl` | 7A | Groups 0–8 with English scaling formulas |
| `modules/4A0-907-551-AA.lbl` | M2.3.2 AAN/ABY | Groups 1–8, 40 cells, PRJ-sourced scaling |
| `modules/4A0-907-551-C.lbl` | M2.3.2 ADU/RS2 | REDIRECT → 551-AA |
| `modules/895-907-551.lbl` | M2.3.2 ABY S2 | Groups 1–7 (Paul Nugent 2002) |
| `engine/06A-906-032-AWP.lbl` | ME7.5 AWP | Full group set, basic settings, coding |

```python
from kwpbridge.lbl_parser import LBLRegistry

reg = LBLRegistry()
lbl = reg.get("06A906032BN")          # auto-searches engine/ and modules/
print(lbl.summary())                  # "06A906032BN  49 groups  196 cells  0 coding values"
print(lbl.get_label(91, 4))          # "Boost Pressure Act"
```

---

## Development

```bash
git clone https://github.com/dspl1236/KWPBridge
cd KWPBridge
pip install -e ".[dev]"

# Run all 106 tests
pytest tests/

# Run a specific suite
pytest tests/test_protocol_detect.py -v
pytest tests/test_mock_m232.py -v

# Start mock ECU (choose: 7a / aah / digifant / m232 / me7)
python -m kwpbridge.mock --ecu me7
```

### Test coverage

| Suite | Tests | Covers |
|-------|-------|--------|
| `test_protocol.py` | core | KWP1281 framing, checksums, block decode |
| `test_formula.py` | core | All formula byte decode/encode pairs |
| `test_lbl_parser.py` | core | Label file parsing, REDIRECT, formula hints |
| `test_mock_m232.py` | 15 | M2.3.2 mock — all 8 groups, scenarios, server aliases |
| `test_protocol_detect.py` | 14 | Auto-detection, fallthrough, retries, status callback |
| other | ~77 | Full suite |

---

## Related projects

| Project | Description |
|---------|-------------|
| [HachiROM](https://github.com/dspl1236/HachiROM) | ROM editor for Hitachi MMS ECUs (7A, AAH) with live overlay |
| [UrROM](https://github.com/dspl1236/UrROM) | ROM editor for Bosch M2.3 / M2.3.2 (AAN/ABY/ADU/RS2) with live overlay |
| [audi90-teensy-ecu](https://github.com/dspl1236/audi90-teensy-ecu) | Teensy 4.1 EPROM emulator / map switcher for 7A ECU |

---

Built with [Claude](https://anthropic.com) (Anthropic).
