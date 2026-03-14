"""Tests for KWP1281 measuring block formula decoding."""

import sys
sys.path.insert(0, '/home/claude/KWPBridge')
from kwpbridge.formula import decode_cell, FORMULA


def test_rpm_formula():
    # Formula 0x08: RPM = (A*256+B) * 0.25
    # 850 RPM = 3400 raw = A=13, B=72
    raw = 3400
    a, b = raw >> 8, raw & 0xFF
    value, unit, display = decode_cell(0x08, a, b)
    assert abs(value - 850.0) < 0.1
    assert unit == "RPM"


def test_temperature_formula():
    # Formula 0x12: temp = (A*256+B)*0.1 - 273.15
    # 87°C = 3601.5 raw -> A=14, B=25... approx
    # Test: raw=3601 -> 3601*0.1 - 273.15 = 86.95
    raw = 3601
    a, b = raw >> 8, raw & 0xFF
    value, unit, display = decode_cell(0x12, a, b)
    assert abs(value - 86.95) < 0.1
    assert unit == "°C"


def test_voltage_formula():
    # Formula 0x07: voltage = (A*256+B) * 0.001
    # 13.8V = 13800 raw = A=53, B=232
    raw = 13800
    a, b = raw >> 8, raw & 0xFF
    value, unit, display = decode_cell(0x07, a, b)
    assert abs(value - 13.8) < 0.01
    assert unit == "V"


def test_unknown_formula_fallback():
    # Unknown formula should return raw value without crashing
    value, unit, display = decode_cell(0xAB, 0x12, 0x34)
    assert value == 0x1234
    assert "formula=0xAB" in display


def test_all_formulas_dont_crash():
    # All defined formulas should decode without exception
    for formula_id, entry in FORMULA.items():
        value, unit, display = decode_cell(formula_id, 100, 50)
        assert isinstance(value, float)
        assert isinstance(unit, str)
        assert isinstance(display, str)


if __name__ == "__main__":
    test_rpm_formula()
    test_temperature_formula()
    test_voltage_formula()
    test_unknown_formula_fallback()
    test_all_formulas_dont_crash()
    print("All formula tests passed")
