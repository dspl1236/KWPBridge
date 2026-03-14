"""
Mock ECU data for 893906266D (7A Late — MMS05C).

Simulates a warm-idling 2.3 20v 7A engine with realistic values.
Values cycle slowly to simulate a running engine — RPM bounces at idle,
coolant warms up, lambda oscillates around stoich.

Group 0 layout (from 893-906-266-D.lbl):
  cell 1 = Kühlmitteltemperatur  (coolant, raw - 50 = °C)
  cell 2 = Motorlast             (engine load, 1-255)
  cell 3 = Motordrehzahl         (RPM, raw × 25)
  cell 4 = LL-Stabilisierung     (idle stabilisation learned value)
  cell 5 = LL-Stab Automatik     (idle stab for auto gearbox)
  cell 6 = Stellung LL-Stab      (idle stab position, 128=neutral)
  cell 7 = Schaltereingänge      (switch inputs, 24=manual gearbox)
  cell 8 = Lambdaregelung        (lambda control, 128=stoich)
  cell 9 = Zündverteilerstellung (distributor position, 0=centre)
  cell 10= Zündwinkel            (ignition angle, raw × 1.33 = °BTDC)
"""

import math
import time

# ECU identity strings — what the real 266D sends on connection
ECU_PART_NUMBER = "893906266D"
ECU_COMPONENT   = "2.3 20V MOTRONIC"
ECU_EXTRA       = ["MMS05C", "7A"]

# Fault codes — none stored on a healthy car
FAULT_CODES = []

# ── Base values at warm idle ──────────────────────────────────────────────────
# These match what you'd see in VCDS group 0 on a healthy 7A at 80°C idle

_BASE = {
    # cell: (base_value, oscillation_amplitude, oscillation_period_s)
    1:  (137, 0,    0),      # coolant: 137 = 87°C  (raw - 50 = °C)
    2:  ( 22, 2,  2.0),      # load: ~22 at idle (8.6%), oscillates
    3:  ( 34, 1,  1.5),      # RPM: 34 = 850 RPM (raw × 25), idle bounce
    4:  (  2, 0,    0),      # LL stab learned: 2
    5:  (  0, 0,    0),      # LL stab auto: 0 (manual gearbox)
    6:  (128, 1,  3.0),      # LL stab position: 128=neutral ±1
    7:  ( 24, 0,    0),      # switch inputs: 24 = manual, clutch up, idle
    8:  (128, 8,  0.8),      # lambda: 128=stoich, oscillates ±8 (normal O2 swing)
    9:  (  0, 1,  2.5),      # distributor: 0=centre ±1
    10: ( 14, 1,  1.2),      # ignition: 14 × 1.33 = 18.6° BTDC at idle
}

# Warm-up profile: coolant rises from cold start over 3 minutes
WARMUP_DURATION = 180.0   # seconds to reach full temp


def _tick(cell: int, t: float, warmup_start: float = 0.0) -> int:
    """Return current raw value for a cell at time t.
    warmup_start: timestamp when engine started (default 0 = use t directly)
    """
    base, amp, period = _BASE[cell]

    # Oscillation
    osc = int(amp * math.sin(2 * math.pi * t / period)) if period > 0 else 0

    # Warm-up for coolant (cell 1)
    if cell == 1:
        elapsed = t - warmup_start
        if 0 <= elapsed < WARMUP_DURATION:
            progress = elapsed / WARMUP_DURATION
            return 110 + int((base - 110) * progress) + osc
        return base + osc

    return base + osc


def get_group_0(t: float = None, warmup_start: float = None) -> list[dict]:
    """
    Return group 0 cells as a list of cell dicts at time t.
    warmup_start: when the engine started (default: t - WARMUP_DURATION, i.e. fully warm)
    """
    if t is None:
        t = time.time()
    if warmup_start is None:
        warmup_start = t - WARMUP_DURATION   # default: fully warm

    cells = []
    for cell_idx in range(1, 11):
        raw = _tick(cell_idx, t, warmup_start)
        # Decode using label file formulas
        if cell_idx == 1:    # coolant: raw - 50 = °C
            value, unit = raw - 50.0, "°C"
            display = f"{value:.1f} °C"
        elif cell_idx == 3:  # RPM: raw × 25
            value, unit = raw * 25.0, "RPM"
            display = f"{value:.0f} RPM"
        elif cell_idx == 8:  # lambda control: 128=stoich
            value, unit = raw / 128.0, "λ"
            display = f"{value:.3f} λ"
        elif cell_idx == 10: # ignition: raw × 1.33 = °BTDC
            value, unit = raw * 1.33, "° BTDC"
            display = f"{value:.1f} °BTDC"
        else:
            value, unit = float(raw), ""
            display = str(raw)

        cells.append({
            "index":   cell_idx,
            "formula": 0x00,
            "value":   value,
            "unit":    unit,
            "display": display,
            "label":   _LABELS.get(cell_idx, f"Cell {cell_idx}"),
        })

    return cells


_LABELS = {
    1:  "Kühlmitteltemperatur",
    2:  "Motorlast",
    3:  "Motordrehzahl",
    4:  "Lernwert LL-Stabilisierung",
    5:  "Lernwert LL-Stab Automatik",
    6:  "Stellung LL-Stabilisierung",
    7:  "Schaltereingänge",
    8:  "Lambdaregelung",
    9:  "Zündverteilerstellung",
    10: "Zündwinkel",
}
