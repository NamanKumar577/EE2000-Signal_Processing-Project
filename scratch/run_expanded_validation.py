#!/usr/bin/env python3
"""
scratch/run_expanded_validation.py
──────────────────────────────────────────────────────────────────────────────
Phase 5: Expanded Dataset Validation across PhysioNet FECGSYNDB
10 Subjects (sub01 - sub10) x 5 SNRs (12dB, 9dB, 6dB, 3dB, 0dB) x 3 Conditions (c0, c1, c2)
= 150 Cases.

Evaluates bit-accurate FPGA model:
  - Sensitivity, PPV, F1 score
  - Missed detections (FN), False detections (FP), Maternal False detections (M_FP)
  - Maternal suppression (dB)
  - FHR error (bpm)
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import csv
from pathlib import Path
from typing import Dict, Any, List

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fpga_implementation.uart_host.validate_real_datasets import (
    load_fecgsyndb_case, HostSpatialCalibrator, generate_synthetic_benchmark
)
from fecg.hardware.bit_accurate_reference import run_bit_accurate_pipeline_final
from src.evaluation import match_beats

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_CSV = PROJECT_ROOT / "fpga_implementation" / "reports" / "phase5_expanded_fecgsyndb_results.csv"

SUBS = [f"sub{i:02d}" for i in range(1, 11)]
SNRS = ["snr12dB", "snr09dB", "snr06dB", "snr03dB", "snr00dB"]
CONDS = ["c0", "c1", "c2"]
FS = 250
TOL_SAMPLES = 13  # +-50 ms at 250 Hz is +-12.5 -> 13 samples
WARMUP_SAMPLES = 512

def evaluate_single_record(mix_4ch, fecg_4ch, mecg_4ch, f_qrs, m_qrs, fhr_nom):
    n_samples = len(mix_4ch)
    x_q12 = np.clip(np.round(mix_4ch), -32768, 32767).astype(np.int64)

    # Calibration on first 2500 samples (10 s)
    cal_len = min(2500, n_samples)
    calibrator = HostSpatialCalibrator()
    w_q15, pc_idx, conf_score, debug_info = calibrator.calibrate(mix_4ch[:cal_len], rule="autocorr")

    # Measure maternal suppression
    w_float = w_q15 / 32768.0
    m_proj = mecg_4ch @ w_float
    f_proj = fecg_4ch @ w_float
    p_m_in = np.mean(mecg_4ch[:, 0] ** 2) + 1e-12
    p_m_out = np.mean(m_proj ** 2) + 1e-12
    maternal_suppression_db = 10.0 * np.log10(p_m_in / p_m_out)

    # Run bit-accurate pipeline
    res = run_bit_accurate_pipeline_final(x_q12, w_q15)
    det_peaks = np.array(list(res.peaks), dtype=np.int64)

    # Exclude warmup samples (first 512 samples)
    f_eval = f_qrs[(f_qrs >= WARMUP_SAMPLES) & (f_qrs < n_samples)]
    m_eval = m_qrs[(m_qrs >= WARMUP_SAMPLES) & (m_qrs < n_samples)]
    d_eval = det_peaks[(det_peaks >= WARMUP_SAMPLES) & (det_peaks < n_samples)]

    # Match fetal beats
    tp, fp, fn = match_beats(f_eval, d_eval, fs=FS, tolerance_ms=50.0)

    # Find which detected beats were false positives
    det_matched = np.zeros(len(d_eval), dtype=bool)
    for ri, r in enumerate(f_eval):
        best_dist = TOL_SAMPLES + 1
        best_di = -1
        for di, d in enumerate(d_eval):
            if det_matched[di]:
                continue
            dist = abs(int(r) - int(d))
            if dist <= TOL_SAMPLES and dist < best_dist:
                best_dist = dist
                best_di = di
        if best_di >= 0:
            det_matched[best_di] = True

    fp_beats = d_eval[~det_matched]

    # Match false positive beats against maternal QRS to find maternal false detections
    m_tp, _, _ = match_beats(m_eval, fp_beats, fs=FS, tolerance_ms=50.0)
    m_fp = m_tp  # Count of false positive detections that correspond to maternal QRS

    sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    ppv = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = 2.0 * sens * ppv / (sens + ppv) if (sens + ppv) > 0 else 0.0
    m_far = (m_fp / len(m_eval)) if len(m_eval) > 0 else 0.0

    # FHR computation
    if len(f_eval) > 1:
        f_rr = np.diff(f_eval)
        gt_fhr = float(60.0 * FS / np.median(f_rr))
    else:
        gt_fhr = fhr_nom

    if len(d_eval) > 1:
        d_rr = np.diff(d_eval)
        valid_rr = d_rr[(d_rr >= 50) & (d_rr <= 300)]
        det_fhr = float(60.0 * FS / np.median(valid_rr)) if len(valid_rr) > 0 else 0.0
    else:
        det_fhr = 0.0

    fhr_err = abs(det_fhr - gt_fhr) if det_fhr > 0.0 else None

    return {
        "pc_selected": pc_idx + 1,
        "weights_q15": list(w_q15),
        "maternal_suppression_db": maternal_suppression_db,
        "n_ref_fetal": len(f_eval),
        "n_ref_maternal": len(m_eval),
        "n_det_beats": len(d_eval),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "m_fp": m_fp,
        "maternal_false_alarm_rate": m_far,
        "sensitivity": sens,
        "ppv": ppv,
        "f1": f1,
        "gt_fhr_bpm": gt_fhr,
        "det_fhr_bpm": det_fhr,
        "fhr_error_bpm": fhr_err
    }

def main():
    print("=" * 80)
    print("PHASE 5 EXPANDED FECGSYNDB BENCHMARK (150 CASES)")
    print("=" * 80)
    t_start = time.time()

    results = []
    total = len(SUBS) * len(SNRS) * len(CONDS)
    count = 0

    for sub in SUBS:
        for snr in SNRS:
            for cond in CONDS:
                count += 1
                case = load_fecgsyndb_case(DATA_DIR, sub, snr, cond)
                res = evaluate_single_record(
                    case["mix_4ch"], case["fecg_4ch"], case["mecg_4ch"],
                    case["f_qrs"], case["m_qrs"], case["fhr_nominal"]
                )
                row = {
                    "case_id": f"{sub}_{snr}_{cond}",
                    "sub_id": sub,
                    "snr": snr,
                    "snr_db": int(snr.replace("snr", "").replace("dB", "")),
                    "condition": cond,
                    "n_samples": len(case["mix_4ch"]),
                    **res
                }
                results.append(row)
                if count % 15 == 0 or count == total:
                    elapsed = time.time() - t_start
                    print(f"[{count:3d}/{total:3d}] {row['case_id']:20s} | Se: {row['sensitivity']*100:5.1f}% | PPV: {row['ppv']*100:5.1f}% | F1: {row['f1']*100:5.1f}% | M_FP: {row['m_fp']:3d} | FHR Err: {row['fhr_error_bpm']:4.1f} bpm | Elapsed: {elapsed:.1f}s")

    # Write results to CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id", "sub_id", "snr", "snr_db", "condition", "n_samples",
        "pc_selected", "weights_q15", "maternal_suppression_db",
        "n_ref_fetal", "n_ref_maternal", "n_det_beats",
        "tp", "fp", "fn", "m_fp", "maternal_false_alarm_rate",
        "sensitivity", "ppv", "f1", "gt_fhr_bpm", "det_fhr_bpm", "fhr_error_bpm"
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print("-" * 80)
    print(f"Completed {total} cases in {time.time() - t_start:.2f} s")
    print(f"Saved results to: {OUT_CSV}")

    # Summary statistics
    se_list = [r["sensitivity"] for r in results]
    ppv_list = [r["ppv"] for r in results]
    f1_list = [r["f1"] for r in results]
    err_list = [r["fhr_error_bpm"] for r in results if r["fhr_error_bpm"] is not None]
    m_fp_total = sum(r["m_fp"] for r in results)
    fp_total = sum(r["fp"] for r in results)
    tp_total = sum(r["tp"] for r in results)
    fn_total = sum(r["fn"] for r in results)

    print("\nOVERALL MACRO SUMMARY (150 CASES):")
    print(f"  Mean Sensitivity: {np.mean(se_list)*100:.2f}% +- {np.std(se_list)*100:.2f}%")
    print(f"  Mean PPV:         {np.mean(ppv_list)*100:.2f}% +- {np.std(ppv_list)*100:.2f}%")
    print(f"  Mean F1 Score:    {np.mean(f1_list)*100:.2f}% +- {np.std(f1_list)*100:.2f}%")
    print(f"  Mean FHR Error:   {np.mean(err_list):.2f} +- {np.std(err_list):.2f} bpm (Median: {np.median(err_list):.2f} bpm)")
    print(f"  Total TP: {tp_total}, FP: {fp_total}, FN: {fn_total}, M_FP: {m_fp_total} ({m_fp_total/fp_total*100:.1f}% of all FP)")

if __name__ == "__main__":
    main()
