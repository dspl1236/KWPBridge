"""
Mock ECU data for 06A906032BN (Bosch ME7.5 — AWP 1.8T 180hp).

Simulates realistic AWP engine behaviour across five scenarios:

  COLD_START   0-60s    cold idle 1100 RPM, rich, retarded timing, high MAF
  WARM_IDLE   60-120s   800 RPM idle, lambda adapting, EPC at position
  CRUISE      120-180s  3500 RPM, 40% load, stoich, boost ~1.1 bar
  BOOST_PULL  180-215s  WOT 3500→6200 RPM, rich, 1.6 bar, knock active
  DECEL       215-245s  foot off, fuel cut, lean spike then stoich
  (loops back to WARM_IDLE)

Measuring block layout (06A-906-032-AWP.lbl confirmed):
  001: RPM, coolant, lambda controller, basic setting flags
  002: RPM, engine load%, injection timing ms, MAF g/s
  003: RPM, MAF g/s, throttle sensor 1%, ignition timing°
  004: RPM, battery V, coolant°C, IAT°C
  005: RPM, load%, VSS km/h, load status
  010: RPM, load%, throttle%, ignition timing°
  022: RPM, load%, cyl1 KR°, cyl2 KR°
  023: RPM, load%, cyl3 KR°, cyl4 KR°
  032: lambda idle adaptation%, lambda partial adaptation%
  033: lambda controller%, O2 upstream V
  050: RPM, ST fuel trim bank1%, LT fuel trim bank1%
  060: throttle sensor1%, sensor2%, learn step count, result
  091: RPM, load%, N75 duty cycle%, boost actual mbar
  094: RPM, load%, ignition actual°, knock retard total°

Cell encoding: same as KWP1281 — [formula][A][B] = 3 bytes
  formula 0x08: RPM   = (A×256+B) × 0.25
  formula 0x04: load% = (A×256+B) × 0.01
  formula 0x02: MAF   = (A×256+B) × 0.01  g/s
  formula 0x12: temp  = (A×256+B) × 0.1 − 273.15  °C
  formula 0x07: volts = (A×256+B) × 0.001  V
  formula 0x09: timing= (A×256+B) × 0.1 − 100  °BTDC
  formula 0x0B: kPa   = (A×256+B) × 0.01
  formula 0x0F: km/h  = (A×256+B) × 0.01
  formula 0x0D: ms    = (A×256+B) × 0.001
  formula 0x10: %     = (A×256+B) × 0.01  (generic percentage)
  formula 0x03: binary flags (A byte = status bits)
"""

import math
import time
from dataclasses import dataclass

# ── ECU identity ──────────────────────────────────────────────────────────────

ECU_PART_NUMBER = "06A906032BN"
ECU_COMPONENT   = "1.8l T  ME7.5"
ECU_EXTRA       = ["AWP", "ME7.5"]
FAULT_CODES     = []
WARMUP_DURATION = 120.0

# ── Formula encode helpers ────────────────────────────────────────────────────
# Each returns (formula_byte, A, B) so mock can produce real protocol bytes

def _enc_rpm(rpm):
    """RPM: formula 0x08, value = (A*256+B)*0.25 → raw = RPM*4"""
    raw = max(0, min(65535, int(round(rpm * 4))))
    return (0x08, raw >> 8, raw & 0xFF)

def _enc_pct(pct):
    """Generic %: formula 0x04, value = (A*256+B)*0.01"""
    raw = max(0, min(65535, int(round(pct * 100))))
    return (0x04, raw >> 8, raw & 0xFF)

def _enc_maf(gs):
    """MAF g/s: formula 0x02, value = (A*256+B)*0.01"""
    raw = max(0, min(65535, int(round(gs * 100))))
    return (0x02, raw >> 8, raw & 0xFF)

def _enc_temp(deg_c):
    """Temperature °C: formula 0x12, value = (A*256+B)*0.1 - 273.15"""
    raw = max(0, min(65535, int(round((deg_c + 273.15) * 10))))
    return (0x12, raw >> 8, raw & 0xFF)

def _enc_volts(v):
    """Voltage: formula 0x07, value = (A*256+B)*0.001"""
    raw = max(0, min(65535, int(round(v * 1000))))
    return (0x07, raw >> 8, raw & 0xFF)

