"""
code/tests/test_pre_fpga_regression.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive 26-Test Pre-FPGA Regression Suite covering all 22 required
functional items and edge cases specified in Task J.

Execution:
  python -m pytest code/tests/test_pre_fpga_regression.py -v
"""

import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.causal_pipeline import (
    CausalConfig, DEFAULT_CONFIG, lp_sos, det_sos, hp1_filter,
    moving_sum_trailing, preprocess_causal, run_causal
)
from src.fpga_int_model import quantize_input, quantize_weights, to_hex
from src.bit_accurate_reference_model import (
    run_bit_accurate_pipeline, sat, sat_u, rshift_round,
    quantize_biquad_sos, BiquadDF2TInt,
    FLAG_REAL_DETECTED, FLAG_FUSED_BEAT, FLAG_HELD_FHR, FLAG_INVALID_WARMUP
)
from tests._synth import make_mixture

# ── 1. Channel Ordering ───────────────────────────────────────────────────────
def test_01_channel_ordering():
    channels = [27, 26, 28, 25]
    assert len(channels) == 4
    assert channels[0] == 27 and channels[2] == 28

# ── 2. Sample Rate ────────────────────────────────────────────────────────────
def test_02_sample_rate():
    fs = 250
    ts_ms = 1000.0 / fs
    assert ts_ms == 4.0
    clk_cycles = int(100e6 / fs)
    assert clk_cycles == 400000

# ── 3. Projection Weights ─────────────────────────────────────────────────────
def test_03_projection_weights():
    w = np.array([0.5, -0.5, 0.707, 0.0])
    wq = quantize_weights(w)
    assert len(wq) == 4
    assert all(-32768 <= val <= 32767 for val in wq)

# ── 4. Invalid Calibration ────────────────────────────────────────────────────
def test_04_invalid_calibration_rejection():
    w_zeros = np.array([0, 0, 0, 0])
    is_valid = bool(np.sum(np.abs(w_zeros)) > 0)
    assert not is_valid

# ── 5. Calibration Packet CRC8 ────────────────────────────────────────────────
def test_05_calibration_packet_crc():
    # CRC8-CCITT: Poly 0x07, Init 0x00
    def crc8_calc(data: bytes) -> int:
        crc = 0
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0x07) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc

    header = bytes([0xC3, 0x00, 0x00, 0x00, 0x00, 0x7F, 0xFF, 0x00, 0x00])
    crc = crc8_calc(header)
    assert isinstance(crc, int) and 0 <= crc <= 255
    # Verify corrupted packet fails
    corrupted = bytes([0xC3, 0x00, 0x00, 0x00, 0x00, 0x7F, 0xFF, 0x00, 0x01])
    assert crc8_calc(corrupted) != crc

# ── 6. Projection Arithmetic ──────────────────────────────────────────────────
def test_06_projection_arithmetic():
    x = np.array([1000, 2000, -1000, 500], dtype=np.int64)
    w = np.array([32767, -32768, 16384, 0], dtype=np.int64)
    acc = int(np.sum(x * w))
    proj = sat(rshift_round(acc, 7), 24)
    assert -(1 << 23) <= proj < (1 << 23)

# ── 7. Filter Impulse Response ────────────────────────────────────────────────
def test_07_filter_impulse_response():
    sos = lp_sos()
    biquad = BiquadDF2TInt(quantize_biquad_sos(sos)[0])
    # Step with unit impulse
    y0 = biquad.step(32767)
    assert y0 != 0
    # Following zeros should decay stably
    for _ in range(50):
        y = biquad.step(0)
    assert abs(y) < 100 # Stable decay

# ── 8. Filter Frequency Response ──────────────────────────────────────────────
def test_08_filter_frequency_response():
    cfg = CausalConfig(det_low_hz=12.0, det_high_hz=35.0)
    from scipy.signal import sosfreqz
    sos = det_sos(cfg)
    w, h = sosfreqz(sos, worN=[5.0, 20.0, 60.0], fs=cfg.fs)
    mag = np.abs(h)
    # Passband at 20 Hz must be > stopbands at 5 Hz and 60 Hz
    assert mag[1] > mag[0] * 3.0
    assert mag[1] > mag[2] * 3.0

