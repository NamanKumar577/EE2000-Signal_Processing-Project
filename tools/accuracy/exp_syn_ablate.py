"""Ablation of the v4 changes on a FECGSYNDB subset (every 21st record)."""
import sys
import pandas as pd
import harness as H
import fe3
import pipeline as P

VAR = {
    "v3":        (None, "robust", "quality"),
    "band":      (P.V4_BAND, "robust", "quality"),
    "matdyn":    (None, "dynamic", "quality"),
    "sel":       (None, "robust", "both"),
    "v4":        (P.V4_BAND, "dynamic", "both"),
}


def one(rec):
    d = H.load(rec)
    if d is None:
        return None
    X, fq = d["X"], d["fq"]
    n = len(X)
    out = {"rid": rec.rid, "cond": rec.cond}
    for k, (band, mat, sel) in VAR.items():
        P.set_band(band)
        (pk, fh), _ = fe3.system_hybrid(X, mat=mat, sel=sel)
        out[k] = H.score(fq, pk, fh, n, 5000)["f1"]
    return out


if __name__ == "__main__":
    step = int(sys.argv[1]) if len(sys.argv) > 1 else 21
    df = pd.DataFrame([r for r in H.run_parallel(one, H.list_records()[::step]) if r])
    print(len(df), "records")
    print(df[list(VAR)].mean().round(2).to_string())
    print(df.groupby("cond")[list(VAR)].mean().round(1).to_string())
