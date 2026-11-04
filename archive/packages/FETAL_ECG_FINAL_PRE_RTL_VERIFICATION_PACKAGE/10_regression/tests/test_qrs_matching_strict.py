"""
Test Strict QRS 1-to-1 Beat Matching and Invariants
===================================================
Verifies:
1. Strict 1-to-1 matching: every reference beat matches at most one detection,
   and every detected beat matches at most one reference beat.
2. Invariants: TP + FP == N_det and TP + FN == N_ref under all conditions.
3. Duplicate detection handling: multiple detections for a single reference peak
   yield exactly 1 TP and remaining as FPs.
4. Out-of-tolerance peaks correctly accounted as FP and FN.
5. Edge cases: empty detections, empty references, empty both.
"""

import numpy as np
import pytest
from evaluation import match_beats, compute_beat_metrics

def test_matching_invariants_random_scenarios():
    """Verify TP + FP == len(det) and TP + FN == len(ref) across various topologies."""
    fs = 250
    tol_ms = 50.0  # +/- 12 samples
    
    scenarios = [
        # (ref, det)
        ([100, 200, 300, 400], [100, 200, 300, 400]),
        ([100, 200, 300, 400], [102, 198, 305, 395]),
        ([100, 200, 300, 400], [100, 105, 200, 300, 305, 400]),  # Duplicates
        ([100, 200, 300, 400], [100, 300]),                      # Missed beats
        ([100, 200, 300, 400], [50, 150, 250, 350, 450]),        # Complete phase offset
        ([], [100, 200]),                                         # Empty ref
        ([100, 200], []),                                         # Empty det
        ([], []),                                                 # Empty both
    ]
    
    for ref_list, det_list in scenarios:
        ref = np.array(ref_list, dtype=int)
        det = np.array(det_list, dtype=int)
        
        tp, fp, fn = match_beats(ref, det, fs=fs, tolerance_ms=tol_ms)
        
        # Fundamental invariants
        assert tp + fp == len(det), f"Failed invariant TP+FP == len(det): {tp}+{fp} != {len(det)}"
        assert tp + fn == len(ref), f"Failed invariant TP+FN == len(ref): {tp}+{fn} != {len(ref)}"
        assert tp >= 0
        assert fp >= 0
        assert fn >= 0

def test_duplicate_detections_within_tolerance():
    """Verify that multiple detections within tolerance cannot produce multiple TPs."""
    fs = 250
    ref = np.array([100], dtype=int)
    # Three detections near sample 100 (+/- 12 sample window)
    det = np.array([96, 100, 104], dtype=int)
    
    tp, fp, fn = match_beats(ref, det, fs=fs, tolerance_ms=50.0)
    assert tp == 1
    assert fp == 2
    assert fn == 0

def test_boundary_tolerance_threshold():
    """Verify exact tolerance boundary behavior (+/- 12 samples at 250 Hz for 50 ms)."""
    fs = 250
    tol_samples = int(round(50.0 * fs / 1000.0))  # 12 samples
    assert tol_samples == 12
    
    ref = np.array([100])
    
    # Exactly on boundary: distance = 12
    det_on_boundary = np.array([112])
    tp, fp, fn = match_beats(ref, det_on_boundary, fs=fs, tolerance_ms=50.0)
    assert (tp, fp, fn) == (1, 0, 0)
    
    # Just outside boundary: distance = 13
    det_outside = np.array([113])
    tp, fp, fn = match_beats(ref, det_outside, fs=fs, tolerance_ms=50.0)
    assert (tp, fp, fn) == (0, 1, 1)

def test_compute_beat_metrics_f1_score():
    """Verify F1 score calculation and undefined handling."""
    fs = 250
    ref = np.array([100, 200, 300, 400])
    det = np.array([100, 200, 300, 400])
    
    m = compute_beat_metrics(ref, det, fs=fs)
    assert m.tp == 4
    assert m.fp == 0
    assert m.fn == 0
    assert m.f1 == 1.0
    assert m.sensitivity == 1.0
    assert m.ppv == 1.0
    
    # Zero detections -> None F1
    m_empty = compute_beat_metrics(ref, np.array([]), fs=fs)
    assert m_empty.tp == 0
    assert m_empty.fn == 4
    assert m_empty.f1 is None
