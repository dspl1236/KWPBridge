"""
Mock ECU data for 893906266D (7A Late — MMS05C).

Simulates realistic engine behaviour across five scenarios that loop
automatically, exercising the full range of the map overlay:

  COLD_START  0-60s    cold hunting idle, lean swings, low advance
  WARM_IDLE   60-120s  fully warm stable idle, lambda oscillating
  CRUISE      120-180s part throttle 2500 RPM, 50% load, stoich
  WOT_RAMP    180-210s WOT pull 2000→5500 RPM, rich
  DECEL       210-240s foot off, RPM drops, lean overrun
  (loops back to WARM_IDLE)

Group 0 layout (from 893-906-266-D.lbl):
  cell 1  = Kuehlmitteltemperatur  (coolant, raw - 50 = C)
  cell 2  = Motorlast              (engine load, 1-255)
  cell 3  = Motordrehzahl          (RPM, raw x 25)
  cell 4  = LL-Stabilisierung      (idle stab learned value)
  cell 5  = LL-Stab Automatik      (idle stab for auto gearbox)
  cell 6  = Stellung LL-Stab       (idle stab position, 128=neutral)
  cell 7  = Schaltereingaenge      (switch inputs, 24=manual gearbox)
  cell 8  = Lambdaregelung         (lambda control, 128=stoich)
  cell 9  = Zuendverteilerstellung (distributor position, 0=centre)
  cell 10 = Zuendwinkel            (ignition angle, raw x 1.33 = BTDC)
"""

import math
import time
from dataclasses import dataclass

# ECU identity
ECU_PART_NUMBER = "893906266D"
ECU_COMPONENT   = "2.3 20V MOTRONIC"
ECU_EXTRA       = ["MMS05C", "7A"]
FAULT_CODES     = []
WARMUP_DURATION = 180.0

_LABELS = {
    1:  "Kuehlmitteltemperatur",
    2:  "Motorlast",
    3:  "Motordrehzahl",
    4:  "Lernwert LL-Stabilisierung",
    5:  "Lernwert LL-Stab Automatik",
    6:  "Stellung LL-Stabilisierung",
    7:  "Schaltereingaenge",
    8:  "Lambdaregelung",
    9:  "Zuendverteilerstellung",
    10: "Zuendwinkel",
}


@dataclass
class _SV:
    """Engine state snapshot — raw cell values."""
    coolant: float   # cell 1  raw  (C + 50)
    load:    float   # cell 2  raw  (1-255)
    rpm:     float   # cell 3  raw  (RPM / 25)
    ll_stab: float   # cell 6  raw  (128=neutral)
    lambda_: float   # cell 8  raw  (128=stoich)
    ignition:float   # cell 10 raw  (BTDC / 1.33)


_COLD  = _SV(coolant=110, load=30,  rpm=36,  ll_stab=135, lambda_=145, ignition=10)
_IDLE  = _SV(coolant=137, load=22,  rpm=34,  ll_stab=128, lambda_=128, ignition=14)
_CRUISE= _SV(coolant=138, load=80,  rpm=100, ll_stab=128, lambda_=128, ignition=22)
_WOT   = _SV(coolant=142, load=220, rpm=220, ll_stab=128, lambda_=112, ignition=18)
_DECEL = _SV(coolant=140, load=8,   rpm=80,  ll_stab=128, lambda_=148, ignition=8)


class _Scenario:
    def __init__(self, name, duration, start, end, osc=None):
        self.name     = name
        self.duration = float(duration)
        self.start    = start
        self.end      = end
        self.osc      = osc or {}  # {cell: (amplitude, period_s)}


