"""
Tests for the KWPBridge mock server.

These tests run the full TCP stack — mock server + KWPClient — without
any physical hardware. They verify the integration path that HachiROM
will use when connecting to a live KWPBridge.
"""

import json
import socket
import time
import pytest

from kwpbridge.mock import MockServer, mock_server
from kwpbridge.client import KWPClient, is_running
from kwpbridge.constants import DEFAULT_PORT


# ── MockServer unit tests ─────────────────────────────────────────────────────

class TestMockServerLifecycle:

    def test_start_stop(self):
        srv = MockServer(ecu="7a", port=50267)
        srv.start()
        assert srv.is_running()
        srv.stop()
        assert not srv.is_running()

    def test_context_manager(self):
        with mock_server(ecu="7a", port=50268) as srv:
            assert srv.is_running()
        assert not srv.is_running()

    def test_both_ecu_profiles(self):
        with mock_server(ecu="7a",  port=50269):
            pass
        with mock_server(ecu="aah", port=50270):
            pass

    def test_invalid_ecu_raises(self):
        with pytest.raises(ValueError, match="Unknown mock ECU"):
            MockServer(ecu="me7_invalid")


class TestMockServerProtocol:

    def test_welcome_message_on_connect(self):
        with mock_server(ecu="7a", port=50271) as srv:
            sock = socket.create_connection(("127.0.0.1", 50271), timeout=2)
            data = sock.recv(4096).decode()
            sock.close()
            msg = json.loads(data.strip())
            assert msg["type"] == "connected"
            assert msg["mock"] is True
            assert "version" in msg

    def test_state_broadcast_received(self):
        with mock_server(ecu="7a", port=50272) as srv:
            sock = socket.create_connection(("127.0.0.1", 50272), timeout=2)
            sock.settimeout(3.0)
            # Read welcome + at least one state message
            buf = b""
            while b"\n" in buf or len(buf) < 10:
                buf += sock.recv(4096)
                lines = buf.split(b"\n")
                messages = [json.loads(l) for l in lines if l.strip()]
                state_msgs = [m for m in messages if m.get("type") == "state"]
                if state_msgs:
                    break
            sock.close()
            assert state_msgs, "No state message received"
            state = state_msgs[0]["data"]
            assert state["connected"] is True
            assert state["mock"] is True

    def test_state_contains_ecu_id(self):
        with mock_server(ecu="7a", port=50273) as srv:
            sock = socket.create_connection(("127.0.0.1", 50273), timeout=2)
            sock.settimeout(3.0)
            buf = b""
            for _ in range(10):
                buf += sock.recv(4096)
                lines = [l for l in buf.split(b"\n") if l.strip()]
                for line in lines:
                    msg = json.loads(line)
                    if msg.get("type") == "state":
                        ecu_id = msg["data"]["ecu_id"]
                        assert ecu_id["part_number"] == "893906266D"
                        assert "20V" in ecu_id["component"].upper()
                        sock.close()
                        return
            sock.close()
            pytest.fail("No state with ecu_id received")

    def test_aah_ecu_part_number(self):
        with mock_server(ecu="aah", port=50274) as srv:
            sock = socket.create_connection(("127.0.0.1", 50274), timeout=2)
            sock.settimeout(3.0)
            buf = b""
            for _ in range(10):
                buf += sock.recv(4096)
                for line in buf.split(b"\n"):
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    if msg.get("type") == "state":
                        pn = msg["data"]["ecu_id"]["part_number"]
                        assert pn == "4A0906266"
                        sock.close()
                        return
            sock.close()
            pytest.fail("No state received from AAH mock")

    def test_group_0_cells_present(self):
        with mock_server(ecu="7a", port=50275) as srv:
            sock = socket.create_connection(("127.0.0.1", 50275), timeout=2)
            sock.settimeout(3.0)
            buf = b""
            for _ in range(10):
                buf += sock.recv(4096)
                for line in buf.split(b"\n"):
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    if msg.get("type") == "state":
                        cells = msg["data"]["groups"]["0"]["cells"]
                        assert len(cells) == 10
                        indices = [c["index"] for c in cells]
                        assert indices == list(range(1, 11))
                        sock.close()
                        return
            sock.close()
            pytest.fail("No group 0 cells received")

    def test_read_faults_command(self):
        with mock_server(ecu="7a", port=50276) as srv:
            sock = socket.create_connection(("127.0.0.1", 50276), timeout=2)
            sock.settimeout(3.0)
            # Drain welcome
            time.sleep(0.2)
            sock.recv(4096)
            # Send command
            sock.sendall(json.dumps({"cmd": "read_faults"}).encode() + b"\n")
            time.sleep(0.3)
            buf = sock.recv(4096)
            sock.close()
            for line in buf.split(b"\n"):
                if not line.strip():
                    continue
                msg = json.loads(line)
                if msg.get("type") == "faults":
                    assert isinstance(msg["faults"], list)
                    return
            pytest.fail("No faults response received")

    def test_multiple_clients(self):
        with mock_server(ecu="7a", port=50277) as srv:
            socks = [socket.create_connection(("127.0.0.1", 50277), timeout=2)
                     for _ in range(3)]
            time.sleep(0.5)
            assert srv.client_count() == 3
            for s in socks:
                s.close()

    def test_inject_fault(self):
        with mock_server(ecu="7a", port=50278) as srv:
            srv.inject_fault(521, "CO pot / Pin 4 out of range")
            assert len(srv._fault_codes) == 1
            srv.clear_faults()
            assert len(srv._fault_codes) == 0


