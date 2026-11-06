"""
src/fecg/telemetry/uart_protocol.py
────────────────────────────────────────────────────────────────────────────
Bit-Accurate UART Communication Protocol Implementation.

Target Platform: RealDigital Boolean Board (AMD/Xilinx Spartan-7 XC7S50-1CSGA324C)
Interface: FTDI USB-UART Bridge (FT2232H) @ 921,600 Baud (Bringup: 115,200 Baud, 8-N-1)

Locked Packet Structures:
  1. Downlink Sample Packet (11 Bytes, Header 0xA5):
     - Byte 0: 0xA5
     - Byte 1: Sequence Counter (8-bit unsigned rolling counter)
     - Bytes 2-3: CH0 sample (Signed 16-bit Q12, Big-Endian)
     - Bytes 4-5: CH1 sample (Signed 16-bit Q12, Big-Endian)
     - Bytes 6-7: CH2 sample (Signed 16-bit Q12, Big-Endian)
     - Bytes 8-9: CH3 sample (Signed 16-bit Q12, Big-Endian)
     - Byte 10: CRC8-CCITT over Bytes 0-9

  2. Downlink Calibration Packet (10 Bytes, Header 0xC3):
     - Byte 0: 0xC3
     - Bytes 1-2: w0 (Signed 16-bit Q1.15, Big-Endian)
     - Bytes 3-4: w1 (Signed 16-bit Q1.15, Big-Endian)
     - Bytes 5-6: w2 (Signed 16-bit Q1.15, Big-Endian)
     - Bytes 7-8: w3 (Signed 16-bit Q1.15, Big-Endian)
     - Byte 9: CRC8-CCITT over Bytes 0-8

  3. Uplink QRS Event & FHR Telemetry Packet (8 Bytes, Header 0xAA):
     - Byte 0: 0xAA
     - Bytes 1-3: Timestamp (24-bit unsigned integer, Big-Endian, latency-compensated)
     - Bytes 4-5: FHR in units of 0.1 bpm (16-bit unsigned, Big-Endian: e.g. 1402 = 140.2 bpm)
     - Byte 6: Authoritative Status Byte:
       * bits 1:0: Classification (00: REAL, 01: FUSED, 10: HELD, 11: WARMUP)
       * bit 2: Calibration Confidence (1: Confident, 0: Uncertain/Retained)
       * bit 3: Saturation/Clipping Indicator (1: Saturated, 0: Normal)
       * bits 7:4: Reserved (0000)
     - Byte 7: CRC8-CCITT over Bytes 0-6

  4. Clean FECG Stream Packet (6 Bytes, Header 0x5A):
     - Byte 0: 0x5A
     - Byte 1: Sequence Counter (8-bit unsigned rolling counter)
     - Bytes 2-4: Clean FECG sample (Signed 24-bit, Big-Endian, scale = 2^20 LSB/mV)
     - Byte 5: CRC8-CCITT over Bytes 0-4

CRC8-CCITT Specification:
  - Polynomial: 0x07 (x^8 + x^2 + x + 1)
  - Initial Value: 0x00
  - Reflect In: False
  - Reflect Out: False
  - Final XOR: 0x00
  - Golden Standard Vector: crc8_ccitt(b"123456789") == 0xF4
"""

from typing import Tuple, Optional, Sequence, List
import struct

CRC8_POLYNOMIAL = 0x07
CRC8_INIT = 0x00

HEADER_SAMPLE        = 0xA5
HEADER_CALIBRATION   = 0xC3
HEADER_FHR_TELEMETRY = 0xAA
HEADER_FECG_STREAM   = 0x5A

FLAG_REAL_DETECTED    = 0b00
FLAG_FUSED_BEAT       = 0b01
FLAG_HELD_FHR         = 0b10
FLAG_INVALID_WARMUP   = 0b11


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


# ── 1. Downlink Sample Packet (11 Bytes) ──────────────────────────────────