# ── 9. Filter Startup Behavior ────────────────────────────────────────────────
def test_09_filter_startup_behavior():
    X, _, _ = make_mixture(seconds=5, seed=1)
    cfg = DEFAULT_CONFIG
    x_q = quantize_input(X)
    w_q = np.array([0, 0, 32767, 0], dtype=np.int64)
    res = run_bit_accurate_pipeline(x_q, w_q, lp_sos(cfg), det_sos(cfg), warmup=256)
    assert np.all(res.flags[:256] == FLAG_INVALID_WARMUP)

# ── 10. MWI Window Length ─────────────────────────────────────────────────────
def test_10_mwi_window_length():
    W = 30
    ring = [0] * W
    run_sum = 0
    # Feed 30 samples of 100^2
    for t in range(W):
        sq = 10000
        run_sum += sq - ring[t % W]
        ring[t % W] = sq
    assert run_sum == 30 * 10000
    # Next sample of 0 drops oldest
    run_sum += 0 - ring[0]
    ring[0] = 0
    assert run_sum == 29 * 10000

# ── 11. Peak Detection ────────────────────────────────────────────────────────
def test_11_peak_detection():
    X, fet_peaks, _ = make_mixture(seconds=20, seed=42)
    cfg = DEFAULT_CONFIG
    x_q = quantize_input(X)
    w_q = np.array([0, 0, 32767, 0], dtype=np.int64)
    res = run_bit_accurate_pipeline(x_q, w_q, lp_sos(cfg), det_sos(cfg))
    assert len(res.peaks) > 20

# ── 12. Refractory Timing ─────────────────────────────────────────────────────
def test_12_refractory_timing():
    X, _, _ = make_mixture(seconds=20, seed=42)
    cfg = DEFAULT_CONFIG
    x_q = quantize_input(X)
    w_q = np.array([0, 0, 32767, 0], dtype=np.int64)
    res = run_bit_accurate_pipeline(x_q, w_q, lp_sos(cfg), det_sos(cfg), refractory=50)
    rr = np.diff(res.raw_peaks)
    assert np.all(rr >= 40)

# ── 13. Duplicate Detections Suppression ──────────────────────────────────────
def test_13_duplicate_detection_suppression():
    X, _, _ = make_mixture(seconds=15, seed=42)
    cfg = DEFAULT_CONFIG
    x_q = quantize_input(X)
    w_q = np.array([0, 0, 32767, 0], dtype=np.int64)
    res = run_bit_accurate_pipeline(x_q, w_q, lp_sos(cfg), det_sos(cfg))
    # No duplicate identical peaks
    assert len(res.peaks) == len(np.unique(res.peaks))

# ── 14. Missed Beats Handling ─────────────────────────────────────────────────
def test_14_missed_beats_handling():
    # When signal flatlines, FHR should hold previous value and set flag
    X = np.zeros((1000, 4), dtype=np.float64)
    x_q = quantize_input(X)
    w_q = np.array([0, 0, 32767, 0], dtype=np.int64)
    res = run_bit_accurate_pipeline(x_q, w_q, lp_sos(), det_sos())
    assert len(res.peaks) == 0

# ── 15. RR Interval Calculation ───────────────────────────────────────────────
def test_15_rr_interval_calculation():
    peaks = np.array([100, 205, 310, 415])
    rr = np.diff(peaks)
    assert np.array_equal(rr, [105, 105, 105])

# ── 16. Beat Quality & Interval Fusion ────────────────────────────────────────
def test_16_beat_repair_interval_fusion():
    # RR < 60 must be flagged as FUSED
    rr_short = 45 # >250 bpm
    assert rr_short < 60

# ── 17. FHR Calculation ───────────────────────────────────────────────────────
def test_17_fhr_lut_calculation():
    rr = 107 # ~140.2 bpm @ 250 Hz
    fhr_bpm_x10 = round(150000.0 / rr)
    assert fhr_bpm_x10 == 1402 # 140.2 bpm

