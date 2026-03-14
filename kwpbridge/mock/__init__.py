"""
KWPBridge mock ECU server — for testing and development.

Simulates a live KWPBridge process without requiring a physical
K-line cable or vehicle ECU.

Quick start:
    from kwpbridge.mock import mock_server
    from kwpbridge.client import KWPClient, is_running

    with mock_server(ecu="7a") as srv:
        assert is_running()
        client = KWPClient()
        client.connect()
        rpm = client.get_value(group=0, cell=3)
        print(f"RPM: {rpm}")
"""

from .server import MockServer, mock_server

__all__ = ["MockServer", "mock_server"]
