"""Tests for KWPBridge client detection — no hardware required."""

import socket
import threading
import time
import json
import pytest
from kwpbridge.client import is_running, get_state, KWPClient
from kwpbridge.constants import DEFAULT_PORT


def _start_mock_server(port: int, responses: list[dict] = None) -> threading.Thread:
    """Start a minimal mock TCP server for testing."""
    responses = responses or [
        {"type": "connected", "version": "0.1.0", "port": port},
        {"type": "state", "data": {
            "connected": True,
            "ecu_address": 0x01,
            "ecu_id": {"part_number": "893906266D", "component": "TEST"},
            "groups": {
                "1": {
                    "group": 1,
                    "timestamp": time.time(),
                    "cells": [
                        {"index": 1, "formula": 8, "value": 2400.0,
                         "unit": "RPM", "display": "2400 RPM", "label": "Engine Speed"},
                    ],
                },
            },
            "faults": [],
            "fault_count": 0,
            "error": "",
            "timestamp": time.time(),
        }},
    ]

    def _serve():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(1)
        srv.settimeout(3.0)
        try:
            conn, _ = srv.accept()
            for msg in responses:
                conn.sendall((json.dumps(msg) + "\n").encode())
                time.sleep(0.05)
            time.sleep(0.5)
            conn.close()
        except Exception:
            pass
        finally:
            srv.close()

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    time.sleep(0.1)  # let server start
    return t


TEST_PORT = 50267   # use different port to avoid conflict with real KWPBridge


def test_is_running_when_nothing_listening():
    # Nothing on TEST_PORT → should return False quickly
    assert not is_running(TEST_PORT, timeout=0.2)


def test_is_running_when_server_up():
    t = _start_mock_server(TEST_PORT)
    time.sleep(0.1)
    result = is_running(TEST_PORT, timeout=0.5)
    assert result is True
    t.join(timeout=2)


def test_get_state_no_server():
    result = get_state(TEST_PORT, timeout=0.3)
    assert result is None


def test_get_state_with_server():
    t = _start_mock_server(TEST_PORT)
    state = get_state(TEST_PORT, timeout=2.0)
    assert state is not None
    assert state["connected"] is True
    assert state["ecu_id"]["part_number"] == "893906266D"
    t.join(timeout=2)


def test_client_get_value():
    t = _start_mock_server(TEST_PORT)

    received = []
    client = KWPClient(port=TEST_PORT)
    client.on_state(lambda s: received.append(s))
    client.connect(auto_reconnect=False)

    time.sleep(1.0)
    client.disconnect()
    t.join(timeout=2)

    assert len(received) > 0
    rpm = None
    for state in received:
        groups = state.get("groups", {})
        g1 = groups.get("1") or groups.get(1)
        if g1:
            for cell in g1.get("cells", []):
                if cell.get("index") == 1:
                    rpm = cell.get("value")
    assert rpm == 2400.0
