"""
KWPBridge CLI entry point.

Usage:
    python -m kwpbridge --port COM3
    python -m kwpbridge --port /dev/ttyUSB0 --cable ross_tech --groups 1 2 3 4
    python -m kwpbridge --port COM3 --protocol kwp2000 --cable ross_tech
    python -m kwpbridge --port COM3 --protocol auto   # tries kwp1281 then kwp2000
    python -m kwpbridge --list-ports
    python -m kwpbridge --scan
"""

import argparse
import logging
import sys

from .constants import (DEFAULT_PORT, CABLE_AUTO, CABLE_ROSS_TECH,
                        CABLE_FTDI, CABLE_CH340, ADDR_ENGINE)
from .protocol_detect import PROTO_AUTO, PROTO_KWP1281, PROTO_KWP2000
from . import __version__


def list_ports():
    """List available serial ports with cable type hints."""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("No serial ports found.")
            return
        print(f"{'Port':<15} {'VID:PID':<12} {'Description'}")
        print("-" * 60)
        for p in ports:
            vid_pid = f"{p.vid:04X}:{p.pid:04X}" if p.vid else "----:----"
            hint = ""
            if p.vid == 0x0403:
                if p.pid in (0xC33A, 0xC33B, 0xC33C, 0xFF00):
                    hint = " <- Ross-Tech"
                else:
                    hint = " <- FTDI (dumb KKL)"
            elif p.vid == 0x1A86:
                hint = " <- CH340 (dumb KKL)"
            print(f"{p.device:<15} {vid_pid:<12} {p.description or ''}{hint}")
    except ImportError:
        print("pyserial not installed. Run: pip install pyserial")


def scan_ecu(port, cable_type, protocol, detect_attempts):
    """
    Try to connect to the ECU, print identification and group 1, then exit.
    Honours --protocol: 'auto' tries KWP1281 then KWP2000.
    """
    from .protocol_detect import ProtocolDetector

    def status(msg):
        print(f"  {msg}")

    print(f"Scanning ECU on {port} (cable={cable_type}, protocol={protocol})…")
    detector = ProtocolDetector(
        port=port, cable_type=cable_type,
        force_protocol=protocol,
        max_attempts=detect_attempts,
        on_status=status,
    )
    result = detector.run()

    if not result.success:
        print(f"\nNo ECU found: {result.summary()}")
        sys.exit(1)

    kwp    = result.connection
    ecu_id = result.ecu_id
    print(f"\n  Protocol:    {result.protocol}")
    print(f"  Part number: {ecu_id.part_number}")
    print(f"  Component:   {ecu_id.component}")
    for e in (ecu_id.extra or []):
        print(f"  Extra:       {e}")

    print("\n  Reading group 1…")
    try:
        block = kwp.read_group(1)
        for cell in block.cells:
            print(f"    [{cell.index}] {cell.label:<30} {cell.display}")
    except Exception as e:
        print(f"    Error reading group 1: {e}")

    print("\n  Reading faults…")
    try:
        faults = kwp.read_faults()
        if faults:
            for f in faults:
                print(f"    {f.code_str}: {f.description} ({f.status_str})")
        else:
            print("    No faults stored.")
    except Exception as e:
        print(f"    Error reading faults: {e}")

    kwp.disconnect()
    print("\nScan complete.")


