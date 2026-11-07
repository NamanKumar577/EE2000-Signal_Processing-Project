"""Compare spatial calibrators under the causal timeline. Common score start = 20 s."""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import pipeline as P  # noqa: E402
import calib as K  # noqa: E402
from exp_baseline import calib_frozen  # noqa: E402

SETTLE = 128
LATENCY = 13
SCORE0 = 5000


def run_sched(X, sched, n):
    """sched: list of (t_apply, w). Before first: unity. Detector restarts after FIRST update only."""
    W = np.zeros((n, X.shape[1]))
    W[:, 0] = 1.0
    for t, w in sched:              # 64-sample linear crossfade, like the RTL slew engine
        w_old = W[t - 1].copy() if t > 0 else W[0].copy()
        ramp = np.minimum(np.arange(1, n - t + 1), 64)[:, None] / 64.0
        W[t:] = w_old + ramp * (np.asarray(w) - w_old)
    proj = np.einsum("nc,nc->n", X, W)
    fe, bp = P.front_end(proj)
    e = P.mwi(bp * bp, 30)
    comp, raw, fhr = P.detect2(np.abs(bp), e, sched[0][0] + SETTLE, 512, 50, 26, LATENCY, 50, 300,
                               DET["sb_on"], DET["sb_frac"], DET["sb_lo"], DET["sb_hi"], DET["sb_wait"],
                               DET["clamp_k"], DET["art_k"])
    return comp, fhr


DET = {"sb_on": 0, "sb_frac": 0.5, "sb_lo": 0.6, "sb_hi": 1.4, "sb_wait": 1.5, "clamp_k": 0.0, "art_k": 0.0}
for a in sys.argv:
    if a.startswith("--det="):          # e.g. --det=sb_on:1,sb_frac:0.4
        for kv in a[6:].split(","):
            k, v = kv.split(":")
            DET[k] = type(DET[k])(float(v)) if DET[k] is not int else int(v)


VARIANTS = {}


def variant(f):
    VARIANTS[f.__name__] = f
    return f


@variant
def frozen6(X):
    wq, _ = calib_frozen(X[:1512])
    return [(1512, np.asarray(wq, float) / 32768)]


@variant
def selfref6(X):
    w, s, _ = K.calib_selfref(X[:1512])
    return [(1512, w)]


@variant
def selfref12(X):
    w, s, _ = K.calib_selfref(X[:3000])
    return [(3000, w)]


@variant
def selfref12_re30(X):
    """initial 12 s calibration, then recalibrate every 30 s on the trailing 30 s."""
    n = len(X)
    w, s, _ = K.calib_selfref(X[:3000])
    sched = [(3000, w)]
    t = 3000 + 7500
    while t < n:
        w2, s2, _ = K.calib_selfref(X[t - 7500:t])
        if np.dot(w2, sched[-1][1]) < 0:
            w2 = -w2
        sched.append((t, w2))
        t += 7500
    return sched


def _track(X, ce, every, win, accept_margin=0.05):
    n = len(X)
    w, s, _ = K.calib_selfref(X[:ce])
    sched = [(ce, w)]
    t = ce + every
    while t < n:
        lo = max(0, t - win)
        Y = K.band(X[lo:t])
        V = K.pca_dirs(Y[512:])
        mpk = K.maternal_peaks(Y @ V[:, 0])
        cur = sched[-1][1]
        s_cur, _ = K.candidate_score(Y @ cur, 512, mpk)
        w2, lam = K.refine(Y, cur, iters=2, mpk=mpk)
        if np.dot(w2, cur) < 0:
            w2 = -w2
        s_new, _ = K.candidate_score(Y @ w2, 512, mpk)
        if s_new >= s_cur - accept_margin:
            sched.append((t, w2))
        t += every
    return sched


@variant
def adapt_2_5(X):
    return K.adaptive_schedule(X, 3000, 500, 1250)


@variant
def adapt_2_10(X):
    return K.adaptive_schedule(X, 3000, 500, 2500)


@variant
def adaptf(X):
    return K.adaptive_schedule2(X)


@variant
def adaptf_a5(X):
    return K.adaptive_schedule2(X, alpha=0.5)


