"""
Mock ECU data for Digifant 1 G60 / G40 (037-906-023 family).

Simulates a warm G60 Corrado / Golf / Jetta at idle with the same
five-scenario loop as the 7A mock.

Group layout (from 037-906-023.lbl):
  Group 1 — primary diagnostic group:
    cell 1 = Engine Speed      (RPM, formula varies by ECU)
    cell 2 = Engine Load       (VAF signal, 0-255)
    cell 3 = Coolant Temp      (lower = hotter — inverse NTC)
    cell 4 = Injection Time    (ms, formula from label hints)

  Group 0 — raw undocumented:
    cell 3 = Coolant Temp      (same inverse NTC)
    cell 5 = O2S Sensor        (164-168=cold/open)

Digifant 1 notes:
  - Load is VAF (vane air flow) signal — not calculated %
  - Coolant is inverse: lower raw = hotter (different to 7A)
    Spec: 120-150 corresponds to ~80-110 degrees C
    Raw 135 = approx 87 degrees C (same target as 7A, different encoding)
  - No lambda group — O2S is raw voltage in group 0 cell 5
  - RPM in group 1 cell 1 — formula: display * 25 = RPM (same as 7A group 0)
"""

import math
import time
from dataclasses import dataclass

ECU_PART_NUMBER = "037906023"
ECU_COMPONENT   = "DIGIFANT   G60"
ECU_EXTRA       = ["Digifant1", "RV"]
FAULT_CODES     = []
WARMUP_DURATION = 180.0

_LABELS_G1 = {
    1: "Engine Speed",
    2: "Engine Load",
    3: "Coolant Temperature",
    4: "Injection Time",
}

_LABELS_G0 = {
    1: "Undocumented",
    2: "Undocumented",
    3: "Coolant Temperature",
    4: "Undocumented",
    5: "O2S Sensor",
    6: "Undocumented",
    7: "Undocumented",
    8: "Undocumented",
    9: "Undocumented",
    10: "Undocumented",
}


@dataclass
class _SV:
    rpm:      float   # cell 1 raw (RPM / 25)
    load:     float   # cell 2 raw (VAF signal 0-255)
    coolant:  float   # cell 3 raw (inverse NTC: lower=hotter, ~135=87C)
    inj_time: float   # cell 4 raw (injection time, approx ms*10)
    o2s:      float   # group 0 cell 5 (O2S voltage, 0-255)


# Inverse coolant encoding: raw 135 = ~87C, raw 110 = cold ~60C
# (opposite of 7A where raw-50=C)
_COLD  = _SV(rpm=36,  load=30,  coolant=110, inj_time=35, o2s=166)
_IDLE  = _SV(rpm=34,  load=22,  coolant=135, inj_time=28, o2s=128)
_CRUISE= _SV(rpm=100, load=85,  coolant=136, inj_time=55, o2s=128)
_WOT   = _SV(rpm=220, load=230, coolant=138, inj_time=110, o2s=40)   # rich at WOT
_DECEL = _SV(rpm=80,  load=8,   coolant=137, inj_time=0,  o2s=230)   # lean overrun


class _Scenario:
    def __init__(self, name, duration, start, end, osc=None):
        self.name     = name
        self.duration = float(duration)
        self.start    = start
        self.end      = end
        self.osc      = osc or {}


SCENARIOS = [
    _Scenario("Cold Start", 60,  _COLD,   _IDLE,
              osc={1:(2,0.7), 5:(20,0.6), 2:(3,0.5)}),
    _Scenario("Warm Idle",  60,  _IDLE,   _IDLE,
              osc={1:(1,1.5), 5:(15,0.9), 2:(2,2.0), 4:(2,1.8)}),
    _Scenario("Cruise",     60,  _CRUISE, _CRUISE,
              osc={1:(2,3.0), 5:(10,1.2), 2:(5,2.5)}),
    _Scenario("WOT Ramp",   30,  _CRUISE, _WOT,
              osc={1:(1,0.5), 5:(8,0.4),  2:(3,0.3)}),
    _Scenario("Decel",      30,  _WOT,    _DECEL,
              osc={1:(3,0.6), 5:(6,0.5),  2:(2,0.4)}),
]

SCENARIO_DURATION = sum(s.duration for s in SCENARIOS)


