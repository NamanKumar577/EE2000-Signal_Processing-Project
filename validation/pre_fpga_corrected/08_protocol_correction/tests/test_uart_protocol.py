"""
code/tests/test_uart_protocol.py
──────────────────────────────────────────────────────────────────────────────
Tests for UART communication protocol encoder, decoder, and CRC8-CCITT.
Verifies:
  1. CRC8-CCITT matches standard polynomial 0x07 with init 0x00.
  2. 10-byte calibration packet encode and decode integrity.
  3. Corrupted CRC8 byte raises ValueError and prevents weight update.
  4. 8-byte QRS/FHR telemetry packet encode and decode integrity.
  5. Correct resolution of 0.1 bpm (e.g. 140.2 bpm -> 1402).
  6. 2-bit state flags and confidence bit preservation.
"""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.uart_protocol import (
    crc8_ccitt, encode_calibration_packet, decode_calibration_packet,
    encode_fhr_telemetry_packet, decode_fhr_telemetry_packet,
    HEADER_CALIBRATION, HEADER_FHR_TELEMETRY
)

def test_crc8_standard_test_vector():
    """Verify CRC8 on standard ASCII string '123456789'."""
    # Standard CRC-8-CCITT (poly 0x07, init 0x00) for b'123456789' is 0xF4
    test_bytes = b"123456789"
    crc = crc8_ccitt(test_bytes)
    assert crc == 0xF4, f"CRC8 test vector failed: got 0x{crc:02X}, expected 0xF4"

def test_calibration_packet_round_trip():
    """Verify encoding and decoding of signed 16-bit Q1.15 spatial weights."""
    weights_in = (16384, -8192, 4096, -2048)
    packet = encode_calibration_packet(weights_in)
    assert len(packet) == 10
    assert packet[0] == HEADER_CALIBRATION

    w0, w1, w2, w3 = decode_calibration_packet(packet)
    assert (w0, w1, w2, w3) == weights_in

def test_calibration_crc_corruption():
    """Corrupting a weight byte or CRC byte must be rejected by decoder."""
    weights_in = (32767, -32768, 0, 1000)
    packet = bytearray(encode_calibration_packet(weights_in))
    # Corrupt single bit
    packet[3] ^= 0x01

    with pytest.raises(ValueError, match="CRC8 mismatch"):
        decode_calibration_packet(bytes(packet))

def test_fhr_telemetry_packet_round_trip():
    """Verify 8-byte FHR telemetry packet encoding and decoding."""
    timestamp_in = 75432
    fhr_x10_in = 1402 # 140.2 bpm
    flag_in = 0b01    # Fused beat
    confident_in = True

    packet = encode_fhr_telemetry_packet(timestamp_in, fhr_x10_in, flag_in, confident=confident_in)
    assert len(packet) == 8
    assert packet[0] == HEADER_FHR_TELEMETRY

    t_out, fhr_out, flag_out, conf_out = decode_fhr_telemetry_packet(packet)
    assert t_out == timestamp_in
    assert abs(fhr_out - 140.2) < 1e-4
    assert flag_out == flag_in
    assert conf_out == confident_in
