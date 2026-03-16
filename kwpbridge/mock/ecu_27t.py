"""
Mock ECU data for 8D0907551M (Bosch ME7.1 — AGB 2.7T 250hp S4 B5).

Simulates realistic twin-turbo engine behaviour across five scenarios:

  COLD_START   0-60s    cold hunting idle, rich, boost near zero
  WARM_IDLE   60-120s   800 RPM stable idle, closed loop, low boost
  CRUISE      120-180s  3200 RPM, 35% load, stoich, light boost
  BOOST_PULL  180-215s  WOT 3500→6000 RPM, rich, ~1.5 bar, knock on one bank
  DECEL       215-245s  foot off, DFCO, lean spike, boost collapses
  (loops back to WARM_IDLE)

Measuring block layout (8D0907551M / ME7.1 S4 B5):
  001: RPM, coolant, lambda controller B1, basic setting flags
  002: RPM, engine load%, injection timing ms, MAF g/s
  003: RPM, MAF g/s, throttle%, ignition timing° BTDC
  004: RPM, battery V, coolant°C, IAT°C
  005: RPM, load%, VSS km/h, load status
  010: RPM, load%, throttle%, ignition timing°
  022: RPM, load%, cyl1 KR°, cyl2 KR° (Bank 1)
  023: RPM, load%, cyl3 KR°, cyl4 KR° (Bank 1 ctd / Bank 2 start)
  032: lambda B1 idle adapt%, lambda B1 partial adapt%
  033: lambda controller B1%, O2 upstream B1 V
  034: lambda controller B2%, O2 upstream B2 V  ← 2.7T has two banks
  050: RPM, ST fuel trim B1%, LT fuel trim B1%
  051: RPM, ST fuel trim B2%, LT fuel trim B2%  ← 2.7T second bank
  060: throttle sensor1%, sensor2%, learn step, result
  091: RPM, load%, N75 duty cycle%, boost actual mbar
  094: RPM, load%, ignition actual°, knock retard total°

The 2.7T has TWO lambda banks (B1=cylinders 1-3, B2=cylinders 4-6).
Groups 034 and 051 are unique to the biturbo layout.

Cell encoding: same as ME7.5 (KWP2000 formula bytes).
"""

import math
import time
from dataclasses import dataclass


ECU_PART_NUMBER = "8D0907551M"
ECU_COMPONENT   = "2.7l V6  ME7.1  "
ECU_EXTRA       = ["AGB", "ME7.1", "S4", "2.7T"]
FAULT_CODES     = []
WARMUP_DURATION = 120.0

# ── Formula encode helpers ────────────────────────────────────────────────────

def _enc_rpm(rpm):
    raw = max(0, min(65535, int(round(rpm * 4))))
    return (0x08, raw >> 8, raw & 0xFF)

def _enc_pct(pct):
    raw = max(0, min(65535, int(round(pct * 100))))
    return (0x04, raw >> 8, raw & 0xFF)

def _enc_maf(gs):
    raw = max(0, min(65535, int(round(gs * 100))))
    return (0x02, raw >> 8, raw & 0xFF)

def _enc_temp(deg_c):
    raw = max(0, min(65535, int(round((deg_c + 273.15) * 10))))
    return (0x12, raw >> 8, raw & 0xFF)

def _enc_volts(v):
    raw = max(0, min(65535, int(round(v * 1000))))
    return (0x07, raw >> 8, raw & 0xFF)

def _enc_timing(deg):
    raw = max(0, min(65535, int(round((deg + 100) * 10))))
    return (0x09, raw >> 8, raw & 0xFF)

def _enc_mbar(mbar):
    raw = max(0, min(65535, int(round(mbar * 100))))
    return (0x0C, raw >> 8, raw & 0xFF)

def _enc_kmh(kmh):
    raw = max(0, min(65535, int(round(kmh * 100))))
    return (0x0F, raw >> 8, raw & 0xFF)

def _enc_ms(ms):
    raw = max(0, min(65535, int(round(ms * 1000))))
    return (0x0D, raw >> 8, raw & 0xFF)

def _enc_adapt(pct):
    raw = max(0, min(65535, int(round((pct + 100) * 10))))
    return (0x09, raw >> 8, raw & 0xFF)

