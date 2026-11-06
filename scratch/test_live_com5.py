#!/usr/bin/env python3
"""
Test basic live communication with FPGA on COM5.
"""
import sys
import time
import serial
from pathlib import Path

PROJECT_ROOT = Path(r"D:\signal_project")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fpga_implementation.uart_host.fecg_uart_client import (
    encode_sample_packet, encode_calibration_packet, UARTStreamFramer
)

def test_live_fpga():
    port = "COM5"
    baud = 115200
    print(f"Connecting to {port} at {baud} baud...")
    ser = serial.Serial(port, baud, timeout=0.5)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)

    # Send calibration weights [7915, -5010, -21569, 22820]
    weights = [7915, -5010, -21569, 22820]
    cal_pkt = encode_calibration_packet(weights)
    print(f"Sending Calibration Packet: {cal_pkt.hex()} (len={len(cal_pkt)})")
    ser.write(cal_pkt)
    time.sleep(0.05)

    framer = UARTStreamFramer()

    # Send 50 test samples at 250 Hz (4 ms interval)
    print("Sending 50 test samples at 250 Hz...")
    tx_times = []
    rx_packets = []
    
    t_start = time.perf_counter()
    next_tx = t_start

    for t in range(50):
        val = 1000 if (t % 20 < 10) else -1000
        pkt = encode_sample_packet(t & 0xFF, val, 0, 0, 0)
        ser.write(pkt)
        tx_times.append(time.perf_counter())

        in_w = ser.in_waiting
        if in_w > 0:
            raw = ser.read(in_w)
            for ptype, pobj, raw_b in framer.feed(raw):
                rx_packets.append((time.perf_counter(), ptype, pobj))

        next_tx += 0.0040
        sleep_dur = next_tx - time.perf_counter()
        if sleep_dur > 0:
            time.sleep(sleep_dur)

    deadline = time.perf_counter() + 0.2
    while time.perf_counter() < deadline:
        if ser.in_waiting > 0:
            raw = ser.read(ser.in_waiting)
            for ptype, pobj, raw_b in framer.feed(raw):
                rx_packets.append((time.perf_counter(), ptype, pobj))
        time.sleep(0.005)

    ser.close()

    print(f"\n--- Results ---")
    print(f"Samples sent: 50")
    print(f"Packets decoded: {framer.total_packets_decoded}")
    print(f"  FECG Stream: {framer.packet_counts['FECG_STREAM']}")
    print(f"  Telemetry:   {framer.packet_counts['TELEMETRY']}")
    print(f"  CRC Errors:  {framer.total_crc_errors}")
    print(f"  Bytes Dropped: {framer.total_bytes_dropped}")

    if rx_packets:
        print(f"\nFirst 5 received packets:")
        for ts, ptype, pobj in rx_packets[:5]:
            if ptype == "FECG_STREAM":
                print(f"  [{ptype}] seq={pobj.seq}, val={pobj.sample_s24} (0x{pobj.sample_s24 & 0xFFFFFF:06X})")
            else:
                print(f"  [{ptype}] {pobj}")

if __name__ == "__main__":
    test_live_fpga()
