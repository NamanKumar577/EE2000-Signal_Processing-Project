#!/usr/bin/env python3
"""
fpga_implementation/uart_host/fecg_uart_client.py
──────────────────────────────────────────────────────────────────────────────
High-Reliability Bidirectional Host-FPGA UART Streaming Engine & Telemetry Driver
for Fetal ECG (FECG) Real-Time Processing on AMD/Xilinx Spartan-7 XC7S50.

Physical Interface:
  - FTDI FT2232H USB-to-UART Bridge on RealDigital Boolean Board (COM5)
  - Production Baud Rate: 921,600 Baud (Bringup Fallback: 115,200 Baud)
  - Framing: 8-N-1 (8 Data bits, No parity, 1 Stop bit)
  - Endianness: Big-Endian (MSB First) for all multi-byte words
  - Error Detection: CRC8-CCITT (polynomial 0x07, init 0x00, test vector '123456789' -> 0xF4)

Bidirectional Packet Protocols:
  1. Downlink Sample Packet (Header 0xA5, 11 Bytes @ 250 Hz):
     [0xA5] [Seq# 1B] [CH0_H, CH0_L 2B] [CH1_H, CH1_L 2B] [CH2_H, CH2_L 2B] [CH3_H, CH3_L 2B] [CRC8 1B]
     Transmits 4-channel signed 16-bit Q12 samples at 250 Hz.
     
  2. Downlink Calibration Weights Packet (Header 0xC3, 10 Bytes on-demand):
     [0xC3] [W0_H, W0_L 2B] [W1_H, W1_L 2B] [W2_H, W2_L 2B] [W3_H, W3_L 2B] [CRC8 1B]
     Transmits 4 signed 16-bit Q1.15 spatial weights.
     
  3. Uplink Clean FECG Stream Packet (Header 0x5A, 6 Bytes @ 250 Hz):
     [0x5A] [Seq# 1B] [FECG_H, FECG_M, FECG_L 3B signed 24-bit Q20] [CRC8 1B]
     Returns clean maternal-subtracted FECG waveform (physical scale 2^20 LSB/mV).
     
  4. Uplink QRS Event & FHR Telemetry Packet (Header 0xAA, 8 Bytes on R-peak):
     [0xAA] [Time_H, Time_M, Time_L 3B unsigned 24b] [FHR_H, FHR_L 2B unsigned 16b in 0.1 bpm] [Status 1B] [CRC8 1B]
     Returns latency-compensated R-peak timing, FHR, beat classification & diagnostic flags.
     
  5. Uplink Diagnostic Packet (Header 0xEE, 8 Bytes on anomaly):
     [0xEE] [ErrCode 1B] [MaxSt_H, MaxSt_L 2B] [Thr_H, Thr_L 2B] [Rsvd 1B] [CRC8 1B]
     Reports hardware anomaly (CRC error, sequence gap, saturation, FIFO overflow).

Features:
  - Robust byte-by-byte streaming framer that resynchronizes immediately without
    dropping subsequent valid frames after noise, line glitches, or dropped bytes.
  - Zero-copy packet encoding/decoding using Python struct and bytearray.
  - Rate-limited real-time streaming generator matching the exact 250 Hz (4.0 ms) sampling period.
  - Optional background thread listener with decoupled queue for non-blocking telemetry ingestion.
  - Built-in comprehensive self-test suite and offline mock serial simulation mode.
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import time
import struct
import queue
import threading
from dataclasses import dataclass
from typing import Tuple, Optional, Sequence, List, Dict, Any, Callable, Union

try:
    import serial
    import serial.tools.list_ports as list_ports
    HAS_PYSERIAL = True
except ImportError:
    serial = None
    list_ports = None
    HAS_PYSERIAL = False

# ==============================================================================
# Protocol Headers & Lengths
# ==============================================================================

HEADER_SAMPLE        = 0xA5  # Downlink 4-ch ADC samples (11 bytes)
HEADER_CALIBRATION   = 0xC3  # Downlink PCA weights (10 bytes)
HEADER_CALIB_RESTART = 0xC4  # Downlink weights + detector warm-up restart (10 bytes)
HEADER_FECG_STREAM   = 0x5A  # Uplink clean FECG waveform (6 bytes)
HEADER_FHR_TELEMETRY = 0xAA  # Uplink QRS/FHR event (8 bytes)
HEADER_DIAGNOSTIC    = 0xEE  # Uplink hardware anomaly (8 bytes)

LEN_SAMPLE           = 11
LEN_CALIBRATION      = 10
LEN_FECG_STREAM      = 6
LEN_FHR_TELEMETRY    = 8
LEN_DIAGNOSTIC       = 8

PACKET_LENGTH_MAP = {
    HEADER_SAMPLE: LEN_SAMPLE,
    HEADER_CALIBRATION: LEN_CALIBRATION,
    HEADER_FECG_STREAM: LEN_FECG_STREAM,
    HEADER_FHR_TELEMETRY: LEN_FHR_TELEMETRY,
    HEADER_DIAGNOSTIC: LEN_DIAGNOSTIC,
}

# Beat Classification Flags (bits 1:0 of Status Byte in 0xAA)
FLAG_REAL_DETECTED  = 0b00
FLAG_FUSED_BEAT     = 0b01
FLAG_HELD_FHR       = 0b10
FLAG_INVALID_WARMUP = 0b11

FLAG_NAMES = {
    FLAG_REAL_DETECTED: "REAL",
    FLAG_FUSED_BEAT: "FUSED",
    FLAG_HELD_FHR: "HELD",
    FLAG_INVALID_WARMUP: "WARMUP"
}

# Hardware Diagnostic Error Codes (Byte 1 in 0xEE)
ERR_DOWNLINK_CRC_FAIL   = 0x01
ERR_DOWNLINK_SEQ_GAP    = 0x02
ERR_BIQUAD_SATURATION   = 0x03
ERR_UART_FIFO_OVERFLOW  = 0x04

ERROR_NAMES = {
    ERR_DOWNLINK_CRC_FAIL: "CRC_FAIL",
    ERR_DOWNLINK_SEQ_GAP: "SEQ_GAP",
    ERR_BIQUAD_SATURATION: "BIQUAD_SATURATION",
    ERR_UART_FIFO_OVERFLOW: "FIFO_OVERFLOW"
}

# Scale Constants
SCALE_Q12 = 4096.0          # 12 fractional bits: 4096 LSB/mV
SCALE_Q15 = 32768.0         # 15 fractional bits: 32768 LSB/unit
SCALE_Q20 = 1048576.0       # 20 fractional bits: 1048576 LSB/mV

# CRC8 Configuration
CRC8_POLYNOMIAL = 0x07
CRC8_INIT = 0x00


# ==============================================================================
# Bit-Accurate CRC8-CCITT Checksum Engine
# ==============================================================================

def crc8_ccitt(data: Union[bytes, bytearray]) -> int:
    """
    Compute bit-accurate CRC-8-CCITT checksum over bytes.
    Standard: ITU-T I.432.1
    Polynomial: x^8 + x^2 + x + 1 (0x07)
    Initial value: 0x00, Final XOR: 0x00, Reflect In/Out: False.
    Golden vector: b"123456789" -> 0xF4.
    """
    crc = CRC8_INIT
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ CRC8_POLYNOMIAL) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


# ==============================================================================
# Structured Telemetry Data Models
# ==============================================================================

@dataclass(frozen=True)
class DownlinkSample:
    seq: int
    ch0: int
    ch1: int
    ch2: int
    ch3: int
    raw_bytes: bytes

    @property
    def ch0_mv(self) -> float:
        return self.ch0 / SCALE_Q12

    @property
    def ch1_mv(self) -> float:
        return self.ch1 / SCALE_Q12

    @property
    def ch2_mv(self) -> float:
        return self.ch2 / SCALE_Q12

    @property
    def ch3_mv(self) -> float:
        return self.ch3 / SCALE_Q12


@dataclass(frozen=True)
class CalibrationWeights:
    w0: int
    w1: int
    w2: int
    w3: int
    raw_bytes: bytes

    @property
    def w0_float(self) -> float:
        return self.w0 / SCALE_Q15

    @property
    def w1_float(self) -> float:
        return self.w1 / SCALE_Q15

    @property
    def w2_float(self) -> float:
        return self.w2 / SCALE_Q15

    @property
    def w3_float(self) -> float:
        return self.w3 / SCALE_Q15


@dataclass(frozen=True)
class CleanFECGSample:
    seq: int
    sample_s24: int
    fecg_mv: float
    raw_bytes: bytes


@dataclass(frozen=True)
class FHRBeatEvent:
    timestamp: int
    fhr_bpm: float
    flag: int
    classification: str
    confident: bool
    saturated: bool
    raw_bytes: bytes


@dataclass(frozen=True)
class DiagnosticEvent:
    error_code: int
    error_name: str
    max_state: int
    threshold: int
    raw_bytes: bytes


# ==============================================================================
# Packet Encoding Functions
# ==============================================================================

def encode_sample_packet(seq: int, ch0: int, ch1: int, ch2: int, ch3: int) -> bytes:
    """
    Encode 4-channel signed 16-bit Q12 samples into an 11-byte Downlink Sample Packet.
    Format: [0xA5] [Seq# 1B] [CH0 2B] [CH1 2B] [CH2 2B] [CH3 2B] [CRC8 1B]
    All channel values are Big-Endian signed 16-bit integers (-32768 to 32767).
    """
    seq_u8 = int(seq) & 0xFF
    c0 = int(ch0)
    c1 = int(ch1)
    c2 = int(ch2)
    c3 = int(ch3)

    for name, val in [("CH0", c0), ("CH1", c1), ("CH2", c2), ("CH3", c3)]:
        if val < -32768 or val > 32767:
            raise ValueError(f"{name} value {val} out of signed 16-bit range [-32768, 32767]")

    payload = bytearray(10)
    payload[0] = HEADER_SAMPLE
    payload[1] = seq_u8
    struct.pack_into(">hhhh", payload, 2, c0, c1, c2, c3)
    crc = crc8_ccitt(payload)
    payload.append(crc)
    return bytes(payload)


def decode_sample_packet(packet: bytes) -> DownlinkSample:
    """Decode and verify an 11-byte Downlink Sample Packet."""
    if len(packet) != LEN_SAMPLE:
        raise ValueError(f"Sample packet length must be {LEN_SAMPLE}, got {len(packet)}")
    if packet[0] != HEADER_SAMPLE:
        raise ValueError(f"Invalid sample header: 0x{packet[0]:02X}")
    expected_crc = crc8_ccitt(packet[:10])
    if packet[10] != expected_crc:
        raise ValueError(f"CRC8 mismatch: expected 0x{expected_crc:02X}, got 0x{packet[10]:02X}")

    seq = packet[1]
    ch0, ch1, ch2, ch3 = struct.unpack_from(">hhhh", packet, 2)
    return DownlinkSample(seq=seq, ch0=ch0, ch1=ch1, ch2=ch2, ch3=ch3, raw_bytes=packet)


def encode_calibration_packet(weights: Sequence[int], restart_detector: bool = False) -> bytes:
    """
    Encode 4 signed 16-bit Q1.15 weights into a 10-byte Downlink Calibration Packet.
    Format: [0xC3] [W0 2B] [W1 2B] [W2 2B] [W3 2B] [CRC8 1B]
    restart_detector=True sends header 0xC4: same weights, and the FPGA re-runs the
    detector warm-up 128 samples later (use for the initial calibration).
    """
    if len(weights) != 4:
        raise ValueError(f"Expected 4 weights, got {len(weights)}")

    payload = bytearray(9)
    payload[0] = HEADER_CALIB_RESTART if restart_detector else HEADER_CALIBRATION
    w_ints = []
    for i, w in enumerate(weights):
        w_int = int(w)
        if w_int < -32768 or w_int > 32767:
            raise ValueError(f"Weight W{i}={w_int} out of signed 16-bit range [-32768, 32767]")
        w_ints.append(w_int)

    struct.pack_into(">hhhh", payload, 1, *w_ints)
    crc = crc8_ccitt(payload)
    payload.append(crc)
    return bytes(payload)


def decode_calibration_packet(packet: bytes) -> CalibrationWeights:
    """Decode and verify a 10-byte Downlink Calibration Packet."""
    if len(packet) != LEN_CALIBRATION:
        raise ValueError(f"Calibration packet length must be {LEN_CALIBRATION}, got {len(packet)}")
    if packet[0] != HEADER_CALIBRATION:
        raise ValueError(f"Invalid calibration header: 0x{packet[0]:02X}")
    expected_crc = crc8_ccitt(packet[:9])
    if packet[9] != expected_crc:
        raise ValueError(f"CRC8 mismatch: expected 0x{expected_crc:02X}, got 0x{packet[9]:02X}")

    w0, w1, w2, w3 = struct.unpack_from(">hhhh", packet, 1)
    return CalibrationWeights(w0=w0, w1=w1, w2=w2, w3=w3, raw_bytes=packet)


def encode_fecg_stream_packet(seq: int, sample_s24: int) -> bytes:
    """
    Encode streaming clean FECG sample into a 6-byte Uplink Clean FECG Stream Packet.
    Format: [0x5A] [Seq# 1B] [FECG_H 1B] [FECG_M 1B] [FECG_L 1B] [CRC8 1B]
    Signed 24-bit integer, Big-Endian, scale 2^20 LSB/mV.
    """
    s_int = int(sample_s24)
    if s_int < -8388608 or s_int > 8388607:
        raise ValueError(f"FECG sample {s_int} out of signed 24-bit range [-8388608, 8388607]")

    s24_u = s_int & 0xFFFFFF
    payload = bytearray([
        HEADER_FECG_STREAM,
        seq & 0xFF,
        (s24_u >> 16) & 0xFF,
        (s24_u >> 8) & 0xFF,
        s24_u & 0xFF
    ])
    crc = crc8_ccitt(payload)
    payload.append(crc)
    return bytes(payload)


def decode_fecg_stream_packet(packet: bytes) -> CleanFECGSample:
    """Decode and verify a 6-byte Uplink Clean FECG Stream Packet."""
    if len(packet) != LEN_FECG_STREAM:
        raise ValueError(f"FECG stream packet length must be {LEN_FECG_STREAM}, got {len(packet)}")
    if packet[0] != HEADER_FECG_STREAM:
        raise ValueError(f"Invalid FECG stream header: 0x{packet[0]:02X}")
    expected_crc = crc8_ccitt(packet[:5])
    if packet[5] != expected_crc:
        raise ValueError(f"CRC8 mismatch: expected 0x{expected_crc:02X}, got 0x{packet[5]:02X}")

    seq = packet[1]
    raw_s24 = (packet[2] << 16) | (packet[3] << 8) | packet[4]
    # Sign-extend 24-bit to signed Python int
    if raw_s24 & 0x800000:
        sample_s24 = raw_s24 - 0x1000000
    else:
        sample_s24 = raw_s24

    fecg_mv = sample_s24 / SCALE_Q20
    return CleanFECGSample(seq=seq, sample_s24=sample_s24, fecg_mv=fecg_mv, raw_bytes=packet)


def encode_fhr_telemetry_packet(
    timestamp: int,
    fhr_x10: int,
    flag_2bit: int,
    confident: bool = True,
    saturated: bool = False
) -> bytes:
    """
    Encode QRS event & FHR telemetry into an 8-byte Uplink Telemetry Packet.
    Format: [0xAA] [Time_H, Time_M, Time_L 3B] [FHR_H, FHR_L 2B] [Status 1B] [CRC8 1B]
    timestamp: 24-bit unsigned sample index (0 to 16,777,215)
    fhr_x10: 16-bit unsigned in 0.1 bpm (e.g. 1402 = 140.2 bpm)
    flag_2bit: 00: Real, 01: Fused, 10: Held, 11: Warmup
    """
    t_int = int(timestamp)
    if t_int < 0 or t_int > 0xFFFFFF:
        raise ValueError(f"Timestamp {t_int} out of 24-bit unsigned range [0, 16777215]")
    f_int = int(fhr_x10)
    if f_int < 0 or f_int > 0xFFFF:
        raise ValueError(f"FHR {f_int} out of 16-bit unsigned range [0, 65535]")

    status_byte = (
        (flag_2bit & 0x03)
        | ((1 if confident else 0) << 2)
        | ((1 if saturated else 0) << 3)
    )

    payload = bytearray([
        HEADER_FHR_TELEMETRY,
        (t_int >> 16) & 0xFF,
        (t_int >> 8) & 0xFF,
        t_int & 0xFF,
        (f_int >> 8) & 0xFF,
        f_int & 0xFF,
        status_byte
    ])
    crc = crc8_ccitt(payload)
    payload.append(crc)
    return bytes(payload)


def decode_fhr_telemetry_packet(packet: bytes) -> FHRBeatEvent:
    """Decode and verify an 8-byte Uplink FHR Telemetry Packet."""
    if len(packet) != LEN_FHR_TELEMETRY:
        raise ValueError(f"FHR packet length must be {LEN_FHR_TELEMETRY}, got {len(packet)}")
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
    confident = bool((status_byte >> 2) & 0x01)
    saturated = bool((status_byte >> 3) & 0x01)
    classification = FLAG_NAMES.get(flag_2bit, "UNKNOWN")

    return FHRBeatEvent(
        timestamp=timestamp,
        fhr_bpm=fhr_bpm,
        flag=flag_2bit,
        classification=classification,
        confident=confident,
        saturated=saturated,
        raw_bytes=packet
    )


def encode_diagnostic_packet(error_code: int, max_state: int = 0, threshold: int = 0) -> bytes:
    """
    Encode hardware diagnostic anomaly into an 8-byte Uplink Diagnostic Packet.
    Format: [0xEE] [ErrCode 1B] [MaxSt 2B] [Thr 2B] [Rsvd 1B] [CRC8 1B]
    """
    payload = bytearray(7)
    payload[0] = HEADER_DIAGNOSTIC
    payload[1] = error_code & 0xFF
    struct.pack_into(">hH", payload, 2, int(max_state), int(threshold) & 0xFFFF)
    payload[6] = 0x00  # Reserved
    crc = crc8_ccitt(payload)
    payload.append(crc)
    return bytes(payload)


def decode_diagnostic_packet(packet: bytes) -> DiagnosticEvent:
    """Decode and verify an 8-byte Uplink Diagnostic Packet."""
    if len(packet) != LEN_DIAGNOSTIC:
        raise ValueError(f"Diagnostic packet length must be {LEN_DIAGNOSTIC}, got {len(packet)}")
    if packet[0] != HEADER_DIAGNOSTIC:
        raise ValueError(f"Invalid diagnostic header: 0x{packet[0]:02X}")
    expected_crc = crc8_ccitt(packet[:7])
    if packet[7] != expected_crc:
        raise ValueError(f"CRC8 mismatch: expected 0x{expected_crc:02X}, got 0x{packet[7]:02X}")

    err_code = packet[1]
    err_name = ERROR_NAMES.get(err_code, f"UNKNOWN_ERR_{err_code}")
    max_state, threshold = struct.unpack_from(">hH", packet, 2)
    return DiagnosticEvent(
        error_code=err_code,
        error_name=err_name,
        max_state=max_state,
        threshold=threshold,
        raw_bytes=packet
    )


# ==============================================================================
# Robust Streaming Framer & Resynchronization Engine
# ==============================================================================

class UARTStreamFramer:
    """
    Robust byte-by-byte streaming framer that parses incoming serial byte streams,
    detects sync headers (0xA5, 0xC3, 0x5A, 0xAA, 0xEE), validates CRC8-CCITT checksums,
    and safely resynchronizes after arbitrary data corruption, line noise, or dropped bytes.

    Resynchronization Guarantee:
      If a byte is dropped or a false header occurs, the framer advances by 1 byte and
      continues searching immediately, preventing false lock or frame starvation.
    """
    def __init__(self):
        self.buffer = bytearray()
        self.total_bytes_received = 0
        self.total_bytes_dropped = 0
        self.total_packets_decoded = 0
        self.total_crc_errors = 0
        self.packet_counts: Dict[str, int] = {
            "SAMPLE": 0,
            "CALIBRATION": 0,
            "FECG_STREAM": 0,
            "TELEMETRY": 0,
            "DIAGNOSTIC": 0,
        }

    def reset(self):
        """Reset internal buffer and counters."""
        self.buffer.clear()
        self.total_bytes_received = 0
        self.total_bytes_dropped = 0
        self.total_packets_decoded = 0
        self.total_crc_errors = 0
        for k in self.packet_counts:
            self.packet_counts[k] = 0

    def feed(self, data: bytes) -> List[Tuple[str, Any, bytes]]:
        """
        Feed incoming raw bytes from UART into the framer.
        Returns a list of parsed packets: (packet_type_str, decoded_object, raw_bytes).
        """
        self.buffer.extend(data)
        self.total_bytes_received += len(data)
        decoded_results = []

        min_packet_len = min(PACKET_LENGTH_MAP.values())  # 6 bytes (FECG_STREAM)

        while len(self.buffer) >= min_packet_len:
            # Locate the first recognized header byte in buffer
            header_idx = -1
            packet_len = 0
            packet_type = None

            for i, byte_val in enumerate(self.buffer):
                if byte_val in PACKET_LENGTH_MAP:
                    header_idx = i
                    packet_len = PACKET_LENGTH_MAP[byte_val]
                    if byte_val == HEADER_SAMPLE:
                        packet_type = "SAMPLE"
                    elif byte_val == HEADER_CALIBRATION:
                        packet_type = "CALIBRATION"
                    elif byte_val == HEADER_FECG_STREAM:
                        packet_type = "FECG_STREAM"
                    elif byte_val == HEADER_FHR_TELEMETRY:
                        packet_type = "TELEMETRY"
                    elif byte_val == HEADER_DIAGNOSTIC:
                        packet_type = "DIAGNOSTIC"
                    break

            if header_idx == -1:
                # No header found anywhere in buffer; drop all bytes except trailing candidates
                dropped_cnt = len(self.buffer)
                self.total_bytes_dropped += dropped_cnt
                self.buffer.clear()
                break

            # Discard any noise / corrupted bytes preceding the detected header
            if header_idx > 0:
                self.total_bytes_dropped += header_idx
                self.buffer = self.buffer[header_idx:]

            # Check if complete packet has arrived yet
            if len(self.buffer) < packet_len:
                # Not enough bytes for full frame; wait for next feed
                break

            candidate = bytes(self.buffer[:packet_len])
            expected_crc = crc8_ccitt(candidate[:-1])

            if candidate[-1] == expected_crc:
                # CRC match! Frame is authenticated
                try:
                    if packet_type == "SAMPLE":
                        obj = decode_sample_packet(candidate)
                    elif packet_type == "CALIBRATION":
                        obj = decode_calibration_packet(candidate)
                    elif packet_type == "FECG_STREAM":
                        obj = decode_fecg_stream_packet(candidate)
                    elif packet_type == "TELEMETRY":
                        obj = decode_fhr_telemetry_packet(candidate)
                    elif packet_type == "DIAGNOSTIC":
                        obj = decode_diagnostic_packet(candidate)
                    else:
                        obj = candidate

                    decoded_results.append((packet_type, obj, candidate))
                    self.total_packets_decoded += 1
                    self.packet_counts[packet_type] += 1
                    self.buffer = self.buffer[packet_len:]
                except Exception:
                    # In case of unpacking anomaly, slide 1 byte
                    self.total_crc_errors += 1
                    self.total_bytes_dropped += 1
                    self.buffer = self.buffer[1:]
            else:
                # CRC mismatch: candidate was line noise or false sync byte
                self.total_crc_errors += 1
                self.total_bytes_dropped += 1
                # Slide by exactly 1 byte to allow recovery of overlapping true frames
                self.buffer = self.buffer[1:]

        return decoded_results


# ==============================================================================
# Host-Side FPGA UART Client Implementation
# ==============================================================================

class FECGUartClient:
    """
    High-Reliability Bidirectional UART Client for Spartan-7 FECG Processing.
    
    Supports:
      - Connection to COM5 (or parameterized port) at 115,200 baud or 921,600 baud.
      - Streaming 4-channel biopotential data packets (0xA5) with rolling sequence counter.
      - On-demand calibration weight dispatch (0xC3).
      - Continuous parsing of incoming clean FECG (0x5A) and FHR telemetry (0xAA).
      - Background listener thread with decoupled thread-safe telemetry queues.
      - Mock / Loopback serial testing mode for offline verification.
    """
    def __init__(
        self,
        port: str = "COM5",
        baud_rate: int = 115_200,
        timeout: float = 0.5,
        serial_instance: Optional[Any] = None
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.ser = serial_instance
        self.framer = UARTStreamFramer()
        self.tx_seq = 0

        # Queues for background reception
        self.fecg_queue: queue.Queue[CleanFECGSample] = queue.Queue(maxsize=10000)
        self.telemetry_queue: queue.Queue[FHRBeatEvent] = queue.Queue(maxsize=1000)
        self.diagnostic_queue: queue.Queue[DiagnosticEvent] = queue.Queue(maxsize=100)

        # Thread management
        self._listener_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        """Check if serial connection is open."""
        return self.ser is not None and getattr(self.ser, "is_open", True)

    def connect(self) -> bool:
        """Open physical serial connection with 8-N-1 framing."""
        if not HAS_PYSERIAL:
            raise RuntimeError("pyserial is required for physical COM connection.")

        if self.ser and getattr(self.ser, "is_open", False):
            return True

        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            # Flush buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.05)
            self.framer.reset()
            return True
        except Exception as e:
            self.ser = None
            raise ConnectionError(f"Failed to connect to {self.port} at {self.baud_rate} baud: {e}")

    def disconnect(self):
        """Stop background threads and close serial connection."""
        self.stop_background_listener()
        with self._lock:
            if self.ser and getattr(self.ser, "is_open", False):
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None

    close = disconnect

    def get_fecg_sample(self, timeout: float = 0.0) -> Optional[CleanFECGSample]:
        """Fetch next clean FECG sample from queue if available."""
        try:
            if timeout is None or timeout <= 0.001:
                return self.fecg_queue.get_nowait()
            return self.fecg_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_telemetry_event(self, timeout: float = 0.0) -> Optional[FHRBeatEvent]:
        """Fetch next QRS telemetry event from queue if available."""
        try:
            if timeout is None or timeout <= 0.001:
                return self.telemetry_queue.get_nowait()
            return self.telemetry_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_statistics(self):
        """Return communications link statistics."""
        class _Stats:
            def __init__(self, tx, fecg_rx, telem_rx, crc, drop):
                self.valid_packets_tx = tx
                self.fecg_stream_packets_rx = fecg_rx
                self.fhr_telemetry_packets_rx = telem_rx
                self.crc_errors = crc
                self.dropped_bytes = drop
        return _Stats(
            tx=self.tx_seq,
            fecg_rx=self.framer.packet_counts.get("FECG_STREAM", 0),
            telem_rx=self.framer.packet_counts.get("TELEMETRY", 0),
            crc=self.framer.total_crc_errors,
            drop=self.framer.total_bytes_dropped
        )

    def send_raw(self, data: bytes):
        """Transmit raw bytes over serial link."""
        if not self.ser:
            raise RuntimeError("Serial port not connected.")
        with self._lock:
            self.ser.write(data)
            if hasattr(self.ser, "flush"):
                self.ser.flush()

    send_bytes = send_raw

    def send_sample(
        self,
        ch0: int,
        ch1: int,
        ch2: int,
        ch3: int,
        seq: Optional[int] = None
    ) -> bytes:
        """
        Send a 4-channel Downlink Sample Packet (0xA5, 11 bytes).
        Automatically manages rolling sequence counter (0 to 255).
        """
        if seq is None:
            seq_val = self.tx_seq
            self.tx_seq = (self.tx_seq + 1) & 0xFF
        else:
            seq_val = seq & 0xFF

        pkt = encode_sample_packet(seq_val, ch0, ch1, ch2, ch3)
        self.send_raw(pkt)
        return pkt

    def send_calibration(self, weights: Sequence[int]) -> bytes:
        """Send a Downlink Spatial Calibration Weights Packet (0xC3, 10 bytes)."""
        pkt = encode_calibration_packet(weights)
        self.send_raw(pkt)
        return pkt

    def read_available_packets(self, max_bytes: int = 4096) -> List[Tuple[str, Any, bytes]]:
        """
        Read all currently available incoming bytes from serial and parse packets.
        Returns list of (packet_type, decoded_object, raw_bytes).
        """
        if not self.ser:
            return []

        with self._lock:
            # Check available bytes if supported
            in_waiting = getattr(self.ser, "in_waiting", 0)
            if in_waiting == 0:
                return []
            bytes_to_read = min(in_waiting, max_bytes)
            raw = self.ser.read(bytes_to_read)

        if not raw:
            return []

        packets = self.framer.feed(raw)

        # Dispatch to internal queues
        for pkt_type, obj, raw_pkt in packets:
            if pkt_type == "FECG_STREAM" and isinstance(obj, CleanFECGSample):
                try:
                    self.fecg_queue.put_nowait(obj)
                except queue.Full:
                    pass
            elif pkt_type == "TELEMETRY" and isinstance(obj, FHRBeatEvent):
                try:
                    self.telemetry_queue.put_nowait(obj)
                except queue.Full:
                    pass
            elif pkt_type == "DIAGNOSTIC" and isinstance(obj, DiagnosticEvent):
                try:
                    self.diagnostic_queue.put_nowait(obj)
                except queue.Full:
                    pass

        return packets

    # --------------------------------------------------------------------------
    # Background Listener & Streaming Service
    # --------------------------------------------------------------------------

    def start_background_listener(
        self,
        on_packet: Optional[Callable[[str, Any], None]] = None
    ):
        """Start background daemon thread continuously polling and parsing UART."""
        if self._listener_thread and self._listener_thread.is_alive():
            return

        self._stop_event.clear()

        def _worker():
            while not self._stop_event.is_set():
                try:
                    pkts = self.read_available_packets(max_bytes=512)
                    if pkts and on_packet:
                        for pkt_type, obj, _ in pkts:
                            try:
                                on_packet(pkt_type, obj)
                            except Exception:
                                pass
                    if not pkts:
                        time.sleep(0.001)  # 1 ms sleep to prevent 100% CPU on empty buffer
                except Exception:
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.01)

        self._listener_thread = threading.Thread(target=_worker, name="UARTListenerThread", daemon=True)
        self._listener_thread.start()

    def stop_background_listener(self):
        """Signal and join background listener thread."""
        self._stop_event.set()
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=1.0)
        self._listener_thread = None

    start_listener = start_background_listener
    stop_listener = stop_background_listener

    def stream_samples_generator(
        self,
        samples_iter,
        fs: float = 250.0,
        stop_check: Optional[Callable[[], bool]] = None
    ):
        """
        Stream 4-channel samples at an exact physiological sampling rate (default 250 Hz = 4.0 ms).
        Uses high-precision sleep with drift compensation.
        samples_iter yields tuples of (ch0, ch1, ch2, ch3).
        """
        interval = 1.0 / fs
        next_time = time.perf_counter()

        for chs in samples_iter:
            if stop_check and stop_check():
                break

            self.send_sample(chs[0], chs[1], chs[2], chs[3])

            next_time += interval
            sleep_dur = next_time - time.perf_counter()
            if sleep_dur > 0:
                time.sleep(sleep_dur)
            else:
                # Falling behind: catch up
                next_time = time.perf_counter()


# ==============================================================================
# Mock Serial Interface for Offline Simulation & Automated Verification
# ==============================================================================

class MockSerialPort:
    """In-memory full-duplex loopback serial port simulator."""
    def __init__(self, echo_fecg: bool = True):
        self.tx_buffer = bytearray()
        self.rx_buffer = bytearray()
        self.is_open = True
        self.echo_fecg = echo_fecg
        self.in_waiting_count = 0
        self._lock = threading.Lock()

    def write(self, data: bytes) -> int:
        with self._lock:
            self.tx_buffer.extend(data)
            # If enabled, simulate FPGA responding to sample packets (0xA5) with clean FECG (0x5A)
            if self.echo_fecg:
                framer = UARTStreamFramer()
                pkts = framer.feed(data)
                for pkt_type, obj, _ in pkts:
                    if pkt_type == "SAMPLE" and isinstance(obj, DownlinkSample):
                        # Simple synthetic clean FECG response
                        fecg_s24 = int(obj.ch0 * 256) # Scale to Q20
                        resp = encode_fecg_stream_packet(obj.seq, fecg_s24)
                        self.rx_buffer.extend(resp)
            return len(data)

    def read(self, size: int = 1) -> bytes:
        with self._lock:
            num = min(len(self.rx_buffer), size)
            res = bytes(self.rx_buffer[:num])
            del self.rx_buffer[:num]
            return res

    @property
    def in_waiting(self) -> int:
        with self._lock:
            return len(self.rx_buffer)

    def flush(self):
        pass

    def reset_input_buffer(self):
        with self._lock:
            self.rx_buffer.clear()

    def reset_output_buffer(self):
        with self._lock:
            self.tx_buffer.clear()

    def close(self):
        self.is_open = False


# ==============================================================================
# Verification Self-Test Suite
# ==============================================================================

def run_self_test() -> bool:
    """Run comprehensive offline verification suite for all packet types and framer."""
    print("=" * 70)
    print("RUNNING BIT-ACCURATE UART CLIENT PROTOCOL SELF-TEST")
    print("=" * 70)
    all_passed = True

    # 1. CRC8-CCITT Golden Vector
    crc_gold = crc8_ccitt(b"123456789")
    assert crc_gold == 0xF4, f"CRC8 test vector failed: got 0x{crc_gold:02X}, expected 0xF4"
    print(f"[PASS] CRC8-CCITT golden vector verified: b'123456789' -> 0x{crc_gold:02X}")

    # 2. Downlink Sample Packet (0xA5, 11 bytes)
    sample_pkt = encode_sample_packet(seq=42, ch0=2048, ch1=-1024, ch2=512, ch3=-256)
    assert len(sample_pkt) == 11, f"Expected 11 bytes, got {len(sample_pkt)}"
    assert sample_pkt[0] == 0xA5, "Header mismatch"
    decoded_sample = decode_sample_packet(sample_pkt)
    assert decoded_sample.seq == 42
    assert decoded_sample.ch0 == 2048 and decoded_sample.ch1 == -1024
    assert decoded_sample.ch2 == 512 and decoded_sample.ch3 == -256
    print(f"[PASS] Downlink Sample Packet (0xA5, 11B) encode/decode round trip verified")

    # 3. Downlink Calibration Packet (0xC3, 10 bytes)
    cal_pkt = encode_calibration_packet([16384, -8192, 4096, -2048])
    assert len(cal_pkt) == 10, f"Expected 10 bytes, got {len(cal_pkt)}"
    assert cal_pkt[0] == 0xC3
    decoded_cal = decode_calibration_packet(cal_pkt)
    assert (decoded_cal.w0, decoded_cal.w1, decoded_cal.w2, decoded_cal.w3) == (16384, -8192, 4096, -2048)
    print(f"[PASS] Downlink Calibration Packet (0xC3, 10B) encode/decode round trip verified")

    # 4. Uplink Clean FECG Stream Packet (0x5A, 6 bytes)
    fecg_pkt = encode_fecg_stream_packet(seq=101, sample_s24=-524288) # -0.5 mV
    assert len(fecg_pkt) == 6, f"Expected 6 bytes, got {len(fecg_pkt)}"
    assert fecg_pkt[0] == 0x5A
    decoded_fecg = decode_fecg_stream_packet(fecg_pkt)
    assert decoded_fecg.seq == 101
    assert decoded_fecg.sample_s24 == -524288
    assert abs(decoded_fecg.fecg_mv - (-0.5)) < 1e-6
    print(f"[PASS] Uplink FECG Stream Packet (0x5A, 6B) encode/decode round trip verified")

    # 5. Uplink QRS Event & FHR Telemetry Packet (0xAA, 8 bytes)
    fhr_pkt = encode_fhr_telemetry_packet(timestamp=125000, fhr_x10=1402, flag_2bit=FLAG_FUSED_BEAT, confident=True, saturated=False)
    assert len(fhr_pkt) == 8, f"Expected 8 bytes, got {len(fhr_pkt)}"
    assert fhr_pkt[0] == 0xAA
    decoded_fhr = decode_fhr_telemetry_packet(fhr_pkt)
    assert decoded_fhr.timestamp == 125000
    assert abs(decoded_fhr.fhr_bpm - 140.2) < 1e-4
    assert decoded_fhr.classification == "FUSED"
    assert decoded_fhr.confident is True
    assert decoded_fhr.saturated is False
    print(f"[PASS] Uplink FHR Telemetry Packet (0xAA, 8B) encode/decode round trip verified")

    # 6. Stream Framer Robustness & Resynchronization under Noise & Byte Drops
    framer = UARTStreamFramer()
    # Construct stream with noise prefix, valid sample packet, garbage bytes, corrupted telemetry packet, and valid FHR packet
    corrupted_fhr = bytearray(fhr_pkt)
    corrupted_fhr[3] ^= 0xFF # Corrupt payload bit

    stream_data = (
        b"\xDE\xAD\xBE\xEF\x00\xFF"  # 6 bytes random garbage
        + sample_pkt                 # 11 bytes valid sample
        + b"\xAA\xBB"                # 2 bytes partial false header
        + bytes(corrupted_fhr)       # 8 bytes corrupted FHR packet (CRC fail)
        + b"\x12\x34\x56"            # 3 bytes noise
        + fecg_pkt                   # 6 bytes valid FECG packet
        + fhr_pkt                    # 8 bytes valid FHR packet
    )

    # Feed in arbitrary small fragments to test stream chunking
    results = []
    chunk_size = 7
    for offset in range(0, len(stream_data), chunk_size):
        results.extend(framer.feed(stream_data[offset:offset+chunk_size]))

    packet_types = [p[0] for p in results]
    assert packet_types == ["SAMPLE", "FECG_STREAM", "TELEMETRY"], f"Unexpected decoded packets: {packet_types}"
    assert framer.total_crc_errors >= 1, "Expected CRC error counted"
    assert framer.total_bytes_dropped > 0, "Expected noise bytes dropped"
    print(f"[PASS] Stream Framer successfully recovered and parsed {len(results)} packets across line noise and byte corruption")

    # 7. Mock Full-Duplex Client Test
    mock_port = MockSerialPort(echo_fecg=True)
    client = FECGUartClient(port="MOCK", baud_rate=115200, serial_instance=mock_port)
    client.send_sample(100, 200, 300, 400)
    rx_pkts = client.read_available_packets()
    assert len(rx_pkts) == 1
    assert rx_pkts[0][0] == "FECG_STREAM"
    print(f"[PASS] Mock full-duplex client loopback transmission verified")

    print("=" * 70)
    print("ALL UART PROTOCOL & CLIENT SELF-TESTS PASSED (100% VERIFIED)")
    print("=" * 70)
    return True


# ==============================================================================
# CLI Entrypoint
# ==============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Spartan-7 FECG UART Client & Telemetry Driver")
    parser.add_argument("--self-test", action="store_true", help="Run offline bit-accurate protocol test suite")
    parser.add_argument("--port", type=str, default="COM5", help="Serial port device (default: COM5)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (115200 or 921600, default: 115200)")
    parser.add_argument("--list-ports", action="store_true", help="List all detected serial ports")
    args = parser.parse_args()

    if args.list_ports:
        if not HAS_PYSERIAL:
            print("pyserial is not installed.")
            sys.exit(1)
        ports = list(list_ports.comports())
        print("Detected Serial Ports:")
        for p in ports:
            print(f"  • {p.device}: {p.description}")
        return

    if args.self_test:
        success = run_self_test()
        sys.exit(0 if success else 1)

    print(f"Starting FECGUartClient on {args.port} at {args.baud} baud...")
    client = FECGUartClient(port=args.port, baud_rate=args.baud)
    try:
        client.connect()
        print(f"Connected to {args.port}. Listening for telemetry packets (Ctrl+C to quit)...")
        while True:
            pkts = client.read_available_packets()
            for ptype, pobj, _ in pkts:
                if ptype == "TELEMETRY":
                    print(f"[BEAT] Time={pobj.timestamp} | FHR={pobj.fhr_bpm:.1f} bpm | Class={pobj.classification} | Conf={pobj.confident}")
                elif ptype == "FECG_STREAM":
                    print(f"[WAVE] Seq={pobj.seq} | FECG={pobj.fecg_mv:.4f} mV")
                elif ptype == "DIAGNOSTIC":
                    print(f"[DIAG] Code={pobj.error_name} | MaxSt={pobj.max_state} | Thr={pobj.threshold}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
