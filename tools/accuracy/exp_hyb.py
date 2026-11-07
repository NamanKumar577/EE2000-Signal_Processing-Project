import sys, numpy as np, pandas as pd, harness as H, fe3
from eval_cinc2013 import load
B = (1.0, 1.5)
def cinc(rid):
    X, fq = load(rid); n = len(X); o = {"id": rid}
    for b in B: o[f"b{b}"] = H.score(fq, *fe3.system_hybrid(X, v2_bonus=b)[0], n, 5000)["f1"]
    return o
def syn(rec):
    d = H.load(rec); X, fq = d["X"], d["fq"]; n = len(X); o = {"id": rec.rid, "cond": rec.cond}
    for b in B: o[f"b{b}"] = H.score(fq, *fe3.system_hybrid(X, v2_bonus=b)[0], n, 5000)["f1"]
    return o
if __name__ == "__main__":
    a = pd.DataFrame(H.run_parallel(cinc, fe3.CINC_DEV, procs=12)); print("CinC dev", a.drop(columns="id").mean().round(2).to_dict())
    s = pd.DataFrame(H.run_parallel(syn, H.list_records()[::7])); print("FECGSYNDB quick", s.drop(columns=["id","cond"]).mean().round(2).to_dict(), s.groupby("cond")[[f"b{b}" for b in B]].mean().round(1).to_dict())
