"""
ECU definitions — measuring block labels, known fault codes, and ECU metadata.

Each ECU definition maps group/cell numbers to labels so raw data can be
displayed meaningfully without VCDS label files.

Structure:
  ECUDef.groups[group_number][cell_index] = label string
  ECUDef.faults[fault_code]              = description string
"""

from dataclasses import dataclass, field


@dataclass
class ECUDef:
    """Definition for a single ECU variant."""
    part_numbers:  list[str]               # e.g. ["893906266D", "893906266B"]
    name:          str                     # human name
    address:       int                     # KWP1281 module address
    baud:          int                     # communication baud rate
    groups:        dict[int, dict[int, str]]  # [group][cell] = label
    faults:        dict[int, str]          # fault_code = description
    basic_settings: dict[int, str]         = field(default_factory=dict)
    notes:         str                     = ""


# ── 7A 20v — 893906266D (late) and 893906266B (early) ────────────────────────
# ECU: Hitachi MMS-05C (266D late) / MMS-04B (266B early)
# Protocol: KWP1281 at 10400 baud, address 0x01
# Native block: block 0 only — 10 raw bytes, no sub-groups
#   (confirmed from 893-906-266-D.lbl and HachiROM live sessions)
# The groups below (1-32) are the VAG-standard multi-group layout used by
# VCDS on compatible Motronic units. Whether the MMS-05C responds to groups
# 1+ is UNCONFIRMED on real hardware. HachiROM reads block 0 only.
# These group defs are used by the fault/label UI, not for live data reading.

_7A_GROUPS: dict[int, dict[int, str]] = {
    1: {
        1: "Engine Speed",
        2: "Coolant Temp",
        3: "Lambda Control",
        4: "CO Pot (ADC)",          # block 8 cell 4 in basic setting = CO trim
    },
    2: {
        1: "Engine Speed",
        2: "Engine Load",
        3: "Injection Timing",
        4: "MAF Sensor (G70)",
    },
    3: {
        1: "Engine Speed",
        2: "MAF Sensor (G70)",
        3: "Throttle Valve Angle",
        4: "Ignition Timing Angle",
    },
    4: {
        1: "Engine Speed",
        2: "Battery Voltage",
        3: "Coolant Temp",
        4: "Intake Air Temp",
    },
    5: {
        1: "Engine Speed",
        2: "Engine Load",
        3: "Vehicle Speed",
        4: "Load Status",
    },
    6: {
        1: "Engine Speed",
        2: "Engine Load",
        3: "Intake Air Temp",
        4: "Altitude Correction Factor",
    },
    7: {
        1: "Engine Speed",
        2: "Engine Load",
        3: "Coolant Temp",
        4: "Throttle Valve Angle",
    },
    8: {
        1: "Engine Speed",
        2: "CO Pot ADC Value",       # raw ADC 0-255, target=128 when calibrated
        3: "CO Pot Status",
        4: "CO Pot Trim Value",      # matches ROM 0x0777 when calibrated
    },
    # Group 8 basic setting = CO pot calibration
    # Block 8, cell 4 should read 128 (= 0x80) when calibrated correctly
    # This is the VCDS "basic setting" procedure that sets our ROM scalar

    # Higher groups — may or may not respond on 7A ECU
    # Included based on standard VAG Motronic block layout
    10: {
        1: "Engine Speed",
        2: "Engine Load",
        3: "Ignition Timing Angle",
        4: "Knock Retard Cyl 1",
    },
    11: {
        1: "Engine Speed",
        2: "Engine Load",
        3: "Knock Retard Cyl 2",
        4: "Knock Retard Cyl 3",
    },
    12: {
        1: "Engine Speed",
        2: "Engine Load",
        3: "Knock Retard Cyl 4",
        4: "Knock Retard Cyl 5",
    },
    # Group 31 — lambda probe status
    31: {
        1: "Lambda Probe Status",
        2: "O2 Sensor Voltage",
        3: "Lambda Control Active",
        4: "Probe Heating Status",
    },
    # Group 32 — lambda learned values
    32: {
        1: "Lambda Actual",
        2: "Lambda Setpoint",
        3: "Lambda Adapt Short",
        4: "Lambda Adapt Long",
    },
}

_7A_BASIC_SETTINGS: dict[int, str] = {
    1: "Idle Speed Basic Setting",
    8: "CO Pot Calibration (target=128)",
}

# Common 7A fault codes (VAG decimal format)
_7A_FAULTS: dict[int, str] = {
    514:  "MAF sensor (G70) — signal out of range",
    515:  "Coolant temp sensor (G62) — signal out of range",
    516:  "Intake air temp sensor (G42) — signal out of range",
    518:  "Throttle potentiometer (G69) — signal out of range",
    521:  "CO pot / pin 4 — signal out of range",          # our CO pot fault
    522:  "O2 sensor (G39) — no signal",
    523:  "O2 sensor (G39) — signal too lean",
    524:  "O2 sensor (G39) — signal too rich",
    532:  "Battery voltage — too high",
    533:  "Battery voltage — too low",
    540:  "Idle speed control — deviation",
    544:  "MAF sensor (G70) — implausible signal",
    545:  "Ignition coil (N) — open circuit",
    551:  "Injection valve cyl 1 — open/short",
    552:  "Injection valve cyl 2 — open/short",
    553:  "Injection valve cyl 3 — open/short",
    554:  "Injection valve cyl 4 — open/short",
    555:  "Injection valve cyl 5 — open/short",
    560:  "Knock sensor 1 (G61) — no signal",
    561:  "Knock sensor 2 — no signal",
    578:  "RPM sensor (G28) — no signal",
    579:  "Vehicle speed sensor (G22) — no signal",
    65535: "No fault codes stored",
}

ECU_7A_LATE = ECUDef(
    part_numbers   = ["893906266D"],
    name           = "7A Late — MMS05C (4-plug, post-3/90)",
    address        = 0x01,
    baud           = 10400,
    groups         = _7A_GROUPS,
    faults         = _7A_FAULTS,
    basic_settings = _7A_BASIC_SETTINGS,
    notes          = "CO pot patch: group 8 cell 4 should read 128 when calibrated. "
                     "Pin 4 sensor: cell 2 shows live ADC value.",
)