@variant
def adaptf_w20(X):
    return K.adaptive_schedule2(X, win=2500, fwin=5000)


@variant
def gate15(X):
    return K.gated_schedule(X, gate=1.5)


@variant
def gate2(X):
    return K.gated_schedule(X, gate=2.0)


@variant
def gate4(X):
    return K.gated_schedule(X, gate=4.0)


@variant
def gate8(X):
    return K.gated_schedule(X, gate=8.0)


@variant
def robust(X):
    return K.robust_schedule(X)


@variant
def robust_q5(X):
    return K.robust_schedule(X, q_min=0.5)


@variant
def adapt_1_5(X):
    return K.adaptive_schedule(X, 3000, 250, 1250)


@variant
def track12_10_20(X):
    return _track(X, 3000, 2500, 5000)


@variant
def track12_10_40(X):
    return _track(X, 3000, 2500, 10000)


def one(rec):
    d = H.load(rec)
    if d is None:
        return None
    X, fq, mq = d["X"], d["fq"], d["mq"]
    n = len(X)
    out = {"rid": rec.rid, "sub": rec.sub, "snr": rec.snr, "lay": rec.lay, "cond": rec.cond}
    for name in SELECTED:
        if name in MULTI:
            t_apply, Wk = MULTI[name](X)
            comp, fhr = run_multi(X, t_apply, Wk, n)
        else:
            sched = VARIANTS[name](X)
            comp, fhr = run_sched(X, sched, n)
        s = H.score(fq, comp, fhr, n, SCORE0, mq)
        out.update({f"{name}_{k}": v for k, v in s.items()})
    return out


SELECTED = [a for a in sys.argv[1:] if not a.startswith("--")] or list(VARIANTS)

if __name__ == "__main__":
    recs = H.list_records()
    if "--quick" in sys.argv:
        recs = recs[::7]
    t0 = time.time()
    rows = [r for r in H.run_parallel(one, recs) if r is not None]
    df = pd.DataFrame(rows)
    tag = "_".join(SELECTED) + ("_quick" if "--quick" in sys.argv else "")
    df.to_csv(HERE / f"results_spatial_{tag}.csv", index=False)
    print(f"{len(df)} records, {time.time()-t0:.0f}s")
    for v in SELECTED:
        m = df[[f"{v}_{k}" for k in ("f1", "se", "ppv", "fhr_mae", "fhr_within5")]].mean().round(2)
        print(f"{v:18s}", m.values, df.groupby("cond")[f"{v}_f1"].mean().round(1).to_dict())


def run_multi(X, t_apply, Wk, n):
    """k-direction fetal-energy detector (each direction: own HP1+LP40+BP chain)."""
    Wk = Wk / np.linalg.norm(Wk[:, 0])   # common scale (keeps relative weighting)
    bps = []
    for i in range(Wk.shape[1]):
        Wt = np.zeros((n, X.shape[1]))
        Wt[:, 0] = 1.0 if i == 0 else 0.0
        ramp = np.minimum(np.arange(1, n - t_apply + 1), 64)[:, None] / 64.0
        Wt[t_apply:] = Wt[t_apply - 1] + ramp * (Wk[:, i] - Wt[t_apply - 1])
        fe, bp = P.front_end(np.einsum("nc,nc->n", X, Wt))
        bps.append(bp)
    E = sum(b * b for b in bps)
    e = P.mwi(E, 30)
    comp, raw, fhr = P.detect2(np.sqrt(E), e, t_apply + SETTLE, 512, 50, 26, LATENCY, 50, 300,
                               DET["sb_on"], DET["sb_frac"], DET["sb_lo"], DET["sb_hi"], DET["sb_wait"],
                               DET["clamp_k"], DET["art_k"])
    return comp, fhr


MULTI = {}


def multi(f):
    MULTI[f.__name__] = f
    return f


@multi
def sub2_12(X):
    w, s, _ = K.calib_selfref(X[:3000])
    Wk, lam = K.subspace2(X[:3000], w, k=2)
    return 3000, Wk


@multi
def sub3_12(X):
    w, s, _ = K.calib_selfref(X[:3000])
    Wk, lam = K.subspace2(X[:3000], w, k=3)
    return 3000, Wk
