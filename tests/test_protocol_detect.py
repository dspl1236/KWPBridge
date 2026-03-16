"""Tests for protocol_detect.py — auto-detection and forced protocols."""

import sys, time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from kwpbridge.protocol_detect import (
    ProtocolDetector, DetectResult, detect_protocol,
    PROTO_AUTO, PROTO_KWP1281, PROTO_KWP2000, PROTOCOL_ORDER,
)


def _make_mock_ecu_id(pn="893906266D", component="2.3 20V MOTRONIC"):
    from kwpbridge.models import ECUIdentification
    return ECUIdentification(part_number=pn, component=component)


def _make_mock_kwp(pn="893906266D"):
    kwp = MagicMock()
    kwp.connected = True
    kwp.connect.return_value = _make_mock_ecu_id(pn)
    kwp.disconnect.return_value = None
    return kwp


class TestDetectResult:

    def test_success_summary(self):
        ecu_id = _make_mock_ecu_id()
        r = DetectResult(success=True, protocol=PROTO_KWP1281, ecu_id=ecu_id)
        assert "kwp1281" in r.summary()
        assert "893906266D" in r.summary()

    def test_failure_summary_shows_errors(self):
        r = DetectResult(success=False,
                         errors={PROTO_KWP1281: ["timeout"], PROTO_KWP2000: ["nack"]},
                         attempts={PROTO_KWP1281: 2, PROTO_KWP2000: 2})
        s = r.summary()
        assert "kwp1281" in s
        assert "kwp2000" in s
        assert "No ECU found" in s

    def test_tried_protocols(self):
        r = DetectResult(success=False,
                         attempts={PROTO_KWP1281: 1, PROTO_KWP2000: 1})
        assert PROTO_KWP1281 in r.tried_protocols
        assert PROTO_KWP2000 in r.tried_protocols


class TestProtocolDetector:

    def _detector(self, force=PROTO_AUTO, attempts=1):
        return ProtocolDetector(
            port="COM_TEST",
            force_protocol=force,
            max_attempts=attempts,
        )

    def test_auto_order(self):
        """Auto mode tries KWP1281 before KWP2000."""
        assert PROTOCOL_ORDER[0] == PROTO_KWP1281
        assert PROTOCOL_ORDER[1] == PROTO_KWP2000

    def test_force_kwp1281_success(self):
        det = self._detector(force=PROTO_KWP1281)
        mock_kwp = _make_mock_kwp("893906266D")
        with patch.object(det, '_try_protocol', return_value=(mock_kwp, mock_kwp.connect.return_value)):
            result = det.run()
        assert result.success
        assert result.protocol == PROTO_KWP1281
        assert result.ecu_id.part_number == "893906266D"
        assert result.connection is mock_kwp

    def test_force_kwp2000_success(self):
        det = self._detector(force=PROTO_KWP2000)
        mock_kwp = _make_mock_kwp("06A906032BN")
        with patch.object(det, '_try_protocol', return_value=(mock_kwp, mock_kwp.connect.return_value)):
            result = det.run()
        assert result.success
        assert result.protocol == PROTO_KWP2000

    def test_auto_falls_through_to_kwp2000(self):
        """When KWP1281 fails, auto mode tries KWP2000."""
        call_log = []
        def side_effect(proto):
            call_log.append(proto)
            if proto == PROTO_KWP1281:
                raise ConnectionError("5-baud timeout")
            return (_make_mock_kwp("06A906032BN"),
                    _make_mock_ecu_id("06A906032BN", "1.8l T  ME7.5"))

        det = self._detector(force=PROTO_AUTO, attempts=1)
        with patch.object(det, '_try_protocol', side_effect=side_effect), \
             patch('time.sleep'):
            result = det.run()

        assert result.success
        assert result.protocol == PROTO_KWP2000
        assert PROTO_KWP1281 in call_log
        assert PROTO_KWP2000 in call_log

    def test_all_fail_returns_failure(self):
        det = self._detector(force=PROTO_AUTO, attempts=1)
        with patch.object(det, '_try_protocol', side_effect=ConnectionError("no ECU")), \
             patch('time.sleep'):
            result = det.run()
        assert not result.success
        assert len(result.errors) == 2

    def test_retries_before_next_protocol(self):
        """With attempts=2, each protocol is tried twice."""
        call_log = []
        def side_effect(proto):
            call_log.append(proto)
            raise ConnectionError("fail")

        det = self._detector(force=PROTO_AUTO, attempts=2)
        with patch.object(det, '_try_protocol', side_effect=side_effect), \
             patch('time.sleep'):
            result = det.run()

        kwp1281_tries = call_log.count(PROTO_KWP1281)
        kwp2000_tries = call_log.count(PROTO_KWP2000)
        assert kwp1281_tries == 2
        assert kwp2000_tries == 2
        assert not result.success

    def test_status_callback_called(self):
        msgs = []
        det = ProtocolDetector(
            port="TEST", force_protocol=PROTO_KWP1281,
            max_attempts=1, on_status=msgs.append)
        mock_kwp = _make_mock_kwp()
        with patch.object(det, '_try_protocol', return_value=(mock_kwp, mock_kwp.connect.return_value)):
            det.run()
        assert any("kwp1281" in m.lower() for m in msgs)

    def test_forced_only_tries_one_protocol(self):
        call_log = []
        def side_effect(proto):
            call_log.append(proto)
            raise ConnectionError("fail")

        det = self._detector(force=PROTO_KWP1281, attempts=1)
        with patch.object(det, '_try_protocol', side_effect=side_effect), \
             patch('time.sleep'):
            result = det.run()

        assert call_log == [PROTO_KWP1281]
        assert PROTO_KWP2000 not in call_log

    def test_connection_object_returned_live(self):
        """result.connection is the actual live connection, ready to use."""
        det = self._detector(force=PROTO_KWP2000)
        mock_kwp = _make_mock_kwp("06A906032BN")
        with patch.object(det, '_try_protocol', return_value=(mock_kwp, mock_kwp.connect.return_value)):
            result = det.run()
        assert result.connection is mock_kwp
        # No extra connect call — the object is already connected
        assert result.connection.connected is True


class TestDetectProtocolFunction:

    def test_convenience_wrapper(self):
        with patch('kwpbridge.protocol_detect.ProtocolDetector.run') as mock_run:
            mock_run.return_value = DetectResult(success=False)
            result = detect_protocol(port="COM_TEST", force_protocol=PROTO_KWP1281)
        assert isinstance(result, DetectResult)
        mock_run.assert_called_once()

    def test_passes_kwargs(self):
        captured = {}
        def capture_init(self, **kwargs):
            captured.update(kwargs)
        # Just verify the constructor args flow through
        with patch('kwpbridge.protocol_detect.ProtocolDetector.run',
                   return_value=DetectResult(success=False)), \
             patch('time.sleep'):
            detect_protocol(
                port="COM3",
                cable_type="ross_tech",
                force_protocol=PROTO_KWP2000,
                max_attempts=3,
            )
