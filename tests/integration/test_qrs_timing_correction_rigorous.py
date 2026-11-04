"""
QRS_TIMING_CORRECTION/tests/test_qrs_timing_correction_rigorous.py
─────────────────────────────────────────────────────────────────
Rigorous regression test suite for QRS timing compensation:
  1. Synthetic pulse timestamp alignment (true peak vs detected timestamp).
  2. Compensation monotonicity and exact step behavior.
  3. No double compensation invariant (res.raw_peaks - res.peaks == 12).
  4. Boundary behavior: beginning of recording (t < 12 clamping at 0) and end of recording.
  5. Strict 1-to-1 beat matching and duplicate rejection.
  6. Empirical benchmark record validation: 12-sample bias near 0 vs 18-sample severe early bias.
"""

import sys
from pathlib import Path
import numpy as np
import pytest
from scipy import signal
import wfdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import CausalConfig, CalibrationBank, preprocess_causal, det_sos, moving_sum_trailing
from src.bit_accurate_reference_model_final import run_bit_accurate_pipeline_final
from tools.pre_fpga_corrected.reconcile_qrs_metrics import match_beats_strict_pairs

FS = 250

def make_synthetic_ecg_train(duration_s=12.0, rate_bpm=140.0, fs=250):
    """Generate realistic synthetic ECG train with known R-peaks throughout."""
    n_samples = int(duration_s * fs)
    period = int(round(60.0 * fs / rate_bpm))  # 107 samples @ 140 bpm
    # Place peaks starting from period // 2 to cover warmup (0 to 512) and evaluation (512 to end)
    peaks = np.arange(period // 2, n_samples - period // 2, period)
    x = np.zeros(n_samples)
    width = 3.5
    for p in peaks:
        idx = np.arange(max(0, p - 15), min(n_samples, p + 16))
        # Realistic QRS pulse
        pulse = 1.2 * np.exp(-0.5 * ((idx - p) / width) ** 2)
        s_wave = -0.25 * np.exp(-0.5 * ((idx - (p + 3)) / (width * 1.2)) ** 2)
        x[idx] += pulse + s_wave
    np.random.seed(42)
    noise = np.random.normal(0, 0.015, n_samples)
    x += noise
    return x, peaks

def test_synthetic_qrs_timestamp_alignment():
    """Verify that with 12-sample compensation, detected peak aligns with true pulse within +/- 1 sample."""
    x_1ch, true_peaks = make_synthetic_ecg_train(duration_s=10.0, rate_bpm=140.0)
    x_4ch = np.column_stack([x_1ch, x_1ch * 0.8, x_1ch * 0.5, x_1ch * 0.2])
    x_q = np.clip(np.round(x_4ch * 4096.0), -32768, 32767).astype(np.int16)
    w_q = np.array([32767, 0, 0, 0], dtype=np.int16)  # Lead 0 passthrough
    
    # Run with 12-sample compensation
    res_12 = run_bit_accurate_pipeline_final(x_q, w_q, mwi_len=30, refractory=50, latency=12)
    det_12 = res_12.peaks
    
    # Run with 18-sample compensation
    res_18 = run_bit_accurate_pipeline_final(x_q, w_q, mwi_len=30, refractory=50, latency=18)
    det_18 = res_18.peaks
    
    # Only evaluate peaks after warmup (sample 512)
    eval_ref = true_peaks[true_peaks > 550]
    
    tp_12, fp_12, fn_12, pairs_12 = match_beats_strict_pairs(eval_ref, det_12, fs=FS, tol_ms=50.0)
    tp_18, fp_18, fn_18, pairs_18 = match_beats_strict_pairs(eval_ref, det_18, fs=FS, tol_ms=50.0)
    
    assert tp_12 >= len(eval_ref) - 1, f"Expected almost all true peaks matched, got {tp_12}/{len(eval_ref)}"
    
    errors_12 = [p[2] for p in pairs_12]
    mean_bias_12 = np.mean(errors_12)
    
    # 12-sample compensation achieves near-zero alignment (|bias| <= 2 samples on synthetic pulses)
    assert abs(mean_bias_12) <= 2.0, f"12-sample compensation bias too high: {mean_bias_12}"
    for e in errors_12:
        assert abs(e) <= 2, f"Individual peak error {e} exceeds 2 samples"
        
    # Check that 18-sample compensation exhibits severe negative bias (at least 4 to 6 samples early)
    errors_18 = [p[2] for p in pairs_18]
    mean_bias_18 = np.mean(errors_18)
    assert mean_bias_18 <= -4.0, f"18-sample compensation should be severely early, got: {mean_bias_18}"

def test_no_double_compensation_invariant():
    """Verify that latency is subtracted exactly once and raw_peaks retains uncompensated positions."""
    x_1ch, true_peaks = make_synthetic_ecg_train(duration_s=8.0, rate_bpm=140.0)
    x_4ch = np.column_stack([x_1ch, x_1ch, x_1ch, x_1ch])
    x_q = np.clip(np.round(x_4ch * 4096.0), -32768, 32767).astype(np.int16)
    w_q = np.array([16384, 16384, 0, 0], dtype=np.int16)
    
    lat = 12
    res = run_bit_accurate_pipeline_final(x_q, w_q, mwi_len=30, refractory=50, latency=lat)
    
    raw = res.raw_peaks
    comp = res.peaks
    assert len(raw) == len(comp)
    assert len(raw) > 5
    
    # Invariant: raw[i] - comp[i] == lat (or comp[i] == 0 if raw[i] < lat)
    for r, c in zip(raw, comp):
        if r >= lat:
            assert r - c == lat, f"Double or incorrect compensation: raw={r}, comp={c}, expected diff={lat}"
        else:
            assert c == 0

def test_boundary_behavior_beginning_and_end():
    """Verify clamping at 0 for early peaks and robust operation at recording termination."""
    n_samples = 800
    x_1ch, _ = make_synthetic_ecg_train(duration_s=4.0, rate_bpm=140.0)
    x_4ch = np.column_stack([x_1ch] * 4)
    x_q = np.clip(np.round(x_4ch * 4096.0), -32768, 32767).astype(np.int16)
    w_q = np.array([32767, 0, 0, 0], dtype=np.int16)
    
    res = run_bit_accurate_pipeline_final(x_q, w_q, mwi_len=30, refractory=50, latency=12)
    comp = res.peaks
    
    # Timestamps must all be non-negative integers
    assert np.all(comp >= 0)
    assert np.all(comp < len(x_1ch))
    assert np.all(np.diff(comp) > 0)  # Monotonicity

def test_strict_one_to_one_matching():
    """Verify that 1-to-1 matching prevents double counting and adheres to invariants."""
    ref = np.array([100, 200, 300])
    # Multiple detections around sample 200
    det = np.array([101, 198, 202, 205, 300])
    
    tp, fp, fn, pairs = match_beats_strict_pairs(ref, det, fs=FS, tol_ms=50.0)
    
    assert tp == 3
    assert fp == 2
    assert fn == 0
    assert tp + fp == len(det)
    assert tp + fn == len(ref)
    assert len(pairs) == 3
    
    # Check that sample 200 was matched to exactly one detection (nearest: 198, diff = -2)
    matched_ref_200 = [p for p in pairs if p[0] == 200]
    assert len(matched_ref_200) == 1
    assert matched_ref_200[0][1] == 198
    assert matched_ref_200[0][2] == -2

def test_empirical_record_timing_verification():
    """Verify timing performance on physiological record sub01_snr12dB_l1_c0."""
    data_path = Path("data/FECGSD/DESTINATION/sub01/snr12dB/sub01_snr12dB_l1_c0")
    if not (data_path.parent / (data_path.name + "_fecg1.hea")).exists():
        pytest.skip("Dataset not available on disk")
        
    fecg = wfdb.rdrecord(str(data_path) + "_fecg1").p_signal[:, [27, 26, 28, 25]]
    mecg = wfdb.rdrecord(str(data_path) + "_mecg").p_signal[:, [27, 26, 28, 25]]
    n1 = wfdb.rdrecord(str(data_path) + "_noise1").p_signal[:, [27, 26, 28, 25]]
    n2 = wfdb.rdrecord(str(data_path) + "_noise2").p_signal[:, [27, 26, 28, 25]]
    mix = fecg + mecg + n1 + n2
    ref_qrs = np.sort(wfdb.rdann(str(data_path) + "_fecg1", "qrs").sample)
    
    cfg_c = CausalConfig(det_low_hz=12.0, det_high_hz=35.0, mwi_len=30, refractory=50)
    bank = CalibrationBank(mix, cfg_c, cal_seconds=10)
    j, _ = bank.select("autocorr")
    w_float = bank.weights(j)
    
    x_q = np.clip(np.round(mix * 4096.0), -32768, 32767).astype(np.int16)
    w_q = np.clip(np.round(w_float * 32768.0), -32768, 32767).astype(np.int16)
    
    # 12-sample compensation
    res_12 = run_bit_accurate_pipeline_final(x_q, w_q, mwi_len=30, refractory=50, latency=12)
    tp_12, fp_12, fn_12, pairs_12 = match_beats_strict_pairs(ref_qrs, res_12.peaks, fs=FS, tol_ms=50.0)
    errs_12 = [p[2] for p in pairs_12]
    mean_bias_12 = np.mean(errs_12)
    pct_2_12 = np.sum(np.abs(errs_12) <= 2) / len(errs_12) * 100.0
    
    # 18-sample compensation
    res_18 = run_bit_accurate_pipeline_final(x_q, w_q, mwi_len=30, refractory=50, latency=18)
    tp_18, fp_18, fn_18, pairs_18 = match_beats_strict_pairs(ref_qrs, res_18.peaks, fs=FS, tol_ms=50.0)
    errs_18 = [p[2] for p in pairs_18]
    mean_bias_18 = np.mean(errs_18)
    pct_2_18 = np.sum(np.abs(errs_18) <= 2) / len(errs_18) * 100.0
    
    # 12-sample compensation must achieve zero-centered bias and high concordance
    assert abs(mean_bias_12) < 0.5, f"12-sample mean bias too high: {mean_bias_12}"
    assert pct_2_12 > 75.0, f"12-sample concordance <= 2 samples too low: {pct_2_12}%"
    
    # 18-sample compensation must show severe negative bias and low concordance
    assert mean_bias_18 < -5.0, f"18-sample bias should be negative, got: {mean_bias_18}"
    assert pct_2_18 < 20.0, f"18-sample concordance should be low due to early shift, got: {pct_2_18}%"
