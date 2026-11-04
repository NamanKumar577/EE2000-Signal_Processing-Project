"""
code/src/uart_protocol.py
──────────────────────────────────────────────────────────────────────────────
Bit-Accurate UART Protocol Encoder & Decoder for Spartan-7 Telemetry.

Packets:
  1. Downlink Calibration Packet (10 Bytes):
     - Byte 0: 0xC3 (Header)
     - Bytes 1-2: w0 (Signed 16-bit Q1.15, Big-Endian)
     - Bytes 3-4: w1 (Signed 16-bit Q1.15, Big-Endian)
     - Bytes 5-6: w2 (Signed 16-bit Q1.15, Big-Endian)
     - Bytes 7-8: w3 (Signed 16-bit Q1.15, Big-Endian)
     - Byte 9: CRC8-CCITT over Bytes 0-8 (Polynomial 0x07)
  
  2. Uplink QRS Event & FHR Telemetry Packet (8 Bytes):
     - Byte 0: 0xAA (Header)
     - Bytes 1-3: Timestamp (24-bit unsigned integer, Big-Endian)
     - Bytes 4-5: FHR in units of 0.1 bpm (16-bit unsigned, Big-Endian: e.g. 1402 = 140.2 bpm)
     - Byte 6: Status Flags:
       * bits 1:0: 00: Real, 01: Fused, 10: Held, 11: Warmup
       * bit 2: Confidence flag (1: Confident, 0: Uncertain)
       * bits 7:3: Reserved (0)
     - Byte 7: CRC8-CCITT over Bytes 0-6 (Polynomial 0x07)
"""

from typing import Tuple, Optional, Sequence
import struct

CRC8_POLYNOMIAL = 0x07
CRC8_INIT = 0x00

def crc8_ccitt(data: bytes) -> int:
    """Compute CRC-8-CCITT checksum over bytes with polynomial 0x07, init 0x00."""
    crc = CRC8_INIT
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ CRC8_POLYNOMIAL) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

# ── Calibration Packet (10 Bytes) ───────────────────────────────────────────
HEADER_CALIBRATION = 0xC3

def encode_calibration_packet(weights: Sequence[int]) -> bytes:
    """Encode 4 signed 16-bit Q1.15 weights into 10-byte calibration packet."""
    if len(weights) != 4:
        raise ValueError(f"Expected 4 weights, got {len(weights)}")
    payload = bytearray([HEADER_CALIBRATION])
    for w in weights:
        payload.extend(struct.pack(">h", int(w)))
    crc = crc8_ccitt(bytes(payload))
    payload.append(crc)
    return bytes(payload)

def decode_calibration_packet(packet: bytes) -> Tuple[int, int, int, int]:
    """Decode and verify 10-byte calibration packet. Returns (w0, w1, w2, w3)."""
    if len(packet) != 10:
        raise ValueError(f"Calibration packet length must be 10, got {len(packet)}")
    if packet[0] != HEADER_CALIBRATION:
        raise ValueError(f"Invalid calibration header: 0x{packet[0]:02X}")
    expected_crc = crc8_ccitt(packet[:9])
    if packet[9] != expected_crc:
        raise ValueError(f"CRC8 mismatch: expected 0x{expected_crc:02X}, got 0x{packet[9]:02X}")
    w0, w1, w2, w3 = struct.unpack(">hhhh", packet[1:9])
    return w0, w1, w2, w3

# ── QRS & FHR Telemetry Packet (8 Bytes) ─────────────────────────────────────
HEADER_FHR_TELEMETRY = 0xAA

def encode_fhr_telemetry_packet(timestamp: int, fhr_x10: int, flag_2bit: int, confident: bool = True) -> bytes:
    """
    Encode QRS event & FHR telemetry into 8-byte packet.
    timestamp: 24-bit unsigned sample index
    fhr_x10: 16-bit unsigned (e.g. 1402 = 140.2 bpm)
    flag_2bit: 00: Real, 01: Fused, 10: Held, 11: Warmup
    """
    status_byte = (flag_2bit & 0x03) | ((1 if confident else 0) << 2)
    payload = bytearray([
        HEADER_FHR_TELEMETRY,
        (timestamp >> 16) & 0xFF,
        (timestamp >> 8) & 0xFF,
        timestamp & 0xFF,
        (fhr_x10 >> 8) & 0xFF,
        fhr_x10 & 0xFF,
        status_byte
    ])
    crc = crc8_ccitt(bytes(payload))
    payload.append(crc)
    return bytes(payload)

def decode_fhr_telemetry_packet(packet: bytes) -> Tuple[int, float, int, bool]:
    """
    Decode and verify 8-byte FHR telemetry packet.
    Returns: (timestamp, fhr_bpm, flag_2bit, is_confident)
    """
    if len(packet) != 8:
        raise ValueError(f"FHR packet length must be 8, got {len(packet)}")
    if packet[0] != HEADER_FHR_TELEMETRY:
        raise ValueError(f"Invalid telemetry header: 0x{packet[0]:02X}")
    expected_crc = crc8_ccitt(packet[:7])
    if packet[7] != expected_crc:
        raise ValueError(f"CRC8 mismatch: expected 0x{expected_crc:02X}, got 0x{packet[7]:02X}")
    
    timestamp = (packet[1] << 16) | (packet[2] << 8) | packet[3]
    fhr_x10 = (packet[4] << 8) | packet[5]
    fhr_bpm = fhr_x10 / 10.0
    status_byte = packet[6]
    flag_2bit = status_byte & 0x03
    is_confident = bool((status_byte >> 2) & 0x01)

    return timestamp, fhr_bpm, flag_2bit, is_confident
