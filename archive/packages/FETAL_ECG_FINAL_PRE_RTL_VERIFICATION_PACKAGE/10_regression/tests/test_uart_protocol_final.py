"""
Test UART Protocol, CRC8-CCITT, Packet Serialization, and Resynchronization
==========================================================================
Verifies:
1. Standard CRC8-CCITT test vector b"123456789" -> 0xF4.
2. FECG stream packet (0x5A) encoding and bit-exact decoding.
3. Telemetry packet (0xAA) encoding and bit-exact decoding.
4. Calibration packet (0xC3) encoding and decoding.
5. Framer robustness against byte drops, noise injection, and resynchronization.
"""

import pytest
from uart_protocol_final import (
    crc8_ccitt,
    encode_fecg_stream_packet,
    decode_fecg_stream_packet,
    encode_fhr_telemetry_packet,
    decode_fhr_telemetry_packet,
    encode_calibration_packet,
    decode_calibration_packet,
    UARTStreamFramer,
    HEADER_CALIBRATION,
    HEADER_FHR_TELEMETRY,
    HEADER_FECG_STREAM,
    FLAG_REAL_DETECTED,
    FLAG_FUSED_BEAT,
    FLAG_HELD_FHR,
    FLAG_INVALID_WARMUP
)

def test_crc8_ccitt_standard_vector():
    """Verify standard test vector: b'123456789' -> 0xF4."""
    test_vec = b"123456789"
    crc = crc8_ccitt(test_vec)
    assert crc == 0xF4, f"CRC8-CCITT failed: expected 0xF4, got 0x{crc:02X}"

def test_fecg_stream_packet_roundtrip():
    """Verify 6-byte stream packet serialization, framing, and deserialization."""
    seq = 42
    # Test positive and negative signed 24-bit values
    test_samples = [1024, -2048, 524287, -524288, 0]
    for s in test_samples:
        pkt = encode_fecg_stream_packet(seq, s)
        assert len(pkt) == 6
        assert pkt[0] == HEADER_FECG_STREAM
        assert pkt[1] == seq
        
        # Check decode
        d_seq, d_sample = decode_fecg_stream_packet(pkt)
        assert d_seq == seq
        assert d_sample == s

def test_telemetry_packet_roundtrip():
    """Verify 8-byte telemetry packet serialization, framing, and deserialization."""
    timestamp = 125000
    fhr_x10 = 1402  # 140.2 bpm
    flag = FLAG_FUSED_BEAT
    confident = True
    saturated = False
    
    pkt = encode_fhr_telemetry_packet(timestamp, fhr_x10, flag, confident, saturated)
    assert len(pkt) == 8
    assert pkt[0] == HEADER_FHR_TELEMETRY
    
    d_time, d_fhr, d_flag, d_conf, d_sat = decode_fhr_telemetry_packet(pkt)
    assert d_time == timestamp
    assert pytest.approx(d_fhr, abs=0.01) == 140.2
    assert d_flag == flag
    assert d_conf is True
    assert d_sat is False

def test_calibration_packet_roundtrip():
    """Verify 10-byte calibration packet serialization, framing, and deserialization."""
    weights = [28500, -14200, 7100, -3550]
    pkt = encode_calibration_packet(weights)
    assert len(pkt) == 10
    assert pkt[0] == HEADER_CALIBRATION
    
    w0, w1, w2, w3 = decode_calibration_packet(pkt)
    assert [w0, w1, w2, w3] == weights

def test_framer_resynchronization():
    """Verify framer recovers cleanly after noise and fragmented packets."""
    framer = UARTStreamFramer()
    
    pkt1 = encode_fecg_stream_packet(1, 1000)
    pkt2 = encode_fecg_stream_packet(2, 2000)
    
    # Inject garbage bytes before pkt1, corrupt pkt1, follow with valid pkt2
    corrupt_stream = b"\x00\xFF\xAA\x01\x02" + pkt1[:4] + b"\xDE\xAD\xBE\xEF" + pkt2
    
    decoded = framer.feed(corrupt_stream)
    
    # Framer should skip corrupted data and successfully extract pkt2
    assert len(decoded) == 1
    p_type, p_payload = decoded[0]
    assert p_type == "FECG_STREAM"
    d_seq, d_val = decode_fecg_stream_packet(p_payload)
    assert d_seq == 2
    assert d_val == 2000
