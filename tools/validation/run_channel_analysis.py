"""
tools/validation/run_channel_analysis.py
──────────────────────────────────────────────────────────────────────────────
Phase 3: Channel Configuration and Spatial Weight Robustness.
Executes:
  1. Channel Ablation:
     - 4-channel baseline [27, 26, 28, 25]
     - Single channels [27], [26], [28], [25]
     - All 2-channel pairs (6 combinations)
     - All 3-channel triplets (4 combinations)
     - Channel permutations
     - Fault injection: zero drop, rail saturation, high noise, baseline drift
  2. Weight Sensitivity and Stability:
     - Weight perturbations (+-1%, +-5%, +-10%, +-20% noise)
     - Weight quantization (16-bit, 12-bit, 8-bit, 4-bit)
     - Calibration window length sweep (3s, 5s, 10s, 30s, 60s, full)
     - Cross-subject weight transfer (sub01 weights tested on sub02..sub10)
     - Temporal non-stationarity in condition c1 (motion)

Outputs:
  - validation/channels/CHANNEL_ABLATION_RESULTS.csv
  - validation/channels/WEIGHT_ROBUSTNESS_RESULTS.csv
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from itertools import combinations
import numpy as np
import wfdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, DEFAULT_CONFIG, run_causal
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
CH_DIR = PROJECT_ROOT / "validation" / "channels"
CH_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS_BASE = [27, 26, 28, 25]

def load_case_raw(sub: str, snr: str, cond: str):
    base_path = str(DATA_DIR / sub / snr / f"{sub}_{snr}_l1_{cond}")
    fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal
    mecg = wfdb.rdrecord(base_path + "_mecg").p_signal
    n1 = wfdb.rdrecord(base_path + "_noise1").p_signal
    n2 = wfdb.rdrecord(base_path + "_noise2").p_signal
    mix = mecg + fecg + n1 + n2
    ref = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)
    return mix, ref

def eval_stream(X_filt_or_raw, w, ref, fs=250):
    fecg, det_res = run_causal(X_filt_or_raw, w)
    m = compute_beat_metrics(ref, det_res.peaks, fs=fs)
    fc = compare_fhr(compute_fhr(det_res.peaks, fs=fs), ref, fs=fs)
    f1 = m.f1 or 0.0
    mae = fc.mean_abs_error_bpm if not np.isnan(fc.mean_abs_error_bpm) else 999.0
    return {
        "f1": round(f1 * 100, 2),
        "mae": round(mae, 2),
        "tp": m.tp,
        "fp": m.fp,
        "fn": m.fn,
        "sens": round((m.sensitivity or 0.0) * 100, 2),
        "ppv": round((m.ppv or 0.0) * 100, 2)
    }

def main():
    print("=" * 70)
    print("STARTING PHASE 3: CHANNEL ABLATION & WEIGHT ROBUSTNESS")
    print("=" * 70)

    fs = 250
    test_records = [
        ("sub01", "snr12dB", "c0"),
        ("sub01", "snr06dB", "c0"),
        ("sub01", "snr00dB", "c0"),
        ("sub01", "snr06dB", "c1"),
        ("sub06", "snr06dB", "c0"),
        ("sub04", "snr06dB", "c0"),
    ]

    # =========================================================================
    # PART 1: CHANNEL ABLATION
    # =========================================================================
    print("\n--- Running Part 1: Channel Ablation ---")
    ablation_rows = []

    for sub, snr, cond in test_records:
        rec_id = f"{sub}_{snr}_{cond}"
        mix_all, ref = load_case_raw(sub, snr, cond)

        # 1. 4-Channel Baseline [27, 26, 28, 25]
        x4 = mix_all[:, CHANNELS_BASE]
        bank4 = CalibrationBank(x4, DEFAULT_CONFIG, cal_seconds=0)
        j4, _ = bank4.select("pc3")
        w4 = bank4.weights(j4)
        res4 = eval_stream(x4, w4, ref, fs)
        ablation_rows.append({
            "test_group": "baseline",
            "configuration": "4-channel [27,26,28,25]",
            "record": rec_id,
            "n_channels": 4,
            **res4
        })

        # 2. Single channels (weight = 1.0)
        for ch in CHANNELS_BASE:
            x1 = mix_all[:, [ch]]
            res1 = eval_stream(x1, np.array([1.0]), ref, fs)
            ablation_rows.append({
                "test_group": "single_channel",
                "configuration": f"lead_{ch}",
                "record": rec_id,
                "n_channels": 1,
                **res1
            })

        # 3. All pairs of 4 channels
        for pair in combinations(CHANNELS_BASE, 2):
            x2 = mix_all[:, list(pair)]
            bank2 = CalibrationBank(x2, DEFAULT_CONFIG, cal_seconds=0)
            # For 2 channels, try PC2 (PC1 is maternal)
            j2, _ = bank2.select("pc2")
            w2 = bank2.weights(j2)
            res2 = eval_stream(x2, w2, ref, fs)
            ablation_rows.append({
                "test_group": "pair",
                "configuration": f"pair_{pair[0]}_{pair[1]}",
                "record": rec_id,
                "n_channels": 2,
                **res2
            })

        # 4. All triplets of 4 channels
        for trip in combinations(CHANNELS_BASE, 3):
            x3 = mix_all[:, list(trip)]
            bank3 = CalibrationBank(x3, DEFAULT_CONFIG, cal_seconds=0)
            j3, _ = bank3.select("pc3")
            w3 = bank3.weights(j3)
            res3 = eval_stream(x3, w3, ref, fs)
            ablation_rows.append({
                "test_group": "triplet",
                "configuration": f"triplet_{trip[0]}_{trip[1]}_{trip[2]}",
                "record": rec_id,
                "n_channels": 3,
                **res3
            })

        # 5. Permutations
        perm = [25, 28, 26, 27]
        xp = mix_all[:, perm]
        bank_p = CalibrationBank(xp, DEFAULT_CONFIG, cal_seconds=0)
        jp, _ = bank_p.select("pc3")
        wp = bank_p.weights(jp)
        resp = eval_stream(xp, wp, ref, fs)
        ablation_rows.append({
            "test_group": "permutation",
            "configuration": "reversed [25,28,26,27]",
            "record": rec_id,
            "n_channels": 4,
            **resp
        })

        # 6. Fault Injections on Lead 27
        # 6a. Zero drop
        x_zero = x4.copy()
        x_zero[:, 0] = 0.0
        res_zero = eval_stream(x_zero, w4, ref, fs)
        ablation_rows.append({
            "test_group": "fault_injection",
            "configuration": "lead_27_zero_disconnect",
            "record": rec_id,
            "n_channels": 4,
            **res_zero
        })

        # 6b. Rail Saturation (+5.0 mV)
        x_sat = x4.copy()
        x_sat[:, 0] = 5.0
        res_sat = eval_stream(x_sat, w4, ref, fs)
        ablation_rows.append({
            "test_group": "fault_injection",
            "configuration": "lead_27_rail_saturation",
            "record": rec_id,
            "n_channels": 4,
            **res_sat
        })

        # 6c. High Noise on Lead 27 (1 mV RMS Gaussian noise)
        x_noise = x4.copy()
        np.random.seed(42)
        x_noise[:, 0] += np.random.normal(0, 1.0, len(x_noise))
        res_noise = eval_stream(x_noise, w4, ref, fs)
        ablation_rows.append({
            "test_group": "fault_injection",
            "configuration": "lead_27_high_noise_1mV",
            "record": rec_id,
            "n_channels": 4,
            **res_noise
        })

        # 6d. Baseline Drift on Lead 27 (0.1 Hz sine wave, 2.0 mV peak)
        t = np.arange(len(x4)) / fs
        x_drift = x4.copy()
        x_drift[:, 0] += 2.0 * np.sin(2 * np.pi * 0.1 * t)
        res_drift = eval_stream(x_drift, w4, ref, fs)
        ablation_rows.append({
            "test_group": "fault_injection",
            "configuration": "lead_27_baseline_drift_0.1Hz",
            "record": rec_id,
            "n_channels": 4,
            **res_drift
        })

    with open(CH_DIR / "CHANNEL_ABLATION_RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ablation_rows[0].keys()))
        w.writeheader()
        w.writerows(ablation_rows)
    print(f"Written: {CH_DIR / 'CHANNEL_ABLATION_RESULTS.csv'}")

    # =========================================================================
    # PART 2: WEIGHT SENSITIVITY & STABILITY
    # =========================================================================
    print("\n--- Running Part 2: Weight Robustness ---")
    robust_rows = []

    for sub, snr, cond in test_records:
        rec_id = f"{sub}_{snr}_{cond}"
        mix_all, ref = load_case_raw(sub, snr, cond)
        x4 = mix_all[:, CHANNELS_BASE]
        bank = CalibrationBank(x4, DEFAULT_CONFIG, cal_seconds=0)
        j_orig, _ = bank.select("pc3")
        w_orig = bank.weights(j_orig)

        # Baseline
        res_base = eval_stream(x4, w_orig, ref, fs)
        robust_rows.append({
            "test_group": "weight_baseline",
            "experiment": "unperturbed_float",
            "record": rec_id,
            "param_val": "16-bit float",
            **res_base
        })

        # 1. Perturbations
        for pct in [1, 5, 10, 20]:
            np.random.seed(100 + pct)
            noise_vec = np.random.normal(0, pct / 100.0, size=len(w_orig))
            w_pert = w_orig * (1.0 + noise_vec)
            w_pert /= np.linalg.norm(w_pert)
            res_p = eval_stream(x4, w_pert, ref, fs)
            robust_rows.append({
                "test_group": "perturbation",
                "experiment": f"noise_{pct}pct",
                "record": rec_id,
                "param_val": f"{pct}%",
                **res_p
            })

        # 2. Weight Quantization
        for bits in [16, 12, 8, 4]:
            q_scale = (1 << (bits - 1)) - 1
            w_quant = np.clip(np.round(w_orig * q_scale), -q_scale, q_scale) / q_scale
            res_q = eval_stream(x4, w_quant, ref, fs)
            robust_rows.append({
                "test_group": "quantization",
                "experiment": f"quant_{bits}bit",
                "record": rec_id,
                "param_val": f"{bits} bits",
                **res_q
            })

        # 3. Calibration Window Length Sweep
        for cal_s in [3, 5, 10, 30, 60, 0]:
            bank_win = CalibrationBank(x4, DEFAULT_CONFIG, cal_seconds=cal_s)
            j_win, _ = bank_win.select("pc3")
            w_win = bank_win.weights(j_win)
            res_win = eval_stream(x4, w_win, ref, fs)
            robust_rows.append({
                "test_group": "calibration_window",
                "experiment": f"cal_{cal_s}s" if cal_s > 0 else "cal_full_record",
                "record": rec_id,
                "param_val": f"{cal_s}s" if cal_s > 0 else "300s",
                **res_win
            })

    # 4. Cross-Subject Weight Transfer
    print("Testing Cross-Subject Weight Transfer...")
    mix_sub01, ref_sub01 = load_case_raw("sub01", "snr06dB", "c0")
    bank_sub01 = CalibrationBank(mix_sub01[:, CHANNELS_BASE], DEFAULT_CONFIG, cal_seconds=0)
    j_sub01, _ = bank_sub01.select("pc3")
    w_sub01 = bank_sub01.weights(j_sub01)

    for target_sub in ["sub02", "sub03", "sub04", "sub06", "sub08", "sub10"]:
        mix_tgt, ref_tgt = load_case_raw(target_sub, "snr06dB", "c0")
        x_tgt = mix_tgt[:, CHANNELS_BASE]
        
        # Native weights for target
        bank_tgt = CalibrationBank(x_tgt, DEFAULT_CONFIG, cal_seconds=0)
        j_tgt, _ = bank_tgt.select("pc3")
        w_tgt = bank_tgt.weights(j_tgt)
        res_native = eval_stream(x_tgt, w_tgt, ref_tgt, fs)
        
        # Foreign sub01 weights on target
        res_foreign = eval_stream(x_tgt, w_sub01, ref_tgt, fs)
        
        robust_rows.append({
            "test_group": "cross_subject",
            "experiment": f"sub01_weights_on_{target_sub}",
            "record": f"{target_sub}_snr06dB_c0",
            "param_val": f"Native F1: {res_native['f1']}%",
            **res_foreign
        })

    # 5. Non-Stationarity in Condition c1 (Motion)
    print("Testing Motion Non-Stationarity in Condition c1...")
    for sub in ["sub01", "sub06"]:
        mix_c1, ref_c1 = load_case_raw(sub, "snr06dB", "c1")
        x_c1 = mix_c1[:, CHANNELS_BASE]
        
        # Calibration in first 10s (t=2s to 12s)
        b_first = CalibrationBank(x_c1, DEFAULT_CONFIG, cal_seconds=10)
        j_first, _ = b_first.select("pc3")
        w_first = b_first.weights(j_first)
        
        # Middle 10s (t=145s to 155s)
        mid_slice = x_c1[145*fs:155*fs]
        b_mid = CalibrationBank(mid_slice, DEFAULT_CONFIG, cal_seconds=0)
        j_mid, _ = b_mid.select("pc3")
        w_mid = b_mid.weights(j_mid)
        
        # End 10s (t=288s to 298s)
        end_slice = x_c1[288*fs:298*fs]
        b_end = CalibrationBank(end_slice, DEFAULT_CONFIG, cal_seconds=0)
        j_end, _ = b_end.select("pc3")
        w_end = b_end.weights(j_end)
        
        cos_mid = float(np.abs(np.dot(w_first, w_mid)) / (np.linalg.norm(w_first) * np.linalg.norm(w_mid)))
        cos_end = float(np.abs(np.dot(w_first, w_end)) / (np.linalg.norm(w_first) * np.linalg.norm(w_end)))
        
        res_c1_first = eval_stream(x_c1, w_first, ref_c1, fs)
        
        robust_rows.append({
            "test_group": "motion_drift",
            "experiment": "first10s_cal_on_full_c1",
            "record": f"{sub}_snr06dB_c1",
            "param_val": f"cos_mid={cos_mid:.3f}, cos_end={cos_end:.3f}",
            **res_c1_first
        })

    with open(CH_DIR / "WEIGHT_ROBUSTNESS_RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(robust_rows[0].keys()))
        w.writeheader()
        w.writerows(robust_rows)
    print(f"Written: {CH_DIR / 'WEIGHT_ROBUSTNESS_RESULTS.csv'}")

    print("\nPhase 3 computation complete!")

if __name__ == "__main__":
    main()
