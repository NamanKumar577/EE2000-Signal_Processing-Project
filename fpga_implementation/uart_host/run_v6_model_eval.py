#!/usr/bin/env python3
"""
Evaluate the final v6 design WITHOUT the board: runs the bit-accurate C system model
(fpga_implementation/v6/model/v6_sim.exe = RTL model + PC brain), which produces the same
output bytes as the Spartan-7 board, and scores it like run_v6_board_eval.py.

Usage: python run_v6_model_eval.py --sets cdev,ad[,ctest,syn] [--limit N] [--out results.csv]
Sets: syn (FECGSYNDB, every 21st record), cdev / ctest (CinC 2013 odd / even records), ad (ADFECGDB).
"""
import argparse
from pathlib import Path

import pandas as pd

from run_v6_board_eval import H, _load, items, model_stream, v5c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="cdev,ad")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    its = items(a.sets.split(","))
    if a.limit:
        its = its[:a.limit]
    rows = []
    for item in its:
        d = _load(item)
        if d is None:
            continue
        X, fq = d
        n = len(X)
        rid = item[1] if isinstance(item[1], str) else item[1].rid
        b, _ = model_stream(v5c.to_i16(X))
        pk, fhr = v5c.beats_to_stream(b, n)
        r = H.score(fq, pk, fhr, n, 5000)
        rows.append({"set": item[0], "rid": rid, "f1": r["f1"], "se": r["se"], "ppv": r["ppv"], "fhr_mae": r["fhr_mae"]})
        print(f"{item[0]:5s} {rid:24s} F1 {r['f1']:6.2f}  Se {r['se']:6.2f}  PPV {r['ppv']:6.2f}  FHR MAE {r['fhr_mae']:6.2f}",
              flush=True)
    df = pd.DataFrame(rows)
    if a.out:
        df.to_csv(Path(a.out), index=False)
    print(df.groupby("set")[["f1", "se", "ppv", "fhr_mae"]].mean().round(2).to_string())


if __name__ == "__main__":
    main()