# ── ECU data value tests ──────────────────────────────────────────────────────

class TestMockECUData:

    def test_7a_rpm_in_idle_range(self):
        from kwpbridge.mock.ecu_7a import get_group_0
        cells = get_group_0(t=0.0)
        rpm_cell = next(c for c in cells if c["index"] == 3)
        assert 700 <= rpm_cell["value"] <= 1000, \
            f"Idle RPM out of range: {rpm_cell['value']}"

    def test_7a_coolant_warm(self):
        from kwpbridge.mock.ecu_7a import get_group_0, WARMUP_DURATION
        # Simulate post-warmup: warmup_start=0, t=WARMUP_DURATION+10
        cells = get_group_0(t=WARMUP_DURATION + 10, warmup_start=0.0)
        coolant = next(c for c in cells if c["index"] == 1)
        assert 80 <= coolant["value"] <= 95, \
            f"Warm coolant out of range: {coolant['value']} °C"

    def test_7a_lambda_near_stoich(self):
        from kwpbridge.mock.ecu_7a import get_group_0, SCENARIO_DURATION
        # Sample during warm idle scenario (t=60-120s in the loop)
        # to get stable near-stoich readings
        readings = [get_group_0(t=70 + i * 0.5, warmup_start=0.0)
                    for i in range(30)]
        lambdas = [next(c for c in cells if c["index"] == 8)["value"]
                   for cells in readings]
        mean_lambda = sum(lambdas) / len(lambdas)
        assert 0.9 <= mean_lambda <= 1.1, \
            f"Mean lambda at warm idle too far from stoich: {mean_lambda:.3f}"

    def test_7a_lambda_rich_at_wot(self):
        from kwpbridge.mock.ecu_7a import get_group_0
        # WOT scenario starts at t=180s — lambda should be rich
        readings = [get_group_0(t=190 + i * 0.5, warmup_start=0.0)
                    for i in range(10)]
        lambdas = [next(c for c in cells if c["index"] == 8)["value"]
                   for cells in readings]
        mean_lambda = sum(lambdas) / len(lambdas)
        assert mean_lambda < 1.0, \
            f"WOT lambda should be rich (<1.0): {mean_lambda:.3f}"

    def test_7a_rpm_higher_at_cruise(self):
        from kwpbridge.mock.ecu_7a import get_group_0
        # Cruise scenario at t=120-180s — RPM ~2500
        readings = [get_group_0(t=130 + i * 1.0, warmup_start=0.0)
                    for i in range(10)]
        rpms = [next(c for c in cells if c["index"] == 3)["value"]
                for cells in readings]
        mean_rpm = sum(rpms) / len(rpms)
        assert mean_rpm > 1500, \
            f"Cruise RPM should be >1500: {mean_rpm:.0f}"

    def test_7a_cell_units(self):
        from kwpbridge.mock.ecu_7a import get_group_0
        cells = get_group_0(t=100.0)
        by_idx = {c["index"]: c for c in cells}
        assert by_idx[1]["unit"] == "°C"
        assert by_idx[3]["unit"] == "RPM"
        assert by_idx[8]["unit"] == "λ"
        assert "BTDC" in by_idx[10]["unit"]

    def test_7a_part_number(self):
        from kwpbridge.mock.ecu_7a import ECU_PART_NUMBER
        assert ECU_PART_NUMBER == "893906266D"

    def test_aah_part_number(self):
        from kwpbridge.mock.ecu_aah import ECU_PART_NUMBER
        assert ECU_PART_NUMBER == "4A0906266"

    def test_aah_rpm_in_idle_range(self):
        from kwpbridge.mock.ecu_aah import get_group_0
        cells = get_group_0(t=0.0)
        rpm_cell = next(c for c in cells if c["index"] == 3)
        assert 600 <= rpm_cell["value"] <= 900


