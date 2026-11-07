import pandas as pd, harness as H, fe3
from eval_cinc2013 import load
def one(rid):
    X, fq = load(rid); n = len(X); s = H.score(fq, *fe3.system_hybrid(X)[0], n, 5000)
    return dict(record=rid, f1=s["f1"], fhr=s["fhr_mae"], w5=s["fhr_within5"])
if __name__ == "__main__":
    d = pd.DataFrame(H.run_parallel(one, fe3.CINC_TEST, procs=12)); print("CinC test hybrid", d.drop(columns="record").mean().round(2).to_dict())
    v = pd.read_csv("results_cinc2013.csv").set_index("record").loc[fe3.CINC_TEST]; print("CinC test v2 F1", v.v2_f1.mean().round(2), "FHR MAE", v.v2_fhr_mae.mean().round(2))
