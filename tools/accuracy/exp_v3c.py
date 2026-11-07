import sys, numpy as np, pandas as pd, harness as H, fe3
from eval_cinc2013 import load
v2 = pd.read_csv("results_cinc2013.csv").set_index("record")["v2_f1"]
def one(rid):
    X, fq = load(rid); n = len(X)
    (pk, fh), (Z, mpk, w, q) = fe3.system_v3c(X)
    s = H.score(fq, pk, fh, n, 5000)
    return {"record": rid, "v2": v2[rid], "v3c": s["f1"], "se": s["se"], "ppv": s["ppv"], "fhr_mae": s["fhr_mae"], "q": q}
if __name__ == "__main__":
    ids = fe3.CINC_TEST if "--test" in sys.argv else fe3.CINC_DEV
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12))
    df.to_csv("results_v3c_" + ("test" if "--test" in sys.argv else "dev") + ".csv", index=False)
    print(df.drop(columns="record").mean().round(2).to_dict(), " >=90:", (df.v3c >= 90).sum(), "/", len(df))
