"""
NIFEA (real, no fetal annotations): surrogate metrics for v4 with and without the
maternal chest lead.  v2 / old columns come from results_nifea.csv (eval_nifea.py).
  v4      : abdominal leads only
  v4chest : maternal peaks from the chest lead -> template canceller
  v4both  : + causal NLMS adaptive cancellation from the chest lead
Note: the maternal-coincidence surrogate also uses the chest lead, so it is not
independent of the v4chest variants.
"""
import numpy as np
import pandas as pd

import harness as H
import fe3
import pipeline as P
from eval_nifea import load, maternal_ref, surrogate, NIFEA, DUPES, HERE

VARIANTS = {"v4": None, "v4chest": "template", "v4both": "both"}


def one(rid):
    P.set_band(P.V4_BAND)
    X, thor = load(rid)
    n = len(X)
    mpk = maternal_ref(thor)
    out = {"record": rid}
    for name, chest in VARIANTS.items():
        (pk, fhr), _ = fe3.system_hybrid(X, mat="dynamic", sel="both", thor=None if chest is None else thor,
                                         chest=chest or "template")
        out.update({f"{name}_{k}": v for k, v in surrogate(pk, fhr * 10, mpk, n).items()})
    return out


if __name__ == "__main__":
    ids = sorted(p.stem for p in NIFEA.glob("*.hea") if p.stem not in DUPES)
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12))
    old = pd.read_csv(HERE / "results_nifea.csv")
    df = old.merge(df, on="record")
    df.to_csv(HERE / "results_nifea_v4.csv", index=False)
    pd.set_option("display.width", 250)
    names = ["v2"] + list(VARIANTS)
    print(df[["record", "maternal_hr"] + [f"{a}_median_fhr" for a in names] + [f"{a}_fhr_110_160_pct" for a in names]].round(1).to_string(index=False))
    for a in names:
        ok = (df[f"{a}_maternal_coinc_pct"] < 30) & (df[f"{a}_fhr_110_160_pct"] >= 70) & (df[f"{a}_median_fhr"].between(105, 180))
        print(f"{a:8s} maternal coinc {df[f'{a}_maternal_coinc_pct'].mean():5.1f}%  FHR in 110-160 {df[f'{a}_fhr_110_160_pct'].mean():5.1f}%  "
              f"in 100-180 {df[f'{a}_fhr_100_180_pct'].mean():5.1f}%  median RR CV {df[f'{a}_rr_cv'].median():.2f}  plausible {ok.sum()}/{len(df)}")
