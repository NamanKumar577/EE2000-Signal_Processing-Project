"""
tools/accuracy/harness.py
Fast float research harness for the causal FECG pipeline on FECGSYNDB.

Purpose: iterate quickly on causal, label-free algorithm changes, then port the
winners to the bit-accurate model (src/fecg/hardware/bit_accurate_reference.py)
and the RTL.  Ground-truth annotations are used ONLY for scoring, never by the
algorithm.

Scoring (fixes vs scratch/run_complete_fecgsyndb_evaluation.py):
  * Causal timeline: the device starts with no spatial weights, the host
    calibrates on samples it has already seen, sends weights, and only beats
    after `score_start` are scored.  Nothing processes a sample with weights
    computed from later samples.
  * FHR error compares the device's reported FHR (median-5 stream) with the
    true FHR (median-5 of true RR) at every true beat, instead of comparing
    instantaneous detector RR with the record's nominal header FHR.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import wfdb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "FECGSD" / "DESTINATION"
FS = 250
NCH = 34
CHANNELS_4CH = [27, 26, 28, 25]
SUBS = [f"sub{i:02d}" for i in range(1, 11)]
SNRS = ["snr00dB", "snr03dB", "snr06dB", "snr09dB", "snr12dB"]
LAYOUTS = [f"l{i}" for i in range(1, 6)]
CONDS = ["c0", "c1", "c2", "c3", "c4"]
TOL = 13  # +-50 ms


@dataclass
class Rec:
    rid: str
    sub: str
    snr: int
    lay: str
    cond: str
    base: str


def list_records(conds=CONDS, subs=SUBS, snrs=SNRS, layouts=LAYOUTS) -> List[Rec]:
    out = []
    for s in subs:
        for snr in snrs:
            for l in layouts:
                for c in conds:
                    base = DATA / s / snr / f"{s}_{snr}_{l}_{c}"
                    parts = ["_fecg1.dat", "_mecg.dat", "_noise1.dat", "_noise2.dat"]
                    if all(Path(str(base) + p).exists() for p in parts):
                        out.append(Rec(f"{s}_{snr}_{l}_{c}", s, int(snr[3:5]), l, c, str(base)))
    return out


def _read(base: str, comp: str) -> np.ndarray:
    return np.fromfile(base + f"_{comp}.dat", dtype=np.int16).reshape(-1, NCH).astype(np.float64)


def load(rec: Rec, chans=CHANNELS_4CH, components: bool = False):
    """Mixture in raw int16 counts (3000 LSB/mV), like the existing evaluation."""
    f = _read(rec.base, "fecg1")
    m = _read(rec.base, "mecg")
    n = _read(rec.base, "noise1") + _read(rec.base, "noise2")
    if rec.cond == "c3" and Path(rec.base + "_noise3.dat").exists():
        n = n + _read(rec.base, "noise3")
    mix = f + m + n
    if not np.isfinite(mix).all():
        return None
    fq = wfdb.rdann(rec.base + "_fecg1", "qrs").sample.astype(np.int64)
    mq = wfdb.rdann(rec.base + "_mecg", "qrs").sample.astype(np.int64)
    out = {"X": mix[:, chans], "fq": fq, "mq": mq, "Xall": mix}
    if components:
        out.update({"F": f[:, chans], "M": m[:, chans], "N": n[:, chans], "Fall": f, "Mall": m})
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Scoring
# ──────────────────────────────────────────────────────────────────────────────

def match(ref: np.ndarray, det: np.ndarray, tol: int = TOL) -> Tuple[int, int, int, np.ndarray]:
    """Greedy one-to-one matching in time order. Returns tp, fp, fn, signed errors."""
    ref = np.sort(ref)
    det = np.sort(det)
    used = np.zeros(len(det), bool)
    errs = []
    tp = 0
    j0 = 0
    for r in ref:
        while j0 < len(det) and det[j0] < r - tol:
            j0 += 1
        best, bd = -1, tol + 1
        j = j0
        while j < len(det) and det[j] <= r + tol:
            if not used[j] and abs(det[j] - r) < bd:
                bd, best = abs(det[j] - r), j
            j += 1
        if best >= 0:
            used[best] = True
            tp += 1
            errs.append(det[best] - r)
    return tp, len(det) - tp, len(ref) - tp, np.array(errs)


def fhr_ref_stream(fq: np.ndarray, n: int) -> np.ndarray:
    """True FHR (bpm) as a step function: 60*fs/median(last 5 true RR), updated at each true beat."""
    out = np.full(n, np.nan)
    rr = np.diff(fq)
    for i in range(1, len(fq)):
        med = np.median(rr[max(0, i - 5):i])
        out[fq[i]:] = 60.0 * FS / med
    return out


def score(fq, det, fhr_dev, n, score_start, mq=None) -> Dict[str, float]:
    """fhr_dev: per-sample device FHR in bpm (nan/0 = none)."""
    r = fq[(fq >= score_start) & (fq < n - TOL)]
    d = det[(det >= score_start) & (det < n - TOL)]
    tp, fp, fn, errs = match(r, d)
    se = tp / max(tp + fn, 1)
    ppv = tp / max(tp + fp, 1)
    f1 = 2 * se * ppv / max(se + ppv, 1e-12)
    res = {"tp": tp, "fp": fp, "fn": fn, "se": 100 * se, "ppv": 100 * ppv, "f1": 100 * f1,
           "terr_mean": float(errs.mean()) if len(errs) else np.nan,
           "terr_std": float(errs.std()) if len(errs) else np.nan}
    # FHR: compare device output and truth at every scored true beat (+ 0.5 s for device to report)
    ref = fhr_ref_stream(fq, n)
    idx = np.clip(r + 125, 0, n - 1)
    dv = fhr_dev[idx]
    rv = ref[r]
    ok = np.isfinite(rv)
    dv2 = np.where(np.isfinite(dv) & (dv > 0), dv, 0.0)  # no output counts as full error
    ae = np.abs(dv2[ok] - rv[ok])
    res["fhr_mae"] = float(ae.mean()) if len(ae) else np.nan
    res["fhr_within5"] = float(100 * np.mean(ae <= 5)) if len(ae) else np.nan
    if mq is not None and fp > 0:
        # how many false positives coincide with maternal beats
        mm = mq[(mq >= score_start) & (mq < n)]
        dfp = np.setdiff1d(d, _matched_dets(r, d))
        tpm, _, _, _ = match(mm, dfp)
        res["fp_maternal"] = tpm
    return res


def _matched_dets(r, d, tol=TOL):
    used = np.zeros(len(d), bool)
    j0 = 0
    for x in np.sort(r):
        while j0 < len(d) and d[j0] < x - tol:
            j0 += 1
        best, bd = -1, tol + 1
        j = j0
        while j < len(d) and d[j] <= x + tol:
            if not used[j] and abs(d[j] - x) < bd:
                bd, best = abs(d[j] - x), j
            j += 1
        if best >= 0:
            used[best] = True
    return d[used]


def run_parallel(fn, recs, procs: Optional[int] = None):
    import multiprocessing as mp
    procs = procs or max(1, (os.cpu_count() or 4) - 1)
    with mp.get_context("spawn").Pool(procs) as pool:
        return pool.map(fn, recs, chunksize=4)