SCENARIOS = [
    _Scenario("Cold Start", 60,  _COLD,   _IDLE,
              osc={3:(2,0.7), 8:(20,0.6), 6:(8,0.4)}),
    _Scenario("Warm Idle",  60,  _IDLE,   _IDLE,
              osc={3:(1,1.5), 8:(8,0.8),  6:(1,3.0), 2:(2,2.0), 10:(1,1.2)}),
    _Scenario("Cruise",     60,  _CRUISE, _CRUISE,
              osc={3:(2,3.0), 8:(5,1.2),  2:(5,2.5), 10:(2,2.0)}),
    _Scenario("WOT Ramp",   30,  _CRUISE, _WOT,
              osc={3:(1,0.5), 8:(4,0.4),  2:(3,0.3)}),
    _Scenario("Decel",      30,  _WOT,    _DECEL,
              osc={3:(3,0.6), 8:(6,0.5),  2:(2,0.4)}),
]

SCENARIO_DURATION = sum(s.duration for s in SCENARIOS)


def _lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def _resolve(engine_t: float):
    """Return (interpolated _SV, Scenario, progress) for engine time."""
    t_loop = engine_t % SCENARIO_DURATION
    offset = 0.0
    for sc in SCENARIOS:
        if t_loop < offset + sc.duration:
            p = (t_loop - offset) / sc.duration
            s, e = sc.start, sc.end
            return _SV(
                coolant  = _lerp(s.coolant,  e.coolant,  p),
                load     = _lerp(s.load,     e.load,     p),
                rpm      = _lerp(s.rpm,      e.rpm,      p),
                ll_stab  = _lerp(s.ll_stab,  e.ll_stab,  p),
                lambda_  = _lerp(s.lambda_,  e.lambda_,  p),
                ignition = _lerp(s.ignition, e.ignition, p),
            ), sc, p
        offset += sc.duration
    return SCENARIOS[-1].end, SCENARIOS[-1], 1.0


def _tick(cell: int, t: float, warmup_start: float = 0.0) -> int:
    engine_t = t - warmup_start if warmup_start > 0 else t
    sv, sc, _ = _resolve(engine_t)

    base = {
        1: sv.coolant, 2: sv.load,    3: sv.rpm,
        4: 2.0,        5: 0.0,        6: sv.ll_stab,
        7: 24.0,       8: sv.lambda_, 9: 0.0,
        10: sv.ignition,
    }.get(cell, 0.0)

    osc = 0.0
    if cell in sc.osc:
        amp, period = sc.osc[cell]
        osc = amp * math.sin(2 * math.pi * t / period)

    return max(0, min(255, int(round(base + osc))))


def get_group_0(t: float = None, warmup_start: float = None) -> list[dict]:
    """Return group 0 cells at time t."""
    if t is None:
        t = time.time()
    if warmup_start is None:
        warmup_start = t - SCENARIO_DURATION * 2

    cells = []
    for idx in range(1, 11):
        raw = _tick(idx, t, warmup_start)
        if idx == 1:
            v, u, d = raw - 50.0, "°C",    f"{raw-50:.1f} °C"
        elif idx == 3:
            v, u, d = raw * 25.0, "RPM",   f"{raw*25:.0f} RPM"
        elif idx == 8:
            lam = raw / 128.0
            v, u, d = lam, "λ",     f"{lam:.3f} λ"
        elif idx == 10:
            deg = raw * 1.33
            v, u, d = deg, "° BTDC", f"{deg:.1f} °BTDC"
        else:
            v, u, d = float(raw), "", str(raw)
        cells.append({
            "index": idx, "formula": 0x00,
            "value": v, "unit": u, "display": d,
            "label": _LABELS.get(idx, f"Cell {idx}"),
        })
    return cells


def get_scenario_info(t: float = None, warmup_start: float = None) -> dict:
    """Return current scenario name and progress — for debug UI."""
    if t is None:
        t = time.time()
    if warmup_start is None:
        warmup_start = t - SCENARIO_DURATION * 2
    engine_t = t - warmup_start
    _, sc, progress = _resolve(engine_t)
    return {
        "scenario":   sc.name,
        "progress":   progress,
        "loop_time":  engine_t % SCENARIO_DURATION,
        "loop_total": SCENARIO_DURATION,
    }
