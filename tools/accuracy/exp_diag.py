"""
Diagnostics on the corrected causal baseline (E):
  E      : frozen calibrator + frozen detector, causal timeline, detector warm-up
           restarted 128 samples after the weights arrive.
  ORACLE : (diagnostic ONLY, uses true components, not deployable) the max-SINR
           4-channel spatial filter -> upper bound of what any 4-ch spatial
           filter can give with the frozen detector.
Also records detector-band SINR of the chosen projection.
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import eigh
from scipy.signal import sosfilt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import pipeline as P  # noqa: E402
from exp_baseline import calib_frozen  # noqa: E402

CAL_END = 1512
SETTLE = 128
DET0 = CAL_END + SETTLE
S0 = DET0 + 512


def run_w(X, w, n):
    W = np.zeros((n, X.shape[1]))
    W[:, 0] = 1.0
    W[CAL_END:] = w
    proj = np.einsum("nc,nc->n", X, W)
    fe, bp = P.front_end(proj)
    e = P.mwi(bp * bp, 30)
    comp, raw, fhr = P.detect(np.abs(bp), e, DET0, 512, 50, 26, 18, 50, 300, 0, 1.66)
    return comp, fhr


def bandf(Y):
    return sosfilt(P.BP_SOS, Y, axis=0)


def sinr(w, Fb, Ib):
    return 10 * np.log10(np.mean((Fb @ w) ** 2) / np.mean((Ib @ w) ** 2))


def one(rec):
    d = H.load(rec, components=True)
    if d is None:
        return None
    X, fq, mq = d["X"], d["fq"], d["mq"]
    n = len(X)
    out = {"rid": rec.rid, "sub": rec.sub, "snr": rec.snr, "lay": rec.lay, "cond": rec.cond}
    wq, j = calib_frozen(X[:CAL_END])
    w = np.asarray(wq, float) / 32768
    comp, fhr = run_w(X, w, n)
    s = H.score(fq, comp, fhr, n, S0, mq)
    out.update({f"E_{k}": v for k, v in s.items()})
    Fb = bandf(d["F"])[S0:]
    Ib = bandf(d["M"] + d["N"])[S0:]
    out["E_sinr"] = sinr(w, Fb, Ib)
    # oracle max-SINR filter (diagnostic only)
    Cf = Fb.T @ Fb
    Ci = Ib.T @ Ib
    vals, vecs = eigh(Cf, Ci)
    wo = vecs[:, -1]
    wo = wo / np.linalg.norm(wo)
    out["O_sinr"] = sinr(wo, Fb, Ib)
    comp, fhr = run_w(X, wo, n)
    s = H.score(fq, comp, fhr, n, S0, mq)
    out.update({f"O_{k}": v for k, v in s.items()})
    # oracle-weights detector ceiling with pure fetal signal (detector-only errors)
    return out


if __name__ == "__main__":
    recs = H.list_records()
    t0 = time.time()
    rows = [r for r in H.run_parallel(one, recs) if r is not None]
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "results_diag.csv", index=False)
    print(f"{len(df)} records, {time.time()-t0:.0f}s")
    for v in ["E", "O"]:
        print(v, df[[f"{v}_f1", f"{v}_se", f"{v}_ppv", f"{v}_fhr_mae", f"{v}_fhr_within5", f"{v}_sinr"]].mean().round(2).to_dict())
        print("  by cond", df.groupby("cond")[f"{v}_f1"].mean().round(1).to_dict())
        print("  by snr ", df.groupby("snr")[f"{v}_f1"].mean().round(1).to_dict())
    print("E fp maternal share:", (df.E_fp_maternal.sum() / max(df.E_fp.sum(), 1)).round(3))
