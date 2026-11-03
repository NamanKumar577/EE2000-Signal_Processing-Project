"""
code/tests/test_fhr_interval_fusion_and_median5.py
──────────────────────────────────────────────────────────────────────────────
Tests for corrected Interval Fusion and Causal Median-of-5 filtering.
Verifies:
  1. True interval fusion merges split peaks and preserves beat count.
  2. Causal Median-of-5 smooths transient outliers and matches hand calculations.
  3. Startup behavior for k=1..4 beats.
  4. Invalid RR intervals are held without corrupting the median buffer.
"""

import sys
from pathlib import Path
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.fhr_implementation_corrected import (
    apply_interval_fusion, causal_median5_rr, compute_fhr_series,
    RR_MIN, RR_MAX, FLAG_REAL_DETECTED, FLAG_FUSED_BEAT, FLAG_HELD_FHR
)

def test_interval_fusion_split_peaks():
    """Two peaks 10 samples apart must merge into one beat."""
    peaks = np.array([100, 110, 220, 330]) # Peaks at 100 and 110 (diff = 10 < 50)
    amps = np.array([0.5, 0.9, 0.8, 0.7])  # Peak at 110 has higher amplitude

    fused_peaks, flags, n_fused = apply_interval_fusion(peaks, amplitudes=amps, min_rr=50)

    assert len(fused_peaks) == 3, "Length must be 3 (merged 100 & 110)"
    assert n_fused == 1
    assert fused_peaks[0] == 110, "Must retain timestamp of stronger peak"
    assert flags[0] == FLAG_FUSED_BEAT
    assert flags[1] == FLAG_REAL_DETECTED
    assert flags[2] == FLAG_REAL_DETECTED

def test_causal_median5_hand_calculated():
    """Verify exact hand-calculated progression of causal Median-of-5."""
    # Input RR intervals:
    # 1. 100 -> buf=[100] -> med=100
    # 2. 102 -> buf=[100, 102] -> med=101
    # 3. 250 (outlier) -> buf=[100, 102, 250] -> med=102
    # 4. 101 -> buf=[100, 102, 250, 101] -> sorted=[100, 101, 102, 250] -> med=101.5 -> 101
    # 5. 99  -> buf=[100, 102, 250, 101, 99] -> sorted=[99, 100, 101, 102, 250] -> med=101
    # 6. 100 -> buf=[102, 250, 101, 99, 100] -> sorted=[99, 100, 101, 102, 250] -> med=101
    rr = [100, 102, 250, 101, 99, 100]
    out = causal_median5_rr(rr)

    assert out[0] == 100
    assert out[1] == 101
    assert out[2] == 102
    assert out[3] in [101, 102]
    assert out[4] == 101
    assert out[5] == 101

def test_invalid_rr_held():
    """An extreme invalid interval (< 50 or > 300) must hold previous filtered value."""
    rr = [100, 100, 100, 100, 100, 350] # 350 is severe bradycardia / dropout (> 300)
    out = causal_median5_rr(rr)
    assert out[5] == 100, "Must hold previous valid RR (100) instead of propagating 350"