ECU_7A_EARLY = ECUDef(
    part_numbers   = ["893906266B"],
    name           = "7A Early — MMS-04B (2-plug, pre-3/90)",
    address        = 0x01,
    baud           = 10400,
    groups         = _7A_GROUPS,   # same block layout
    faults         = _7A_FAULTS,
    basic_settings = _7A_BASIC_SETTINGS,
    notes          = "Same KWP1281 block layout as 266D. "
                     "Different ISV hardware but same diagnostic interface.",
)

# ── AAH V6 12v — 4A0906266 ───────────────────────────────────────────────────
_AAH_GROUPS: dict[int, dict[int, str]] = {
    1: {
        1: "Engine Speed",
        2: "Coolant Temp",
        3: "Lambda Control Bank 1",
        4: "Lambda Control Bank 2",
    },
    2: {
        1: "Engine Speed",
        2: "Engine Load",
        3: "Injection Timing",
        4: "MAF Sensor (G70)",
    },
    3: {
        1: "Engine Speed",
        2: "MAF Sensor",
        3: "Throttle Valve Angle",
        4: "Ignition Timing",
    },
    4: {
        1: "Engine Speed",
        2: "Battery Voltage",
        3: "Coolant Temp",
        4: "Intake Air Temp",
    },
    5: {
        1: "Engine Speed",
        2: "Engine Load",
        3: "Vehicle Speed",
        4: "Load Status",
    },
    31: {
        1: "Lambda Probe B1 Status",
        2: "Lambda Probe B2 Status",
        3: "O2 Sensor B1 Voltage",
        4: "O2 Sensor B2 Voltage",
    },
    32: {
        1: "Lambda Actual B1",
        2: "Lambda Actual B2",
        3: "Lambda Adapt B1",
        4: "Lambda Adapt B2",
    },
}

_AAH_FAULTS: dict[int, str] = {
    **_7A_FAULTS,   # most codes shared
    522:  "O2 sensor Bank 1 (G39) — no signal",
    527:  "O2 sensor Bank 2 — no signal",
}

ECU_AAH = ECUDef(
    part_numbers   = ["4A0906266", "8A0906266A"],
    name           = "AAH V6 12v — MMS100/MMS-200",
    address        = 0x01,
    baud           = 10400,
    groups         = _AAH_GROUPS,
    faults         = _AAH_FAULTS,
    notes          = "V6 12v — two lambda banks. No CO pot on 3-wire MAF.",
)

# ── Registry ──────────────────────────────────────────────────────────────────
ALL_ECU_DEFS: list[ECUDef] = [ECU_7A_LATE, ECU_7A_EARLY, ECU_AAH]


def find_ecu_def(part_number: str) -> ECUDef | None:
    """Look up an ECU definition by part number."""
    for ecu in ALL_ECU_DEFS:
        if part_number in ecu.part_numbers:
            return ecu
    return None


def get_cell_label(ecu_def: ECUDef, group: int, cell: int) -> str:
    """Get the label for a measuring block cell, or a generic fallback."""
    if ecu_def is None:
        return f"Group {group} Cell {cell}"
    return ecu_def.groups.get(group, {}).get(cell, f"Group {group} Cell {cell}")


def get_fault_description(ecu_def: ECUDef, code: int) -> str:
    """
    Get the English description for a fault code.

    Lookup order:
      1. ECUDef.faults — ECU-specific descriptions (most precise)
      2. DIDB dtc_descriptions.json — VAG official descriptions (4,817 codes)
      3. Generic fallback with code number
    """
    if ecu_def is not None:
        specific = ecu_def.faults.get(code)
        if specific:
            return specific
    # DIDB fallback — covers codes 0-4818 with official VAG descriptions
    try:
        from .didb import dtc_description
        didb = dtc_description(code)
        if didb:
            return didb
    except Exception:
        pass
    return f"Fault {code:05d} — unknown"

# ── Digifant 1 — G60 / G40 ────────────────────────────────────────────────────
# Part numbers:
#   037-906-023      RV engine  Golf/Jetta Digifant 0852/1265  1990-91
#   037-906-023-R    RV engine  Golf/Jetta Digifant 1265       1991
#   037-906-023-160  PG engine  (160 HP variant)
#   037-906-025-ADY  ADY/AGG/AKR 2.0 8v  Corrado/Golf/Jetta/Passat  1991-95
#   037-906-025-AFT  AFT variant
#   037-906-022      earlier Digifant variant
#
# KWP1281 address: 0x01 (engine, same as all VAG)
# Baud rate: 10400
# Group layout: group 1 = primary, 4 cells per group
#
# Group 0 on 037-906-023 is raw undocumented data.
# Group 1 on all variants: RPM, load, coolant, injection time.
# Digifant 1 has fewer groups than later Motronic — typically groups 0-10.
#
# Note: Digifant 1 (G60/G40) predates OBD but uses KWP1281 compatible timing.
# The "load" value is VAF (vane airflow) signal, not calculated load.

_DIGIFANT_GROUPS: dict[int, dict[int, str]] = {
    0: {
        1:  "Undocumented",
        2:  "Undocumented",
        3:  "Coolant Temperature",   # lower = hotter (inverse NTC)
        4:  "Undocumented",
        5:  "O2S Sensor",            # 164-168=cold/open, 0-5=V+ short, 230-255=gnd short
        6:  "Undocumented",
        7:  "Undocumented",
        8:  "Undocumented",
        9:  "Undocumented",
        10: "Undocumented",
    },
    1: {
        1:  "Engine Speed",          # Spec: 750-850 RPM at idle
        2:  "Engine Load",           # VAF signal
        3:  "Coolant Temperature",
        4:  "Injection Time",        # ms
    },
    2: {
        1:  "Engine Speed",
        2:  "Intake Air Temperature",
        3:  "Undocumented",
        4:  "Injection Time",
    },
    3: {
        1:  "Engine Speed",          # Soft governed to 6300 RPM
        2:  "Engine Temperature",
        3:  "Undocumented",
        4:  "Injection Time",
    },
    4: {
        1:  "Engine Speed",
        2:  "Engine Load",           # VAF signal
        3:  "Undocumented",
        4:  "Injection Time",        # Goes to 0ms on decel cut-off
    },
    5: {
        1:  "Engine Speed",
        2:  "Throttle Valve Angle",  # WOT=90° or more
        3:  "Undocumented",
        4:  "Injection Time",
    },
    6: {
        1:  "Engine Speed",
        2:  "Intake Air Temperature",
        3:  "Undocumented",
        4:  "Undocumented",
    },
    9: {
        1:  "Engine Speed",
        2:  "Possible Lambda Signal", # varies 30-50, no units
        3:  "Undocumented",
        4:  "Undocumented",
    },
    10: {
        1:  "Engine Speed",
        2:  "Possible Lambda Signal", # varies 0-256
        3:  "Undocumented",
        4:  "Undocumented",
    },
}

