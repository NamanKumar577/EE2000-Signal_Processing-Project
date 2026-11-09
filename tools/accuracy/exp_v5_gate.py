"""Selection with a label-free maternal-coincidence penalty, so raw-lead candidates
(which can lock onto the mother) are safe to add.  Dev sets only."""
import numpy as np
import pandas as pd
import harness as H
import fe3
import pipeline as P
from devbench import _load, items
from exp_v5_raw import raw_tracks


def coinc(pk, mpk, tol=12):
    if len(pk) == 0 or len(mpk) == 0:
        return 0.0
    j = np.clip(np.searchsorted(mpk, pk), 1, len(mpk) - 1)
    d = np.minimum(np.abs(mpk[j] - pk), np.abs(mpk[j - 1] - pk))
    return float(np.mean(d <= tol))


def select(tracks, mpk, n, t_start, hop=1250, look=2500, sel="quality", c0=0.2, c1=0.5, gate=1e9):
    out = []
    t = t_start
    while t < n:
        t0 = max(0, t - look)
        qs = []
        for k, (pk, bp, e) in enumerate(tracks):
            q = fe3.window_quality(bp, e, pk, t0, t)
            if sel == "both":
                p = pk[(pk >= t0) & (pk < t)]
                R = np.median(np.diff(p)) if len(p) > 3 else 1e9
                acc = min(1.0, len(p) / max((t - t0) / R, 1)) if 60 * 250 / R >= 80 else 0.0
                q *= fe3.window_agreement(tracks, k, t0, t) * acc
            if c1 > c0:
                p = pk[(pk >= t0) & (pk < t)]
                m = mpk[(mpk >= t0 - 20) & (mpk < t + 20)]
                c = coinc(p, m)
                mr = 60 * 250 / np.median(np.diff(m)) if len(m) > 3 else 1e9
                if mr < gate:
                    q *= float(np.clip((c1 - c) / (c1 - c0), 0, 1))
            qs.append(q)
        k = int(np.argmax(qs))
        pk = tracks[k][0]
        out.extend(pk[(pk >= t) & (pk < t + hop)].tolist())
        t += hop
    peaks = np.maximum(0, np.array(sorted(out), np.int64) - 13)
    return peaks, fe3.fhr_median5(peaks, n)


def one(item):
    d = _load(item)
    if d is None:
        return None
    X, fq = d
    n = len(X)
    out = {"set": item[0], "rid": item[1] if isinstance(item[1], str) else item[1].rid}
    P.set_band(P.V4_BAND)
    tr = fe3.hybrid_tracks(X, mat="dynamic")
    Xf = fe3.prefilter(X)
    mpk, _ = fe3.maternal_peaks_dynamic(X)
    rt = raw_tracks(X, Xf, mpk, det="track")
    rd = raw_tracks(X, Xf, mpk, det="det")
    V = {"full": tr, "nov2+rawTD": tr[1:] + rt + rd, "full+rawT": tr + rt, "full+rawTD": tr + rt + rd}
    for name, t in V.items():
        for sel in ("quality",):
            for gate in (95, 105, 115):
                pk, fh = select(t, mpk, n, 4877, sel=sel, c0=0.3, c1=0.6, gate=gate)
                out[f"{name}_g{gate}"] = H.score(fq, pk, fh, n, 5000)["f1"]
    return out


if __name__ == "__main__":
    rows = [r for r in H.run_parallel(one, items(["syn", "cdev", "ad"]), procs=14) if r]
    df = pd.DataFrame(rows)
    df.to_csv("results_v5_gate.csv", index=False)
    cols = [c for c in df.columns if c not in ("set", "rid")]
    print(df.groupby("set")[cols].mean().round(1).T.to_string())
