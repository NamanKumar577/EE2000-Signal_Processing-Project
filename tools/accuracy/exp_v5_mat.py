"""Maternal train selection with rate continuity (mother's HR cannot jump >20%
between 5 s decisions).  Dev sets only."""
import numpy as np
import pandas as pd
from scipy.signal import sosfilt
import harness as H
import fe3
import pipeline as P
from devbench import _load, items
from exp_v5_raw import raw_tracks
from exp_v5_gate import select, coinc

FS = 250


def maternal_cont(X, init=2500, hop=1250, look=5000, refractory=75, mwi_len=38, jump=0.2, lo=40, hi=130):
    Y = sosfilt(fe3.MAT_SOS, P.hp1(X), axis=0)
    C = Y[256:init].T @ Y[256:init]
    _, V = np.linalg.eigh(C)
    n = len(X)
    trains = []
    for j in range(1, V.shape[1] + 1):
        y = Y @ V[:, -j]
        e = P.mwi(y * y, mwi_len)
        _, raw, _ = P.detect2(np.abs(y), e, 0, 512, refractory, 30, 0, refractory, 625,
                              0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
        trains.append(raw)
    state = {"rate": None}

    def choose(t, prev=None):
        st = [fe3._train_stats(pk, max(512, t - look), t) for pk in trains]
        best = None
        for k, (rate, reg) in enumerate(st):
            if reg < 0.6 or not (lo <= rate <= hi):
                continue
            if state["rate"] is not None and abs(rate / state["rate"] - 1) > jump:
                continue
            if best is None or rate < st[best][0] * 0.9:
                best = k
        if best is not None:
            state["rate"] = st[best][0]
            return best
        return prev if prev is not None else int(np.argmax([s[1] for s in st]))

    k = choose(init)
    out = [trains[k][trains[k] < init]]
    t = init
    while t < n:
        k = choose(t, k)
        pk = trains[k]
        out.append(pk[(pk >= t) & (pk < t + hop)])
        t += hop
    pk = np.concatenate(out)
    keep = np.concatenate([[True], np.diff(pk) >= refractory])[:len(pk)]
    return pk[keep], None


def one(item):
    d = _load(item)
    if d is None:
        return None
    X, fq = d
    n = len(X)
    out = {"set": item[0], "rid": item[1] if isinstance(item[1], str) else item[1].rid}
    P.set_band(P.V4_BAND)
    mq = None
    if item[0] == "syn":
        mq = H.load(item[1])["mq"]
    orig = fe3.maternal_peaks_dynamic
    for mname in ("dyn", "cont"):
        if mname == "cont":
            fe3.maternal_peaks_dynamic = maternal_cont
        tr = fe3.hybrid_tracks(X, mat="dynamic")
        Xf = fe3.prefilter(X)
        mpk, _ = fe3.maternal_peaks_dynamic(X)
        fe3.maternal_peaks_dynamic = orig
        if mq is not None:
            out[f"{mname}_matok"] = coinc(mpk, mq, tol=15) * 100
        rt = raw_tracks(X, Xf, mpk, det="track")
        rd = raw_tracks(X, Xf, mpk, det="det")
        for name, t in {"full": tr, "nov2+rawTD": tr[1:] + rt + rd, "full+rawTD": tr + rt + rd}.items():
            for gate in (105, 1000):
                pk, fh = select(t, mpk, n, 4877, c0=0.3, c1=0.6, gate=gate)
                out[f"{mname}_{name}_g{gate}"] = H.score(fq, pk, fh, n, 5000)["f1"]
            (pk, fh), _ = fe3.select_tracks(t, n, 4877)
            out[f"{mname}_{name}_nopen"] = H.score(fq, pk, fh, n, 5000)["f1"]
    return out


if __name__ == "__main__":
    rows = [r for r in H.run_parallel(one, items(["syn", "cdev", "ad"]), procs=14) if r]
    df = pd.DataFrame(rows)
    df.to_csv("results_v5_mat.csv", index=False)
    cols = [c for c in df.columns if c not in ("set", "rid")]
    print(df.groupby("set")[cols].mean().round(1).T.to_string())
