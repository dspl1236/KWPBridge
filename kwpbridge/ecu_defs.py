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
# Measuring blocks verified from VCDS sessions on Motronic 2.x / KWP1281
# 4 cells per group, standard VAG measuring block layout
# Groups 1-8 confirmed on 7A; higher groups may not all respond

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
    """Get the description for a fault code, or a generic fallback."""
    if ecu_def is None:
        return f"Fault {code:05d}"
    return ecu_def.faults.get(code, f"Fault {code:05d} — unknown")

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
