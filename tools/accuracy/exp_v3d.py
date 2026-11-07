import sys, numpy as np, pandas as pd, harness as H, fe3
from eval_cinc2013 import load
def one(rid):
    X, fq = load(rid); n = len(X); out = {"record": rid}
    for hop, look in ((1250, 2500), (625, 1875), (1250, 3750)):
        (pk, fh), ch = fe3.system_v3d(X, hop=hop, look=look)
        out[f"d_{hop}_{look}"] = H.score(fq, pk, fh, n, 5000)["f1"]
    return out
if __name__ == "__main__":
    ids = fe3.CINC_TEST if "--test" in sys.argv else fe3.CINC_DEV
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12))
    print(df.drop(columns="record").mean().round(2).to_dict())