def _lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def _resolve(engine_t: float):
    t_loop = engine_t % SCENARIO_DURATION
    offset = 0.0
    for sc in SCENARIOS:
        if t_loop < offset + sc.duration:
            p = (t_loop - offset) / sc.duration
            s, e = sc.start, sc.end
            return _SV(
                rpm      = _lerp(s.rpm,      e.rpm,      p),
                load     = _lerp(s.load,     e.load,     p),
                coolant  = _lerp(s.coolant,  e.coolant,  p),
                inj_time = _lerp(s.inj_time, e.inj_time, p),
                o2s      = _lerp(s.o2s,      e.o2s,      p),
            ), sc, p
        offset += sc.duration
    return SCENARIOS[-1].end, SCENARIOS[-1], 1.0


def _osc(cell, sc, t):
    if cell in sc.osc:
        amp, period = sc.osc[cell]
        return amp * math.sin(2 * math.pi * t / period)
    return 0.0


def _tick_g1(cell: int, t: float, warmup_start: float) -> int:
    engine_t = t - warmup_start if warmup_start > 0 else t
    sv, sc, _ = _resolve(engine_t)
    base = {1: sv.rpm, 2: sv.load, 3: sv.coolant, 4: sv.inj_time}.get(cell, 0.0)
    return max(0, min(255, int(round(base + _osc(cell, sc, t)))))


def _tick_g0(cell: int, t: float, warmup_start: float) -> int:
    engine_t = t - warmup_start if warmup_start > 0 else t
    sv, sc, _ = _resolve(engine_t)
    # Group 0 cell 3 = coolant (same as group 1 cell 3)
    # Group 0 cell 5 = O2S sensor
    base = {3: sv.coolant, 5: sv.o2s}.get(cell, 0)
    osc  = _osc(5 if cell == 5 else cell, sc, t) if cell in (3, 5) else 0
    return max(0, min(255, int(round(base + osc))))


def get_group_1(t: float = None, warmup_start: float = None) -> list[dict]:
    """Primary diagnostic group — RPM, load, coolant, injection time."""
    if t is None:
        t = time.time()
    if warmup_start is None:
        warmup_start = t - SCENARIO_DURATION * 2

    cells = []
    for idx in range(1, 5):
        raw = _tick_g1(idx, t, warmup_start)
        if idx == 1:
            v, u, d = raw * 25.0, "RPM",  f"{raw*25:.0f} RPM"
        elif idx == 2:
            v, u, d = float(raw), "",     str(raw)           # VAF raw
        elif idx == 3:
            # Inverse coolant: approximate C = 250 - raw (rough)
            approx_c = max(-40, min(130, 250 - raw))
            v, u, d  = float(approx_c), "C",  f"{approx_c:.0f} C (approx)"
        elif idx == 4:
            v, u, d = float(raw), "ms",   f"{raw/10:.1f} ms"
        else:
            v, u, d = float(raw), "",     str(raw)
        cells.append({
            "index": idx, "formula": 0x00,
            "value": v, "unit": u, "display": d,
            "label": _LABELS_G1.get(idx, f"Cell {idx}"),
        })
    return cells


def get_group_0(t: float = None, warmup_start: float = None) -> list[dict]:
    """Group 0 — raw undocumented data with coolant and O2S."""
    if t is None:
        t = time.time()
    if warmup_start is None:
        warmup_start = t - SCENARIO_DURATION * 2

    cells = []
    for idx in range(1, 11):
        raw = _tick_g0(idx, t, warmup_start)
        if idx == 3:
            approx_c = max(-40, min(130, 250 - raw))
            v, u, d  = float(approx_c), "C", f"{approx_c:.0f} C"
        elif idx == 5:
            v_volts = raw / 255.0 * 1.1
            v, u, d = v_volts, "V", f"{v_volts:.2f} V"
        else:
            v, u, d = float(raw), "", str(raw)
        cells.append({
            "index": idx, "formula": 0x00,
            "value": v, "unit": u, "display": d,
            "label": _LABELS_G0.get(idx, f"Cell {idx}"),
        })
    return cells


def get_group(group: int, t: float = None, warmup_start: float = None) -> list[dict]:
    """Get any group — routes to group 0 or group 1."""
    if group == 0:
        return get_group_0(t, warmup_start)
    return get_group_1(t, warmup_start)


def get_scenario_info(t: float = None, warmup_start: float = None) -> dict:
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