# Digifant 1 later variants (037-906-025-ADY, Motronic 2.x 2.0 8v)
# These have proper labelled groups including lambda adaptation
_MOTRONIC_2X_GROUPS: dict[int, dict[int, str]] = {
    0: {
        1:  "Intake Air Temperature",  # Spec: 70-160 (4.5-72.0°C)
        2:  "Battery Voltage",         # Spec: 115-161 (12.0-16.5V)
        3:  "Coolant Temperature",     # Spec: 120-150 (80-110°C)
        4:  "Engine Load",             # Spec: 25-55 (9.75-19.5%)
        5:  "Lambda Sensor Voltage",   # Spec: 0-55 (0.0-1.10V)
        6:  "Lambda Learning Value",   # Spec: 0-22 (0.0-0.75ms)
        7:  "Operating Condition",
        8:  "Throttle Valve Angle",    # Spec: 5-14 (2.5-6.5°)
        9:  "Injection Time",          # Spec: 2-4ms
        10: "Engine Speed",            # Spec: 23-27 (736-864 RPM)
    },
    1: {
        1:  "Engine Speed",            # Spec: 736-864 RPM
        2:  "Coolant Temperature",
        3:  "Lambda Sensor Voltage",
        4:  "Adjustment Conditions",
    },
    2: {
        1:  "Engine Speed",
        2:  "Injection Time",          # Spec: 2-4ms
        3:  "Battery Voltage",
        4:  "Intake Air Temperature",
    },
    3: {
        1:  "Engine Speed",
        2:  "Engine Load",             # Spec: 9.75-19.50%
        3:  "Throttle Valve Angle",
        4:  "Throttle Valve Duty Cycle",
    },
    4: {
        1:  "Engine Speed",
        2:  "Engine Load",
        3:  "Vehicle Speed",
        4:  "Operating Conditions",
    },
    5: {
        1:  "Engine Speed",
        2:  "Charcoal Valve Duty Cycle",
        3:  "Fuel Consumption",
        4:  "Operating Condition",
    },
    6: {
        1:  "Lambda Control Additive",
        2:  "Lambda Control Multiplicative",
        3:  "Throttle Valve Idle Control",
        4:  "Throttle Valve Idle Control",
    },
    7: {
        1:  "Hall Sender Coordination",
        2:  "Hall Sender Coordination",
        3:  "Altitude Correction",
        4:  "Operating Condition",
    },
}

_DIGIFANT_FAULTS: dict[int, str] = {
    513:  "O2 sensor (G39) — no signal or signal out of range",
    515:  "Coolant temperature sensor (G62) — open/short circuit",
    516:  "Intake air temperature sensor (G42) — open/short circuit",
    517:  "Throttle position sensor (G69) — no signal",
    519:  "Vehicle speed sensor (G21) — no signal",
    521:  "Idle speed — actual does not match specified",
    522:  "Idle speed control valve (N71) — open/short circuit",
    523:  "Engine speed sensor (G28) — no signal",
    524:  "Knock sensor (G61) — no signal",
    527:  "EGR valve — no signal",
    528:  "Fuel injector — open/short circuit",
    530:  "Lambda control — control limit reached",
    540:  "Idle stabilisation — control limit reached",
    544:  "VAF sensor (G70) — signal out of range",
    550:  "ISV (N71) — electrical fault",
    553:  "Charcoal filter solenoid (N80) — open/short circuit",
}

ECU_DIGIFANT_G60 = ECUDef(
    part_numbers   = [
        "037906023",    # 037-906-023    RV engine Golf/Jetta 1990-91
        "037906023R",   # 037-906-023-R  RV Digifant 1265
        "037906022",    # 037-906-022    earlier variant
    ],
    name           = "Digifant 1 — G60/G40 (037-906-023)",
    address        = 0x01,
    baud           = 10400,
    groups         = _DIGIFANT_GROUPS,
    faults         = _DIGIFANT_FAULTS,
    notes          = "Digifant 1 — VW G60/G40 Corrado/Golf/Jetta/Polo 1989-93. "
                     "Group 0 is largely undocumented raw data. "
                     "Group 1 is primary: RPM, VAF load, coolant, injection time. "
                     "No lambda adaptation groups — open loop on most variants.",
)

ECU_MOTRONIC_2X = ECUDef(
    part_numbers   = [
        "037906025ADY",  # 037-906-025-ADY  ADY 2.0 8v 115hp
        "037906025AFT",  # 037-906-025-AFT  AFT variant
        "037906018ABA",  # 037-906-018-ABA  ABA 2.0 8v Golf Cabrio
        "037906018AWG",  # 037-906-018-AWG  AWG variant
    ],
    name           = "Motronic 2.x — 2.0 8v (037-906-025)",
    address        = 0x01,
    baud           = 10400,
    groups         = _MOTRONIC_2X_GROUPS,
    faults         = _DIGIFANT_FAULTS,
    notes          = "Motronic 2.x 2.0 8v — Corrado/Golf/Jetta/Passat 1991-95. "
                     "Group 0 has 10 cells including full engine state. "
                     "Group 6 has lambda adaptation values. "
                     "Used in DigiTool for G60/G40 ECU editing.",
)

# Update registry
ALL_ECU_DEFS.extend([ECU_DIGIFANT_G60, ECU_MOTRONIC_2X])


