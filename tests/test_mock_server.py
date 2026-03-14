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
        from kwpbridge.mock.ecu_7a import get_group_0
        # Sample several ticks — mean should be near stoich
        readings = [get_group_0(t=i * 0.1)for i in range(50)]
        lambdas = [next(c for c in cells if c["index"] == 8)["value"]
                   for cells in readings]
        mean_lambda = sum(lambdas) / len(lambdas)
        assert 0.9 <= mean_lambda <= 1.1, \
            f"Mean lambda too far from stoich: {mean_lambda:.3f}"

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
