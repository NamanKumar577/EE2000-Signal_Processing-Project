"""
tools/qrs_timing_correction/evaluate_qrs_timing_correction.py
─────────────────────────────────────────────────────────────
Comprehensive Investigation and Correction of QRS Timing Compensation.

Evaluates:
  1. Causal pipeline across all 30 benchmark records (10 subjects x 3 SNRs, condition c0).
  2. Candidate compensation values: 0, 10, 11, 12, 13, 14, 18 samples.
  3. Strict 1-to-1 beat matching with standard clinical tolerance (+-50 ms / +-12 samples @ 250 Hz).
  4. Wide-window matching (+-100 ms / +-25 samples) for unclipped raw delay measurement.
  5. Per-record error distributions, histograms, and aggregate comparisons.

Outputs:
  - QRS_TIMING_CORRECTION/QRS_TIMING_RESULTS.csv
  - QRS_TIMING_CORRECTION/QRS_TIMING_PER_RECORD.csv
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import wfdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import CalibrationBank, CausalConfig
from src.bit_accurate_reference_model_final import run_bit_accurate_pipeline_final
from tools.pre_fpga_corrected.reconcile_qrs_metrics import match_beats_strict_pairs

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "QRS_TIMING_CORRECTION"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250

def run_evaluation():
    print("=" * 80)
    print(" EVALUATING QRS TIMING COMPENSATION ACROSS 30 BENCHMARK RECORDS")
    print("=" * 80)

    subs = [f"sub{i:02d}" for i in range(1, 11)]
    snrs = ["snr00dB", "snr06dB", "snr12dB"]
    cond = "c0"
    comp_candidates = [0, 6, 10, 11, 12, 13, 14, 18]

    cfg_c = CausalConfig(
        det_low_hz=12.0,
        det_high_hz=35.0,
        mwi_len=30,
        refractory=50
    )

    per_record_rows = []
    
    for sub in subs:
        for snr in snrs:
            rec_name = f"{sub}_{snr}_l1_{cond}"
            base_path = str(DATA_DIR / sub / snr / rec_name)
            if not Path(base_path + "_fecg1.hea").exists():
                print(f"Skipping missing record: {rec_name}")
                continue

            try:
                fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal[:, CHANNELS]
                mecg = wfdb.rdrecord(base_path + "_mecg").p_signal[:, CHANNELS]
                n1 = wfdb.rdrecord(base_path + "_noise1").p_signal[:, CHANNELS]
                n2 = wfdb.rdrecord(base_path + "_noise2").p_signal[:, CHANNELS]
                mix = fecg + mecg + n1 + n2
                ref_qrs = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)
            except Exception as e:
                print(f"Error loading {rec_name}: {e}")
                continue

            # Run calibration bank (10s window) to get spatial beamforming weights
            bank = CalibrationBank(mix, cfg_c, cal_seconds=10)
            j, _ = bank.select("autocorr")
            w_float = bank.weights(j)

            # Quantize to 16-bit counts
            x_q = np.clip(np.round(mix * 4096.0), -32768, 32767).astype(np.int16)
            w_q = np.clip(np.round(w_float * 32768.0), -32768, 32767).astype(np.int16)

            # Run bit-accurate pipeline with zero internal latency to get pristine raw detections
            res_fx = run_bit_accurate_pipeline_final(x_q, w_q, mwi_len=30, refractory=50, latency=0)
            raw_peaks = res_fx.raw_peaks

            # Also compute unconstrained raw delay with a wide 100 ms (25 sample) tolerance
            tp_wide, _, _, pairs_wide = match_beats_strict_pairs(ref_qrs, raw_peaks, fs=FS, tol_ms=100.0)
            unconstrained_raw_delay = float(np.mean([p[2] for p in pairs_wide])) if pairs_wide else np.nan

            for comp in comp_candidates:
                comp_peaks = np.maximum(raw_peaks - comp, 0)
                tp, fp, fn, pairs = match_beats_strict_pairs(ref_qrs, comp_peaks, fs=FS, tol_ms=50.0)

                n_ref = len(ref_qrs)
                n_det = len(comp_peaks)
                f1 = (2 * tp / (2 * tp + fp + fn)) * 100.0 if (2 * tp + fp + fn) > 0 else 0.0
                sens = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
                ppv = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0

                if len(pairs) > 0:
                    errors = np.array([p[2] for p in pairs])
                    mean_err = float(np.mean(errors))
                    mae_err = float(np.mean(np.abs(errors)))
                    median_ae = float(np.median(np.abs(errors)))
                    std_err = float(np.std(errors))
                    exact_0 = float(np.sum(errors == 0) / len(errors) * 100.0)
                    pct_le_1 = float(np.sum(np.abs(errors) <= 1) / len(errors) * 100.0)
                    pct_le_2 = float(np.sum(np.abs(errors) <= 2) / len(errors) * 100.0)
                    pct_le_3 = float(np.sum(np.abs(errors) <= 3) / len(errors) * 100.0)

                    # Distribution histogram: counts in bins
                    bin_neg_large = int(np.sum(errors < -6))
                    bin_neg_med = int(np.sum((errors >= -6) & (errors <= -3)))
                    bin_neg_small = int(np.sum((errors >= -2) & (errors <= -1)))
                    bin_zero = int(np.sum(errors == 0))
                    bin_pos_small = int(np.sum((errors >= 1) & (errors <= 2)))
                    bin_pos_med = int(np.sum((errors >= 3) & (errors <= 6)))
                    bin_pos_large = int(np.sum(errors > 6))
                else:
                    mean_err = np.nan
                    mae_err = np.nan
                    median_ae = np.nan
                    std_err = np.nan
                    exact_0 = 0.0
                    pct_le_1 = 0.0
                    pct_le_2 = 0.0
                    pct_le_3 = 0.0
                    bin_neg_large = bin_neg_med = bin_neg_small = bin_zero = bin_pos_small = bin_pos_med = bin_pos_large = 0

                per_record_rows.append({
                    "record": rec_name,
                    "subject": sub,
                    "snr_db": int(snr[3:5]),
                    "compensation_samples": comp,
                    "compensation_ms": comp * 4.0,
                    "n_ref": n_ref,
                    "n_det": n_det,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "sensitivity_pct": round(sens, 2),
                    "ppv_pct": round(ppv, 2),
                    "f1_pct": round(f1, 2),
                    "mean_timing_err_samples": round(mean_err, 3) if not np.isnan(mean_err) else np.nan,
                    "mean_timing_err_ms": round(mean_err * 4.0, 2) if not np.isnan(mean_err) else np.nan,
                    "mae_timing_err_samples": round(mae_err, 3) if not np.isnan(mae_err) else np.nan,
                    "median_ae_timing_err_samples": round(median_ae, 3) if not np.isnan(median_ae) else np.nan,
                    "std_timing_err_samples": round(std_err, 3) if not np.isnan(std_err) else np.nan,
                    "exact_0samp_pct": round(exact_0, 2),
                    "pct_within_1samp": round(pct_le_1, 2),
                    "pct_within_2samp": round(pct_le_2, 2),
                    "pct_within_3samp": round(pct_le_3, 2),
                    "unconstrained_raw_delay_samples": round(unconstrained_raw_delay, 2),
                    "count_err_le_minus7": bin_neg_large,
                    "count_err_minus6_to_minus3": bin_neg_med,
                    "count_err_minus2_to_minus1": bin_neg_small,
                    "count_err_0": bin_zero,
                    "count_err_plus1_to_plus2": bin_pos_small,
                    "count_err_plus3_to_plus6": bin_pos_med,
                    "count_err_ge_plus7": bin_pos_large
                })

            print(f"Processed {rec_name:22s} | Unconstrained Raw Delay: {unconstrained_raw_delay:5.2f} samples")

    df_per_record = pd.DataFrame(per_record_rows)
    per_record_csv = OUT_DIR / "QRS_TIMING_PER_RECORD.csv"
    df_per_record.to_csv(per_record_csv, index=False)
    print(f"\nSaved per-record CSV: {per_record_csv} ({len(df_per_record)} rows)")

    # Compute overall aggregates across all 30 records
    agg_rows = []
    for comp in comp_candidates:
        df_c = df_per_record[df_per_record["compensation_samples"] == comp]
        
        # Micro-aggregation over all matched pairs
        tot_ref = df_c["n_ref"].sum()
        tot_det = df_c["n_det"].sum()
        tot_tp = df_c["tp"].sum()
        tot_fp = df_c["fp"].sum()
        tot_fn = df_c["fn"].sum()
        micro_f1 = (2 * tot_tp / (2 * tot_tp + tot_fp + tot_fn)) * 100.0
        micro_sens = (tot_tp / (tot_tp + tot_fn)) * 100.0
        micro_ppv = (tot_tp / (tot_tp + tot_fp)) * 100.0

        macro_mean_err = df_c["mean_timing_err_samples"].mean()
        macro_mae = df_c["mae_timing_err_samples"].mean()
        macro_median_ae = df_c["median_ae_timing_err_samples"].median()
        macro_exact_0 = df_c["exact_0samp_pct"].mean()
        macro_le_1 = df_c["pct_within_1samp"].mean()
        macro_le_2 = df_c["pct_within_2samp"].mean()
        macro_le_3 = df_c["pct_within_3samp"].mean()
        macro_f1 = df_c["f1_pct"].mean()

        agg_rows.append({
            "compensation_samples": comp,
            "compensation_ms": comp * 4.0,
            "mean_timing_bias_samples": round(macro_mean_err, 3),
            "mean_timing_bias_ms": round(macro_mean_err * 4.0, 2),
            "mae_timing_err_samples": round(macro_mae, 3),
            "mae_timing_err_ms": round(macro_mae * 4.0, 2),
            "median_ae_samples": round(macro_median_ae, 3),
            "pct_within_1samp": round(macro_le_1, 2),
            "pct_within_2samp": round(macro_le_2, 2),
            "pct_within_3samp": round(macro_le_3, 2),
            "exact_0samp_pct": round(macro_exact_0, 2),
            "macro_f1_pct": round(macro_f1, 2),
            "micro_f1_pct": round(micro_f1, 2),
            "total_tp": tot_tp,
            "total_fp": tot_fp,
            "total_fn": tot_fn,
            "total_matched_pairs": tot_tp
        })

    df_agg = pd.DataFrame(agg_rows)
    agg_csv = OUT_DIR / "QRS_TIMING_RESULTS.csv"
    df_agg.to_csv(agg_csv, index=False)
    print(f"Saved aggregate CSV: {agg_csv}")

    print("\n" + "=" * 80)
    print(" OVERALL AGGREGATE QRS TIMING COMPENSATION COMPARISON")
    print("=" * 80)
    print(df_agg[["compensation_samples", "mean_timing_bias_samples", "mae_timing_err_samples", "pct_within_1samp", "pct_within_2samp", "pct_within_3samp", "macro_f1_pct", "total_tp"]].to_string(index=False))

if __name__ == "__main__":
    run_evaluation()
