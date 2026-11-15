#!/usr/bin/env python3
"""
F1 against output delay for v7-DL (C model, DEV sets only): sweeps the future window V7_WF
(segments of 2.5 s) with everything else frozen, and adds the causal v6.1 point.

    python v7_delay_sweep.py            -> results_v7_delay_sweep.csv (per record) and a summary

Delay per record comes from the model's own histogram (env V7_DELAY: total, median, p99, max in
0.1-s bins). Summary: median of the per-record medians, maximum of the per-record maxima.
"""
import os
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

import harness as H
import v5c
from devbench import items
from devbench_v6 import CACHE, build, prep

HERE = Path(__file__).resolve().parent
VARIANTS = ([("v61", "-DV61")] + [(f"wf{w}", f"-DV7 -DV7_WF={w}") for w in (0, 1, 2, 3, 4, 5)]
            + [(f"wf{w}_dl{d}", f"-DV7 -DV7_WF={w} -DV7_DL={d * 250}") for w, d in ((0, 5), (0, 10), (1, 10), (2, 12))])


def run_one(args):
    name, exe, key = args
    f = CACHE / f"{key}.i16"
    fq = np.load(CACHE / f"{key}.fq.npy")
    n = f.stat().st_size // 8
    r = subprocess.run([str(exe), str(f)], capture_output=True, text=True, check=True,
                       env=dict(os.environ, V7_DELAY="1"))
    b = np.array([list(map(int, l.split())) for l in r.stdout.splitlines() if l.strip()], dtype=np.int64).reshape(-1, 3)
    pk, fhr = v5c.beats_to_stream(b, n)
    s = H.score(fq, pk, fhr, n, 5000)
    med = mx = np.nan
    for l in r.stderr.splitlines():
        if l.startswith("v7 delay"):
            tot, m, _, x = map(int, l.split()[2:])
            if tot:
                med, mx = m / 10.0, x / 10.0
    st, rid = key.split("_", 1)
    return {"variant": name, "set": st, "rid": rid, "f1": s["f1"], "fhr_mae": s["fhr_mae"], "delay_med": med, "delay_max": mx}


def main():
    sets = ["syn", "cdev", "ad"]
    exes = [(n, build(f"dsw_{n}", fl)) for n, fl in VARIANTS]
    with Pool(12) as p:
        keys = [k for k in p.map(prep, items(sets)) if k]
        rows = p.map(run_one, [(n, e, k) for n, e in exes for k in keys])
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "results_v7_delay_sweep.csv", index=False)
    f1 = df.pivot_table(index="variant", columns="set", values="f1", aggfunc="mean")
    dl = df.groupby("variant").agg(delay_med=("delay_med", "median"), delay_max=("delay_max", "max"))
    print(f1.join(dl).reindex([n for n, _ in VARIANTS]).round(2).to_string())


if __name__ == "__main__":
    sys.exit(main())
