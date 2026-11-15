#!/usr/bin/env python3
"""
Corrected versions of mid-term figures used in the final report (review fixes, 15 Nov).

Writes into report/final_report/figures/ only; the mid-term report and its generator
(report/mid_term/tools/generate_all_audited_figures.py) stay unchanged. Plot style is taken
from the mid-term generator.

  Fig. 1  signal_amplitude_disparity.png  FMR range from the measured per-lead values
  Fig. 2  system_pipeline.png             title above the frame, labels inside their boxes
  Fig. 3  fmr_lead_topography_34ch.png    measured per-lead FMR (sub01-sub07, l1, c0) from FECGSYNDB
  Fig. 7  fhr_error_bland_altman.png      legend entry "Vivek Hybrid" -> "Wavelet Hybrid"
                                           (no generator script exists; the legend text is repainted)
  Fig. 9  f1_heatmap.png                  two-line column labels (no overlap)
  Fig. 12 mega_f1_by_method.png           SD bars clipped to [0, 100] %, labels beside the bars
  Fig. 17 dsp_time_multiplexing_schedule  summary box inside the axes, clear of the axis title
  Fig. 19 hw_accuracy_tradeoff.png        y axis refers to Tab. 7 (population means); legend below the axes
  Fig. 21 runtime_comparison.png          times from code/results/mega_benchmark_summary.csv,
                                           FPGA 148 cycles x 10 ns x 75,000 = 111 ms

    venv/Scripts/python.exe report/final_report/tools/fix_midterm_figures.py
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont
import wfdb

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "report/final_report/figures"
MID = ROOT / "report/mid_term"

# plot style (rcParams) of the mid-term generator
_spec = importlib.util.spec_from_file_location("mid_figs", MID / "tools/generate_all_audited_figures.py")
_mid = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mid)

SEL = [27, 26, 28, 25]  # mid-term 4-lead sub-array (0-based)


def save(fig, name):
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT / name)


def measured_fmr():
    """fetal/maternal RMS ratio per lead, mean over sub01-sub07 (snr12dB, l1, c0; FMR does not depend on noise)"""
    base = ROOT / "data/FECGSD/DESTINATION"
    rows = []
    for s in range(1, 8):
        r = base / f"sub{s:02d}/snr12dB/sub{s:02d}_snr12dB_l1_c0"
        f = wfdb.rdrecord(str(r) + "_fecg1").p_signal
        m = wfdb.rdrecord(str(r) + "_mecg").p_signal
        rows.append(np.sqrt((f ** 2).mean(0)) / np.sqrt((m ** 2).mean(0)))
    return np.mean(rows, axis=0)


def fig1_amplitude(fmr):
    lo, hi = fmr[:32].min(), fmr[:32].max()
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    cats = ['Maternal ECG\n(Abdominal Peak)', 'Fetal ECG\n(Suprapubic Peak)', 'EMG Noise\n(Muscle Activity)', 'Baseline Drift\n(Respiration)']
    amps = [2.50, 0.04, 0.15, 0.25]
    ax.bar(cats, amps, color=['#c0392b', '#2980b9', '#7f8c8d', '#f39c12'], width=0.52, edgecolor='black', linewidth=0.8, alpha=0.85)
    ax.set_ylabel('Peak-to-Peak Amplitude (mV, Log Scale)', fontweight='bold')
    ax.set_title('Biopotential Amplitude Disparity on Abdominal Surface Leads', fontweight='bold', pad=12)
    ax.set_yscale('log')
    ax.set_ylim(0.008, 15.0)
    ax.grid(True, which='both', linestyle='--', alpha=0.4)
    ax.text(0, 3.2, '2.50 mV\n(Dominant)', ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#c0392b')
    ax.text(1, 0.05, '0.04 mV (40 µV)\n[62.5× weaker]', ha='center', va='bottom', fontsize=8.5, fontweight='bold', color='#2980b9')
    ax.text(2, 0.19, '0.15 mV', ha='center', va='bottom', fontsize=8.5)
    ax.text(3, 0.32, '0.25 mV', ha='center', va='bottom', fontsize=8.5)
    ax.annotate('', xy=(1, 0.04), xytext=(0, 2.5), arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=1.5, linestyle=':'))
    callout = ("Amplitude Disparity:\n"
               "• Specific Callout: 2.50 mV vs 0.04 mV = 62.5× (35.9 dB)\n"
               "• Clinical Literature Range: 10–250× (20–48 dB)\n"
               f"• Measured Training RMS FMR per lead: {lo:.2f}–{hi:.2f} "
               f"({20 * np.log10(lo):.1f} to {20 * np.log10(hi):.1f} dB)")
    ax.text(2.0, 3.6, callout, ha='center', va='center', fontsize=8,
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#f8f9fa', edgecolor='#bdc3c7', lw=1.2))
    fig.tight_layout()
    save(fig, 'signal_amplitude_disparity.png')


def fig2_pipeline():
    fig, ax = plt.subplots(figsize=(12.0, 4.4))
    ax.set_xlim(0, 16.1)
    ax.set_ylim(0.2, 5.9)
    ax.axis('off')

    def box(x, y, w, h, title, sub, color, bg):
        ax.add_patch(patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15", ec=color, fc=bg, lw=1.6))
        ax.text(x + w / 2, y + h * 0.72, title, ha='center', va='center', fontweight='bold', fontsize=7.8, color=color)
        ax.text(x + w / 2, y + h * 0.33, sub, ha='center', va='center', fontsize=7.2, color='#2c3e50')

    def arrow(x1, y1, x2, y2, label="", dy=0.0):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(facecolor='#2c3e50', edgecolor='#2c3e50', arrowstyle='->', lw=1.5))
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, label, ha='center', va='center', fontsize=7.0, fontweight='bold',
                    color='#2c3e50', bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none'))

    box(0.3, 2.2, 1.8, 1.6, "1. Acquisition", "4-Ch Suprapubic\n[27, 26, 28, 25]\nFs = 250 Hz", "#2980b9", "#ebf5fb")
    arrow(2.25, 3.0, 2.75, 3.0)
    box(2.9, 2.2, 1.8, 1.6, "2. Preprocessing", "4-SOS Butterworth\n0.5–40 Hz (8th-ord)\n4 Ch × 4 SOS = 80c", "#2980b9", "#ebf5fb")
    arrow(4.85, 3.0, 5.35, 3.0)
    box(5.5, 2.2, 1.8, 1.6, "3. Mains Rejection", "Dual 50/60 Hz\nNotch Filter (IIR)\n4 Ch × 1 SOS = 20c", "#c0392b", "#fdebd0")
    arrow(7.45, 3.3, 8.45, 3.95, "Primary", dy=0.18)
    arrow(7.45, 2.7, 8.45, 1.75, "Baselines", dy=-0.2)
    box(8.6, 3.25, 2.7, 1.5, "4A. Spatial Beamformer", "w = v2 (suppress v1)\nSingle DSP48E1 (4c)\nQ1.15 Fixed-Point", "#27ae60", "#e8f8f5")
    box(8.6, 0.75, 2.7, 1.5, "4B. Comparison Baselines", "Pan-Tompkins Maternal QRS\nTemplate Sub. / SVD\n[Comparison Only]", "#7f8c8d", "#f2f4f4")
    arrow(11.45, 4.0, 11.95, 3.3)
    arrow(11.45, 1.5, 11.95, 2.7)
    box(12.1, 2.2, 2.2, 1.6, "5. Fetal QRS Detector", "Peak-Energy Detector\n5-pt Deriv + Square\nInt W=15, Dual Thresh", "#8e44ad", "#f4ecf7")
    arrow(14.45, 3.0, 14.75, 3.0)
    box(14.9, 2.2, 0.95, 1.6, "6. Display\n& UART", "FHR Med-5\n7-Seg\nUART", "#d35400", "#fef5e7")
    ax.add_patch(patches.FancyBboxPatch((2.65, 0.45), 13.35, 4.65, boxstyle="round,pad=0.1", ec='#1b4f72', fc='none', lw=1.5, linestyle='--'))
    ax.text(9.2, 5.55, "Target FPGA Hardware Pipeline (Xilinx Spartan-7 XC7S50 @ 100 MHz oscillator) [L4 Target]",
            ha='center', va='center', fontweight='bold', fontsize=9.0, color='#1b4f72')
    save(fig, 'system_pipeline.png')


def fig3_fmr(fmr):
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ch = np.arange(34)
    colors = ['#2980b9' if c in SEL else ('#c0392b' if c >= 32 else '#95a5a6') for c in ch]
    ax.bar(ch, fmr, color=colors, width=0.7, edgecolor='black', linewidth=0.6, alpha=0.85)
    ax.set_xlabel('Physical Electrode Channel Index (0-based, Leads 0 to 33)', fontweight='bold')
    ax.set_ylabel('Fetal-to-Maternal Ratio (RMS_f / RMS_m)', fontweight='bold')
    ax.set_title('34-Lead FMR Topography (Training Partition: sub01–sub07, mean)', fontweight='bold', pad=10)
    ax.set_xticks(np.arange(0, 34, 2))
    ax.set_ylim(0, 0.95)
    ax.grid(True, linestyle='--', alpha=0.4, axis='y')
    ax.axvspan(24.5, 28.5, color='#27ae60', alpha=0.18, label='Selected Sub-Array [27, 26, 28, 25]')
    ax.axvspan(31.5, 33.5, color='#e74c3c', alpha=0.18, label='Maternal Thoracic Leads (32, 33)')
    top = int(np.argmax(fmr))
    ax.annotate(f'Lead {top} (FMR = {fmr[top]:.2f}, highest)', xy=(top, fmr[top]), xytext=(top, 0.75),
                arrowprops=dict(facecolor='black', arrowstyle='->', lw=1.0), fontsize=8, fontweight='bold', ha='center',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#f4f6f7', edgecolor='#7f8c8d'))
    ax.annotate(f'Leads 26 / 27 (FMR = {fmr[26]:.2f} / {fmr[27]:.2f})', xy=(26.5, max(fmr[26], fmr[27])), xytext=(33.6, 0.64),
                arrowprops=dict(facecolor='black', arrowstyle='->', lw=1.0), fontsize=8, fontweight='bold', ha='right',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#eef2f7', edgecolor='#2980b9'))
    ax.legend(loc='upper left', framealpha=0.9, fontsize=8)
    fig.tight_layout()
    save(fig, 'fmr_lead_topography_34ch.png')


def fig7_legend():
    """repaint the legend entry 'Vivek Hybrid' of the mid-term PNG (row y 214-241, text from x 288)"""
    im = Image.open(MID / "figures/fhr_error_bland_altman.png").convert("RGB")
    a = np.asarray(im).astype(int)
    x0, y0, y1 = 286, 210, 246
    row = a[y0:y1, x0:560].sum(2)
    xs = np.where((row < 300).any(0))[0]
    assert len(xs) and xs.max() < 200, "legend text not where expected"
    font_path = font_manager.findfont("DejaVu Sans")
    ref = a[129:157, x0:600].sum(2)   # first legend label 'Spatial PCA (4-Ch)', for the font size
    ref_w = np.where((ref < 300).any(0))[0].max() + 1
    size = 10
    while ImageFont.truetype(font_path, size + 1).getlength("Spatial PCA (4-Ch)") <= ref_w:
        size += 1
    font = ImageFont.truetype(font_path, size)
    d = ImageDraw.Draw(im)
    d.rectangle([x0, y0, x0 + xs.max() + 6, y1], fill=(255, 255, 255))
    text = "Wavelet Hybrid"   # short form like the other entries; "Wavelet-Thr. Hybrid" does not fit the box
    assert x0 + font.getlength(text) < 562, "new label wider than the legend box"
    top = 214 - (font.getbbox("W")[1])   # align the cap height with the old text
    d.text((x0 + 2, top), text, font=font, fill=(0, 0, 0))
    im.save(OUT / "fhr_error_bland_altman.png", dpi=(300, 300))
    print("wrote", OUT / "fhr_error_bland_altman.png")


def fig9_heatmap():
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    cases = ['TC1\n(12 dB)', 'TC2\n(6 dB)', 'TC3\n(0 dB)', 'TC4\n(Motion)', 'TC5\n(Arrhythmia)']
    methods = ['Spatial PCA (4-Ch)', 'Deep 1D U-Net (1-Ch)', 'MC Template Fusion (4-Ch)', 'Wavelet-Threshold Hybrid',
               'Template Sub. (Fixed)', 'Hankel-SVD V1', 'SWT-LMS Wavelet Filter']
    m = np.array([[100.0, 100.0, 100.0, 72.8, 88.0], [99.7, 99.8, 99.4, 99.6, 94.5], [97.8, 94.1, 31.4, 58.6, 67.0],
                  [77.3, 31.4, 24.6, 36.8, 28.1], [76.4, 30.8, 23.9, 35.7, 28.5], [76.4, 31.0, 23.7, 36.0, 27.7],
                  [15.1, 17.6, 19.2, 18.5, 14.6]])   # values of the mid-term figure
    im = ax.imshow(m, cmap='YlGnBu', aspect='auto', vmin=10, vmax=100)
    ax.set_xticks(np.arange(len(cases)))
    ax.set_yticks(np.arange(len(methods)))
    ax.set_xticklabels(cases, fontweight='bold')
    ax.set_yticklabels(methods, fontweight='bold')
    for i in range(len(methods)):
        for j in range(len(cases)):
            ax.text(j, i, f"{m[i, j]:.1f}%", ha="center", va="center", color="white" if m[i, j] > 65 else "black",
                    fontweight="bold", fontsize=8)
    cb = fig.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label('F1-Score (%)', fontweight='bold')
    ax.set_title('Subject 1 F1-Score Matrix across Extraction Paradigms', fontweight='bold', pad=10)
    fig.tight_layout()
    save(fig, 'f1_heatmap.png')


def fig12_mega():
    df = pd.read_csv(ROOT / "code/results/mega_benchmark_results.csv")
    names = {'Wavelet_Threshold_Hybrid': 'Wavelet-Threshold Hybrid', 'Spatial_PCA_4ch': 'Spatial PCA (4-Ch)',
             'Deep_UNet_4ch': 'Deep U-Net (4-Ch)', 'Deep_UNet_1ch': 'Deep U-Net (1-Ch)',
             'MC_Template_Fusion_4ch': 'MC Template Fusion', 'Template_Sub_Fixed': 'Template Sub. (Fixed)',
             'Template_Sub_Adaptive': 'Template Sub. (Adapt.)', 'SVD_V1_Fixed': 'Hankel-SVD V1', 'SVD_V3_Moving': 'Hankel-SVD V3'}
    df['name'] = df['method'].map(lambda k: names.get(k, k))
    st = df.groupby('name')['f1'].agg(['mean', 'std']).reset_index()
    st['mean'] *= 100
    st['std'] *= 100
    st = st.sort_values('mean')
    lo = np.minimum(st['std'], st['mean'])
    hi = np.minimum(st['std'], 100 - st['mean'])
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    colors = ['#1b9e77' if 'Spatial' in n else ('#d95f02' if 'Deep' in n else '#7570b3') for n in st['name']]
    bars = ax.barh(st['name'], st['mean'], xerr=[lo, hi], color=colors, height=0.6, edgecolor='black', alpha=0.85, capsize=3)
    ax.set_xlabel('Mean F1-Score (%)  [± 1 SD, clipped to 0–100 %]', fontweight='bold')
    ax.set_title('FECGSYNDB Population Benchmark\n(250 Records, 2,250 Runs)', fontweight='bold', pad=8)
    ax.set_xlim(0, 125)
    ax.set_xticks(range(0, 101, 20))
    ax.grid(axis='x', linestyle='--', alpha=0.4)
    for b, v, h in zip(bars, st['mean'], hi):
        ax.text(v + h + 2.0, b.get_y() + b.get_height() / 2, f'{v:.2f}%', va='center', fontsize=7.5, fontweight='bold')
    fig.tight_layout()
    save(fig, 'mega_f1_by_method.png')


def fig17_dsp():
    fig, ax = plt.subplots(figsize=(8.0, 3.9))
    stages = [('Butterworth SOS\n(4 Ch × 4 SOS × 5)', 0, 80, '#2980b9'), ('Notch\n(4 × 1 SOS × 5)', 80, 20, '#e74c3c'),
              ('Spatial PCA\n(4 Ch × 1)', 100, 4, '#27ae60'), ('Derivative\n(5-tap)', 104, 5, '#f39c12'), ('Square', 109, 1, '#8e44ad'),
              ('Moving Int.\n(W=15)', 110, 2, '#16a085'), ('Threshold\nCompare', 112, 4, '#d35400'),
              ('Refractory\nCounter', 116, 2, '#7f8c8d'), ('DSP48 Pipeline\n& Staging Latency', 118, 30, '#34495e')]
    y, h = 0.45, 0.5
    for name, start, dur, color in stages:
        ax.add_patch(patches.Rectangle((start, y - h / 2), dur, h, linewidth=0.8, edgecolor='black', facecolor=color, alpha=0.85))
        if dur >= 15:
            ax.text(start + dur / 2, y, f'{name}\n[{dur} cyc]', ha='center', va='center', color='white', fontweight='bold', fontsize=7.2)
        elif dur >= 4:
            ax.text(start + dur / 2, y, f'{dur}', ha='center', va='center', color='white', fontweight='bold', fontsize=7)
    ax.set_xlim(0, 160)
    ax.set_ylim(0, 1.32)
    ax.set_xlabel('Clock Cycles at 100 MHz (1 Cycle = 10 ns) — Per-Sample Critical Path: 148 Cycles = 1.48 µs', fontweight='bold')
    ax.set_title('Single-DSP48E1 Time-Multiplexed Execution Schedule (Peak-Energy QRS Detector Pipeline)', fontweight='bold', pad=12)
    ax.set_yticks([])
    ax.grid(axis='x', linestyle='--', alpha=0.4)
    summary = ("Timing Budget & Margin on Spartan-7:\n"
               "• Total Per-Sample Sized Latency: 148 clock cycles = 1.48 µs\n"
               "• Available Real-Time Sampling Budget (Fs = 250 Hz): 400,000 cycles = 4,000 µs (4.0 ms)\n"
               "• Compute Duty Cycle: 148 / 400,000 = 0.037% (2,702× Real-Time Processing Margin)")
    ax.text(80, 1.27, summary, ha='center', va='top', fontsize=8,
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#eef2f7', edgecolor='#2980b9', lw=1.2))
    fig.tight_layout()
    save(fig, 'dsp_time_multiplexing_schedule.png')


def fig19_tradeoff():
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    methods = [('Spatial PCA (4-Ch) [Ours]', 990, 93.00, '#1b9e77', 'o', 100), ('Wavelet-Thr. Hybrid', 1320, 60.52, '#e7298a', 's', 70),
               ('Template Sub. (Fixed)', 1020, 59.41, '#66a61e', '^', 70), ('MC Template Fusion (4-Ch)', 1650, 56.80, '#7570b3', 'D', 70),
               ('Template Sub. (Adapt.)', 1480, 56.83, '#1abc9c', 'v', 60), ('Hankel-SVD V1 (Fixed)', 4200, 55.55, '#e6ab02', 'P', 80),
               ('Hankel-SVD V3 (Moving)', 3800, 46.69, '#d35400', 'X', 70), ('Deep 1D U-Net (Edge FPGA)', 28400, 90.76, '#d95f02', '*', 120)]
    for name, lut, f1, color, marker, sz in methods:
        ax.scatter(lut, f1, color=color, marker=marker, s=sz, edgecolors='black', linewidth=0.8, label=name, zorder=5)
        if 'Spatial PCA' in name:
            ax.annotate(f'{name}\n93.00% F1 | 990 LUTs (3.0%)', xy=(lut, f1), xytext=(lut * 1.25, f1 - 1.5),
                        arrowprops=dict(facecolor='black', arrowstyle='->', lw=1.0), fontweight='bold', fontsize=8, color='#1b9e77',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='#eef2f7', edgecolor='#1b9e77'))
        elif 'Deep 1D U-Net' in name:
            ax.annotate(f'{name}\n90.76% F1 | 28.4k LUTs (87.1%)\n[Infeasible on-chip; needs external DRAM]', xy=(lut, f1),
                        xytext=(lut * 0.45, f1 - 9.0), arrowprops=dict(facecolor='black', arrowstyle='->', lw=1.0), fontsize=7.5,
                        color='#d95f02', bbox=dict(boxstyle='round,pad=0.2', facecolor='#fdf2e9', edgecolor='#d95f02'))
    ax.axvline(32600, color='red', linestyle='--', lw=1.4, label='XC7S50 Device Capacity (32,600 LUTs)')
    ax.set_xscale('log')
    ax.set_xlabel('Estimated Logic LUT Utilization on Spartan-7 (Log Scale)', fontweight='bold')
    ax.set_ylabel('Population Mean F1-Score (%) [Tab. 7]', fontweight='bold')
    ax.set_title('Hardware Resource Sizing vs. Detection Accuracy Pareto Trade-Off', fontweight='bold', pad=10)
    ax.set_xlim(500, 50000)
    ax.set_ylim(40, 100)
    ax.grid(True, which='both', linestyle='--', alpha=0.4)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.17), framealpha=0.9, fontsize=7.2, ncol=3)
    fig.tight_layout()
    save(fig, 'hw_accuracy_tradeoff.png')


def fig21_runtime():
    s = pd.read_csv(ROOT / "code/results/mega_benchmark_summary.csv").set_index('method')['mean_runtime_ms']
    fpga_ms = 148 * 10e-9 * 75000 * 1e3   # 148 cycles at 100 MHz per sample
    rows = [('Spatial PCA (4-Ch)\n[Host CPU, 1 Thread]', s['Spatial_PCA_4ch'], '#2980b9'),
            ('Deep U-Net (4-Ch)\n[RTX 4060 GPU]', s['Deep_UNet_4ch'], '#8e44ad'),
            ('MC Template Fusion\n[Host CPU]', s['MC_Template_Fusion_4ch'], '#3498db'),
            ('Adaptive EMA TS\n[Host CPU]', s['Template_Sub_Adaptive'], '#1abc9c'),
            ('Hankel-SVD V1\n[Host CPU]', s['SVD_V1_Fixed'], '#e67e22'),
            ('FPGA Pipeline Sized\n[Spartan-7 @ 100MHz]', fpga_ms, '#27ae60')]
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    y = np.arange(len(rows))
    ax.barh(y, [r[1] for r in rows], color=[r[2] for r in rows], height=0.55, edgecolor='black', linewidth=0.7, alpha=0.85)
    ax.set_xscale('log')
    ax.set_xlim(10, 3000)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel('Execution Time per 5-Minute Record (ms, Log Scale)', fontweight='bold')
    ax.set_title('Execution Time per 5-Minute Record (75,000 Samples)', fontweight='bold', pad=10)
    ax.grid(True, which='both', linestyle='--', alpha=0.4)
    for i, (name, ms, color) in enumerate(rows):
        label = f'{ms:.1f} ms'
        if 'FPGA' in name:
            label = f'{ms:.1f} ms pure compute (1.48 µs/sample)\n[real time: 300 s at 250 Hz arrival]'
        ax.text(ms * 1.12, i, label, va='center', fontsize=8, fontweight='bold' if i in (0, 1, 5) else 'normal', color=color if i in (0, 1, 5) else 'black')
    fig.tight_layout()
    save(fig, 'runtime_comparison.png')


def main():
    fmr = measured_fmr()
    # Fig. 1 and the heatmap (Fig. 9) are now drawn from result files by ws4_figures.py (run after this script)
    fig2_pipeline()
    fig3_fmr(fmr)
    fig7_legend()
    fig12_mega()
    fig17_dsp()
    fig19_tradeoff()
    fig21_runtime()


if __name__ == "__main__":
    main()
