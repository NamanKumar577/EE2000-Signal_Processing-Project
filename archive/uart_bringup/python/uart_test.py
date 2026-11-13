#!/usr/bin/env python3
"""
uart_bringup/python/uart_test.py
──────────────────────────────────────────────────────────────────────────────
Laptop-Side UART Communication and Verification Suite for Spartan-7 XC7S50.

Usage:
  # 1. Scan and list available serial ports:
  python uart_test.py --list

  # 2. Run full automated verification suite on a port:
  python uart_test.py --port COM5 --baud 115200 --all

  # 3. Send a custom string and check echo:
  python uart_test.py --port COM5 --baud 115200 --string "Hello Spartan-7!"

  # 4. Interactive echo terminal:
  python uart_test.py --port COM5 --baud 115200 --interactive
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import time
import argparse
import random
from typing import List, Tuple, Optional

try:
    import serial
    import serial.tools.list_ports as list_ports
except ImportError:
    print("[ERROR] pyserial is not installed! Install via: pip install pyserial")
    sys.exit(1)


def scan_ports() -> List[Tuple[str, str, str]]:
    """Discovers and returns all detected COM/serial ports on the laptop."""
    ports = list(list_ports.comports())
    return [(p.device, p.description, p.hwid) for p in ports]


def print_available_ports():
    """Prints formatted table of all discovered ports."""
    ports = scan_ports()
    print("=" * 70)
    print("DISCOVERED SERIAL / COM PORTS ON LAPTOP:")
    print("=" * 70)
    if not ports:
        print("  [NONE] No serial ports or USB-to-UART bridges currently detected.")
        print("  -> Ensure your USB-UART cable or FPGA board is connected.")
        print("  -> Check Device Manager for FTDI / CP210x / CH340 devices.")
    else:
        for dev, desc, hwid in ports:
            print(f"  • {dev:10s} : {desc}")
            print(f"    HWID     : {hwid}")
    print("=" * 70)


class UartTester:
    """Manages the laptop serial connection and test execution."""
    def __init__(self, port: str, baud_rate: int = 115200, timeout: float = 1.0):
        self.port_name = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def connect(self) -> bool:
        """Opens the serial connection with 8N1 configuration."""
        try:
            self.ser = serial.Serial(
                port=self.port_name,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            # Flush buffers and allow bridge reset stabilization
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.05)
            print(f"[OK] Connected to {self.port_name} at {self.baud_rate} baud (8-N-1).")
            return True
        except serial.SerialException as e:
            print(f"[ERROR] Failed to open port {self.port_name}: {e}")
            return False

    def close(self):
        """Closes the serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"[INFO] Connection to {self.port_name} closed.")

    def echo_transaction(self, tx_bytes: bytes) -> Tuple[bool, bytes, float]:
        """Transmits raw bytes to the FPGA and reads echoed response.

        Returns: (success, received_bytes, round_trip_time_seconds)
        """
        if not self.ser or not self.ser.is_open:
            return False, b"", 0.0

        self.ser.reset_input_buffer()
        t0 = time.perf_counter()

        try:
            self.ser.write(tx_bytes)
            self.ser.flush()
        except serial.SerialTimeoutException:
            return False, b"", 0.0

        # Read back exact expected number of bytes
        expected_len = len(tx_bytes)
        rx_bytes = bytearray()

        while len(rx_bytes) < expected_len:
            remaining = expected_len - len(rx_bytes)
            chunk = self.ser.read(remaining)
            if not chunk:
                break  # Timed out
            rx_bytes.extend(chunk)

        t_elapsed = time.perf_counter() - t0
        rx_data = bytes(rx_bytes)
        success = (rx_data == tx_bytes)

        return success, rx_data, t_elapsed


