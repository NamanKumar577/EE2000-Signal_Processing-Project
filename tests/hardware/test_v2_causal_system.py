"""
Tests for the v2 system: host adaptive beamformer (causality, packet semantics)
and the bit-accurate model's 0xC4 detector restart and 13-sample latency.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fecg.hardware.bit_accurate_reference import (  # noqa: E402
    BitAccuratePipelineRunner, DET_RESTART_DELAY, LATENCY_COMPENSATION_SAMPLES)
from fecg.host.adaptive_beamformer import plan_schedule  # noqa: E402

REC = ROOT / "data" / "FECGSD" / "DESTINATION" / "sub01" / "snr06dB" / "sub01_snr06dB_l1_c3"
CH = [27, 26, 28, 25]


def _load(n):
    parts = []
    for c in ("fecg1", "mecg", "noise1", "noise2", "noise3"):
        p = Path(str(REC) + f"_{c}.dat")
        parts.append(np.fromfile(p, dtype=np.int16).reshape(-1, 34)[:n, CH].astype(float))
    return sum(parts)


pytestmark = pytest.mark.skipif(not Path(str(REC) + "_fecg1.dat").exists(), reason="FECGSYNDB not present")


def test_host_controller_is_causal():
    """Commands issued up to sample T must not change when samples after T exist."""
    X = _load(30000)
    full = plan_schedule(X)
    T = 20000
    trunc = plan_schedule(X[:T])
    a = [(c.t, c.w_q15, c.restart) for c in full if c.t <= T]
    b = [(c.t, c.w_q15, c.restart) for c in trunc if c.t <= T]
    assert a == b and len(a) >= 1


def test_first_command_is_restart_at_cal_end_and_weights_fit_q15():
    cmds = plan_schedule(_load(15000))
    assert cmds[0].t == 3000 and cmds[0].restart
    assert all(not c.restart for c in cmds[1:])
    for c in cmds:
        assert all(-32768 <= w <= 32767 for w in c.w_q15)


def test_restart_reruns_warmup_and_latency_is_13():
    X = _load(12000)
    xq = np.clip(np.round(X), -32768, 32767).astype(np.int64)
    cmds = plan_schedule(X)
    r = BitAccuratePipelineRunner().process_block(
        xq, target_weights=[(c.t, c.w_q15, c.restart) for c in cmds])
    t0 = cmds[0].t + DET_RESTART_DELAY - 1          # first sample of the re-run warm-up
    raw = np.asarray(r.raw_peaks)
    # no beat can be declared while the detector is re-warming (raw peak index < t0+512
    # would require a detection decided inside the warm-up window)
    decided = raw + 1                                # detection decided >= 1 sample after peak
    assert not np.any((decided >= t0 + 26) & (decided < t0 + 512)), "detection during warm-up"
    assert np.all(r.fhr_hold[t0:t0 + 512] == 0)
    # beats resume after the warm-up
    assert np.sum(raw > t0 + 512) > 20
    assert LATENCY_COMPENSATION_SAMPLES == 13
    assert np.all(np.asarray(r.peaks) == np.maximum(0, raw - 13))