def main():
    parser = argparse.ArgumentParser(
        prog="kwpbridge",
        description=(
            f"KWPBridge v{__version__} -- VAG K-Line diagnostic bridge\n"
            f"Supports KWP1281 (pre-2002: 7A, AAH, M2.3.2, Digifant) and\n"
            f"KWP2000/ISO14230 (ME7.x, MED7.x, post-2001 VAG)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version",
                        version=f"KWPBridge {__version__}")
    parser.add_argument("--port", "-p", default=None,
                        help="Serial port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--cable", "-c", default=CABLE_AUTO,
                        choices=[CABLE_AUTO, CABLE_ROSS_TECH, CABLE_FTDI, CABLE_CH340],
                        help="Cable type (default: auto-detect from USB VID/PID)")
    parser.add_argument("--protocol", default=PROTO_AUTO,
                        choices=[PROTO_AUTO, PROTO_KWP1281, PROTO_KWP2000],
                        help=(
                            "ECU protocol (default: auto — tries kwp1281 then kwp2000). "
                            "Use 'kwp1281' for pre-2002 VAG (7A, AAH, Digifant, M2.3.2). "
                            "Use 'kwp2000' for ME7.x, MED7.x, post-2001 VAG."
                        ))
    parser.add_argument("--detect-attempts", type=int, default=2,
                        metavar="N",
                        help="Retries per protocol in auto mode (default: 2)")
    parser.add_argument("--groups", "-g", nargs="+", type=int,
                        default=[1, 2, 3, 4],
                        help="Measuring block groups to poll (default: 1 2 3 4)")
    parser.add_argument("--tcp-port", type=int, default=DEFAULT_PORT,
                        help=f"TCP port for IPC (default: {DEFAULT_PORT})")
    parser.add_argument("--ecu-address", type=lambda x: int(x, 0),
                        default=ADDR_ENGINE,
                        help=f"ECU address (default: 0x{ADDR_ENGINE:02X} = engine)")
    parser.add_argument("--list-ports", action="store_true",
                        help="List available serial ports and exit")
    parser.add_argument("--scan", action="store_true",
                        help="Connect, print identification and group 1, then exit")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    parser.add_argument("--poll-hz", type=float, default=10.0,
                        help="Target polling rate in Hz (default: 10)")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list_ports:
        list_ports()
        return

    if args.port is None:
        parser.error("--port required (use --list-ports to see available ports)")

    if args.scan:
        scan_ecu(args.port, args.cable, args.protocol, args.detect_attempts)
        return

    from .server import KWPServer
    server = KWPServer(
        serial_port      = args.port,
        groups           = args.groups,
        ecu_address      = args.ecu_address,
        cable_type       = args.cable,
        tcp_port         = args.tcp_port,
        poll_interval    = 1.0 / args.poll_hz,
        protocol         = args.protocol,
        detect_attempts  = args.detect_attempts,
    )

    proto_desc = {
        PROTO_AUTO:    "auto (tries kwp1281 → kwp2000)",
        PROTO_KWP1281: "kwp1281 (pre-2002 VAG: 7A, AAH, M2.3.2, Digifant)",
        PROTO_KWP2000: "kwp2000 (ME7.x / MED7.x / post-2001 VAG)",
    }
    print(f"KWPBridge v{__version__}")
    print(f"  Serial port:  {args.port}  (cable={args.cable})")
    print(f"  Protocol:     {proto_desc.get(args.protocol, args.protocol)}")
    print(f"  Poll groups:  {args.groups}  @ {args.poll_hz:.0f} Hz")
    print(f"  TCP port:     {args.tcp_port}")
    print(f"  ECU address:  0x{args.ecu_address:02X}")
    print(f"\nClients connect to 127.0.0.1:{args.tcp_port}")
    print("Press Ctrl+C to stop.\n")

    server.start()


if __name__ == "__main__":
    main()


def list_ports():
    """List available serial ports with cable type hints."""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("No serial ports found.")
            return
        print(f"{'Port':<15} {'VID:PID':<12} {'Description'}")
        print("-" * 60)
        for p in ports:
            vid_pid = f"{p.vid:04X}:{p.pid:04X}" if p.vid else "----:----"
            hint = ""
            if p.vid == 0x0403:
                if p.pid in (0xC33A, 0xC33B, 0xC33C, 0xFF00):
                    hint = " <- Ross-Tech"
                else:
                    hint = " <- FTDI (dumb KKL)"
            elif p.vid == 0x1A86:
                hint = " <- CH340 (dumb KKL)"
            print(f"{p.device:<15} {vid_pid:<12} {p.description or ''}{hint}")
    except ImportError:
        print("pyserial not installed. Run: pip install pyserial")


def scan_ecu(port, cable_type):
    """Try to connect to the ECU and print identification."""
    from .protocol import KWP1281, KWPError
    print(f"Scanning ECU on {port} (cable={cable_type})...")
    kwp = KWP1281(port=port, cable_type=cable_type)
    try:
        eid = kwp.connect(ADDR_ENGINE)
        print(f"  Connected!")
        print(f"  Part number: {eid.part_number}")
        print(f"  Component:   {eid.component}")
        for e in eid.extra:
            print(f"  Extra:       {e}")

        print("\n  Reading group 1...")
        block = kwp.read_group(1)
        for cell in block.cells:
            print(f"    [{cell.index}] {cell.label:<30} {cell.display}")

        print("\n  Reading faults...")
        faults = kwp.read_faults()
        if faults:
            for f in faults:
                print(f"    {f.code_str}: {f.description} ({f.status_str})")
        else:
            print("    No faults stored.")

        kwp.disconnect()
        print("\nScan complete.")

    except KWPError as e:
        print(f"  Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="kwpbridge",
        description=f"KWPBridge v{__version__} -- KWP1281 K-Line bridge for VAG vehicles",
    )
    parser.add_argument("--version", action="version",
                        version=f"KWPBridge {__version__}")
    parser.add_argument("--port", "-p", default=None,
                        help="Serial port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--cable", "-c", default=CABLE_AUTO,
                        choices=[CABLE_AUTO, CABLE_ROSS_TECH, CABLE_FTDI, CABLE_CH340],
                        help="Cable type (default: auto-detect from USB VID/PID)")
    parser.add_argument("--groups", "-g", nargs="+", type=int,
                        default=[1, 2, 3, 4],
                        help="Measuring block groups to poll (default: 1 2 3 4)")
    parser.add_argument("--tcp-port", type=int, default=DEFAULT_PORT,
                        help=f"TCP port for IPC (default: {DEFAULT_PORT})")
    parser.add_argument("--ecu-address", type=lambda x: int(x, 0),
                        default=ADDR_ENGINE,
                        help=f"ECU address (default: 0x{ADDR_ENGINE:02X} = engine)")
    parser.add_argument("--list-ports", action="store_true",
                        help="List available serial ports and exit")
    parser.add_argument("--scan", action="store_true",
                        help="Connect, print identification and group 1, then exit")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    parser.add_argument("--poll-hz", type=float, default=10.0,
                        help="Target polling rate in Hz (default: 10)")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list_ports:
        list_ports()
        return

    if args.port is None:
        parser.error("--port required (use --list-ports to see available ports)")

    if args.scan:
        scan_ecu(args.port, args.cable)
        return

    from .server import KWPServer
    server = KWPServer(
        serial_port   = args.port,
        groups        = args.groups,
        ecu_address   = args.ecu_address,
        cable_type    = args.cable,
        tcp_port      = args.tcp_port,
        poll_interval = 1.0 / args.poll_hz,
    )

    print(f"KWPBridge v{__version__}")
    print(f"  Serial port:  {args.port}  (cable={args.cable})")
    print(f"  Poll groups:  {args.groups}  @ {args.poll_hz:.0f} Hz")
    print(f"  TCP port:     {args.tcp_port}")
    print(f"  ECU address:  0x{args.ecu_address:02X}")
    print(f"\nClients connect to 127.0.0.1:{args.tcp_port}")
    print("Press Ctrl+C to stop.\n")

    server.start()


if __name__ == "__main__":
    main()
