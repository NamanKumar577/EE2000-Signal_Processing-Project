"""
tools/improvements/run_spatial_calibration_study.py
──────────────────────────────────────────────────────────────────────────────
Priority 2: Investigate Spatial Calibration and Patient-Specific Weight Selection.

Compares label-free component selection strategies on the 4-channel spatial beamformer:
  1. Fixed PC3 (Baseline)
  2. Fixed PC2
  3. Fixed PC4
  4. Periodicity-based Selection (periodic_rr)
  5. Envelope Autocorrelation Selection (autocorr)
  6. Kurtosis-based Selection (kurtosis - selects component with sharpest sparse peaks)
  7. Spectral Fetal Ratio (energy in 15-35 Hz vs 1-10 Hz)
  8. Oracle Upper Bound (peeks at ground truth beats - theoretical limit only)

Strictly evaluates on:
  - Train Partition: sub01 to sub07
  - Validation Partition: sub08
  - Held-out Test Partition: sub09, sub10
Across layouts l1 and l2 (500 simulation records).

Outputs:
  - validation/improvements/SPATIAL_CALIBRATION_RESULTS.csv
  - validation/improvements/SPATIAL_CALIBRATION_REPORT.md
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from collections import defaultdict
from scipy.stats import kurtosis
import numpy as np
import wfdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, CausalConfig, DEFAULT_CONFIG, run_causal,
    preprocess_causal, det_sos, sosfilt
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "improvements"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250

PARTITIONS = {
    "train": {f"sub{i:02d}" for i in range(1, 8)},
    "val": {"sub08"},
    "test": {"sub09", "sub10"},
}

def partition_of(sub: str) -> str:
    for name, subs in PARTITIONS.items():
        if sub in subs:
            return name
    return "other"

def select_by_kurtosis(bank: CalibrationBank) -> int:
    """Select component with highest excess kurtosis in the 8-30 Hz detector band."""
    best_j = 2
    best_kurt = -999.0
    for j in range(4):
        # Examine bandpassed component
        sig = bank.det_full(j).x_bp
        if sig is None:
            # Recompute if not cached
            w = bank.weights(j)
            fecg = preprocess_causal(bank.Xf_full @ w)
            sig = sosfilt(det_sos(), fecg)
        k = float(kurtosis(sig[bank.cfg.warmup:]))
        if k > best_kurt:
            best_kurt = k
            best_j = j
    return best_j

def select_by_spectral_ratio(bank: CalibrationBank) -> int:
    """Select component maximizing ratio of fetal band (15-35 Hz) to maternal band (1-10 Hz)."""
    best_j = 2
    best_ratio = -999.0
    for j in range(4):
        w = bank.weights(j)
        proj = bank.Xf_full @ w
        # FFT power spectrum
        fft_vals = np.abs(np.fft.rfft(proj[bank.cfg.warmup:])) ** 2
        freqs = np.fft.rfftfreq(len(proj) - bank.cfg.warmup, d=1.0/FS)
        
        p_fetal = np.sum(fft_vals[(freqs >= 15.0) & (freqs <= 35.0)])
        p_maternal = np.sum(fft_vals[(freqs >= 1.0) & (freqs <= 10.0)])
        ratio = p_fetal / (p_maternal + 1e-12)
        if ratio > best_ratio:
            best_ratio = ratio
            best_j = j
    return best_j

def main():
    print("=" * 70)
    print("STARTING PRIORITY 2: SPATIAL CALIBRATION & COMPONENT SELECTION STUDY")
    print("=" * 70)

    subs = [f"sub{i:02d}" for i in range(1, 11)]
    snrs = ["snr00dB", "snr06dB", "snr12dB"]
    layouts = ["l1", "l2"]
    conditions = ["c0", "c1", "c2", "c3", "c4"]

    rules = ["pc3", "pc2", "pc4", "periodic_rr", "autocorr", "kurtosis", "spectral_ratio", "oracle"]
    results = []
    
    t_start = time.time()
    total_recs = 0

    for lay in layouts:
        for sub in subs:
            part = partition_of(sub)
            for snr in snrs:
                snr_db = int(snr[3:5])
                for cond in conditions:
                    rec_name = f"{sub}_{snr}_{lay}_{cond}"
                    base_path = str(DATA_DIR / sub / snr / rec_name)
                    if not Path(base_path + "_fecg1.hea").exists():
                        continue

                    try:
                        fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal[:, CHANNELS]
                        mecg = wfdb.rdrecord(base_path + "_mecg").p_signal[:, CHANNELS]
                        n1 = wfdb.rdrecord(base_path + "_noise1").p_signal[:, CHANNELS]
                        n2 = wfdb.rdrecord(base_path + "_noise2").p_signal[:, CHANNELS]
                        mix = fecg + mecg + n1 + n2
                        ref = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)
                    except Exception:
                        continue

                    # Calibration bank
                    bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=10)

                    for rule in rules:
                        if rule in ("pc1", "pc2", "pc3", "pc4", "periodic_rr", "autocorr"):
                            j, _ = bank.select(rule)
                        elif rule == "oracle":
                            j, _ = bank.select("oracle", ref_qrs=ref)
                        elif rule == "kurtosis":
                            j = select_by_kurtosis(bank)
                        elif rule == "spectral_ratio":
                            j = select_by_spectral_ratio(bank)
                            
                        w = bank.weights(j)
                        fecg_out, det_res = run_causal(mix, w, DEFAULT_CONFIG)
                        m = compute_beat_metrics(ref, det_res.peaks, fs=FS)
                        fc = compare_fhr(compute_fhr(det_res.peaks, fs=FS), ref, fs=FS)
                        
                        f1 = m.f1 or 0.0
                        mae = fc.mean_abs_error_bpm if not np.isnan(fc.mean_abs_error_bpm) else 999.0
                        
                        results.append({
                            "record": rec_name,
                            "partition": part,
                            "layout": lay,
                            "sub_id": sub,
                            "snr_db": snr_db,
                            "condition": cond,
                            "rule": rule,
                            "is_label_free": rule != "oracle",
                            "selected_pc": j + 1,
                            "f1": round(f1 * 100, 2),
                            "fhr_mae_bpm": round(mae, 2),
                            "sensitivity": round((m.sensitivity or 0.0) * 100, 2),
                            "ppv": round((m.ppv or 0.0) * 100, 2),
                            "tp": m.tp,
                            "fp": m.fp,
                            "fn": m.fn
                        })
                    total_recs += 1

    print(f"\nProcessed {total_recs} records in {time.time()-t_start:.1f} s!")

    # Save SPATIAL_CALIBRATION_RESULTS.csv
    csv_path = OUT_DIR / "SPATIAL_CALIBRATION_RESULTS.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(f"Written: {csv_path}")

    # Summary by partition: train, val, test, all
    summary_by_rule = defaultdict(lambda: defaultdict(list))
    for r in results:
        rule = r["rule"]
        part = r["partition"]
        summary_by_rule[rule]["all_f1"].append(r["f1"])
        summary_by_rule[rule]["all_mae"].append(r["fhr_mae_bpm"])
        summary_by_rule[rule][f"{part}_f1"].append(r["f1"])
        summary_by_rule[rule][f"{part}_mae"].append(r["fhr_mae_bpm"])

    print("\n=== SPATIAL CALIBRATION COMPONENT SELECTION COMPARISON ===")
    print(f"{'Rule':18s} {'Label-Free':>10s} {'Train F1':>10s} {'Val F1':>10s} {'Test F1':>10s} {'Overall F1':>12s} {'Overall MAE':>12s}")
    for rule in rules:
        d = summary_by_rule[rule]
        tr_f1 = np.mean(d["train_f1"]) if d["train_f1"] else 0.0
        va_f1 = np.mean(d["val_f1"]) if d["val_f1"] else 0.0
        te_f1 = np.mean(d["test_f1"]) if d["test_f1"] else 0.0
        ov_f1 = np.mean(d["all_f1"]) if d["all_f1"] else 0.0
        ov_mae = np.mean([m for m in d["all_mae"] if m < 500]) if d["all_mae"] else 999.0
        lf_str = "YES" if rule != "oracle" else "NO (Oracle)"
        print(f"  {rule:16s} {lf_str:>10s} {tr_f1:9.2f}% {va_f1:9.2f}% {te_f1:9.2f}% {ov_f1:11.2f}% {ov_mae:10.2f} bpm")

if __name__ == "__main__":
    main()
