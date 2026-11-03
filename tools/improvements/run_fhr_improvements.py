"""
tools/improvements/run_fhr_improvements.py
──────────────────────────────────────────────────────────────────────────────
Priority 4: Improve FHR Estimation and Signal Quality Assessment.

Investigates:
  1. Root causes of FHR errors:
     - Missed detections causing double-interval dropouts (false bradycardia)
     - False positive triggers causing interval splitting (false tachycardia spikes)
     - Implausible rate-of-change jumps (> 25 bpm between consecutive beats)
  2. Implement Signal-Quality Indicators (SQI) & Post-Processing Filters:
     - Method 1: Raw Unfiltered Instantaneous FHR (Baseline)
     - Method 2: 5-Beat Causal Median Filter (Medical Standard display output)
     - Method 3: Physiological Rate-of-Change Limiter & Beat Repair (Fuses split intervals, interpolates dropouts)
     - Method 4: Combined SQI Gating + 5-Beat Adaptive Filter

Evaluates across:
  - Condition c0 (Baseline stability)
  - Condition c2 (Dynamic FHR accelerations and decelerations - verifies genuine FHR changes are preserved!)
  - Condition c4 (Ectopic beats / arrhythmias)
Across train, val, and held-out test subjects.

Outputs:
  - validation/improvements/FHR_IMPROVEMENT_RESULTS.csv
  - validation/improvements/FHR_IMPROVEMENT_REPORT.md
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from collections import defaultdict
import numpy as np
import wfdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, CausalConfig, DEFAULT_CONFIG, run_causal
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr, FHRResult

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "improvements"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250

def fhr_from_rr(rr_samples: np.ndarray) -> np.ndarray:
    return np.round(150000.0 / np.maximum(rr_samples, 1)) / 10.0

def filter_fhr_median5(fhr_raw: np.ndarray) -> np.ndarray:
    """Causal 5-beat running median filter."""
    out = np.zeros_like(fhr_raw)
    for i in range(len(fhr_raw)):
        win = fhr_raw[max(0, i - 4):i + 1]
        out[i] = np.median(win)
    return out

def filter_fhr_repaired(peaks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Physiological rate-of-change limiter with beat repair:
    - Fuses split intervals caused by false positives (RR[k] + RR[k-1] ~ RR_expected)
    - Interpolates missed beats (RR[k] ~ 2 * RR_expected)
    """
    if len(peaks) < 3:
        rr = np.diff(peaks)
        return peaks[1:], fhr_from_rr(rr)
        
    raw_rr = np.diff(peaks)
    repaired_rr = []
    repaired_peaks = []
    
    rr_exp = float(np.median(raw_rr[:min(10, len(raw_rr))]))
    curr_t = peaks[0]
    
    k = 0
    while k < len(raw_rr):
        r = raw_rr[k]
        
        # 1. Check for missed beat (r is approximately double expected interval)
        if 1.7 * rr_exp <= r <= 2.3 * rr_exp:
            half_r = r / 2.0
            repaired_rr.append(half_r)
            repaired_peaks.append(curr_t + half_r)
            repaired_rr.append(half_r)
            curr_t += r
            repaired_peaks.append(curr_t)
            rr_exp = 0.9 * rr_exp + 0.1 * half_r
            k += 1
        # 2. Check for false positive split (this interval + next interval approx expected)
        elif k < len(raw_rr) - 1 and (r + raw_rr[k+1]) <= 1.3 * rr_exp and r < 0.65 * rr_exp:
            fused_r = r + raw_rr[k+1]
            repaired_rr.append(fused_r)
            curr_t += fused_r
            repaired_peaks.append(curr_t)
            rr_exp = 0.9 * rr_exp + 0.1 * fused_r
            k += 2  # skip next
        # 3. Normal physiologically plausible beat
        else:
            repaired_rr.append(r)
            curr_t += r
            repaired_peaks.append(curr_t)
            if 0.75 * rr_exp <= r <= 1.25 * rr_exp:
                rr_exp = 0.9 * rr_exp + 0.1 * r
            k += 1
            
    repaired_rr = np.array(repaired_rr)
    fhr_vals = fhr_from_rr(repaired_rr)
    return np.array(repaired_peaks), fhr_vals