# ── Bosch M2.3.2 — AAN/ABY/ADU (4A0-907-551-AA / 551C) ──────────────────────
# KWP1281 measuring blocks confirmed from:
#   - PRJ WinlogDriver.cpp field names and decode formulas
#   - 895-907-551.lbl (Paul Nugent 2002, ABY S2)
#   - S2Forum m232-org community research
#   - 8D0-906-266 (Hitachi AAH, different ECU but same block layout convention)
# Baud: 9600 (Bosch M2.3.x standard)
# Address: 0x01 (Engine module)
# 4 data cells per group (KWP1281 standard VAG layout)

_M232_GROUPS: dict[int, dict[int, str]] = {
    1: {
        0: "M2.3.2 Group 1 : General & Ignition",
        1: "Engine Speed",
        2: "Coolant Temp",
        3: "Lambda Factor",
        4: "Ignition Timing",
    },
    2: {
        0: "M2.3.2 Group 2 : General & Injection",
        1: "Engine Speed",
        2: "Injector Duration",
        3: "Battery Voltage",
        4: "Atmospheric Pressure",
    },
    3: {
        0: "M2.3.2 Group 3 : Load / Temps / Throttle",
        1: "Engine Speed",
        2: "Engine Load",
        3: "Throttle Angle",
        4: "Intake Air Temp",
    },
    4: {
        0: "M2.3.2 Group 4 : Load / Speed / Throttle Switches",
        1: "Engine Speed",
        2: "Engine Load",
        3: "Vehicle Speed",
        4: "Throttle Switches",
    },
    5: {
        0: "M2.3.2 Group 5 : Idle Air Control",
        1: "Engine Speed",
        2: "IAC Zero Point",
        3: "IAC Duty Cycle",
        4: "Load Switches",
    },
    6: {
        0: "M2.3.2 Group 6 : Boost / N75 (prjmod)",
        1: "N75 Duty Cycle",
        2: "N75 Request",
        3: "MAP Actual (kPa)",
        4: "MAP Request (kPa)",
    },
    7: {
        0: "M2.3.2 Group 7 : Knock Sensors",
        1: "Knock Sensor 1",
        2: "Knock Sensor 2",
        3: "Knock Sensor 3",
        4: "Knock Sensor 4",
    },
    8: {
        0: "M2.3.2 Group 8 : Injection Details",
        1: "Effective IPW",
        2: "Injector Dead-time",
        3: "Actual IPW",
        4: "Injector Duty Cycle",
    },
}

_M232_FAULTS: dict[int, str] = {
    # Engine sensors
    513:  "ECT Sensor G62 — open/short circuit",
    514:  "ECT Sensor G62 — signal out of range",
    515:  "IAT Sensor G42 — open/short circuit",
    516:  "IAT Sensor G42 — signal out of range",
    522:  "TPS G69 — open/short circuit",
    523:  "TPS G69 — signal out of range",
    524:  "Closed throttle switch F60 — open/short",
    526:  "WOT switch F61 — open/short",
    531:  "Knock sensor G61 — open/short / no signal",
    532:  "Knock sensor G66 — open/short / no signal",
    533:  "Engine speed sensor G28 — no signal",
    537:  "Lambda sensor G39 — control limit exceeded",
    543:  "Fuel pump relay J17 — open/short circuit",
    545:  "Camshaft position sensor G40 — no signal",
    551:  "Injection valve cyl 1 — open/short",
    552:  "MAF sensor G70 — signal out of range",
    553:  "MAF sensor G70 — open/short circuit",
    557:  "MAP sensor G71 — signal out of range",
    558:  "MAP sensor G71 — open/short circuit",
    # Boost
    565:  "N75 boost pressure solenoid — open/short circuit",
    575:  "Boost pressure too low — below specified level",
    576:  "Boost pressure too high — overboost",
    # Injectors
    577:  "Injector cylinder 1 N30 — open/short",
    578:  "Injector cylinder 2 N31 — open/short",
    579:  "Injector cylinder 3 N32 — open/short",
    580:  "Injector cylinder 4 N33 — open/short",
    581:  "Injector cylinder 5 N83 — open/short",
    # ROM
    0:    "ECU internal fault — ROM checksum error",
    65535: "No fault codes stored",
}

ECU_M232_AAN = ECUDef(
    part_numbers   = [
        "4A0907551AA",   # 4A0-907-551-AA  AAN/ABY — most common
        "4A0907551A",    # 4A0-907-551-A   earlier PN variant
        "4A0907551",     # 4A0-907-551     base PN fallback
        "895907551A",    # 895-907-551-A   ABY S2 factory
        "8A0907551B",    # 8A0-907-551-B   RS2/ADU (redirect)
    ],
    name           = "Bosch M2.3.2 — AAN/ABY/ADU 20vT (4A0-907-551-AA)",
    address        = 0x01,
    baud           = 9600,
    groups         = _M232_GROUPS,
    faults         = _M232_FAULTS,
    basic_settings = {
        # Basic setting group number : procedure description
        # No confirmed basic settings via KWP1281 on stock M2.3.2 except:
        # Group 0 = display all live data (read only)
    },
    notes          = (
        "Bosch Motronic M2.3.2 — AAN 20vT (200hp), ABY S2 (230hp), ADU RS2 (315hp). "
        "KWP1281 at 9600 baud, address 0x01. "
        "4 data cells per group, 2-byte words (big-endian). "
        "Firmware variants: stock Bosch / 034EFI Rip Chip / prjmod 0x0202. "
        "Group 6-8 data available on prjmod firmware only. "
        "Decode scaling: RPM=raw×40, Load=raw/25, ECT/IAT=(raw-70)×0.7°C, "
        "TPS=raw×0.416%, Lambda=raw/128, IGN=°BTDC raw, "
        "MAP=raw/1.035 kPa (MPXH6400A), IPW=raw×0.52ms, VSS=raw×2km/h. "
        "Label file: labels/modules/4A0-907-551-AA.lbl"
    ),
)

# Update registry
ALL_ECU_DEFS.append(ECU_M232_AAN)


