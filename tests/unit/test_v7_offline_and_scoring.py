"""
Unit tests for the v7-LA offline look-ahead steps and the causal scoring harness, on
small synthetic beat trains (no data files needed).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "accuracy"))
sys.path.insert(0, str(ROOT / "fpga_implementation" / "uart_host"))

H = pytest.importorskip("harness")
V = pytest.importorskip("v7_offline")


# ---------------------------------------------------------------- scoring harness
def test_match_perfect_and_tolerance():
    ref = np.arange(1000, 10000, 100)
    tp, fp, fn, err = H.match(ref, ref + 5)
    assert (tp, fp, fn) == (len(ref), 0, 0)
    tp, fp, fn, _ = H.match(ref, ref + 20)              # 80 ms > 50 ms tolerance
    assert tp == 0 and fp == len(ref) and fn == len(ref)


def test_score_f1_and_fhr():
    n = 20000
    ref = np.arange(1000, n - 200, 100)                 # 150 bpm
    fhr = np.full(n, 150.0)
    r = H.score(ref, ref, fhr, n, 5000)
    assert r["f1"] == pytest.approx(100.0) and r["fhr_mae"] == pytest.approx(0.0, abs=1e-6)
    r = H.score(ref, ref[::2], np.zeros(n), n, 5000)    # half the beats, no FHR output
    assert r["se"] == pytest.approx(50.0, abs=1.0) and r["ppv"] == pytest.approx(100.0)


# ---------------------------------------------------------------- v7-LA steps
def test_cleanup_fills_a_missed_beat():
    b = np.arange(1000, 3000, 100)
    missing = np.delete(b, 10)
    allq = {0: missing, 1: np.array([b[10] + 2])}
    out = V.cleanup(missing, allq)
    assert np.min(np.abs(out - b[10])) <= 2 and len(out) == len(b)


def test_cleanup_drops_a_split_beat():
    b = np.arange(1000, 3000, 100)
    extra = np.sort(np.r_[b, b[10] + 40])
    out = V.cleanup(extra, {0: extra})
    assert len(out) == len(b) and b[10] + 40 not in out


def test_fhr_centred_constant_rhythm():
    b = np.arange(1000, 10000, 100)                     # RR 0.4 s = 150 bpm
    f = V.fhr_centred(b, 12000)
    assert np.allclose(f[1100:9800], 150.0)


def _tracks(n, good=3):
    """16 tracks: track `good` is a clean 150-bpm train with consistent beat shapes, the rest noise"""
    rng = np.random.default_rng(0)
    shape = np.sin(np.linspace(0, np.pi, 31)) * 1000
    tr = {}
    for k in range(16):
        if k == good:
            q = np.arange(4000, n, 100)
            snaps = [(int(t), shape + rng.normal(0, 30, 31)) for t in q]
        else:
            q = np.sort(rng.integers(4000, n, size=(n - 4000) // 130))
            snaps = [(int(t), rng.normal(0, 1000, 31)) for t in q]
        tr[k] = {"q": list(map(int, q)), "snap": snaps, "pem": [0] * len(q)}
    return tr


def test_viterbi_follows_the_consistent_track():
    n = 30000
    tr = _tracks(n, good=3)
    b, path = V.offline(tr, np.zeros(0, np.int64), n)
    assert np.mean(np.array(path) == 3) > 0.9
    ref = np.arange(4000, n, 100) - V.LAT
    tp, fp, fn, _ = H.match(ref[ref >= 5000], b[b >= 5000])
    assert tp / max(tp + fn, 1) > 0.95 and tp / max(tp + fp, 1) > 0.95


def test_parse_reads_device_frames():
    from run_v6_board_eval import frame
    bp = np.arange(31, dtype="<i4")
    up = (frame(0x87, bytes([5]) + (1234).to_bytes(4, "little"))
          + frame(0x88, bytes([5]) + (1234).to_bytes(4, "little") + bp.tobytes() + (77).to_bytes(2, "little"))
          + frame(0x83, (999).to_bytes(4, "little")))
    tr, _, mpk = V.parse(up)
    assert tr[5]["q"] == [1234] and tr[5]["snap"][0][0] == 1234
    assert np.array_equal(tr[5]["snap"][0][1], bp.astype(float)) and list(mpk) == [999]
