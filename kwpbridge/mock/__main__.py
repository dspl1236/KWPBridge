"""
python -m kwpbridge.mock

Runs the mock server in the foreground so you can connect
HachiROM or any other tool to it during development.

Usage:
    python -m kwpbridge.mock
    python -m kwpbridge.mock --ecu aah
    python -m kwpbridge.mock --ecu 7a --port 50266 --hz 5 --verbose
"""

import argparse
import logging
import time

from .server import MockServer
from ..constants import DEFAULT_PORT


def main():
    parser = argparse.ArgumentParser(
        prog="python -m kwpbridge.mock",
        description="KWPBridge mock ECU server for development and testing")
    parser.add_argument("--ecu",  "-e", default="7a",
                        choices=["7a", "aah"],
                        help="ECU profile to simulate (default: 7a)")
    parser.add_argument("--port", "-p", default=DEFAULT_PORT, type=int,
                        help=f"TCP port (default: {DEFAULT_PORT})")
    parser.add_argument("--hz",   "-f", default=3.0, type=float,
                        help="Broadcast rate in Hz (default: 3)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S")

    srv = MockServer(ecu=args.ecu, port=args.port, poll_hz=args.hz)
    srv.start()

    ecu_map = {"7a": "893906266D  2.3 20v 7A", "aah": "4A0906266  2.8 V6 AAH"}
    print(f"\n  KWPBridge Mock Server")
    print(f"  ECU:  {ecu_map[args.ecu]}")
    print(f"  Port: {args.port}")
    print(f"  Rate: {args.hz} Hz")
    print(f"\n  Connect HachiROM or any KWPBridge client.")
    print(f"  Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
            cc = srv.client_count()
            if cc:
                print(f"  [{time.strftime('%H:%M:%S')}] {cc} client(s) connected", end="\r")
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
