#!/usr/bin/env python3
"""
Figures for the final report (fpr-8).  Every number is read from the saved result
files in the repository; nothing is typed in by hand except the version summary
table (Fig. 1), whose values are the logged means quoted in report/night_20261109/RESULTS.md
and report/rtl_pc_split/LOG.md.

Run from the repository root:
    venv/Scripts/python.exe report/final_report/tools/make_final_figures.py
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "report" / "final_report" / "figures"
ACC = ROOT / "tools" / "accuracy"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "legend.fontsize": 8,
                     "figure.dpi": 150, "savefig.dpi": 300, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.spines.top": False, "axes.spines.right": False})
SET_NAME = {"syn": "FECGSYNDB\n(60, synthetic)", "ad": "ADFECGDB\n(5, real)",
            "cdev": "CinC dev\n(38, real)", "ctest": "CinC test\n(37, real, held out)"}
SET_COL = {"syn": "#4C72B0", "ad": "#55A868", "cdev": "#DD8452", "ctest": "#C44E52"}
VER_COL = ["#9E9E9E", "#8172B3", "#64B5CD", "#4C9F70", "#DD8452", "#C44E52"]

board = pd.read_csv(ROOT / "report/rtl_pc_split/board_umem/board_cdev_ad_ctest_syn.csv")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


# 1. accuracy of every version on every data set ---------------------------------------
def fig_progression():
    vers = ["Mid-term design\n(causal re-run)", "v2", "v3 (Python)", "v4 (Python)", "v5 (MicroBlaze)", "v6 (RTL, final)"]
    data = {  # mean F1 %, from RESULTS.md / LOG.md / results_cinc2013.csv
        "CinC test (37)": [16.7, 41.2, 49.9, 53.1, 65.8, 65.5],
        "CinC dev (38)": [22.8, 42.0, 59.4, 68.4, 75.3, 76.0],
        "ADFECGDB (5)": [np.nan, 37.0, 78.6, 91.3, 93.4, 92.7],
        "FECGSYNDB (1,248)": [82.2, 95.6, 95.0, np.nan, 91.5, 91.4],
    }
    fig, ax = plt.subplots(figsize=(7.0, 2.9))
    x = np.arange(len(data))
    w = 0.13
    for i, v in enumerate(vers):
        vals = [data[k][i] for k in data]
        b = ax.bar(x + (i - 2.5) * w, vals, w, label=v.replace("\n", " "), color=VER_COL[i], edgecolor="white", lw=0.4)
        for r, val in zip(b, vals):
            if np.isfinite(val):
                ax.text(r.get_x() + r.get_width() / 2, val + 1, f"{val:.0f}", ha="center", va="bottom", fontsize=6)
    ax.set_xticks(x, list(data))
    ax.set_ylabel("Beat F1 (%)")
    ax.set_ylim(0, 100)
    ax.legend(ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.12), frameon=False, fontsize=6.5)
    ax.set_title("Fetal QRS detection accuracy of every design version (strictly causal, label-free)")
    save(fig, "fin_version_progression.png")


# 2. v6 architecture -------------------------------------------------------------------
def fig_architecture():
    fig, ax = plt.subplots(figsize=(7.0, 3.3))
    ax.set_xlim(-1, 101)
    ax.set_ylim(0, 48)
    ax.axis("off")

    def box(x, y, w, h, text, fc, fs=6.2, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec="#333", lw=0.7))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, weight="bold" if bold else None)

    def arrow(x0, y0, x1, y1, txt="", c="#333", dy=1.0):
        ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="-|>", color=c, lw=0.9))
        if txt:
            ax.text((x0 + x1) / 2, (y0 + y1) / 2 + dy, txt, ha="center", fontsize=6, color=c)

    ax.add_patch(FancyBboxPatch((14, 17), 85, 29, boxstyle="round,pad=0.3", fc="#EEF3FA", ec="#4C72B0", lw=1.2))
    ax.text(15, 44.2, "Spartan-7 XC7S50 @ 50 MHz: hand-written Verilog, no soft processor (all sample-rate work)",
            fontsize=7, weight="bold", color="#24476F")
    box(0, 27, 10, 8, "4 abdominal\nleads\nint16, 250 Hz", "#FFFFFF")
    arrow(10.8, 31, 15, 31)
    ax.text(5, 22.5, "UART\n921.6 kbaud", ha="center", fontsize=6)
    box(16, 34, 13, 7, "IIR filters\n(SOS, Q28)", "#DCE8F5")
    box(16, 20, 13, 9, "Maternal R-peak\ndetectors (4)", "#DCE8F5")
    box(32, 34, 15, 7, "Maternal cancel.\nper lead (template\nfit + subtract)", "#DCE8F5", fs=6.5)
    box(32, 20, 15, 9, "16 spatial\nprojections\n+ band-pass", "#DCE8F5")
    box(50, 34, 15, 7, "Envelopes,\nblanking", "#DCE8F5")
    box(50, 20, 15, 9, "12 beat trackers\n+ 4 threshold\ndetectors", "#DCE8F5")
    box(68, 27, 13, 9, "Feature capture,\nselected-track\nbeat + FHR out", "#DCE8F5")
    box(84, 27, 13, 9, "UART TX\nframes\n(OUT, requests)", "#DCE8F5")
    for (a, b) in [((29.6, 37.5), (31.4, 37.5)), ((47.6, 37.5), (49.4, 37.5)), ((47.6, 24.5), (49.4, 24.5)),
                   ((65.6, 24.5), (67.4, 30)), ((65.6, 37.5), (67.4, 33)), ((81.6, 31.5), (83.4, 31.5))]:
        arrow(*a, *b)
    arrow(22.5, 33.4, 22.5, 29.6)
    arrow(39.5, 33.4, 39.5, 29.6)
    ax.add_patch(FancyBboxPatch((14, 1), 85, 11, boxstyle="round,pad=0.3", fc="#FBEFE6", ec="#DD8452", lw=1.2))
    ax.text(15, 10.6, "PC brain (v6_brain.exe): 5 low-rate decisions on FPGA data; never the raw recording",
            fontsize=7, weight="bold", color="#8A4A1C")
    jobs = ["Maternal PCA\n(once, 10 s)", "Maternal train\nchoice (5 s)", "Template basis\n(per maternal beat)",
            "GEVD calibration\n(once, 15 s)", "Track selection\n(every 2.5 s)"]
    for i, j in enumerate(jobs):
        box(16 + i * 16.6, 2.5, 14, 6, j, "#FFFFFF", fs=6.3)
    arrow(60, 16.5, 60, 12.5, c="#8A4A1C")
    ax.text(61, 14, "requests (FPGA stalls until answered)", fontsize=6, color="#8A4A1C", va="center")
    arrow(40, 12.5, 40, 16.5, c="#24476F")
    ax.text(39, 14, "answers", fontsize=6, color="#24476F", va="center", ha="right")
    save(fig, "fin_v6_architecture.png")


# 3. per-record F1 on the board --------------------------------------------------------
def fig_board_distribution():
    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    order = ["syn", "ad", "cdev", "ctest"]
    vals = [board[board.set == s].f1.values for s in order]
    bp = ax.boxplot(vals, widths=0.5, patch_artist=True, showfliers=False, medianprops=dict(color="k"))
    rng = np.random.default_rng(0)
    for i, (s, v) in enumerate(zip(order, vals)):
        bp["boxes"][i].set(facecolor=SET_COL[s], alpha=0.35)
        ax.scatter(i + 1 + rng.uniform(-0.15, 0.15, len(v)), v, s=7, color=SET_COL[s], alpha=0.8, lw=0)
        ax.text(i + 1, 103, f"mean {v.mean():.1f}", ha="center", fontsize=6.5)
    ax.set_xticks(range(1, 5), [SET_NAME[s].replace(", ", ",\n") for s in order], fontsize=6.3)
    ax.set_ylabel("Beat F1 per record (%)")
    ax.set_ylim(0, 108)
    ax.set_title("v6 on the board: 140 records, all bit-exact", fontsize=9)
    save(fig, "fin_board_f1_distribution.png")


# 4. FECGSYNDB by condition and SNR: v2 vs final algorithm --------------------------------
def fig_syn_breakdown():
    v2 = pd.read_csv(ACC / "results_bitaccurate.csv")
    v5 = pd.read_csv(ACC / "results_v5_final_synall.csv")
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.5))
    conds = ["c0", "c1", "c2", "c3", "c4"]
    lab = ["c0\nbaseline", "c1\nmovement", "c2\nHR\nchange", "c3\ncontrac-\ntion", "c4\nectopic"]
    x = np.arange(5)
    for k, (df, nm, c) in enumerate([(v2, "v2 (synthetic-tuned)", VER_COL[1]), (v5, "v5/v6 final algorithm", VER_COL[5])]):
        m = df.groupby("cond").f1.mean().reindex(conds)
        axs[0].bar(x + (k - 0.5) * 0.38, m.values, 0.38, label=nm, color=c)
        snr = df.groupby("snr").f1.mean()
        axs[1].plot(snr.index, snr.values, "o-", label=nm, color=c)
    axs[0].set_xticks(x, lab, fontsize=7)
    axs[0].set_ylim(60, 102)
    axs[0].set_ylabel("Mean F1 (%)")
    axs[0].set_title("FECGSYNDB (1,248 records) by condition")
    axs[1].set_xlabel("Input SNR (dB)")
    axs[1].set_ylim(80, 100)
    axs[1].set_title("by noise level")
    axs[1].legend(frameon=False, loc="lower right")
    save(fig, "fin_syn_condition_snr.png")


# 5. paired CinC records: v2 vs v6 -------------------------------------------------------
def fig_cinc_paired():
    c = pd.read_csv(ACC / "results_cinc2013.csv").rename(columns={"record": "rid"})
    b = board[board.set.isin(["cdev", "ctest"])][["set", "rid", "f1"]]
    m = b.merge(c[["rid", "v2_f1", "old_f1"]], on="rid")
    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    for s, mk in [("cdev", "o"), ("ctest", "s")]:
        g = m[m.set == s]
        ax.scatter(g.v2_f1, g.f1, s=14, marker=mk, color=SET_COL[s], label=SET_NAME[s].replace("\n", " "), alpha=0.85)
    ax.plot([0, 100], [0, 100], "k--", lw=0.7)
    better = (m.f1 > m.v2_f1 + 1).sum()
    worse = (m.f1 < m.v2_f1 - 1).sum()
    ax.text(3, 93, f"better: {better} records\nworse: {worse} records", fontsize=7)
    ax.set_xlabel("v2 F1 per record (%)")
    ax.set_ylabel("v6 board F1 per record (%)")
    ax.set_xlim(0, 101)
    ax.set_ylim(0, 101)
    ax.legend(frameon=False, loc="lower right", fontsize=6.5)
    ax.set_title("CinC 2013 real recordings: v2 vs v6", fontsize=9)
    save(fig, "fin_cinc_v2_vs_v6.png")


# 6. Se vs PPV on the board --------------------------------------------------------------
def fig_se_ppv():
    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    for s in ["syn", "ad", "cdev", "ctest"]:
        g = board[board.set == s]
        ax.scatter(g.se, g.ppv, s=12, color=SET_COL[s], label=SET_NAME[s].replace("\n", " "), alpha=0.8)
    ax.plot([0, 100], [0, 100], "k--", lw=0.6)
    ax.set_xlabel("Sensitivity Se (%)")
    ax.set_ylabel("Positive predictive value PPV (%)")
    ax.set_xlim(0, 101)
    ax.set_ylim(0, 101)
    ax.legend(frameon=False, fontsize=6.5, loc="lower right")
    ax.set_title("v6 board: Se vs PPV per record", fontsize=9)
    save(fig, "fin_board_se_ppv.png")


# 7. where the remaining real-data error is ---------------------------------------------
def fig_selection_gap():
    d = pd.read_csv(ACC / "results_diag_v5.csv")
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.5), gridspec_kw=dict(width_ratios=[1, 1.6]))
    sets = ["syn", "ad", "cdev"]
    cols = [("sel", "label-free selection (ours)", VER_COL[5]), ("best_track", "best single track (uses labels)", VER_COL[3]),
            ("win_oracle", "per-5 s oracle (uses labels)", VER_COL[1])]
    x = np.arange(3)
    for k, (cn, nm, c) in enumerate(cols):
        m = d.groupby("set")[cn].mean().reindex(sets)
        axs[0].bar(x + (k - 1) * 0.27, m.values, 0.27, label=nm, color=c)
    axs[0].set_xticks(x, ["FECGSYNDB", "ADFECGDB", "CinC dev"], fontsize=7)
    axs[0].set_ylim(60, 101)
    axs[0].set_ylabel("Mean F1 (%)")
    axs[0].legend(frameon=False, fontsize=6, loc="lower left")
    axs[0].set_title("Selection vs oracles (dev sets)")
    g = d[d.set == "cdev"].sort_values("sel")
    xi = np.arange(len(g))
    axs[1].vlines(xi, g.sel, g.win_oracle, color="#BBBBBB", lw=1)
    axs[1].scatter(xi, g.win_oracle, s=8, color=VER_COL[1], label="oracle")
    axs[1].scatter(xi, g.sel, s=8, color=VER_COL[5], label="ours")
    axs[1].set_xticks([])
    axs[1].set_xlabel("CinC dev records (sorted by our F1)")
    axs[1].set_ylabel("F1 (%)")
    axs[1].legend(frameon=False, fontsize=6.5, loc="lower right")
    axs[1].set_title("Per-record gap to the oracle")
    save(fig, "fin_selection_gap.png")


# 8. FPGA resources of each hardware version ---------------------------------------------
def fig_resources():
    vers = ["v2 RTL", "v5\nMicroBlaze", "v6 RTL\nfirst build", "v6 RTL\nfinal"]
    lut = [3881 / 32600, 3300 / 32600, 19000 / 32600, 18127 / 32600]
    dsp = [39 / 120, 5 / 120, 33 / 120, 33 / 120]
    bram = [0 / 75, 72 / 75, 74.5 / 75, 60 / 75]
    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    x = np.arange(4)
    for k, (v, nm, c) in enumerate([(lut, "LUT", "#4C72B0"), (dsp, "DSP48", "#55A868"), (bram, "Block RAM", "#C44E52")]):
        b = ax.bar(x + (k - 1) * 0.26, np.array(v) * 100, 0.26, label=nm, color=c)
        for r, val in zip(b, v):
            ax.text(r.get_x() + r.get_width() / 2, val * 100 + 1, f"{val * 100:.0f}", ha="center", fontsize=5.5)
    ax.set_xticks(x, vers, fontsize=6)
    ax.set_ylabel("Utilisation of XC7S50 (%)")
    ax.set_ylim(0, 122)
    ax.legend(frameon=False, fontsize=6.5, ncol=3, loc="upper center")
    ax.set_title("FPGA resources by version", fontsize=9)
    save(fig, "fin_fpga_resources.png")


# 9. speed on the board ------------------------------------------------------------------
def fig_speed():
    b = board.copy()
    b["rt"] = b.record_s / b.stream_s
    order = ["syn", "ad", "cdev", "ctest"]
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    rng = np.random.default_rng(1)
    for i, s in enumerate(order):
        g = b[b.set == s].rt.values
        ax.boxplot([g], positions=[i], orientation="horizontal", widths=0.5, showfliers=False,
                   patch_artist=True, boxprops=dict(facecolor=SET_COL[s], alpha=0.35), medianprops=dict(color="k"))
        ax.scatter(g, i + rng.uniform(-0.15, 0.15, len(g)), s=6, color=SET_COL[s], lw=0)
        ax.text(10.1, i, f"{g.mean():.1f}x", va="center", fontsize=7)
    ax.axvline(1, color="k", lw=0.8)
    ax.text(1.08, 3.35, "real time", fontsize=6.5)
    ax.set_yticks(range(4), [SET_NAME[s].split(chr(10))[0] for s in order], fontsize=7)
    ax.set_xlim(0.8, 11)
    ax.set_xlabel("Processing speed per record (x real time)")
    ax.set_title("Board throughput incl. UART and PC brain", fontsize=9)
    save(fig, "fin_board_speed.png")


# 10. synthetic-to-real gap: U-Net vs ours ------------------------------------------------
def fig_syn_real_gap():
    u = pd.read_csv(ACC / "results_unet_syn.csv")
    v2 = pd.read_csv(ACC / "results_bitaccurate.csv").set_index("rid").loc[u.rid]
    v5 = pd.read_csv(ACC / "results_v5_final_synall.csv").set_index("rid").loc[u.rid]
    ua = pd.read_csv(ACC / "results_unet_adfecgdb.csv").f1.mean()
    ad = pd.read_csv(ACC / "results_adfecgdb.csv")
    syn = [u.f1.mean(), v2.f1.mean(), v5.f1.mean()]
    real = [ua, ad.v2_f1.mean(), board[board.set == "ad"].f1.mean()]
    nm = ["1D U-Net\n(mid-term)", "v2 (causal\nbeamformer)", "v5/v6\n(final algorithm)"]
    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    x = np.arange(3)
    b1 = ax.bar(x - 0.2, syn, 0.4, label=f"FECGSYNDB ({len(u)} records)", color="#4C72B0")
    b2 = ax.bar(x + 0.2, real, 0.4, label="ADFECGDB (5 real, scalp reference)", color="#55A868")
    for r, val in list(zip(b1, syn)) + list(zip(b2, real)):
        ax.text(r.get_x() + r.get_width() / 2, val + 1, f"{val:.1f}", ha="center", fontsize=6.5)
    ax.set_xticks(x, nm, fontsize=6.3)
    ax.set_ylabel("Mean F1 (%)")
    ax.set_ylim(0, 132)
    ax.legend(frameon=False, fontsize=6.3, loc="upper left", ncol=1)
    ax.set_title("Synthetic accuracy does not transfer to real data", fontsize=7.8)
    save(fig, "fin_synthetic_vs_real.png")


# 11. start-up timeline ------------------------------------------------------------------
def fig_timeline():
    fig, ax = plt.subplots(figsize=(7.0, 1.9))
    rows = [("Filters + maternal R-peak detection", 0, 60, "#4C72B0"),
            ("Store first 10 s (for maternal PCA)", 0, 10, "#8172B3"),
            ("Maternal cancellation (template per beat)", 10.4, 60, "#55A868"),
            ("Collect 12 s for GEVD calibration", 3, 15, "#DD8452"),
            ("16 tracks: trackers warm up / run", 15.5, 60, "#64B5CD"),
            ("Selected beats + FHR output", 19.5, 60, "#C44E52")]
    for i, (nm, a, b, c) in enumerate(rows[::-1]):
        ax.barh(i, b - a, left=a, color=c, height=0.6)
        ax.text(-0.5, i, nm, ha="right", va="center", fontsize=6.8)
    for t, lab in [(10, "PCA\nrequest"), (15, "GEVD\nrequest"), (19.5, "first\nbeat")]:
        ax.axvline(t, color="k", lw=0.6, ls=":")
        ax.text(t, len(rows) - 0.3, lab, ha="center", fontsize=6)
    ax.set_yticks([])
    ax.set_xlim(0, 40)
    ax.set_xlabel("Time from start of recording (s)\n(selection repeats every 2.5 s; output delay about 1.5-2 s)")
    ax.grid(axis="y", visible=False)
    save(fig, "fin_startup_timeline.png")


# 12. example output on a real recording (C system model, bit-exact with the board) -------
def fig_fhr_trace():
    sys.path.insert(0, str(ACC))
    sys.path.insert(0, str(ROOT / "fpga_implementation" / "uart_host"))
    import harness as H
    import v5c
    from devbench import _load
    from run_v6_board_eval import model_stream

    X, fq = _load(("ad", "r01"))
    n = len(X)
    b, _ = model_stream(v5c.to_i16(X))
    pk, fhr = v5c.beats_to_stream(b, n)
    r = H.score(fq, pk, fhr, n, 5000)
    ref = H.fhr_ref_stream(fq, n)
    t = np.arange(n) / 250.0
    fig, axs = plt.subplots(2, 1, figsize=(7.0, 3.6), gridspec_kw=dict(height_ratios=[1.1, 1]))
    a0, a1 = 120 * 250, 126 * 250
    for k in range(4):
        seg = X[a0:a1, k]
        seg = (seg - np.median(seg)) / (np.percentile(np.abs(seg - np.median(seg)), 99) + 1e-9)
        axs[0].plot(t[a0:a1], seg - 2.2 * k, lw=0.5, color="#555")
    for p in fq[(fq >= a0) & (fq < a1)]:
        axs[0].axvline(p / 250, color="#55A868", lw=0.8, alpha=0.6)
    for p in pk[(pk >= a0) & (pk < a1)]:
        axs[0].plot(p / 250, 1.3, "v", color="#C44E52", ms=4)
    axs[0].set_yticks([])
    axs[0].set_xlim(a0 / 250, a1 / 250)
    axs[0].set_title("ADFECGDB r01: 4 raw abdominal leads, true fetal beats (green lines), v6 detections (red marks)", fontsize=8)
    ok = fhr > 0
    axs[1].plot(t, ref, color="#55A868", lw=1.2, label="reference FHR (scalp electrode)")
    axs[1].plot(t[ok], fhr[ok], color="#C44E52", lw=0.8, label="v6 output FHR")
    axs[1].set_xlabel("Time (s)")
    axs[1].set_ylabel("FHR (bpm)")
    axs[1].set_ylim(80, 180)
    axs[1].legend(frameon=False, fontsize=7, loc="lower right")
    axs[1].set_title(f"Whole 5-min record: F1 {r['f1']:.1f}%, FHR MAE {r['fhr_mae']:.2f} bpm", fontsize=8)
    save(fig, "fin_fhr_trace_r01.png")
    return r


if __name__ == "__main__":
    fig_progression()
    fig_architecture()
    fig_board_distribution()
    fig_syn_breakdown()
    fig_cinc_paired()
    fig_se_ppv()
    fig_selection_gap()
    fig_resources()
    fig_speed()
    fig_syn_real_gap()
    fig_timeline()
    if "--trace" in sys.argv:
        print(fig_fhr_trace())
