#!/usr/bin/env python3
"""Maternal-fetal QRS collisions counted from FECGSYNDB reference annotations (snr12dB folder; annotations
do not depend on SNR). A fetal beat collides if its R peak is within (w_m + w_f)/2 = 70 ms of a maternal R peak.
Predicted rate per record: (w_m + w_f) / T_m with T_m the record's mean maternal RR.
Output: tools/report_stats/out/collisions.csv (per record) and a summary on stdout.
    venv/Scripts/python.exe tools/report_stats/collisions.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import wfdb

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
WM, WF = 0.090, 0.050
rows = []
for h in sorted((ROOT / "data/FECGSD/DESTINATION").glob("sub*/snr12dB/*_mecg.hea")):
    base = str(h)[:-9]
    rid = Path(base).name
    try:
        m = wfdb.rdann(base + "_mecg", "qrs")
        f = wfdb.rdann(base + "_fecg1", "qrs")
    except Exception:
        continue
    fs = m.fs or 250
    tm, tf = m.sample / fs, f.sample / fs
    if len(tm) < 3 or len(tf) < 3:
        continue
    idx = np.clip(np.searchsorted(tm, tf), 1, len(tm) - 1)
    d = np.minimum(np.abs(tf - tm[idx - 1]), np.abs(tf - tm[idx]))
    Tm = np.diff(tm).mean()
    rows.append(dict(rid=rid, cond=rid.split("_")[-1], n_fetal=len(tf), measured=(d < (WM + WF) / 2).mean(),
                     predicted=(WM + WF) / Tm, mean_mrr_s=Tm))
df = pd.DataFrame(rows)
df.to_csv(OUT / "collisions.csv", index=False, float_format="%.4f")
print(f"records {len(df)}  measured {100*df.measured.mean():.1f}%  predicted {100*df.predicted.mean():.1f}%  "
      f"mean maternal RR {1000*df.mean_mrr_s.mean():.0f} ms  pooled measured "
      f"{100*(df.measured*df.n_fetal).sum()/df.n_fetal.sum():.1f}%")
print((df.groupby("cond")[["measured", "predicted"]].mean() * 100).round(1).to_string())
