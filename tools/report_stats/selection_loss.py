#!/usr/bin/env python3
"""Selection loss vs candidate quality of v7-DL on the development sets.
Input: tools/accuracy/_taps/results.csv, variant 'base' (byte-identical to the v7-DL C model; dev sets only:
FECGSYNDB subset 60, CinC dev 38, ADFECGDB 5). Columns: f1 (final), best_track (best single track per record),
win_oracle (best track per 5-s window). Paired bootstrap 95% CIs over records (10,000, seed 2026).
Output: tools/report_stats/out/selection_loss.csv
    venv/Scripts/python.exe tools/report_stats/selection_loss.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
d = pd.read_csv(ROOT / "tools/accuracy/_taps/results.csv")
d = d[d.variant == "base"]


def ci(x):
    rng = np.random.default_rng(2026)
    bs = rng.choice(x, (10000, len(x)), replace=True).mean(1)
    return np.percentile(bs, [2.5, 97.5])


rows = []
for s, g in d.groupby("set"):
    r = dict(set=s, n=len(g), final=g.f1.mean(), best_track=g.best_track.mean(), oracle=g.win_oracle.mean())
    for nm, x in [("sel_loss_best", g.best_track - g.f1), ("sel_loss_oracle", g.win_oracle - g.f1), ("cand_loss", 100 - g.best_track)]:
        lo, hi = ci(x.to_numpy())
        r[nm], r[nm + "_lo"], r[nm + "_hi"] = x.mean(), lo, hi
    rows.append(r)
df = pd.DataFrame(rows)
df.to_csv(OUT / "selection_loss.csv", index=False, float_format="%.2f")
print(df.round(2).to_string(index=False))
