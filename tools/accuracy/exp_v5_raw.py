"""Can self-calibrated raw-lead candidates replace the v2 host-beamformer track?
(dev sets only).  Extra tracks are computed on the un-cancelled leads Xf."""
import numpy as np
import pandas as pd
from scipy.signal import sosfilt
import harness as H
import fe3
import pipeline as P
from devbench import _load, items


def raw_tracks(X, Xf, mpk, cal_begin=750, cal_end=3750, det="track"):
    out = []
    for w in fe3.candidates_residual(Xf, mpk, cal_begin, cal_end)[8:]:   # 4 GEVD-refined on raw leads
        y = fe3.project(Xf, w, cal_end)
        bp = sosfilt(P.BP_SOS, y)
        e = P.mwi(bp * bp, 30)
        if det == "track":
            pk, _ = fe3.track_beats(y, cal_end + 127, mpk=None, latency=0)
        else:
            _, pk, _ = P.detect2(np.abs(bp), e, cal_end + 127, 512, 50, 26, 0, 50, 300,
                                 0, 0.5, 0.6, 1.4, 1.5, 0.0, 0.0)
        out.append((pk, bp, e))
    return out


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
    V = {"full": tr, "nov2": tr[1:], "nov2+rawT": tr[1:] + rt, "nov2+rawD": tr[1:] + rd,
         "nov2+rawTD": tr[1:] + rt + rd, "full+rawT": tr + rt}
    for name, t in V.items():
        for sel in ("quality", "both"):
            (pk, fh), _ = fe3.select_tracks(t, n, 4877, sel=sel)
            out[f"{name}_{sel[0]}"] = H.score(fq, pk, fh, n, 5000)["f1"]
    return out


if __name__ == "__main__":
    rows = [r for r in H.run_parallel(one, items(["syn", "cdev", "ad"]), procs=14) if r]
    df = pd.DataFrame(rows)
    df.to_csv("results_v5_raw.csv", index=False)
    cols = [c for c in df.columns if c not in ("set", "rid")]
    print(df.groupby("set")[cols].mean().round(1).T.to_string())