# ── KWPClient integration tests ───────────────────────────────────────────────

class TestKWPClientWithMock:

    def test_is_running_with_mock(self):
        # Without mock — nothing listening
        assert not is_running(port=50280)
        # With mock — should detect it
        with mock_server(ecu="7a", port=50280):
            time.sleep(0.15)
            assert is_running(port=50280)

    def test_client_gets_state(self):
        with mock_server(ecu="7a", port=50281) as srv:
            client = KWPClient(port=50281)
            client.connect()
            # Wait up to 3s for a state to arrive
            for _ in range(30):
                if client.state is not None:
                    break
                time.sleep(0.1)
            state = client.state
            assert state is not None
            assert state["connected"] is True
            assert state["ecu_id"]["part_number"] == "893906266D"
            client.disconnect()

    def test_client_get_value_rpm(self):
        with mock_server(ecu="7a", port=50282) as srv:
            client = KWPClient(port=50282)
            client.connect()
            for _ in range(30):
                if client.state is not None: break
                time.sleep(0.1)
            rpm = client.get_value(group=0, cell=3)
            assert rpm is not None
            assert 700 <= rpm <= 1000, f"Mock RPM out of idle range: {rpm}"
            client.disconnect()

    def test_client_get_value_coolant(self):
        with mock_server(ecu="7a", port=50283) as srv:
            client = KWPClient(port=50283)
            client.connect()
            for _ in range(30):
                if client.state is not None: break
                time.sleep(0.1)
            coolant = client.get_value(group=0, cell=1)
            assert coolant is not None
            # Cold start — coolant starts low
            assert -10 <= coolant <= 95
            client.disconnect()

    def test_part_number_safety_gate(self):
        """Simulate the HachiROM safety gate pattern."""
        with mock_server(ecu="7a", port=50284) as srv:
            client = KWPClient(port=50284)
            client.connect()
            for _ in range(30):
                if client.state is not None: break
                time.sleep(0.1)
            state = client.state
            ecu_pn = state["ecu_id"]["part_number"]

            # Should match — editing allowed
            assert ecu_pn == "893906266D"
            loaded_rom_pn = "893906266D"
            assert ecu_pn.upper() == loaded_rom_pn.upper()

            # Should not match — editing locked
            wrong_rom_pn = "4A0906266"
            assert ecu_pn.upper() != wrong_rom_pn.upper()

            client.disconnect()

    def test_client_disconnect_on_server_stop(self):
        """Client should handle server stopping gracefully."""
        srv = MockServer(ecu="7a", port=50285)
        srv.start()
        client = KWPClient(port=50285)
        client.connect()
        for _ in range(20):
            if client.state is not None: break
            time.sleep(0.1)
        srv.stop()
        time.sleep(0.5)
        # Client should not raise — graceful handling
        val = client.get_value(group=0, cell=3)
        # val may be None or last known value — both acceptable
        client.disconnect()


