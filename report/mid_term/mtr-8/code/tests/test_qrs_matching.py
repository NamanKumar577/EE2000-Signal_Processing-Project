"""
tests/test_qrs_matching.py
──────────────────────────────────────────────────────────────────────────────
Tests for beat-matching logic in src/evaluation.py.

Owner    : Vivek
Run from the code/ directory:
    python -m pytest tests/test_qrs_matching.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation import match_beats, compute_beat_metrics


FS = 250
TOLERANCE_MS = 50.0
TOL_SAMPLES = int(round(TOLERANCE_MS * FS / 1000.0))   # 12 samples at 250 Hz


class TestMatchBeats:
    """Hand-checkable examples (Section 13 requirement)."""

    def test_perfect_match(self):
        ref = np.array([100, 200, 300])
        det = np.array([100, 200, 300])
        tp, fp, fn = match_beats(ref, det, FS, TOLERANCE_MS)
        assert tp == 3
        assert fp == 0
        assert fn == 0

    def test_all_missed(self):
        ref = np.array([100, 200, 300])
        det = np.array([])
        tp, fp, fn = match_beats(ref, det, FS, TOLERANCE_MS)
        assert tp == 0
        assert fp == 0
        assert fn == 3

    def test_all_false_positives(self):
        ref = np.array([])
        det = np.array([100, 200, 300])
        tp, fp, fn = match_beats(ref, det, FS, TOLERANCE_MS)
        assert tp == 0
        assert fp == 3
        assert fn == 0

    def test_within_tolerance(self):
        ref = np.array([100])
        det = np.array([100 + TOL_SAMPLES])   # exactly at boundary → should match
        tp, fp, fn = match_beats(ref, det, FS, TOLERANCE_MS)
        assert tp == 1
        assert fp == 0
        assert fn == 0

    def test_just_outside_tolerance(self):
        ref = np.array([100])
        det = np.array([100 + TOL_SAMPLES + 1])   # 1 sample outside
        tp, fp, fn = match_beats(ref, det, FS, TOLERANCE_MS)
        assert tp == 0
        assert fp == 1
        assert fn == 1

    def test_one_extra_detection(self):
        # ref: [100, 300], det: [100, 200, 300]  → 200 is FP
        ref = np.array([100, 300])
        det = np.array([100, 200, 300])
        tp, fp, fn = match_beats(ref, det, FS, TOLERANCE_MS)
        assert tp == 2
        assert fp == 1
        assert fn == 0

    def test_no_double_counting(self):
        # Two detections near one reference beat — only one TP allowed
        ref = np.array([100])
        det = np.array([99, 101])
        tp, fp, fn = match_beats(ref, det, FS, TOLERANCE_MS)
        assert tp == 1
        assert fp == 1
        assert fn == 0


class TestComputeBeatMetrics:
    def test_perfect_scores(self):
        ref = np.array([100, 200, 300])
        det = np.array([100, 200, 300])
        m = compute_beat_metrics(ref, det, FS, TOLERANCE_MS)
        assert m.sensitivity == pytest.approx(1.0)
        assert m.ppv == pytest.approx(1.0)
        assert m.f1 == pytest.approx(1.0)

    def test_sensitivity_undefined_when_no_ref_beats(self):
        ref = np.array([])
        det = np.array([100])
        m = compute_beat_metrics(ref, det, FS, TOLERANCE_MS)
        assert m.sensitivity is None
        assert m.f1 is None

    def test_ppv_undefined_when_no_det_beats(self):
        ref = np.array([100])
        det = np.array([])
        m = compute_beat_metrics(ref, det, FS, TOLERANCE_MS)
        assert m.ppv is None

    def test_mixed_performance(self):
        # ref: 5 beats, det: 4 matching + 1 FP + 1 FN
        ref = np.array([100, 200, 300, 400, 500])
        det = np.array([100, 200, 300, 400, 600])  # 500 missed, 600 is FP
        m = compute_beat_metrics(ref, det, FS, TOLERANCE_MS)
        assert m.tp == 4
        assert m.fp == 1
        assert m.fn == 1
        assert m.sensitivity == pytest.approx(4 / 5)
        assert m.ppv == pytest.approx(4 / 5)