def _enc_timing(deg):
    """Timing °BTDC: formula 0x09, value = (A*256+B)*0.1 - 100"""
    raw = max(0, min(65535, int(round((deg + 100) * 10))))
    return (0x09, raw >> 8, raw & 0xFF)

def _enc_kpa(kpa):
    """kPa: formula 0x0B, value = (A*256+B)*0.01"""
    raw = max(0, min(65535, int(round(kpa * 100))))
    return (0x0B, raw >> 8, raw & 0xFF)

def _enc_mbar(mbar):
    """mbar via kPa formula: formula 0x0C, value = (A*256+B)*0.01 → raw=mbar*100"""
    raw = max(0, min(65535, int(round(mbar * 100))))
    return (0x0C, raw >> 8, raw & 0xFF)

def _enc_kmh(kmh):
    """Speed km/h: formula 0x0F, value = (A*256+B)*0.01"""
    raw = max(0, min(65535, int(round(kmh * 100))))
    return (0x0F, raw >> 8, raw & 0xFF)

def _enc_ms(ms):
    """Time ms: formula 0x0D, value = (A*256+B)*0.001"""
    raw = max(0, min(65535, int(round(ms * 1000))))
    return (0x0D, raw >> 8, raw & 0xFF)

def _enc_lambda(lam):
    """Lambda: formula 0x05, value = (A*256+B)*0.0001 + 0.5"""
    raw = max(0, min(65535, int(round((lam - 0.5) / 0.0001))))
    return (0x05, raw >> 8, raw & 0xFF)

def _enc_adapt(pct):
    """Adaptation %: formula 0x10, (A*256+B)*0.01 with -100% offset via 0x09"""
    # Adaptation shown as %, can be negative — use formula 0x09 (same as timing)
    raw = max(0, min(65535, int(round((pct + 100) * 10))))
    return (0x09, raw >> 8, raw & 0xFF)

def _enc_binary(flags):
    """Binary/status: formula 0x03, A = flags byte"""
    return (0x03, int(flags) & 0xFF, 0x00)


# ── Engine state ──────────────────────────────────────────────────────────────

@dataclass
class _SV:
    """Engine state snapshot — engineering values."""
    rpm:      float   # RPM
    ect:      float   # °C coolant
    iat:      float   # °C intake air
    lambda_:  float   # λ (1.0 = stoich)
    timing:   float   # °BTDC actual ignition
    load:     float   # engine load %
    maf:      float   # MAF g/s
    tps1:     float   # throttle sensor 1 %
    vss:      float   # km/h
    batt:     float   # V battery
    boost_mbar: float # boost pressure mbar absolute
    n75_dc:   float   # N75 duty cycle %
    ipw:      float   # injection pulse width ms
    lambda_idle_adapt:  float  # % idle lambda adaptation
    lambda_part_adapt:  float  # % partial throttle lambda adaptation
    lambda_ctrl:        float  # % lambda controller output
    o2_upstream_v:      float  # V upstream O2 sensor
    knock_cyl1: float          # °KR cylinder 1 retard
    knock_cyl2: float          # °KR cylinder 2
    knock_cyl3: float          # °KR cylinder 3
    knock_cyl4: float          # °KR cylinder 4
    fuel_trim_st: float        # % short-term fuel trim
    fuel_trim_lt: float        # % long-term fuel trim


_COLD  = _SV(rpm=1100, ect=20,  iat=15, lambda_=0.93, timing=5,  load=18,
             maf=5.0,  tps1=1.5, vss=0,  batt=14.2,  boost_mbar=970,
             n75_dc=0, ipw=4.8, lambda_idle_adapt=-2.0, lambda_part_adapt=-1.5,
             lambda_ctrl=-8.0, o2_upstream_v=0.12,
             knock_cyl1=0, knock_cyl2=0, knock_cyl3=0, knock_cyl4=0,
             fuel_trim_st=-3.0, fuel_trim_lt=-1.5)

