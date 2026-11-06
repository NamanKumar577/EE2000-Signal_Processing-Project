"""
tests/integration/test_fecg_uart_client.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive Unit & Integration Test Suite for Host UART Streaming Client
and Bit-Accurate Telemetry Protocol on AMD/Xilinx Spartan-7 XC7S50.
"""

import time
import random
import pytest
from pathlib import Path

from fpga_implementation.uart_host.fecg_uart_client import (
    crc8_ccitt,
    encode_sample_packet, decode_sample_packet,
    encode_calibration_packet, decode_calibration_packet,
    encode_fecg_stream_packet, decode_fecg_stream_packet,
    encode_fhr_telemetry_packet, decode_fhr_telemetry_packet,
    encode_diagnostic_packet, decode_diagnostic_packet,
    UARTStreamFramer, FECGUartClient, MockSerialPort,
    HEADER_SAMPLE, HEADER_CALIBRATION, HEADER_FECG_STREAM,
    HEADER_FHR_TELEMETRY, HEADER_DIAGNOSTIC,
    LEN_SAMPLE, LEN_CALIBRATION, LEN_FECG_STREAM, LEN_FHR_TELEMETRY, LEN_DIAGNOSTIC,
    FLAG_REAL_DETECTED, FLAG_FUSED_BEAT, FLAG_HELD_FHR, FLAG_INVALID_WARMUP,
    ERR_DOWNLINK_CRC_FAIL, ERR_DOWNLINK_SEQ_GAP, ERR_BIQUAD_SATURATION, ERR_UART_FIFO_OVERFLOW,
    SCALE_Q12, SCALE_Q15, SCALE_Q20
)


def test_crc8_standard_test_vector():
    """Verify CRC-8-CCITT against standard golden test vector."""
    assert crc8_ccitt(b"123456789") == 0xF4
    assert crc8_ccitt(b"") == 0x00
    assert crc8_ccitt(b"\x00") == 0x00


def test_crc8_single_bit_sensitivity():
    """Verify any 1-bit flip alters the computed CRC8."""
    data = bytearray(b"FetalECG_1234")
    original_crc = crc8_ccitt(data)
    for byte_idx in range(len(data)):
        for bit_idx in range(8):
            corrupted = bytearray(data)
            corrupted[byte_idx] ^= (1 << bit_idx)
            corrupted_crc = crc8_ccitt(corrupted)
            assert corrupted_crc != original_crc, f"CRC collision on byte {byte_idx} bit {bit_idx}"


# ── 1. Downlink Sample Packet (0xA5, 11 bytes) ──────────────────────────────

def test_sample_packet_round_trip():
    """Verify 11-byte Downlink Sample Packet encoding and decoding."""
    seq = 175
    ch0, ch1, ch2, ch3 = 4096, -2048, 1024, -512
    pkt = encode_sample_packet(seq, ch0, ch1, ch2, ch3)

    assert len(pkt) == LEN_SAMPLE == 11
    assert pkt[0] == HEADER_SAMPLE

    sample = decode_sample_packet(pkt)
    assert sample.seq == seq
    assert (sample.ch0, sample.ch1, sample.ch2, sample.ch3) == (ch0, ch1, ch2, ch3)
    assert abs(sample.ch0_mv - 1.0) < 1e-5
    assert abs(sample.ch1_mv - (-0.5)) < 1e-5


def test_sample_packet_boundary_values():
    """Test signed 16-bit boundary limits [-32768, 32767]."""
    pkt_min = encode_sample_packet(0, -32768, -32768, -32768, -32768)
    dec_min = decode_sample_packet(pkt_min)
    assert dec_min.ch0 == -32768

    pkt_max = encode_sample_packet(255, 32767, 32767, 32767, 32767)
    dec_max = decode_sample_packet(pkt_max)
    assert dec_max.ch0 == 32767

    # Out of bounds must raise ValueError
    with pytest.raises(ValueError):
        encode_sample_packet(0, 32768, 0, 0, 0)
    with pytest.raises(ValueError):
        encode_sample_packet(0, -32769, 0, 0, 0)


def test_sample_packet_crc_corruption():
    """Corrupting any byte in sample packet must be rejected."""
    pkt = bytearray(encode_sample_packet(10, 100, 200, 300, 400))
    pkt[5] ^= 0x01
    with pytest.raises(ValueError, match="CRC8 mismatch"):
        decode_sample_packet(bytes(pkt))


