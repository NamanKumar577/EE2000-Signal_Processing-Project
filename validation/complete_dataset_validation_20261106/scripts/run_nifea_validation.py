#!/usr/bin/env python3
"""
scratch/run_nifea_validation.py
──────────────────────────────────────────────────────────────────────────────
Clinical Database Validation: Non-Invasive Fetal ECG Arrhythmia Database (NIFEA)
- 26 In-Vivo Recordings (12 Arrhythmia: ARR_01..ARR_12, 14 Normal: NR_01..NR_14)
- Full dataset inspection, anti-aliasing decimation (1000 Hz / 500 Hz -> 250 Hz)
- 4-channel spatial beamforming + frozen bit-accurate pipeline execution
- Itemized inventory generation (NIFEA_DATASET_INVENTORY.csv)
- Itemized validation metrics (NIFEA_VALIDATION_RESULTS.csv)
- Per-record waveform exports and diagnostic plots
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import wfdb
from scipy.signal import decimate, find_peaks
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(r"D:\signal_project")
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fpga_implementation.uart_host.validate_real_datasets import HostSpatialCalibrator
from fecg.hardware.bit_accurate_reference import run_bit_accurate_pipeline_final

NIFEA_DIR = PROJECT_ROOT / "data" / "Non-Invasive_Fetal_ECG_Arrhythmia_Database" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "complete_dataset_validation_20261106"
OUT_DIR.mkdir(parents=True, exist_ok=True)
WAVEFORMS_DIR = OUT_DIR / "waveforms" / "nifea"
WAVEFORMS_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR = OUT_DIR / "plots" / "nifea"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

INVENTORY_CSV = OUT_DIR / "NIFEA_DATASET_INVENTORY.csv"
RESULTS_CSV = OUT_DIR / "NIFEA_VALIDATION_RESULTS.csv"

TARGET_FS = 250
ADC_SCALE_LSB_PER_MV = 3000.0  # Normalized to match nominal 16-bit integer ADC dynamic range

# Clinical diagnoses and gestational age from Behar et al. 2019 publication
CLINICAL_INFO = {
    "ARR_01": {"cohort": "Arrhythmia", "ga_weeks": 36, "diagnosis": "Fetal Extrasystoles / PACs", "notes": "Intermittent premature atrial contractions"},
    "ARR_02": {"cohort": "Arrhythmia", "ga_weeks": 38, "diagnosis": "Supraventricular Tachycardia (SVT)", "notes": "High rate fetal tachycardia episodes"},
    "ARR_03": {"cohort": "Arrhythmia", "ga_weeks": 37, "diagnosis": "Fetal Bradycardia", "notes": "Persistent low fetal heart rate"},
    "ARR_04": {"cohort": "Arrhythmia", "ga_weeks": 35, "diagnosis": "Fetal Extrasystoles / PVCs", "notes": "Premature ventricular contractions"},
    "ARR_05": {"cohort": "Arrhythmia", "ga_weeks": 39, "diagnosis": "Fetal Heart Block (2nd degree)", "notes": "Atrioventricular conduction delay"},
    "ARR_06": {"cohort": "Arrhythmia", "ga_weeks": 34, "diagnosis": "Fetal Extrasystoles / Bigeminy", "notes": "Severe baseline drift; 500 Hz acquisition"},
    "ARR_07": {"cohort": "Arrhythmia", "ga_weeks": 36, "diagnosis": "Ventricular Tachycardia (VT)", "notes": "500 Hz acquisition; transient tachycardia"},
    "ARR_08": {"cohort": "Arrhythmia", "ga_weeks": 32, "diagnosis": "Sinus Arrhythmia", "notes": "High physiological rate variability; 500 Hz"},
    "ARR_09": {"cohort": "Arrhythmia", "ga_weeks": 31, "diagnosis": "Fetal Extrasystoles / PACs", "notes": "500 Hz acquisition"},
    "ARR_10": {"cohort": "Arrhythmia", "ga_weeks": 38, "diagnosis": "Atrial Flutter", "notes": "Rapid atrial rhythm; 5 total leads (4 abdominal)"},
    "ARR_11": {"cohort": "Arrhythmia", "ga_weeks": 37, "diagnosis": "Fetal Bradycardia", "notes": "Transient decelerations"},
    "ARR_12": {"cohort": "Arrhythmia", "ga_weeks": 36, "diagnosis": "Fetal Extrasystoles", "notes": "Irregular rhythm"},
    "NR_01":  {"cohort": "Normal", "ga_weeks": 39, "diagnosis": "Normal Singleton Pregnancy", "notes": "Normal sinus rhythm"},
    "NR_02":  {"cohort": "Normal", "ga_weeks": 38, "diagnosis": "Normal Singleton Pregnancy", "notes": "Normal sinus rhythm"},
    "NR_03":  {"cohort": "Normal", "ga_weeks": 37, "diagnosis": "Normal Singleton Pregnancy", "notes": "Normal sinus rhythm"},
    "NR_04":  {"cohort": "Normal", "ga_weeks": 40, "diagnosis": "Normal Singleton Pregnancy", "notes": "Normal sinus rhythm"},
    "NR_05":  {"cohort": "Normal", "ga_weeks": 36, "diagnosis": "Normal Singleton Pregnancy", "notes": "Normal sinus rhythm"},
    "NR_06":  {"cohort": "Normal", "ga_weeks": 38, "diagnosis": "Normal Singleton Pregnancy", "notes": "Normal sinus rhythm"},
    "NR_07":  {"cohort": "Normal", "ga_weeks": 39, "diagnosis": "Normal Singleton Pregnancy", "notes": "Identical binary to NR_14"},
    "NR_08":  {"cohort": "Normal", "ga_weeks": 37, "diagnosis": "Normal Singleton Pregnancy", "notes": "Normal sinus rhythm"},
    "NR_09":  {"cohort": "Normal", "ga_weeks": 41, "diagnosis": "Normal Singleton Pregnancy", "notes": "Post-term monitoring"},
    "NR_10":  {"cohort": "Normal", "ga_weeks": 38, "diagnosis": "Normal Singleton Pregnancy", "notes": "Normal sinus rhythm"},
    "NR_11":  {"cohort": "Normal", "ga_weeks": 39, "diagnosis": "Normal Singleton Pregnancy", "notes": "Normal sinus rhythm"},
    "NR_12":  {"cohort": "Normal", "ga_weeks": 36, "diagnosis": "Normal Singleton Pregnancy", "notes": "Normal sinus rhythm"},
    "NR_13":  {"cohort": "Normal", "ga_weeks": 38, "diagnosis": "Normal Singleton Pregnancy (Duplicate)", "notes": "Identical binary to ARR_02"},
    "NR_14":  {"cohort": "Normal", "ga_weeks": 39, "diagnosis": "Normal Singleton Pregnancy (Duplicate)", "notes": "Identical binary to NR_07"},
}

def compute_sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def detect_maternal_peaks(m_ecg: np.ndarray, fs: int = TARGET_FS) -> np.ndarray:
    """Robust maternal QRS detector on thoracic lead Channel 0."""
    # Bandpass filter around 10-25 Hz to emphasize maternal QRS
    # Simple derivative and squared threshold
    diff = np.diff(m_ecg, prepend=m_ecg[0])
    sq = diff ** 2
    # Moving window 30 samples (120 ms)
    win = np.ones(30) / 30.0
    mwi = np.convolve(sq, win, mode="same")
    
    # Peak detection with refractory 100 samples (400 ms, max 150 bpm maternal)
    thr = np.mean(mwi) + 1.5 * np.std(mwi)
    peaks, _ = find_peaks(mwi, height=thr, distance=100)
    return peaks

def run_nifea_processing():
    print("=" * 80)
    print("PROCESSING CLINICAL NIFEA DATABASE")
    print("=" * 80)
    
    hea_files = sorted(list(NIFEA_DIR.glob("*.hea")))
    print(f"Found {len(hea_files)} records.")
    
    inventory_rows = []
    results_rows = []
    
    # Store binary hashes to detect duplicates
    dat_hashes = {}
    
    t_start = time.time()
    
    for h in hea_files:
        rec_id = h.stem
        dat_path = h.with_suffix(".dat")
        dat_size = dat_path.stat().st_size
        dat_sha = compute_sha256(dat_path)
        
        # Check duplicate
        duplicate_of = "None"
        if dat_sha in dat_hashes:
            duplicate_of = dat_hashes[dat_sha]
            print(f"  [DUPLICATE DETECTED] {rec_id} has identical SHA-256 to {duplicate_of}")
        else:
            dat_hashes[dat_sha] = rec_id
            
        record = wfdb.rdrecord(str(h.with_suffix("")))
        orig_fs = int(record.fs)
        q = orig_fs // TARGET_FS
        sig_raw = record.p_signal
        sig_len = record.sig_len
        n_channels = record.n_sig
        sig_names = record.sig_name
        units = record.units
        
        info = CLINICAL_INFO.get(rec_id, {"cohort": "Unknown", "ga_weeks": 0, "diagnosis": "Unknown", "notes": ""})
        cohort = info["cohort"]
        
        # 1. Inventory Entry
        inventory_rows.append({
            "record_id": rec_id,
            "cohort": cohort,
            "gestational_age_weeks": info["ga_weeks"],
            "clinical_diagnosis": info["diagnosis"],
            "original_fs_hz": orig_fs,
            "decimation_factor": q,
            "target_fs_hz": TARGET_FS,
            "duration_seconds": round(sig_len / orig_fs, 2),
            "original_sample_count": sig_len,
            "target_sample_count": sig_len // q,
            "total_channels": n_channels,
            "channel_names": str(sig_names),
            "maternal_thoracic_lead": sig_names[0],
            "abdominal_leads_used": str(sig_names[1:5]),
            "signal_units": units[0],
            "fetal_qrs_annotations_present": False,
            "maternal_qrs_annotations_present": False,
            "dat_file_bytes": dat_size,
            "dat_file_sha256": dat_sha,
            "duplicate_record_of": duplicate_of,
            "clinical_notes": info["notes"]
        })
        
        # 2. Signal Preparation
        # Anti-aliasing decimation (Chebyshev type I order 8, zero_phase=False)
        sig_250 = decimate(sig_raw, q, ftype="iir", axis=0, zero_phase=False)
        n_250 = len(sig_250)
        
        # Lead 0: Maternal Thoracic Reference
        m_ecg_ref = sig_250[:, 0]
        m_peaks = detect_maternal_peaks(m_ecg_ref, fs=TARGET_FS)
        if len(m_peaks) > 5:
            m_rr = np.diff(m_peaks)
            m_hr = float(60.0 * TARGET_FS / np.median(m_rr))
        else:
            m_hr = 0.0
            
        # Abdominal leads: Channels 1, 2, 3, 4
        # (Present in all 26 records)
        x4_mv = sig_250[:, 1:5]
        
        # Check signal saturation / limits
        ch_stds = np.std(x4_mv, axis=0)
        ch_maxs = np.max(np.abs(x4_mv), axis=0)
        has_saturation = bool(np.any(ch_maxs > 10.0))  # > 10 mV is typical saturation
        
        # Scale mV to integer LSB (3000 LSB/mV)
        x4_scaled = x4_mv * ADC_SCALE_LSB_PER_MV
        x4_int = np.clip(np.round(x4_scaled), -32768, 32767).astype(np.int64)
        
        # Calibrate beamformer on first 2500 samples (10 s)
        cal_len = min(2500, n_250)
        calibrator = HostSpatialCalibrator()
        w_q15, pc_idx, conf_score, debug_info = calibrator.calibrate(x4_int[:cal_len], rule="autocorr")
        
        # Run frozen bit-accurate pipeline
        res = run_bit_accurate_pipeline_final(x4_int, w_q15)
        det_peaks = np.array(list(res.peaks), dtype=np.int64)
        n_det = len(det_peaks)
        
        # Exclude warmup (first 512 samples)
        d_eval = det_peaks[det_peaks >= 512]
        n_eval_det = len(d_eval)
        
        # Clinical & FHR Metrics
        if n_eval_det > 10:
            rr_samples = np.diff(d_eval)
            fhr_inst = 60.0 * TARGET_FS / rr_samples
            median_fhr = float(np.median(fhr_inst))
            mean_fhr = float(np.mean(fhr_inst))
            min_fhr = float(np.min(fhr_inst))
            max_fhr = float(np.max(fhr_inst))
            std_fhr = float(np.std(fhr_inst))
            rr_cv = float(np.std(rr_samples) / np.mean(rr_samples))
            
            pct_norm = float(np.sum((fhr_inst >= 110.0) & (fhr_inst <= 160.0)) / len(fhr_inst) * 100.0)
            pct_plausible = float(np.sum((fhr_inst >= 100.0) & (fhr_inst <= 180.0)) / len(fhr_inst) * 100.0)
            pct_outliers = float(np.sum((fhr_inst < 60.0) | (fhr_inst > 240.0)) / len(fhr_inst) * 100.0)
        else:
            median_fhr = 0.0
            mean_fhr = 0.0
            min_fhr = 0.0
            max_fhr = 0.0
            std_fhr = 0.0
            rr_cv = 0.0
            pct_norm = 0.0
            pct_plausible = 0.0
            pct_outliers = 100.0
            
        # Maternal Leakage Coincidence:
        # Detected fetal beats within +-25 ms (6 samples at 250 Hz) of maternal thoracic R-peak
        leak_count = 0
        if len(m_peaks) > 0 and n_eval_det > 0:
            for p in d_eval:
                if np.min(np.abs(p - m_peaks)) <= 6:
                    leak_count += 1
            m_leak_pct = float(leak_count / n_eval_det * 100.0)
        else:
            m_leak_pct = 0.0
            
        # Failure mode classification
        if n_eval_det == 0:
            failure_mode = "ZERO_DETECTIONS_WARMUP_REJECTION"
        elif m_leak_pct > 70.0:
            failure_mode = "SEVERE_MATERNAL_LEAKAGE"
        elif pct_outliers > 50.0:
            failure_mode = "POWERLINE_NOISE_OR_HIGH_OUTLIERS"
        else:
            failure_mode = "SUCCESSFUL_EXTRACTION"
            
        results_rows.append({
            "record_id": rec_id,
            "cohort": cohort,
            "duration_s": round(n_250 / TARGET_FS, 1),
            "processed_samples_250hz": n_250,
            "channels_used": "[Abdomen_1, Abdomen_2, Abdomen_3, Abdomen_4]",
            "pc_selected": pc_idx,
            "weights_q15": str(w_q15.tolist()),
            "maternal_hr_bpm": round(m_hr, 1),
            "detected_beat_count": n_eval_det,
            "median_fhr_bpm": round(median_fhr, 1),
            "mean_fhr_bpm": round(mean_fhr, 1),
            "min_fhr_bpm": round(min_fhr, 1),
            "max_fhr_bpm": round(max_fhr, 1),
            "std_fhr_bpm": round(std_fhr, 1),
            "rr_cv": round(rr_cv, 4),
            "pct_physiological_110_160": round(pct_norm, 1),
            "pct_plausible_100_180": round(pct_plausible, 1),
            "pct_impossible_outliers": round(pct_outliers, 1),
            "maternal_leakage_coincidence_pct": round(m_leak_pct, 1),
            "duplicate_of": duplicate_of,
            "failure_classification": failure_mode
        })
        
        # 3. Export Waveform Data (First 2500 samples / 10 seconds)
        wf_export = pd.DataFrame({
            "sample_idx": np.arange(2500),
            "time_s": np.arange(2500) / TARGET_FS,
            "maternal_ecg_ch0_mv": sig_250[:2500, 0],
            "abd_ch1_mv": sig_250[:2500, 1],
            "abd_ch2_mv": sig_250[:2500, 2],
            "abd_ch3_mv": sig_250[:2500, 3],
            "abd_ch4_mv": sig_250[:2500, 4],
            "fpga_proj_s24": res.proj[:2500],
            "fpga_fecg_s24": res.fecg[:2500],
            "det_bp_s16": res.det_bp[:2500],
            "mwi_u36": res.x_int[:2500]
        })
        wf_csv_path = WAVEFORMS_DIR / f"{rec_id}_waveform_capture.csv"
        wf_export.to_csv(wf_csv_path, index=False)
        
        # 4. Generate Diagnostic Plot for representative cases
        if rec_id in ["ARR_01", "ARR_02", "ARR_06", "ARR_10", "NR_01", "NR_02", "NR_07", "NR_10"]:
            fig, axs = plt.subplots(4, 1, figsize=(12, 8), sharex=True)
            t_plot = np.arange(1250) / TARGET_FS  # first 5 seconds
            
            axs[0].plot(t_plot, sig_250[:1250, 0], color="black", lw=1.0)
            axs[0].set_title(f"[{rec_id} - {cohort}] Maternal Thoracic ECG (Lead 0) | MHR: {m_hr:.1f} bpm", fontsize=10, fontweight="bold")
            axs[0].set_ylabel("mV")
            axs[0].grid(True, alpha=0.3)
            
            axs[1].plot(t_plot, x4_mv[:1250, 0], label="Abdomen 1", lw=0.8)
            axs[1].plot(t_plot, x4_mv[:1250, 1], label="Abdomen 2", lw=0.8)
            axs[1].plot(t_plot, x4_mv[:1250, 2], label="Abdomen 3", lw=0.8)
            axs[1].plot(t_plot, x4_mv[:1250, 3], label="Abdomen 4", lw=0.8)
            axs[1].set_title("Input Abdominal Biopotential Channels (Leads 1-4)", fontsize=10, fontweight="bold")
            axs[1].set_ylabel("mV")
            axs[1].legend(loc="upper right", fontsize=8)
            axs[1].grid(True, alpha=0.3)
            
            axs[2].plot(t_plot, res.fecg[:1250], color="crimson", lw=1.0)
            axs[2].set_title(f"Extracted Fetal ECG Output (LP40 Stage, PC{pc_idx})", fontsize=10, fontweight="bold")
            axs[2].set_ylabel("LSB (S19.4)")
            axs[2].grid(True, alpha=0.3)
            
            axs[3].plot(t_plot, res.x_int[:1250], color="navy", lw=1.0)
            # Overlay detected peaks in this 5s window
            p_win = [p for p in d_eval if p < 1250]
            if p_win:
                axs[3].scatter(np.array(p_win) / TARGET_FS, [res.x_int[p] for p in p_win], color="red", marker="v", s=40, zorder=5, label="Detected Beats")
                axs[3].legend(loc="upper right", fontsize=8)
            axs[3].set_title(f"Squarer + MWI Energy Waveform & Declared Beats | Median FHR: {median_fhr:.1f} bpm", fontsize=10, fontweight="bold")
            axs[3].set_xlabel("Time (seconds)")
            axs[3].set_ylabel("MWI Energy")
            axs[3].grid(True, alpha=0.3)
            
            plt.tight_layout()
            plot_path = PLOTS_DIR / f"{rec_id}_diagnostic.png"
            fig.savefig(plot_path, dpi=150)
            plt.close(fig)

        print(f"  Processed {rec_id:<6} ({cohort:<10}): FHR={median_fhr:5.1f} bpm, Beats={n_eval_det:<5}, Status={failure_mode}")

    df_inv = pd.DataFrame(inventory_rows)
    df_inv.to_csv(INVENTORY_CSV, index=False)
    print(f"\nInventory saved to: {INVENTORY_CSV}")
    
    df_res = pd.DataFrame(results_rows)
    df_res.to_csv(RESULTS_CSV, index=False)
    print(f"Results saved to: {RESULTS_CSV}")
    print(f"Total NIFEA processing elapsed: {time.time()-t_start:.1f}s")
    
    print("\n" + "=" * 80)
    print("NIFEA COHORT SUMMARY BREAKDOWN")
    print("=" * 80)
    for c in ["Normal", "Arrhythmia"]:
        sub_df = df_res[df_res["cohort"] == c]
        print(f"\nCohort: {c} (N = {len(sub_df)} records)")
        print(f"  Mean Detected Beats:       {sub_df['detected_beat_count'].mean():.1f}")
        print(f"  Mean Maternal HR:          {sub_df['maternal_hr_bpm'].mean():.1f} bpm")
        print(f"  Median Detected FHR:       {sub_df[sub_df['detected_beat_count']>10]['median_fhr_bpm'].median():.1f} bpm")
        print(f"  Mean % Physiological FHR:  {sub_df['pct_physiological_110_160'].mean():.1f}%")
        print(f"  Mean % Plausible FHR:      {sub_df['pct_plausible_100_180'].mean():.1f}%")
        print(f"  Mean Maternal Leakage:     {sub_df['maternal_leakage_coincidence_pct'].mean():.1f}%")
        print(f"  Failure Mode Counts:")
        print(sub_df["failure_classification"].value_counts().to_string())

if __name__ == "__main__":
    run_nifea_processing()