def encode_sample_packet(seq: int, ch0: int, ch1: int, ch2: int, ch3: int) -> bytes:
    """
    Encode 4-channel signed 16-bit Q12 samples into an 11-byte Downlink Sample Packet.
    Format: [0xA5] [Seq# 1B] [CH0 2B] [CH1 2B] [CH2 2B] [CH3 2B] [CRC8 1B]
    """
    seq_u8 = int(seq) & 0xFF
    channels = [int(ch0), int(ch1), int(ch2), int(ch3)]
    for i, ch in enumerate(channels):
        if ch < -32768 or ch > 32767:
            raise ValueError(f"Channel CH{i} value {ch} out of signed 16-bit range [-32768, 32767]")

    payload = bytearray([HEADER_SAMPLE, seq_u8])
    for ch in channels:
        payload.extend(struct.pack(">h", ch))
    crc = crc8_ccitt(bytes(payload))
    payload.append(crc)
    return bytes(payload)


def decode_sample_packet(packet: bytes) -> Tuple[int, int, int, int, int]:
    """
    Decode and verify 11-byte Downlink Sample Packet.
    Returns: (seq, ch0, ch1, ch2, ch3)
    """
    if len(packet) != 11:
        raise ValueError(f"Sample packet length must be 11, got {len(packet)}")
    if packet[0] != HEADER_SAMPLE:
        raise ValueError(f"Invalid sample header: 0x{packet[0]:02X}")
    expected_crc = crc8_ccitt(packet[:10])
    if packet[10] != expected_crc:
        raise ValueError(f"CRC8 mismatch: expected 0x{expected_crc:02X}, got 0x{packet[10]:02X}")
    seq = packet[1]
    ch0, ch1, ch2, ch3 = struct.unpack(">hhhh", packet[2:10])
    return seq, ch0, ch1, ch2, ch3


# ── 2. Downlink Calibration Packet (10 Bytes) ────────────────────────────

def encode_calibration_packet(weights: Sequence[int]) -> bytes:
    """Encode 4 signed 16-bit Q1.15 weights into 10-byte calibration packet."""
    if len(weights) != 4:
        raise ValueError(f"Expected 4 weights, got {len(weights)}")
    payload = bytearray([HEADER_CALIBRATION])
    for w in weights:
        w_int = int(w)
        if w_int < -32768 or w_int > 32767:
            raise ValueError(f"Weight {w_int} out of signed 16-bit range [-32768, 32767]")
        payload.extend(struct.pack(">h", w_int))
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


# ── 3. Uplink QRS Event & FHR Telemetry Packet (8 Bytes) ─────────────────

def encode_fhr_telemetry_packet(
    timestamp: int,
    fhr_x10: int,
    flag_2bit: int,
    confident: bool = True,
    saturated: bool = False
) -> bytes:
    """
    Encode QRS event & FHR telemetry into 8-byte packet.
    timestamp: 24-bit unsigned sample index (0 to 16,777,215)
    fhr_x10: 16-bit unsigned in 0.1 bpm (e.g. 1402 = 140.2 bpm)
    flag_2bit: 00: Real, 01: Fused, 10: Held, 11: Warmup
    confident: Calibration confidence bit (bit 2)
    saturated: Stage saturation indicator (bit 3)
    """
    if timestamp < 0 or timestamp > 0xFFFFFF:
        raise ValueError(f"Timestamp {timestamp} out of 24-bit unsigned range")
    if fhr_x10 < 0 or fhr_x10 > 0xFFFF:
        raise ValueError(f"FHR {fhr_x10} out of 16-bit unsigned range")

    status_byte = (
        (flag_2bit & 0x03)
        | ((1 if confident else 0) << 2)
        | ((1 if saturated else 0) << 3)
    )

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


