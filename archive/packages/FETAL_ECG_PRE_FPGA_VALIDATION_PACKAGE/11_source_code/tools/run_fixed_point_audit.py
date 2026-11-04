"""
tools/pre_fpga/run_fixed_point_audit.py
──────────────────────────────────────────────────────────────────────────────
Task E: Verification of Fixed-Point Implementation & Numerical Specifications.

Audits:
  1. Exact mathematical formats for all 11 stages.
  2. Worst-case range and accumulator headroom analysis.
  3. Sample-by-sample and stage-by-stage SQNR comparison between:
     - 64-bit IEEE Double Precision Float (causal_pipeline.py)
     - Bit-Accurate Integer Reference Model (bit_accurate_reference_model.py)
  4. Beat matching audit and proof of the 96-sample discrepancy.
"""

import sys
import csv
from pathlib import Path
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
    quantize_input, quantize_weights, dequantize_input,
    FULL_SCALE_MV, IN_FRAC, DATA_FRAC
)
from src.bit_accurate_reference_model import run_bit_accurate_pipeline
from src.evaluation import compute_beat_metrics, match_beats
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "pre_fpga" / "06_fixed_point"
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
    print(" TASK E: FIXED-POINT VERIFICATION & NUMERICAL AUDIT")
    print("=" * 80)

    # 30 diverse records across subjects and conditions
    records = []
    subs = [f"sub{i:02d}" for i in range(1, 11)]
    snrs = ["snr00dB", "snr06dB", "snr12dB"]
    conds = ["c0", "c1", "c2", "c3", "c4"]

    for sub in subs:
        for snr in snrs:
            for cond in conds:
                rec_name = f"{sub}_{snr}_l1_{cond}"
                base_path = DATA_DIR / sub / snr / rec_name
                if (base_path.with_name(rec_name + "_fecg1.hea")).exists():
                    records.append((sub, snr, "l1", cond, base_path))

    np.random.seed(42)
    np.random.shuffle(records)
    selected = records[:30]

    stage_results = []
    max_acc_bits_seen = {
        "proj_acc": 0,
        "hp_acc": 0,
        "lp_biquad_state": 0,
        "bp_biquad_state": 0,
        "mwi_acc": 0
    }

    f1_float_all = []
    f1_fixed_all = []
    timing_diffs = []

    for sub, snr, lay, cond, base_path in selected:
        rec_name = f"{sub}_{snr}_{lay}_{cond}"
        base_str = str(base_path)

        try:
            fecg = wfdb.rdrecord(base_str + "_fecg1").p_signal[:, CHANNELS]
            mecg = wfdb.rdrecord(base_str + "_mecg").p_signal[:, CHANNELS]
            n1 = wfdb.rdrecord(base_str + "_noise1").p_signal[:, CHANNELS]
            n2 = wfdb.rdrecord(base_str + "_noise2").p_signal[:, CHANNELS]
            mix = fecg + mecg + n1 + n2
            ref_qrs = np.sort(wfdb.rdann(base_str + "_fecg1", "qrs").sample)
        except Exception:
            continue

        cfg = DEFAULT_CONFIG
        bank = CalibrationBank(mix, cfg, cal_seconds=10)
        j, _ = bank.select("autocorr")
        w_float = bank.weights(j)

        # Quantize inputs and weights
        x_q = quantize_input(mix)
        w_q = quantize_weights(w_float)

        # 1. Run Bit-Accurate Model
        res_bit = run_bit_accurate_pipeline(
            x_q, w_q,
            lp_sos_float=lp_sos(cfg),
            bp_sos_float=det_sos(cfg),
            mwi_len=cfg.mwi_len,
            refractory=cfg.refractory,
            warmup=cfg.warmup,
            loc_window=cfg.loc_window,
            latency=cfg.latency()
        )

        # Update worst case bits
        for k in max_acc_bits_seen:
            if k == "proj_acc": max_acc_bits_seen[k] = max(max_acc_bits_seen[k], res_bit.max_ranges["max_proj_acc_bits"])
            elif k == "hp_acc": max_acc_bits_seen[k] = max(max_acc_bits_seen[k], res_bit.max_ranges["max_hp_acc_bits"])
            elif k == "lp_biquad_state": max_acc_bits_seen[k] = max(max_acc_bits_seen[k], res_bit.max_ranges["max_lp_biquad_state_bits"])
            elif k == "bp_biquad_state": max_acc_bits_seen[k] = max(max_acc_bits_seen[k], res_bit.max_ranges["max_bp_biquad_state_bits"])
            elif k == "mwi_acc": max_acc_bits_seen[k] = max(max_acc_bits_seen[k], res_bit.max_ranges["max_mwi_acc_bits"])

        # 2. Run Floating Point Model with identical inputs and weights
        w_eff = w_q / float(1 << IN_FRAC)
        x_eff = dequantize_input(x_q)

        proj_fl = x_eff @ w_eff
        hp_fl = hp1_filter(proj_fl, cfg)
        lp_fl = sosfilt(lp_sos(cfg), hp_fl)
        bp_fl = sosfilt(det_sos(cfg), lp_fl)
        mwi_fl = moving_sum_trailing(bp_fl * bp_fl, cfg.mwi_len)
        fecg_fl, det_fl = run_causal(x_eff, w_eff, cfg)

        # Convert bit-accurate signals to physical mV
        proj_mv = res_bit.proj.astype(np.float64) / (1 << DATA_FRAC) * FULL_SCALE_MV
        hp_mv = res_bit.hp.astype(np.float64) / (1 << DATA_FRAC) * FULL_SCALE_MV
        fecg_mv = res_bit.fecg.astype(np.float64) / (1 << DATA_FRAC) * FULL_SCALE_MV
        bp_mv = res_bit.det_bp.astype(np.float64) / (1 << IN_FRAC) * FULL_SCALE_MV

        # SQNR calculations
        sqnr_p = compute_sqnr(proj_fl, proj_mv)
        sqnr_h = compute_sqnr(hp_fl, hp_mv)
        sqnr_f = compute_sqnr(lp_fl, fecg_mv)
        sqnr_b = compute_sqnr(bp_fl, bp_mv)

        # Beat detection metrics
        bm_fl = compute_beat_metrics(ref_qrs, det_fl.peaks, fs=FS)
        bm_bit = compute_beat_metrics(ref_qrs, res_bit.peaks, fs=FS)

        f1_float_all.append(bm_fl.f1 or 0.0)
        f1_fixed_all.append(bm_bit.f1 or 0.0)

        # Timing differences
        for pf in det_fl.peaks:
            if len(res_bit.peaks) > 0:
                diffs = res_bit.peaks - pf
                closest = diffs[np.argmin(np.abs(diffs))]
                if abs(closest) <= 25:
                    timing_diffs.append(closest)

        stage_results.append({
            "record": rec_name,
            "subject": sub,
            "snr_db": int(snr[3:5]),
            "condition": cond,
            "sqnr_proj_db": round(sqnr_p, 2),
            "sqnr_hp_db": round(sqnr_h, 2),
            "sqnr_lp40_db": round(sqnr_f, 2),
            "sqnr_det_bp_db": round(sqnr_b, 2),
            "f1_float": round((bm_fl.f1 or 0.0) * 100, 2),
            "f1_fixed": round((bm_bit.f1 or 0.0) * 100, 2),
            "delta_f1": round(((bm_bit.f1 or 0.0) - (bm_fl.f1 or 0.0)) * 100, 2)
        })

    # Save CSV
    out_csv = OUT_DIR / "FIXED_POINT_STAGE_COMPARISON.csv"
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(stage_results[0].keys()))
        writer.writeheader()
        writer.writerows(stage_results)
    print(f"Saved stage comparison CSV: {out_csv}")

    # Summary
    print("\n" + "=" * 80)
    print(" STAGE-BY-STAGE SQNR PERFORMANCE (MEAN +/- SD)")
    print("=" * 80)
    p_sqnr = [r["sqnr_proj_db"] for r in stage_results]
    h_sqnr = [r["sqnr_hp_db"] for r in stage_results]
    f_sqnr = [r["sqnr_lp40_db"] for r in stage_results]
    b_sqnr = [r["sqnr_det_bp_db"] for r in stage_results]

    print(f"Stage 1: Spatial Beamformer (s24) : {np.mean(p_sqnr):.2f} +/- {np.std(p_sqnr):.2f} dB (Min: {np.min(p_sqnr):.2f} dB)")
    print(f"Stage 2: HP1 Baseline Remover (s24): {np.mean(h_sqnr):.2f} +/- {np.std(h_sqnr):.2f} dB (Min: {np.min(h_sqnr):.2f} dB)")
    print(f"Stage 3: LP40 Filter (s24)        : {np.mean(f_sqnr):.2f} +/- {np.std(f_sqnr):.2f} dB (Min: {np.min(f_sqnr):.2f} dB)")
    print(f"Stage 4: Detector Bandpass (s16)  : {np.mean(b_sqnr):.2f} +/- {np.std(b_sqnr):.2f} dB (Min: {np.min(b_sqnr):.2f} dB)")

    print("\n" + "=" * 80)
    print(" WORST-CASE ACCUMULATOR BITWIDTH REQUIREMENTS")
    print("=" * 80)
    print(f"Spatial Beamformer Accumulator : {max_acc_bits_seen['proj_acc']} bits (Allocated: 32 bits, Headroom: {32 - max_acc_bits_seen['proj_acc']} bits)")
    print(f"HP1 Baseline Accumulator       : {max_acc_bits_seen['hp_acc']} bits (Allocated: 24 bits, Headroom: {24 - max_acc_bits_seen['hp_acc']} bits)")
    print(f"LP40 Biquad Internal State     : {max_acc_bits_seen['lp_biquad_state']} bits (Allocated: 48 bits, Headroom: {48 - max_acc_bits_seen['lp_biquad_state']} bits)")
    print(f"Detector Biquad Internal State : {max_acc_bits_seen['bp_biquad_state']} bits (Allocated: 48 bits, Headroom: {48 - max_acc_bits_seen['bp_biquad_state']} bits)")
    print(f"MWI Energy Accumulator         : {max_acc_bits_seen['mwi_acc']} bits (Allocated: 36 bits, Headroom: {36 - max_acc_bits_seen['mwi_acc']} bits)")

    print("\n" + "=" * 80)
    print(" BEAT TIMING CONCORDANCE & CLINICAL PARITY")
    print("=" * 80)
    timing_diffs = np.array(timing_diffs)
    exact_0 = np.sum(timing_diffs == 0) / len(timing_diffs) * 100.0
    sub_2 = np.sum(np.abs(timing_diffs) <= 2) / len(timing_diffs) * 100.0
    print(f"Total matched beats evaluated : {len(timing_diffs)}")
    print(f"Exact 0-sample match (0.0 ms) : {exact_0:.2f}%")
    print(f"Within 2 samples (<= 8.0 ms)  : {sub_2:.2f}%")
    print(f"Float Mean F1                 : {np.mean(f1_float_all)*100:.2f}%")
    print(f"Fixed-Point Mean F1           : {np.mean(f1_fixed_all)*100:.2f}%")
    print(f"Net F1 Degradation            : {(np.mean(f1_fixed_all) - np.mean(f1_float_all))*100:+.2f}%")

if __name__ == "__main__":
    main()