_IDLE  = _SV(rpm=820,  ect=90,  iat=35, lambda_=1.0,  timing=12, load=15,
             maf=3.5,  tps1=1.8, vss=0,  batt=14.0,  boost_mbar=960,
             n75_dc=0, ipw=3.2, lambda_idle_adapt=0.5, lambda_part_adapt=0.8,
             lambda_ctrl=0.5, o2_upstream_v=0.45,
             knock_cyl1=0, knock_cyl2=0, knock_cyl3=0, knock_cyl4=0,
             fuel_trim_st=0.5, fuel_trim_lt=0.8)

_CRUISE= _SV(rpm=3500, ect=92,  iat=40, lambda_=1.0,  timing=22, load=40,
             maf=18.0, tps1=22, vss=100, batt=13.8,  boost_mbar=1100,
             n75_dc=20, ipw=5.8, lambda_idle_adapt=0.5, lambda_part_adapt=0.8,
             lambda_ctrl=1.2, o2_upstream_v=0.42,
             knock_cyl1=0, knock_cyl2=0, knock_cyl3=0, knock_cyl4=0,
             fuel_trim_st=0.8, fuel_trim_lt=1.0)

_BOOST = _SV(rpm=6200, ect=96,  iat=48, lambda_=0.88, timing=18, load=170,
             maf=80.0, tps1=95, vss=150, batt=13.6,  boost_mbar=1650,
             n75_dc=70, ipw=12.5, lambda_idle_adapt=0.5, lambda_part_adapt=0.8,
             lambda_ctrl=-6.5, o2_upstream_v=0.08,
             knock_cyl1=1.5, knock_cyl2=0.75, knock_cyl3=1.0, knock_cyl4=0.5,
             fuel_trim_st=-2.0, fuel_trim_lt=0.5)

_DECEL = _SV(rpm=2000, ect=92,  iat=42, lambda_=1.5,  timing=8,  load=5,
             maf=2.0,  tps1=1.5, vss=80, batt=14.2,  boost_mbar=950,
             n75_dc=0, ipw=0.8, lambda_idle_adapt=0.5, lambda_part_adapt=0.8,
             lambda_ctrl=12.0, o2_upstream_v=0.88,
             knock_cyl1=0, knock_cyl2=0, knock_cyl3=0, knock_cyl4=0,
             fuel_trim_st=1.5, fuel_trim_lt=0.8)


class _Scenario:
    def __init__(self, name, duration, start, end, osc=None):
        self.name     = name
        self.duration = float(duration)
        self.start    = start
        self.end      = end
        self.osc      = osc or {}


