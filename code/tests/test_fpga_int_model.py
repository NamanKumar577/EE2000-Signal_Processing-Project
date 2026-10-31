"""
tests/test_fpga_int_model.py
Dataset-free tests for the integer golden model (src/fpga_int_model.py).

Run from project root:
    PYTHONPATH=code pytest code/tests/test_fpga_int_model.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.causal_pipeline import DEFAULT_CONFIG, CalibrationBank
from src.evaluation import compute_beat_metrics
from src.fpga_int_model import (
    COEF_BITS, DATA_BITS, compare_with_float, dump_stages, fhr_lut, quantize_input,
    quantize_sos, quantize_weights, read_hex, rshift_round, run_int_pipeline, sat, to_hex,
)
from src.causal_pipeline import det_sos, lp_sos
from tests._synth import make_mixture

CFG = DEFAULT_CONFIG


@pytest.fixture(scope="module")
def setup():
    X, fet_peaks, _ = make_mixture(seconds=40, seed=3)
    bank = CalibrationBank(X, CFG, cal_seconds=20)
    w = bank.weights(1)
    x_q = quantize_input(X)
    w_q = quantize_weights(w)
    res = run_int_pipeline(x_q, w_q, CFG)
    return X, fet_peaks, w, x_q, w_q, res


def test_helpers():
    assert sat(10 ** 9, 24) == 2 ** 23 - 1 and sat(-10 ** 9, 24) == -2 ** 23
    assert rshift_round(5, 1) == 3 and rshift_round(-5, 1) == -2   # half rounds up
    assert to_hex(-1, 16) == "ffff" and to_hex(5, 24) == "000005"


def test_quantisers_in_range():
    q = quantize_input(np.array([-100.0, 0.0, 100.0, 2.5]))
    assert q[0] == -32768 and q[2] == 32767 and q[1] == 0 and q[3] == 16384
    wq = quantize_weights(np.array([1.0, -1.0, 0.5, 0.0]))
    assert wq.tolist() == [32767, -32768, 16384, 0]
    for sos in (lp_sos(CFG), det_sos(CFG)):
        for row in quantize_sos(sos):
            assert all(-(1 << (COEF_BITS - 1)) <= c < (1 << (COEF_BITS - 1)) for c in row)


def test_lp_numerator_two_is_exact():
    """Q3.15 must represent the numerator coefficient 2.0 exactly (Q2.16 could not)."""
    assert (2 << 15) in [c for row in quantize_sos(lp_sos(CFG)) for c in row]


def test_fhr_lut():
    lut = fhr_lut()
    assert len(lut) == 241 and lut[0] == 2500 and lut[-1] == 500        # 250 bpm .. 50 bpm
    assert lut[107 - 60] == round(150000 / 107)                           # ~140.2 bpm
    assert max(lut) < 4096                                                # fits 12 bits


def test_model_is_integer_only(setup):
    *_, res = setup
    for name in ("proj", "hp", "fecg", "det_bp", "x_int", "beat_flag", "fhr_hold", "peaks", "rr"):
        assert np.issubdtype(getattr(res, name).dtype, np.integer), name


def test_value_ranges(setup):
    *_, res = setup
    lim = 1 << (DATA_BITS - 1)
    assert np.all(np.abs(res.proj) <= lim) and np.all(np.abs(res.fecg) <= lim)
    assert np.all(np.abs(res.det_bp) <= 1 << 15)
    assert res.x_int.min() >= 0 and int(res.x_int.max()).bit_length() <= 40
    assert res.stats["max_biquad_state_bits"] <= 48


def test_matches_float_reference(setup):
    X, _, w, *_ = setup
    r = compare_with_float(X, w, CFG)
    assert r["sqnr_db"] > 40.0, r
    # A beat whose energy sits almost exactly on the threshold can be declared on a
    # different candidate once values are rounded to integers; allow a few percent.
    # (The RTL must match the INTEGER model exactly, not the float one.)
    assert r["fp"] + r["fn"] <= max(2, int(0.03 * r["n_float_beats"])), r
    assert r["n_int_beats"] == r["n_float_beats"] or abs(r["n_int_beats"] - r["n_float_beats"]) <= 2


def test_finds_the_fetal_beats(setup):
    _, fet_peaks, *_, res = setup
    m = compute_beat_metrics(fet_peaks, res.peaks, fs=CFG.fs)
    assert m.f1 is not None and m.f1 > 0.9, m


def test_no_beats_during_warmup(setup):
    *_, res = setup
    assert res.warmup_flag[:CFG.warmup].all() and not res.warmup_flag[CFG.warmup:].any()
    assert res.beat_flag[:CFG.warmup].sum() == 0
    assert res.decl_idx.min() >= CFG.warmup


def test_refractory_and_fhr(setup):
    *_, res = setup
    rr = np.diff(res.raw_peaks)
    assert rr.min() >= 40                                  # refractory is on candidate time, R shifts a little
    ok = (res.rr >= 60) & (res.rr <= 300)
    assert np.all(res.fhr_beat[ok] > 0)
    valid = res.fhr_beat[ok]
    assert 1200 < np.median(valid) < 1600                  # ~140 bpm in x10 units


def test_causal(setup):
    X, _, w, x_q, w_q, res = setup
    cut = 5000
    x2 = x_q.copy()
    x2[cut:] = np.random.default_rng(0).integers(-3000, 3000, x2[cut:].shape)
    res2 = run_int_pipeline(x2, w_q, CFG)
    for name in ("proj", "hp", "fecg", "det_bp", "x_int", "fhr_hold"):
        assert np.array_equal(getattr(res, name)[:cut], getattr(res2, name)[:cut]), name
    assert np.array_equal(res.beat_flag[:cut - 1], res2.beat_flag[:cut - 1])


def test_deterministic(setup):
    *_, x_q, w_q, res = setup
    res2 = run_int_pipeline(x_q, w_q, CFG)
    assert np.array_equal(res.x_int, res2.x_int) and np.array_equal(res.peaks, res2.peaks)


def test_hex_dump_roundtrip(setup, tmp_path):
    *_, x_q, w_q, res = setup
    files = dump_stages(tmp_path, x_q, w_q, res)
    assert "proj_s24.hex" in files and "fhr_lut_u16.hex" in files
    assert np.array_equal(read_hex(tmp_path / "proj_s24.hex", 24), res.proj)
    assert np.array_equal(read_hex(tmp_path / "det_bp_s16.hex", 16), res.det_bp)
    assert np.array_equal(read_hex(tmp_path / "x_int_u40.hex", 40, signed=False), res.x_int)
    assert np.array_equal(read_hex(tmp_path / "stimulus_ch2_s16.hex", 16), x_q[:, 2])
    assert np.array_equal(read_hex(tmp_path / "fhr_lut_u16.hex", 16, signed=False), np.array(fhr_lut()))
    peaks = [int(v) for v in (tmp_path / "peaks.txt").read_text().split()]
    assert peaks == res.peaks.tolist()
