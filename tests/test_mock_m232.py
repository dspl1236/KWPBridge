"""Tests for the M2.3.2 mock ECU."""

import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kwpbridge.mock.ecu_m232 import (
    get_group, get_scenario_info, SCENARIOS, SCENARIO_DURATION,
    ECU_PART_NUMBER, ECU_COMPONENT, _COLD, _IDLE, _BOOST,
)


class TestM232Mock:

    def test_part_number(self):
        assert ECU_PART_NUMBER == "4A0907551AA"

    def test_scenario_duration_positive(self):
        assert SCENARIO_DURATION > 0

    def test_all_groups_return_4_cells(self):
        t = 100.0
        for grp in range(1, 9):
            cells = get_group(grp, t)
            assert len(cells) == 4, f"Group {grp} returned {len(cells)} cells"

    def test_cell_structure(self):
        cells = get_group(1, 100.0)
        for c in cells:
            assert "index" in c
            assert "value" in c
            assert "label" in c
            assert "unit" in c

    def test_group1_rpm_range(self):
        """RPM stays in plausible range across the scenario loop."""
        for offset in range(0, int(SCENARIO_DURATION), 10):
            cells = get_group(1, offset)
            rpm = cells[0]["value"]
            assert 400 <= rpm <= 7000, f"RPM {rpm} out of range at t={offset}"

    def test_group1_lambda_range(self):
        """Lambda stays in plausible range."""
        for offset in range(0, int(SCENARIO_DURATION), 10):
            cells = get_group(1, offset)
            lam = cells[2]["value"]
            assert 0.5 <= lam <= 1.8, f"Lambda {lam} out of range at t={offset}"

    def test_group3_load_raw(self):
        """Group 3 cell 2 (load) should be raw 1-255, not /25 decoded."""
        for offset in [70, 150, 195]:  # idle, cruise, boost
            cells = get_group(3, offset)
            load = cells[1]["value"]
            assert load >= 1, f"Load {load} too low at t={offset}"
            assert load <= 255, f"Load {load} > 255 at t={offset}"

    def test_group6_map_kpa(self):
        """MAP kPa in group 6 should be plausible absolute pressure."""
        for offset in [70, 150, 195]:
            cells = get_group(6, offset)
            map_kpa = cells[2]["value"]
            assert 60 <= map_kpa <= 320, f"MAP {map_kpa} out of range"

    def test_group8_ipw(self):
        """IPW should be positive ms."""
        for offset in range(0, int(SCENARIO_DURATION), 15):
            cells = get_group(8, offset)
            ipw = cells[0]["value"]
            assert 0.5 <= ipw <= 20.0, f"IPW {ipw} ms out of range"

    def test_unknown_group_returns_empty(self):
        assert get_group(99, 0.0) == []

    def test_get_scenario_info(self):
        info = get_scenario_info(100.0)
        assert "scenario" in info
        assert 0.0 <= info["progress"] <= 1.0

    def test_scenario_names_cycle(self):
        """Each scenario name appears at the right time slot."""
        offset = 0.0
        seen = []
        for sc in SCENARIOS:
            mid = offset + sc.duration / 2
            info = get_scenario_info(mid)
            seen.append(info["scenario"])
            offset += sc.duration
        assert len(seen) == len(SCENARIOS)
        assert seen[0] == "Cold Start"
        assert "Boost Run" in seen

    def test_server_instantiation(self):
        from kwpbridge.mock.server import MockServer
        srv = MockServer(ecu="m232")
        assert srv._part_number == "4A0907551AA"

    def test_server_alias_aan(self):
        from kwpbridge.mock.server import MockServer
        srv = MockServer(ecu="aan")
        assert srv._part_number == "4A0907551AA"

    def test_get_group0_compat(self):
        """Mock server calls get_group_0 — verify it works."""
        from kwpbridge.mock.ecu_m232 import get_group_0
        cells = get_group_0(100.0)
        assert len(cells) == 4
        assert cells[0]["unit"] == "RPM"
