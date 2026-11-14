#!/usr/bin/env python3
"""
Extra analyses for the final report:
  1. 95% confidence intervals of the board F1 per data set (bootstrap over records);
  2. failure analysis of the CinC 2013 recordings (C model of v6, bit-exact with the board):
     maternal train and fetal output read from the model's own uplink stream;
  3. project timeline figure.
Writes report/final_report/tables/*.csv and figures fin_failures.png, fin_timeline.png.

    venv/Scripts/python.exe report/final_report/tools/final_analysis.py
"""
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "report/final_report/figures"
TAB = ROOT / "report/final_report/tables"
TAB.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "tools/accuracy"))
sys.path.insert(0, str(ROOT / "fpga_implementation/uart_host"))
plt.rcParams.update({"font.size": 8, "axes.grid": True, "grid.alpha": 0.3, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 300})
board = pd.read_csv(ROOT / "report/rtl_pc_split/board_umem/board_cdev_ad_ctest_syn.csv")
cinc = pd.read_csv(ROOT / "tools/accuracy/results_cinc2013.csv").rename(columns={"record": "rid"})


# 1 ------------------------------------------------------------------------------------
def confidence_intervals():
    rng = np.random.default_rng(2026)
    rows = []
    sets = [("syn", "FECGSYNDB subset"), ("ad", "ADFECGDB"), ("cdev", "CinC dev"), ("ctest", "CinC test")]
    unrel = set(cinc.rid[cinc.unreliable_ref])
    for s, name in sets:
        for only_rel in ([False, True] if s.startswith("c") else [False]):
            g = board[board.set == s]
            if only_rel:
                g = g[~g.rid.isin(unrel)]
            f = g.f1.values
            bs = rng.choice(f, (10000, len(f)), replace=True).mean(1)
            rows.append({"set": name + (" (reliable references)" if only_rel else ""), "records": len(f),
                         "f1_mean": f.mean(), "ci_low": np.percentile(bs, 2.5), "ci_high": np.percentile(bs, 97.5),
                         "median": np.median(f), "fhr_mae": g.fhr_mae.mean()})
    df = pd.DataFrame(rows)
    df.to_csv(TAB / "board_f1_ci.csv", index=False)
    print(df.round(2).to_string(index=False))
    return df


# 2 ------------------------------------------------------------------------------------
def frames(up):
    i, out = 0, []
    while i + 5 <= len(up):
        if up[i] != 0xA5 or up[i + 1] != 0x5A:
            i += 1
            continue
        cmd, ln = up[i + 2], up[i + 3] | (up[i + 4] << 8)
        out.append((cmd, up[i + 5:i + 5 + ln]))
        i += 6 + ln
    return out


def failure_analysis():
    import harness as H
    import v5c
    from eval_cinc2013 import load
    from run_v6_board_eval import model_stream

    rows, traces = [], {}
    for rid in sorted(board[board.set.isin(["cdev", "ctest"])].rid):
        X, fq = load(rid)
        n = len(X)
        b, up = model_stream(v5c.to_i16(X))
        mpk = np.array([int.from_bytes(bytes(p[0:4]), "little") for c, p in frames(up) if c == 0x83])
        out_t, out_f = b[:, 0], b[:, 1] / 10.0
        sc = out_t >= 5000
        mat_hr = 60 * 250 / np.median(np.diff(mpk)) if len(mpk) > 2 else np.nan
        ref_hr = 60 * 250 / np.median(np.diff(fq)) if len(fq) > 2 else np.nan
        out_hr = np.median(out_f[sc & (out_f > 0)]) if (sc & (out_f > 0)).any() else np.nan
        if len(mpk) and sc.any():
            d = np.abs(out_t[sc][:, None] - mpk[None, :]).min(1)
            coinc = float(np.mean(d <= 12))
        else:
            coinc = np.nan
        r = board[board.rid == rid].iloc[0]
        rows.append({"rid": rid, "set": r.set, "f1": r.f1, "ref_fhr": ref_hr, "out_fhr": out_hr, "mat_hr": mat_hr,
                     "maternal_train_found": len(mpk) > 2,
                     "mat_coinc": coinc, "unreliable_ref": bool(cinc.loc[cinc.rid == rid, "unreliable_ref"].iloc[0])})
        pk, fhr = v5c.beats_to_stream(b, n)
        traces[rid] = (n, H.fhr_ref_stream(fq, n), fhr, mat_hr)
    df = pd.DataFrame(rows)

    def cat(r):
        if r.f1 >= 50:
            return "ok"
        if r.unreliable_ref:
            return "reference unreliable"
        if r.out_fhr < 100 or (abs(r.out_fhr - r.mat_hr) < 10) or r.mat_coinc > 0.5:
            return "followed the mother"
        return "wrong fetal-range track"
    df["category"] = df.apply(cat, axis=1)
    df.to_csv(TAB / "cinc_failures.csv", index=False)
    print(df.category.value_counts().to_string())
    print(df[df.category != "ok"].sort_values("f1").round(1).to_string(index=False))

    # figure: scatter of output vs reference FHR, plus one example per category
    fig = plt.figure(figsize=(7.0, 4.4))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.25, 1])
    ax = fig.add_subplot(gs[0, :2])
    col = {"ok": "#55A868", "followed the mother": "#C44E52", "wrong fetal-range track": "#DD8452",
           "reference unreliable": "#8172B3"}
    for c, g in df.groupby("category"):
        ax.scatter(g.ref_fhr, g.out_fhr, s=16, color=col[c], label=f"{c} ({len(g)})", alpha=0.85)
    ok = df.mat_hr.notna()
    ax.scatter(df.ref_fhr[ok], df.mat_hr[ok], s=6, marker="x", color="#999", label="maternal HR found by the FPGA")
    ax.axhspan(50, 100, color="#C44E52", alpha=0.06, lw=0)
    ax.text(91, 53, "adult heart-rate range", fontsize=6, ha="left", va="bottom", color="#C44E52")
    ax.plot([60, 200], [60, 200], "k--", lw=0.6)
    ax.set_xlabel("reference FHR, median (bpm)")
    ax.set_ylabel("v6 output FHR, median (bpm)")
    ax.set_xlim(90, 175)
    ax.set_ylim(50, 200)
    ax.legend(fontsize=6, frameon=False, loc="upper left")
    ax.set_title("CinC 2013 (75 records): where the output rate ends up", fontsize=8)
    ax2 = fig.add_subplot(gs[0, 2])
    vc = df.category.value_counts()
    ax2.barh(range(len(vc)), vc.values, color=[col[c] for c in vc.index])
    ax2.set_yticks(range(len(vc)), [c.replace(" ", "\n", 1) for c in vc.index], fontsize=6.5)
    ax2.set_xlabel("records")
    ax2.set_title("F1 < 50%: cause", fontsize=8)
    ex = []
    for c in ["followed the mother", "wrong fetal-range track", "reference unreliable"]:
        g = df[df.category == c].sort_values("f1")
        if len(g):
            ex.append((c, g.iloc[0].rid, g.iloc[0].f1))
    for k, (c, rid, f1) in enumerate(ex):
        a = fig.add_subplot(gs[1, k])
        n, ref, fhr, mh = traces[rid]
        t = np.arange(n) / 250
        a.plot(t, ref, color="#55A868", lw=1.0, label="reference FHR")
        m = fhr > 0
        a.plot(t[m], fhr[m], color="#C44E52", lw=0.8, label="v6 FHR")
        if np.isfinite(mh):
            a.axhline(mh, color="#777", lw=0.8, ls="--", label="maternal HR")
        a.set_xlim(15, 60)
        a.set_ylim(50, 200)
        a.set_title(f"{rid} ({c}), F1 {f1:.0f}%", fontsize=6.5)
        a.set_xlabel("time (s)", fontsize=7)
        if k == 0:
            a.set_ylabel("bpm", fontsize=7)
            a.legend(fontsize=5.5, frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT / "fin_failures.png")
    plt.close(fig)
    print("wrote fin_failures.png")
    return df


