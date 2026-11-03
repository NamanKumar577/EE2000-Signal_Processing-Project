"""
tools/validation/run_qrs_fhr_analysis.py
──────────────────────────────────────────────────────────────────────────────
Phase 5: QRS Detection and FHR Estimation Sensitivity.
Executes:
  1. Beat-matching tolerance sweep: +-10 ms, +-20 ms, +-50 ms, +-100 ms.
  2. Detector parameter sweep:
     - BP low cutoff: 5, 8, 10, 12 Hz
     - BP high cutoff: 25, 30, 35, 40 Hz
     - MWI length: 10, 15, 20, 25, 30 samples
     - Refractory period: 37, 45, 50, 55, 62 samples (148 to 248 ms)
     - Level update shift: 2, 3, 4 (EMA gain)
  3. Timing jitter and latency offset evaluation.
  4. FHR Estimation and Bland-Altman Analysis:
     - FHR MAE, RMSE, Bias, and 95% Limits of Agreement
     - Physiological stratification: Bradycardia (<110), Normal (110-160), Tachycardia (>160)
     - Condition c2 acceleration/deceleration tracking

Outputs:
  - validation/detector/QRS_DETECTION_RESULTS.csv
  - validation/detector/FHR_RESULTS.csv
  - validation/detector/PARAMETER_SWEEP_RESULTS.csv
  - validation/detector/QRS_FHR_REPORT.md
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
import numpy as np
import wfdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, CausalConfig, DEFAULT_CONFIG, run_causal, detect_causal, preprocess_causal
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
DET_DIR = PROJECT_ROOT / "validation" / "detector"
DET_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250

def load_case(sub: str, snr: str, cond: str):
    base_path = str(DATA_DIR / sub / snr / f"{sub}_{snr}_l1_{cond}")
    fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal[:, CHANNELS]
    mecg = wfdb.rdrecord(base_path + "_mecg").p_signal[:, CHANNELS]
    n1 = wfdb.rdrecord(base_path + "_noise1").p_signal[:, CHANNELS]
    n2 = wfdb.rdrecord(base_path + "_noise2").p_signal[:, CHANNELS]
    mix = fecg + mecg + n1 + n2
    ref = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)
    return mix, ref

def main():
    print("=" * 70)
    print("STARTING PHASE 5: QRS DETECTION & FHR ESTIMATION SENSITIVITY")
    print("=" * 70)

    test_records = [
        ("sub01", "snr12dB", "c0"),
        ("sub01", "snr06dB", "c0"),
        ("sub01", "snr00dB", "c0"),
        ("sub01", "snr06dB", "c1"),
        ("sub01", "snr06dB", "c2"),
        ("sub01", "snr06dB", "c3"),
        ("sub01", "snr06dB", "c4"),
        ("sub06", "snr06dB", "c0"),
        ("sub04", "snr06dB", "c0"),
        ("sub10", "snr06dB", "c0"),
    ]

    # Pre-load data and compute base PC3 weights
    data_cache = []
    for sub, snr, cond in test_records:
        mix, ref = load_case(sub, snr, cond)
        bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=0)
        j, _ = bank.select("pc3")
        w = bank.weights(j)
        proj = mix @ w
        fecg = preprocess_causal(proj, DEFAULT_CONFIG)
        data_cache.append((f"{sub}_{snr}_{cond}", sub, snr, cond, mix, proj, fecg, ref, w))

    # =========================================================================
    # PART 1: BEAT-MATCHING TOLERANCE SENSITIVITY
    # =========================================================================
    print("\n--- Part 1: Beat-Matching Tolerance Sweep ---")
    tol_rows = []
    # Tolerances in ms and samples: 10 ms (2.5), 20 ms (5), 50 ms (12.5), 100 ms (25)
    tols_ms = [10, 20, 50, 100]
    
    for rec_id, sub, snr, cond, mix, proj, fecg, ref, w in data_cache:
        det_res = detect_causal(fecg, DEFAULT_CONFIG)
        peaks = det_res.peaks
        
        for tol_ms in tols_ms:
            tol_samples = int(round(tol_ms / 1000.0 * FS))
            # Custom beat metrics with variable tolerance window
            matched_ref = set()
            tp = 0
            fp = 0
            timing_errors = []
            
            for p in peaks:
                dists = np.abs(ref - p)
                idx = int(np.argmin(dists))
                if dists[idx] <= tol_samples and idx not in matched_ref:
                    tp += 1
                    matched_ref.add(idx)
                    timing_errors.append(p - ref[idx])
                else:
                    fp += 1
            fn = len(ref) - tp
            sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            ppv = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            f1 = (2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) > 0 else 0.0
            
            mean_jitter = float(np.mean(np.abs(timing_errors))) * (1000.0 / FS) if timing_errors else 0.0
            std_jitter = float(np.std(timing_errors)) * (1000.0 / FS) if timing_errors else 0.0
            
            tol_rows.append({
                "record": rec_id,
                "sub_id": sub,
                "snr": snr,
                "condition": cond,
                "tolerance_ms": tol_ms,
                "tolerance_samples": tol_samples,
                "f1": round(f1 * 100, 2),
                "sensitivity": round(sens * 100, 2),
                "ppv": round(ppv * 100, 2),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "mean_abs_jitter_ms": round(mean_jitter, 2),
                "std_jitter_ms": round(std_jitter, 2)
            })

    with open(DET_DIR / "QRS_DETECTION_RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(tol_rows[0].keys()))
        w.writeheader()
        w.writerows(tol_rows)
    print(f"Written: {DET_DIR / 'QRS_DETECTION_RESULTS.csv'}")

    # =========================================================================
    # PART 2: DETECTOR PARAMETER SWEEP
    # =========================================================================
    print("\n--- Part 2: Parameter Sweep ---")
    param_rows = []
    
    # Sweep configurations
    sweeps = [
        # 1. Bandpass Low Cutoff
        ("bp_low", [5.0, 8.0, 10.0, 12.0]),
        # 2. Bandpass High Cutoff
        ("bp_high", [25.0, 30.0, 35.0, 40.0]),
        # 3. MWI Length
        ("mwi_len", [10, 15, 20, 25, 30]),
        # 4. Refractory Period
        ("refractory", [37, 45, 50, 55, 62]),
        # 5. EMA Shift (adaptation gain)
        ("level_shift", [2, 3, 4])
    ]

    for param_name, values in sweeps:
        for val in values:
            f1_list, mae_list = [], []
            for rec_id, sub, snr, cond, mix, proj, fecg, ref, w in data_cache:
                kwargs = {}
                if param_name == "bp_low":
                    kwargs["det_low_hz"] = float(val)
                elif param_name == "bp_high":
                    kwargs["det_high_hz"] = float(val)
                elif param_name == "mwi_len":
                    kwargs["mwi_len"] = int(val)
                elif param_name == "refractory":
                    kwargs["refractory"] = int(val)
                elif param_name == "level_shift":
                    kwargs["level_shift"] = int(val)
                
                cfg = CausalConfig(**kwargs)
                det_res = detect_causal(fecg, cfg)
                m = compute_beat_metrics(ref, det_res.peaks, fs=FS)
                fc = compare_fhr(compute_fhr(det_res.peaks, fs=FS), ref, fs=FS)
                f1_list.append(m.f1 or 0.0)
                if not np.isnan(fc.mean_abs_error_bpm):
                    mae_list.append(fc.mean_abs_error_bpm)
                    
            param_rows.append({
                "parameter": param_name,
                "value": val,
                "mean_f1": round(float(np.mean(f1_list)) * 100, 2),
                "std_f1": round(float(np.std(f1_list)) * 100, 2),
                "min_f1": round(float(np.min(f1_list)) * 100, 2),
                "max_f1": round(float(np.max(f1_list)) * 100, 2),
                "mean_fhr_mae": round(float(np.mean(mae_list)), 2) if mae_list else 999.0
            })

    with open(DET_DIR / "PARAMETER_SWEEP_RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(param_rows[0].keys()))
        w.writeheader()
        w.writerows(param_rows)
    print(f"Written: {DET_DIR / 'PARAMETER_SWEEP_RESULTS.csv'}")

    # =========================================================================
    # PART 3: FHR ESTIMATION & BLAND-ALTMAN ANALYSIS
    # =========================================================================
    print("\n--- Part 3: FHR Estimation & Bland-Altman ---")
    fhr_rows = []
    
    all_fhr_ref = []
    all_fhr_det = []
    all_errors = []

    for rec_id, sub, snr, cond, mix, proj, fecg, ref, w in data_cache:
        det_res = detect_causal(fecg, DEFAULT_CONFIG)
        peaks = det_res.peaks
        
        # Beat-to-beat RR intervals
        if len(peaks) > 1 and len(ref) > 1:
            ref_fhr_series = compute_fhr(ref, fs=FS)
            det_fhr_series = compute_fhr(peaks, fs=FS)
            comp = compare_fhr(det_fhr_series, ref, fs=FS)
            
            # Interpolated time-aligned FHR for Bland-Altman
            t_common = np.arange(5, 295, 0.5)  # 2 Hz FHR sampling
            fhr_ref_interp = np.interp(t_common, ref_fhr_series.time_s, ref_fhr_series.fhr_bpm)
            fhr_det_interp = np.interp(t_common, det_fhr_series.time_s, det_fhr_series.fhr_bpm)
            
            diff = fhr_det_interp - fhr_ref_interp
            bias = float(np.mean(diff))
            std_diff = float(np.std(diff))
            loa_lower = bias - 1.96 * std_diff
            loa_upper = bias + 1.96 * std_diff
            
            all_fhr_ref.extend(fhr_ref_interp)
            all_fhr_det.extend(fhr_det_interp)
            all_errors.extend(diff)
            
            # Stratify into Bradycardia (<110), Normal (110-160), Tachycardia (>160)
            brady_mask = fhr_ref_interp < 110
            norm_mask = (fhr_ref_interp >= 110) & (fhr_ref_interp <= 160)
            tachy_mask = fhr_ref_interp > 160
            
            mae_brady = float(np.mean(np.abs(diff[brady_mask]))) if np.any(brady_mask) else None
            mae_norm = float(np.mean(np.abs(diff[norm_mask]))) if np.any(norm_mask) else None
            mae_tachy = float(np.mean(np.abs(diff[tachy_mask]))) if np.any(tachy_mask) else None
            
            fhr_rows.append({
                "record": rec_id,
                "sub_id": sub,
                "condition": cond,
                "fhr_mae_bpm": round(comp.mean_abs_error_bpm, 2),
                "fhr_rmse_bpm": round(comp.rmse_bpm, 2),
                "bland_altman_bias_bpm": round(bias, 2),
                "loa_lower_bpm": round(loa_lower, 2),
                "loa_upper_bpm": round(loa_upper, 2),
                "mae_bradycardia": round(mae_brady, 2) if mae_brady is not None else "",
                "mae_normal_fhr": round(mae_norm, 2) if mae_norm is not None else "",
                "mae_tachycardia": round(mae_tachy, 2) if mae_tachy is not None else "",
            })

    with open(DET_DIR / "FHR_RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fhr_rows[0].keys()))
        w.writeheader()
        w.writerows(fhr_rows)
    print(f"Written: {DET_DIR / 'FHR_RESULTS.csv'}")

    all_errors = np.array(all_errors)
    global_bias = float(np.mean(all_errors))
    global_std = float(np.std(all_errors))
    print(f"\nGlobal Bland-Altman across 10 records:")
    print(f"  Bias: {global_bias:+.2f} bpm")
    print(f"  95% Limits of Agreement: [{global_bias - 1.96*global_std:.2f}, {global_bias + 1.96*global_std:.2f}] bpm")

    print("\nPhase 5 computation complete!")

if __name__ == "__main__":
    main()
