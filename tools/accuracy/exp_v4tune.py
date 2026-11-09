"""Selection-rule sweep on ADFECGDB and a FECGSYNDB subset (tracks computed once)."""
import sys
import pandas as pd
import harness as H
import fe3
import pipeline as P
import adfecgdb as A

RULES = [("quality", 0), ("both", 0), ("both", 0.25), ("both", 0.5), ("both", 1.0)]


def run(X, fq, out):
    n = len(X)
    P.set_band(P.V4_BAND)
    for mat in ("robust", "dynamic"):
        tr = fe3.hybrid_tracks(X, mat=mat)
        for sel, a in RULES:
            (pk, fh), _ = fe3.select_tracks(tr, n, 4877, sel=sel, agr_floor=a)
            out[f"{mat[0]}_{sel}{a}"] = H.score(fq, pk, fh, n, 5000)["f1"]
    return out


def one_ad(rid):
    X, fq = A.load(rid)
    return run(X, fq, {"rid": rid, "cond": "ad"})


def one_syn(rec):
    d = H.load(rec)
    return None if d is None else run(d["X"], d["fq"], {"rid": rec.rid, "cond": rec.cond})


if __name__ == "__main__":
    ad = pd.DataFrame(H.run_parallel(one_ad, A.RECORDS, procs=5))
    syn = pd.DataFrame([r for r in H.run_parallel(one_syn, H.list_records()[::21]) if r])
    cols = [c for c in ad.columns if c not in ("rid", "cond")]
    pd.set_option("display.width", 250)
    print("ADFECGDB\n", ad[cols].mean().round(2).to_string())
    print("FECGSYNDB subset\n", syn[cols].mean().round(2).to_string())
    print(syn.groupby("cond")[cols].mean().round(1).T.to_string())