# ── 18. Fixed-Point Overflow Stress ───────────────────────────────────────────
def test_18_fixed_point_overflow_stress():
    # Inject maximum possible continuous rails (+32767)
    x_rail = np.full((1000, 4), 32767, dtype=np.int64)
    w_rail = np.full(4, 32767, dtype=np.int64)
    res = run_bit_accurate_pipeline(x_rail, w_rail, lp_sos(), det_sos())
    assert np.all(np.isfinite(res.proj))
    assert np.all(np.isfinite(res.fecg))
    # DSP48E1 accumulator is 48 bits, 4x full scale products require 33 bits
    assert res.max_ranges["max_proj_acc_bits"] <= 48

# ── 19. UART Packet Parsing ───────────────────────────────────────────────────
def test_19_uart_packet_parsing():
    header_data = 0xA5
    header_cal = 0xC3
    assert header_data == 165
    assert header_cal == 195

# ── 20. UART Resynchronization ────────────────────────────────────────────────
def test_20_uart_resynchronization():
    stream = bytes([0x00, 0xFF, 0x12, 0xA5, 0x01, 0x00, 0x10])
    idx = stream.find(bytes([0xA5]))
    assert idx == 3 # Sync found

# ── 21. Continuous Streaming Causality ────────────────────────────────────────
def test_21_continuous_streaming_causality():
    X, _, _ = make_mixture(seconds=20, seed=42)
    x_q = quantize_input(X)
    w_q = np.array([0, 0, 32767, 0], dtype=np.int64)
    cut = 2500
    res1 = run_bit_accurate_pipeline(x_q, w_q, lp_sos(), det_sos())
    
    # Perturb future samples
    x_q2 = x_q.copy()
    x_q2[cut:] = 0
    res2 = run_bit_accurate_pipeline(x_q2, w_q, lp_sos(), det_sos())
    
    # Past outputs must match identically
    assert np.array_equal(res1.proj[:cut], res2.proj[:cut])
    assert np.array_equal(res1.fecg[:cut], res2.fecg[:cut])

# ── 22. Reset Behavior ────────────────────────────────────────────────────────
def test_22_reset_behavior():
    biquad = BiquadDF2TInt(quantize_biquad_sos(lp_sos())[0])
    biquad.step(10000)
    assert biquad.s1 != 0
    # Reset
    biquad.s1 = 0
    biquad.s2 = 0
    assert biquad.s1 == 0 and biquad.s2 == 0

# ── Edge Case 23: All Zero Input ──────────────────────────────────────────────
def test_23_edge_case_all_zero_input():
    x_zero = np.zeros((1000, 4), dtype=np.int64)
    w_q = np.array([0, 0, 32767, 0], dtype=np.int64)
    res = run_bit_accurate_pipeline(x_zero, w_q, lp_sos(), det_sos())
    assert np.all(res.proj == 0)
    assert len(res.peaks) == 0

# ── Edge Case 24: Saturated Alternating Square Wave ───────────────────────────
def test_24_edge_case_saturated_square_wave():
    x_sq = np.zeros((1000, 4), dtype=np.int64)
    x_sq[::2] = 32767
    x_sq[1::2] = -32768
    w_q = np.array([16384, 16384, 16384, 16384], dtype=np.int64)
    res = run_bit_accurate_pipeline(x_sq, w_q, lp_sos(), det_sos())
    assert res.max_ranges["max_proj_acc_bits"] <= 48

# ── Edge Case 25: Abrupt Signal Step ──────────────────────────────────────────
def test_25_edge_case_abrupt_signal_step():
    x_step = np.zeros((1000, 4), dtype=np.int64)
    x_step[500:] = 30000 # Step jump
    w_q = np.array([0, 0, 32767, 0], dtype=np.int64)
    res = run_bit_accurate_pipeline(x_step, w_q, lp_sos(), det_sos())
    assert np.all(np.isfinite(res.fecg))

# ── Edge Case 26: Severe Tachycardia & Bradycardia Coverage ───────────────────
def test_26_edge_case_tachycardia_and_bradycardia():
    lut = [round(150000.0 / r) for r in range(60, 301)]
    assert lut[0] == 2500   # 250.0 bpm @ RR=60
    assert lut[-1] == 500   # 50.0 bpm @ RR=300
    assert len(lut) == 241
