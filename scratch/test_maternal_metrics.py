#!/usr/bin/env python3
"""
scratch/test_maternal_metrics.py
──────────────────────────────────────────────────────────────────────────────
Verification script for the mathematically and clinically correct definition of:
  1. n_coincident_beats: True fetal beats overlapping maternal beats (|f - m| <= 50 ms)
  2. maternal_coincidence_rate: n_coincident_beats / max(n_fetal_ref, 1)
  3. maternal_false_detections (M_FP): Detected beats that are FP_fetal AND coincide with maternal beats
  4. maternal_false_alarm_rate: M_FP / max(n_det, 1)
  5. maternal_leakage_rate: M_FP / max(n_maternal_ref, 1)

Evaluates on:
  - SYNTHETIC_75M_140F
  - PhysioNet sub01_snr12dB_c0
  - PhysioNet sub01_snr06dB_c0
  - PhysioNet sub01_snr00dB_c0
  - PhysioNet sub04_snr06dB_c0
  - PhysioNet sub08_snr06dB_c0
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, List
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fpga_implementation.uart_host.validate_real_datasets import (
    load_fecgsyndb_case, generate_synthetic_benchmark, HostSpatialCalibrator, FS, bar
)
from src.evaluation import compute_beat_metrics, BeatMetrics


def match_beats_detailed(
    ref_samples: np.ndarray,
    det_samples: np.ndarray,
    fs: int = FS,
    tolerance_ms: float = 50.0,
) -> Dict[str, Any]:
    """
    Greedy 1-to-1 beat matching identical to src/evaluation.py, but returning
    explicit boolean masks and arrays of TP, FP, and FN events.
    """
    tol_samples = int(round(tolerance_ms * fs / 1000.0))
    ref = np.sort(ref_samples).astype(np.int64)
    det = np.sort(det_samples).astype(np.int64)

    ref_matched = np.zeros(len(ref), dtype=bool)
    det_matched = np.zeros(len(det), dtype=bool)

    for ri, r in enumerate(ref):
        best_dist = tol_samples + 1
        best_di = -1
        for di, d in enumerate(det):
            if det_matched[di]:
                continue
            dist = abs(int(r) - int(d))
            if dist <= tol_samples and dist < best_dist:
                best_dist = dist
                best_di = di
        if best_di >= 0:
            ref_matched[ri] = True
            det_matched[best_di] = True

    tp = int(np.sum(ref_matched))
    fp = int(np.sum(~det_matched))
    fn = int(np.sum(~ref_matched))

    sens = tp / (tp + fn) if (tp + fn) > 0 else None
    ppv = tp / (tp + fp) if (tp + fp) > 0 else None
    f1 = (2 * sens * ppv / (sens + ppv)) if (sens is not None and ppv is not None and (sens + ppv) > 0) else None

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "sensitivity": sens,
        "ppv": ppv,
        "f1": f1,
        "tol_samples": tol_samples,
        "ref": ref,
        "det": det,
        "ref_matched": ref_matched,
        "det_matched": det_matched,
        "tp_det": det[det_matched],
        "fp_det": det[~det_matched],
        "fn_ref": ref[~ref_matched],
    }


def compute_maternal_metrics(
    eval_f_ref: np.ndarray,
    eval_m_ref: np.ndarray,
    eval_det: np.ndarray,
    fs: int = FS,
    tolerance_ms: float = 50.0,
) -> Dict[str, Any]:
    """
    Computes rigorous clinical maternal and fetal metrics:
      - Fetal performance: TP, FP, FN, Sens, PPV, F1
      - Physiological Coincidence: n_coincident_beats, maternal_coincidence_rate
      - Maternal False Alarm: maternal_false_detections (M_FP), maternal_false_alarm_rate
      - Maternal Leakage: maternal_leakage_rate
      - Old flawed metric: bm_maternal.sensitivity
    """
    tol_samples = int(round(tolerance_ms * fs / 1000.0))
    f_match = match_beats_detailed(eval_f_ref, eval_det, fs=fs, tolerance_ms=tolerance_ms)

    # 1. Physiological Coincidence between reference fetal and maternal beats
    coincident_f_mask = np.zeros(len(eval_f_ref), dtype=bool)
    if len(eval_m_ref) > 0 and len(eval_f_ref) > 0:
        for fi, f_peak in enumerate(eval_f_ref):
            if np.min(np.abs(eval_m_ref - f_peak)) <= tol_samples:
                coincident_f_mask[fi] = True
    n_coincident_beats = int(np.sum(coincident_f_mask))
    maternal_coincidence_rate = n_coincident_beats / max(len(eval_f_ref), 1)

    # 2. Coincident reference fetal beats successfully detected (Sensitivity during overlap)
    coincident_tp_detected = int(np.sum(coincident_f_mask & f_match["ref_matched"]))
    coincident_sensitivity = coincident_tp_detected / max(n_coincident_beats, 1) if n_coincident_beats > 0 else 1.0

    # 3. Maternal False Detections: Detections that are NOT fetal (FP_fetal) AND coincide with maternal beat
    maternal_fp_list = []
    other_fp_list = []
    if len(eval_m_ref) > 0:
        for d in f_match["fp_det"]:
            if np.min(np.abs(eval_m_ref - d)) <= tol_samples:
                maternal_fp_list.append(d)
            else:
                other_fp_list.append(d)
    else:
        other_fp_list = list(f_match["fp_det"])

    maternal_false_detections = len(maternal_fp_list)
    other_false_detections = len(other_fp_list)

    # 4. Rates
    # False Alarm Rate: fraction of total detections that are maternal false alarms
    maternal_false_alarm_rate = maternal_false_detections / max(len(eval_det), 1)
    # Maternal Leakage Rate: fraction of maternal beats that leaked through as false alarms
    maternal_leakage_rate = maternal_false_detections / max(len(eval_m_ref), 1)

    # 5. Old flawed calculation for comparison
    bm_maternal_old = compute_beat_metrics(eval_m_ref, eval_det, fs=fs, tolerance_ms=tolerance_ms)
    old_maternal_metric = bm_maternal_old.sensitivity if bm_maternal_old.sensitivity is not None else 0.0

    return {
        "n_f_ref": len(eval_f_ref),
        "n_m_ref": len(eval_m_ref),
        "n_det": len(eval_det),
        "tp": f_match["tp"],
        "fp": f_match["fp"],
        "fn": f_match["fn"],
        "sensitivity": f_match["sensitivity"],
        "ppv": f_match["ppv"],
        "f1": f_match["f1"],
        "n_coincident_beats": n_coincident_beats,
        "maternal_coincidence_rate": maternal_coincidence_rate,
        "coincident_tp_detected": coincident_tp_detected,
        "coincident_sensitivity": coincident_sensitivity,
        "maternal_false_detections": maternal_false_detections,
        "other_false_detections": other_false_detections,
        "maternal_fp_peaks": maternal_fp_list,
        "other_fp_peaks": other_fp_list,
        "maternal_false_alarm_rate": maternal_false_alarm_rate,
        "maternal_leakage_rate": maternal_leakage_rate,
        "old_flawed_maternal_metric": old_maternal_metric,
    }


def main():
    data_dir = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
    suite = [
        generate_synthetic_benchmark(n_samples=2500),
        load_fecgsyndb_case(data_dir, "sub01", "snr12dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub01", "snr06dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub01", "snr00dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub04", "snr06dB", "c0"),
        load_fecgsyndb_case(data_dir, "sub08", "snr06dB", "c0"),
    ]

    print("=" * 120)
    print("MATERNAL FALSE ALARM METRIC AUDIT & VERIFICATION")
    print("=" * 120)

    results = []
    for case in suite:
        case_id = case["case_id"]
        mix_4ch = case["mix_4ch"]
        f_qrs = case["f_qrs"]
        m_qrs = case["m_qrs"]

        n_eval = min(len(mix_4ch), 2500)
        mix_eval = mix_4ch[:n_eval]
        f_qrs_eval = f_qrs[f_qrs < n_eval]
        m_qrs_eval = m_qrs[m_qrs < n_eval]

        x_q12 = np.clip(np.round(mix_eval), -32768, 32767).astype(np.int64)

        # Host PCA Calibration
        calibrator = HostSpatialCalibrator()
        w_q15, pc_idx, conf_score, _ = calibrator.calibrate(mix_eval, rule="autocorr")

        # Python bit-accurate model execution
        py_res = bar.run_bit_accurate_pipeline_final(x_q12, w_q15)
        py_peaks = np.array(list(py_res.peaks), dtype=np.int64)

        # Skip warmup samples (first 512 samples)
        eval_f_ref = f_qrs_eval[f_qrs_eval >= 512]
        eval_m_ref = m_qrs_eval[m_qrs_eval >= 512]
        eval_det = py_peaks[py_peaks >= 512]

        metrics = compute_maternal_metrics(eval_f_ref, eval_m_ref, eval_det, fs=FS, tolerance_ms=50.0)
        metrics["case_id"] = case_id
        results.append(metrics)

    # Print Table
    hdr = f"{'Case ID':<20} | {'N_f':<4} | {'N_m':<4} | {'N_det':<5} | {'TP':<3} | {'FP':<3} | {'N_coinc':<7} | {'Coinc%':<7} | {'M_FP':<4} | {'Other_FP':<8} | {'Correct FAR':<11} | {'Old Flawed':<10}"
    print(hdr)
    print("-" * len(hdr))

    for r in results:
        print(
            f"{r['case_id']:<20} | "
            f"{r['n_f_ref']:<4} | "
            f"{r['n_m_ref']:<4} | "
            f"{r['n_det']:<5} | "
            f"{r['tp']:<3} | "
            f"{r['fp']:<3} | "
            f"{r['n_coincident_beats']:<7} | "
            f"{r['maternal_coincidence_rate']*100:>5.1f}% | "
            f"{r['maternal_false_detections']:<4} | "
            f"{r['other_false_detections']:<8} | "
            f"{r['maternal_false_alarm_rate']*100:>9.2f}% | "
            f"{r['old_flawed_maternal_metric']*100:>8.2f}%"
        )
    print("=" * 120)

    # Detailed Analysis of False Positives
    print("\nDETAILED ANALYSIS OF FALSE POSITIVES & COINCIDENCE:")
    for r in results:
        print(f"\n--- {r['case_id']} ---")
        print(f"  Fetal Beats (Ref): {r['n_f_ref']}, Maternal Beats (Ref): {r['n_m_ref']}, Detected Beats: {r['n_det']}")
        print(f"  True Positives: {r['tp']}, False Positives (Fetal): {r['fp']}, False Negatives: {r['fn']}")
        print(f"  Physiological Coincident Beats: {r['n_coincident_beats']} / {r['n_f_ref']} ({r['maternal_coincidence_rate']*100:.1f}%)")
        print(f"  Coincident Fetal Beats Detected: {r['coincident_tp_detected']} / {r['n_coincident_beats']} ({r['coincident_sensitivity']*100:.1f}%)")
        print(f"  Maternal False Detections (M_FP): {r['maternal_false_detections']} (indices: {r['maternal_fp_peaks']})")
        print(f"  Other Noise False Detections: {r['other_false_detections']} (indices: {r['other_fp_peaks']})")
        print(f"  Correct Maternal False Alarm Rate (M_FP / N_det): {r['maternal_false_alarm_rate']*100:.2f}%")
        print(f"  Correct Maternal Leakage Rate (M_FP / N_m_ref): {r['maternal_leakage_rate']*100:.2f}%")
        print(f"  Old Flawed Metric (Sens of eval_det against m_qrs): {r['old_flawed_maternal_metric']*100:.2f}%")
        if r['fp'] == 0:
            print(f"  >> AUDIT NOTE: Since FP = 0, every detected beat was a true fetal beat. Maternal False Alarm Rate is exactly 0.0%!")
            print(f"     Old metric of {r['old_flawed_maternal_metric']*100:.1f}% was merely capturing the physiological coincidence of fetal and maternal beats.")


if __name__ == "__main__":
    main()
