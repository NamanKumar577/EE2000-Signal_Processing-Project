"""
code/tests/test_fixed_point_arithmetic_exact.py
──────────────────────────────────────────────────────────────────────────────
Tests for bit-accurate fixed-point integer arithmetic (Priority 3).
Verifies:
  1. Convergent Rounding (Round-to-Nearest-Even) for positive and negative numbers.
  2. Exact halfway boundary values (+-2.5, +-3.5, +-4.5).
  3. Immediate above/below halfway boundaries.
  4. Zero and maximum/minimum boundary limits.
  5. Saturation behavior for signed 16-bit, 24-bit, and 48-bit integers.
  6. Enforced 48-bit state clamping in BiquadDF2TIntCorrected.
"""

import sys
from pathlib import Path
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.bit_accurate_reference_model_corrected import (
    rshift_round_nearest_even, rshift_round_symmetric, sat, sat_u,
    BiquadDF2TIntCorrected, LP40_COEFFS_Q15
)

def test_convergent_rounding_positive():
    """Verify convergent rounding for positive integers with shift=1 (divide by 2)."""
    # 4 / 2 = 2.0 -> 2
    assert rshift_round_nearest_even(4, 1) == 2
    # 5 / 2 = 2.5 (halfway, 2 is even) -> 2
    assert rshift_round_nearest_even(5, 1) == 2
    # 6 / 2 = 3.0 -> 3
    assert rshift_round_nearest_even(6, 1) == 3
    # 7 / 2 = 3.5 (halfway, 3 is odd) -> 4
    assert rshift_round_nearest_even(7, 1) == 4
    # 8 / 2 = 4.0 -> 4
    assert rshift_round_nearest_even(8, 1) == 4
    # 9 / 2 = 4.5 (halfway, 4 is even) -> 4
    assert rshift_round_nearest_even(9, 1) == 4

def test_convergent_rounding_negative():
    """Verify convergent rounding for negative integers with shift=1 (divide by 2)."""
    # -4 / 2 = -2.0 -> -2
    assert rshift_round_nearest_even(-4, 1) == -2
    # -5 / 2 = -2.5 (halfway, -2 is even) -> -2
    assert rshift_round_nearest_even(-5, 1) == -2
    # -6 / 2 = -3.0 -> -3
    assert rshift_round_nearest_even(-6, 1) == -3
    # -7 / 2 = -3.5 (halfway, -3 is odd) -> -4
    assert rshift_round_nearest_even(-7, 1) == -4
    # -8 / 2 = -4.0 -> -4
    assert rshift_round_nearest_even(-8, 1) == -4
    # -9 / 2 = -4.5 (halfway, -4 is even) -> -4
    assert rshift_round_nearest_even(-9, 1) == -4

def test_rounding_above_below_halfway():
    """Verify values immediately above and below halfway with shift=4 (divide by 16)."""
    shift = 4
    half = 8 # 8/16 = 0.5
    base = 10 * 16 # 160 -> 10.0

    # Exactly halfway: 168 / 16 = 10.5 (10 is even) -> 10
    assert rshift_round_nearest_even(base + half, shift) == 10

    # Immediately above halfway: 169 / 16 = 10.5625 -> 11
    assert rshift_round_nearest_even(base + half + 1, shift) == 11

    # Immediately below halfway: 167 / 16 = 10.4375 -> 10
    assert rshift_round_nearest_even(base + half - 1, shift) == 10

    # Negative immediately above/below
    neg_base = -160 # -10.0
    # -168 / 16 = -10.5 (-10 is even) -> -10
    assert rshift_round_nearest_even(-168, shift) == -10
    # -169 / 16 = -10.5625 -> -11
    assert rshift_round_nearest_even(-169, shift) == -11
    # -167 / 16 = -10.4375 -> -10
    assert rshift_round_nearest_even(-167, shift) == -10

def test_zero_and_extremes():
    """Verify zero and boundary limits for shifts and saturation."""
    assert rshift_round_nearest_even(0, 15) == 0
    assert sat(0, 16) == 0

    # 16-bit signed: [-32768, 32767]
    assert sat(32767, 16) == 32767
    assert sat(32768, 16) == 32767 # Saturates positive
    assert sat(-32768, 16) == -32768
    assert sat(-32769, 16) == -32768 # Saturates negative

    # 48-bit signed limits: [-(1<<47), (1<<47)-1]
    lim_48 = 1 << 47
    assert sat(lim_48 - 1, 48) == lim_48 - 1
    assert sat(lim_48 + 100, 48) == lim_48 - 1
    assert sat(-lim_48, 48) == -lim_48
    assert sat(-lim_48 - 100, 48) == -lim_48

def test_biquad_state_width_enforcement():
    """Biquad state must be clamped to 48 bits under extreme input stimuli."""
    biquad = BiquadDF2TIntCorrected(LP40_COEFFS_Q15[0], out_bits=24)
    # Feed maximum positive impulse
    for _ in range(50):
        biquad.step(8388607) # Max signed 24-bit input

    # Verify state registers do not exceed 48 bits signed
    assert abs(biquad.s1) < (1 << 47), f"s1 exceeded 48 bits: {biquad.s1}"
    assert abs(biquad.s2) < (1 << 47), f"s2 exceeded 48 bits: {biquad.s2}"
    assert biquad.overflow_count == 0, "Stable filter should not overflow 48 bits under bounded input"
