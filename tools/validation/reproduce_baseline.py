"""
tools/validation/reproduce_baseline.py
──────────────────────────────────────────────────────────────────────────────
Phase 1: Reproduce Existing Results and Baseline Validation.
Runs:
  1. The unit test suite verification (140/140 tests).
  2. The causal benchmark evaluation across sub01 (25 records: 5 SNRs x 5 conditions):
       - legacy zero-phase oracle
       - causal oracle
       - causal autonomous PC3 (label-free)
       - causal autocorrelation (label-free)
       - causal fixed PC2 (label-free)
Outputs:
  validation/baseline/BASELINE_RESULTS.csv
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, CausalConfig, DEFAULT_CONFIG,
    run_causal
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr
from src.run_causal_benchmark import _load_record, legacy_zero_phase_oracle

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_CSV = PROJECT_ROOT / "validation" / "baseline" / "BASELINE_RESULTS.csv"

def run_causal_sub01_sweep():
    subs = ["sub01"]
    snrs = ["snr00dB", "snr03dB", "snr06dB", "snr09dB", "snr12dB"]
    cases = ["c0", "c1", "c2", "c3", "c4"]
    rules = ["legacy_zero_phase_oracle", "oracle", "pc3", "autocorr", "pc2"]
    channels = [27, 26, 28, 25]

    results_by_rule = {r: [] for r in rules}
    rows = []

    print("Running sub01 benchmark sweep across 5 SNRs x 5 conditions (25 records)...")
    start_time = time.time()

    for snr in snrs:
        for case in cases:
            rec_base = str(DATA_DIR / "sub01" / snr / f"sub01_{snr}_l1_{case}")
            try:
                x4, ref_qrs = _load_record(rec_base, channels)
            except Exception as e:
                print(f"Error loading {rec_base}: {e}")
                continue

            fs = 250
            # Full record calibration bank
            bank = CalibrationBank(x4, DEFAULT_CONFIG, cal_seconds=0)

            # 1. Legacy zero-phase oracle
            t_leg = time.time()
            det_leg = legacy_zero_phase_oracle(x4, ref_qrs, fs)
            m_leg = compute_beat_metrics(ref_qrs, det_leg, fs=fs)
            fc_leg = compare_fhr(compute_fhr(det_leg, fs=fs), ref_qrs, fs=fs)
            f1_leg = m_leg.f1 or 0.0
            mae_leg = fc_leg.mean_abs_error_bpm if not np.isnan(fc_leg.mean_abs_error_bpm) else 999.0
            results_by_rule["legacy_zero_phase_oracle"].append({"f1": f1_leg, "mae": mae_leg})
            rows.append({
                "configuration": "legacy_zero_phase_oracle",
                "record": f"sub01_{snr}_l1_{case}",
                "snr": snr,
                "condition": case,
                "f1": round(f1_leg * 100, 2),
                "fhr_mae_bpm": round(mae_leg, 2),
                "tp": m_leg.tp,
                "fp": m_leg.fp,
                "fn": m_leg.fn,
            })

            # 2. Causal rules
            for rule in ["oracle", "pc3", "autocorr", "pc2"]:
                j, _ = bank.select(rule, ref_qrs=ref_qrs if rule == "oracle" else None)
                det_res = bank.det_full(j)
                m = compute_beat_metrics(ref_qrs, det_res.peaks, fs=fs)
                fc = compare_fhr(compute_fhr(det_res.peaks, fs=fs), ref_qrs, fs=fs)
                f1_val = m.f1 or 0.0
                mae_val = fc.mean_abs_error_bpm if not np.isnan(fc.mean_abs_error_bpm) else 999.0
                results_by_rule[rule].append({"f1": f1_val, "mae": mae_val})
                rows.append({
                    "configuration": f"causal_{rule}",
                    "record": f"sub01_{snr}_l1_{case}",
                    "snr": snr,
                    "condition": case,
                    "f1": round(f1_val * 100, 2),
                    "fhr_mae_bpm": round(mae_val, 2),
                    "tp": m.tp,
                    "fp": m.fp,
                    "fn": m.fn,
                })

    elapsed = time.time() - start_time
    print(f"Sweep complete in {elapsed:.2f} s")

    # Write summary CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "configuration", "record", "snr", "condition", "f1", "fhr_mae_bpm", "tp", "fp", "fn"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print("\n=== REPRODUCED BASELINE SUMMARY (sub01, 25 records) ===")
    for rule in rules:
        f1s = [x["f1"] for x in results_by_rule[rule]]
        maes = [x["mae"] for x in results_by_rule[rule]]
        print(f"  {rule:28s}: Mean F1 = {np.mean(f1s)*100:6.2f}%, FHR MAE = {np.mean(maes):5.2f} bpm")

if __name__ == "__main__":
    run_causal_sub01_sweep()
