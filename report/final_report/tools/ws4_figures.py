#!/usr/bin/env python3
"""
WS4: mid-term figures regenerated from result files instead of values typed into the mid-term script.
Writes into report/final_report/figures/ only (run AFTER fix_midterm_figures.py; it replaces two of its outputs).

  signal_amplitude_disparity.png  Fig. 1: measured maternal / fetal beat amplitude and FMR range
                                   (tools/report_stats/out/amplitude_measured.csv, from tools/report_stats/fmr_measured.py)
  f1_heatmap.png, f1_comparison_all_methods.png, snr_degradation_curve.png
        single-channel rows: code/results/metrics.csv (TC1-TC5)
        Spatial PCA and MC template fusion (4 leads): code/results/multichannel_scaling_metrics.csv
        Deep U-Net (1-ch): code/results/mega_benchmark_results.csv, the sub01 l1 records of TC1-TC5 (a separate run)
  multichannel_fpga_resource_scaling.png   code/results/multichannel_scaling_metrics.csv (analytical model columns)
  eigenvalue_subspace_spectrum.png        tools/report_stats/out/r3_eigen.csv (WS3, tools/report_stats/r3_eigen.py)

    venv/Scripts/python.exe report/final_report/tools/ws4_figures.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "report/final_report/figures"
RS = ROOT / "tools/report_stats/out"
plt.rcParams.update({"font.size": 9, "axes.labelsize": 10, "axes.titlesize": 11, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "legend.fontsize": 8})
TCS = ["TC1", "TC2", "TC3", "TC4", "TC5"]
TC_LAB = ["TC1\n(12 dB)", "TC2\n(6 dB)", "TC3\n(0 dB)", "TC4\n(Motion)", "TC5\n(Ectopic)"]
TC_DEF = {"TC1": (12, "c0"), "TC2": (6, "c0"), "TC3": (0, "c0"), "TC4": (6, "c1"), "TC5": (6, "c4")}


def save(fig, name):
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT / name)


def subject1_matrix():
    """F1 (%) of seven methods on Subject 1 TC1-TC5, each row from the file named in ROWS."""
    met = pd.read_csv(ROOT / "code/results/metrics.csv")
    mc = pd.read_csv(ROOT / "code/results/multichannel_scaling_metrics.csv")
    mega = pd.read_csv(ROOT / "code/results/mega_benchmark_results.csv")
    rows = {}
    for nm, key in [("Spatial PCA (4-Ch)", "spatial_pca_beamforming"), ("MC Template Fusion (4-Ch)", "multichannel_template_subtraction_fusion")]:
        x = mc[(mc.method == key) & (mc.n_channels == 4)].set_index("test_id").f1
        rows[nm] = [100 * x[t] for t in TCS]
    s1 = mega[(mega.sub_id == "sub01") & (mega.layout == "l1") & (mega.method == "Deep_UNet_1ch")]
    rows["Deep 1D U-Net (1-Ch)"] = [100 * s1[(s1.snr_db == TC_DEF[t][0]) & (s1.case_id == TC_DEF[t][1])].f1.iloc[0] for t in TCS]
    for nm, (m, v) in [("Wavelet-Threshold Hybrid", ("alternative", "default")), ("Template Sub. (Fixed)", ("template_subtraction", "fixed_ensemble")),
                       ("Hankel-SVD V1", ("SVD", "variant_1_fixed_period")), ("SWT-LMS-SSNF", ("SWT_LMS_SSNF", "swt_lms_ssnf"))]:
        x = met[(met.method == m) & (met.variant == v)].set_index("test_id").f1
        rows[nm] = [100 * x[t] for t in TCS]
    df = pd.DataFrame(rows, index=TCS).T
    df.to_csv(RS / "ws4_subject1_matrix.csv", float_format="%.2f")
    return df


def fig_heatmap(df):
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    im = ax.imshow(df.values, cmap="YlGnBu", aspect="auto", vmin=10, vmax=100)
    ax.set_xticks(range(5), TC_LAB, fontweight="bold")
    ax.set_yticks(range(len(df)), df.index, fontweight="bold")
    for i in range(len(df)):
        for j in range(5):
            v = df.values[i, j]
            ax.text(j, i, f"{v:.1f}%", ha="center", va="center", color="white" if v > 65 else "black", fontweight="bold", fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.85).set_label("F1-Score (%)", fontweight="bold")
    ax.set_title("Subject 1 F1-Score Matrix", fontweight="bold", pad=10)
    fig.tight_layout()
    save(fig, "f1_heatmap.png")


def fig_bars(df):
    fig, ax = plt.subplots(figsize=(10.5, 3.8))
    x = np.arange(5)
    w = 0.8 / len(df)
    cols = plt.cm.tab10(np.arange(len(df)))
    for k, (nm, row) in enumerate(df.iterrows()):
        ax.bar(x - 0.4 + (k + 0.5) * w, row.values, w, label=nm, color=cols[k], edgecolor="black", linewidth=0.4)
    ax.set_xticks(x, TC_LAB)
    ax.set_ylabel("F1-Score (%)", fontweight="bold")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4, frameon=False)
    ax.set_title("F1-Score per Method on the Subject 1 Test Cases", fontweight="bold")
    fig.tight_layout()
    save(fig, "f1_comparison_all_methods.png")


def fig_snr(df):
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    snr = [12, 6, 0]
    for nm, row in df.iterrows():
        ax.plot(snr, row.values[:3], "o-", label=nm, lw=1.6, ms=4)
    ax.set_xlabel("Input SNR (dB)", fontweight="bold")
    ax.set_ylabel("F1-Score (%)", fontweight="bold")
    ax.set_xticks(snr)
    ax.invert_xaxis()
    ax.set_ylim(0, 105)
    ax.grid(linestyle="--", alpha=0.4)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, frameon=False)
    ax.set_title("F1 against Input SNR (Subject 1, condition c0)", fontweight="bold")
    fig.tight_layout()
    save(fig, "snr_degradation_curve.png")


def fig_scaling():
    mc = pd.read_csv(ROOT / "code/results/multichannel_scaling_metrics.csv")
    x = mc[(mc.method == "spatial_pca_beamforming") & (mc.test_id == "TC1")].sort_values("n_channels")
    fig, ax1 = plt.subplots(figsize=(7.2, 3.6))
    ax1.step(x.n_channels, x.dsp_slices, where="mid", color="#2980b9", lw=2.2, label="DSP48E1 slices (model)")
    ax1.set_xlabel("Number of leads", fontweight="bold")
    ax1.set_ylabel("DSP48E1 slices (model)", color="#2980b9", fontweight="bold")
    ax1.set_ylim(0, 6)
    ax1.grid(linestyle="--", alpha=0.4)
    ax2 = ax1.twinx()
    ax2.plot(x.n_channels, x.uart_util_921k, "s--", color="#c0392b", lw=1.6, ms=4, label="UART use at 921,600 baud (model)")
    ax2.set_ylabel("UART use (%)", color="#c0392b", fontweight="bold")
    ax2.set_ylim(0, 25)
    r4 = x[x.n_channels == 4].iloc[0]
    ax1.axvline(4, color="#27ae60", ls=":", lw=1.5)
    ax1.text(4.6, 4.8, f"4 leads: {int(r4.dsp_slices)} DSP, {int(r4.luts)} LUTs,\n{r4.uart_util_921k:.1f}% UART (analytical model)", color="#27ae60", fontsize=8, fontweight="bold")
    ax1.set_title("Analytical Resource Model of the Mid-term Beamformer", fontweight="bold")
    fig.tight_layout()
    save(fig, "multichannel_fpga_resource_scaling.png")


def fig_eigen():
    e = pd.read_csv(RS / "r3_eigen.csv")
    subj, mean = e[e["sub"] != "mean"], e[e["sub"] == "mean"].iloc[0]
    fig, axs = plt.subplots(1, 2, figsize=(7.5, 3.0))
    for ax, pre, title in [(axs[0], "var_v", "(a) Share of mixture variance"), (axs[1], "fetal_v", "(b) Share of fetal energy")]:
        cols = [f"{pre}{i}" for i in range(1, 5)]
        ax.bar(range(4), [mean[c] for c in cols], color=["#c0392b", "#27ae60", "#7f8c8d", "#95a5a6"], edgecolor="black", alpha=0.85)
        for k, c in enumerate(cols):
            ax.scatter(np.full(len(subj), k) + np.linspace(-0.15, 0.15, len(subj)), subj[c], s=8, color="black", zorder=3)
            ax.text(k, mean[c] + 3, f"{mean[c]:.1f}%", ha="center", fontsize=8, fontweight="bold")
        ax.set_xticks(range(4), ["v1", "v2", "v3", "v4"])
        ax.set_ylim(0, 110)
        ax.set_title(title, fontweight="bold")
        ax.grid(axis="y", linestyle="--", alpha=0.4)
    axs[0].set_ylabel("%", fontweight="bold")
    fig.tight_layout()
    save(fig, "eigenvalue_subspace_spectrum.png")


def fig_amplitude():
    a = pd.read_csv(RS / "amplitude_measured.csv").iloc[0]
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    ax.bar(["Maternal ECG", "Fetal ECG"], [a.maternal_pp_mV, a.fetal_pp_mV], color=["#c0392b", "#2980b9"], width=0.5, edgecolor="black", alpha=0.85)
    for k, v in enumerate([a.maternal_pp_mV, a.fetal_pp_mV]):
        ax.text(k, v * 1.03, f"{v:.2f}", ha="center", va="bottom", fontweight="bold")
    ax.set_ylabel("Median beat peak-to-peak\n(FECGSYNDB normalised units)", fontweight="bold")
    ax.set_ylim(0, a.maternal_pp_mV * 1.35)
    ax.text(0.5, a.maternal_pp_mV * 1.18, f"ratio {a.ratio:.1f}x ({a.ratio_dB:.1f} dB); RMS FMR per lead {a.fmr_min:.2f}-{a.fmr_max:.2f}",
            ha="center", fontsize=8.5, bbox=dict(boxstyle="round,pad=0.3", facecolor="#f8f9fa", edgecolor="#bdc3c7"))
    ax.set_title("Maternal and Fetal Amplitude on FECGSYNDB Training Leads", fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    save(fig, "signal_amplitude_disparity.png")


if __name__ == "__main__":
    m = subject1_matrix()
    print(m.round(1))
    fig_heatmap(m)
    fig_bars(m)
    fig_snr(m)
    fig_scaling()
    fig_eigen()
    fig_amplitude()
