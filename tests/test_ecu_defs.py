"""Tests for ECU definitions."""

import sys
sys.path.insert(0, '/home/claude/KWPBridge')
from kwpbridge.ecu_defs import (
    find_ecu_def, get_cell_label, get_fault_description,
    ECU_7A_LATE, ECU_7A_EARLY, ECU_AAH
)


def test_find_ecu_def():
    assert find_ecu_def("893906266D") is ECU_7A_LATE
    assert find_ecu_def("893906266B") is ECU_7A_EARLY
    assert find_ecu_def("4A0906266")  is ECU_AAH
    assert find_ecu_def("UNKNOWN")    is None


def test_cell_labels():
    assert get_cell_label(ECU_7A_LATE, 1, 1) == "Engine Speed"
    assert get_cell_label(ECU_7A_LATE, 2, 4) == "MAF Sensor (G70)"
    assert get_cell_label(ECU_7A_LATE, 8, 4) == "CO Pot Trim Value"
    # Unknown group falls back gracefully
    assert "999" in get_cell_label(ECU_7A_LATE, 999, 1)


def test_fault_descriptions():
    assert "co pot" in get_fault_description(ECU_7A_LATE, 521).lower()
    assert "MAF" in get_fault_description(ECU_7A_LATE, 514)
    # Unknown code
    assert "unknown" in get_fault_description(ECU_7A_LATE, 99999).lower()


def test_both_7a_ecus_same_groups():
    # 266D and 266B should have identical group definitions
    assert ECU_7A_LATE.groups == ECU_7A_EARLY.groups


if __name__ == "__main__":
    test_find_ecu_def()
    test_cell_labels()
    test_fault_descriptions()
    test_both_7a_ecus_same_groups()
    print("All ECU def tests passed")