def _enc_binary(flags):
    return (0x03, int(flags) & 0xFF, 0x00)


# ── Engine state ──────────────────────────────────────────────────────────────

@dataclass
class _SV:
    rpm:          float
    ect:          float
    iat:          float
    lambda_b1:    float   # Bank 1 lambda (cyl 1-3)
    lambda_b2:    float   # Bank 2 lambda (cyl 4-6)
    timing:       float
    load:         float
    maf:          float
    tps1:         float
    vss:          float
    batt:         float
    boost_mbar:   float
    n75_dc:       float
    ipw:          float
    lambda_idle_b1:  float
    lambda_part_b1:  float
    lambda_idle_b2:  float
    lambda_part_b2:  float
    lambda_ctrl_b1:  float
    lambda_ctrl_b2:  float
    o2_b1:        float
    o2_b2:        float
    knock_cyl1:   float
    knock_cyl2:   float
    knock_cyl3:   float
    knock_cyl4:   float   # B2 start
    fuel_trim_st_b1: float
    fuel_trim_lt_b1: float
    fuel_trim_st_b2: float
    fuel_trim_lt_b2: float


_COLD = _SV(
    rpm=1050, ect=18, iat=14, lambda_b1=0.91, lambda_b2=0.92,
    timing=4, load=16, maf=4.5, tps1=1.4, vss=0, batt=14.2,
    boost_mbar=960, n75_dc=0, ipw=5.2,
    lambda_idle_b1=-3.0, lambda_part_b1=-1.8,
    lambda_idle_b2=-2.5, lambda_part_b2=-1.5,
    lambda_ctrl_b1=-9.0, lambda_ctrl_b2=-8.5,
    o2_b1=0.10, o2_b2=0.11,
    knock_cyl1=0, knock_cyl2=0, knock_cyl3=0, knock_cyl4=0,
    fuel_trim_st_b1=-4.0, fuel_trim_lt_b1=-2.0,
    fuel_trim_st_b2=-3.5, fuel_trim_lt_b2=-1.8,
)

_IDLE = _SV(
    rpm=810, ect=90, iat=34, lambda_b1=1.0, lambda_b2=1.0,
    timing=11, load=14, maf=3.2, tps1=1.7, vss=0, batt=13.9,
    boost_mbar=950, n75_dc=0, ipw=3.0,
    lambda_idle_b1=0.4, lambda_part_b1=0.7,
    lambda_idle_b2=0.3, lambda_part_b2=0.6,
    lambda_ctrl_b1=0.4, lambda_ctrl_b2=0.3,
    o2_b1=0.44, o2_b2=0.43,
    knock_cyl1=0, knock_cyl2=0, knock_cyl3=0, knock_cyl4=0,
    fuel_trim_st_b1=0.4, fuel_trim_lt_b1=0.7,
    fuel_trim_st_b2=0.3, fuel_trim_lt_b2=0.6,
)

_CRUISE = _SV(
    rpm=3200, ect=92, iat=38, lambda_b1=1.0, lambda_b2=1.0,
    timing=20, load=35, maf=16.0, tps1=20, vss=95, batt=13.7,
    boost_mbar=1080, n75_dc=15, ipw=5.2,
    lambda_idle_b1=0.4, lambda_part_b1=0.7,
    lambda_idle_b2=0.3, lambda_part_b2=0.6,
    lambda_ctrl_b1=1.1, lambda_ctrl_b2=0.9,
    o2_b1=0.43, o2_b2=0.41,
    knock_cyl1=0, knock_cyl2=0, knock_cyl3=0, knock_cyl4=0,
    fuel_trim_st_b1=0.7, fuel_trim_lt_b1=0.9,
    fuel_trim_st_b2=0.5, fuel_trim_lt_b2=0.8,
)