# 3 ------------------------------------------------------------------------------------
def timeline():
    ph = [("Proposal, literature, data set choice", date(2026, 9, 25), date(2026, 9, 29), "#9E9E9E"),
          ("Mid-term: methods, benchmarks, report", date(2026, 10, 13), date(2026, 10, 27), "#9E9E9E"),
          ("Causal pipeline, integer golden model", date(2026, 10, 31), date(2026, 11, 1), "#8172B3"),
          ("UART bring-up on the board", date(2026, 11, 3), date(2026, 11, 4), "#8172B3"),
          ("Audit, full FECGSYNDB + NIFEA validation", date(2026, 11, 4), date(2026, 11, 7), "#8172B3"),
          ("v2: GEVD beamformer, RTL fixes, board", date(2026, 11, 7), date(2026, 11, 8), "#8172B3"),
          ("Real data (CinC, ADFECGDB); v3, v4", date(2026, 11, 7), date(2026, 11, 9), "#64B5CD"),
          ("v5: whole algorithm on MicroBlaze", date(2026, 11, 9), date(2026, 11, 10), "#DD8452"),
          ("v6: C model, Verilog RTL, board 140/140", date(2026, 11, 10), date(2026, 11, 11), "#C44E52"),
          ("Web demo, BRAM sharing, final report", date(2026, 11, 13), date(2026, 11, 15), "#C44E52")]
    fig, ax = plt.subplots(figsize=(7.0, 2.6))
    t0 = date(2026, 9, 22)
    for i, (n, a, b, c) in enumerate(ph[::-1]):
        ax.barh(i, (b - a).days + 0.6, left=(a - t0).days, color=c, height=0.6)

    for d, lab in [(date(2026, 9, 29), "PPR-8"), (date(2026, 10, 27), "MTR-8"), (date(2026, 11, 15), "FPR-8")]:
        ax.axvline((d - t0).days + 0.6, color="k", lw=0.7, ls=":")
        ax.text((d - t0).days + 0.6, len(ph) - 0.2, lab, fontsize=6.5, ha="center")
    ticks = [date(2026, 9, 25), date(2026, 10, 5), date(2026, 10, 15), date(2026, 10, 25), date(2026, 11, 4), date(2026, 11, 14)]
    ax.set_xticks([(d - t0).days for d in ticks], [d.strftime("%d %b") for d in ticks], fontsize=7)
    ax.set_yticks(range(len(ph)), [p[0] for p in ph[::-1]], fontsize=6.6)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, (date(2026, 11, 16) - t0).days)
    ax.grid(axis="y", visible=False)
    ax.set_title("Project timeline (from the repository history)", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fin_timeline.png")
    plt.close(fig)
    print("wrote fin_timeline.png")


if __name__ == "__main__":
    confidence_intervals()
    timeline()
    failure_analysis()
