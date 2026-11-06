"""
src/fecg/telemetry/__init__.py
"""

from .uart_protocol import (
    crc8_ccitt,
    encode_sample_packet,
    decode_sample_packet,
    encode_calibration_packet,
    decode_calibration_packet,
    encode_fhr_telemetry_packet,
    decode_fhr_telemetry_packet,
    encode_fecg_stream_packet,
    decode_fecg_stream_packet,
    UARTStreamFramer,
    HEADER_SAMPLE,
    HEADER_CALIBRATION,
    HEADER_FHR_TELEMETRY,
    HEADER_FECG_STREAM,
    FLAG_REAL_DETECTED,
    FLAG_FUSED_BEAT,
    FLAG_HELD_FHR,
    FLAG_INVALID_WARMUP,
)

__all__ = [
    "crc8_ccitt",
    "encode_sample_packet",
    "decode_sample_packet",
    "encode_calibration_packet",
    "decode_calibration_packet",
    "encode_fhr_telemetry_packet",
    "decode_fhr_telemetry_packet",
    "encode_fecg_stream_packet",
    "decode_fecg_stream_packet",
    "UARTStreamFramer",
    "HEADER_SAMPLE",
    "HEADER_CALIBRATION",
    "HEADER_FHR_TELEMETRY",
    "HEADER_FECG_STREAM",
    "FLAG_REAL_DETECTED",
    "FLAG_FUSED_BEAT",
    "FLAG_HELD_FHR",
    "FLAG_INVALID_WARMUP",
]
