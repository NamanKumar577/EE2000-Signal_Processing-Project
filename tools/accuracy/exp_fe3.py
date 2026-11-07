"""Stage-1 diagnostics of front end v3 on CinC dev split (odd records)."""
import sys
import numpy as np
import pandas as pd

import harness as H
import fe3
from eval_cinc2013 import load

SCORE0 = 5000
EXTRA_DELAY = 0    # cancellation delay is applied offline; scoring times unchanged


def one(rid):
    X, fq = load(rid)
    n = len(X)
    Xf = fe3.prefilter(X)
    mpk, y = fe3.maternal_peaks_causal(X)
    out = {"record": rid, "mhr": round(60 * 250 / np.median(np.diff(mpk)), 1) if len(mpk) > 3 else 0}
    # fetal-in-maternal-train contamination (how many maternal detections are fetal beats)
    j = np.searchsorted(fq, mpk)
    d = np.minimum(np.abs(mpk - fq[np.clip(j - 1, 0, len(fq) - 1)]), np.abs(mpk - fq[np.clip(j, 0, len(fq) - 1)]))
    out["mat_on_fetal_pct"] = round(100 * float(np.mean(d <= 5)), 1)
    variants = {"raw": Xf}
    for nc in (1, 3):
        variants[f"ts{nc}"] = fe3.cancel_maternal(Xf, mpk, ncomp=nc)
    for name, Z in variants.items():
        # maternal residual reduction in detector band
        B0 = fe3.band(Xf)
        B1 = fe3.band(Z)
        idx = (mpk[mpk > 3000][:, None] + np.arange(-10, 40)[None, :]).ravel()
        idx = idx[idx < n]
        out[f"{name}_red"] = round(10 * np.log10(np.sum(B0[idx] ** 2) / max(np.sum(B1[idx] ** 2), 1e-12)), 1)
        w = fe3.oracle_filter(Z, fq)
        comp, fhr = fe3.detect_on_lead(Z @ w, 3127)
        out[f"{name}_orcF1"] = H.score(fq, comp, fhr, n, SCORE0)["f1"]
        # best single lead (oracle choice, diagnostic)
        out[f"{name}_bestlead"] = max(H.score(fq, *fe3.detect_on_lead(Z[:, m], 3127), n, SCORE0)["f1"] for m in range(Z.shape[1]))
    return out


if __name__ == "__main__":
    ids = fe3.CINC_DEV if "--test" not in sys.argv else fe3.CINC_TEST
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12))
    pd.set_option("display.width", 250)
    print(df.round(1).to_string(index=False))
    print(df.drop(columns=["record"]).mean().round(2).to_string())