def decode_fhr_telemetry_packet(packet: bytes) -> Tuple[int, float, int, bool, bool]:
    """
    Decode and verify 8-byte FHR telemetry packet.
    Returns: (timestamp, fhr_bpm, flag_2bit, is_confident, is_saturated)
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
    is_saturated = bool((status_byte >> 3) & 0x01)

    return timestamp, fhr_bpm, flag_2bit, is_confident, is_saturated


# ── 4. Clean FECG Stream Packet (6 Bytes) ────────────────────────────────

def encode_fecg_stream_packet(seq: int, sample_s24: int) -> bytes:
    """
    Encode streaming clean FECG sample into 6-byte packet.
    seq: 8-bit rolling sequence counter
    sample_s24: Signed 24-bit integer sample
    """
    sample_int = int(sample_s24)
    # Pack signed 24-bit
    s24_unsigned = sample_int & 0xFFFFFF
    payload = bytearray([
        HEADER_FECG_STREAM,
        seq & 0xFF,
        (s24_unsigned >> 16) & 0xFF,
        (s24_unsigned >> 8) & 0xFF,
        s24_unsigned & 0xFF
    ])
    crc = crc8_ccitt(bytes(payload))
    payload.append(crc)
    return bytes(payload)


def decode_fecg_stream_packet(packet: bytes) -> Tuple[int, int]:
    """
    Decode and verify 6-byte streaming FECG packet.
    Returns: (seq, sample_s24)
    """
    if len(packet) != 6:
        raise ValueError(f"FECG stream packet length must be 6, got {len(packet)}")
    if packet[0] != HEADER_FECG_STREAM:
        raise ValueError(f"Invalid stream header: 0x{packet[0]:02X}")
    expected_crc = crc8_ccitt(packet[:5])
    if packet[5] != expected_crc:
        raise ValueError(f"CRC8 mismatch: expected 0x{expected_crc:02X}, got 0x{packet[5]:02X}")
    seq = packet[1]
    raw_s24 = (packet[2] << 16) | (packet[3] << 8) | packet[4]
    # Sign extend 24-bit to signed python int
    if raw_s24 & 0x800000:
        sample_s24 = raw_s24 - 0x1000000
    else:
        sample_s24 = raw_s24
    return seq, sample_s24


# ── 5. Streaming Framing and Resynchronization Engine ─────────────────────

class UARTStreamFramer:
    """
    Robust byte-by-byte streaming framer that parses incoming byte streams,
    detects sync headers, verifies CRC8 checksums, and safely resynchronizes
    after arbitrary data corruption or dropped bytes.
    """
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> List[Tuple[str, bytes]]:
        """Feed incoming bytes and return list of verified (packet_type, packet_bytes)."""
        self.buffer.extend(data)
        packets = []

        while len(self.buffer) >= 6:  # Minimum packet length is 6 bytes (FECG)
            # Find next valid header candidate
            header_idx = -1
            packet_type = None
            packet_len = 0

            for i, b in enumerate(self.buffer):
                if b == HEADER_SAMPLE and len(self.buffer) - i >= 11:
                    header_idx = i
                    packet_type = "SAMPLE"
                    packet_len = 11
                    break
                elif b == HEADER_CALIBRATION and len(self.buffer) - i >= 10:
                    header_idx = i
                    packet_type = "CALIBRATION"
                    packet_len = 10
                    break
                elif b == HEADER_FHR_TELEMETRY and len(self.buffer) - i >= 8:
                    header_idx = i
                    packet_type = "TELEMETRY"
                    packet_len = 8
                    break
                elif b == HEADER_FECG_STREAM and len(self.buffer) - i >= 6:
                    header_idx = i
                    packet_type = "FECG_STREAM"
                    packet_len = 6
                    break

            if header_idx == -1:
                # No complete packet header found; discard garbage up to last possible candidate
                if len(self.buffer) > 11:
                    self.buffer = self.buffer[-10:]
                break

            # Discard any corrupted leading bytes before header
            if header_idx > 0:
                self.buffer = self.buffer[header_idx:]

            candidate = bytes(self.buffer[:packet_len])
            # Verify CRC
            expected_crc = crc8_ccitt(candidate[:-1])
            if candidate[-1] == expected_crc:
                packets.append((packet_type, candidate))
                self.buffer = self.buffer[packet_len:]
            else:
                # CRC failed; false header match or corrupted packet: slide by 1 byte to resynchronize
                self.buffer = self.buffer[1:]

        return packets
