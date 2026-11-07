"""Calibration v3 candidate: 'fastest regular train' selection (FHR > MHR)."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import numpy as np
from scipy.linalg import eigh
from fecg.host import adaptive_beamformer as AB

def calibrate3(Xbuf, reg_min=0.6, lo=80.0, hi=220.0):
    Y = AB.band(np.asarray(Xbuf, float))
    W0 = AB.WARMUP
    C = Y[W0:].T @ Y[W0:] / (len(Y) - W0)
    vals, V = np.linalg.eigh(C); V = V[:, ::-1]
    mpk = AB.maternal_peaks(Y @ V[:, 0])
    seeds = [V[:, j] for j in range(V.shape[1])]
    if len(mpk) >= 4:
        Cm = AB._loaded(AB._qrs_cov(Y, mpk, 8) + 1e-3 * np.trace(C) / C.shape[0] * np.eye(C.shape[0]))
        _, mv = eigh(C, Cm); seeds += [mv[:, -1], mv[:, -2]]
    cands = []
    for s0 in seeds:
        for ex in (mpk, None):
            w = AB._refine(Y, s0, ex)
            pk = AB._peaks_after(Y @ w)
            r = AB._rate(pk); reg = AB._regularity(pk, lo, hi)
            cands.append((w, r, reg, AB._score(Y @ w, mpk)))
    regs = [c for c in cands if c[2] >= reg_min]
    if regs:
        rmax = max(c[1] for c in regs)
        top = [c for c in regs if c[1] >= 0.95 * rmax]          # the fastest regular source
        best = max(top, key=lambda c: c[2] + 0.0 * c[3])
        return best[0], {"rule": "fastest_regular", "rate": best[1], "reg": best[2]}
    best = max(cands, key=lambda c: c[3])
    return best[0], {"rule": "score", "rate": best[1], "reg": best[2]}
