"""Does (causal) maternal template subtraction raise the real-data ceiling?"""
import numpy as np, pandas as pd
from scipy.signal import sosfilt
import harness as H, exp_cinc as E, pipeline as P
from fecg.host import adaptive_beamformer as AB

def mts2(X, mpk, L1=40, L2=110, alpha=1/8, search=5, warm=3):
    """Per-lead causal template subtraction on HP1+LP40 leads. Template = EMA of
    PAST beats; each beat aligned to the template (+-search samples, all leads
    jointly) and amplitude-matched per lead. Output delay = L2 samples."""
    Xf = sosfilt(P.LP_SOS, P.hp1(X), axis=0)
    out = Xf.copy(); n = len(X); T = None; k = 0
    for p in mpk:
        if p - L1 - search < 0 or p + L2 + search > n: continue
        if T is not None and k >= warm:
            best, bl = -np.inf, 0
            for lag in range(-search, search + 1):
                s = Xf[p + lag - L1:p + lag + L2]
                c = np.sum(s * T)
                if c > best: best, bl = c, lag
            p = p + bl
        seg = Xf[p - L1:p + L2]
        if T is None:
            T = seg.copy()
        else:
            if k >= warm:
                g = np.clip(np.sum(seg * T, 0) / np.maximum(np.sum(T * T, 0), 1e-9), 0.6, 1.4)
                out[p - L1:p + L2] = seg - T * g
            T = T + alpha * (seg - T)
        k += 1
    return out

def one(rid):
    X, fq = E.load(rid); n = len(X)
    mpk = E.maternal_detect_causal(X)
    Xc = mts2(X, mpk)
    Yr = AB.band(X); Yc = AB.band(Xc)
    idx = (mpk[mpk > 3000][:, None] + np.arange(-10, 40)[None, :]).ravel(); idx = idx[idx < n]
    red = 10 * np.log10(np.sum(Yr[idx] ** 2) / max(np.sum(Yc[idx] ** 2), 1e-9))
    f = lambda Z, w: H.score(fq, *E.run_static(Z, w, n), n, 5000)["f1"]
    w_c, _ = AB.calibrate(Xc[:3000])
    return dict(record=rid, unreliable=rid in E.UNRELIABLE, red_db=round(red, 1),
                oracle_raw=f(X, E.oracle_w(X, fq + 14, n)), oracle_mts=f(Xc, E.oracle_w(Xc, fq + 14, n)),
                v2_mts=f(Xc, w_c))

if __name__ == "__main__":
    df = pd.DataFrame(H.run_parallel(one, [f"a{i:02d}" for i in range(1, 76)], procs=12))
    df.to_csv("results_mts_cinc.csv", index=False)
    print(df[["red_db", "oracle_raw", "oracle_mts", "v2_mts"]].describe().round(1).loc[["mean", "50%"]])
    print("reliable", df[~df.unreliable][["oracle_raw", "oracle_mts", "v2_mts"]].mean().round(2).to_dict())
