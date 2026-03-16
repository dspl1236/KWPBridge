"""
Mock ECU data for 4A0907551AA (Bosch Motronic M2.3.2 — AAN/ABY).

Simulates realistic AAN 20vT engine behaviour across six scenarios:

  COLD_START   0-60s    cold hunting idle, lean, retarded, IAC active
  WARM_IDLE   60-120s   fully warm idle, lambda oscillating, 800 RPM
  CRUISE      120-180s  3rd gear 3000 RPM, 45% load, stoich cruise
  BOOST_RUN   180-225s  WOT pull 3000→6000 RPM, 1.5 bar, rich
  DECEL       225-255s  overrun, fuel cut lean spike then stoich
  (loops back to WARM_IDLE)

Group layout (from 4A0-907-551-AA.lbl and WinlogDriver.cpp):
  Group 1: RPM, ECT, Lambda, Ignition
  Group 2: RPM, IPW, Battery, AtmPressure
  Group 3: RPM, Load, TPS, IAT
  Group 4: RPM, Load, VSS, ThrottleSwitches
  Group 5: RPM, IAC_zero, IAC_DC, LoadSwitches
  Group 6: N75_DC, N75_req, MAP_actual_kPa, MAP_req_kPa  (prjmod)
  Group 7: Knock1, Knock2, Knock3, Knock4  (×0.5 per sensor)
  Group 8: IPW_eff, IPW_deadtime, IPW_actual, IDC

Scaling (WinlogDriver.cpp confirmed):
  RPM:     raw × 40
  Load:    raw / 25.0
  Battery: raw × 0.068 = V
  ECT/IAT: (raw - 70) × 0.7 = °C  (approx: raw - 70 raw decode)
  TPS:     raw × 0.416 = %
  Lambda:  raw / 128 = λ
  IGN:     0.75 × (ign_req - knock_total) = °BTDC  (approx = raw °BTDC)
  MAP:     raw / 1.035 = kPa abs  (MPXH6400A)
  IPW_eff: raw × 0.52 = ms
  VSS:     raw × 2 = km/h
  N75 DC:  raw / 194 × 100 = %
"""

import math
import time
from dataclasses import dataclass

# ── ECU identity ──────────────────────────────────────────────────────────────

ECU_PART_NUMBER = "4A0907551AA"
ECU_COMPONENT   = "2.2l R5 MOTR.RHV"
ECU_EXTRA       = ["AAN", "prjmod 0x0202"]
FAULT_CODES     = []
WARMUP_DURATION = 120.0

# ── Engine state dataclass ────────────────────────────────────────────────────

@dataclass
class _SV:
    """Engine state snapshot — decoded engineering values."""
    rpm:      float   # RPM
    ect:      float   # °C  (raw = °C + 70)
    iat:      float   # °C
    lambda_:  float   # λ (1.0 = stoich)
    timing:   float   # °BTDC
    load:     float   # raw 1-255  (decoded = raw/25)
    tps:      float   # %  (raw = % / 0.416)
    vss:      float   # km/h  (raw = km/h / 2)
    batt:     float   # V  (raw = V / 0.068)
    map_kpa:  float   # kPa absolute  (raw = kPa × 1.035)
    n75_dc:   float   # % duty cycle  (raw = % × 194 / 100)
    ipw_ms:   float   # ms effective pulse width  (raw = ms / 0.52)
    iac_zero: float   # IAC zero point raw (70-125)
    iac_dc:   float   # IAC duty cycle raw
    knock1:   float   # knock sensor 1 units (raw × 0.5)


_COLD  = _SV(rpm=650,  ect=20,  iat=15, lambda_=0.92, timing=5,  load=30,  tps=2,
             vss=0,  batt=14.2, map_kpa=95,  n75_dc=0,  ipw_ms=4.2, iac_zero=110, iac_dc=45, knock1=0)
_IDLE  = _SV(rpm=820,  ect=90,  iat=35, lambda_=1.0,  timing=10, load=22,  tps=2,
             vss=0,  batt=14.0, map_kpa=95,  n75_dc=0,  ipw_ms=2.8, iac_zero=90,  iac_dc=30, knock1=0)
