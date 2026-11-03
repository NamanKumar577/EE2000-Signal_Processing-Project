"""
Test End-to-End Bit-Accurate Pipeline on Synthetic Multi-Channel ECG
===================================================================
Verifies:
1. Complete closed-loop execution of the bit-accurate hardware reference model.
2. Zero overflow or clipping across all 15 stages during normal operation.
3. Separation of fetal QRS complexes from dominant maternal ECG and baseline wander.
4. Downstream latency-compensated peak detection and causal FHR tracking.
5. Invariant checking: timestamps are strictly increasing, FHR within physiological bounds.
"""

import numpy as np
import pytest
from bit_accurate_reference_model_final import (
    run_bit_accurate_pipeline_final,
    ADC_SCALE_LSB_PER_MV,
    BitAccurateFinalResult
)

def generate_synthetic_4ch_recording(duration_s=10.0, fs=250):
    """
    Generate synthetic 4-channel abdominal recording:
    - Maternal heart rate: 75 bpm (RR = 200 samples)
    - Fetal heart rate: 140 bpm (RR = 107 samples)
    - Baseline wander: 0.2 Hz sine wave
    - Additive Gaussian noise
    """
    n_samples = int(duration_s * fs)
    t = np.arange(n_samples) / fs
    
    # Baseline wander
    bw = 0.3 * np.sin(2 * np.pi * 0.2 * t)
    
    # Synthetic QRS shape (Gaussian pulse)
    def make_ecg_train(rate_bpm, amp_mv, width_samples=4):
        period = int(round(60.0 * fs / rate_bpm))
        peaks = np.arange(period // 2, n_samples - period // 2, period)
        signal = np.zeros(n_samples)
        for p in peaks:
            idx = np.arange(max(0, p - 3 * width_samples), min(n_samples, p + 3 * width_samples))
            pulse = amp_mv * np.exp(-0.5 * ((idx - p) / width_samples) ** 2)
            signal[idx] += pulse
        return signal, peaks

    m_ecg, m_peaks = make_ecg_train(rate_bpm=75.0, amp_mv=1.2, width_samples=6)
    f_ecg, f_peaks = make_ecg_train(rate_bpm=140.0, amp_mv=0.25, width_samples=3)

    # Lead mixing matrix (4 channels)
    # Maternal dominates ch0, ch1, ch2; Fetal is strong on ch3
    A_m = np.array([1.0, 0.8, 0.6, 0.2])
    A_f = np.array([0.1, 0.2, 0.4, 0.9])
    
    x_mv = np.zeros((n_samples, 4))
    np.random.seed(42)
    noise = np.random.normal(0, 0.02, (n_samples, 4))
    
    for c in range(4):
        x_mv[:, c] = A_m[c] * m_ecg + A_f[c] * f_ecg + bw * (0.8 + 0.1 * c) + noise[:, c]
        
    # Quantize to 16-bit Q12 counts (4096 LSB/mV)
    x_q = np.clip(np.round(x_mv * ADC_SCALE_LSB_PER_MV), -32768, 32767).astype(np.int16)
    
    # Beamforming weights tailored to cancel maternal on ch3 (ch3 - 0.2*ch0)
    # Scaled to Q1.15 (32768)
    w_ideal = np.array([-6553, 0, 0, 32767], dtype=np.int16) # -0.2*32768, 1.0*32767
    
    return x_q, w_ideal, f_peaks

def test_pipeline_synthetic_execution_and_overflows():
    """Verify bit-accurate pipeline runs without any arithmetic overflows on synthetic signal."""
    x_q, w_q, true_f_peaks = generate_synthetic_4ch_recording(duration_s=8.0, fs=250)
    
    result = run_bit_accurate_pipeline_final(x_q, w_q)
    assert isinstance(result, BitAccurateFinalResult)
    
    # Invariant: zero overflows in all stages
    acc = result.accounting
    assert acc.proj_mult_overflow == 0
    assert acc.proj_acc_overflow == 0
    assert acc.proj_sat_count == 0
    assert acc.hp_acc_overflow == 0
    assert acc.hp_sat_count == 0
    assert acc.lp_biquad_state_overflow == 0
    assert acc.lp_biquad_out_sat == 0
    assert acc.bp_biquad_state_overflow == 0
    assert acc.bp_biquad_out_sat == 0
    assert acc.det_shift_sat_count == 0
    assert acc.squaring_overflow == 0
    assert acc.mwi_acc_overflow == 0
    assert acc.threshold_overflow == 0
    assert acc.rr_overflow == 0
    assert acc.fhr_lut_overflow == 0
    assert acc.total_overflows() == 0
    assert acc.total_saturations() == 0

def test_pipeline_fetal_detection_and_fhr_tracking():
    """Verify pipeline detects fetal beats and estimates FHR around 140 bpm."""
    x_q, w_q, true_f_peaks = generate_synthetic_4ch_recording(duration_s=8.0, fs=250)
    
    result = run_bit_accurate_pipeline_final(x_q, w_q)
    
    # Peaks should be detected
    peaks = result.peaks
    assert len(peaks) > 5, f"Expected multiple fetal peak detections, got {len(peaks)}"
    
    # Timestamps should be strictly increasing
    assert np.all(np.diff(peaks) > 0), "Peak timestamps are not strictly monotonic"
    
    # FHR estimates after startup warmup (e.g. after sample 1000)
    fhr_stream = result.fhr_hold[1000:]
    valid_fhr = fhr_stream[fhr_stream > 0]
    assert len(valid_fhr) > 0
    
    # Median detected FHR should be near 140 bpm (+/- 15 bpm)
    median_fhr = np.median(valid_fhr) / 10.0  # fhr_hold is in 0.1 bpm
    assert 125.0 <= median_fhr <= 155.0, f"Detected median FHR {median_fhr} bpm out of expected range"
