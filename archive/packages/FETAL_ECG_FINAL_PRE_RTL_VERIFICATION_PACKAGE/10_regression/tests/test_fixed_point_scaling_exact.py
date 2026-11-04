"""
10_regression/tests/test_fixed_point_scaling_exact.py
────────────────────────────────────────────────────────────────────────────
Unit tests for exact fixed-point scaling, SQNR derivation, and conversion equations.
"""

import numpy as np
import pytest

from bit_accurate_reference_model_final import (
    PHYSICAL_SCALE_Q20, ADC_SCALE_LSB_PER_MV, WEIGHT_SCALE, PROJ_SHIFT,
    rshift_round_nearest_even, sat
)

def test_mathematical_scaling_derivation():
    """Verify that (ADC_SCALE * WEIGHT_SCALE) >>> 7 equals exactly 2^20."""
    adc_scale = ADC_SCALE_LSB_PER_MV  # 4096.0 (2^12)
    w_scale = WEIGHT_SCALE            # 32768.0 (2^15)
    
    # Combined product scale: 2^12 * 2^15 = 2^27
    prod_scale = adc_scale * w_scale
    assert prod_scale == 2**27
    
    # Right-shift by 7 bits: 2^27 / 2^7 = 2^20 = 1048576
    proj_scale = prod_scale / (1 << PROJ_SHIFT)
    assert proj_scale == PHYSICAL_SCALE_Q20
    assert proj_scale == 1048576.0

def test_physical_millivolt_reconstruction():
    """Verify exact round-trip reconstruction from millivolts to integer and back."""
    v_mv = 1.25  # 1.25 mV test biopotential
    w_float = 0.5 # Unit-norm weight component
    
    # Quantize input and weight
    x_q = int(round(v_mv * ADC_SCALE_LSB_PER_MV)) # 1.25 * 4096 = 5120
    w_q = int(round(w_float * WEIGHT_SCALE))       # 0.5 * 32768 = 16384
    
    # Hardware MAC
    acc = x_q * w_q # 5120 * 16384 = 83,886,080
    proj_q = rshift_round_nearest_even(acc, PROJ_SHIFT) # 83886080 >> 7 = 655360
    
    # Physical reconstruction using locked formula
    v_recon = proj_q / PHYSICAL_SCALE_Q20 # 655360 / 1048576 = 0.625 mV
    expected_mv = v_mv * w_float          # 1.25 * 0.5 = 0.625 mV
    
    assert abs(v_recon - expected_mv) < 1e-9

def test_prior_scaling_bug_mathematical_proof():
    """
    Formally prove that the prior formula (res.proj / 2^23) * (32768 * 2^7 / 4096)
    produces exactly 128x the signal amplitude, causing -42.08 dB SQNR.
    """
    proj_q = 1048576 # Corresponds to exactly 1.0 mV in Q20
    
    # Prior flawed formula
    flawed_mv = (proj_q / (1 << 23)) * (32768.0 * (1 << 7) / 4096.0)
    # Correct formula
    correct_mv = proj_q / PHYSICAL_SCALE_Q20
    
    assert correct_mv == 1.0
    assert flawed_mv == 128.0  # Exactly 128 times too large!
    
    # Compute resulting SQNR of 128x scaling error
    # SQNR = 10 * log10(x^2 / (x - 128x)^2) = 10 * log10(1 / 127^2)
    flawed_sqnr = 10.0 * np.log10(1.0 / (127.0**2))
    assert round(flawed_sqnr, 2) == -42.08
