import sys, numpy as np, pandas as pd, harness as H, fe3
from eval_cinc2013 import load
v2 = pd.read_csv("results_cinc2013.csv").set_index("record")["v2_f1"]
def one(rid):
    X, fq = load(rid); n = len(X); out = {"record": rid, "v2": v2[rid]}
    (comp, fhr), (Z, mpk, w) = fe3.system_v3b(X)
    out["lf_thr"] = H.score(fq, comp, fhr, n, 5000)["f1"]
    wo = fe3.oracle_filter(Z, fq)
    for tag, ww in (("orc", wo), ("lf", w)):
        y = fe3.project(Z, ww, 3750)
        for tf in (0.15, 0.3):
            pk, fh = fe3.track_beats(y, 3877, mpk=mpk, thr_frac=tf)
            out[f"{tag}_trk{tf}"] = H.score(fq, pk, fh, n, 5000)["f1"]
    return out
if __name__ == "__main__":
    ids = fe3.CINC_TEST if "--test" in sys.argv else fe3.CINC_DEV
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12))
    df.to_csv("results_track_" + ("test" if "--test" in sys.argv else "dev") + ".csv", index=False)
    print(df.drop(columns="record").mean().round(2).to_dict())
