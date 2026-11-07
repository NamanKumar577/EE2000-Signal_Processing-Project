import sys, numpy as np, pandas as pd, harness as H, fe3
from eval_cinc2013 import load
VARS = {"v3_nc1": dict(ncomp=1), "v3_nc3": dict(ncomp=3), "v3_nc3_pc1mat": dict(ncomp=3, robust_mat=False), "v3_nc2": dict(ncomp=2)}
def one(rid):
    X, fq = load(rid); n = len(X); out = {"record": rid}
    for k, kw in VARS.items():
        out[k] = H.score(fq, *fe3.system_v3(X, **kw), n, 5000)["f1"]
    return out
if __name__ == "__main__":
    ids = fe3.CINC_TEST if "--test" in sys.argv else fe3.CINC_DEV
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12))
    print(df.round(1).to_string(index=False)); print(df.drop(columns=["record"]).mean().round(2).to_dict())
