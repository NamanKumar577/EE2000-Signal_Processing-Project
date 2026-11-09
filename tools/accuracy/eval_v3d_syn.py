import sys, numpy as np, pandas as pd, harness as H, fe3, pipeline as P
V4 = "--v4" in sys.argv
def one(rec):
    d = H.load(rec)
    if d is None: return None
    X, fq = d["X"], d["fq"]; n = len(X)
    if V4:
        P.set_band(P.V4_BAND)
        (pk, fh), ch = fe3.system_hybrid(X, mat="dynamic", sel="both")
    else:
        (pk, fh), ch = fe3.system_hybrid(X)
    s = H.score(fq, pk, fh, n, 5000)
    return {"rid": rec.rid, "cond": rec.cond, "f1": s["f1"], "se": s["se"], "ppv": s["ppv"], "fhr_mae": s["fhr_mae"]}
if __name__ == "__main__":
    recs = H.list_records() if "--full" in sys.argv else H.list_records()[::7]
    df = pd.DataFrame([r for r in H.run_parallel(one, recs) if r]); df.to_csv("results_v4_syn.csv" if V4 else "results_hybrid_syn.csv", index=False)
    print(df[["f1","se","ppv","fhr_mae"]].mean().round(2).to_dict()); print(df.groupby("cond").f1.mean().round(1).to_dict())
    b = pd.read_csv("results_bitaccurate.csv").set_index("rid")
    print("v2 on same records:", b.loc[df.rid, "f1"].mean().round(2), b.loc[df.rid].groupby("cond").f1.mean().round(1).to_dict())