def run_comprehensive_tests(tester: UartTester):
    """Executes the full suite of communication and reliability tests."""
    print("\n" + "=" * 70)
    print(f"STARTING COMPREHENSIVE UART RELIABILITY VERIFICATION SUITE")
    print(f"Port: {tester.port_name} | Baud: {tester.baud_rate} | Target: Spartan-7 XC7S50")
    print("=" * 70)

    total_suites = 0
    passed_suites = 0

    # -------------------------------------------------------------------------
    # TEST 1: Single Characters
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Single Character Transmissions...")
    total_suites += 1
    test_chars = [b"A", b"Z", b"0", b"9", b"!", b"\r", b"\n", b"\x00", b"\xFF"]
    t1_pass = True
    for ch in test_chars:
        ok, rx, rtt = tester.echo_transaction(ch)
        if ok:
            print(f"  [PASS] Char {ch!r:10s} -> Echo: {rx!r:10s} (RTT: {rtt*1000:.2f} ms)")
        else:
            print(f"  [FAIL] Char {ch!r:10s} -> Echo: {rx!r:10s} (MISMATCH/TIMEOUT)")
            t1_pass = False

    if t1_pass:
        passed_suites += 1
        print("  -> SUITE 1 RESULT: PASS (All single characters matched)")
    else:
        print("  -> SUITE 1 RESULT: FAIL")

    # -------------------------------------------------------------------------
    # TEST 2: Short Strings
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Short String Transmissions...")
    total_suites += 1
    test_strings = [
        b"Hello FPGA!",
        b"Spartan-7 XC7S50",
        b"RealDigital Boolean Board",
        b"Fetal ECG Telemetry Link"
    ]
    t2_pass = True
    for s in test_strings:
        ok, rx, rtt = tester.echo_transaction(s)
        if ok:
            rate = len(s) / rtt if rtt > 0 else 0
            print(f"  [PASS] \"{s.decode()}\" -> Echo matched ({len(s)} bytes, RTT: {rtt*1000:.2f} ms, {rate:.1f} B/s)")
        else:
            print(f"  [FAIL] \"{s.decode()}\" -> Echo failed: received {rx!r}")
            t2_pass = False

    if t2_pass:
        passed_suites += 1
        print("  -> SUITE 2 RESULT: PASS (All short strings matched)")
    else:
        print("  -> SUITE 2 RESULT: FAIL")

    # -------------------------------------------------------------------------
    # TEST 3: Long Stream / Paragraph
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Long Continuous Stream Transmission (512 Bytes)...")
    total_suites += 1
    long_msg = (
        b"The AMD/Xilinx Spartan-7 XC7S50 FPGA platform operates at a 100.0 MHz system "
        b"clock and features a hardware-synthesized 8N1 UART communication engine. "
        b"In this verification phase, bidirectional host-to-FPGA streaming is tested "
        b"for framing stability, clock drift tolerance, and zero dropped bytes. "
        b"Continuous biopotential ingestion requires steady telemetry bandwidth without "
        b"buffer underrun or overrun. This test confirms sustained loopback echo integrity. "
    )
    long_payload = (long_msg * 2)[:512]
    ok, rx, rtt = tester.echo_transaction(long_payload)
    if ok:
        throughput_kbps = (len(long_payload) * 10 / rtt) / 1000  # 10 bits/byte UART
        passed_suites += 1
        print(f"  [PASS] 512-byte continuous block echoed with 100% data integrity!")
        print(f"         Total Time   : {rtt*1000:.2f} ms")
        print(f"         Throughput   : {throughput_kbps:.2f} kbaud (Effective: {len(long_payload)/rtt:.1f} B/s)")
        print("  -> SUITE 3 RESULT: PASS")
    else:
        print(f"  [FAIL] Long block mismatch: Sent 512 bytes, received {len(rx)} bytes")
        print("  -> SUITE 3 RESULT: FAIL")

    # -------------------------------------------------------------------------
    # TEST 4: Full 256-Byte Binary Sweep (0x00 - 0xFF)
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Full 256-Byte Binary Value Sweep (0x00 through 0xFF)...")
    total_suites += 1
    binary_payload = bytes(range(256))
    ok, rx, rtt = tester.echo_transaction(binary_payload)
    if ok:
        passed_suites += 1
        print(f"  [PASS] Complete 256-byte binary pattern verified (all 8-bit symbols matched).")
        print(f"         RTT: {rtt*1000:.2f} ms")
        print("  -> SUITE 4 RESULT: PASS")
    else:
        diffs = [f"Byte {i}: Sent 0x{b:02X} != Recv 0x{rx[i]:02X}" for i, b in enumerate(binary_payload) if i < len(rx) and b != rx[i]]
        print(f"  [FAIL] Binary sweep mismatch ({len(diffs)} byte differences): {diffs[:5]}")
        print("  -> SUITE 4 RESULT: FAIL")

    # -------------------------------------------------------------------------
    # TEST 5: Repeated Rapid Stress Test (50 Iterations)
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Rapid Stress & Reliability Test (50 Iterations)...")
    total_suites += 1
    t5_pass = True
    latencies = []
    total_bytes_sent = 0

    for it in range(50):
        # Generate random length random payload
        pkt_len = random.randint(8, 64)
        payload = bytes([random.randint(0, 255) for _ in range(pkt_len)])
        ok, rx, rtt = tester.echo_transaction(payload)
        if ok:
            latencies.append(rtt)
            total_bytes_sent += pkt_len
        else:
            print(f"  [FAIL] Stress test iteration {it+1} failed: sent {pkt_len} bytes, got {len(rx)} bytes")
            t5_pass = False
            break

    if t5_pass and latencies:
        passed_suites += 1
        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        print(f"  [PASS] 50/50 stress iterations completed successfully.")
        print(f"         Total Bytes Echoed : {total_bytes_sent} bytes")
        print(f"         Latency (Min/Avg/Max): {min_lat*1000:.2f} ms / {avg_lat*1000:.2f} ms / {max_lat*1000:.2f} ms")
        print("  -> SUITE 5 RESULT: PASS")
    else:
        print("  -> SUITE 5 RESULT: FAIL")

    # -------------------------------------------------------------------------
    # Final Scorecard
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"HARDWARE TEST SUMMARY: {passed_suites} / {total_suites} SUITES PASSED")
    if passed_suites == total_suites:
        print("OVERALL STATUS: [PASS] UART HARDWARE COMMUNICATION LINK FULLY VERIFIED")
    else:
        print("OVERALL STATUS: [FAIL] ONE OR MORE COMMUNICATION SUITES ENCOUNTERED ERRORS")
    print("=" * 70)


