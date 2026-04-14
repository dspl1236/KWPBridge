# KWPBridge

[![CI](https://github.com/dspl1236/KWPBridge/actions/workflows/build.yml/badge.svg)](https://github.com/dspl1236/KWPBridge/actions/workflows/build.yml)
[![Download](https://img.shields.io/github/v/release/dspl1236/KWPBridge?label=Download&logo=windows)](https://github.com/dspl1236/KWPBridge/releases/latest/download/KWPBridge.exe)

> **⚠ Work in Progress — Use at Your Own Risk**
>
> This tool is under active development. Features may be incomplete, map
> addresses may be unverified, and patches may not have been tested on all
> hardware variants. **Always read and back up your original ROM before making
> any changes.** Read it twice, compare the files, keep both copies safe.
>
> If you find a bug, incorrect address, or have a ROM dump to contribute,
> please [open an issue](https://github.com/dspl1236/KWPBridge/issues).


**[⬇ Download KWPBridge.exe (Windows)](https://github.com/dspl1236/KWPBridge/releases/latest/download/KWPBridge.exe)**

---

K-line diagnostic bridge for VAG vehicles. Connects to an ECU via a generic
KKL 409.1 USB cable (FTDI-based, creates a COM port), reads live measuring
blocks and fault codes, and broadcasts everything over a local TCP socket so
any number of tools can consume it simultaneously — ROM editors, dashboards,
data loggers — without each needing their own serial port connection.

Supports two protocols over K-line:

- **KWP1281** — pre-2002 VAG: Hitachi MMS (7A 20v, AAH V6), Digifant
  (G60/G40), Motronic 2.x (2.0 8v), Bosch M2.3.2 (AAN/ABY/ADU 20vT)
- **KWP2000 / ISO 14230** — Bosch ME7.x, MED7.x, and most post-2001 VAG ECUs

Protocol is **auto-detected by default** — KWPBridge tries KWP1281 first,
then KWP2000, in the same order VCDS uses. Override with `--protocol` when
you already know the ECU.

> **MED9.1 (03H906032 / 1K0907115) — documented, transport not yet
> implemented.** The Bosch MED9.1 ECU uses KWP2000 messages over **TP2.0
> CAN**, not over K-line. KKL cables are not compatible. MED9.1 ECU
> definitions (measuring blocks, fault codes, security access) are present
> in this release for when the CAN transport layer lands. Live connection
> to MED9.1 ECUs requires a CAN interface (SocketCAN / PCAN) and a future
> KWPBridge update. Use [EliasTuning/MED9RamReader](https://github.com/EliasTuning/MED9RamReader)
> in the meantime.

---

## Architecture

```
Vehicle ECU
  │  K-line (12 V single-wire)
KKL 409.1 cable  (USB → virtual COM port)
  │
KWPBridge  ──  python -m kwpbridge --port COM3
  │  TCP 127.0.0.1:50266  (newline-delimited JSON)
  │
  ├── HachiROM          live map overlay — Hitachi MMS (7A, AAH)
  ├── UrROM             live map overlay — Bosch M2.3.2 (AAN/ABY/ADU)
  ├── KWPBridge GUI     gauges, fault codes, basic settings
  └── Any tool          kwpbridge.client.KWPClient
```

Client tools call `kwpbridge.client.is_running()` on startup. If `True`,
live features activate automatically. If `False`, they stay hidden. KWPBridge
owns the serial port; all clients just subscribe over TCP.

---

## Supported ECUs

### KWP1281 — pre-2002 VAG (K-line, KKL cable)

| ECU | Platform | Engine | Vehicle |
|-----|----------|--------|---------|
| 893-906-266-D | Hitachi MMS05C | 7A 2.3 20v | Audi 80/90/Coupe (late, 4-plug, post 03/90) |
| 893-906-266-B | Hitachi MMS-04B | 7A 2.3 20v | Audi 80/90/Coupe (early, 2-plug, pre 03/90) |
| 4A0-906-266 | Hitachi MMS100 | AAH 2.8 V6 12v | Audi 100/A6/UrS4 |
| 8A0-906-266-A | Hitachi MMS-200 | AAH/ACK V6 | Audi A6/Coupe |
| 037-906-023 | Digifant 1 | PL/RV/G60/G40 | VW Corrado/Golf/Polo |
| 037-906-025-ADY/AFT | Motronic 2.x | 2.0 8v | VW Golf/Jetta/Passat |
| 4A0-907-551-AA/A | Bosch M2.3.2 | AAN 20vT 200hp | Audi 200 20vT / UrS4 |
| 895-907-551-A | Bosch M2.3.2 | ABY 20vT 230hp | Audi S2 Coupe/Avant |
| 4A0-907-551-C | Bosch M2.3.2 | ADU 20vT 315hp | Audi RS2 Avant |

### KWP2000 / ISO 14230 — post-2001 VAG (K-line, KKL cable)

| ECU | Platform | Engine | Vehicle |
|-----|----------|--------|---------|
| 06A-906-032-BN/BH/BD/BG/BF/BE/BB | Bosch ME7.5 | AWP 1.8T 180hp | Audi TT 225 / Golf 4 GTI / Jetta GLI |
| 06A-906-032-AY/AX/AS | Bosch ME7.5 | AUM 1.8T 150hp | Audi A3 / Golf 4 |
| 06A-906-032-GD/GC/KL/KN | Bosch ME7.5 | AUQ 1.8T 180hp | Audi A3 / Seat Leon / Skoda |
| 06A-906-032-HS/GF/GG/EB | Bosch ME7.5 | BAM/AWW 1.8T | Audi TT / VW Golf 4 |
| 06A-906-032 | Bosch ME7.5 | AWP/AUM/AUQ/BAM | Root PN — accepts all variants |

Additional ME7 part numbers are resolved via root PN fallback. Total: 19 known part numbers.

### KWP2000 over TP2.0 CAN — documented, transport not yet implemented

> These ECUs are **defined** in KWPBridge (measuring blocks, fault codes,
> security access keys) but require a CAN transport layer that is not yet
> built. KKL cables are not compatible. Listed here for future reference.

| ECU | Platform | Engine | Vehicle |
|-----|----------|--------|---------|
| 03H-906-032-BE/BG/CA/DA/EK/L/DQ | Bosch MED9.1 | VR6 3.6L FSI | Porsche Cayenne / VW Touareg / Q7 |
| 03H-906-026 | Bosch MED9.1 | BUB 3.2L VR6 | VW Golf R32 MK5 / Audi TT 3.2 |
| 1K0-907-115-S/C/F/L | Bosch MED9.1 | EA113 2.0 TFSI | VW Golf V 2.0 TFSI / Audi A3 |
| 1K8-907-115-F/L | Bosch MED9.1 | EA113 2.0 TFSI | VW Golf VI 2.0 TFSI |

MED9.1 live access: CAN address 0x01, TP2.0 transport, KWP2000 service layer.
Security access READ: `key = (seed + 0x11170) & 0xFFFFFFFF`.
Security access WRITE (SA2): 5-round rotate-left XOR `0x5FBD5DBD`.
For offline ROM editing, see [MED9Tool](https://github.com/dspl1236/MED9Tool).

---

## Supported Cables

**You need a cable that creates a virtual COM port.** Ross-Tech HEX-V2
cables do NOT work — they use a proprietary USB protocol that only VCDS
can talk to. Use a generic FTDI-based KKL cable instead (~$15 on Amazon).

**MED9.1 ECUs require a CAN interface, not a KKL cable.** See the
TP2.0/CAN section above.

| Cable | `--cable` flag | Notes |
|-------|---------------|-------|
| FTDI-based KKL (generic 409.1) | `ftdi` | **Recommended.** Real FTDI FT232RL chip. Creates COM port. ~$15. |
| CH340-based KKL | `ch340` | Budget option. Creates COM port. May be unreliable on some systems. |
| Ross-Tech KKL-USB (old, discontinued) | `ross_tech` | Legacy. Older FTDI-based Ross-Tech cables that created COM ports. Cable firmware handles 5-baud init. |
| Any | `auto` | **Default.** Detects cable type from USB VID/PID on connection. |

**NOT compatible:**
- Ross-Tech HEX-V2 (current product) — proprietary USB, no COM port
- Ross-Tech HEX-USB+CAN — proprietary USB, no COM port
- Any cable that doesn't appear in Device Manager as a COM port

FTDI VID `0x0403` with generic PID `0x6001` = standard KKL cable.
FTDI VID `0x0403` PIDs `0xC33A/C33B/C33C/FF00` = old Ross-Tech KKL-USB.
VID `0x1A86` (Nuvoton) = CH340.

---

## Quick Start

```bash
pip install kwpbridge

# List available serial ports with cable type hints
python -m kwpbridge --list-ports

# Scan: connect, print ECU ID + group 1 + faults, then exit
python -m kwpbridge --port COM3 --scan

# Run the bridge (broadcasts on localhost:50266)
python -m kwpbridge --port COM3

# ME7 / KWP2000 (if using legacy Ross-Tech KKL-USB cable)
python -m kwpbridge --port COM3 --protocol kwp2000

# ME7 — boost + knock monitoring
python -m kwpbridge --port COM3 --protocol kwp2000 --groups 1 2 3 4 91 22 23

# M2.3.2 AAN — all useful groups
python -m kwpbridge --port COM3 --protocol kwp1281 --groups 1 2 3 4 5 6

# Pre-2002 car, explicit protocol (skip auto-detection)
python -m kwpbridge --port COM3 --protocol kwp1281 --groups 1 2 3 4 8
```

### Protocol flags

| Flag | Behaviour |
|------|-----------|
| `--protocol auto` | Try KWP1281 first, then KWP2000. **Default.** |
| `--protocol kwp1281` | Force KWP1281 (5-baud slow init). Pre-2002 VAG. |
| `--protocol kwp2000` | Force KWP2000 (ISO14230 fast init). ME7+ / post-2001 VAG. |

`--detect-attempts N` sets how many times each protocol is tried before
moving on (default: 2). Use on flaky cables or long wiring.

---

## Measuring Block Groups

### 7A 20v / AAH V6 (KWP1281)

| Group | Cell 1 | Cell 2 | Cell 3 | Cell 4 |
|-------|--------|--------|--------|--------|
| 0 | Coolant Temp | Engine Load | Engine Speed | Idle Stab |
| 1 | Engine Speed | Coolant Temp | Lambda Control | CO Pot ADC |
| 2 | Engine Speed | Engine Load | Injection Timing | MAF (G70) |
| 3 | Engine Speed | MAF (G70) | Throttle Angle | Ignition Timing |
| 4 | Engine Speed | Battery Voltage | Coolant Temp | Intake Air Temp |
| 5 | Engine Speed | Engine Load | Vehicle Speed | Load Status |
| 6 | Engine Speed | Engine Load | Intake Air Temp | Altitude Factor |
| 8 | Engine Speed | CO Pot ADC | CO Pot Status | CO Pot Trim |

**Group 0** is the Hitachi single-measurement block (10 cells). Groups 1–8
follow standard VAG 4-cell layout.

**Group 8 / CO pot basic setting:** Cell 4 should read `128` (0x80) when the
CO pot is correctly calibrated. This value is written to ROM scalar `0x0777`.
Run VCDS basic setting on group 8 to calibrate.

### Bosch M2.3.2 — AAN/ABY/ADU 20vT (KWP1281)

| Group | Cell 1 | Cell 2 | Cell 3 | Cell 4 |
|-------|--------|--------|--------|--------|
| 1 | Engine Speed | Coolant Temp | Lambda Factor | Ignition Timing |
| 2 | Engine Speed | Injector Duration (ms) | Battery Voltage | Atm. Pressure |
| 3 | Engine Speed | Engine Load | Throttle Angle | Intake Air Temp |
| 4 | Engine Speed | Engine Load | Vehicle Speed | Throttle Switches |
| 5 | Engine Speed | IAC Zero Point | IAC Duty Cycle | Load Switches |
| 6 | N75 Duty Cycle | N75 Request | MAP Actual (kPa) | MAP Request |
| 7 | Knock Sensor 1 | Knock Sensor 2 | Knock Sensor 3 | Knock Sensor 4 |
| 8 | Effective IPW | Injector Dead-time | Actual IPW | Injector Duty Cycle |

**Groups 6–8** require prjmod or 034EFI firmware. Stock Bosch chips do not
expose boost pressure, knock sensors, or full injection detail. Use `--groups 1 2 3 4 5 6` with a tuned chip.

Scaling (from PRJ WinlogDriver.cpp source): RPM = raw × 40, ECT/IAT = (raw − 70) × 0.7 °C,
Lambda = raw / 128, MAP = raw / 1.035 kPa (MPXH6400A sensor), IPW = raw × 0.52 ms.

### Bosch ME7.5 — AWP/AUM/AUQ/BAM 1.8T (KWP2000)

| Group | Cell 1 | Cell 2 | Cell 3 | Cell 4 |
|-------|--------|--------|--------|--------|
| 1 | Engine Speed | Coolant Temp | Lambda Controller % | Basic Setting Flags |
| 2 | Engine Speed | Engine Load % | Injection Timing ms | MAF g/s |
| 3 | Engine Speed | MAF g/s | Throttle Sensor 1 % | Ignition Timing ° |
| 4 | Engine Speed | Battery V | Coolant Temp | Intake Air Temp |
| 5 | Engine Speed | Engine Load % | Vehicle Speed | Load Status |
| 10 | Engine Speed | Engine Load % | Throttle Sensor 1 % | Ignition Timing ° |
| 14 | Engine Speed | Engine Load % | Misfire Counter | Misfire Recognition |
| 15 | Cyl 1 Misfire | Cyl 2 Misfire | Cyl 3 Misfire | Malfunction Recog. |
| 16 | Cyl 4 Misfire | Malfunction Recog. | — | — |
| 22 | Engine Speed | Engine Load % | Cyl 1 KR ° | Cyl 2 KR ° |
| 23 | Engine Speed | Engine Load % | Cyl 3 KR ° | Cyl 4 KR ° |
| 28 | Engine Speed | Engine Load % | Coolant Temp | Knock Sensor Test |
| 30 | O2 Status B1S1 | O2 Status B1S2 | — | — |
| 32 | Lambda Idle Adapt % | Lambda Part Adapt % | — | — |
| 33 | Lambda Controller % | O2 Upstream V | — | — |
| 34 | Engine Speed | Catalyst Temp | Period Duration | Lambda Aging |
| 36 | O2 S2 Downstream V | Lambda Availability | — | — |
| 41 | Engine Speed | Engine Load % | Injector Bank 1 | Injector Bank 2 |
| 43 | Engine Speed | Engine Load % | Injector Cyl 1 | Injector Cyl 2 |
| 46 | Engine Speed | Engine Load % | Injector Cyl 3 | Injector Cyl 4 |
| 50 | Engine Speed | ST Fuel Trim % | LT Fuel Trim % | — |
| 54 | Engine Speed | Load % | O2 Upstream V | O2 Downstream V |
| 55 | Engine Speed | Load % | Catalyst Efficiency | — |
| 56 | Engine Speed | Coolant Temp | Catalyst Temp | — |
| 60 | Throttle Sensor 1 % | Throttle Sensor 2 % | Learn Step | Result |
| 61 | Engine Speed | Voltage Supply | Throttle Actuator | Op. Condition |
| 62 | Throttle S1 | Throttle S2 | Throttle Pos (G79) | Accel Pedal S2 |
| 66 | Engine Speed | Engine Load % | EVAP Purge Valve | Fuel Pressure |
| 70 | Engine Speed | Engine Load % | Catalyst Temp B1 | Catalyst Temp B2 |
| 77 | Engine Speed | Engine Load % | EGR Valve Position | EGR Duty Cycle |
| 89 | Engine Speed | Coolant Temp | Engine Load % | Barometric Pressure |
| 91 | Engine Speed | Engine Load % | N75 Duty Cycle % | Boost Pressure mbar |
| 94 | Engine Speed | Engine Load % | Ignition Actual ° | Knock Retard Total ° |
| 99 | Readiness Code | — | — | — |

**Recommended group sets:**

| Use case | Groups |
|----------|--------|
| Daily monitoring | `1 2 3 4 91` |
| Tune / knock watch | `1 2 3 4 91 22 23 94` |
| Lambda / fuel trim | `1 32 33 50 54` |
| Throttle / EPC | `3 60 61 62` |
| Full diagnostic | `1 2 3 4 5 10 22 23 28 32 33 50 60 91 94` |

**Basic Setting Flags (Group 1 Cell 4):** Each bit enables/disables a
readiness condition. All 8 bits set = `0b11111111` = 255 = all conditions
met. Bit 0 = coolant < 80°C, Bit 1 = RPM < 2000, Bit 2 = throttle closed,
Bit 3 = lambda regulation correct, Bit 4 = idle state, Bit 5 = A/C off,
Bit 6 = catalyst > 350°C, Bit 7 = no faults.

### Bosch MED9.1 — VR6/TFSI (KWP2000 over TP2.0 CAN) — definitions only

> **Live CAN connection not yet implemented.** The following measuring
> block definitions are embedded in `ecu_defs.py` and will be available
> for display once the TP2.0 transport layer is added.

45 measuring groups defined (1–114), covering: engine speed/load/lambda
dual-bank, 6-cylinder knock retard, dual camshaft adjustment, HPFP/LPFP
rail pressure, boost pressure setpoint/actual. 59 fault codes including
6-cylinder injectors/misfires, dual-bank O2/catalyst, HPFP, and Bosch
Immo4 CAN DTCs.

---

## Protocol Auto-Detection

With `--protocol auto` (the default), KWPBridge negotiates in the same
order as VCDS — oldest protocol first:

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

Status messages stream to the GUI status bar in real time. KWP1281 failure
typically takes 5–8 s on a bench setup before falling through to KWP2000.
Use `--protocol kwp2000` to skip this when the ECU is known.

```python
from kwpbridge import detect_protocol

result = detect_protocol(port="COM3", cable_type="ross_tech")
if result.success:
    print(f"Protocol: {result.protocol}")       # 'kwp1281' or 'kwp2000'
    print(f"ECU:      {result.ecu_id.part_number}")
    # result.connection is live — ready for read_group() calls immediately
    block = result.connection.read_group(1)
else:
    print(f"No ECU: {result.summary()}")
```

---

## IPC Protocol (TCP)

KWPBridge listens on `127.0.0.1:50266`. All messages are newline-delimited JSON.

### Server → Client

```json
{"type": "connected", "version": "0.9.9"}

{"type": "state", "data": {
  "connected": true,
  "protocol":  "kwp2000",
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
        {"index": 2, "label": "Coolant Temp",        "value": 90.0,   "unit": "°C"},
        {"index": 3, "label": "Lambda Controller",   "value": 1.2,    "unit": "%"},
        {"index": 4, "label": "Basic Setting Flags", "value": 127.0,  "unit": ""}
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

### Client → Server (commands)

```json
{"cmd": "read_faults"}
{"cmd": "clear_faults"}
{"cmd": "basic_setting", "group": 8}
{"cmd": "set_groups", "groups": [1, 2, 3, 91]}
{"cmd": "get_state"}
```

---

## Cell Value Encoding (Formula Bytes)

Every measuring block cell is encoded as `[formula_byte][A][B]` where
`value = fn(A, B)`. KWP1281 and KWP2000 use the same formula table.

| Byte | Name | Decode | Unit |
|------|------|--------|------|
| `0x08` | Engine Speed | (A×256+B) × 0.25 | RPM |
| `0x04` | Load / Duty Cycle | (A×256+B) × 0.01 | % |
| `0x10` | Percentage | (A×256+B) × 0.01 | % |
| `0x12` | Temperature | (A×256+B) × 0.1 − 273.15 | °C |
| `0x14` | Temperature (simple) | A − 48 | °C |
| `0x07` | Voltage | (A×256+B) × 0.001 | V |
| `0x11` | Voltage (0.001 V) | (A×256+B) × 0.001 | V |
| `0x02` | MAF | (A×256+B) × 0.01 | g/s |
| `0x06` | MAF (alt) | (A×256+B) × 0.01 | kg/h |
| `0x09` | Ignition / Timing | (A×256+B) × 0.1 − 100 | ° BTDC |
| `0x0A` | Timing (alt) | (A×256+B) × 0.1 − 100 | ° |
| `0x05` | Lambda | (A×256+B) × 0.0001 + 0.5 | λ |
| `0x27` | Lambda (alt) | (A×256+B) × 0.0001 + 0.5 | λ |
| `0x0B` | Pressure (kPa) | (A×256+B) × 0.01 | kPa |
| `0x0C` | Pressure (mbar) | (A×256+B) × 0.01 | mbar |
| `0x0D` | Injection Time | (A×256+B) × 0.001 | ms |
| `0x0E` | Time | (A×256+B) × 0.001 | ms |
| `0x0F` | Vehicle Speed | (A×256+B) × 0.01 | km/h |
| `0x13` | Throttle Position | (A×256+B) × 0.01 | % |
| `0x03` | Binary / Status | A = status flags | — |
| `0x01` | Raw (counts) | A×256+B | — |
| `0xFF` | Raw (alt) | A×256+B | — |

```python
from kwpbridge.formula import decode_cell

value, unit, display = decode_cell(0x08, 0x0D, 0x00)
# → (832.0, 'RPM', '832 RPM')

value, unit, display = decode_cell(0x12, 0x0E, 0x3F)
# → (91.6, '°C', '91.6 °C')

value, unit, display = decode_cell(0x05, 0x1A, 0x00)
# → (1.0, 'λ', '1.000 λ')
```

---

## Client Library

```python
from kwpbridge.client import KWPClient, is_running

# Check whether KWPBridge is running before enabling live features
if not is_running():
    print("Start KWPBridge: python -m kwpbridge --port COM3")

# Subscribe to state updates
client = KWPClient()
client.on_state(lambda s: print(
    f"RPM: {s['groups']['1']['cells'][0]['value']:.0f}  "
    f"Boost: {s['groups']['91']['cells'][3]['value']:.0f} mbar  "
    f"Protocol: {s.get('protocol', '?')}"
))
client.connect()

# Read faults
client.on_state(None)
faults = client.read_faults()
for f in faults:
    print(f"  {f['code']}: {f['description']}")
```

---

## Mock ECU Server

KWPBridge includes realistic ECU simulators for all supported platforms.
No cable or vehicle needed. Scenarios loop automatically, covering cold
start through WOT and back.

```python
from kwpbridge.mock import mock_server

with mock_server(ecu="7a")       as srv: ...  # 7A 20v — MMS05C     [KWP1281]
with mock_server(ecu="aah")      as srv: ...  # AAH V6 — MMS100     [KWP1281]
with mock_server(ecu="digifant") as srv: ...  # Digifant G60/G40    [KWP1281]
with mock_server(ecu="m232")     as srv: ...  # AAN M2.3.2 prjmod   [KWP1281]
with mock_server(ecu="me7")      as srv: ...  # AWP ME7.5 1.8T      [KWP2000]
```

All formula bytes are correctly encoded (`[formula][A][B]`) so
`formula.decode_cell()` produces physically realistic values throughout
the scenario loop.

**ME7 mock scenarios (245 s loop):**

| Scenario | Duration | RPM | Load | Boost | Lambda | Knock |
|----------|----------|-----|------|-------|--------|-------|
| Cold Start | 60 s | 1100 | 18 % | 970 mbar | 0.93 | — |
| Warm Idle | 60 s | 820 | 15 % | 960 mbar | 1.00 | — |
| Cruise | 60 s | 3500 | 40 % | 1100 mbar | 1.00 | — |
| Boost Pull | 35 s | → 6200 | 170 % | 1650 mbar | 0.88 | cyl 1–4 active |
| Decel | 30 s | → 2000 | 5 % | 950 mbar | 1.50 | — |

**M2.3.2 mock scenarios (255 s loop):**

| Scenario | Duration | RPM | Load | MAP | Lambda |
|----------|----------|-----|------|-----|--------|
| Cold Start | 60 s | 650 | 30 | 95 kPa | 0.92 |
| Warm Idle | 60 s | 820 | 22 | 95 kPa | 1.00 |
| Cruise | 60 s | 3000 | 100 | 115 kPa | 1.00 |
| Boost Run | 45 s | → 6000 | 230 | 255 kPa | 0.87 |
| Decel | 30 s | → 2500 | 8 | 75 kPa | 1.40 |

In the GUI, click **⚙ Mock ECU** and choose from the picker. The Protocol
combo auto-sets to KWP2000 when ME7 is selected.

---

## Bench Setup (OBD → ECU)

For bench testing with a standalone ECU:

1. Apply 12 V to ECU power pins and chassis ground.
2. Connect OBD-II K-line (pin 7) through the KKL cable.
3. For ME7: ensure pin 16 (battery +) and pin 4/5 (ground) are connected
   on the OBD connector.
4. Run `python -m kwpbridge --port COM3 --scan` to identify the ECU.
5. Use `--protocol kwp2000` for ME7 bench work to
   skip the KWP1281 detection delay.

The ME7.5 AWP ECU accepts KWP2000 connections without the engine running.
Groups 1, 2, 4, 60, 61 are readable in key-on/engine-off. Groups 22, 23,
91, 94 require the engine running.

---

## Label Files

KWPBridge bundles **1,174 VCDS-format `.lbl` files** covering the full VAG
catalogue. The correct label file loads automatically on connection by
matching the ECU part number.

Key bundled files for supported ECUs:

| File | ECU | Coverage |
|------|-----|----------|
| `labels/engine/893-906-266-D-EN.lbl` | 7A late | Groups 0–8, CO pot, coding |
| `labels/engine/893-906-266-D.lbl` | 7A late | Groups 0 (original German) |
| `labels/modules/4A0-907-551-AA.lbl` | M2.3.2 AAN/ABY | Groups 1–8, 29 fault codes |
| `labels/modules/4A0-907-551-C.lbl` | M2.3.2 ADU/RS2 | Redirects to 551-AA |
| `labels/modules/8A0-907-551-B.lbl` | M2.3.2 RS2 alt PN | Redirects to 551-AA |
| `labels/engine/06A-906-032-AWP.lbl` | ME7.5 AWP | Full group set, basic setting, coding |
| `labels/engine/06A-906-032-BAM.lbl` | ME7.5 BAM | BAM 1.8T variant |
| `labels/engine/06A-906-032-AUM.lbl` | ME7.5 AUM | AUM 1.8T 150hp |
| `labels/engine/06F-906-056-BLR.lbl` | MED9.1 BLR (closest) | Groups 1–114, used for MED9.1 display |

Add custom label files with `--labels-path /path/to/labels/`. The registry
searches subdirectories and follows `REDIRECT` directives.

---

## Development

```bash
git clone https://github.com/dspl1236/KWPBridge
cd KWPBridge
pip install -e ".[dev]"
pytest tests/          # 153 tests
```

Run the GUI without a cable:

```bash
python -m kwpbridge.gui    # ⚙ Mock ECU to simulate any platform
```

Run a mock server from the command line:

```bash
python -m kwpbridge.mock --ecu me7       # ME7 AWP 1.8T
python -m kwpbridge.mock --ecu m232      # AAN M2.3.2
python -m kwpbridge.mock --ecu 7a        # 7A 20v
```

### Module structure

| Module | Purpose |
|--------|---------|
| `protocol.py` | KWP1281 serial implementation (5-baud init, block framing) |
| `kwp2000.py` | KWP2000/ISO14230 serial implementation (fast init, frame construction) |
| `protocol_detect.py` | Auto-detection — tries KWP1281 then KWP2000 |
| `server.py` | TCP bridge server — broadcasts state to all clients |
| `client.py` | TCP client — subscribe to live data |
| `formula.py` | Cell value decode table (24 formula bytes) |
| `ecu_defs.py` | ECU definitions — group layouts, fault code descriptions |
| `lbl_parser.py` | VCDS `.lbl` file parser with formula extraction |
| `mock/` | Realistic ECU simulators (5 platforms) |
| `gui/` | PyQt5 desktop GUI |

---

## Known Limitations

| Area | Issue | Status |
|------|-------|--------|
| **MED9.1 live connection** | KWP2000 over TP2.0 CAN not yet implemented — requires CAN interface, not KKL cable | Planned |
| **Ignition formula 0x09** | Two-byte formula `(a*256+b)*0.1-100` may not match all ECUs — verify against real data | Needs verification |
| **Lambda formula 0x27** | Non-standard factor 0.00006104 — verify against ME7 ECU data | Needs verification |
| **KWP1281 block counter** | Counter not validated on receive — desync goes undetected | TODO |
| **KWP1281 echo bytes** | Echo bytes from Ross-Tech cables not consumed — may corrupt reads | TODO |
| **GUI fault read/clear** | Fault operations run on main thread — blocks UI and races with worker | TODO |
| **Missing formula bytes** | 0x15 (battery V), 0x16 (current), 0x19 (air mass), 0x1A (knock), 0x21 (%) not implemented | TODO |
| **No GUI tests** | GaugeWidget, KWPBridgeWindow, ConnectionWorker have no headless tests | TODO |

---

## Related Projects

- [MED9Tool](https://github.com/dspl1236/MED9Tool) — ROM editor for Bosch MED9.1 (03H906032 / 1K0907115). Immo-off, speed remove, emissions, presets, signature-based address finder.
- [HachiROM](https://github.com/dspl1236/HachiROM) — ROM editor for Hitachi MMS ECUs (7A 20v, AAH V6 12v). Live overlay via KWPBridge.
- [UrROM](https://github.com/dspl1236/UrROM) — ROM editor for Bosch M2.3.2 (AAN/ABY/ADU 20vT). Live overlay via KWPBridge.
- [DigiTool](https://github.com/dspl1236/DigiTool) — ROM editor for Digifant G60/G40.
- [TriCoreTool](https://github.com/dspl1236/TriCoreTool) — ROM editor for Bosch MED17/EDC17 (TriCore platform, modern VAG).
- [audi90-teensy-ecu](https://github.com/dspl1236/audi90-teensy-ecu) — Teensy 4.1 EPROM emulator / map switcher for Bosch M2.3.2.

---

Built with [Claude](https://anthropic.com) (Anthropic) as development partner.
