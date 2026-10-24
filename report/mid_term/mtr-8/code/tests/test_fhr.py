"""
tests/test_fhr.py
──────────────────────────────────────────────────────────────────────────────
Tests for src/fhr.py — FHR calculation and comparison.

Owner    : Vivek
Run from the code/ directory:
    python -m pytest tests/test_fhr.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.fhr import compute_fhr, compare_fhr, FHR_MIN_BPM, FHR_MAX_BPM

FS = 250


class TestComputeFHR:
    """Known synthetic intervals → expected BPM values."""

    def test_constant_rr_140bpm(self):
        # 140 BPM → RR = 60/140 ≈ 0.4286 s → 107 samples at 250 Hz
        rr_samples = int(round(60 / 140 * FS))
        peaks = np.arange(0, 5 * rr_samples, rr_samples)
        result = compute_fhr(peaks, fs=FS)
        assert len(result.fhr_bpm) == len(peaks) - 1
        assert np.all(np.isfinite(result.fhr_bpm[result.valid_mask]))
        np.testing.assert_allclose(
            result.fhr_bpm[result.valid_mask], 140.0, atol=0.5
        )

    def test_empty_peaks_returns_empty(self):
        result = compute_fhr(np.array([]), fs=FS)
        assert len(result.fhr_bpm) == 0
        assert len(result.time_s) == 0

    def test_single_peak_returns_empty(self):
        result = compute_fhr(np.array([100]), fs=FS)
        assert len(result.fhr_bpm) == 0

    def test_implausible_interval_flagged_as_nan(self):
        # Very long interval → FHR well below FHR_MIN_BPM
        peaks = np.array([0, int(FS * 100)])   # 100 s between beats → 0.6 BPM
        result = compute_fhr(peaks, fs=FS)
        assert result.n_implausible == 1
        assert np.isnan(result.fhr_bpm[0])
        assert not result.valid_mask[0]

    def test_mean_fhr_excludes_implausible(self):
        # Mix of valid and implausible
        valid_rr  = int(round(60 / 140 * FS))
        bad_rr    = int(FS * 100)              # implausible
        peaks = np.array([0, valid_rr, valid_rr + bad_rr])
        result = compute_fhr(peaks, fs=FS)
        assert result.n_implausible == 1
        # Mean should only include the valid beat
        assert abs(result.mean_fhr_bpm - 140.0) < 1.0

    def test_fhr_physiological_range_accepted(self):
        for bpm in [60, 100, 140, 180, 220]:
            rr = int(round(60 / bpm * FS))
            peaks = np.arange(0, 10 * rr, rr)
            result = compute_fhr(peaks, fs=FS)
            assert np.all(result.valid_mask), (
                f"All beats at {bpm} BPM should be valid"
            )

    def test_time_axis_is_midpoint(self):
        rr = 100  # samples
        peaks = np.array([0, rr, 2 * rr])
        result = compute_fhr(peaks, fs=FS)
        expected_t = np.array([rr / 2, rr + rr / 2]) / FS
        np.testing.assert_allclose(result.time_s, expected_t)


class TestCompareFHR:
    def test_perfect_match_gives_zero_error(self):
        rr = int(round(60 / 140 * FS))
        peaks = np.arange(0, 20 * rr, rr)
        from src.fhr import FHRResult, compute_fhr
        est = compute_fhr(peaks, fs=FS)
        cmp = compare_fhr(est, peaks, fs=FS)
        assert cmp.mean_abs_error_bpm == pytest.approx(0.0, abs=0.01)

    def test_insufficient_beats_returns_nan(self):
        est_result = compute_fhr(np.array([]), fs=FS)
        cmp = compare_fhr(est_result, np.array([100]), fs=FS)
        assert np.isnan(cmp.mean_abs_error_bpm)
