#!/usr/bin/env python3
"""
scratch/simulate_fhr_audit.py
──────────────────────────────────────────────────────────────────────────────
Root-Cause Audit Simulation: Fetal Heart Rate Detection Audit
Compares:
  - Case A: Flawed hardware test (unity weights w=[32768,0,0,0], maternal=8000,
            fetal=2500, both placed on channel 0).
  - Case B: True 4-channel spatial mixture with PCA beamformer weights that
            cancel maternal ECG and isolate fetal ECG.

Outputs detailed numerical metrics and diagnostic signal waveform plots.
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Ensure src is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import importlib.util

REF_PATH = os.path.join(PROJECT_ROOT, "src/fecg/hardware/bit_accurate_reference.py")
spec_bar = importlib.util.spec_from_file_location("bit_accurate_reference", REF_PATH)
bar = importlib.util.module_from_spec(spec_bar)
sys.modules["bit_accurate_reference"] = bar
spec_bar.loader.exec_module(bar)

run_bit_accurate_pipeline_final = bar.run_bit_accurate_pipeline_final
sat = bar.sat
sat_u = bar.sat_u
rshift_round_nearest_even = bar.rshift_round_nearest_even
integer_median = bar.integer_median
FHR_FROZEN_INTEGER_LUT = bar.FHR_FROZEN_INTEGER_LUT
RR_MIN = bar.RR_MIN
RR_MAX = bar.RR_MAX

def simulate_case_a():
    """
    Case A: The flawed test from Step 1341 / Section 4.3 of Hardware Report.
    """
    N = 2500
    fs = 250
    x_mixture = np.zeros((N, 4), dtype=np.int64)

    # Maternal beats at 75 bpm (RR = 200 samples)
    m_peaks = list(range(100, N, 200))
    for m_peak in m_peaks:
        for offset, amp in [(-2, -500), (-1, -1200), (0, 8000), (1, -1800), (2, 800)]:
            idx = m_peak + offset
            if 0 <= idx < N:
                x_mixture[idx, 0] += amp

    # Fetal beats at 140 bpm (RR = 107 samples)
    f_peaks = list(range(150, N, 107))
    for f_peak in f_peaks:
        for offset, amp in [(-1, -300), (0, 2500), (1, -600)]:
            idx = f_peak + offset
            if 0 <= idx < N:
                x_mixture[idx, 0] += amp

    # Unity weights: bypass channel 0
    w_unity = np.array([32768, 0, 0, 0], dtype=np.int64)

    res = run_bit_accurate_pipeline_final(x_mixture, w_unity)
    return x_mixture, w_unity, m_peaks, f_peaks, res

def simulate_case_b():
    """
    Case B: True multichannel mixture where PCA beamforming cancels maternal ECG.
    """
    N = 2500
    fs = 250
    t = np.arange(N) / fs

    # Maternal ECG at 75 bpm (RR = 200 samples)
    m_peaks = list(range(100, N, 200))
    m_ecg = np.zeros(N)
    for b in m_peaks:
        for idx, amp in [(-2, -0.2), (-1, -0.4), (0, 2.5), (1, -0.6), (2, 0.3)]:
            pos = b + idx
            if 0 <= pos < N:
                m_ecg[pos] += amp

    # Fetal ECG at 140 bpm (RR = 107 samples)
    f_peaks = list(range(150, N, 107))
    f_ecg = np.zeros(N)
    for b in f_peaks:
        for idx, amp in [(-1, -0.05), (0, 0.4), (1, -0.1)]:
            pos = b + idx
            if 0 <= pos < N:
                f_ecg[pos] += amp

    # 4-channel spatial mixing matrix
    # Maternal dominates CH0 & CH1; Fetal projects strongly onto CH1, CH2, CH3
    A = np.array([
        [1.00,  0.10],   # CH0: mostly maternal
        [0.80,  0.35],   # CH1: maternal + fetal
        [0.30,  0.60],   # CH2: moderate maternal + strong fetal
        [0.15, -0.50]    # CH3: weak maternal + negative fetal
    ])

    sources = np.vstack([m_ecg, f_ecg])
    mixture = (A @ sources).T  # (N, 4)

    # Convert to Signed 16-bit Q12 (4096 LSB/mV)
    x_4ch = np.clip(np.round(mixture * 4096.0), -32768, 32767).astype(np.int64)

    # Compute covariance & PCA weights
    # Estimate covariance matrix over first 1000 samples
    cov = np.cov(x_4ch[:1000], rowvar=False)
    evals, evecs = np.linalg.eigh(cov)
    # In np.linalg.eigh, eigenvalues are in ascending order.
    # Second largest eigenvalue is evecs[:, -2], which isolates subordinate fetal component.
    w_fetal = evecs[:, -2]
    w_fetal = w_fetal / np.linalg.norm(w_fetal)
    # Ensure positive polarity for fetal projection
    if np.dot(w_fetal, A[:, 1]) < 0:
        w_fetal = -w_fetal

    w_q15 = np.clip(np.round(w_fetal * 32768.0), -32768, 32767).astype(np.int64)

    res = run_bit_accurate_pipeline_final(x_4ch, w_q15)
    return x_4ch, w_q15, m_peaks, f_peaks, res, A, w_fetal

def analyze_and_plot():
    print("=" * 80)
    print("RUNNING FETAL HEART RATE DETECTION AUDIT SIMULATION")
    print("=" * 80)

    # Run Case A
    x_a, w_a, m_peaks_a, f_peaks_a, res_a = simulate_case_a()

    print("\n--- CASE A: FLAWED TEST (Unity Weights on Single Lead, Step 1341) ---")
    print(f"Input Mixture Shape: {x_a.shape}")
    print(f"Weights (Q15): {w_a.tolist()}")
    print(f"True Maternal Peak Count: {len(m_peaks_a)} (Period = 200 samples = 75 bpm)")
    print(f"True Fetal Peak Count:    {len(f_peaks_a)} (Period = 107 samples = 140 bpm)")
    print(f"Detected Peak Count:      {len(res_a.peaks)}")
    print(f"Compensated Peak Indices: {res_a.peaks.tolist()}")
    print(f"Raw Peak Indices:         {res_a.raw_peaks.tolist()}")
    print(f"Detected RR Intervals:    {res_a.rr.tolist()}")

    # Determine which peaks were detected in Case A
    m_matched = 0
    f_matched = 0
    for p in res_a.peaks:
        # Check distance to maternal peaks
        d_m = min(abs(p - mp) for mp in m_peaks_a)
        d_f = min(abs(p - fp) for fp in f_peaks_a)
        if d_m <= 10:
            m_matched += 1
        elif d_f <= 10:
            f_matched += 1

    print(f"Peaks Matching Maternal QRS: {m_matched} / {len(res_a.peaks)}")
    print(f"Peaks Matching Fetal QRS:    {f_matched} / {len(res_a.peaks)}")

    # Check FHR values
    fhr_vals = res_a.fhr_hold[res_a.peaks] / 10.0 if len(res_a.peaks) > 0 else []
    print(f"FHR at Detected Beats (bpm): {fhr_vals.tolist()}")
    steady_fhr_a = np.median(res_a.fhr_hold[600:]) / 10.0
    print(f"Steady-State FHR (t > 600):  {steady_fhr_a:.1f} bpm")

    # Intermediate signal statistics for Case A
    print("\nCase A Intermediate Signal Max Ranges:")
    print(f"  proj max: {np.max(np.abs(res_a.proj))} (Q20: {np.max(np.abs(res_a.proj))/(2**20):.4f} mV)")
    print(f"  hp max:   {np.max(np.abs(res_a.hp))} (Q20: {np.max(np.abs(res_a.hp))/(2**20):.4f} mV)")
    print(f"  lp max:   {np.max(np.abs(res_a.fecg))} (Q20: {np.max(np.abs(res_a.fecg))/(2**20):.4f} mV)")
    print(f"  bp max:   {np.max(np.abs(res_a.det_bp))} (Q12: {np.max(np.abs(res_a.det_bp))/4096.0:.4f} mV)")
    print(f"  mwi max:  {np.max(res_a.x_int)}")

    # Run Case B
    x_b, w_b, m_peaks_b, f_peaks_b, res_b, A_b, w_fetal_b = simulate_case_b()

    print("\n--- CASE B: TRUE MULTICHANNEL MIXTURE WITH PCA CANCELLATION ---")
    print(f"Input Mixture Shape: {x_b.shape}")
    print(f"Calculated PC2 Spatial Weights (Q15): {w_b.tolist()}")
    print(f"True Maternal Peak Count: {len(m_peaks_b)} (Period = 200 samples = 75 bpm)")
    print(f"True Fetal Peak Count:    {len(f_peaks_b)} (Period = 107 samples = 140 bpm)")
    print(f"Detected Peak Count:      {len(res_b.peaks)}")
    print(f"Compensated Peak Indices: {res_b.peaks.tolist()}")
    print(f"Raw Peak Indices:         {res_b.raw_peaks.tolist()}")
    print(f"Detected RR Intervals:    {res_b.rr.tolist()}")

    # Determine which peaks were detected in Case B
    m_matched_b = 0
    f_matched_b = 0
    for p in res_b.peaks:
        d_m = min(abs(p - mp) for mp in m_peaks_b)
        d_f = min(abs(p - fp) for fp in f_peaks_b)
        if d_f <= 10:
            f_matched_b += 1
        elif d_m <= 10:
            m_matched_b += 1

    print(f"Peaks Matching Fetal QRS:    {f_matched_b} / {len(res_b.peaks)}")
    print(f"Peaks Matching Maternal QRS: {m_matched_b} / {len(res_b.peaks)}")

    fhr_vals_b = (res_b.fhr_hold[res_b.peaks] / 10.0).tolist() if len(res_b.peaks) > 0 else []
    print(f"FHR at Detected Beats (bpm): {fhr_vals_b}")
    steady_fhr_b = np.median(res_b.fhr_hold[600:]) / 10.0
    print(f"Steady-State FHR (t > 600):  {steady_fhr_b:.1f} bpm")

    # Mathematical projection of maternal and fetal components in Case B
    maternal_proj_gain = np.dot(w_fetal_b, A_b[:, 0])
    fetal_proj_gain    = np.dot(w_fetal_b, A_b[:, 1])
    print(f"\nCase B PCA Spatial Suppression:")
    print(f"  Maternal mixing vector a_m: {A_b[:, 0]}")
    print(f"  Fetal mixing vector a_f:    {A_b[:, 1]}")
    print(f"  Normalized weights w:       {w_fetal_b}")
    print(f"  Maternal projection w . a_m: {maternal_proj_gain:.6f} (Linear Suppression)")
    print(f"  Fetal projection w . a_f:    {fetal_proj_gain:.6f} (Fetal Retention)")
    suppression_ratio = abs(fetal_proj_gain) / (abs(maternal_proj_gain) + 1e-12)
    print(f"  Fetal-to-Maternal Gain Ratio: {suppression_ratio:.2f} ({20*np.log10(suppression_ratio):.2f} dB)")

    # ──────────────────────────────────────────────────────────────────────────
    # Generate Comprehensive Diagnostic Comparison Plots
    # ──────────────────────────────────────────────────────────────────────────
    plot_path = Path("scratch/fhr_detection_audit_comparison.png")
    fig, axes = plt.subplots(6, 2, figsize=(16, 14), sharex=True)

    t_sec = np.arange(2500) / 250.0

    # 1. Raw Inputs
    axes[0, 0].plot(t_sec, x_a[:, 0], color="tab:blue", lw=1.0, label="CH0 (Maternal=8000 + Fetal=2500)")
    axes[0, 0].plot(t_sec, x_a[:, 1], color="tab:gray", lw=0.5, linestyle="--", label="CH1..3 = 0")
    axes[0, 0].set_title("Case A: Flawed Single-Lead Test (Unity Weights)\nRaw Input x_raw [LSB]", fontsize=10, fontweight="bold")
    axes[0, 0].set_ylabel("LSB (Q12)")
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend(loc="upper right", fontsize=8)

    for ch, col in enumerate(["tab:blue", "tab:orange", "tab:green", "tab:red"]):
        axes[0, 1].plot(t_sec, x_b[:, ch], color=col, lw=0.8, label=f"CH{ch}")
    axes[0, 1].set_title("Case B: True 4-Channel Mixture with Spatial Diversity\nRaw Input x_raw [LSB]", fontsize=10, fontweight="bold")
    axes[0, 1].set_ylabel("LSB (Q12)")
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].legend(loc="upper right", fontsize=8)

    # 2. Beamformer Output (proj)
    axes[1, 0].plot(t_sec, res_a.proj / (2**20), color="tab:purple", lw=1.0)
    axes[1, 0].set_title("Beamformer Output proj (Maternal Completely Dominates, Amp=1.95 mV)", fontsize=9)
    axes[1, 0].set_ylabel("mV (Q20)")
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].plot(t_sec, res_b.proj / (2**20), color="tab:purple", lw=1.0)
    axes[1, 1].set_title("Beamformer Output proj (Maternal Cancelled, Fetal Isolated, Amp=0.35 mV)", fontsize=9)
    axes[1, 1].set_ylabel("mV (Q20)")
    axes[1, 1].grid(True, alpha=0.3)

    # 3. Clean FECG (HP1 + LP40)
    axes[2, 0].plot(t_sec, res_a.fecg / (2**20), color="darkgreen", lw=1.0)
    axes[2, 0].set_title("Clean FECG Waveform (Maternal QRS at 75 bpm Dominant)", fontsize=9)
    axes[2, 0].set_ylabel("mV (Q20)")
    axes[2, 0].grid(True, alpha=0.3)

    axes[2, 1].plot(t_sec, res_b.fecg / (2**20), color="darkgreen", lw=1.0)
    axes[2, 1].set_title("Clean FECG Waveform (Clean Fetal QRS Complexes at 140 bpm)", fontsize=9)
    axes[2, 1].set_ylabel("mV (Q20)")
    axes[2, 1].grid(True, alpha=0.3)

    # 4. Bandpass (det_bp)
    axes[3, 0].plot(t_sec, res_a.det_bp / 4096.0, color="tab:brown", lw=1.0)
    axes[3, 0].set_title("Bandpass Filter Output (12-35 Hz Config C)", fontsize=9)
    axes[3, 0].set_ylabel("mV (Q12)")
    axes[3, 0].grid(True, alpha=0.3)

    axes[3, 1].plot(t_sec, res_b.det_bp / 4096.0, color="tab:brown", lw=1.0)
    axes[3, 1].set_title("Bandpass Filter Output (12-35 Hz Config C)", fontsize=9)
    axes[3, 1].set_ylabel("mV (Q12)")
    axes[3, 1].grid(True, alpha=0.3)

    # 5. MWI & Detected Peaks
    axes[4, 0].plot(t_sec, res_a.x_int, color="tab:red", lw=1.0, label="MWI Energy")
    if len(res_a.peaks) > 0:
        axes[4, 0].scatter(res_a.peaks / 250.0, res_a.x_int[res_a.raw_peaks], color="black", s=30, zorder=5, label="Detected Beats (Maternal)")
    for mp in m_peaks_a:
        if mp / 250.0 >= 2.05: # Post warmup
            axes[4, 0].axvline(mp / 250.0, color="blue", alpha=0.2, linestyle=":")
    axes[4, 0].set_title("Squarer & MWI Energy with Detected Beat Peaks (Warmup = 2.05s)", fontsize=9)
    axes[4, 0].set_ylabel("Energy (36-bit)")
    axes[4, 0].grid(True, alpha=0.3)
    axes[4, 0].legend(loc="upper right", fontsize=8)

    axes[4, 1].plot(t_sec, res_b.x_int, color="tab:red", lw=1.0, label="MWI Energy")
    if len(res_b.peaks) > 0:
        axes[4, 1].scatter(res_b.peaks / 250.0, res_b.x_int[res_b.raw_peaks], color="darkgreen", s=30, zorder=5, label="Detected Beats (Fetal)")
    for fp in f_peaks_b:
        if fp / 250.0 >= 2.05:
            axes[4, 1].axvline(fp / 250.0, color="green", alpha=0.2, linestyle=":")
    axes[4, 1].set_title("Squarer & MWI Energy with Detected Beat Peaks (Warmup = 2.05s)", fontsize=9)
    axes[4, 1].set_ylabel("Energy (36-bit)")
    axes[4, 1].grid(True, alpha=0.3)
    axes[4, 1].legend(loc="upper right", fontsize=8)

    # 6. FHR Output Stream
    axes[5, 0].plot(t_sec, res_a.fhr_hold / 10.0, color="crimson", lw=1.5, label="Output FHR")
    axes[5, 0].axhline(75.0, color="blue", linestyle="--", label="Maternal Rate = 75 bpm")
    axes[5, 0].axhline(140.0, color="green", linestyle="--", label="Target Fetal Rate = 140 bpm")
    axes[5, 0].set_title("Final Output FHR: Locks to MATERNAL Rate (75.0 bpm)", fontsize=9, fontweight="bold", color="crimson")
    axes[5, 0].set_xlabel("Time (seconds)")
    axes[5, 0].set_ylabel("Heart Rate (bpm)")
    axes[5, 0].set_ylim(40, 160)
    axes[5, 0].grid(True, alpha=0.3)
    axes[5, 0].legend(loc="lower right", fontsize=8)

    axes[5, 1].plot(t_sec, res_b.fhr_hold / 10.0, color="darkgreen", lw=1.5, label="Output FHR")
    axes[5, 1].axhline(75.0, color="blue", linestyle="--", label="Maternal Rate = 75 bpm")
    axes[5, 1].axhline(140.2, color="green", linestyle="--", label="Target Fetal Rate = 140.2 bpm")
    axes[5, 1].set_title("Final Output FHR: Correctly Identifies FETAL Rate (140.2 bpm)", fontsize=9, fontweight="bold", color="darkgreen")
    axes[5, 1].set_xlabel("Time (seconds)")
    axes[5, 1].set_ylabel("Heart Rate (bpm)")
    axes[5, 1].set_ylim(40, 160)
    axes[5, 1].grid(True, alpha=0.3)
    axes[5, 1].legend(loc="lower right", fontsize=8)

    plt.tight_layout()
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"\nSaved comparison plot to: {plot_path.resolve()}")
    print("=" * 80)

if __name__ == "__main__":
    analyze_and_plot()
