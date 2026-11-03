"""
tools/pre_fpga/run_raw_qrs_vs_fhr_study.py
──────────────────────────────────────────────────────────────────────────────
Task C: Separation of Raw QRS Detection Performance from FHR Post-Processing.

Evaluates:
  1. Raw QRS metrics (TP, FP, FN, Sens, Prec, F1, timing error) before any repair.
  2. Four-stage FHR comparison:
     - M1: Raw instantaneous FHR
     - M2: Causal Median5 filter on raw RR intervals
     - M3: Physiological Beat Repair only (Fusion + Midpoint Split)
     - M4: Repaired Beats + Causal Median5 filter
  3. Strict Audit of Dangerous Cases:
     - Dynamic rate changes (Condition c2 accelerations/decelerations)
     - Arrhythmias and extrasystoles (Condition c4)
     - Verification of the 1.7–2.3 RR repair condition:
       Measures True Insertion Rate vs False Insertion Rate during rate changes.
  4. 2-bit State Flag Emulation:
     - 00: REAL_DETECTED
     - 01: INTERPOLATED_MIDPOINT
     - 10: FUSED_BEAT
     - 11: INVALID_INTERVAL
"""

import sys
import csv
import time
from pathlib import Path
from collections import defaultdict
import numpy as np
import wfdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, DEFAULT_CONFIG, run_causal
)
from src.evaluation import compute_beat_metrics, match_beats
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "pre_fpga" / "04_qrs_fhr_validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250

def causal_median5(arr: np.ndarray) -> np.ndarray:
    out = np.zeros_like(arr)
    buf = []
    for i, v in enumerate(arr):
        buf.append(v)
        if len(buf) > 5:
            buf.pop(0)
        out[i] = np.median(buf)
    return out

def apply_beat_repair(peaks: np.ndarray, ref_peaks: np.ndarray):
    """
    Apply physiological beat repair while tracking repair accuracy against ground truth.
    Returns: repaired_peaks, repaired_flags, n_fused, n_inserted, n_correct_insert, n_false_insert
    """
    if len(peaks) < 2:
        return peaks, np.zeros(len(peaks), dtype=int), 0, 0, 0, 0

    repaired_peaks = []
    repaired_flags = [] # 0: real, 1: midpoint, 2: fused
    n_fused = 0
    n_inserted = 0
    n_correct_insert = 0
    n_false_insert = 0

    repaired_peaks.append(peaks[0])
    repaired_flags.append(0)

    for i in range(1, len(peaks)):
        p_curr = peaks[i]
        p_prev = repaired_peaks[-1]
        rr = p_curr - p_prev

        # Fusion: false positive double-count if rr < 60 samples (240 ms / > 250 bpm)
        if rr < 60:
            n_fused += 1
            # Replace previous with average or keep current
            repaired_peaks[-1] = int(round(0.5 * (p_prev + p_curr)))
            repaired_flags[-1] = 2 # Fused
            continue

        # Check for isolated dropout: 1.7 to 2.3 * prev_rr
        if len(repaired_peaks) >= 2:
            prev_rr = repaired_peaks[-1] - repaired_peaks[-2]
            if 1.7 * prev_rr <= rr <= 2.3 * prev_rr:
                # Insert synthetic midpoint beat
                midpoint = int(round(p_prev + 0.5 * rr))
                repaired_peaks.append(midpoint)
                repaired_flags.append(1) # Midpoint
                n_inserted += 1

                # Verify if there is a real reference beat near this midpoint (+-50 ms / +-12.5 samples)
                if len(ref_peaks) > 0:
                    min_dist = np.min(np.abs(ref_peaks - midpoint))
                    if min_dist <= 12.5:
                        n_correct_insert += 1
                    else:
                        n_false_insert += 1

        repaired_peaks.append(p_curr)
        repaired_flags.append(0)

    return np.array(repaired_peaks, dtype=int), np.array(repaired_flags, dtype=int), n_fused, n_inserted, n_correct_insert, n_false_insert

