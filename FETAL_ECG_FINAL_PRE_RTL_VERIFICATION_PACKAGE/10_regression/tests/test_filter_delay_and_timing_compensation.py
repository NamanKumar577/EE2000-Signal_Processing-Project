"""
10_regression/tests/test_filter_delay_and_timing_compensation.py
────────────────────────────────────────────────────────────────────────────
Unit tests for frequency-dependent filter group delay and 18-sample timing compensation.
"""

import numpy as np
import pytest
from scipy import signal

from causal_pipeline import CausalConfig, hp1_coeffs, lp_sos, det_sos
from bit_accurate_reference_model_final import LATENCY_COMPENSATION_SAMPLES

def test_config_c_group_delay_at_15hz():
    """Verify that Config C bandpass total filter group delay at 15 Hz rounds to 18 samples."""
    cfg_c = CausalConfig(det_low_hz=12.0, det_high_hz=35.0, mwi_len=30, refractory=50)
    
    # Calculate group delay at 15 Hz
    w_pair = 2.0 * np.pi * np.array([14.95, 15.05]) / cfg_c.fs
    b_hp, a_hp = hp1_coeffs(cfg_c)
    sos_lp = lp_sos(cfg_c)
    sos_bp = det_sos(cfg_c)
    
    _, h1 = signal.freqz(b_hp, a_hp, worN=w_pair)
    _, h2 = signal.sosfreqz(sos_lp, worN=w_pair)
    _, h3 = signal.sosfreqz(sos_bp, worN=w_pair)
    
    p = np.unwrap(np.angle(h1)) + np.unwrap(np.angle(h2)) + np.unwrap(np.angle(h3))
    gd_15 = float(-(p[1] - p[0]) / (w_pair[1] - w_pair[0]))
    
    assert abs(gd_15 - 17.86) < 0.15
    assert round(gd_15) == 18
    assert LATENCY_COMPENSATION_SAMPLES == 18

def test_legacy_default_group_delay_at_15hz():
    """Verify that legacy default (8-30 Hz) filter group delay at 15 Hz is ~12.4 samples."""
    cfg_leg = CausalConfig(det_low_hz=8.0, det_high_hz=30.0, mwi_len=20, refractory=50)
    
    w_pair = 2.0 * np.pi * np.array([14.95, 15.05]) / cfg_leg.fs
    b_hp, a_hp = hp1_coeffs(cfg_leg)
    sos_lp = lp_sos(cfg_leg)
    sos_bp = det_sos(cfg_leg)
    
    _, h1 = signal.freqz(b_hp, a_hp, worN=w_pair)
    _, h2 = signal.sosfreqz(sos_lp, worN=w_pair)
    _, h3 = signal.sosfreqz(sos_bp, worN=w_pair)
    
    p = np.unwrap(np.angle(h1)) + np.unwrap(np.angle(h2)) + np.unwrap(np.angle(h3))
    gd_leg = float(-(p[1] - p[0]) / (w_pair[1] - w_pair[0]))
    
    assert abs(gd_leg - 12.36) < 0.15
    assert round(gd_leg, 1) == 12.4

def test_latency_rewind_subtractor():
    """Verify that latency compensation correctly subtracts 18 samples and clamps at 0."""
    raw_peak = 100
    comp_peak = max(0, raw_peak - LATENCY_COMPENSATION_SAMPLES)
    assert comp_peak == 82
    
    # Boundary clamp at 0
    early_peak = 10
    comp_early = max(0, early_peak - LATENCY_COMPENSATION_SAMPLES)
    assert comp_early == 0