SCENARIOS = [
    _Scenario("Cold Start", 60,  _COLD,   _IDLE,
              osc={"rpm":(120,0.7), "lambda_":(0.06,0.45), "timing":(3,0.8),
                   "ect":(2,5.0), "lambda_ctrl":(3,0.5)}),
    _Scenario("Warm Idle",  60,  _IDLE,   _IDLE,
              osc={"rpm":(30,1.5), "lambda_":(0.04,0.9), "timing":(1.5,1.2),
                   "o2_upstream_v":(0.35,0.8), "lambda_ctrl":(1.5,0.9)}),
    _Scenario("Cruise",     60,  _CRUISE, _CRUISE,
              osc={"rpm":(100,3.0), "lambda_":(0.025,1.8), "maf":(2,2.5),
                   "boost_mbar":(40,3.0), "n75_dc":(5,2.0)}),
    _Scenario("Boost Pull", 35,  _CRUISE, _BOOST,
              osc={"rpm":(80,0.35), "lambda_":(0.03,0.4), "maf":(5,0.5),
                   "knock_cyl1":(1.0,0.25), "knock_cyl2":(0.5,0.3),
                   "boost_mbar":(80,0.6), "n75_dc":(8,0.5)}),
    _Scenario("Decel",      30,  _BOOST,  _DECEL,
              osc={"rpm":(200,0.7), "lambda_":(0.3,0.5), "load":(2,0.4)}),
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
            sv = _SV(**{
                f: _lerp(getattr(s, f), getattr(e, f), p)
                for f in _SV.__dataclass_fields__
            })
            for field, (amp, period) in sc.osc.items():
                osc_val = amp * math.sin(2 * math.pi * engine_t / period)
                setattr(sv, field, getattr(sv, field) + osc_val)
            # Clamp safety
            sv.rpm     = max(0, sv.rpm)
            sv.lambda_ = max(0.5, sv.lambda_)
            sv.boost_mbar = max(900, sv.boost_mbar)
            sv.knock_cyl1 = max(0, sv.knock_cyl1)
            sv.knock_cyl2 = max(0, sv.knock_cyl2)
            sv.knock_cyl3 = max(0, sv.knock_cyl3)
            sv.knock_cyl4 = max(0, sv.knock_cyl4)
            return sv, sc, p
        offset += sc.duration
    return SCENARIOS[-1].end, SCENARIOS[-1], 1.0


# ── Cell builders ─────────────────────────────────────────────────────────────

def _cell(index, formula, a, b, value, unit, label, display=None):
    return {
        "index": index, "formula": formula, "a": a, "b": b,
        "value": round(value, 3), "unit": unit, "label": label,
        "display": display or f"{value:.1f} {unit}".strip(),
    }


def _c(index, encoder_result, label, value_decoded, unit):
    """Build cell from encoder (formula, A, B) + decoded value."""
    f, a, b = encoder_result
    return _cell(index, f, a, b, value_decoded, unit, label)


def get_group(group: int, t: float = None,
              warmup_start: float = None) -> list[dict]:
    """Return decoded cells for a ME7 measuring block group."""
    if t is None:
        t = time.time()
    engine_t = (t - warmup_start) if warmup_start else t
    sv, sc, _ = _resolve(engine_t)

    if group == 1:
        return [
            _c(1, _enc_rpm(sv.rpm),         "Engine Speed",         sv.rpm,    "RPM"),
            _c(2, _enc_temp(sv.ect),         "Coolant Temperature",  sv.ect,    "°C"),
            _c(3, _enc_adapt(sv.lambda_ctrl),"Lambda Controller",    sv.lambda_ctrl, "%"),
            _c(4, _enc_binary(0b01111111),   "Basic Setting Flags",  0b01111111, ""),
        ]
    if group == 2:
        return [
            _c(1, _enc_rpm(sv.rpm),    "Engine Speed",     sv.rpm,  "RPM"),
            _c(2, _enc_pct(sv.load),   "Engine Load",      sv.load, "%"),
            _c(3, _enc_ms(sv.ipw),     "Injection Timing", sv.ipw,  "ms"),
            _c(4, _enc_maf(sv.maf),    "Intake Air Mass",  sv.maf,  "g/s"),
        ]
    if group == 3:
        return [
            _c(1, _enc_rpm(sv.rpm),    "Engine Speed",         sv.rpm,   "RPM"),
            _c(2, _enc_maf(sv.maf),    "Intake Air Mass",      sv.maf,   "g/s"),
            _c(3, _enc_pct(sv.tps1),   "Throttle Sensor 1",    sv.tps1,  "%"),
            _c(4, _enc_timing(sv.timing),"Ignition Timing Angle",sv.timing,"° BTDC"),
        ]
    if group == 4:
        return [
            _c(1, _enc_rpm(sv.rpm),    "Engine Speed",     sv.rpm,  "RPM"),
            _c(2, _enc_volts(sv.batt), "Voltage Supply",   sv.batt, "V"),
            _c(3, _enc_temp(sv.ect),   "Coolant Temp",     sv.ect,  "°C"),
            _c(4, _enc_temp(sv.iat),   "Intake Air Temp",  sv.iat,  "°C"),
        ]
    if group == 5:
        status = 1 if sv.load < 20 else (2 if sv.load < 80 else 3)
        return [
            _c(1, _enc_rpm(sv.rpm),   "Engine Speed",  sv.rpm,  "RPM"),
            _c(2, _enc_pct(sv.load),  "Engine Load",   sv.load, "%"),
            _c(3, _enc_kmh(sv.vss),   "Vehicle Speed", sv.vss,  "km/h"),
            _c(4, _enc_binary(status),"Load Status",   status,  ""),
        ]
    if group == 10:
        return [
            _c(1, _enc_rpm(sv.rpm),       "Engine Speed",     sv.rpm,    "RPM"),
            _c(2, _enc_pct(sv.load),      "Engine Load",      sv.load,   "%"),
            _c(3, _enc_pct(sv.tps1),      "Throttle Sensor 1",sv.tps1,   "%"),
            _c(4, _enc_timing(sv.timing), "Ignition Timing",  sv.timing,  "° BTDC"),
        ]
    if group == 22:
        return [
            _c(1, _enc_rpm(sv.rpm),           "Engine Speed",       sv.rpm,       "RPM"),
            _c(2, _enc_pct(sv.load),          "Engine Load",        sv.load,      "%"),
            _c(3, _enc_timing(-sv.knock_cyl1),"Cyl 1 Knock Retard", -sv.knock_cyl1,"°"),
            _c(4, _enc_timing(-sv.knock_cyl2),"Cyl 2 Knock Retard", -sv.knock_cyl2,"°"),
        ]
    if group == 23:
        return [
            _c(1, _enc_rpm(sv.rpm),           "Engine Speed",       sv.rpm,       "RPM"),
            _c(2, _enc_pct(sv.load),          "Engine Load",        sv.load,      "%"),
            _c(3, _enc_timing(-sv.knock_cyl3),"Cyl 3 Knock Retard", -sv.knock_cyl3,"°"),
            _c(4, _enc_timing(-sv.knock_cyl4),"Cyl 4 Knock Retard", -sv.knock_cyl4,"°"),
        ]
    if group == 32:
        return [
            _c(1, _enc_adapt(sv.lambda_idle_adapt), "Lambda Idle Adapt",  sv.lambda_idle_adapt, "%"),
            _c(2, _enc_adapt(sv.lambda_part_adapt), "Lambda Partial Adapt",sv.lambda_part_adapt, "%"),
        ]
    if group == 33:
        return [
            _c(1, _enc_adapt(sv.lambda_ctrl),    "Lambda Controller",    sv.lambda_ctrl,   "%"),
            _c(2, _enc_volts(sv.o2_upstream_v),  "O2 Sensor 1 Upstream", sv.o2_upstream_v, "V"),
        ]
    if group == 50:
        return [
            _c(1, _enc_rpm(sv.rpm),              "Engine Speed",       sv.rpm,           "RPM"),
            _c(2, _enc_adapt(sv.fuel_trim_st),   "ST Fuel Trim Bank1", sv.fuel_trim_st,  "%"),
            _c(3, _enc_adapt(sv.fuel_trim_lt),   "LT Fuel Trim Bank1", sv.fuel_trim_lt,  "%"),
        ]
    if group == 60:
        tps2 = 100.0 - sv.tps1   # complementary sensor
        return [
            _c(1, _enc_pct(sv.tps1),         "Throttle Sensor 1",    sv.tps1, "%"),
            _c(2, _enc_pct(tps2),            "Throttle Sensor 2",    tps2,    "%"),
            _c(3, _enc_binary(8),            "Learn Step Counter",    8,       ""),
            _c(4, _enc_binary(1),            "Throttle Adaptation",   1,       ""),
        ]
    if group == 91:
        return [
            _c(1, _enc_rpm(sv.rpm),          "Engine Speed",       sv.rpm,         "RPM"),
            _c(2, _enc_pct(sv.load),         "Engine Load",        sv.load,        "%"),
            _c(3, _enc_pct(sv.n75_dc),       "N75 Duty Cycle",     sv.n75_dc,      "%"),
            _c(4, _enc_mbar(sv.boost_mbar),  "Boost Pressure Act", sv.boost_mbar,  "mbar"),
        ]
    if group == 94:
        kr_total = (sv.knock_cyl1 + sv.knock_cyl2 +
                    sv.knock_cyl3 + sv.knock_cyl4) / 4.0
        return [
            _c(1, _enc_rpm(sv.rpm),        "Engine Speed",     sv.rpm,     "RPM"),
            _c(2, _enc_pct(sv.load),       "Engine Load",      sv.load,    "%"),
            _c(3, _enc_timing(sv.timing),  "Ignition Actual",  sv.timing,  "° BTDC"),
            _c(4, _enc_timing(-kr_total),  "Knock Retard Total",-kr_total, "°"),
        ]
    return []


def get_group_0(t: float = None, warmup_start: float = None) -> list[dict]:
    """Return group 1 as 'group 0' for mock server compatibility."""
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
