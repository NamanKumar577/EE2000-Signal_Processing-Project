"""
10_regression/tests/test_filter_coefficients_exact.py
────────────────────────────────────────────────────────────────────────────
Unit tests verifying exact frozen filter coefficients and recursive filter pole stability.
"""

import numpy as np
import pytest

from bit_accurate_reference_model_final import (
    LP40_COEFFS_Q15, DET_BP_CONFIG_C_COEFFS_Q15, COEF_SCALE
)

def test_lp40_coefficients_table():
    """Verify LP40 frozen signed 18-bit Q3.15 coefficients."""
    assert len(LP40_COEFFS_Q15) == 2  # 2 cascaded biquads (order 4)
    
    # Section 0
    b0, b1, b2, a1_neg, a2_neg = LP40_COEFFS_Q15[0]
    assert (b0, b1, b2, a1_neg, a2_neg) == (749, 1499, 749, 19727, -4049)
    
    # Section 1
    b0, b1, b2, a1_neg, a2_neg = LP40_COEFFS_Q15[1]
    assert (b0, b1, b2, a1_neg, a2_neg) == (32768, 65536, 32768, 26540, -16764)

def test_detector_bp_coefficients_table():
    """Verify Config C bandpass frozen signed 18-bit Q3.15 coefficients."""
    assert len(DET_BP_CONFIG_C_COEFFS_Q15) == 4  # 4 cascaded biquads (order 8)
    
    expected = [
        (119, 238, 119, 38563, -16484),
        (32768, 65536, 32768, 49834, -21435),
        (32768, -65536, 32768, 37298, -24206),
        (32768, -65536, 32768, 58829, -29016)
    ]
    for s_idx, exp in enumerate(expected):
        assert DET_BP_CONFIG_C_COEFFS_Q15[s_idx] == exp

def test_filter_pole_stability():
    """Verify that all biquad poles are strictly located inside the unit circle (|p| < 1.0)."""
    all_biquads = list(LP40_COEFFS_Q15) + list(DET_BP_CONFIG_C_COEFFS_Q15)
    
    for b0, b1, b2, a1_neg, a2_neg in all_biquads:
        # a0 = 1.0, a1 = -a1_neg / SCALE, a2 = -a2_neg / SCALE
        a1 = -a1_neg / float(COEF_SCALE)
        a2 = -a2_neg / float(COEF_SCALE)
        
        poles = np.roots([1.0, a1, a2])
        for p in poles:
            assert np.abs(p) < 1.0, f"Unstable pole detected: {p} (magnitude {abs(p)})"