# ── 2. Downlink Calibration Packet (0xC3, 10 bytes) ──────────────────────────

def test_calibration_packet_round_trip():
    """Verify 10-byte Downlink Calibration Packet encoding and decoding."""
    weights = (16384, -16384, 8192, -4096)
    pkt = encode_calibration_packet(weights)

    assert len(pkt) == LEN_CALIBRATION == 10
    assert pkt[0] == HEADER_CALIBRATION

    cal = decode_calibration_packet(pkt)
    assert (cal.w0, cal.w1, cal.w2, cal.w3) == weights
    assert abs(cal.w0_float - 0.5) < 1e-5
    assert abs(cal.w1_float - (-0.5)) < 1e-5


def test_calibration_packet_errors():
    """Verify validation of weight length and range."""
    with pytest.raises(ValueError, match="Expected 4 weights"):
        encode_calibration_packet([1, 2, 3])
    with pytest.raises(ValueError):
        encode_calibration_packet([32768, 0, 0, 0])

    pkt = bytearray(encode_calibration_packet([100, 200, 300, 400]))
    pkt[9] ^= 0xFF
    with pytest.raises(ValueError, match="CRC8 mismatch"):
        decode_calibration_packet(bytes(pkt))


# ── 3. Uplink Clean FECG Stream Packet (0x5A, 6 bytes) ───────────────────────

def test_fecg_stream_packet_round_trip():
    """Verify 6-byte Clean FECG Stream Packet with signed 24-bit Q20 values."""
    test_cases = [
        (0, 0, 0.0),
        (1, 1048576, 1.0),            # +1.0 mV
        (2, -1048576, -1.0),          # -1.0 mV
        (3, 524288, 0.5),             # +0.5 mV
        (4, -524288, -0.5),           # -0.5 mV
        (255, 8388607, 7.999999),     # Max positive signed 24-bit
        (128, -8388608, -8.0),        # Min negative signed 24-bit
    ]
    for seq, s24, expected_mv in test_cases:
        pkt = encode_fecg_stream_packet(seq, s24)
        assert len(pkt) == LEN_FECG_STREAM == 6
        assert pkt[0] == HEADER_FECG_STREAM

        fecg = decode_fecg_stream_packet(pkt)
        assert fecg.seq == seq
        assert fecg.sample_s24 == s24
        assert abs(fecg.fecg_mv - expected_mv) < 1e-4


def test_fecg_stream_packet_overflow():
    """Verify 24-bit integer overflow checks."""
    with pytest.raises(ValueError):
        encode_fecg_stream_packet(0, 8388608)
    with pytest.raises(ValueError):
        encode_fecg_stream_packet(0, -8388609)


# ── 4. Uplink QRS Event & FHR Telemetry Packet (0xAA, 8 bytes) ───────────────

def test_fhr_telemetry_packet_round_trip():
    """Verify 8-byte FHR Telemetry Packet encoding and decoding."""
    timestamp = 16000000
    fhr_x10 = 1455  # 145.5 bpm
    flag = FLAG_REAL_DETECTED
    confident = True
    saturated = False

    pkt = encode_fhr_telemetry_packet(timestamp, fhr_x10, flag, confident=confident, saturated=saturated)
    assert len(pkt) == LEN_FHR_TELEMETRY == 8
    assert pkt[0] == HEADER_FHR_TELEMETRY

    event = decode_fhr_telemetry_packet(pkt)
    assert event.timestamp == timestamp
    assert abs(event.fhr_bpm - 145.5) < 1e-5
    assert event.flag == flag
    assert event.classification == "REAL"
    assert event.confident is True
    assert event.saturated is False


def test_fhr_telemetry_flags_permutation():
    """Verify all 4 classification flags and status bit combinations."""
    flags = [
        (FLAG_REAL_DETECTED, "REAL"),
        (FLAG_FUSED_BEAT, "FUSED"),
        (FLAG_HELD_FHR, "HELD"),
        (FLAG_INVALID_WARMUP, "WARMUP"),
    ]
    for flag_val, flag_name in flags:
        for conf in [True, False]:
            for sat in [True, False]:
                pkt = encode_fhr_telemetry_packet(1000, 1200, flag_val, confident=conf, saturated=sat)
                event = decode_fhr_telemetry_packet(pkt)
                assert event.flag == flag_val
                assert event.classification == flag_name
                assert event.confident == conf
                assert event.saturated == sat


