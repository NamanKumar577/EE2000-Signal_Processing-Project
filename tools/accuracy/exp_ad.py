"""ADFECGDB development comparisons of system_hybrid variants (prints mean F1 per variant)."""
import sys
import numpy as np
import pandas as pd
import harness as H
import fe3
import adfecgdb as A

import pipeline as P
set_band = P.set_band

VARIANTS = {k: ({"mat": "dynamic"}, b) for k, b in {
    "def": None, "w60_15_50": (60, 15, 50, 0), "w60_15_50n": (60, 15, 50, 50),
    "w60_12_45n": (60, 12, 45, 50), "w50_15_45": (50, 15, 45, 0), "w60_15_40": (60, 15, 40, 0)}.items()}


def one(rid):
    X, fq = A.load(rid)
    n = len(X)
    out = {"record": rid}
    for name, (kw, b) in VARIANTS.items():
        set_band(b)
        (pk, fhr), _ = fe3.system_hybrid(X, **kw)
        s = H.score(fq, pk, fhr, n, 5000)
        out[name] = s["f1"]
        out[name + "_mae"] = s["fhr_mae"]
    return out


if __name__ == "__main__":
    df = pd.DataFrame(H.run_parallel(one, A.RECORDS, procs=5))
    print(df.round(1).to_string(index=False))
    print(df.drop(columns=["record"]).mean().round(2).to_string())
