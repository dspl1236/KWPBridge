"""Tests for ECU definitions and label lookup."""

import pytest
from kwpbridge.ecu_defs import (
    ECU_7A_LATE, ECU_7A_EARLY, ECU_AAH,
    find_ecu_def, get_cell_label, get_fault_description,
    ALL_ECU_DEFS,
)


def test_find_7a_late():
    ecu = find_ecu_def("893906266D")
    assert ecu is not None
    assert ecu is ECU_7A_LATE


def test_find_7a_early():
    ecu = find_ecu_def("893906266B")
    assert ecu is not None
    assert ecu is ECU_7A_EARLY


def test_find_aah():
    ecu = find_ecu_def("4A0906266")
    assert ecu is not None
    assert ecu is ECU_AAH


def test_find_mms200():
    ecu = find_ecu_def("8A0906266A")
    assert ecu is not None
    assert ecu is ECU_AAH   # shares AAH definition


def test_find_unknown():
    ecu = find_ecu_def("999999999X")
    assert ecu is None


def test_cell_labels_7a():
    ecu = ECU_7A_LATE
    assert "Speed" in get_cell_label(ecu, 1, 1)   # Group 1, cell 1 = Engine Speed
    assert "Coolant" in get_cell_label(ecu, 1, 2) # Group 1, cell 2 = Coolant Temp
    assert "CO Pot" in get_cell_label(ecu, 8, 2)  # Group 8 = CO pot data


def test_cell_label_fallback():
    ecu = ECU_7A_LATE
    label = get_cell_label(ecu, 255, 4)
    assert "255" in label   # fallback includes group number


def test_cell_label_no_ecu():
    label = get_cell_label(None, 1, 1)
    assert "1" in label


def test_fault_description_7a():
    ecu = ECU_7A_LATE
    desc = get_fault_description(ecu, 521)
    assert "CO pot" in desc.lower() or "pin 4" in desc.lower()


def test_fault_description_maf():
    ecu = ECU_7A_LATE
    desc = get_fault_description(ecu, 514)
    assert "MAF" in desc or "G70" in desc


def test_fault_description_unknown():
    ecu = ECU_7A_LATE
    desc = get_fault_description(ecu, 99999)
    assert "99999" in desc


def test_7a_early_same_groups():
    # 266B and 266D should have same measuring block layout
    assert ECU_7A_EARLY.groups == ECU_7A_LATE.groups


def test_all_ecus_have_engine_address():
    for ecu in ALL_ECU_DEFS:
        assert ecu.address == 0x01, f"{ecu.name} should use engine address 0x01"


def test_co_pot_basic_setting():
    # Group 8 basic setting should be documented for 7A ECUs
    ecu = ECU_7A_LATE
    assert 8 in ecu.basic_settings
    assert "CO" in ecu.basic_settings[8].upper() or "128" in ecu.basic_settings[8]