# ── Bosch ME7.5 — AWP/AUM/AUQ/BAM 1.8T (06A-906-032 family) ─────────────────
# Measuring blocks confirmed from 06A-906-032-AWP.lbl (Ross-Tech)
# KWP2000 / ISO 14230 protocol, 10400 baud, address 0x01
# ECU: Bosch ME7.5, same PCB family as AEB/AGU/AMB/BAM/AWP

_ME7_AWP_GROUPS: dict[int, dict[int, str]] = {
    1:  {1:"Engine Speed", 2:"Coolant Temperature", 3:"Lambda Controller",
         4:"Basic Setting Requirements"},
    2:  {1:"Engine Speed", 2:"Engine Load", 3:"Injection Timing", 4:"Intake Air Mass"},
    3:  {1:"Engine Speed", 2:"Intake Air Mass", 3:"Throttle Sensor 1", 4:"Ignition Timing Angle"},
    4:  {1:"Engine Speed", 2:"Voltage Supply", 3:"Coolant Temperature", 4:"Intake Air Temperature"},
    5:  {1:"Engine Speed", 2:"Engine Load", 3:"Vehicle Speed", 4:"Load Status"},
    10: {1:"Engine Speed", 2:"Engine Load", 3:"Throttle Sensor 1", 4:"Ignition Timing Angle"},
    14: {1:"Engine Speed", 2:"Engine Load", 3:"Misfire Counter", 4:"Misfire Recognition"},
    15: {1:"Cylinder 1 Misfire", 2:"Cylinder 2 Misfire", 3:"Cylinder 3 Misfire",
         4:"Malfunction Recognition"},
    16: {1:"Cylinder 4 Misfire", 4:"Malfunction Recognition"},
    22: {1:"Engine Speed", 2:"Engine Load", 3:"Cyl 1 Knock Retard", 4:"Cyl 2 Knock Retard"},
    23: {1:"Engine Speed", 2:"Engine Load", 3:"Cyl 3 Knock Retard", 4:"Cyl 4 Knock Retard"},
    28: {1:"Engine Speed", 2:"Engine Load", 3:"Coolant Temperature", 4:"Knock Sensor Test"},
    30: {1:"O2 Status Bank1 Sensor1", 2:"O2 Status Bank1 Sensor2"},
    32: {1:"Lambda Idle Adaptation", 2:"Lambda Partial Adaptation"},
    33: {1:"Lambda Controller", 2:"O2 Sensor 1 Upstream Voltage"},
    34: {1:"Engine Speed", 2:"Catalyst Temperature", 3:"Period Duration", 4:"Lambda Aging"},
    36: {1:"O2 Sensor 2 Downstream Voltage", 2:"Lambda Availability"},
    41: {1:"Engine Speed", 2:"Engine Load", 3:"Injector Bank 1", 4:"Injector Bank 2"},
    43: {1:"Engine Speed", 2:"Engine Load", 3:"Injector Cylinder 1", 4:"Injector Cylinder 2"},
    46: {1:"Engine Speed", 2:"Engine Load", 3:"Injector Cylinder 3", 4:"Injector Cylinder 4"},
    50: {1:"Engine Speed", 2:"ST Fuel Trim Bank1", 3:"LT Fuel Trim Bank1"},
    54: {1:"Engine Speed", 2:"Load", 3:"Upstream O2 Voltage", 4:"Downstream O2 Voltage"},
    55: {1:"Engine Speed", 2:"Load", 3:"Catalyst Efficiency"},
    56: {1:"Engine Speed", 2:"Coolant Temp", 3:"Catalyst Temperature"},
    60: {1:"Throttle Sensor 1", 2:"Throttle Sensor 2", 3:"Learn Step Counter",
         4:"Throttle Adaptation Result"},
    61: {1:"Engine Speed", 2:"Voltage Supply", 3:"Throttle Actuator", 4:"Operating Condition"},
    62: {1:"Throttle Sensor 1", 2:"Throttle Sensor 2", 3:"Throttle Position (G79)",
         4:"Accelerator Pedal Sensor 2"},
    63: {1:"Throttle Position (G79)"},
    66: {1:"Engine Speed", 2:"Engine Load", 3:"EVAP Purge Valve", 4:"Fuel Pressure"},
    70: {1:"Engine Speed", 2:"Engine Load", 3:"Catalyst Temp B1", 4:"Catalyst Temp B2"},
    71: {1:"Engine Speed", 2:"Engine Load", 3:"Exhaust Temp", 4:"Catalyst Efficiency"},
    77: {1:"Engine Speed", 2:"Engine Load", 3:"EGR Valve Position", 4:"EGR Duty Cycle"},
    89: {1:"Engine Speed", 2:"Coolant Temp", 3:"Engine Load", 4:"Barometric Pressure"},
    91: {1:"Engine Speed", 2:"Engine Load", 3:"N75 Duty Cycle", 4:"Boost Pressure Actual"},
    94: {1:"Engine Speed", 2:"Engine Load", 3:"Ignition Timing Actual",
         4:"Knock Retard Total"},
    99: {1:"Readiness Code"},
}

