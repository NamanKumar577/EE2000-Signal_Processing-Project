import sys, numpy as np, pandas as pd, harness as H, fe3
from eval_cinc2013 import load, UNRELIABLE
v2 = pd.read_csv("results_cinc2013.csv").set_index("record")
def one(rid):
    X, fq = load(rid); n = len(X)
    (pk, fh), ch = fe3.system_hybrid(X)
    s = H.score(fq, pk, fh, n, 5000)
    return {"record": rid, "unreliable": rid in UNRELIABLE, "v2_f1": v2.loc[rid, "v2_f1"], "v3_f1": s["f1"],
            "v3_se": s["se"], "v3_ppv": s["ppv"], "v3_tp": s["tp"], "v3_fp": s["fp"], "v3_fn": s["fn"],
            "v2_tp": v2.loc[rid, "v2_tp"], "v2_fp": v2.loc[rid, "v2_fp"], "v2_fn": v2.loc[rid, "v2_fn"]}
if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else "test"
    ids = {"test": fe3.CINC_TEST, "dev": fe3.CINC_DEV, "all": fe3.CINC_DEV + fe3.CINC_TEST}[split]
    df = pd.DataFrame(H.run_parallel(one, ids, procs=12)); df.to_csv(f"results_hybrid_{split}.csv", index=False)
    for lab, d in (("all", df), ("reliable", df[~df.unreliable])):
        for a in ("v2", "v3"):
            tp, fp, fn = d[f"{a}_tp"].sum(), d[f"{a}_fp"].sum(), d[f"{a}_fn"].sum()
            print(f"{split}/{lab:8s} {a}: mean F1 {d[f'{a}_f1'].mean():6.2f} pooled F1 {200*tp/(2*tp+fp+fn):6.2f} n={len(d)} >=90%: {(d[f'{a}_f1']>=90).sum()}")