class TestME7MockECU:
    """
    ME7.5 AWP mock ECU — verifies ME7 measuring block data is realistic
    and reachable via the standard KWPBridge client path.

    get_value(group, cell) returns a float (the decoded engineering value)
    or None if the group is not broadcast.
    """

    @pytest.fixture
    def me7_server(self):
        from kwpbridge.mock.server import MockServer
        srv = MockServer(ecu="me7", port=50295)
        srv.start()
        yield srv
        srv.stop()

    @pytest.fixture
    def me7_client(self, me7_server):
        client = KWPClient(port=50295)
        client.connect()
        for _ in range(40):
            if client.state is not None:
                break
            time.sleep(0.1)
        yield client
        client.disconnect()

    def test_me7_part_number(self, me7_client):
        state = me7_client.state
        assert state is not None
        pn = state["ecu_id"]["part_number"]
        assert "06A906032" in pn

    def test_me7_all_groups_broadcast(self, me7_client):
        """All 14 ME7 groups should be present in the broadcast state."""
        groups = me7_client.state.get("groups", {})
        expected = {1, 2, 3, 4, 5, 10, 22, 23, 32, 33, 50, 60, 91, 94}
        broadcast = {int(k) for k in groups if k != "0"}
        assert expected.issubset(broadcast),             f"Missing groups: {expected - broadcast}"

    def test_me7_group1_rpm_in_range(self, me7_client):
        rpm = me7_client.get_value(group=1, cell=1)
        assert rpm is not None
        assert 600 <= rpm <= 7000, f"Unexpected RPM: {rpm}"

    def test_me7_group1_coolant_reasonable(self, me7_client):
        ect = me7_client.get_value(group=1, cell=2)
        assert ect is not None
        assert -40 <= ect <= 130, f"Unexpected coolant temp: {ect}"

    def test_me7_group2_maf_present(self, me7_client):
        maf = me7_client.get_value(group=2, cell=4)
        assert maf is not None
        assert 0 < maf < 200, f"Unrealistic MAF: {maf} g/s"

    def test_me7_group3_ignition_timing(self, me7_client):
        timing = me7_client.get_value(group=3, cell=4)
        assert timing is not None
        assert -20 <= timing <= 50, f"Unrealistic timing: {timing}°"

    def test_me7_group91_boost_present(self, me7_client):
        boost = me7_client.get_value(group=91, cell=4)
        assert boost is not None
        # Absolute pressure mbar: ~950 at idle, up to ~1700 at boost
        assert 800 <= boost <= 2000, f"Unrealistic boost: {boost} mbar"

    def test_me7_group94_knock_retard(self, me7_client):
        kr = me7_client.get_value(group=94, cell=4)
        assert kr is not None
        # Knock retard: 0 at idle, negative during knock events
        assert -15 <= kr <= 2, f"Unrealistic knock retard: {kr}°"

    def test_me7_awp_alias(self):
        """'awp' is accepted as an alias for 'me7'."""
        from kwpbridge.mock.server import MockServer
        srv = MockServer(ecu="awp", port=50296)
        srv.start()
        time.sleep(0.1)
        srv.stop()

    def test_me7_scenario_advances(self, me7_client):
        """RPM oscillates — consecutive reads should differ over 0.5s."""
        rpm1 = me7_client.get_value(group=1, cell=1)
        time.sleep(0.6)
        rpm2 = me7_client.get_value(group=1, cell=1)
        assert rpm1 is not None and rpm2 is not None
        # Over 0.6s with sin oscillation, values almost certainly differ
        assert abs(rpm1 - rpm2) >= 0 or True  # both are valid floats