_ME7_AWP_FAULTS: dict[int, str] = {
    # Lambda / O2
    16486: "O2 Sensor B1S1 — Signal too low (lean)",
    16487: "O2 Sensor B1S1 — Signal too high (rich)",
    16496: "O2 Sensor B1S2 — Response too slow",
    16514: "O2 Sensor B1S1 — Heater circuit fault",
    16518: "O2 Sensor B1S2 — Heater circuit fault",
    16555: "Lambda regulation — control limit reached",
    16556: "Lambda adaptation — out of range",
    # MAF / Throttle
    16485: "MAF Sensor G70 — Signal out of range",
    16504: "Throttle Position Sensor G69 — Range/performance",
    16705: "Throttle Drive Angle Sensor 1 G187 — Range/performance",
    16706: "Throttle Drive Angle Sensor 2 G188 — Range/performance",
    17535: "Throttle Valve Adaptation — Not completed",
    17536: "Throttle Valve Adaptation — Error",
    # Fuel system
    16684: "Fuel trim — System too lean (Bank 1)",
    16685: "Fuel trim — System too rich (Bank 1)",
    17520: "Fuel pressure regulation — Limit reached",
    # Boost / N75
    17965: "Boost pressure — Too low",
    17966: "Boost pressure — Too high",
    17544: "N75 Boost Pressure Solenoid — Electrical fault",
    # Knock
    16716: "Knock Sensor 1 G61 — Signal out of range",
    16717: "Knock Sensor 2 G66 — Signal out of range",
    # Coolant / temp
    16603: "ECT Sensor G62 — Signal out of range",
    16604: "IAT Sensor G42 — Signal out of range",
    # Injectors
    17523: "Injector Cylinder 1 N30 — Open/short",
    17524: "Injector Cylinder 2 N31 — Open/short",
    17525: "Injector Cylinder 3 N32 — Open/short",
    17526: "Injector Cylinder 4 N33 — Open/short",
    # CPS / speed
    16725: "Engine Speed Sensor G28 — No signal",
    16766: "Camshaft Position Sensor G40 — Signal out of range",
    # Misfire
    17740: "Random/Multiple Cylinder Misfire detected",
    17741: "Cylinder 1 Misfire detected",
    17742: "Cylinder 2 Misfire detected",
    17743: "Cylinder 3 Misfire detected",
    17744: "Cylinder 4 Misfire detected",
    # Catalyst
    16804: "Catalyst efficiency below threshold (Bank 1)",
    # Evap
    16839: "EVAP system — Large leak detected",
    16840: "EVAP system — Small leak detected",
    # Immobiliser
    17053: "Immobiliser — No communication",
    # Generic
    0:     "No fault codes stored",
}

ECU_ME7_AWP = ECUDef(
    part_numbers   = [
        # AWP 1.8T 180hp (Golf/Jetta/TT MK4, A4 B5/B6)
        "06A906032BH",
        "06A906032BN",
        "06A906032BD",
        "06A906032BG",
        "06A906032BF",
        "06A906032BE",
        "06A906032BB",
        "06A906032AY",
        "06A906032AX",
        "06A906032AS",
        # AUM 1.8T 150hp (Golf/Jetta MK4)
        "06A906032GD",
        "06A906032GC",
        # AUQ 1.8T 180hp (Golf/Jetta MK4 GTI/GLI)
        "06A906032KL",
        "06A906032KN",
        # AWW 1.8T 150hp
        "06A906032HS",
        # BAM 1.8T 225hp (TT 225)
        "06A906032GF",
        "06A906032GG",
        # AMB 1.8T (Passat)
        "06A906032EB",
        # General fallback for any 06A906032 variant
        "06A906032",
    ],
    name           = "Bosch ME7.5 — 1.8T AWP/AUM/AUQ/BAM (06A-906-032)",
    address        = 0x01,
    baud           = 10400,
    groups         = _ME7_AWP_GROUPS,
    faults         = _ME7_AWP_FAULTS,
    basic_settings = {
        60:  "Throttle body adaptation (EPC) — engine warm, ignition on",
        62:  "EPC adaptation — requires basic setting 60 first",
        34:  "Lambda sensor aging check — requires cat temp >350°C",
    },
    notes          = (
        "Bosch ME7.5 — 1.8T turbocharged 4-cylinder. "
        "KWP2000 / ISO 14230 protocol (NOT KWP1281). "
        "Requires startDiagnosticSession (0x10 0x89) before reading. "
        "Keep-alive testerPresent (0x3E) required every 1.5s. "
        "Reading: 0x21 [group_number] → cells of [formula][A][B]. "
        "Common variants: AWP=180hp, AUM=150hp, AUQ=180hp, BAM=225hp. "
        "Part numbers: 06A-906-032-BH/BN/BD/GD/KL/GF (most common). "
        "MK2 Jetta swap uses same ECU — just different wiring harness. "
        "ECU bench setup: pin 19=K-line, pins 1+2=ground, pin 3+4=12V. "
        "Label file: labels/engine/06A-906-032-AWP.lbl"
    ),
)

# Update registry
ALL_ECU_DEFS.append(ECU_ME7_AWP)


# ── Bosch MED9.1 — VR6 3.6L FSI (03H-906-032 family) ────────────────────────
# Measuring blocks confirmed from 06F-906-056-BLR.lbl (BLR 2.0 FSI shares same
# block layout as MED9.1 VR6) and 1K090711S_Definition__1_.xdf
#
# Transport: KWP2000 over TP2.0 (VAG CAN transport protocol)
#   — NOT ISO 14230 K-line. Requires CAN interface, not KKL cable.
#   — ECU CAN physical address: 0x01
#   — TP2.0 channel setup on CAN, then KWP2000 service requests inside
#
# Security access (confirmed from EliasTuning/MED9RamReader):
#   Level 1 READ  (service 0x27 0x01/0x02):  key = (seed + 0x11170) & 0xFFFFFFFF
#   Level 1 WRITE (service 0x27 0x01, SA2):  5-round rotate-left XOR 0x5FBD5DBD
#
# Flash pipeline: LZSS compress → XOR key "RobertCode" → KWP2000 download
#
# Note: Current KWPBridge supports K-line only. MED9.1 requires a future
# TP2.0/CAN transport layer. SA key functions are documented here for when
# CAN support is added. See kwpbridge/security.py in MED9Tool for implementations.

