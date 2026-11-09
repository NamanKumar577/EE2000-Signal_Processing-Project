"""v5 port-simplification ablation (dev sets only): which v4 parts matter?
Tracks computed once per record; selection run on candidate subsets."""
import sys
import numpy as np
import pandas as pd
import harness as H
import fe3
import pipeline as P
from devbench import _load, items

SUBSETS = {
    "full": lambda tr: tr,
    "no_v2": lambda tr: tr[1:],
    "no_gevd": lambda tr: tr[:9],
    "no_v2_gevd": lambda tr: tr[1:9],
    "pca_only": lambda tr: tr[5:9],
    "leads_gevd": lambda tr: tr[1:5] + tr[9:],
}


def one(item):
    d = _load(item)
    if d is None:
        return None
    X, fq = d
    n = len(X)
    out = {"set": item[0], "rid": item[1] if isinstance(item[1], str) else item[1].rid}
    P.set_band(P.V4_BAND)
    for mat in ("robust", "dynamic"):
        tr = fe3.hybrid_tracks(X, mat=mat)
        for name, f in SUBSETS.items():
            for sel in ("quality", "both"):
                (pk, fh), _ = fe3.select_tracks(f(tr), n, 4877, sel=sel)
                out[f"{mat[0]}_{name}_{sel[0]}"] = H.score(fq, pk, fh, n, 5000)["f1"]
    return out


if __name__ == "__main__":
    rows = [r for r in H.run_parallel(one, items(["syn", "cdev", "ad"]), procs=14) if r]
    df = pd.DataFrame(rows)
    df.to_csv("results_v5_ablate.csv", index=False)
    cols = [c for c in df.columns if c not in ("set", "rid")]
    pd.set_option("display.width", 250)
    print(df.groupby("set")[cols].mean().round(1).T.to_string())
