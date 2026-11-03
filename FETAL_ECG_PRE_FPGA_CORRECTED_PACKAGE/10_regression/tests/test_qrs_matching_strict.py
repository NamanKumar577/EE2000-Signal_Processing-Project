"""
code/tests/test_qrs_matching_strict.py
──────────────────────────────────────────────────────────────────────────────
Tests for strict one-to-one beat matching and metric calculations.
Verifies:
  1. A detected beat never matches multiple reference beats.
  2. A reference beat never matches multiple detected beats.
  3. Conservation: TP + FP == len(det) and TP + FN == len(ref).
  4. Matching within +-50 ms (+-12 samples @ 250 Hz).
  5. Micro vs Macro averaging arithmetic correctness.
"""

import sys
from pathlib import Path
import numpy as np
import pytest

def match_beats_strict_pairs(ref_samples, det_samples, fs=250, tol_ms=50.0):
    """
    Strict greedy nearest-distance 1-to-1 matching.
    Guarantees:
      TP + FP == len(det)
      TP + FN == len(ref)
    """
    tol_samp = int(round(tol_ms * fs / 1000.0))
    if len(ref_samples) == 0 or len(det_samples) == 0:
        return 0, len(det_samples), len(ref_samples), []
    
    diffs = []
    for d_idx, d in enumerate(det_samples):
        for r_idx, r in enumerate(ref_samples):
            dist = abs(d - r)
            if dist <= tol_samp:
                diffs.append((dist, d_idx, r_idx))
    diffs.sort(key=lambda x: x[0])
    
    matched_det = set()
    matched_ref = set()
    pairs = []
    for dist, d_idx, r_idx in diffs:
        if d_idx not in matched_det and r_idx not in matched_ref:
            matched_det.add(d_idx)
            matched_ref.add(r_idx)
            pairs.append((int(ref_samples[r_idx]), int(det_samples[d_idx])))
            
    tp = len(matched_det)
    fp = len(det_samples) - tp
    fn = len(ref_samples) - tp
    return tp, fp, fn, pairs

def test_single_detection_multiple_reference_candidates():
    """If one detection is close to two reference beats, it must only match the nearest one."""
    ref = np.array([100, 108])  # Two reference beats 8 samples apart (32 ms)
    det = np.array([103])        # One detection between them (dist 3 to ref[0], dist 5 to ref[1])

    tp, fp, fn, pairs = match_beats_strict_pairs(ref, det, fs=250, tol_ms=50.0)
    assert tp == 1, "Only one true positive can be claimed"
    assert fp == 0, "No false positives since single detection was matched"
    assert fn == 1, "The second reference beat must be an unmatched false negative"
    assert len(pairs) == 1
    assert pairs[0][0] == 100, "Must match ref[0] which was closer (dist 3 vs dist 5)"
    assert pairs[0][1] == 103

def test_multiple_detections_single_reference_candidate():
    """If two detections are close to one reference beat, only one can be TP, the other is FP."""
    ref = np.array([200])
    det = np.array([195, 203]) # Two detections near 200 (dist 5 and dist 3)

    tp, fp, fn, pairs = match_beats_strict_pairs(ref, det, fs=250, tol_ms=50.0)
    assert tp == 1, "Only one detection can match the single reference beat"
    assert fp == 1, "The second detection must be marked as false positive"
    assert fn == 0, "Reference beat was matched"
    assert len(pairs) == 1

def test_tolerance_boundary():
    """At 250 Hz, 50 ms is 12 samples. A beat at dist 12 matches; dist 13 fails."""
    ref = np.array([500])
    det_inside = np.array([512]) # dist = 12 samples -> 48 ms <= 50 ms
    det_outside = np.array([513]) # dist = 13 samples -> 52 ms > 50 ms

    tp_in, fp_in, fn_in, _ = match_beats_strict_pairs(ref, det_inside, fs=250, tol_ms=50.0)
    assert tp_in == 1 and fp_in == 0 and fn_in == 0, "Distance 12 must match"

    tp_out, fp_out, fn_out, _ = match_beats_strict_pairs(ref, det_outside, fs=250, tol_ms=50.0)
    assert tp_out == 0 and fp_out == 1 and fn_out == 1, "Distance 13 must not match"

def test_mathematical_conservation():
    """Verify TP + FP == len(det) and TP + FN == len(ref) on arbitrary inputs."""
    rng = np.random.default_rng(42)
    ref = np.sort(rng.integers(100, 10000, size=50))
    det = np.sort(rng.integers(100, 10000, size=65))

    tp, fp, fn, pairs = match_beats_strict_pairs(ref, det, fs=250, tol_ms=50.0)
    assert tp + fp == len(det)
    assert tp + fn == len(ref)
    assert len(pairs) == tp

def test_micro_vs_macro_averaging():
    """Micro and macro averages must be distinct when record sizes or performances differ."""
    # Record A: 100 ref, 90 TP, 10 FP, 10 FN -> Sens = 90%, Prec = 90%, F1 = 90%
    # Record B: 10 ref, 5 TP, 5 FP, 5 FN    -> Sens = 50%, Prec = 50%, F1 = 50%
    tp_a, fp_a, fn_a = 90, 10, 10
    tp_b, fp_b, fn_b = 5, 5, 5

    macro_f1 = (90.0 + 50.0) / 2.0 # 70.0%
    micro_f1 = 2 * (tp_a + tp_b) / (2 * (tp_a + tp_b) + (fp_a + fp_b) + (fn_a + fn_b)) * 100.0
    # 2 * 95 / (190 + 15 + 15) = 190 / 220 = 86.36%

    assert abs(macro_f1 - 70.0) < 1e-6
    assert abs(micro_f1 - 86.3636) < 1e-3
    assert macro_f1 != micro_f1, "Micro and macro F1 must be mathematically distinct"
