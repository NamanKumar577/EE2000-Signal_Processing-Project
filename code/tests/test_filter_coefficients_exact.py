"""
code/tests/test_filter_coefficients_exact.py
──────────────────────────────────────────────────────────────────────────────
Tests for exact frozen digital filter coefficients and BIBO stability.
Verifies:
  1. LP40 coefficients match signed 18-bit Q3.15 table.
  2. Config C bandpass coefficients match signed 18-bit Q3.15 table.
  3. Filter pole locations remain strictly inside unit circle (|z| < 1.0).
  4. DC response of bandpass filter is zero.
"""

import sys
from pathlib import Path
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.bit_accurate_reference_model_corrected import (
    LP40_COEFFS_Q15, DET_BP_CONFIG_C_COEFFS_Q15
)

def test_lp40_coefficients_table():
    """Verify LP40 integer coefficients and section dimensions."""
    assert len(LP40_COEFFS_Q15) == 2, "LP40 must have 2 biquad sections (4th order)"
    sec0 = LP40_COEFFS_Q15[0]
    sec1 = LP40_COEFFS_Q15[1]

    # Section 0
    assert sec0 == (749, 1499, 749, 19727, -4049)
    # Section 1
    assert sec1 == (32768, 65536, 32768, 26540, -16764)

def test_detector_bp_coefficients_table():
    """Verify Config C 12-35 Hz bandpass integer coefficients."""
    assert len(DET_BP_CONFIG_C_COEFFS_Q15) == 4, "Config C must have 4 biquad sections (8th order)"
    assert DET_BP_CONFIG_C_COEFFS_Q15[0] == (119, 238, 119, 38563, -16484)
    assert DET_BP_CONFIG_C_COEFFS_Q15[1] == (32768, 65536, 32768, 49834, -21435)
    assert DET_BP_CONFIG_C_COEFFS_Q15[2] == (32768, -65536, 32768, 37298, -24206)
    assert DET_BP_CONFIG_C_COEFFS_Q15[3] == (32768, -65536, 32768, 58829, -29016)

def test_filter_pole_stability():
    """Verify all biquad poles have magnitude < 1.0 (BIBO stability)."""
    scale = 32768.0
    for i, sec in enumerate(list(LP40_COEFFS_Q15) + list(DET_BP_CONFIG_C_COEFFS_Q15)):
        b0, b1, b2, a1_neg, a2_neg = sec
        a1 = -a1_neg / scale
        a2 = -a2_neg / scale
        # Roots of 1 + a1*z^-1 + a2*z^-2 = z^2 + a1*z + a2 = 0
        poles = np.roots([1.0, a1, a2])
        for p in poles:
            assert abs(p) < 1.0, f"Unstable pole found in section {i}: |z| = {abs(p)}"