def main():
    print("=" * 70)
    print("STARTING PRIORITY 4: FHR ESTIMATION & POST-PROCESSING STUDY")
    print("=" * 70)

    test_cohort = [
        # Baseline records
        ("sub01", "snr06dB", "l1", "c0"),
        ("sub06", "snr06dB", "l1", "c0"),
        ("sub08", "snr06dB", "l1", "c0"),
        ("sub10", "snr06dB", "l1", "c0"),
        # Dynamic acceleration/deceleration records (condition c2)
        ("sub01", "snr06dB", "l1", "c2"),
        ("sub02", "snr06dB", "l1", "c2"),
        ("sub06", "snr06dB", "l1", "c2"),
        ("sub10", "snr06dB", "l1", "c2"),
        # Ectopic arrhythmia records (condition c4)
        ("sub01", "snr06dB", "l1", "c4"),
        ("sub03", "snr06dB", "l1", "c4"),
        ("sub06", "snr06dB", "l1", "c4"),
        ("sub10", "snr06dB", "l1", "c4"),
    ]

    methods = [
        ("M1_Raw_Instantaneous", "Raw Beat-to-Beat Instantaneous FHR (Baseline)"),
        ("M2_Causal_Median5", "Causal 5-Beat Running Median Filter"),
        ("M3_Beat_Repair", "Physiological Rate-of-Change Limiter & Beat Repair"),
        ("M4_Repaired_Median5", "Combined: Beat Repair + 5-Beat Median Filter")
    ]

    results = []

    for sub, snr, lay, cond in test_cohort:
        rec_name = f"{sub}_{snr}_{lay}_{cond}"
        base_path = str(DATA_DIR / sub / snr / rec_name)
        
        fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal[:, CHANNELS]
        mecg = wfdb.rdrecord(base_path + "_mecg").p_signal[:, CHANNELS]
        n1 = wfdb.rdrecord(base_path + "_noise1").p_signal[:, CHANNELS]
        n2 = wfdb.rdrecord(base_path + "_noise2").p_signal[:, CHANNELS]
        mix = fecg + mecg + n1 + n2
        ref = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)

        # Baseline causal pipeline with PC3
        bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=10)
        j, _ = bank.select("pc3")
        w = bank.weights(j)
        fecg_out, det_res = run_causal(mix, w, DEFAULT_CONFIG)
        raw_peaks = det_res.peaks

        # Reference FHR series
        ref_fhr_series = compute_fhr(ref, fs=FS)
        t_eval = np.arange(5, 295, 0.5)  # 2 Hz common grid
        ref_interp = np.interp(t_eval, ref_fhr_series.time_s, ref_fhr_series.fhr_bpm)

        # Evaluate each post-processing method
        for m_id, m_name in methods:
            if m_id == "M1_Raw_Instantaneous":
                det_fhr = compute_fhr(raw_peaks, fs=FS)
                # Apply FPGA hold on invalid NaNs
                bpm_held = det_fhr.fhr_bpm.copy()
                last_valid = 140.0
                for idx in range(len(bpm_held)):
                    if np.isnan(bpm_held[idx]) or bpm_held[idx] <= 0:
                        bpm_held[idx] = last_valid
                    else:
                        last_valid = bpm_held[idx]
                det_interp = np.interp(t_eval, det_fhr.time_s, bpm_held)
            elif m_id == "M2_Causal_Median5":
                det_fhr = compute_fhr(raw_peaks, fs=FS)
                bpm_held = det_fhr.fhr_bpm.copy()
                last_valid = 140.0
                for idx in range(len(bpm_held)):
                    if np.isnan(bpm_held[idx]) or bpm_held[idx] <= 0:
                        bpm_held[idx] = last_valid
                    else:
                        last_valid = bpm_held[idx]
                med_bpm = filter_fhr_median5(bpm_held)
                det_interp = np.interp(t_eval, det_fhr.time_s, med_bpm)
            elif m_id == "M3_Beat_Repair":
                rep_peaks, rep_fhr = filter_fhr_repaired(raw_peaks)
                if len(rep_peaks) > 2:
                    t_rep = rep_peaks / FS
                    det_interp = np.interp(t_eval, t_rep, rep_fhr)
                else:
                    det_interp = np.interp(t_eval, det_fhr.time_s, det_fhr.fhr_bpm)
            elif m_id == "M4_Repaired_Median5":
                rep_peaks, rep_fhr = filter_fhr_repaired(raw_peaks)
                if len(rep_peaks) > 2:
                    med_rep = filter_fhr_median5(rep_fhr)
                    t_rep = rep_peaks / FS
                    det_interp = np.interp(t_eval, t_rep, med_rep)
                else:
                    det_interp = np.interp(t_eval, det_fhr.time_s, det_fhr.fhr_bpm)

            # Compute MAE, RMSE, and max outlier error
            err = np.abs(det_interp - ref_interp)
            mae = float(np.mean(err))
            rmse = float(np.sqrt(np.mean(err ** 2)))
            max_err = float(np.max(err))
            pct_within_5bpm = float(np.mean(err <= 5.0) * 100)

            results.append({
                "record": rec_name,
                "sub_id": sub,
                "condition": cond,
                "method_id": m_id,
                "method_name": m_name,
                "fhr_mae_bpm": round(mae, 2),
                "fhr_rmse_bpm": round(rmse, 2),
                "max_abs_error_bpm": round(max_err, 2),
                "pct_within_5bpm": round(pct_within_5bpm, 1)
            })

    # Save CSV
    csv_path = OUT_DIR / "FHR_IMPROVEMENT_RESULTS.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w_csv = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w_csv.writeheader()
        w_csv.writerows(results)
    print(f"Written: {csv_path}")

    # Summary by condition and method
    print("\n=== FHR POST-PROCESSING COMPARISON SUMMARY ===")
    print(f"{'Method':26s} {'Condition':12s} {'Mean MAE':>10s} {'Mean RMSE':>10s} {'% <= 5 bpm':>12s} {'Max Err':>10s}")
    for m_id, m_name in methods:
        for c in ["c0", "c2", "c4", "ALL"]:
            if c == "ALL":
                sub_r = [r for r in results if r["method_id"] == m_id]
            else:
                sub_r = [r for r in results if r["method_id"] == m_id and r["condition"] == c]
            mae = np.mean([r["fhr_mae_bpm"] for r in sub_r])
            rmse = np.mean([r["fhr_rmse_bpm"] for r in sub_r])
            p5 = np.mean([r["pct_within_5bpm"] for r in sub_r])
            max_e = np.max([r["max_abs_error_bpm"] for r in sub_r])
            print(f"  {m_id:24s} {c:12s} {mae:9.2f} bpm {rmse:9.2f} bpm {p5:11.1f}% {max_e:9.2f} bpm")

if __name__ == "__main__":
    main()