def evaluate_fhr_series(peaks: np.ndarray, ref_peaks: np.ndarray, duration_sec: float = 300.0):
    if len(peaks) < 2:
        return 999.0, 999.0, 999.0, 0.0, 0.0, duration_sec

    # Calculate instantaneous RR and FHR
    rr = np.diff(peaks)
    fhr = np.zeros(len(rr))
    fhr_hold = 140.0
    invalid_beats = 0

    for i, r in enumerate(rr):
        if 60 <= r <= 300:
            fhr[i] = (60.0 * FS) / r
            fhr_hold = fhr[i]
        else:
            fhr[i] = fhr_hold
            invalid_beats += 1

    t_beats = peaks[1:] / FS
    t_grid = np.arange(0, duration_sec, 0.5)
    fhr_interp = np.interp(t_grid, t_beats, fhr, left=140.0, right=fhr_hold)

    # Reference FHR
    if len(ref_peaks) >= 2:
        rr_ref = np.diff(ref_peaks)
        fhr_ref = (60.0 * FS) / np.maximum(rr_ref, 1)
        t_ref = ref_peaks[1:] / FS
        ref_interp = np.interp(t_grid, t_ref, fhr_ref, left=140.0, right=fhr_ref[-1])
    else:
        return 999.0, 999.0, 999.0, 0.0, 0.0, duration_sec

    # Evaluate only after warmup (2.5 s)
    valid_mask = t_grid >= 2.5
    err = fhr_interp[valid_mask] - ref_interp[valid_mask]
    abs_err = np.abs(err)

    mae = float(np.mean(abs_err))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mape = float(np.mean(abs_err / (ref_interp[valid_mask] + 1e-6)) * 100.0)
    pct_5 = float(np.mean(abs_err <= 5.0) * 100.0)
    pct_10 = float(np.mean(abs_err <= 10.0) * 100.0)
    invalid_sec = float(invalid_beats * (1.0 / (np.mean(fhr_ref) / 60.0)))

    return mae, rmse, mape, pct_5, pct_10, invalid_sec

