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
                        choices=["7a", "aah", "digifant", "g60", "g40",
                                 "me7", "awp", "aum", "auq", "bam",
                                 "27t", "s4", "agb", "are", "bes"],
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

    ecu_map = {
        "7a":       "893906266D  2.3 20v 7A",
        "aah":      "4A0906266   2.8 V6 AAH",
        "digifant": "037906023   Digifant 1 G60/G40",
        "g60":      "037906023   Digifant 1 G60",
        "g40":      "037906023   Digifant 1 G40",
        "me7":      "06A906032BN ME7.5 AWP 1.8T 180hp",
        "awp":      "06A906032BN ME7.5 AWP 1.8T 180hp",
        "aum":      "06A906032BN ME7.5 AUM 1.8T 150hp (AWP mock)",
        "auq":      "06A906032BN ME7.5 AUQ 1.8T 180hp (AWP mock)",
        "bam":      "06A906032BN ME7.5 BAM 1.8T 190hp (AWP mock)",
        "27t":      "8D0907551M  ME7.1 AGB 2.7T 250hp S4 B5",
        "s4":       "8D0907551M  ME7.1 AGB 2.7T 250hp S4 B5",
        "agb":      "8D0907551M  ME7.1 AGB 2.7T 250hp S4 B5",
        "are":      "8D0907551M  ME7.1 ARE 2.7T 265hp (AGB mock)",
        "bes":      "8D0907551M  ME7.1 BES 2.7T 250hp (AGB mock)",
    }
    print("\n  KWPBridge Mock Server")
    print(f"  ECU:  {ecu_map[args.ecu]}")
    print(f"  Port: {args.port}")
    print(f"  Rate: {args.hz} Hz")
    print("\n  Connect HachiROM or any KWPBridge client.")
    print("  Press Ctrl+C to stop.\n")

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

# m232 alias already handled in server.py