def interactive_terminal(tester: UartTester):
    """Interactive console where user types text and sees FPGA echo."""
    print("=" * 70)
    print("INTERACTIVE UART ECHO TERMINAL (Type 'exit' or 'quit' to quit)")
    print("Connected to:", tester.port_name, f"at {tester.baud_rate} baud")
    print("=" * 70)

    while True:
        try:
            line = input("\nSend > ")
            if line.strip().lower() in ["exit", "quit"]:
                break
            if not line:
                continue

            send_data = line.encode("utf-8") + b"\n"
            ok, rx, rtt = tester.echo_transaction(send_data)
            if ok:
                print(f"FPGA Echo < {rx.decode(errors='replace').strip()}  (RTT: {rtt*1000:.2f} ms)")
            else:
                print(f"[TIMEOUT / MISMATCH] Received: {rx!r}")
        except KeyboardInterrupt:
            break
    print("\nExiting interactive terminal.")


def main():
    parser = argparse.ArgumentParser(
        description="UART Hardware Verification and Testing Tool for Spartan-7 XC7S50"
    )
    parser.add_argument("--list", action="store_true", help="Scan and list all detected COM/serial ports")
    parser.add_argument("--port", type=str, default="", help="Serial port name (e.g. COM3, COM5, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--timeout", type=float, default=1.0, help="Read timeout in seconds (default: 1.0)")
    parser.add_argument("--string", type=str, default="", help="Send a single test string and verify echo")
    parser.add_argument("--all", action="store_true", help="Run the full automated verification test suite")
    parser.add_argument("--interactive", action="store_true", help="Open interactive echo terminal")

    args = parser.parse_args()

    if args.list or not args.port:
        print_available_ports()
        if not args.port:
            print("\nHint: Specify --port <PORT_NAME> (e.g. --port COM3 --all) to test communication.")
            return

    tester = UartTester(port=args.port, baud_rate=args.baud, timeout=args.timeout)
    if not tester.connect():
        sys.exit(1)

    try:
        if args.all:
            run_comprehensive_tests(tester)
        elif args.string:
            payload = args.string.encode("utf-8")
            print(f"Transmitting: {args.string!r} ({len(payload)} bytes)...")
            ok, rx, rtt = tester.echo_transaction(payload)
            if ok:
                print(f"[PASS] Echo matched: {rx.decode(errors='replace')!r} (RTT: {rtt*1000:.2f} ms)")
            else:
                print(f"[FAIL] Echo failed: received {rx!r}")
        elif args.interactive:
            interactive_terminal(tester)
        else:
            print("No test mode specified. Running quick single-string test...")
            ok, rx, rtt = tester.echo_transaction(b"PING\n")
            if ok:
                print(f"[PASS] Received echo: {rx!r} ({rtt*1000:.2f} ms)")
            else:
                print(f"[FAIL] Received: {rx!r}")
    finally:
        tester.close()


if __name__ == "__main__":
    main()
