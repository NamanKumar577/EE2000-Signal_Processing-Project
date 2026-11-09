"""Selection-rule comparison on ADFECGDB (tracks computed once per record)."""
import numpy as np
import pandas as pd
import harness as H
import fe3
import adfecgdb as A
from exp_ad import set_band

RULES = [("quality", 2500), ("agree", 2500), ("both", 2500), ("agree", 1250), ("both", 1250), ("agree", 5000), ("both", 5000)]


def one(rid):
    set_band((60, 15, 40, 0))
    X, fq = A.load(rid)
    n = len(X)
    tr = fe3.hybrid_tracks(X, mat="dynamic")
    out = {"record": rid}
    for sel, look in RULES:
        (pk, fhr), _ = fe3.select_tracks(tr, n, 4877, look=look, sel=sel)
        s = H.score(fq, pk, fhr, n, 5000)
        out[f"{sel}{look}"] = s["f1"]
    return out


if __name__ == "__main__":
    df = pd.DataFrame(H.run_parallel(one, A.RECORDS, procs=5))
    print(df.round(1).to_string(index=False))
    print(df.drop(columns=["record"]).mean().round(2).to_string())
