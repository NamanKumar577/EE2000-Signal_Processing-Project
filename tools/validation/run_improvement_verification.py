"""
tools/validation/run_improvement_verification.py
──────────────────────────────────────────────────────────────────────────────
Phase 12: Prioritized Improvement Plan and Experimental Verification.
Implements and tests 3 concrete improvements on the challenging/problematic cohort
(sub04, sub08, sub09, and condition c4):
  1. Baseline: Standard causal pipeline (static PC3, 8-30 Hz BP, 200 ms refractory).
  2. Improvement 1: Optimized Spectral Tuning (12-35 Hz Bandpass, 120 ms MWI).
  3. Improvement 2: Autonomous Periodicity Scoring (periodic_rr rule on calibration).
  4. Improvement 3: Search-Back Detection with Dynamic Refractory Blanking.
  5. Combined Pipeline: Integrating all three improvements.

Outputs:
  - validation/improvements/ALGORITHM_COMPARISON.csv
  - validation/improvements/IMPROVEMENT_REPORT.md
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
import numpy as np
import wfdb
from scipy.signal import sosfilt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, CausalConfig, DEFAULT_CONFIG, run_causal,
    preprocess_causal, detect_causal, moving_sum_trailing, det_sos
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr

IMPROVE_DIR = PROJECT_ROOT / "validation" / "improvements"
IMPROVE_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
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

def detect_with_searchback(fecg: np.ndarray, cfg: CausalConfig = DEFAULT_CONFIG) -> np.ndarray:
    """Causal detector enhanced with search-back thresholding and dynamic refractory."""
    x = np.asarray(fecg, dtype=np.float64)
    n = len(x)
    warm = cfg.warmup
    if n < warm + 4:
        return np.array([], dtype=int)

    x_bp = sosfilt(det_sos(cfg), x)
    x_int = moving_sum_trailing(x_bp * x_bp, cfg.mwi_len)

    peak = float(np.max(x_int[:warm]))
    noise = float(np.mean(x_int[:warm]))
    if peak <= noise:
        return np.array([], dtype=int)

    a, b, c = x_int[:-2], x_int[1:-1], x_int[2:]
    cand = np.nonzero((a < b) & (b >= c))[0] + 1
    cand = cand[cand >= warm - 1]

    gain = 2.0 ** -cfg.level_shift
    abs_bp = np.abs(x_bp)
    raw_peaks = []
    last_m = -(10 ** 9)
    rr_avg = 100  # Default 150 bpm (100 samples)

    for m in cand:
        v = x_int[m]
        thr = 0.25 * peak + 0.75 * noise
        
        # Dynamic refractory: if running RR is short, reduce refractory from 50 to 40 (160 ms)
        dyn_refractory = 40 if rr_avg < 90 else cfg.refractory

        # Primary threshold test
        if v > thr:
            if m - last_m >= dyn_refractory:
                n_decl = m + 1
                lo = max(0, n_decl - (cfg.loc_window - 1))
                r = lo + int(np.argmax(abs_bp[lo:n_decl + 1]))
                raw_peaks.append(r)
                if last_m > 0:
                    rr_avg = 0.8 * rr_avg + 0.2 * (m - last_m)
                last_m = m
                peak += (v - peak) * gain
        # Search-back secondary test: if no beat declared for 1.5x expected RR interval
        elif (m - last_m) > 1.5 * rr_avg and v > (0.5 * thr):
            if m - last_m >= dyn_refractory:
                n_decl = m + 1
                lo = max(0, n_decl - (cfg.loc_window - 1))
                r = lo + int(np.argmax(abs_bp[lo:n_decl + 1]))
                raw_peaks.append(r)
                rr_avg = 0.8 * rr_avg + 0.2 * (m - last_m)
                last_m = m
                peak += (v - peak) * gain * 0.5
        else:
            noise += (v - noise) * gain

    raw = np.array(raw_peaks, dtype=int)
    lat = cfg.latency()
    return np.maximum(raw - lat, 0)

def main():
    print("=" * 70)
    print("STARTING PHASE 12: PRIORITIZED IMPROVEMENT VERIFICATION")
    print("=" * 70)

    # Focus test on the problematic failure cases identified in Phase 11:
    test_cases = [
        ("sub04", "snr06dB", "c0"),  # Severe MECG breakthrough
        ("sub04", "snr00dB", "c0"),
        ("sub08", "snr06dB", "c0"),  # Orthogonal lead field
        ("sub08", "snr00dB", "c0"),
        ("sub09", "snr06dB", "c0"),  # Low amplitude
        ("sub09", "snr00dB", "c0"),
        ("sub01", "snr06dB", "c4"),  # Ectopic arrhythmia
        ("sub06", "snr06dB", "c4"),
        ("sub10", "snr06dB", "c4"),
        ("sub01", "snr06dB", "c2"),  # Dynamic FHR acceleration
    ]

    pipeline_variants = [
        ("Baseline", "Baseline Causal Pipeline (Static PC3, 8-30Hz BP, 80ms MWI, 200ms Refractory)"),
        ("Imp1_Spectral_Tuning", "Imp 1: Optimized Spectral Tuning (12-35Hz BP, 120ms MWI)"),
        ("Imp2_Periodic_RR", "Imp 2: Autonomous Periodicity Scoring (periodic_rr rule)"),
        ("Imp3_Searchback_Refractory", "Imp 3: Dual-Threshold Search-Back + Dynamic Refractory"),
        ("Combined_Enhanced", "Combined: Imp 1 (Spectral) + Imp 2 (Periodicity) + Imp 3 (Search-Back)")
    ]

    results_by_variant = {k: [] for k, _ in pipeline_variants}
    row_records = []

    for sub, snr, cond in test_cases:
        rec_id = f"{sub}_{snr}_{cond}"
        mix, ref = load_case(sub, snr, cond)
        bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=10)
        
        # 1. Baseline
        j_base, _ = bank.select("pc3")
        w_base = bank.weights(j_base)
        fecg_base, det_base = run_causal(mix, w_base, DEFAULT_CONFIG)
        m_base = compute_beat_metrics(ref, det_base.peaks, fs=FS)
        fc_base = compare_fhr(compute_fhr(det_base.peaks, fs=FS), ref, fs=FS)
        results_by_variant["Baseline"].append({"f1": m_base.f1 or 0.0, "mae": fc_base.mean_abs_error_bpm or 999.0})
        row_records.append({
            "record": rec_id,
            "pipeline_variant": "Baseline",
            "f1": round((m_base.f1 or 0.0) * 100, 2),
            "fhr_mae_bpm": round(fc_base.mean_abs_error_bpm or 999.0, 2),
            "sensitivity": round((m_base.sensitivity or 0.0) * 100, 2),
            "ppv": round((m_base.ppv or 0.0) * 100, 2)
        })

        # 2. Imp 1: Spectral Tuning (12-35 Hz BP, 30-sample MWI)
        cfg_imp1 = CausalConfig(det_low_hz=12.0, det_high_hz=35.0, mwi_len=30)
        fecg_imp1, det_imp1 = run_causal(mix, w_base, cfg_imp1)
        m_imp1 = compute_beat_metrics(ref, det_imp1.peaks, fs=FS)
        fc_imp1 = compare_fhr(compute_fhr(det_imp1.peaks, fs=FS), ref, fs=FS)
        results_by_variant["Imp1_Spectral_Tuning"].append({"f1": m_imp1.f1 or 0.0, "mae": fc_imp1.mean_abs_error_bpm or 999.0})
        row_records.append({
            "record": rec_id,
            "pipeline_variant": "Imp1_Spectral_Tuning",
            "f1": round((m_imp1.f1 or 0.0) * 100, 2),
            "fhr_mae_bpm": round(fc_imp1.mean_abs_error_bpm or 999.0, 2),
            "sensitivity": round((m_imp1.sensitivity or 0.0) * 100, 2),
            "ppv": round((m_imp1.ppv or 0.0) * 100, 2)
        })

        # 3. Imp 2: Autonomous Periodicity Selection (periodic_rr)
        j_imp2, _ = bank.select("periodic_rr")
        w_imp2 = bank.weights(j_imp2)
        fecg_imp2, det_imp2 = run_causal(mix, w_imp2, DEFAULT_CONFIG)
        m_imp2 = compute_beat_metrics(ref, det_imp2.peaks, fs=FS)
        fc_imp2 = compare_fhr(compute_fhr(det_imp2.peaks, fs=FS), ref, fs=FS)
        results_by_variant["Imp2_Periodic_RR"].append({"f1": m_imp2.f1 or 0.0, "mae": fc_imp2.mean_abs_error_bpm or 999.0})
        row_records.append({
            "record": rec_id,
            "pipeline_variant": "Imp2_Periodic_RR",
            "f1": round((m_imp2.f1 or 0.0) * 100, 2),
            "fhr_mae_bpm": round(fc_imp2.mean_abs_error_bpm or 999.0, 2),
            "sensitivity": round((m_imp2.sensitivity or 0.0) * 100, 2),
            "ppv": round((m_imp2.ppv or 0.0) * 100, 2)
        })

        # 4. Imp 3: Search-Back + Dynamic Refractory
        fecg_imp3 = preprocess_causal(mix @ w_base, DEFAULT_CONFIG)
        peaks_imp3 = detect_with_searchback(fecg_imp3, DEFAULT_CONFIG)
        m_imp3 = compute_beat_metrics(ref, peaks_imp3, fs=FS)
        fc_imp3 = compare_fhr(compute_fhr(peaks_imp3, fs=FS), ref, fs=FS)
        results_by_variant["Imp3_Searchback_Refractory"].append({"f1": m_imp3.f1 or 0.0, "mae": fc_imp3.mean_abs_error_bpm or 999.0})
        row_records.append({
            "record": rec_id,
            "pipeline_variant": "Imp3_Searchback_Refractory",
            "f1": round((m_imp3.f1 or 0.0) * 100, 2),
            "fhr_mae_bpm": round(fc_imp3.mean_abs_error_bpm or 999.0, 2),
            "sensitivity": round((m_imp3.sensitivity or 0.0) * 100, 2),
            "ppv": round((m_imp3.ppv or 0.0) * 100, 2)
        })

        # 5. Combined: Imp 1 + Imp 2 + Imp 3
        bank_comb = CalibrationBank(mix, cfg_imp1, cal_seconds=10)
        j_comb, _ = bank_comb.select("periodic_rr")
        w_comb = bank_comb.weights(j_comb)
        fecg_comb = preprocess_causal(mix @ w_comb, cfg_imp1)
        peaks_comb = detect_with_searchback(fecg_comb, cfg_imp1)
        m_comb = compute_beat_metrics(ref, peaks_comb, fs=FS)
        fc_comb = compare_fhr(compute_fhr(peaks_comb, fs=FS), ref, fs=FS)
        results_by_variant["Combined_Enhanced"].append({"f1": m_comb.f1 or 0.0, "mae": fc_comb.mean_abs_error_bpm or 999.0})
        row_records.append({
            "record": rec_id,
            "pipeline_variant": "Combined_Enhanced",
            "f1": round((m_comb.f1 or 0.0) * 100, 2),
            "fhr_mae_bpm": round(fc_comb.mean_abs_error_bpm or 999.0, 2),
            "sensitivity": round((m_comb.sensitivity or 0.0) * 100, 2),
            "ppv": round((m_comb.ppv or 0.0) * 100, 2)
        })

    # Save ALGORITHM_COMPARISON.csv
    csv_path = IMPROVE_DIR / "ALGORITHM_COMPARISON.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w_csv = csv.DictWriter(f, fieldnames=list(row_records[0].keys()))
        w_csv.writeheader()
        w_csv.writerows(row_records)
    print(f"Written: {csv_path}")

    # Print Summary Table
    print("\n=== CANDIDATE IMPROVEMENT VERIFICATION (CHALLENGING COHORT) ===")
    base_mean_f1 = np.mean([x["f1"] for x in results_by_variant["Baseline"]]) * 100
    base_mean_mae = np.mean([x["mae"] for x in results_by_variant["Baseline"] if x["mae"] < 500])

    for k, desc in pipeline_variants:
        f1_vals = [x["f1"] for x in results_by_variant[k]]
        mae_vals = [x["mae"] for x in results_by_variant[k] if x["mae"] < 500]
        mean_f1 = np.mean(f1_vals) * 100
        mean_mae = np.mean(mae_vals)
        delta_f1 = mean_f1 - base_mean_f1
        delta_mae = mean_mae - base_mean_mae
        print(f"  {k:28s}: F1 = {mean_f1:6.2f}% ({delta_f1:+5.2f}%), FHR MAE = {mean_mae:5.2f} bpm ({delta_mae:+5.2f} bpm)")

if __name__ == "__main__":
    main()
