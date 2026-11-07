import sys, numpy as np, pandas as pd, harness as H, fe3
from eval_cinc2013 import load
v2 = pd.read_csv("results_cinc2013.csv").set_index("record")["v2_f1"]
WINS = [(0, 45), (5, 40), (0, 55)]
def one(rid):
    X, fq = load(rid); n = len(X); out = {"record": rid, "v2": v2[rid]}
    (comp, fhr), (Z, mpk, w) = fe3.system_v3b(X)
    wo = fe3.oracle_filter(Z, fq); yo = fe3.project(Z, wo, 3750); yl = fe3.project(Z, w, 3750)
    for a, b in WINS:
        out[f"orc_{a}_{b}"] = H.score(fq, *fe3.detect_blanked(yo, mpk, 3877, a, b), n, 5000)["f1"]
        out[f"lf_{a}_{b}"] = H.score(fq, *fe3.detect_blanked(yl, mpk, 3877, a, b), n, 5000)["f1"]
    return out
if __name__ == "__main__":
    ids = fe3.CINC_TEST if "--test" in sys.argv else fe3.CINC_DEV
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12))
    df.to_csv("results_v3b_" + ("test" if "--test" in sys.argv else "dev") + ".csv", index=False)
    print(df.drop(columns="record").mean().round(2).to_dict())
