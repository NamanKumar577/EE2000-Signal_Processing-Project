"""
tools/validation/run_nifea_analysis.py
──────────────────────────────────────────────────────────────────────────────
Phase 7: Clinical Dataset Validation on the Non-Invasive Fetal ECG
Arrhythmia Database (NIFEA).

Database Structure:
  - 26 in-vivo clinical recordings: 12 arrhythmia cases (ARR_01..ARR_12), 14 normal cases (NR_01..NR_14).
  - Sampling rates: 1000 Hz (22 records), 500 Hz (4 records).
  - Leads: 1 maternal thoracic ECG lead + 5 abdominal biopotential leads (Abdomen_1..5).
  - Ground truth annotations: None provided in raw database.

Methodology:
  1. Decimation with anti-aliasing filtering to 250 Hz (M=4 for 1000 Hz, M=2 for 500 Hz).
  2. Select 4 abdominal leads: [1, 2, 3, 4] (Abdomen_1..4).
  3. Run 4-channel causal beamformer (label-free PC3 and autocorr).
  4. Clinical metrics:
     - Mean FHR (bpm)
     - % of beats in physiological window [110, 160] bpm
     - % of beats in plausible window [100, 180] bpm
     - Outlier / impossible FHR rate (<60 or >240 bpm)
     - RR interval coefficient of variation (CV)
     - Maternal thoracic R-peak synchronization / leakage ratio

Outputs:
  - validation/clinical/NIFEA_DATASET_AUDIT.md
  - validation/clinical/NIFEA_RESULTS.csv
  - validation/clinical/NIFEA_VALIDATION_REPORT.md
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
import numpy as np
import wfdb
from scipy.signal import decimate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, DEFAULT_CONFIG, run_causal, preprocess_causal, detect_causal
)
from src.fhr import compute_fhr
from src.qrs_detector import detect_fetal_qrs

NIFEA_DIR = PROJECT_ROOT / "data" / "Non-Invasive_Fetal_ECG_Arrhythmia_Database" / "DESTINATION"
CLINICAL_DIR = PROJECT_ROOT / "validation" / "clinical"
CLINICAL_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FS = 250

def process_nifea_record(rec_path: Path):
    rec_id = rec_path.stem
    record = wfdb.rdrecord(str(rec_path.with_suffix("")))
    sig = record.p_signal
    orig_fs = int(record.fs)
    n_ch = record.n_sig
    sig_names = record.sig_name
    
    # Decimation factor
    q = orig_fs // TARGET_FS
    assert orig_fs % TARGET_FS == 0, f"Unsupported fs: {orig_fs}"
    
    # Apply anti-aliasing decimation (Chebyshev type I order 8)
    sig_250 = decimate(sig, q, ftype="iir", axis=0, zero_phase=False)
    
    # Lead 0 is maternal ECG thoracic reference
    m_ecg_ref = sig_250[:, 0]
    m_peaks, _ = detect_fetal_qrs(m_ecg_ref, fs=TARGET_FS)
    m_fhr = 60.0 * TARGET_FS / np.median(np.diff(m_peaks)) if len(m_peaks) > 5 else 0.0
    
    # Abdominal leads: leads 1, 2, 3, 4
    x4 = sig_250[:, 1:5]
    
    # Calibrate beamformer (first 30s)
    cal_len = 30 * TARGET_FS
    x_cal = x4[:cal_len] if len(x4) >= cal_len else x4
    bank = CalibrationBank(x4, DEFAULT_CONFIG, cal_seconds=30)
    j, _ = bank.select("pc3")
    w = bank.weights(j)
    
    fecg_out, det_res = run_causal(x4, w)
    det_peaks = det_res.peaks
    
    # Evaluation metrics
    n_det = len(det_peaks)
    dur_s = len(sig_250) / TARGET_FS
    
    if n_det > 10:
        rr_samples = np.diff(det_peaks)
        fhr_instant = 60.0 * TARGET_FS / rr_samples
        # Filter plausible physiological values
        mean_fhr = float(np.median(fhr_instant))
        fhr_std = float(np.std(fhr_instant))
        rr_cv = float(np.std(rr_samples) / np.mean(rr_samples))
        
        pct_norm = float(np.sum((fhr_instant >= 110) & (fhr_instant <= 160)) / len(fhr_instant) * 100)
        pct_plausible = float(np.sum((fhr_instant >= 100) & (fhr_instant <= 180)) / len(fhr_instant) * 100)
        pct_outliers = float(np.sum((fhr_instant < 60) | (fhr_instant > 240)) / len(fhr_instant) * 100)
    else:
        mean_fhr = 0.0
        fhr_std = 0.0
        rr_cv = 0.0
        pct_norm = 0.0
        pct_plausible = 0.0
        pct_outliers = 100.0
        
    # Maternal leakage check: how many detected fetal peaks coincide with maternal peaks?
    # Coincidence tolerance = 25 ms (6 samples at 250 Hz)
    leak_count = 0
    if len(m_peaks) > 0 and n_det > 0:
        for p in det_peaks:
            if np.min(np.abs(p - m_peaks)) <= 6:
                leak_count += 1
    m_leak_pct = (leak_count / n_det * 100) if n_det > 0 else 0.0

    cohort = "Arrhythmia" if "ARR" in rec_id else "Normal"
    
    return {
        "record_id": rec_id,
        "cohort": cohort,
        "original_fs_hz": orig_fs,
        "decimation_ratio": q,
        "duration_s": round(dur_s, 1),
        "n_channels": n_ch,
        "maternal_hr_bpm": round(m_fhr, 1),
        "n_fetal_detections": n_det,
        "median_fhr_bpm": round(mean_fhr, 1),
        "fhr_std_bpm": round(fhr_std, 1),
        "rr_cv": round(rr_cv, 3),
        "pct_fhr_110_160": round(pct_norm, 1),
        "pct_fhr_100_180": round(pct_plausible, 1),
        "pct_impossible_outliers": round(pct_outliers, 1),
        "maternal_coincidence_pct": round(m_leak_pct, 1),
    }

def main():
    print("=" * 70)
    print("STARTING PHASE 7: CLINICAL DATASET VALIDATION (NIFEA)")
    print("=" * 70)
    
    hea_files = sorted(list(NIFEA_DIR.glob("*.hea")))
    print(f"Discovered {len(hea_files)} clinical records in NIFEA.")
    
    results = []
    for hea in hea_files:
        t0 = time.time()
        res = process_nifea_record(hea)
        results.append(res)
        print(f"  Processed {res['record_id']:8s} ({res['cohort']:10s}, {res['original_fs_hz']}Hz): "
              f"FHR={res['median_fhr_bpm']:5.1f} bpm, Norm={res['pct_fhr_110_160']:5.1f}%, Leak={res['maternal_coincidence_pct']:4.1f}% ({time.time()-t0:.2f}s)")
        
    # Save NIFEA_RESULTS.csv
    csv_path = CLINICAL_DIR / "NIFEA_RESULTS.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(f"\nWritten: {csv_path}")

    # Compute Cohort Aggregates
    arr_res = [r for r in results if r["cohort"] == "Arrhythmia"]
    norm_res = [r for r in results if r["cohort"] == "Normal"]
    
    print("\n=== CLINICAL COHORT SUMMARY ===")
    print(f"Normal Cohort (N={len(norm_res)}):")
    print(f"  Mean FHR: {np.mean([r['median_fhr_bpm'] for r in norm_res]):.1f} bpm")
    print(f"  % in Normal [110, 160] bpm: {np.mean([r['pct_fhr_110_160'] for r in norm_res]):.1f}%")
    print(f"  % Plausible [100, 180] bpm: {np.mean([r['pct_fhr_100_180'] for r in norm_res]):.1f}%")
    print(f"  Maternal Coincidence Leakage: {np.mean([r['maternal_coincidence_pct'] for r in norm_res]):.1f}%")

    print(f"\nArrhythmia Cohort (N={len(arr_res)}):")
    print(f"  Mean FHR: {np.mean([r['median_fhr_bpm'] for r in arr_res]):.1f} bpm")
    print(f"  % in Normal [110, 160] bpm: {np.mean([r['pct_fhr_110_160'] for r in arr_res]):.1f}%")
    print(f"  % Plausible [100, 180] bpm: {np.mean([r['pct_fhr_100_180'] for r in arr_res]):.1f}%")
    print(f"  Maternal Coincidence Leakage: {np.mean([r['maternal_coincidence_pct'] for r in arr_res]):.1f}%")

if __name__ == "__main__":
    main()