_BOOST = _SV(
    rpm=6000, ect=95, iat=46, lambda_b1=0.87, lambda_b2=0.86,
    timing=17, load=160, maf=75.0, tps1=95, vss=145, batt=13.5,
    boost_mbar=1520, n75_dc=65, ipw=11.8,
    lambda_idle_b1=0.4, lambda_part_b1=0.7,
    lambda_idle_b2=0.3, lambda_part_b2=0.6,
    lambda_ctrl_b1=-6.0, lambda_ctrl_b2=-5.5,
    o2_b1=0.08, o2_b2=0.07,
    knock_cyl1=1.2, knock_cyl2=0.5, knock_cyl3=0, knock_cyl4=2.0,
    fuel_trim_st_b1=-2.5, fuel_trim_lt_b1=0.4,
    fuel_trim_st_b2=-2.0, fuel_trim_lt_b2=0.5,
)

_DECEL = _SV(
    rpm=1800, ect=91, iat=40, lambda_b1=1.6, lambda_b2=1.5,
    timing=7, load=4, maf=1.8, tps1=1.4, vss=75, batt=14.1,
    boost_mbar=940, n75_dc=0, ipw=0.5,
    lambda_idle_b1=0.4, lambda_part_b1=0.7,
    lambda_idle_b2=0.3, lambda_part_b2=0.6,
    lambda_ctrl_b1=11.5, lambda_ctrl_b2=10.8,
    o2_b1=0.87, o2_b2=0.84,
    knock_cyl1=0, knock_cyl2=0, knock_cyl3=0, knock_cyl4=0,
    fuel_trim_st_b1=1.4, fuel_trim_lt_b1=0.7,
    fuel_trim_st_b2=1.2, fuel_trim_lt_b2=0.6,
)


class _Scenario:
    def __init__(self, name, duration, start, end, osc=None):
        self.name     = name
        self.duration = float(duration)
        self.start    = start
        self.end      = end
        self.osc      = osc or {}


SCENARIOS = [
    _Scenario("Cold Start", 60,  _COLD,   _IDLE,
              osc={"rpm": (90, 0.7), "lambda_b1": (0.06, 0.45),
                   "lambda_b2": (0.05, 0.50), "ect": (2, 5.0)}),
    _Scenario("Warm Idle",  60,  _IDLE,   _IDLE,
              osc={"rpm": (25, 1.5), "lambda_b1": (0.04, 0.9),
                   "lambda_b2": (0.04, 0.85), "o2_b1": (0.35, 0.8),
                   "o2_b2": (0.33, 0.82)}),
    _Scenario("Cruise",     60,  _CRUISE, _CRUISE,
              osc={"rpm": (80, 3.0), "boost_mbar": (35, 3.0), "n75_dc": (4, 2.0)}),
    _Scenario("Boost Pull", 35,  _CRUISE, _BOOST,
              osc={"rpm": (60, 0.35), "lambda_b1": (0.025, 0.4),
                   "lambda_b2": (0.020, 0.38),
                   "knock_cyl1": (0.8, 0.22), "knock_cyl4": (1.2, 0.18),
                   "boost_mbar": (70, 0.55)}),
    _Scenario("Decel",      30,  _BOOST,  _DECEL,
              osc={"rpm": (180, 0.7), "lambda_b1": (0.3, 0.5),
                   "lambda_b2": (0.25, 0.45)}),
]

SCENARIO_DURATION = sum(s.duration for s in SCENARIOS)


def _lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def _resolve(engine_t: float):
    t = engine_t % SCENARIO_DURATION
    offset = 0.0
    for sc in SCENARIOS:
        if t < offset + sc.duration:
            p  = (t - offset) / sc.duration
            s, e = sc.start, sc.end
            sv = _SV(**{f: _lerp(getattr(s, f), getattr(e, f), p)
                        for f in _SV.__dataclass_fields__})
            for field, (amp, period) in sc.osc.items():
                osc_v = amp * math.sin(2 * math.pi * engine_t / period)
                setattr(sv, field, getattr(sv, field) + osc_v)
            sv.rpm          = max(0, sv.rpm)
            sv.lambda_b1    = max(0.5, sv.lambda_b1)
            sv.lambda_b2    = max(0.5, sv.lambda_b2)
            sv.boost_mbar   = max(900, sv.boost_mbar)
            sv.knock_cyl1   = max(0, sv.knock_cyl1)
            sv.knock_cyl2   = max(0, sv.knock_cyl2)
            sv.knock_cyl3   = max(0, sv.knock_cyl3)
            sv.knock_cyl4   = max(0, sv.knock_cyl4)
            return sv, sc, p
        offset += sc.duration
    return SCENARIOS[-1].end, SCENARIOS[-1], 1.0


