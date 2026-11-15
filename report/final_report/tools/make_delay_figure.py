#!/usr/bin/env python3
"""
F1 against output delay of v7-DL (dev sets, C model = board) for fpr-8.tex.

    python tools/accuracy/v7_delay_sweep.py                    (writes the input CSV)
    python report/final_report/tools/make_delay_figure.py      -> figures/fin_v7_delay.png, tables/v7_delay_sweep.csv
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "report" / "final_report" / "figures"
TAB = ROOT / "report" / "final_report" / "tables"
SRC = ROOT / "tools" / "accuracy" / "results_v7_delay_sweep.csv"

plt.rcParams.update({"font.size": 8, "axes.labelsize": 8, "figure.dpi": 150, "savefig.dpi": 300,
                     "axes.grid": True, "grid.alpha": 0.3, "axes.spines.top": False, "axes.spines.right": False})
V61, V7 = "#eb6834", "#1baf7a"          # same version colours as make_v7_figures.py
INK, MUTED = "#222222", "#666666"
SETS = [("cdev", "CinC dev (38)"), ("ad", "ADFECGDB (5)"), ("syn", "FECGSYNDB subset (60)")]
LIVE = (1.5, 2.0)                       # v6.1 beats leave 1.5-2 s after they occur (Sec. final_results)


def main():
    df = pd.read_csv(SRC)
    f1 = df.pivot_table(index="variant", columns="set", values="f1", aggfunc="mean")
    dl = df.groupby("variant").agg(med=("delay_med", "median"), mx=("delay_max", "max"))
    wf = [f"wf{w}" for w in range(6)]
    tab = pd.DataFrame({"future_window_s": [2.5 * w for w in range(6)],
                        "delay_median_s": dl.loc[wf, "med"].values,
                        "delay_max_s_deadline15": dl.loc[wf, "mx"].values,
                        **{s: f1.loc[wf, s].round(2).values for s, _ in SETS}}, index=wf)
    short = {"wf0": "wf0_dl5", "wf1": "wf1_dl10", "wf2": "wf2_dl12"}
    tab["delay_max_s_shorter_deadline"] = [dl.loc[short[v], "mx"] if v in short else None for v in wf]
    tab.to_csv(TAB / "v7_delay_sweep.csv")
    print(tab.to_string())

    fig, axes = plt.subplots(3, 1, figsize=(3.4, 3.0), sharex=True)
    x = dl.loc[wf, "med"].values
    for ax, (s, name) in zip(axes, SETS):
        y = f1.loc[wf, s].values
        ax.plot(x, y, color=V7, lw=1.5, marker="o", ms=4.5, mec="white", mew=0.8, zorder=3)
        ax.plot(x[3], y[3], marker="o", ms=8, color=V7, mec=INK, mew=0.9, zorder=4)
        y61 = f1.loc["v61", s]
        ax.errorbar(sum(LIVE) / 2, y61, xerr=(LIVE[1] - LIVE[0]) / 2, color=V61, marker="s", ms=4.5,
                    mec="white", mew=0.8, lw=1.2, capsize=0, zorder=3)
        ax.text(sum(LIVE) / 2 + 0.6, y61, f"v6.1 live {y61:.1f}", fontsize=6.5, color=INK, va="center")
        ax.text(x[0], y[0] - 0.12 * (ax.get_ylim()[1] - ax.get_ylim()[0]), f"{y[0]:.1f}", fontsize=6.5,
                color=INK, ha="center", va="top")
        ax.annotate(f"final v7-DL {y[3]:.1f}", (x[3], y[3]), (x[3] - 0.3, y[3] - 0.35 * (y[3] - y61)),
                    fontsize=6.5, color=INK, ha="right", va="center",
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
        ax.set_title(name, fontsize=8, loc="left", color=INK)
        ax.set_ylabel("F1 (%)")
        lo, hi = min(y.min(), y61), max(y.max(), y61)
        ax.set_ylim(lo - 0.25 * (hi - lo), hi + 0.15 * (hi - lo))
    axes[-1].set_xlabel("median output delay (s)")
    axes[-1].set_xlim(0, 18)
    fig.tight_layout(h_pad=0.6)
    fig.savefig(FIG / "fin_v7_delay.png", bbox_inches="tight")
    print("wrote", FIG / "fin_v7_delay.png")


if __name__ == "__main__":
    main()