# ── 5. Uplink Diagnostic Packet (0xEE, 8 bytes) ──────────────────────────────

def test_diagnostic_packet_round_trip():
    """Verify 8-byte Diagnostic Packet."""
    pkt = encode_diagnostic_packet(ERR_BIQUAD_SATURATION, max_state=32000, threshold=1500)
    assert len(pkt) == LEN_DIAGNOSTIC == 8
    assert pkt[0] == HEADER_DIAGNOSTIC

    diag = decode_diagnostic_packet(pkt)
    assert diag.error_code == ERR_BIQUAD_SATURATION
    assert diag.error_name == "BIQUAD_SATURATION"
    assert diag.max_state == 32000
    assert diag.threshold == 1500


# ── 6. Streaming Framer & Resynchronization Robustness ────────────────────────

def test_framer_clean_multi_packet_stream():
    """Verify stream framer parses back-to-back packets of different types."""
    framer = UARTStreamFramer()

    pkt_sample = encode_sample_packet(1, 100, 200, 300, 400)
    pkt_fecg1 = encode_fecg_stream_packet(1, 500000)
    pkt_fecg2 = encode_fecg_stream_packet(2, 510000)
    pkt_fhr = encode_fhr_telemetry_packet(500, 1380, FLAG_REAL_DETECTED)
    pkt_cal = encode_calibration_packet([1000, 2000, 3000, 4000])

    full_stream = pkt_sample + pkt_fecg1 + pkt_fecg2 + pkt_fhr + pkt_cal

    results = framer.feed(full_stream)
    assert len(results) == 5
    assert [p[0] for p in results] == ["SAMPLE", "FECG_STREAM", "FECG_STREAM", "TELEMETRY", "CALIBRATION"]
    assert framer.total_bytes_dropped == 0
    assert framer.total_crc_errors == 0


def test_framer_resynchronization_after_corruption():
    """
    Test framer resynchronization when corrupted bytes or false headers appear
    in the stream.
    """
    framer = UARTStreamFramer()

    valid1 = encode_fecg_stream_packet(10, 100000)
    valid2 = encode_fhr_telemetry_packet(2500, 1420, FLAG_FUSED_BEAT)

    # Corrupted packet: valid header, garbage payload, invalid CRC
    corrupted_packet = bytes([HEADER_FECG_STREAM, 0x11, 0x22, 0x33, 0x44, 0x00])

    # Stream: noise + valid1 + corrupted + noise + valid2
    noisy_stream = (
        b"\xFF\x00\x12\x34\x56"  # 5 bytes line noise
        + valid1
        + corrupted_packet
        + b"\xAA"                # False 0xAA header byte without full valid packet
        + valid2
    )

    results = framer.feed(noisy_stream)
    assert len(results) == 2
    assert results[0][0] == "FECG_STREAM"
    assert results[1][0] == "TELEMETRY"
    assert framer.total_crc_errors >= 1
    assert framer.total_bytes_dropped > 0


def test_framer_fragmented_delivery():
    """Verify framer handles byte-by-byte or tiny chunk deliveries seamlessly."""
    framer = UARTStreamFramer()
    pkt = encode_sample_packet(99, 1000, -1000, 2000, -2000)

    # Deliver 1 byte at a time
    accumulated_results = []
    for b in pkt:
        res = framer.feed(bytes([b]))
        accumulated_results.extend(res)

    assert len(accumulated_results) == 1
    assert accumulated_results[0][0] == "SAMPLE"
    assert accumulated_results[0][1].seq == 99


# ── 7. Full-Duplex Client & Rate Generation ──────────────────────────────────

def test_client_mock_loopback_and_background_listener():
    """Verify FECGUartClient with MockSerialPort and background listener thread."""
    mock = MockSerialPort(echo_fecg=True)
    client = FECGUartClient(port="MOCK", baud_rate=115200, serial_instance=mock)

    received_packets = []

    def on_pkt(ptype, obj):
        received_packets.append((ptype, obj))

    client.start_background_listener(on_packet=on_pkt)

    # Send 10 samples
    for i in range(10):
        client.send_sample(ch0=100 + i, ch1=200, ch2=300, ch3=400)
        time.sleep(0.005)

    # Give listener thread time to dispatch
    time.sleep(0.05)
    client.stop_background_listener()

    assert len(received_packets) == 10
    assert all(p[0] == "FECG_STREAM" for p in received_packets)
    assert client.fecg_queue.qsize() == 10
