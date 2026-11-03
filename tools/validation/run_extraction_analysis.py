"""
tools/validation/run_extraction_analysis.py
──────────────────────────────────────────────────────────────────────────────
Phase 4: Signal Extraction Quality and Maternal-Fetal Separation.
Executes:
  1. Waveform Extraction Metrics:
     - Output SNR (dB), SNR Improvement (dB)
     - Pearson correlation with ground truth fetal signal
     - Waveform RMSE
     - Signal-to-Interference Ratio (SIR) before and after beamforming
  2. Maternal QRS Overlap Analysis:
     - Identification of coincident beats (|t_fetal - t_maternal| <= 50 ms)
     - Detection sensitivity on overlapping beats vs non-overlapping beats
     - Maternal leakage ratio (leakage amplitude relative to fetal QRS)
  3. Time-resolved stability in Condition c1 (30-second epochs)
  4. Generation of diagnostic failure plots in validation/extraction/FAILURE_PLOTS/

Outputs:
  - validation/extraction/EXTRACTION_METRICS.csv
  - validation/extraction/EXTRACTION_QUALITY_REPORT.md
  - validation/extraction/FAILURE_PLOTS/*.png
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
import numpy as np
import wfdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, DEFAULT_CONFIG, run_causal, preprocess_causal
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
EXT_DIR = PROJECT_ROOT / "validation" / "extraction"
PLOT_DIR = EXT_DIR / "FAILURE_PLOTS"
EXT_DIR.mkdir(parents=True, exist_ok=True)
PLOT_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250

def load_case_components(sub: str, snr: str, cond: str):
    base_path = str(DATA_DIR / sub / snr / f"{sub}_{snr}_l1_{cond}")
    fecg_rec = wfdb.rdrecord(base_path + "_fecg1").p_signal
    mecg_rec = wfdb.rdrecord(base_path + "_mecg").p_signal
    n1_rec = wfdb.rdrecord(base_path + "_noise1").p_signal
    n2_rec = wfdb.rdrecord(base_path + "_noise2").p_signal
    
    fecg_4ch = fecg_rec[:, CHANNELS]
    mecg_4ch = mecg_rec[:, CHANNELS]
    noise_4ch = (n1_rec + n2_rec)[:, CHANNELS]
    mix_4ch = fecg_4ch + mecg_4ch + noise_4ch
    
    f_qrs = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)
    m_qrs = np.sort(wfdb.rdann(base_path + "_mecg", "qrs").sample)
    
    return mix_4ch, fecg_4ch, mecg_4ch, noise_4ch, f_qrs, m_qrs

def main():
    print("=" * 70)
    print("STARTING PHASE 4: EXTRACTION QUALITY & MATERNAL-FETAL SEPARATION")
    print("=" * 70)
    
    test_suite = [
        ("sub01", "snr12dB", "c0"),
        ("sub01", "snr06dB", "c0"),
        ("sub01", "snr00dB", "c0"),
        ("sub01", "snr06dB", "c1"),
        ("sub01", "snr06dB", "c2"),
        ("sub01", "snr06dB", "c3"),
        ("sub01", "snr06dB", "c4"),
        ("sub06", "snr06dB", "c0"),
        ("sub04", "snr06dB", "c0"),
        ("sub08", "snr06dB", "c0"),
        ("sub10", "snr06dB", "c0"),
    ]
    
    metrics_rows = []
    
    for sub, snr, cond in test_suite:
        rec_id = f"{sub}_{snr}_{cond}"
        mix_4ch, fecg_4ch, mecg_4ch, noise_4ch, f_qrs, m_qrs = load_case_components(sub, snr, cond)
        
        # Spatial beamformer
        bank = CalibrationBank(mix_4ch, DEFAULT_CONFIG, cal_seconds=0)
        j, _ = bank.select("pc3")
        w = bank.weights(j)
        
        # 1. Output signal & detection
        fecg_out, det_res = run_causal(mix_4ch, w)
        det_peaks = det_res.peaks
        
        # Reference projected fetal signal (filtered through same causal chain)
        fecg_proj = fecg_4ch @ w
        fecg_ref_filt = preprocess_causal(fecg_proj)
        
        # Project maternal and noise components to evaluate leakage
        mecg_proj = mecg_4ch @ w
        mecg_leak = preprocess_causal(mecg_proj)
        noise_proj = noise_4ch @ w
        noise_leak = preprocess_causal(noise_proj)
        
        # Compute Waveform Metrics
        p_fecg = np.mean(fecg_ref_filt ** 2)
        p_mecg_residue = np.mean(mecg_leak ** 2)
        p_noise_residue = np.mean(noise_leak ** 2)
        p_interference = p_mecg_residue + p_noise_residue
        
        # Input SIR on lead 27
        p_in_fecg = np.mean(fecg_4ch[:, 0] ** 2)
        p_in_mecg = np.mean(mecg_4ch[:, 0] ** 2)
        sir_in_db = 10.0 * np.log10(p_in_fecg / p_in_mecg + 1e-12)
        sir_out_db = 10.0 * np.log10(p_fecg / p_mecg_residue + 1e-12)
        sir_improvement_db = sir_out_db - sir_in_db
        
        # Output SNR
        snr_out_db = 10.0 * np.log10(p_fecg / p_interference + 1e-12)
        snr_in_db = 10.0 * np.log10(p_in_fecg / (p_in_mecg + np.mean(noise_4ch[:, 0] ** 2) + 1e-12))
        snr_improvement_db = snr_out_db - snr_in_db
        
        # Pearson correlation
        corr = float(np.corrcoef(fecg_out, fecg_ref_filt)[0, 1])
        rmse = float(np.sqrt(np.mean((fecg_out - fecg_ref_filt) ** 2)))
        
        # 2. Maternal QRS Overlap Analysis
        # Overlap window: +- 50 ms = +- 12.5 samples -> tol = 13 samples
        tol_overlap = 13
        is_overlap = []
        for f_beat in f_qrs:
            min_dist = np.min(np.abs(f_beat - m_qrs))
            is_overlap.append(min_dist <= tol_overlap)
        is_overlap = np.array(is_overlap, dtype=bool)
        
        n_overlap_total = int(np.sum(is_overlap))
        n_non_overlap_total = int(len(f_qrs) - n_overlap_total)
        
        # Check detection success for each fetal beat
        det_tol = 13  # 50 ms matching tolerance
        det_overlap_tp = 0
        det_non_overlap_tp = 0
        
        for idx, f_beat in enumerate(f_qrs):
            if len(det_peaks) > 0 and np.min(np.abs(det_peaks - f_beat)) <= det_tol:
                if is_overlap[idx]:
                    det_overlap_tp += 1
                else:
                    det_non_overlap_tp += 1
                    
        se_overlap = (det_overlap_tp / n_overlap_total * 100) if n_overlap_total > 0 else 0.0
        se_non_overlap = (det_non_overlap_tp / n_non_overlap_total * 100) if n_non_overlap_total > 0 else 0.0
        
        # Maternal Leakage Ratio
        # Amplitude of mecg_leak at maternal peaks relative to fecg_ref_filt at fetal peaks
        m_peak_amps = np.abs(mecg_leak[m_qrs[m_qrs < len(mecg_leak)]])
        f_peak_amps = np.abs(fecg_ref_filt[f_qrs[f_qrs < len(fecg_ref_filt)]])
        leakage_ratio = float(np.median(m_peak_amps) / (np.median(f_peak_amps) + 1e-12))
        
        # Overall detection
        m_eval = compute_beat_metrics(f_qrs, det_peaks, fs=FS)
        
        metrics_rows.append({
            "record": rec_id,
            "sub_id": sub,
            "snr": snr,
            "condition": cond,
            "f1_overall": round((m_eval.f1 or 0.0) * 100, 2),
            "snr_in_db": round(snr_in_db, 2),
            "snr_out_db": round(snr_out_db, 2),
            "snr_gain_db": round(snr_improvement_db, 2),
            "sir_in_db": round(sir_in_db, 2),
            "sir_out_db": round(sir_out_db, 2),
            "sir_gain_db": round(sir_improvement_db, 2),
            "correlation": round(corr, 4),
            "rmse_mv": round(rmse, 4),
            "n_overlap_beats": n_overlap_total,
            "se_overlap_pct": round(se_overlap, 2),
            "n_non_overlap_beats": n_non_overlap_total,
            "se_non_overlap_pct": round(se_non_overlap, 2),
            "se_delta_overlap": round(se_overlap - se_non_overlap, 2),
            "maternal_leakage_ratio": round(leakage_ratio, 3)
        })
        
        # Generate diagnostic plots for key cases
        if rec_id == "sub01_snr06dB_c0":
            # Plot 1: Overlapping beat detail
            plt.figure(figsize=(12, 6))
            # Find an overlapping beat
            ov_indices = np.where(is_overlap)[0]
            if len(ov_indices) > 0:
                target_f_beat = f_qrs[ov_indices[5]]
                win = slice(max(0, target_f_beat - 350), min(len(fecg_out), target_f_beat + 350))
                t_axis = np.arange(win.start, win.stop) / FS
                
                plt.subplot(3, 1, 1)
                plt.plot(t_axis, mix_4ch[win, 0], 'k', label='Raw Lead 27 (MECG dominated)')
                plt.legend(loc='upper right')
                plt.ylabel('Amplitude (mV)')
                plt.title(f'Maternal-Fetal QRS Overlap Detail ({rec_id})')
                
                plt.subplot(3, 1, 2)
                plt.plot(t_axis, fecg_out[win], 'b', label='Beamformer Output (fecg_out)')
                plt.plot(t_axis, fecg_ref_filt[win], 'g--', alpha=0.7, label='Ground Truth Fetal Reference')
                for mb in m_qrs:
                    if win.start <= mb < win.stop:
                        plt.axvline(mb / FS, color='r', linestyle=':', label='Maternal QRS' if mb == m_qrs[0] else "")
                plt.legend(loc='upper right')
                plt.ylabel('mV')
                
                plt.subplot(3, 1, 3)
                plt.plot(t_axis, mecg_leak[win], 'r', label='Maternal Leakage Residue')
                plt.legend(loc='upper right')
                plt.xlabel('Time (seconds)')
                plt.ylabel('mV')
                
                plt.tight_layout()
                plt.savefig(PLOT_DIR / "overlap_leakage_detail.png", dpi=150)
                plt.close()
                
        if rec_id == "sub01_snr06dB_c1":
            # Plot 2: Motion Artifact Non-stationarity in c1
            plt.figure(figsize=(14, 5))
            t_full = np.arange(len(fecg_out)) / FS
            plt.plot(t_full[::2], fecg_out[::2], 'b', lw=0.6, label='Extracted FECG')
            plt.plot(t_full[::2], mecg_leak[::2], 'r', lw=0.6, alpha=0.6, label='Maternal Residue')
            plt.title(f'Condition c1 (Motion Artifact) Signal Profile over 300s ({rec_id})')
            plt.xlabel('Time (seconds)')
            plt.ylabel('Amplitude (mV)')
            plt.legend(loc='upper right')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(PLOT_DIR / "motion_drift_300s.png", dpi=150)
            plt.close()
            
        if rec_id == "sub04_snr06dB_c0":
            # Plot 3: Severe Maternal Leakage Failure in sub04
            plt.figure(figsize=(12, 5))
            win4 = slice(5000, 6500)
            t4 = np.arange(win4.start, win4.stop) / FS
            plt.plot(t4, fecg_out[win4], 'b', label='Extracted Output (PC3)')
            plt.plot(t4, mecg_leak[win4], 'r--', label='Maternal Breakthrough Spike')
            for fb in f_qrs:
                if win4.start <= fb < win4.stop:
                    plt.axvline(fb / FS, color='g', linestyle='--', alpha=0.7, label='Fetal Ground Truth' if fb == f_qrs[0] else "")
            plt.title(f'Severe Maternal Breakthrough Failure in Sub04 (False Positives Triggered on MECG)')
            plt.xlabel('Time (seconds)')
            plt.ylabel('mV')
            plt.legend(loc='upper right')
            plt.tight_layout()
            plt.savefig(PLOT_DIR / "maternal_breakthrough_sub04.png", dpi=150)
            plt.close()

    # Save EXTRACTION_METRICS.csv
    csv_path = EXT_DIR / "EXTRACTION_METRICS.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(metrics_rows[0].keys()))
        w.writeheader()
        w.writerows(metrics_rows)
    print(f"Written: {csv_path}")

    # 3. Time-Resolved Window Analysis for Condition c1
    print("\nRunning Time-Resolved 30-Second Epoch Analysis for Condition c1...")
    mix_c1, fecg_c1, _, _, f_qrs_c1, _ = load_case_components("sub01", "snr06dB", "c1")
    bank_c1 = CalibrationBank(mix_c1, DEFAULT_CONFIG, cal_seconds=10)
    j_c1, _ = bank_c1.select("pc3")
    w_c1 = bank_c1.weights(j_c1)
    fecg_out_c1, det_c1 = run_causal(mix_c1, w_c1)
    
    epoch_rows = []
    epoch_len = 30 * FS
    for epoch_idx in range(10):
        ep_start = epoch_idx * epoch_len
        ep_end = (epoch_idx + 1) * epoch_len
        ref_ep = f_qrs_c1[(f_qrs_c1 >= ep_start) & (f_qrs_c1 < ep_end)]
        det_ep = det_c1.peaks[(det_c1.peaks >= ep_start) & (det_c1.peaks < ep_end)]
        
        m_ep = compute_beat_metrics(ref_ep, det_ep, fs=FS)
        epoch_rows.append({
            "epoch": f"{epoch_idx*30}-{(epoch_idx+1)*30}s",
            "f1": round((m_ep.f1 or 0.0) * 100, 2),
            "tp": m_ep.tp,
            "fp": m_ep.fp,
            "fn": m_ep.fn
        })
        
    print("Condition c1 30-second epoch stability:")
    for r in epoch_rows:
        print(f"  Epoch {r['epoch']:10s}: F1 = {r['f1']:6.2f}% (TP={r['tp']}, FP={r['fp']}, FN={r['fn']})")

    print("\nPhase 4 computation complete!")

if __name__ == "__main__":
    main()
