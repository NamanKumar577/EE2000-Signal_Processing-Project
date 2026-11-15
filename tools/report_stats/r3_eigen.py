"""R3 replication: 4-lead covariance eigen-energy shares on FECGSYNDB training subjects (sub01-sub07, snr12dB, l1, c0),
plus the R5 median of fixed template subtraction. Output: tools/report_stats/out/r3_eigen.csv, out/r5_median.csv"""
from pathlib import Path
import numpy as np
import pandas as pd
import wfdb

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
LEADS = [27, 26, 28, 25]
rows = []
for s in range(1, 8):
    b = ROOT / f"data/FECGSD/DESTINATION/sub{s:02d}/snr12dB/sub{s:02d}_snr12dB_l1_c0"
    comp = {k: wfdb.rdrecord(f"{b}_{k}").p_signal[:, LEADS] for k in ["fecg1", "mecg", "noise1", "noise2"]}
    x = sum(comp.values())
    x = x - x.mean(0)
    ev, V = np.linalg.eigh(np.cov(x.T))
    order = np.argsort(ev)[::-1]
    ev, V = ev[order], V[:, order]
    f = comp["fecg1"] - comp["fecg1"].mean(0)
    fe = ((f @ V) ** 2).sum(0)
    rows.append(dict(sub=f"sub{s:02d}", **{f"var_v{i+1}": 100 * ev[i] / ev.sum() for i in range(4)},
                     **{f"fetal_v{i+1}": 100 * fe[i] / fe.sum() for i in range(4)}))
d = pd.DataFrame(rows)
d.loc["mean"] = d.mean(numeric_only=True)
d.loc["mean", "sub"] = "mean"
d.to_csv(OUT / "r3_eigen.csv", index=False, float_format="%.2f")
print(d.round(1).to_string(index=False))
m = pd.read_csv(ROOT / "code/results/mega_benchmark_results.csv")
t = m[m.method == "Template_Sub_Fixed"].f1 * 100
pd.DataFrame([dict(method="Template_Sub_Fixed", n=len(t), mean=t.mean(), median=t.median())]).to_csv(OUT / "r5_median.csv", index=False, float_format="%.2f")
print("R5 Template_Sub_Fixed n=%d mean=%.2f median=%.2f" % (len(t), t.mean(), t.median()))
