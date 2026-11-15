#!/usr/bin/env python3
"""
Figures of the last final-phase step (v6.1, v7-LA, v7-DL) for fpr-8.tex, from the saved result files.

    python report/final_report/tools/make_v7_figures.py      -> report/final_report/figures/fin_v7_*.png

Inputs: board results of v6 / v6.1 / v7-DL (report/rtl_pc_split/board_umem, report/v61_v7/board_v61,
report/v61_v7/board_v7), C-model results on all FECGSYNDB records and the offline v7-LA results
(tools/accuracy/results_*.csv).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "report" / "final_report" / "figures"
ACC = ROOT / "tools" / "accuracy"
B6 = ROOT / "report" / "rtl_pc_split" / "board_umem" / "board_cdev_ad_ctest_syn.csv"
B61 = ROOT / "report" / "v61_v7" / "board_v61" / "board_cdev_ad_ctest_syn.csv"
B7 = ROOT / "report" / "v61_v7" / "board_v7" / "board_cdev_ad_ctest_syn.csv"
UNREL = {"a33", "a38", "a47", "a52", "a54", "a71", "a74"}

plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "legend.fontsize": 8,
                     "figure.dpi": 150, "savefig.dpi": 300, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.spines.top": False, "axes.spines.right": False})
# categorical slots 1-4 of the validated default palette, fixed order: v6, v6.1, v7-DL, v7-LA
COL = {"v6": "#2a78d6", "v6.1": "#eb6834", "v7-DL": "#1baf7a", "v7-LA": "#eda100"}
INK, MUTED = "#222222", "#666666"


def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / name)


def board(path):
    return pd.read_csv(path)


def means():
    b6, b61, b7 = board(B6), board(B61), board(B7)
    la_dev = pd.read_csv(ACC / "results_v7la_dev.csv")
    la_test = pd.read_csv(ACC / "results_v7la_ctest.csv")
    syn61 = pd.read_csv(ACC / "results_v61_synall.csv")
    syn_la = pd.read_csv(ACC / "results_v7la_synall.csv")
    syn_dl = pd.read_csv(ACC / "results_v7dl_synall.csv")

    def m(df, s, reliable=False):
        d = df[df.set == s]
        if reliable:
            d = d[~d.rid.isin(UNREL)]
        return d.f1.mean()
    groups = ["CinC test\n(37, held out)", "CinC test\nreliable refs (33)", "CinC dev\n(38)", "ADFECGDB\n(5)", "FECGSYNDB\nall (1,248)"]
    vals = {
        "v6": [m(b6, "ctest"), m(b6, "ctest", True), m(b6, "cdev"), m(b6, "ad"), syn61[syn61.variant == "base"].f1.mean()],
        "v6.1": [m(b61, "ctest"), m(b61, "ctest", True), m(b61, "cdev"), m(b61, "ad"), syn61[syn61.variant == "v61"].f1.mean()],
        "v7-DL": [m(b7, "ctest"), m(b7, "ctest", True), m(b7, "cdev"), m(b7, "ad"), syn_dl.f1.mean()],
        "v7-LA": [la_test.f1.mean(), la_test[~la_test.rid.isin(UNREL)].f1.mean(), m(la_dev, "cdev"), m(la_dev, "ad"), syn_la.f1.mean()],
    }
    return groups, vals


def fig_results():
    """column-width grouped bars: F1 of every version on every data set"""
    groups, vals = means()
    labels = ["CinC test\n(held out)", "CinC test\nreliable", "CinC\ndev", "ADF-\nECGDB", "FECG-\nSYNDB"]
    fig, ax = plt.subplots(figsize=(3.4, 2.75))
    x = np.arange(len(groups))
    w = 0.2
    names = {"v6": "v6 (board)", "v6.1": "v6.1 (board)", "v7-DL": "v7-DL (board, final)", "v7-LA": "v7-LA (offline, PC)"}
    for i, k in enumerate(["v6", "v6.1", "v7-DL", "v7-LA"]):
        ax.bar(x + (i - 1.5) * w, vals[k], w - 0.02, color=COL[k], label=names[k], zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=6.5)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_ylim(50, 100)
    ax.set_ylabel("Mean beat F1 (%)", fontsize=7.5)
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=2, loc="lower center", frameon=False, fontsize=6.5, bbox_to_anchor=(0.5, 1.0),
              handlelength=1.2, columnspacing=1.0)
    save(fig, "fin_v7_results.png")


def fig_timing():
    """column-width diagram: when does v7-DL decide a 2.5-s segment"""
    fig, ax = plt.subplots(figsize=(3.4, 1.9))
    ax.set_xlim(-16.5, 17)
    ax.set_ylim(-0.75, 4.3)
    ax.axis("off")
    ax.annotate("", (16.8, 0.5), (-16.3, 0.5), arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.7))
    for t in range(-15, 16, 5):
        ax.plot([t, t], [0.42, 0.58], color=MUTED, lw=0.7)
        ax.text(t, 0.05, f"{t:+d}" if t else "0", ha="center", fontsize=6, color=MUTED)
    ax.text(-16.3, -0.6, "time relative to the start of segment i (s)", fontsize=6, color=MUTED)
    ax.add_patch(Rectangle((-15, 0.85), 25, 0.6, fc="#cde2fb", ec=COL["v6"], lw=0.7))
    ax.text(-2.5, 1.15, "quality window of all 16 tracks: -15 s ... +10 s", fontsize=6, ha="center", va="center", color=INK)
    ax.add_patch(Rectangle((0, 1.8), 2.5, 0.55, fc=COL["v7-DL"], ec="none"))
    ax.text(-0.4, 2.07, "segment i (2.5 s)", fontsize=6, ha="right", va="center", color=INK)
    ax.annotate("", (11.3, 2.07), (2.8, 2.07), arrowprops=dict(arrowstyle="-|>", color=COL["v6.1"], lw=0.9))
    ax.text(7.0, 2.25, "Viterbi step", fontsize=6, ha="center", va="bottom", color=INK)
    ax.plot([11.5, 11.5], [0.6, 3.05], color=COL["v6.1"], lw=1.2)
    ax.text(11.5, 3.1, "decision\n+11.5 s", fontsize=6, ha="center", va="bottom", color=INK)
    ax.text(-16.3, 3.95, "final beats leave the FPGA about 13.5 s", fontsize=6, va="top", color=INK)
    ax.text(-16.3, 3.35, "after they occur (median), at most 17.5 s", fontsize=6, va="top", color=INK)
    save(fig, "fin_v7_timing.png")


def fig_cinc():
    """column-width scatter: final v7-DL against live v6.1, same board runs"""
    b7 = board(B7)
    c = b7[b7.set.isin(["cdev", "ctest"])]
    fig, ax = plt.subplots(figsize=(3.4, 2.9))
    # data-set colours of the other report figures (make_final_figures.py SET_COL)
    for s, mk, col, nm in [("cdev", "o", "#DD8452", "CinC dev (38)"), ("ctest", "s", "#C44E52", "CinC test (37)")]:
        g = c[c.set == s]
        ax.scatter(g.f1_causal, g.f1, s=14, marker=mk, color=col, label=nm, edgecolor="white", lw=0.5, zorder=3)
    ax.plot([0, 100], [0, 100], color=MUTED, lw=0.8, ls="--", zorder=2)
    up = int((c.f1 > c.f1_causal + 1).sum())
    dn = int((c.f1 < c.f1_causal - 1).sum())
    ax.text(3, 95, f"{up} records better, {dn} worse\n(by more than 1 point)", fontsize=6.5, color=INK, va="top")
    ax.set_xlim(-2, 102)
    ax.set_ylim(-2, 102)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("F1 of the live v6.1 output (%)", fontsize=7.5)
    ax.set_ylabel("F1 of the final v7-DL output (%)", fontsize=7.5)
    ax.legend(loc="lower right", frameon=False, fontsize=6.5)
    save(fig, "fin_v7_cinc.png")


def fig_conditions():
    """column-width bars: FECGSYNDB (1,248) by condition"""
    syn61 = pd.read_csv(ACC / "results_v61_synall.csv")
    syn61 = syn61[syn61.variant == "v61"]
    sets = {"v6.1": syn61, "v7-DL": pd.read_csv(ACC / "results_v7dl_synall.csv"), "v7-LA": pd.read_csv(ACC / "results_v7la_synall.csv")}
    conds = ["c0", "c1", "c2", "c3", "c4"]
    names = ["c0\nnormal", "c1\nfetal\nmovement", "c2\nHR\nchanges", "c3\ncontrac-\ntions", "c4\nectopic\nbeats"]
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    x = np.arange(5)
    w = 0.26
    for i, (k, d) in enumerate(sets.items()):
        cc = d.rid.str.extract(r"_(c\d)$")[0]
        v = [d[cc == q].f1.mean() for q in conds]
        ax.bar(x + (i - 1) * w, v, w - 0.02, color=COL[k], label=k, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=6.5)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_ylim(70, 100)
    ax.set_ylabel("Mean F1 (%)", fontsize=7.5)
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=3, loc="lower center", frameon=False, fontsize=6.5, bbox_to_anchor=(0.5, 1.0))
    save(fig, "fin_v7_conditions.png")


def ci_table():
    """95% bootstrap CIs of the board F1 (same method as final_analysis.py) -> tables/board_v7_f1_ci.csv"""
    rows = []
    for ver, path in [("v6.1", B61), ("v7-DL", B7)]:
        d = board(path)
        rng = np.random.default_rng(2026)
        for s, nm in [("syn", "FECGSYNDB subset"), ("ad", "ADFECGDB"), ("cdev", "CinC dev"), ("ctest", "CinC test"), ("all", "CinC all")]:
            for rel in (False, True):
                g = d[d.set.isin(["cdev", "ctest"])] if s == "all" else d[d.set == s]
                if rel:
                    if s not in ("cdev", "ctest", "all"):
                        continue
                    g = g[~g.rid.isin(UNREL)]
                f = g.f1.values
                bs = rng.choice(f, (10000, len(f)), replace=True).mean(1)
                rows.append({"version": ver, "set": nm + (" reliable" if rel else ""), "records": len(f),
                             "f1_mean": round(f.mean(), 2), "ci_low": round(np.percentile(bs, 2.5), 1),
                             "ci_high": round(np.percentile(bs, 97.5), 1), "median": round(np.median(f), 1),
                             "n_ge_90": int((f >= 90).sum())})
    df = pd.DataFrame(rows)
    out = ROOT / "report" / "final_report" / "tables" / "board_v7_f1_ci.csv"
    df.to_csv(out, index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    ci_table()
    fig_results()
    fig_timing()
    fig_cinc()
    fig_conditions()