_CRUISE= _SV(rpm=3000, ect=92,  iat=38, lambda_=1.0,  timing=24, load=100, tps=30,
             vss=90, batt=13.8, map_kpa=115, n75_dc=12, ipw_ms=4.5, iac_zero=90,  iac_dc=0,  knock1=0)
_BOOST = _SV(rpm=6000, ect=96,  iat=45, lambda_=0.87, timing=20, load=230, tps=100,
             vss=150,batt=13.6, map_kpa=255, n75_dc=65, ipw_ms=9.5, iac_zero=90,  iac_dc=0,  knock1=2)
_DECEL = _SV(rpm=2500, ect=92,  iat=40, lambda_=1.4,  timing=6,  load=8,   tps=2,
             vss=80, batt=14.1, map_kpa=75,  n75_dc=0,  ipw_ms=1.5, iac_zero=90,  iac_dc=0,  knock1=0)


class _Scenario:
    def __init__(self, name, duration, start, end, osc=None):
        self.name     = name
        self.duration = float(duration)
        self.start    = start
        self.end      = end
        self.osc      = osc or {}  # {field: (amplitude, period_s)}


SCENARIOS = [
    _Scenario("Cold Start", 60,  _COLD,   _IDLE,
              osc={"rpm":(80,0.8), "lambda_":(0.12,0.5), "timing":(3,0.7), "iac_dc":(8,0.4)}),
    _Scenario("Warm Idle",  60,  _IDLE,   _IDLE,
              osc={"rpm":(25,1.5), "lambda_":(0.05,0.9), "timing":(1,1.2), "ect":(1,4.0)}),
    _Scenario("Cruise",     60,  _CRUISE, _CRUISE,
              osc={"rpm":(80,3.0), "lambda_":(0.03,1.5), "timing":(2,2.0), "load":(8,2.5)}),
    _Scenario("Boost Run",  45,  _CRUISE, _BOOST,
              osc={"rpm":(50,0.4), "lambda_":(0.04,0.5), "knock1":(1.5,0.3)}),
    _Scenario("Decel",      30,  _BOOST,  _DECEL,
              osc={"rpm":(100,0.6),"lambda_":(0.15,0.4), "load":(5,0.5)}),
]

SCENARIO_DURATION = sum(s.duration for s in SCENARIOS)


def _lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def _resolve(engine_t: float) -> tuple[_SV, "_Scenario", float]:
    t_loop = engine_t % SCENARIO_DURATION
    offset = 0.0
    for sc in SCENARIOS:
        if t_loop < offset + sc.duration:
            p = (t_loop - offset) / sc.duration
            s, e = sc.start, sc.end
            sv = _SV(
                rpm      = _lerp(s.rpm,      e.rpm,      p),
                ect      = _lerp(s.ect,      e.ect,      p),
                iat      = _lerp(s.iat,      e.iat,      p),
                lambda_  = _lerp(s.lambda_,  e.lambda_,  p),
                timing   = _lerp(s.timing,   e.timing,   p),
                load     = _lerp(s.load,     e.load,     p),
                tps      = _lerp(s.tps,      e.tps,      p),
                vss      = _lerp(s.vss,      e.vss,      p),
                batt     = _lerp(s.batt,     e.batt,     p),
                map_kpa  = _lerp(s.map_kpa,  e.map_kpa,  p),
                n75_dc   = _lerp(s.n75_dc,   e.n75_dc,   p),
                ipw_ms   = _lerp(s.ipw_ms,   e.ipw_ms,   p),
                iac_zero = _lerp(s.iac_zero, e.iac_zero, p),
                iac_dc   = _lerp(s.iac_dc,   e.iac_dc,   p),
                knock1   = _lerp(s.knock1,   e.knock1,   p),
            )
            # Apply oscillations
            for field, (amp, period) in sc.osc.items():
                osc_val = amp * math.sin(2 * math.pi * engine_t / period)
                setattr(sv, field, getattr(sv, field) + osc_val)
            return sv, sc, p
        offset += sc.duration
    return SCENARIOS[-1].end, SCENARIOS[-1], 1.0


def _make_cell(idx: int, value: float, unit: str, label: str) -> dict:
    disp = f"{value:.1f} {unit}".strip() if unit else f"{value:.1f}"
    return {"index": idx, "formula": 0x00,
            "value": round(value, 3), "unit": unit,
            "display": disp, "label": label}


