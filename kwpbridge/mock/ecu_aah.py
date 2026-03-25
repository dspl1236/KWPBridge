"""
Mock ECU data for 4A0906266 (AAH 2.8 V6 — MMS100).

Simulates a warm-idling AAH V6 at ~750 RPM.
"""

import math
import time

ECU_PART_NUMBER = "4A0906266"
ECU_COMPONENT   = "2.8 V6 MOTRONIC"
ECU_EXTRA       = ["MMS100", "AAH"]

FAULT_CODES = []

_BASE = {
    1:  (137, 0,    0),      # coolant: 87°C
    2:  ( 18, 2,  2.0),      # load: lower than 7A at idle
    3:  ( 30, 1,  1.5),      # RPM: 30 = 750 RPM
    4:  (  1, 0,    0),      # LL stab
    5:  (  0, 0,    0),
    6:  (128, 1,  3.0),
    7:  ( 24, 0,    0),
    8:  (128, 8,  0.8),      # lambda
    9:  (  0, 1,  2.5),
    10: ( 13, 1,  1.2),      # ignition: slightly less advance than 7A
}

WARMUP_DURATION = 180.0


def _tick(cell: int, t: float, warmup_start: float = 0.0) -> int:
    base, amp, period = _BASE[cell]
    osc = int(amp * math.sin(2 * math.pi * t / period)) if period > 0 else 0
    if cell == 1:
        elapsed = t - warmup_start
        if 0 <= elapsed < WARMUP_DURATION:
            progress = elapsed / WARMUP_DURATION
            return 110 + int((base - 110) * progress) + osc
        return max(0, min(255, base + osc))
    return max(0, min(255, base + osc))


def get_group_0(t: float = None, warmup_start: float = None) -> list[dict]:
    if t is None:
        t = time.time()
    if warmup_start is None:
        warmup_start = t - WARMUP_DURATION  # default: fully warm
    cells = []
    for cell_idx in range(1, 11):
        raw = _tick(cell_idx, t, warmup_start)
        if cell_idx == 1:
            value, unit, display = raw - 50.0, "°C", f"{raw-50:.1f} °C"
        elif cell_idx == 3:
            value, unit, display = raw * 25.0, "RPM", f"{raw*25:.0f} RPM"
        elif cell_idx == 8:
            lam = raw / 128.0
            value, unit, display = lam, "λ", f"{lam:.3f} λ"
        elif cell_idx == 10:
            deg = raw * 1.33
            value, unit, display = deg, "° BTDC", f"{deg:.1f} °BTDC"
        else:
            value, unit, display = float(raw), "", str(raw)
        cells.append({
            "index": cell_idx, "formula": 0x00,
            "value": value, "unit": unit, "display": display,
            "label": _LABELS.get(cell_idx, f"Cell {cell_idx}"),
        })
    return cells


_LABELS = {
    1: "Kühlmitteltemperatur", 2: "Motorlast", 3: "Motordrehzahl",
    4: "Lernwert LL-Stabilisierung", 5: "Lernwert LL-Stab Automatik",
    6: "Stellung LL-Stabilisierung", 7: "Schaltereingänge",
    8: "Lambdaregelung", 9: "Zündverteilerstellung", 10: "Zündwinkel",
}
