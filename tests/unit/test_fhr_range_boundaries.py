"""
code/tests/test_fhr_range_boundaries.py
──────────────────────────────────────────────────────────────────────────────
Tests for FHR and RR range boundary consistency (Priority 5).
Verifies:
  1. 50 samples corresponds to 300 bpm @ 250 Hz.
  2. 60 samples corresponds to 250 bpm @ 250 Hz.
  3. 300 samples corresponds to 50 bpm @ 250 Hz.
  4. FHR LUT covers RR from 50 to 300 (251 entries).
  5. Refractory period of 50 samples permits 300 bpm firing.
"""

import sys
from pathlib import Path
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.bit_accurate_reference_model_corrected import (
    REFRACTORY_SAMPLES, RR_MIN, RR_MAX, FHR_MIN_BPM, FHR_MAX_BPM
)

def test_mathematical_range_mapping():
    """Verify conversion at 250 Hz: FHR = 15000 / RR."""
    fs = 250
    # 300 bpm -> 50 samples
    rr_300 = int(round(60.0 * fs / 300.0))
    assert rr_300 == 50

    # 250 bpm -> 60 samples
    rr_250 = int(round(60.0 * fs / 250.0))
    assert rr_250 == 60

    # 50 bpm -> 300 samples
    rr_50 = int(round(60.0 * fs / 50.0))
    assert rr_50 == 300

def test_constants_consistency():
    """Verify code constants match reconciled specifications."""
    assert REFRACTORY_SAMPLES == 50, "Refractory period must be 50 samples (200 ms = 300 bpm)"
    assert RR_MIN == 50, "RR_MIN must be 50 samples to support up to 300 bpm"
    assert RR_MAX == 300, "RR_MAX must be 300 samples to support down to 50 bpm"
    assert FHR_MIN_BPM == 50
    assert FHR_MAX_BPM == 300

def test_lut_dimensions():
    """LUT must cover RR 50 to 300 inclusive (251 entries)."""
    fhr_lut = [round(150000.0 / r) for r in range(RR_MIN, RR_MAX + 1)]
    assert len(fhr_lut) == 251
    assert fhr_lut[0] == 3000, "RR=50 maps to 300.0 bpm (3000)"
    assert fhr_lut[-1] == 500, "RR=300 maps to 50.0 bpm (500)"