def get_group(group: int, t: float = None,
              warmup_start: float = None) -> list[dict]:
    """Return the 4 cells for a given measuring block group."""
    if t is None:
        t = time.time()
    engine_t = (t - warmup_start) if warmup_start else t
    sv, sc, _ = _resolve(engine_t)
    sv.rpm      = max(0, sv.rpm)
    sv.lambda_  = max(0.5, sv.lambda_)
    sv.map_kpa  = max(60, sv.map_kpa)

    # IDC calculation
    idc = (sv.ipw_ms + 0.3) * sv.rpm / 1200.0

    if group == 1:
        return [
            _make_cell(1, sv.rpm,     "RPM",    "Engine Speed"),
            _make_cell(2, sv.ect,     "°C",     "Coolant Temperature"),
            _make_cell(3, sv.lambda_, "λ",      "Lambda Factor"),
            _make_cell(4, sv.timing,  "° BTDC", "Ignition Timing"),
        ]
    if group == 2:
        return [
            _make_cell(1, sv.rpm,    "RPM", "Engine Speed"),
            _make_cell(2, sv.ipw_ms, "ms",  "Injector Duration"),
            _make_cell(3, sv.batt,   "V",   "Battery Voltage"),
            _make_cell(4, 95.0,      "kPa", "Atmospheric Pressure"),
        ]
    if group == 3:
        return [
            _make_cell(1, sv.rpm,    "RPM", "Engine Speed"),
            _make_cell(2, sv.load,   "",    "Engine Load"),   # raw 1-255, no formula
            _make_cell(3, sv.tps,    "%",   "Throttle Angle"),
            _make_cell(4, sv.iat,    "°C",  "Intake Air Temp"),
        ]
    if group == 4:
        return [
            _make_cell(1, sv.rpm,    "RPM",  "Engine Speed"),
            _make_cell(2, sv.load,   "",     "Engine Load"),   # raw 1-255
            _make_cell(3, sv.vss,    "km/h", "Vehicle Speed"),
            _make_cell(4, 4.0,       "",     "Throttle Switches"),
        ]
    if group == 5:
        return [
            _make_cell(1, sv.rpm,      "RPM", "Engine Speed"),
            _make_cell(2, sv.iac_zero, "",    "IAC Zero Point"),
            _make_cell(3, sv.iac_dc,   "%",   "IAC Duty Cycle"),
            _make_cell(4, 4.0,         "",    "Load Switches"),
        ]
    if group == 6:
        return [
            _make_cell(1, sv.n75_dc,   "%DC",  "N75 Duty Cycle"),
            _make_cell(2, sv.n75_dc,   "%DC",  "N75 Request"),
            _make_cell(3, sv.map_kpa,  "kPa",  "MAP Actual"),
            _make_cell(4, sv.map_kpa,  "kPa",  "MAP Request"),
        ]
    if group == 7:
        k = max(0.0, sv.knock1)
        return [
            _make_cell(1, k,         "", "Knock Sensor 1"),
            _make_cell(2, k * 0.6,   "", "Knock Sensor 2"),
            _make_cell(3, k * 0.4,   "", "Knock Sensor 3"),
            _make_cell(4, k * 0.3,   "", "Knock Sensor 4"),
        ]
    if group == 8:
        return [
            _make_cell(1, sv.ipw_ms,      "ms", "Effective IPW"),
            _make_cell(2, 0.3,            "ms", "Injector Dead-time"),
            _make_cell(3, sv.ipw_ms+0.3,  "ms", "Actual IPW"),
            _make_cell(4, min(idc, 100.0),"%",  "Injector Duty Cycle"),
        ]
    # Default fallback
    return []


# mock server compatibility — the server calls get_group_0
def get_group_0(t: float = None, warmup_start: float = None) -> list[dict]:
    """Return group 1 data (primary group) as 'group 0' for mock server compat."""
    return get_group(1, t, warmup_start)


def get_scenario_info(t: float = None, warmup_start: float = None) -> dict:
    if t is None:
        t = time.time()
    engine_t = (t - warmup_start) if warmup_start else t
    _, sc, progress = _resolve(engine_t)
    return {
        "scenario":   sc.name,
        "progress":   progress,
        "loop_time":  engine_t % SCENARIO_DURATION,
        "loop_total": SCENARIO_DURATION,
    }
