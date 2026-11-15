#!/usr/bin/env python3
"""
Statistics for the final report, computed only from existing per-record result files.

Inputs (read-only):
  report/rtl_pc_split/board_umem/board_cdev_ad_ctest_syn.csv   v6 on the board (140 records)
  report/v61_v7/board_v61/board_cdev_ad_ctest_syn.csv          v6.1 on the board
  report/v61_v7/board_v7/board_cdev_ad_ctest_syn.csv           v7-DL on the board
  tools/accuracy/results_v61_synall.csv (variant base = v6, v61), results_v7dl_synall.csv   C model, 1,248 FECGSYNDB
  report/final_report/tables/board_f1_ci.csv, board_v7_f1_ci.csv   existing CIs (for the check)
Outputs: tools/report_stats/out/
  ci.csv          record bootstrap CIs (10,000 resamples, seed 2026, percentile), median, check vs existing tables
  cluster.csv     subject-clustered bootstrap for FECGSYNDB (resample the 10 subjects)
  paired.csv      paired v6 / v6.1 / v7-DL differences: mean, paired bootstrap CI, Wilcoxon signed-rank p
  shortfall.csv   share of the gap to 100% caused by records below 50% (v7-DL)

    venv/Scripts/python.exe tools/report_stats/stats.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
N_BOOT, SEED = 10000, 2026
UNREL = {"a33", "a38", "a47", "a52", "a54", "a71", "a74"}   # flagged by the challenge organisers (Behar et al. 2014)

board = {
    "v6": pd.read_csv(ROOT / "report/rtl_pc_split/board_umem/board_cdev_ad_ctest_syn.csv"),
    "v6.1": pd.read_csv(ROOT / "report/v61_v7/board_v61/board_cdev_ad_ctest_syn.csv"),
    "v7-DL": pd.read_csv(ROOT / "report/v61_v7/board_v7/board_cdev_ad_ctest_syn.csv"),
}
s61 = pd.read_csv(ROOT / "tools/accuracy/results_v61_synall.csv")
syn = {"v6": s61[s61.variant == "base"], "v6.1": s61[s61.variant == "v61"],
       "v7-DL": pd.read_csv(ROOT / "tools/accuracy/results_v7dl_synall.csv")}
syn = {k: v.assign(sub=v.rid.str[:5]).set_index("rid").sort_index() for k, v in syn.items()}


def subsets(df):
    yield "FECGSYNDB subset", df[df.set == "syn"]
    yield "ADFECGDB", df[df.set == "ad"]
    yield "CinC dev", df[df.set == "cdev"]
    yield "CinC test", df[df.set == "ctest"]
    yield "CinC all", df[df.set.isin(["cdev", "ctest"])]
    for nm, d in [("CinC dev", df[df.set == "cdev"]), ("CinC test", df[df.set == "ctest"]), ("CinC all", df[df.set.isin(["cdev", "ctest"])])]:
        yield nm + " reliable", d[~d.rid.isin(UNREL)]


def boot_ci(f):
    rng = np.random.default_rng(SEED)
    bs = rng.choice(f, (N_BOOT, len(f)), replace=True).mean(1)
    return np.percentile(bs, [2.5, 97.5])


# existing CIs, keyed (version, set)
old = {}
o6 = pd.read_csv(ROOT / "report/final_report/tables/board_f1_ci.csv")
for r in o6.itertuples():
    old[("v6", r.set.replace(" (reliable references)", " reliable"))] = (r.f1_mean, r.ci_low, r.ci_high)
for r in pd.read_csv(ROOT / "report/final_report/tables/board_v7_f1_ci.csv").itertuples():
    old[(r.version, r.set)] = (r.f1_mean, r.ci_low, r.ci_high)

rows = []
for ver, df in board.items():
    for nm, d in subsets(df):
        f = d.f1.to_numpy()
        lo, hi = boot_ci(f)
        o = old.get((ver, nm))
        diff = max(abs(lo - o[1]), abs(hi - o[2])) if o else np.nan
        rows.append(dict(version=ver, set=nm, n=len(f), mean=f.mean(), ci_low=lo, ci_high=hi, median=np.median(f),
                         old_low=o[1] if o else np.nan, old_high=o[2] if o else np.nan, max_ci_diff=diff,
                         flag="DIFF" if o and diff > 0.15 else ""))
for ver, d in syn.items():
    f = d.f1.to_numpy()
    lo, hi = boot_ci(f)
    rows.append(dict(version=ver, set="FECGSYNDB all (C model)", n=len(f), mean=f.mean(), ci_low=lo, ci_high=hi, median=np.median(f)))
ci = pd.DataFrame(rows)
ci.to_csv(OUT / "ci.csv", index=False, float_format="%.2f")

# subject-clustered bootstrap: resample the 10 subjects, keep all records of each drawn subject
crow = []
for label, data in [("FECGSYNDB all (C model)", syn), ("FECGSYNDB subset (board)", {k: v[v.set == "syn"].assign(sub=v[v.set == "syn"].rid.str[:5]) for k, v in board.items()})]:
    for ver, d in data.items():
        g = d.groupby("sub").f1
        sums, cnts = g.sum().to_numpy(), g.count().to_numpy()
        rng = np.random.default_rng(SEED)
        idx = rng.integers(0, len(sums), (N_BOOT, len(sums)))
        bs = sums[idx].sum(1) / cnts[idx].sum(1)
        lo, hi = np.percentile(bs, [2.5, 97.5])
        crow.append(dict(data=label, version=ver, subjects=len(sums), records=int(cnts.sum()), mean=d.f1.mean(), ci_low=lo, ci_high=hi))
# ectopic-beat condition c4 of the 1,248 records (v7-DL), record and subject-clustered
d4 = syn["v7-DL"][syn["v7-DL"].index.str.endswith("_c4")]
g = d4.groupby("sub").f1
sums, cnts = g.sum().to_numpy(), g.count().to_numpy()
rng = np.random.default_rng(SEED)
idx = rng.integers(0, len(sums), (N_BOOT, len(sums)))
lo, hi = np.percentile(sums[idx].sum(1) / cnts[idx].sum(1), [2.5, 97.5])
crow.append(dict(data="FECGSYNDB c4 (C model)", version="v7-DL", subjects=len(sums), records=int(cnts.sum()), mean=d4.f1.mean(), ci_low=lo, ci_high=hi))
pd.DataFrame(crow).to_csv(OUT / "cluster.csv", index=False, float_format="%.2f")

# paired comparisons on the same records
prow = []
pairs = [("v6", "v6.1"), ("v6.1", "v7-DL"), ("v6", "v7-DL")]
def paired(a, b, label, nm):
    d = (b - a).to_numpy()
    rng = np.random.default_rng(SEED)
    bs = rng.choice(d, (N_BOOT, len(d)), replace=True).mean(1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    nz = d[d != 0]
    p = wilcoxon(nz).pvalue if len(nz) >= 1 else np.nan
    prow.append(dict(set=label, comparison=nm, n=len(d), n_nonzero=len(nz), mean_diff=d.mean(), ci_low=lo, ci_high=hi,
                     better=int((d > 0).sum()), worse=int((d < 0).sum()), wilcoxon_p=p))
for x, y in pairs:
    A, B = board[x].set_index("rid"), board[y].set_index("rid")
    for nm, d in subsets(board[x]):
        r = d.rid
        paired(A.loc[r, "f1"], B.loc[r, "f1"], nm, f"{y} - {x}")
    paired(syn[x].f1, syn[y].loc[syn[x].index, "f1"], "FECGSYNDB all (C model)", f"{y} - {x}")
pd.DataFrame(prow).to_csv(OUT / "paired.csv", index=False, float_format="%.4g")

# shortfall decomposition (v7-DL)
srow = []
v7 = board["v7-DL"]
for nm, d in [("ADFECGDB", v7[v7.set == "ad"]), ("FECGSYNDB subset", v7[v7.set == "syn"]), ("FECGSYNDB all (C model)", syn["v7-DL"]),
              ("CinC test", v7[v7.set == "ctest"]), ("CinC all", v7[v7.set.isin(["cdev", "ctest"])])]:
    f = d.f1.to_numpy(); short = 100 - f
    for thr in (50, 70, 90):
        low = f < thr
        srow.append(dict(set=nm, n=len(f), mean=f.mean(), median=np.median(f), threshold=thr, n_below=int(low.sum()),
                         share_of_shortfall=100 * short[low].sum() / short.sum() if short.sum() else 0,
                         points_lost=short[low].sum() / len(f), gap=100 - f.mean()))
pd.DataFrame(srow).to_csv(OUT / "shortfall.csv", index=False, float_format="%.2f")

pd.set_option("display.width", 200)
print(ci[["version", "set", "n", "mean", "ci_low", "ci_high", "median", "max_ci_diff", "flag"]].round(2).to_string(index=False))
print(pd.DataFrame(crow).round(2).to_string(index=False))
print(pd.DataFrame(prow).round(4).to_string(index=False))
print(pd.DataFrame(srow).round(2).to_string(index=False))