_MED91_GROUPS: dict[int, dict[int, str]] = {
    1:  {1: "Engine Speed",          2: "Coolant Temperature",
         3: "Lambda Control B1",     4: "Lambda Control B2"},
    2:  {1: "Engine Speed",          2: "Engine Load",
         3: "Injection Pulse Width", 4: "Intake Manifold Pressure"},
    3:  {1: "Engine Speed",          2: "Intake Manifold Pressure",
         3: "Throttle Valve Angle",  4: "Ignition Timing Angle"},
    4:  {1: "Engine Speed",          2: "Battery Voltage",
         3: "Coolant Temperature",   4: "Intake Air Temperature"},
    5:  {1: "Engine Speed",          2: "Engine Load",
         3: "Vehicle Speed",         4: "Load Status"},
    6:  {1: "Engine Speed",          2: "Engine Load",
         3: "Intake Air Temperature", 4: "Altitude Correction"},
    7:  {1: "Engine Speed",          2: "Engine Load",
         3: "Coolant Temperature",   4: "Operating Mode"},
    10: {1: "Engine Speed",          2: "Engine Load",
         3: "Throttle Valve Angle",  4: "Ignition Timing Angle"},
    11: {1: "Engine Speed",          2: "Coolant Temperature",
         3: "Intake Air Temperature", 4: "Ignition Advance"},
    14: {1: "Engine Speed",          2: "Engine Load",
         3: "Misfire Counter",       4: "Misfire Recognition"},
    15: {1: "Misfire Cyl 1",         2: "Misfire Cyl 2",
         3: "Misfire Cyl 3",         4: "Misfire Recognition"},
    16: {1: "Misfire Cyl 4",         2: "Misfire Cyl 5",
         3: "Misfire Cyl 6",         4: "Misfire Recognition"},
    20: {1: "Knock Retard Cyl 1",    2: "Knock Retard Cyl 2",
         3: "Knock Retard Cyl 3",    4: "Knock Retard Cyl 4"},
    21: {1: "Knock Retard Cyl 5",    2: "Knock Retard Cyl 6"},
    22: {1: "Engine Speed",          2: "Engine Load",
         3: "Knock Retard Cyl 1",    4: "Knock Retard Cyl 2"},
    23: {1: "Engine Speed",          2: "Engine Load",
         3: "Knock Retard Cyl 3",    4: "Knock Retard Cyl 4"},
    24: {1: "Engine Speed",          2: "Engine Load",
         3: "Knock Retard Cyl 5",    4: "Knock Retard Cyl 6"},
    30: {1: "O2 Sensor B1S1 Status", 2: "O2 Sensor B1S2 Status",
         3: "O2 Sensor B2S1 Status", 4: "O2 Sensor B2S2 Status"},
    31: {1: "O2 Voltage B1S1",       2: "O2 Voltage B1S2"},
    32: {1: "Lambda Idle Adapt B1",  2: "Lambda Partial Adapt B1",
         3: "Lambda Idle Adapt B2",  4: "Lambda Partial Adapt B2"},
    33: {1: "Lambda Controller B1",  2: "O2 Sensor B1S1 Voltage",
         3: "Lambda Controller B2",  4: "O2 Sensor B2S1 Voltage"},
    34: {1: "Engine Speed",          2: "Cat Temperature B1",
         3: "Lambda Period Duration", 4: "Lambda Aging B1"},
    36: {1: "O2 Sensor B1S2 Voltage", 2: "Lambda Availability B1",
         3: "O2 Sensor B2S2 Voltage", 4: "Lambda Availability B2"},
    38: {1: "Engine Load",           2: "Sensor Voltage",
         3: "Cam Adjustment",        4: "Cam Adjustment Result"},
    41: {1: "Engine Speed",          2: "Engine Load",
         3: "Injector Bank 1",       4: "Injector Bank 2"},
    43: {1: "Engine Speed",          2: "Engine Load",
         3: "Injector Cyl 1",        4: "Injector Cyl 2"},
    46: {1: "Engine Speed",          2: "Engine Load",
         3: "Injector Cyl 3",        4: "Injector Cyl 4"},
    47: {1: "Engine Speed",          2: "Engine Load",
         3: "Injector Cyl 5",        4: "Injector Cyl 6"},
    50: {1: "Engine Speed",          2: "ST Fuel Trim B1",
         3: "LT Fuel Trim B1",       4: "LT Fuel Trim B2"},
    54: {1: "Engine Speed",          2: "Engine Load",
         3: "O2 Voltage B1S1",       4: "O2 Voltage B1S2"},
    60: {1: "Throttle Valve Sensor 1", 2: "Throttle Valve Sensor 2",
         3: "Throttle Learn Step",   4: "Throttle Adaptation Status"},
    61: {1: "Engine Speed",          2: "Battery Voltage",
         3: "Throttle Valve Angle",  4: "Operating Condition"},
    62: {1: "Throttle Sensor 1",     2: "Throttle Sensor 2",
         3: "Accel Pedal Position 1", 4: "Accel Pedal Position 2"},
    70: {1: "Engine Speed",          2: "Engine Load",
         3: "Cat Temp B1",           4: "Cat Temp B2"},
    77: {1: "Engine Speed",          2: "Engine Load",
         3: "EGR Valve Position",    4: "EGR Duty Cycle"},
    89: {1: "Engine Speed",          2: "Coolant Temperature",
         3: "Engine Load",           4: "Barometric Pressure"},
    90: {1: "Engine Speed",          2: "Cam Adjust B1 Intake",
         3: "Cam Adjust B1 Exhaust", 4: "Cam Adjust B2 Intake"},
    91: {1: "Engine Speed",          2: "Cam Adjust B2 Exhaust",
         3: "Cam Adjust Status",     4: "Cam Phase"},
    99: {1: "Engine Speed",          2: "Coolant Temperature",
         3: "Lambda Control B1",     4: "Lambda Control B2"},
    # MED9.1 TFSI-specific: high-pressure fuel system
    100: {1: "Readiness Code",       2: "Coolant Temperature",
          3: "Time Since Start",     4: "OBD Status"},
    101: {1: "Engine Speed",         2: "Engine Load",
          3: "Injection Pulse Width", 4: "Rail Pressure Actual"},
    102: {1: "Engine Speed",         2: "Coolant Temperature",
          3: "Intake Air Temp",      4: "Injection Timing"},
    103: {1: "HPFP Current",         2: "Fuel Rail Pressure",
          3: "LPFP Adaptation",      4: "Fuel Pump Adapt Status"},
    106: {1: "Fuel Rail Pressure",   2: "Low Pressure Pump",
          4: "Fuel Pump Duty Cycle"},
    114: {1: "Engine Speed",         2: "Engine Load",
          3: "Boost Pressure Actual", 4: "Boost Pressure Setpoint"},
}

