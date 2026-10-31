"""
tests/test_causal_pipeline.py
Dataset-free tests for the causal float reference (src/causal_pipeline.py).

Run from project root:
    PYTHONPATH=code pytest code/tests/test_causal_pipeline.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.causal_pipeline import (
    DEFAULT_CONFIG, CalibrationBank, detect_causal, group_delay_samples, hp1_filter,
    pca_components, preprocess_causal, run_causal,
)
from src.evaluation import compute_beat_metrics
from tests._synth import make_mixture

CFG = DEFAULT_CONFIG


@pytest.fixture(scope="module")
def mix():
    return make_mixture(seconds=60, seed=0)


def test_latency_is_computed_from_filters():
    gd = group_delay_samples(CFG, 15.0)
    assert 10.0 < gd < 15.0                       # about 12.25 samples (49 ms)
    assert CFG.latency() == int(round(gd))


def test_hp1_matches_shift_recursion():
    """HP1 must equal y = x - B[n-1], B[n] = B[n-1] + 2**-k (x - B[n-1])."""
    rng = np.random.default_rng(1)
    x = rng.standard_normal(500)
    beta = 2.0 ** -CFG.hp_shift_k
    B, y = 0.0, np.zeros_like(x)
    for i, v in enumerate(x):
        y[i] = v - B
        B = B + beta * (v - B)
    assert np.allclose(hp1_filter(x, CFG), y)


def test_hp1_removes_dc():
    y = hp1_filter(np.full(3000, 2.0), CFG)
    assert abs(y[-1]) < 1e-6


def test_preprocess_is_causal():
    rng = np.random.default_rng(2)
    x = rng.standard_normal(2000)
    x2 = x.copy()
    x2[1200:] += 5.0
    assert np.array_equal(preprocess_causal(x, CFG)[:1200], preprocess_causal(x2, CFG)[:1200])


def test_projection_first_equals_filter_first(mix):
    X, _, _ = mix
    w = np.array([0.5, -0.5, 0.5, 0.5])
    a = preprocess_causal(X @ w, CFG)
    b = preprocess_causal(X, CFG) @ w
    assert np.allclose(a, b, atol=1e-9)


def test_detector_does_not_use_the_future(mix):
    """Beats found before t must not change when samples after t are altered."""
    X, _, _ = mix
    bank = CalibrationBank(X, CFG, cal_seconds=30)
    w = bank.weights(1)
    fecg, det = run_causal(X, w, CFG)
    cut = 8000
    X2 = X.copy()
    X2[cut:] += np.random.default_rng(3).standard_normal(X2[cut:].shape) * 0.5
    fecg2, det2 = run_causal(X2, w, CFG)
    assert np.array_equal(det.decl_idx[det.decl_idx < cut - 1], det2.decl_idx[det2.decl_idx < cut - 1])
    assert np.array_equal(det.peaks[det.decl_idx < cut - 1], det2.peaks[det2.decl_idx < cut - 1])


def test_pca_sorted_and_unit_norm(mix):
    X, _, _ = mix
    W, ev = pca_components(preprocess_causal(X, CFG)[CFG.warmup:])
    assert np.all(np.diff(ev) <= 1e-12)
    assert np.allclose(np.linalg.norm(W, axis=0), 1.0)
    for j in range(4):
        assert W[np.argmax(np.abs(W[:, j])), j] > 0


@pytest.mark.parametrize("rule", ["pc2", "periodic_rr", "autocorr"])
def test_label_free_rules_find_fetal_beats(mix, rule):
    X, fet_peaks, _ = mix
    bank = CalibrationBank(X, CFG, cal_seconds=30)
    j, scores = bank.select(rule)
    det = bank.det_full(j)
    m = compute_beat_metrics(fet_peaks, det.peaks, fs=CFG.fs)
    assert m.f1 is not None and m.f1 > 0.9, (rule, j, scores, m)


def test_latency_compensation_centres_the_beats(mix):
    X, fet_peaks, _ = mix
    bank = CalibrationBank(X, CFG, cal_seconds=30)
    det = bank.det_full(1)
    ref = fet_peaks[fet_peaks > 600]
    offs = []
    for p in det.peaks:
        d = p - ref
        i = int(np.argmin(np.abs(d)))
        if abs(d[i]) <= 25:
            offs.append(d[i])
    assert len(offs) > 50
    assert abs(float(np.median(offs))) <= 3        # residual bias within 12 ms


def test_oracle_needs_labels(mix):
    X, _, _ = mix
    bank = CalibrationBank(X, CFG, cal_seconds=30)
    with pytest.raises(ValueError):
        bank.select("oracle")


def test_short_input_returns_no_beats():
    det = detect_causal(np.random.default_rng(0).standard_normal(300), CFG)
    assert len(det.peaks) == 0