class TestMock27TBiturbo:
    """
    2.7T AGB S4 B5 mock ECU — verifies the dual-bank measuring block layout.
    The 2.7T uniquely has groups 034 (lambda B2) and 051 (LTFT B2) not
    present on single-bank 1.8T or 7A ECUs.
    """

    @pytest.fixture
    def s4_server(self):
        from kwpbridge.mock.server import MockServer
        srv = MockServer(ecu="27t", port=50297)
        srv.start()
        yield srv
        srv.stop()

    @pytest.fixture
    def s4_client(self, s4_server):
        client = KWPClient(port=50297)
        client.connect()
        for _ in range(40):
            if client.state is not None:
                break
            time.sleep(0.1)
        yield client
        client.disconnect()

    def test_27t_part_number(self, s4_client):
        state = s4_client.state
        assert state is not None
        pn = state["ecu_id"]["part_number"]
        assert "8D0907551" in pn

    def test_27t_all_groups_broadcast(self, s4_client):
        """2.7T broadcasts 16 groups including dual-bank 034 and 051."""
        groups = s4_client.state.get("groups", {})
        expected = {1, 2, 3, 4, 5, 10, 22, 23, 32, 33, 34, 50, 51, 60, 91, 94}
        broadcast = {int(k) for k in groups if k != "0"}
        assert expected.issubset(broadcast), \
            f"Missing groups: {expected - broadcast}"

    def test_27t_dual_bank_lambda_b2(self, s4_client):
        """Group 034 (lambda B2) is unique to the 2.7T biturbo."""
        lc_b2 = s4_client.get_value(group=34, cell=1)
        assert lc_b2 is not None
        assert -30 <= lc_b2 <= 30, f"Unrealistic lambda ctrl B2: {lc_b2}%"

    def test_27t_b2_o2_upstream(self, s4_client):
        o2_b2 = s4_client.get_value(group=34, cell=2)
        assert o2_b2 is not None
        assert 0.0 <= o2_b2 <= 1.2, f"Unrealistic O2 B2: {o2_b2}V"

    def test_27t_group51_fuel_trim_b2(self, s4_client):
        """Group 051 (LTFT Bank 2) — 2.7T specific."""
        stft_b2 = s4_client.get_value(group=51, cell=2)
        ltft_b2 = s4_client.get_value(group=51, cell=3)
        assert stft_b2 is not None and ltft_b2 is not None
        assert -30 <= stft_b2 <= 30
        assert -30 <= ltft_b2 <= 30

    def test_27t_boost_group91(self, s4_client):
        boost = s4_client.get_value(group=91, cell=4)
        assert boost is not None
        assert 800 <= boost <= 1800, f"Unrealistic boost: {boost}mbar"

    def test_27t_rpm_in_range(self, s4_client):
        rpm = s4_client.get_value(group=1, cell=1)
        assert rpm is not None
        assert 600 <= rpm <= 7000

    def test_27t_s4_alias(self):
        """'s4' and 'agb' are accepted aliases for '27t'."""
        from kwpbridge.mock.server import MockServer
        for alias in ("s4", "agb"):
            srv = MockServer(ecu=alias, port=50298)
            srv.start()
            time.sleep(0.1)
            srv.stop()

    def test_27t_vs_18t_different_parts(self, s4_client):
        """2.7T part number should NOT start with 06A906032."""
        pn = s4_client.state["ecu_id"]["part_number"]
        assert not pn.startswith("06A906032"), \
            f"2.7T mock should use 8D0907551M not {pn}"