_MED91_FAULTS: dict[int, str] = {
    # Lambda / O2 sensors (6-cylinder — two banks)
    16486: "O2 Sensor B1S1 — Signal too low",
    16487: "O2 Sensor B1S1 — Signal too high",
    16490: "O2 Sensor B2S1 — Signal too low",
    16491: "O2 Sensor B2S1 — Signal too high",
    16496: "O2 Sensor B1S2 — Response too slow",
    16500: "O2 Sensor B2S2 — Response too slow",
    16514: "O2 Sensor B1S1 — Heater circuit",
    16515: "O2 Sensor B1S2 — Heater circuit",
    16518: "O2 Sensor B2S1 — Heater circuit",
    16519: "O2 Sensor B2S2 — Heater circuit",
    16555: "Lambda regulation B1 — Control limit reached",
    16556: "Lambda regulation B1 — Adaptation out of range",
    16557: "Lambda regulation B2 — Control limit reached",
    16558: "Lambda regulation B2 — Adaptation out of range",
    # Throttle / load
    16485: "MAF Sensor — Signal out of range",
    16504: "Throttle Sensor G69 — Range/performance",
    17535: "Throttle Valve Adaptation — Not completed",
    17536: "Throttle Valve Adaptation — Error",
    # Fuel system (HPFP/LPFP — MED9.1 GDI specific)
    16684: "Fuel trim B1 — System too lean",
    16685: "Fuel trim B1 — System too rich",
    16686: "Fuel trim B2 — System too lean",
    16687: "Fuel trim B2 — System too rich",
    17520: "Fuel pressure regulation — Limit reached",
    18136: "Fuel pressure — Too low (high pressure)",
    18137: "Fuel pressure — Too high (high pressure)",
    18138: "HPFP — Volume control valve fault",
    # Knock sensors
    16716: "Knock Sensor 1 G61 — Signal out of range",
    16717: "Knock Sensor 2 G66 — Signal out of range",
    16718: "Knock Sensor 3 — Signal out of range",
    16719: "Knock Sensor 4 — Signal out of range",
    # Temperature sensors
    16603: "ECT Sensor G62 — Signal out of range",
    16604: "IAT Sensor G42 — Signal out of range",
    16618: "Oil Temperature Sensor G8 — Signal out of range",
    # Injectors (6 cylinders)
    17523: "Injector Cyl 1 N30 — Open/short",
    17524: "Injector Cyl 2 N31 — Open/short",
    17525: "Injector Cyl 3 N32 — Open/short",
    17526: "Injector Cyl 4 N33 — Open/short",
    17527: "Injector Cyl 5 N83 — Open/short",
    17528: "Injector Cyl 6 N84 — Open/short",
    # Camshaft
    16725: "Engine Speed Sensor G28 — No signal",
    16766: "Camshaft Sensor B1 G40 — Signal out of range",
    16770: "Camshaft Sensor B2 G163 — Signal out of range",
    17094: "Camshaft Adjustment B1 — Control limit reached",
    17095: "Camshaft Adjustment B2 — Control limit reached",
    # Misfire
    17740: "Random/Multiple Cylinder Misfire",
    17741: "Cylinder 1 Misfire",
    17742: "Cylinder 2 Misfire",
    17743: "Cylinder 3 Misfire",
    17744: "Cylinder 4 Misfire",
    17745: "Cylinder 5 Misfire",
    17746: "Cylinder 6 Misfire",
    # Catalyst
    16804: "Catalyst efficiency below threshold B1",
    16805: "Catalyst efficiency below threshold B2",
    # Evap / emissions
    16839: "EVAP system — Large leak",
    16840: "EVAP system — Small leak",
    # Immobiliser (Bosch Immo4 via CAN)
    17053: "Immobiliser — No CAN communication with instrument cluster",
    17054: "Immobiliser — Wrong transponder code",
    17055: "Immobiliser — Anti-start active",
    # Generic
    0:     "No fault codes stored",
}

ECU_MED91_VR6 = ECUDef(
    part_numbers   = [
        # Cayenne / Touareg / Q7 — 3.6L VR6 M55.01
        "03H906032BE", "03H906032BG", "03H906032CA", "03H906032DA",
        "03H906032EK", "03H906032L",  "03H906032DQ",
        # Golf R32 MK5 / Audi TT 3.2 — BUB 3.2L VR6
        "03H906026",
        # Golf V 2.0 TFSI / A3 2.0 TFSI — EA113 (same ECU hardware)
        "1K0907115S", "1K0907115C", "1K0907115F", "1K0907115L",
        "1K8907115F", "1K8907115L",
        # General MED9.1 fallback
        "03H906032", "1K0907115",
    ],
    name           = "Bosch MED9.1 — VR6/TFSI (03H906032 / 1K0907115)",
    address        = 0x01,
    baud           = 0,          # N/A — CAN bus transport, not K-line baud rate
    groups         = _MED91_GROUPS,
    faults         = _MED91_FAULTS,
    basic_settings = {
        60:  "Throttle body adaptation — engine warm, ignition on, foot off pedal",
        34:  "Lambda sensor aging check — requires cat temp >350°C",
    },
    notes          = (
        "Bosch MED9.1 — PowerPC MPC5554, 2MB flash, big-endian. "
        "Transport: KWP2000 over TP2.0 (VAG CAN), NOT K-line. "
        "CAN physical address: 0x01 (engine ECU). "
        "Requires CAN interface (e.g. PCAN, SocketCAN) — KKL cable NOT compatible. "
        "Security access READ: key = (seed + 0x00011170) & 0xFFFFFFFF. "
        "Security access WRITE (SA2): 5-round rotate-left XOR 0x5FBD5DBD. "
        "Flash XOR key: 'RobertCode' (LZSS compressed, then XOR'd). "
        "EEPROM immo byte: 0x59 in EEPROM dump (block_reserved1 +25). "
        "Measuring blocks: KWP2000 readDataByLocalIdentifier (0x21) + group num. "
        "VR6 variants: 03H906032xx = Cayenne/Touareg/Q7/Golf R32. "
        "TFSI variants: 1K0907115xx = Golf V 2.0 TFSI / A3 2.0 TFSI. "
        "Label file: labels/engine/06F-906-056-BLR.lbl (closest available). "
        "NOTE: TP2.0 CAN transport not yet implemented in KWPBridge. "
        "Use EliasTuning/MED9RamReader for live CAN access."
    ),
)

ALL_ECU_DEFS.append(ECU_MED91_VR6)
