"""Tests for KWPBridge data models."""

import sys, time
sys.path.insert(0, '/home/claude/KWPBridge')
from kwpbridge.models import MeasuringCell, MeasuringBlock, FaultCode, ECUIdentification, BridgeState


def test_measuring_block_as_dict():
    cell = MeasuringCell(
        index=1, formula=0x08, raw_a=13, raw_b=72,
        value=850.0, unit="RPM", display="850 RPM", label="Engine Speed")
    block = MeasuringBlock(group=1, cells=[cell], timestamp=1234567.0)
    d = block.as_dict()
    assert d['group'] == 1
    assert d['cells'][0]['value'] == 850.0
    assert d['cells'][0]['label'] == "Engine Speed"


def test_fault_code_formatting():
    f = FaultCode(code=521, status=0x06, description="CO pot signal")
    assert f.code_str == "00521"
    assert "stored" in f.status_str


def test_bridge_state_serialisation():
    state = BridgeState(
        connected=True,
        ecu_id=ECUIdentification(part_number="893906266D", component="2.3 20V"),
    )
    d = state.as_dict()
    assert d['connected'] is True
    assert d['ecu_id']['part_number'] == "893906266D"


if __name__ == "__main__":
    test_measuring_block_as_dict()
    test_fault_code_formatting()
    test_bridge_state_serialisation()
    print("All model tests passed")