def main():
    print("=" * 80)
    print(" TASK C: RAW QRS PERFORMANCE VS. FHR CORRECTION STUDY")
    print("=" * 80)

    subs = [f"sub{i:02d}" for i in range(1, 11)]
    snrs = ["snr00dB", "snr06dB", "snr12dB"]
    conds = ["c0", "c1", "c2", "c3", "c4"]

    raw_qrs_rows = []
    fhr_stage_rows = []
    beat_repair_rows = []
    dynamic_hr_rows = []

    for sub in subs:
        for snr in snrs:
            snr_db = int(snr[3:5])
            for cond in conds:
                rec_name = f"{sub}_{snr}_l1_{cond}"
                base_path = str(DATA_DIR / sub / snr / rec_name)
                if not Path(base_path + "_fecg1.hea").exists():
                    continue

                try:
                    fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal[:, CHANNELS]
                    mecg = wfdb.rdrecord(base_path + "_mecg").p_signal[:, CHANNELS]
                    n1 = wfdb.rdrecord(base_path + "_noise1").p_signal[:, CHANNELS]
                    n2 = wfdb.rdrecord(base_path + "_noise2").p_signal[:, CHANNELS]
                    mix = fecg + mecg + n1 + n2
                    ref_qrs = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)
                except Exception:
                    continue

                # Run baseline extraction
                bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=10)
                j, _ = bank.select("autocorr")
                w = bank.weights(j)
                _, det = run_causal(mix, w, DEFAULT_CONFIG)
                raw_peaks = det.peaks

                # 1. Raw QRS Detection Metrics (Strict one-to-one beat matching at +-50 ms)
                bm = compute_beat_metrics(ref_qrs, raw_peaks, fs=FS, tolerance_ms=50.0)
                
                # Match beats sample-by-sample for timing jitter
                tp, fp, fn = match_beats(ref_qrs, raw_peaks, fs=FS, tolerance_ms=50.0)
                # Compute timing errors for matched beats
                timing_errors_ms = []
                for r in ref_qrs:
                    # find closest within 12.5 samples
                    dists = raw_peaks - r
                    close = dists[np.abs(dists) <= 12.5]
                    if len(close) > 0:
                        timing_errors_ms.append(close[0] * 4.0)

                mean_timing_err = float(np.mean(timing_errors_ms)) if timing_errors_ms else 0.0
                std_timing_err = float(np.std(timing_errors_ms)) if timing_errors_ms else 0.0

                raw_qrs_rows.append({
                    "record": rec_name,
                    "subject": sub,
                    "snr_db": snr_db,
                    "condition": cond,
                    "tp": bm.tp,
                    "fp": bm.fp,
                    "fn": bm.fn,
                    "sensitivity": round(bm.sensitivity or 0.0, 4),
                    "precision": round(bm.ppv or 0.0, 4),
                    "f1": round((bm.f1 or 0.0) * 100, 2),
                    "mean_timing_error_ms": round(mean_timing_err, 2),
                    "std_timing_error_ms": round(std_timing_err, 2),
                    "n_ref": len(ref_qrs),
                    "n_raw_det": len(raw_peaks)
                })

                # 2. Evaluate FHR Processing Stages: M1, M2, M3, M4
                # M1: Raw instantaneous FHR
                mae1, rmse1, mape1, p5_1, p10_1, inv1 = evaluate_fhr_series(raw_peaks, ref_qrs)

                # M2: Median5 on raw
                if len(raw_peaks) >= 2:
                    rr_raw = np.diff(raw_peaks)
                    rr_med = causal_median5(rr_raw)
                    p_med = np.concatenate([[raw_peaks[0]], raw_peaks[0] + np.cumsum(rr_med)])
                else:
                    p_med = raw_peaks
                mae2, rmse2, mape2, p5_2, p10_2, inv2 = evaluate_fhr_series(p_med, ref_qrs)

                # M3: Beat repair only
                p_rep, flags_rep, n_fused, n_ins, n_cor_ins, n_fal_ins = apply_beat_repair(raw_peaks, ref_qrs)
                mae3, rmse3, mape3, p5_3, p10_3, inv3 = evaluate_fhr_series(p_rep, ref_qrs)

                # M4: Beat repair + Median5
                if len(p_rep) >= 2:
                    rr_rep = np.diff(p_rep)
                    rr_rep_med = causal_median5(rr_rep)
                    p_rep_med = np.concatenate([[p_rep[0]], p_rep[0] + np.cumsum(rr_rep_med)])
                else:
                    p_rep_med = p_rep
                mae4, rmse4, mape4, p5_4, p10_4, inv4 = evaluate_fhr_series(p_rep_med, ref_qrs)

                fhr_stage_rows.append({
                    "record": rec_name,
                    "subject": sub,
                    "snr_db": snr_db,
                    "condition": cond,
                    "m1_mae_bpm": round(mae1, 2),
                    "m1_rmse_bpm": round(rmse1, 2),
                    "m1_pct_within_5bpm": round(p5_1, 1),
                    "m2_mae_bpm": round(mae2, 2),
                    "m2_rmse_bpm": round(rmse2, 2),
                    "m2_pct_within_5bpm": round(p5_2, 1),
                    "m3_mae_bpm": round(mae3, 2),
                    "m3_rmse_bpm": round(rmse3, 2),
                    "m3_pct_within_5bpm": round(p5_3, 1),
                    "m4_mae_bpm": round(mae4, 2),
                    "m4_rmse_bpm": round(rmse4, 2),
                    "m4_pct_within_5bpm": round(p5_4, 1),
                    "m4_pct_within_10bpm": round(p10_4, 1),
                    "delta_mae_m4_vs_m1": round(mae4 - mae1, 2)
                })

                # 3. Beat Repair Specific Audit
                ins_accuracy = (n_cor_ins / n_ins * 100.0) if n_ins > 0 else 100.0
                beat_repair_rows.append({
                    "record": rec_name,
                    "subject": sub,
                    "snr_db": snr_db,
                    "condition": cond,
                    "n_raw_beats": len(raw_peaks),
                    "n_fused_beats": n_fused,
                    "n_inserted_beats": n_ins,
                    "n_correct_inserts": n_cor_ins,
                    "n_false_inserts": n_fal_ins,
                    "insertion_accuracy_pct": round(ins_accuracy, 1)
                })

                # 4. Dynamic Tracking for c2
                if cond == "c2":
                    dynamic_hr_rows.append({
                        "record": rec_name,
                        "subject": sub,
                        "snr_db": snr_db,
                        "m1_mae_bpm": round(mae1, 2),
                        "m4_mae_bpm": round(mae4, 2),
                        "m4_pct_within_5bpm": round(p5_4, 1),
                        "inserted_beats": n_ins,
                        "false_inserts": n_fal_ins
                    })

    # Save CSVs
    raw_csv = OUT_DIR / "QRS_RAW_METRICS.csv"
    with open(raw_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(raw_qrs_rows[0].keys()))
        writer.writeheader()
        writer.writerows(raw_qrs_rows)
    print(f"Saved raw QRS metrics CSV: {raw_csv}")

    fhr_csv = OUT_DIR / "FHR_STAGE_COMPARISON.csv"
    with open(fhr_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fhr_stage_rows[0].keys()))
        writer.writeheader()
        writer.writerows(fhr_stage_rows)
    print(f"Saved FHR stage comparison CSV: {fhr_csv}")

    repair_csv = OUT_DIR / "BEAT_REPAIR_AUDIT.csv"
    with open(repair_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(beat_repair_rows[0].keys()))
        writer.writeheader()
        writer.writerows(beat_repair_rows)
    print(f"Saved beat repair audit CSV: {repair_csv}")

    dyn_csv = OUT_DIR / "DYNAMIC_HEART_RATE_ANALYSIS.csv"
    with open(dyn_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(dynamic_hr_rows[0].keys()))
        writer.writeheader()
        writer.writerows(dynamic_hr_rows)
    print(f"Saved dynamic heart rate analysis CSV: {dyn_csv}")

    # Summary
    print("\n" + "=" * 80)
    print(" FHR STAGE SUMMARY (M1 -> M2 -> M3 -> M4)")
    print("=" * 80)
    m1_maes = [r["m1_mae_bpm"] for r in fhr_stage_rows]
    m2_maes = [r["m2_mae_bpm"] for r in fhr_stage_rows]
    m3_maes = [r["m3_mae_bpm"] for r in fhr_stage_rows]
    m4_maes = [r["m4_mae_bpm"] for r in fhr_stage_rows]
    m4_p5 = [r["m4_pct_within_5bpm"] for r in fhr_stage_rows]

    print(f"M1: Raw Instantaneous  : MAE = {np.mean(m1_maes):.2f} +/- {np.std(m1_maes):.2f} bpm")
    print(f"M2: Median5 Only       : MAE = {np.mean(m2_maes):.2f} +/- {np.std(m2_maes):.2f} bpm")
    print(f"M3: Beat Repair Only   : MAE = {np.mean(m3_maes):.2f} +/- {np.std(m3_maes):.2f} bpm")
    print(f"M4: Repair + Median5   : MAE = {np.mean(m4_maes):.2f} +/- {np.std(m4_maes):.2f} bpm (Time <=5 bpm: {np.mean(m4_p5):.1f}%)")

if __name__ == "__main__":
    main()
