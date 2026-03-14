"""Tests for KWP1281 measuring block value decode formulas."""

import pytest
from kwpbridge.formula import decode_cell, FORMULA


def test_rpm_decode():
    # Formula 0x08 = RPM, value = (A*256+B) * 0.25
    # 2400 RPM: raw = 2400/0.25 = 9600 = 0x2580 → A=0x25, B=0x80
    value, unit, display = decode_cell(0x08, 0x25, 0x80)
    assert unit == "RPM"
    assert abs(value - 2400.0) < 1.0


def test_temperature_decode():
    # Formula 0x12 = temp, value = (A*256+B)*0.1 - 273.15
    # 90°C: raw = (90 + 273.15)/0.1 = 3631.5 ≈ 3632 = 0x0E30 → A=0x0E, B=0x30
    value, unit, display = decode_cell(0x12, 0x0E, 0x30)
    assert unit == "°C"
    assert abs(value - 90.05) < 0.5


def test_voltage_decode():
    # Formula 0x07 = voltage, value = (A*256+B) * 0.001
    # 13.8V: raw = 13800 = 0x35E8 → A=0x35, B=0xE8
    value, unit, display = decode_cell(0x07, 0x35, 0xE8)
    assert unit == "V"
    assert abs(value - 13.8) < 0.01


def test_lambda_decode():
    # Formula 0x05 = lambda, value = (A*256+B)*0.0001 + 0.5
    # λ=1.0: raw = (1.0-0.5)/0.0001 = 5000 = 0x1388 → A=0x13, B=0x88
    value, unit, display = decode_cell(0x05, 0x13, 0x88)
    assert unit == "λ"
    assert abs(value - 1.0) < 0.001


def test_unknown_formula_fallback():
    # Unknown formula should return raw value without error
    value, unit, display = decode_cell(0xAB, 0x12, 0x34)
    assert value == 0x1234
    assert "formula=0xAB" in display


def test_all_formulas_callable():
    # Every formula in the table should decode without raising
    for formula_byte, entry in FORMULA.items():
        try:
            value, unit, display = decode_cell(formula_byte, 0x10, 0x20)
            assert isinstance(value, float)
        except Exception as e:
            pytest.fail(f"Formula 0x{formula_byte:02X} ({entry.name}) raised: {e}")


def test_percentage_decode():
    # Formula 0x04 = percentage, value = (A*256+B) * 0.01
    # 45.2%: raw = 4520 = 0x11A8 → A=0x11, B=0xA8
    value, unit, display = decode_cell(0x04, 0x11, 0xA8)
    assert unit == "%"
    assert abs(value - 45.2) < 0.1


def test_binary_status():
    # Formula 0x03 = binary/status, returns A as-is
    value, unit, display = decode_cell(0x03, 0b10110000, 0x00)
    assert value == 0b10110000
