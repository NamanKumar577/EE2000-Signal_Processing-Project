"""
code/tests/test_bit_accurate_reference.py
──────────────────────────────────────────────────────────────────────────────
Automated test suite verifying the bit-accurate integer reference model
against the floating-point reference and golden hardware expectations.
"""

import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.causal_pipeline import DEFAULT_CONFIG, CalibrationBank, run_causal, lp_sos, det_sos
from src.fpga_int_model import quantize_input, quantize_weights, dequantize_input, IN_FRAC
from src.bit_accurate_reference_model import (
    run_bit_accurate_pipeline, sat, sat_u, rshift_round,
    FLAG_REAL_DETECTED, FLAG_FUSED_BEAT, FLAG_INVALID_WARMUP
)
from tests._synth import make_mixture

@pytest.fixture(scope="module")
def setup_models():
    X, fet_peaks, _ = make_mixture(seconds=30, seed=42)
    cfg = DEFAULT_CONFIG
    bank = CalibrationBank(X, cfg, cal_seconds=10)
    w_fl = bank.weights(1)

    x_q = quantize_input(X)
    w_q = quantize_weights(w_fl)

    res_bit = run_bit_accurate_pipeline(
        x_q, w_q,
        lp_sos_float=lp_sos(cfg),
        bp_sos_float=det_sos(cfg),
        mwi_len=cfg.mwi_len,
        refractory=cfg.refractory,
        warmup=cfg.warmup,
        loc_window=cfg.loc_window,
        latency=cfg.latency()
    )

    w_eff = w_q / float(1 << IN_FRAC)
    x_eff = dequantize_input(x_q)
    fecg_fl, det_fl = run_causal(x_eff, w_eff, cfg)

    return X, fet_peaks, res_bit, det_fl, cfg

def test_helpers():
    assert sat(10000000, 24) == 8388607
    assert sat(-10000000, 24) == -8388608
    assert sat_u(100000, 16) == 65535
    assert rshift_round(7, 2) == 2   # 7 + 2 = 9 >> 2 = 2
    assert rshift_round(6, 2) == 2   # 6 + 2 = 8 >> 2 = 2

def test_fixed_point_integer_types(setup_models):
    _, _, res, _, _ = setup_models
    assert np.issubdtype(res.proj.dtype, np.integer)
    assert np.issubdtype(res.hp.dtype, np.integer)
    assert np.issubdtype(res.fecg.dtype, np.integer)
    assert np.issubdtype(res.det_bp.dtype, np.integer)
    assert np.issubdtype(res.x_int.dtype, np.integer)
    assert np.issubdtype(res.peaks.dtype, np.integer)

def test_accumulator_headroom(setup_models):
    _, _, res, _, _ = setup_models
    assert res.max_ranges["max_proj_acc_bits"] <= 32
    assert res.max_ranges["max_lp_biquad_state_bits"] <= 48
    assert res.max_ranges["max_bp_biquad_state_bits"] <= 48
    assert res.max_ranges["max_mwi_acc_bits"] <= 36

def test_concordance_with_float(setup_models):
    _, _, res, det_fl, cfg = setup_models
    # Beats match within 2 samples on >95% of beats
    assert abs(len(res.peaks) - len(det_fl.peaks)) <= 2
    diffs = []
    for pf in det_fl.peaks:
        closest = res.peaks - pf
        diffs.append(closest[np.argmin(np.abs(closest))])
    diffs = np.array(diffs)
    concordance = np.sum(np.abs(diffs) <= 2) / len(diffs)
    assert concordance >= 0.95

def test_warmup_suppression(setup_models):
    _, _, res, _, cfg = setup_models
    assert np.all(res.flags[:cfg.warmup] == FLAG_INVALID_WARMUP)
    if len(res.peaks) > 0:
        assert res.peaks[0] >= cfg.warmup - cfg.latency()