# ── Cell builder ──────────────────────────────────────────────────────────────

def _c(index, encoder_result, label, value_decoded, unit):
    f, a, b = encoder_result
    return {"index": index, "formula": f, "a": a, "b": b,
            "value": round(value_decoded, 3), "unit": unit, "label": label,
            "display": f"{value_decoded:.1f} {unit}".strip()}


def get_group(group: int, t: float = None,
              warmup_start: float = None) -> list:
    if t is None:
        t = time.time()
    engine_t = (t - warmup_start) if warmup_start else t
    sv, sc, _ = _resolve(engine_t)

    if group == 1:
        return [
            _c(1, _enc_rpm(sv.rpm),          "Engine Speed",        sv.rpm,   "RPM"),
            _c(2, _enc_temp(sv.ect),          "Coolant Temp",        sv.ect,   "°C"),
            _c(3, _enc_adapt(sv.lambda_ctrl_b1), "Lambda Ctrl B1",   sv.lambda_ctrl_b1, "%"),
            _c(4, _enc_binary(0b01111111),    "Basic Flags",         0x7F,     ""),
        ]
    if group == 2:
        return [
            _c(1, _enc_rpm(sv.rpm),   "Engine Speed",  sv.rpm,  "RPM"),
            _c(2, _enc_pct(sv.load),  "Engine Load",   sv.load, "%"),
            _c(3, _enc_ms(sv.ipw),    "Injection PW",  sv.ipw,  "ms"),
            _c(4, _enc_maf(sv.maf),   "Air Mass",      sv.maf,  "g/s"),
        ]
    if group == 3:
        return [
            _c(1, _enc_rpm(sv.rpm),         "Engine Speed",    sv.rpm,    "RPM"),
            _c(2, _enc_maf(sv.maf),         "Air Mass",        sv.maf,    "g/s"),
            _c(3, _enc_pct(sv.tps1),        "Throttle",        sv.tps1,   "%"),
            _c(4, _enc_timing(sv.timing),   "Ignition Timing", sv.timing, "°BTDC"),
        ]
    if group == 4:
        return [
            _c(1, _enc_rpm(sv.rpm),    "Engine Speed", sv.rpm,  "RPM"),
            _c(2, _enc_volts(sv.batt), "Battery V",    sv.batt, "V"),
            _c(3, _enc_temp(sv.ect),   "Coolant Temp", sv.ect,  "°C"),
            _c(4, _enc_temp(sv.iat),   "IAT",          sv.iat,  "°C"),
        ]
    if group == 5:
        status = 1 if sv.load < 20 else (2 if sv.load < 80 else 3)
        return [
            _c(1, _enc_rpm(sv.rpm),          "Engine Speed", sv.rpm,  "RPM"),
            _c(2, _enc_pct(sv.load),         "Engine Load",  sv.load, "%"),
            _c(3, _enc_kmh(sv.vss),          "Vehicle Speed",sv.vss,  "km/h"),
            _c(4, _enc_binary(status),       "Load Status",  status,  ""),
        ]
    if group == 10:
        return [
            _c(1, _enc_rpm(sv.rpm),         "Engine Speed",    sv.rpm,   "RPM"),
            _c(2, _enc_pct(sv.load),        "Engine Load",     sv.load,  "%"),
            _c(3, _enc_pct(sv.tps1),        "Throttle",        sv.tps1,  "%"),
            _c(4, _enc_timing(sv.timing),   "Ignition Timing", sv.timing,"°BTDC"),
        ]
    if group == 22:
        return [
            _c(1, _enc_rpm(sv.rpm),               "Engine Speed",    sv.rpm,        "RPM"),
            _c(2, _enc_pct(sv.load),              "Engine Load",     sv.load,       "%"),
            _c(3, _enc_timing(-sv.knock_cyl1),    "Cyl1 KR",        -sv.knock_cyl1, "°"),
            _c(4, _enc_timing(-sv.knock_cyl2),    "Cyl2 KR",        -sv.knock_cyl2, "°"),
        ]
    if group == 23:
        return [
            _c(1, _enc_rpm(sv.rpm),               "Engine Speed",    sv.rpm,        "RPM"),
            _c(2, _enc_pct(sv.load),              "Engine Load",     sv.load,       "%"),
            _c(3, _enc_timing(-sv.knock_cyl3),    "Cyl3 KR",        -sv.knock_cyl3, "°"),
            _c(4, _enc_timing(-sv.knock_cyl4),    "Cyl4 KR (B2)",   -sv.knock_cyl4, "°"),
        ]
    if group == 32:
        return [
            _c(1, _enc_adapt(sv.lambda_idle_b1), "Idle Adapt B1",  sv.lambda_idle_b1, "%"),
            _c(2, _enc_adapt(sv.lambda_part_b1), "Part Adapt B1",  sv.lambda_part_b1, "%"),
        ]
    if group == 33:
        return [
            _c(1, _enc_adapt(sv.lambda_ctrl_b1), "Lambda Ctrl B1", sv.lambda_ctrl_b1, "%"),
            _c(2, _enc_volts(sv.o2_b1),          "O2 B1 Upstream", sv.o2_b1,         "V"),
        ]
    if group == 34:
        return [
            _c(1, _enc_adapt(sv.lambda_ctrl_b2), "Lambda Ctrl B2", sv.lambda_ctrl_b2, "%"),
            _c(2, _enc_volts(sv.o2_b2),          "O2 B2 Upstream", sv.o2_b2,         "V"),
        ]
    if group == 50:
        return [
            _c(1, _enc_rpm(sv.rpm),                 "Engine Speed",  sv.rpm,           "RPM"),
            _c(2, _enc_adapt(sv.fuel_trim_st_b1),   "STFT B1",       sv.fuel_trim_st_b1, "%"),
            _c(3, _enc_adapt(sv.fuel_trim_lt_b1),   "LTFT B1",       sv.fuel_trim_lt_b1, "%"),
        ]
    if group == 51:
        return [
            _c(1, _enc_rpm(sv.rpm),                 "Engine Speed",  sv.rpm,           "RPM"),
            _c(2, _enc_adapt(sv.fuel_trim_st_b2),   "STFT B2",       sv.fuel_trim_st_b2, "%"),
            _c(3, _enc_adapt(sv.fuel_trim_lt_b2),   "LTFT B2",       sv.fuel_trim_lt_b2, "%"),
        ]
    if group == 60:
        tps2 = 100.0 - sv.tps1
        return [
            _c(1, _enc_pct(sv.tps1),  "Throttle Sensor 1", sv.tps1, "%"),
            _c(2, _enc_pct(tps2),     "Throttle Sensor 2", tps2,    "%"),
            _c(3, _enc_binary(8),     "Learn Step",        8,       ""),
            _c(4, _enc_binary(1),     "Throttle Adapt",    1,       ""),
        ]
    if group == 91:
        return [
            _c(1, _enc_rpm(sv.rpm),         "Engine Speed",  sv.rpm,       "RPM"),
            _c(2, _enc_pct(sv.load),        "Engine Load",   sv.load,      "%"),
            _c(3, _enc_pct(sv.n75_dc),      "N75 DC",        sv.n75_dc,    "%"),
            _c(4, _enc_mbar(sv.boost_mbar), "Boost Actual",  sv.boost_mbar,"mbar"),
        ]
    if group == 94:
        kr_total = (sv.knock_cyl1 + sv.knock_cyl2 +
                    sv.knock_cyl3 + sv.knock_cyl4) / 4.0
        return [
            _c(1, _enc_rpm(sv.rpm),        "Engine Speed",    sv.rpm,    "RPM"),
            _c(2, _enc_pct(sv.load),       "Engine Load",     sv.load,   "%"),
            _c(3, _enc_timing(sv.timing),  "Ignition Actual", sv.timing, "°BTDC"),
            _c(4, _enc_timing(-kr_total),  "KR Total",       -kr_total,  "°"),
        ]
    return []


def get_group_0(t: float = None, warmup_start: float = None) -> list:
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
