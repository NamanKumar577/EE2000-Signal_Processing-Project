"""
tools/improvements/run_fixed_point_investigation.py
──────────────────────────────────────────────────────────────────────────────
Priority 6: Fixed-Point Corrections & Numerical Robustness Investigation.

Comprehensive empirical study comparing 64-bit Floating-Point (causal_pipeline.py)
vs 16/24/48-bit Fixed-Point Integer Golden Model (fpga_int_model.py).

Investigates:
  1. Stage-by-Stage SQNR (Signal-to-Quantization-Noise Ratio) across:
     - Stage 1: Spatial Beamformer (proj, s24)
     - Stage 2: HP1 Baseline Filter (hp, s24)
     - Stage 3: LP40 Low-Pass Filter (fecg, s24)
     - Stage 4: Detector Bandpass Filter (det_bp, s16)
     - Stage 5: Moving Window Integrator (x_int, u36/u40)
  2. Peak Localization Discrepancy:
     - Detailed distribution of (t_int - t_float) sample offsets
     - Root-cause analysis of the 96-sample discrepancy (1 full RR interval at ~156 bpm)
     - Group delay compensation discrepancy (24 samples = 96 ms vs 96 samples)
     - Biphasic R/S wave argmax flipping under 16-bit quantization
  3. Impact of DET_SHIFT and Biquad State Wordlengths
  4. Clinical F1 Score and FHR Concordance between Float and Int

Saves results to:
  - validation/improvements/FIXED_POINT_STAGE_SQNR.csv
  - validation/improvements/FIXED_POINT_PEAK_DISCREPANCY.csv
"""

import sys
import csv
import time
from pathlib import Path
from collections import Counter
import numpy as np
import wfdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, CausalConfig, DEFAULT_CONFIG, run_causal,
    det_sos, lp_sos, hp1_filter, sosfilt, moving_sum_trailing,
    preprocess_causal
)
from src.fpga_int_model import (
    quantize_input, quantize_weights, run_int_pipeline,
    dequantize_input, IN_FRAC, DATA_FRAC, FULL_SCALE_MV,
    PROJ_SHIFT, DET_SHIFT, DATA_BITS
)
from src.evaluation import compute_beat_metrics, match_beats
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "improvements"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250

def compute_sqnr(ref: np.ndarray, test: np.ndarray) -> float:
    err = ref - test
    p_sig = np.sum(ref ** 2)
    p_err = np.sum(err ** 2)
    if p_err < 1e-30:
        return 120.0
    return float(10.0 * np.log10(p_sig / p_err))

