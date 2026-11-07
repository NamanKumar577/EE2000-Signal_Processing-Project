"""
CinC 2013 diagnostics / experiments (float mirror of the FPGA datapath).
  v2      : current system (host beamformer on raw leads)
  oracle  : DIAGNOSTIC ONLY - best linear 4-lead filter from TRUE fetal beats
  mts_v2  : causal maternal template subtraction per lead, then the v2 host
            beamformer and the unchanged FPGA detector chain
  mts_orc : DIAGNOSTIC - oracle filter after template subtraction
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import eigh

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))
import harness as H  # noqa: E402
import pipeline as P  # noqa: E402
from eval_cinc2013 import load, UNRELIABLE  # noqa: E402
from fecg.host import adaptive_beamformer as AB  # noqa: E402

SCORE0 = 5000
LAT = 13


def run_sched(X, cmds, n):
    W = np.zeros((n, X.shape[1]))
    W[:, 0] = 1.0
    for c in cmds:
        t = c.t
        w = np.asarray(c.w_q15, float) / 32768
        w_old = W[t - 1].copy()
        ramp = np.minimum(np.arange(1, n - t + 1), 64)[:, None] / 64.0
        W[t:] = w_old + ramp * (w - w_old)
    fe, bp = P.front_end(np.einsum("nc,nc->n", X, W))
    e = P.mwi(bp * bp, 30)
    det0 = cmds[0].t + 127 if cmds else 0
    comp, raw, fhr = P.detect2(np.abs(bp), e, det0, 512, 50, 26, LAT, 50, 300, 0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
    return comp, fhr


def run_static(X, w, n, t_apply=3000):
    class C:  # minimal command object
        pass
    c = C()
    c.t, c.w_q15, c.restart = t_apply, list(np.clip(np.round(w / np.max(np.abs(w)) * 0.999 * 32768), -32768, 32767)), True
    return run_sched(X, [c], n)


# ── causal maternal template subtraction ─────────────────────────────────────
def maternal_detect_causal(X):
    """Causal maternal R-peak detector: FPGA-style adaptive detector on the summed
    band energy of all leads (maternal dominates), refractory 75 samples (300 ms).
    Returns peak indices and the sample at which each was decided."""
    Y = AB.band(X)
    E = np.sum(Y * Y, axis=1)
    e = P.mwi(E, 30)
    comp, raw, _ = P.detect2(np.sqrt(E), e, 0, 512, 75, 26, 0, 75, 500, 0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
    return raw


def template_subtract(X, mpk, L1=25, L2=100, alpha=1.0 / 8):
    """Per lead, subtract an EMA (1/8) template of PAST maternal beats aligned at
    each maternal peak.  Only past beats form the template; samples up to
    p+L2 are modified, i.e. the cleaned stream has a fixed L2 (+detector) delay."""
    Xh = P.hp1(X)                       # same baseline remover as the FPGA
    out = Xh.copy()
    T = None
    n = len(X)
    for p in mpk:
        lo, hi = p - L1, p + L2
        if lo < 0 or hi > n:
            continue
        seg = Xh[lo:hi]
        if T is not None:
            # per-lead least-squares amplitude match (one scalar per lead)
            g = np.sum(seg * T, axis=0) / np.maximum(np.sum(T * T, axis=0), 1e-9)
            g = np.clip(g, 0.5, 1.5)
            out[lo:hi] = seg - T * g
            T = T + alpha * (seg - T)
        else:
            T = seg.copy()
    return out


def oracle_w(X, fq, n):
    Y = AB.band(X)
    pk = fq[(fq > 600) & (fq < n - 10)]
    Cf = AB._qrs_cov(Y, pk)
    C = Y[600:].T @ Y[600:] / (n - 600)
    _, v = eigh(Cf, AB._loaded(C))
    return v[:, -1]


def one(rid):
    X, fq = load(rid)
    n = len(X)
    out = {"record": rid, "unreliable": rid in UNRELIABLE}
    sc = lambda comp, fhr: H.score(fq, comp, fhr, n, SCORE0)  # noqa: E731
    out["v2"] = sc(*run_sched(X, AB.plan_schedule(X), n))["f1"]
    out["oracle"] = sc(*run_static(X, oracle_w(X, fq, n), n))["f1"]
    mpk = maternal_detect_causal(X)
    Xc = template_subtract(X, mpk)
    out["mts_v2"] = sc(*run_sched(Xc, AB.plan_schedule(Xc), n))["f1"]
    out["mts_orc"] = sc(*run_static(Xc, oracle_w(Xc, fq, n), n))["f1"]
    out["mhr"] = round(60 * 250 / np.median(np.diff(mpk)), 1) if len(mpk) > 3 else 0
    return out


if __name__ == "__main__":
    ids = [f"a{i:02d}" for i in range(1, 76)]
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12))
    df.to_csv(HERE / "results_exp_cinc.csv", index=False)
    print(df.round(1).to_string(index=False))
    for cols in (["v2", "oracle", "mts_v2", "mts_orc"],):
        print("all      mean", df[cols].mean().round(2).to_dict())
        print("reliable mean", df[~df.unreliable][cols].mean().round(2).to_dict())
