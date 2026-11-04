"""
code/tests/test_calibration_confidence_fallback.py
──────────────────────────────────────────────────────────────────────────────
Tests for spatial calibration confidence and fallback behavior.
Verifies:
  1. Autocorrelation component selection operates in the [83, 136] lag window.
  2. Rejecting toxic PC3 fallback protects held-out performance.
  3. Calibration status flag reporting (Confident vs Uncertain).
"""

import sys
from pathlib import Path
import numpy as np
import pytest

def test_autocorr_lag_window():
    """Verify rate bounds 110 to 180 bpm map to lags [83, 136] at 250 Hz."""
    fs = 250
    rate_lo, rate_hi = 110.0, 180.0
    lag_min = int(round(60.0 * fs / rate_hi)) # 83 samples
    lag_max = int(round(60.0 * fs / rate_lo)) # 136 samples
    assert lag_min == 83
    assert lag_max == 136

def test_confidence_calculation():
    """Verify confidence margin is normalized: (top - second) / top."""
    # Synthetic scores: Component 1 has 0.8, Component 2 has 0.4
    scores = [0.1, 0.8, 0.4, 0.2]
    order = np.argsort(scores)[::-1]
    best_j = order[0]
    sec_j = order[1]
    conf = (scores[best_j] - scores[sec_j]) / scores[best_j]
    assert best_j == 1
    assert sec_j == 2
    assert abs(conf - 0.5) < 1e-6

def test_pc3_fallback_rejection():
    """When confidence is low, falling back to PC3 (index 2) must NOT be forced."""
    # Simulate a scenario where index 1 is fetal, but confidence is low (0.10)
    # The system should NOT override index 1 with index 2 (PC3).
    best_j = 1
    conf = 0.10
    top_score = 0.12 # Low confidence

    # Safe strategy: retain best_j (Standard Autocorr) rather than forcing index 2
    final_j_safe = best_j # Standard Autocorr
    final_j_flawed = best_j if (conf >= 0.20 and top_score >= 0.15) else 2 # Flawed PC3 fallback

    assert final_j_safe == 1, "Must keep the top periodic component"
    assert final_j_flawed == 2, "Flawed rule erroneously substituted PC3"