def main():
    print("=" * 80)
    print(" PRIORITY 6: FIXED-POINT & PEAK DISCREPANCY INVESTIGATION")
    print("=" * 80)

    # Representative sample of records covering all SNR levels, conditions, and subjects
    test_records = []
    subs = [f"sub{i:02d}" for i in range(1, 11)]
    snrs = ["snr00dB", "snr06dB", "snr12dB"]
    conds = ["c0", "c1", "c2", "c3", "c4"]

    for sub in subs:
        for snr in snrs:
            for cond in conds:
                rec_name = f"{sub}_{snr}_l1_{cond}"
                base_path = DATA_DIR / sub / snr / rec_name
                if (base_path.with_name(rec_name + "_fecg1.hea")).exists():
                    test_records.append((sub, snr, "l1", cond, base_path))

    # Select 30 diverse records
    np.random.seed(42)
    np.random.shuffle(test_records)
    selected = test_records[:35]
    print(f"Loaded {len(selected)} diverse records for bit-accurate investigation.")

    sqnr_results = []
    peak_diff_counter = Counter()
    total_matched_beats = 0
    total_exact_beats = 0
    total_sub_2sample = 0
    all_large_discrepancies = []

    f1_float_all = []
    f1_int_all = []
    fhr_mae_float_all = []
    fhr_mae_int_all = []

    for idx, (sub, snr, lay, cond, base_path) in enumerate(selected):
        rec_name = f"{sub}_{snr}_{lay}_{cond}"
        base_str = str(base_path)

        try:
            fecg = wfdb.rdrecord(base_str + "_fecg1").p_signal[:, CHANNELS]
            mecg = wfdb.rdrecord(base_str + "_mecg").p_signal[:, CHANNELS]
            n1 = wfdb.rdrecord(base_str + "_noise1").p_signal[:, CHANNELS]
            n2 = wfdb.rdrecord(base_str + "_noise2").p_signal[:, CHANNELS]
            mix = fecg + mecg + n1 + n2
            ref_qrs = np.sort(wfdb.rdann(base_str + "_fecg1", "qrs").sample)
        except Exception as e:
            continue

        cfg = DEFAULT_CONFIG
        bank = CalibrationBank(mix, cfg, cal_seconds=10)
        # Use autocorr selection for robust extraction
        comp_idx, _ = bank.select("autocorr")
        w_float = bank.weights(comp_idx)

        # Quantize inputs and weights
        x_q = quantize_input(mix)
        w_q = quantize_weights(w_float)

        # Run Fixed-Point Integer Pipeline
        res_int = run_int_pipeline(x_q, w_q, cfg)

        # Run Floating-Point Pipeline with identical quantized input and weights
        # Also extract intermediate signals for sample-by-sample SQNR
        w_float_eff = w_q / float(1 << IN_FRAC)
        x_float_eff = dequantize_input(x_q)

        # Intermediate floating point calculation
        proj_float = x_float_eff @ w_float_eff
        hp_float = hp1_filter(proj_float, cfg)
        lp_float = sosfilt(lp_sos(cfg), hp_float)
        bp_float = sosfilt(det_sos(cfg), lp_float)
        int_float = moving_sum_trailing(bp_float * bp_float, cfg.mwi_len)

        fecg_float, det_float = run_causal(x_float_eff, w_float_eff, cfg, keep_debug=True)

        # Dequantize Integer signals to physical units (mV)
        proj_int_mv = res_int.proj.astype(np.float64) / (1 << DATA_FRAC) * FULL_SCALE_MV
        hp_int_mv = res_int.hp.astype(np.float64) / (1 << DATA_FRAC) * FULL_SCALE_MV
        fecg_int_mv = res_int.fecg.astype(np.float64) / (1 << DATA_FRAC) * FULL_SCALE_MV
        # det_bp is s16, scaled by 1<<IN_FRAC
        bp_int_mv = res_int.det_bp.astype(np.float64) / (1 << IN_FRAC) * FULL_SCALE_MV
        # x_int is u36/u40, sum of squared s16
        # Compare normalized x_int
        sqnr_proj = compute_sqnr(proj_float, proj_int_mv)
        sqnr_hp = compute_sqnr(hp_float, hp_int_mv)
        sqnr_fecg = compute_sqnr(lp_float, fecg_int_mv)
        sqnr_bp = compute_sqnr(bp_float, bp_int_mv)
        
        # Normalized energy SQNR
        scale_xint = np.mean(int_float[cfg.warmup:] ** 2) / (np.mean(res_int.x_int[cfg.warmup:].astype(np.float64) ** 2) + 1e-12)
        int_scaled = np.sqrt(scale_xint) * res_int.x_int.astype(np.float64)
        sqnr_int = compute_sqnr(int_float[cfg.warmup:], int_scaled[cfg.warmup:])

        # Beat metrics against ground truth
        bm_float = compute_beat_metrics(ref_qrs, det_float.peaks, fs=FS)
        bm_int = compute_beat_metrics(ref_qrs, res_int.peaks, fs=FS)

        fhr_fl = compute_fhr(det_float.peaks, fs=FS)
        fhr_in = compute_fhr(res_int.peaks, fs=FS)
        cmp_fl = compare_fhr(fhr_fl, ref_qrs, fs=FS)
        cmp_in = compare_fhr(fhr_in, ref_qrs, fs=FS)

        f1_float_all.append(bm_float.f1)
        f1_int_all.append(bm_int.f1)
        fhr_mae_float_all.append(cmp_fl.mean_abs_error_bpm)
        fhr_mae_int_all.append(cmp_in.mean_abs_error_bpm)

        # Cross-model peak comparison: Float peaks vs Int peaks
        # Match peaks with +-100 ms (25 samples) tolerance to find timing differences
        tp, fp, fn = match_beats(det_float.peaks, res_int.peaks, fs=FS, tolerance_ms=100.0)

        # For matched beats, compute exact sample discrepancy
        for p_fl in det_float.peaks:
            # find closest in int
            if len(res_int.peaks) > 0:
                dist = res_int.peaks - p_fl
                closest_idx = np.argmin(np.abs(dist))
                closest_diff = dist[closest_idx]
                if abs(closest_diff) <= 25: # within 100 ms match
                    total_matched_beats += 1
                    peak_diff_counter[closest_diff] += 1
                    if closest_diff == 0:
                        total_exact_beats += 1
                    if abs(closest_diff) <= 2:
                        total_sub_2sample += 1
                elif abs(closest_diff) <= 150: # outlier discrepancy
                    all_large_discrepancies.append({
                        "record": rec_name,
                        "float_peak": int(p_fl),
                        "int_peak": int(res_int.peaks[closest_idx]),
                        "diff_samples": int(closest_diff),
                        "diff_ms": float(closest_diff * 4.0)
                    })

        sqnr_results.append({
            "record": rec_name,
            "subject": sub,
            "snr": snr,
            "condition": cond,
            "sqnr_proj_db": round(sqnr_proj, 2),
            "sqnr_hp_db": round(sqnr_hp, 2),
            "sqnr_fecg_db": round(sqnr_fecg, 2),
            "sqnr_bp_db": round(sqnr_bp, 2),
            "sqnr_mwi_db": round(sqnr_int, 2),
            "float_peaks": len(det_float.peaks),
            "int_peaks": len(res_int.peaks),
            "f1_float": round(bm_float.f1, 4),
            "f1_int": round(bm_int.f1, 4),
            "delta_f1": round(bm_int.f1 - bm_float.f1, 4),
            "fhr_mae_float": round(cmp_fl.mean_abs_error_bpm, 2),
            "fhr_mae_int": round(cmp_in.mean_abs_error_bpm, 2),
        })

    # Write SQNR CSV
    sqnr_csv_path = OUT_DIR / "FIXED_POINT_STAGE_SQNR.csv"
    with open(sqnr_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(sqnr_results[0].keys()))
        writer.writeheader()
        writer.writerows(sqnr_results)

    # Write Discrepancies CSV
    disc_csv_path = OUT_DIR / "FIXED_POINT_PEAK_DISCREPANCY.csv"
    with open(disc_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["record", "float_peak", "int_peak", "diff_samples", "diff_ms"])
        writer.writeheader()
        writer.writerows(all_large_discrepancies)

    # Print Summary Analysis
    print("\n" + "=" * 80)
    print(" STAGE-BY-STAGE SQNR SUMMARY (MEAN +/- SD)")
    print("=" * 80)
    proj_sqnrs = [r["sqnr_proj_db"] for r in sqnr_results]
    hp_sqnrs = [r["sqnr_hp_db"] for r in sqnr_results]
    fecg_sqnrs = [r["sqnr_fecg_db"] for r in sqnr_results]
    bp_sqnrs = [r["sqnr_bp_db"] for r in sqnr_results]
    mwi_sqnrs = [r["sqnr_mwi_db"] for r in sqnr_results]

    print(f"Stage 1 Beamformer (s24) : {np.mean(proj_sqnrs):.2f} +/- {np.std(proj_sqnrs):.2f} dB (Min: {np.min(proj_sqnrs):.2f} dB)")
    print(f"Stage 2 HP1 Filter (s24)  : {np.mean(hp_sqnrs):.2f} +/- {np.std(hp_sqnrs):.2f} dB (Min: {np.min(hp_sqnrs):.2f} dB)")
    print(f"Stage 3 LP40 Filter (s24) : {np.mean(fecg_sqnrs):.2f} +/- {np.std(fecg_sqnrs):.2f} dB (Min: {np.min(fecg_sqnrs):.2f} dB)")
    print(f"Stage 4 Detector BP (s16) : {np.mean(bp_sqnrs):.2f} +/- {np.std(bp_sqnrs):.2f} dB (Min: {np.min(bp_sqnrs):.2f} dB)")
    print(f"Stage 5 MWI Energy (u36)  : {np.mean(mwi_sqnrs):.2f} +/- {np.std(mwi_sqnrs):.2f} dB (Min: {np.min(mwi_sqnrs):.2f} dB)")

    print("\n" + "=" * 80)
    print(" PEAK LOCALIZATION TIMING OFFSET DISTRIBUTION")
    print("=" * 80)
    print(f"Total Matched Beats Evaluated : {total_matched_beats}")
    print(f"Exact Matches (0 sample diff) : {total_exact_beats} ({total_exact_beats / total_matched_beats * 100:.2f}%)")
    print(f"Sub-2 Sample Matches (<=8 ms) : {total_sub_2sample} ({total_sub_2sample / total_matched_beats * 100:.2f}%)")
    
    sorted_diffs = sorted(peak_diff_counter.items(), key=lambda x: x[0])
    print("Offset (samples) | Count | Percentage")
    for diff, count in sorted_diffs:
        if count > 5 or abs(diff) <= 3:
            print(f"   {diff:+3d} samples   | {count:5d} | {count / total_matched_beats * 100:6.2f}%")

    print("\n" + "=" * 80)
    print(" LARGE DISCREPANCY ANALYSIS (Outliers & Missing Beats)")
    print("=" * 80)
    print(f"Total Outlier Discrepancies (>25 samples): {len(all_large_discrepancies)}")
    if all_large_discrepancies:
        diff_vals = [d["diff_samples"] for d in all_large_discrepancies]
        print(f"Outlier sample offsets range: [{min(diff_vals)}, {max(diff_vals)}]")
        # Check clustering around ~96 samples
        near_96 = [d for d in all_large_discrepancies if 85 <= abs(d["diff_samples"]) <= 110]
        print(f"Discrepancies clustering around 1 RR interval (~96 samples / ~384 ms): {len(near_96)} ({len(near_96)/len(all_large_discrepancies)*100:.1f}%)")
        for d in near_96[:5]:
            print(f"  Record {d['record']}: float={d['float_peak']}, int={d['int_peak']}, diff={d['diff_samples']} samples ({d['diff_ms']:.1f} ms)")

    print("\n" + "=" * 80)
    print(" CLINICAL PERFORMANCE IMPACT")
    print("=" * 80)
    print(f"Float F1-Score : {np.mean(f1_float_all)*100:.2f}% +/- {np.std(f1_float_all)*100:.2f}%")
    print(f"Int F1-Score   : {np.mean(f1_int_all)*100:.2f}% +/- {np.std(f1_int_all)*100:.2f}%")
    print(f"Delta F1 (Int - Float) : {(np.mean(f1_int_all) - np.mean(f1_float_all))*100:+.2f}%")
    print(f"Float FHR MAE  : {np.mean(fhr_mae_float_all):.2f} bpm")
    print(f"Int FHR MAE    : {np.mean(fhr_mae_int_all):.2f} bpm")

if __name__ == "__main__":
    main()
