"""
tools/improvements/run_detector_improvements.py
──────────────────────────────────────────────────────────────────────────────
Priority 3: Investigate Detector Improvements.

Compares four distinct detector configurations in a 2x2 factorial design:
  Config A (Baseline):       8-30 Hz BP, MWI = 20 (80 ms),  Refractory = 200 ms (50 samples)
  Config B (Refractory 220): 8-30 Hz BP, MWI = 20 (80 ms),  Refractory = 220 ms (55 samples)
  Config C (Spectral 12-35): 12-35 Hz BP, MWI = 30 (120 ms), Refractory = 200 ms (50 samples)
  Config D (Combined):       12-35 Hz BP, MWI = 30 (120 ms), Refractory = 220 ms (55 samples)

Evaluates all 4 configurations on the exact same simulation records across:
  - Train: sub01 to sub07
  - Val:   sub08
  - Test:  sub09, sub10 (held-out)
Across layouts l1, l2, l3 (450 records).

Outputs:
  - validation/improvements/DETECTOR_COMPARISON_RESULTS.csv
  - validation/improvements/DETECTOR_IMPROVEMENTS_REPORT.md
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict
import numpy as np
import wfdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, CausalConfig, DEFAULT_CONFIG, run_causal
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "improvements"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250

CONFIGS = {
    "Config_A_Baseline": CausalConfig(det_low_hz=8.0, det_high_hz=30.0, mwi_len=20, refractory=50),
    "Config_B_Refractory220": CausalConfig(det_low_hz=8.0, det_high_hz=30.0, mwi_len=20, refractory=55),
    "Config_C_Spectral12_35": CausalConfig(det_low_hz=12.0, det_high_hz=35.0, mwi_len=30, refractory=50),
    "Config_D_Combined": CausalConfig(det_low_hz=12.0, det_high_hz=35.0, mwi_len=30, refractory=55)
}

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

def evaluate_case(args):
    sub, snr, lay, cond = args
    base_path = str(DATA_DIR / sub / snr / f"{sub}_{snr}_{lay}_{cond}")
    if not Path(base_path + "_fecg1.hea").exists():
        return None

    try:
        fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal[:, CHANNELS]
        mecg = wfdb.rdrecord(base_path + "_mecg").p_signal[:, CHANNELS]
        n1 = wfdb.rdrecord(base_path + "_noise1").p_signal[:, CHANNELS]
        n2 = wfdb.rdrecord(base_path + "_noise2").p_signal[:, CHANNELS]
        mix = fecg + mecg + n1 + n2
        ref = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)
    except Exception:
        return None

    # Derive weights once using autocorr (our verified best spatial rule) or pc3
    # Use baseline pc3 weights to test purely the detector changes!
    try:
        bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=10)
        j, _ = bank.select("pc3")
        w = bank.weights(j)
    except Exception:
        return None

    rows = []
    part = partition_of(sub)
    snr_db = int(snr[3:5])

    for cfg_name, cfg in CONFIGS.items():
        try:
            fecg_out, det_res = run_causal(mix, w, cfg)
            m = compute_beat_metrics(ref, det_res.peaks, fs=FS)
            fc = compare_fhr(compute_fhr(det_res.peaks, fs=FS), ref, fs=FS)
            
            f1 = m.f1 or 0.0
            mae = fc.mean_abs_error_bpm if not np.isnan(fc.mean_abs_error_bpm) else 999.0
            
            rows.append({
                "record": f"{sub}_{snr}_{lay}_{cond}",
                "config_name": cfg_name,
                "partition": part,
                "layout": lay,
                "sub_id": sub,
                "snr_db": snr_db,
                "condition": cond,
                "f1": round(f1 * 100, 2),
                "fhr_mae_bpm": round(mae, 2),
                "sensitivity": round((m.sensitivity or 0.0) * 100, 2),
                "ppv": round((m.ppv or 0.0) * 100, 2),
                "tp": m.tp,
                "fp": m.fp,
                "fn": m.fn
            })
        except Exception:
            continue

    return rows

def main():
    print("=" * 70)
    print("STARTING PRIORITY 3: DETECTOR PARAMETER COMPARISON (2x2 FACTORIAL)")
    print("=" * 70)

    subs = [f"sub{i:02d}" for i in range(1, 11)]
    snrs = ["snr00dB", "snr06dB", "snr12dB"]
    layouts = ["l1", "l2", "l3"]
    conditions = ["c0", "c1", "c2", "c3", "c4"]

    tasks = []
    for lay in layouts:
        for sub in subs:
            for snr in snrs:
                for cond in conditions:
                    tasks.append((sub, snr, lay, cond))

    print(f"Total simulation records in evaluation grid: {len(tasks)}")
    t0 = time.time()
    all_evals = []

    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(evaluate_case, t): t for t in tasks}
        for future in as_completed(futures):
            res = future.result()
            if res:
                all_evals.extend(res)

    print(f"Sweep complete in {time.time()-t0:.1f} s! Total evaluations generated: {len(all_evals)}")

    # Save DETECTOR_COMPARISON_RESULTS.csv
    csv_path = OUT_DIR / "DETECTOR_COMPARISON_RESULTS.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w_csv = csv.DictWriter(f, fieldnames=list(all_evals[0].keys()))
        w_csv.writeheader()
        w_csv.writerows(all_evals)
    print(f"Written: {csv_path}")

    # Summary by partition: train, val, test, all
    summary = defaultdict(lambda: defaultdict(list))
    for r in all_evals:
        cfg = r["config_name"]
        part = r["partition"]
        summary[cfg]["all_f1"].append(r["f1"])
        summary[cfg]["all_mae"].append(r["fhr_mae_bpm"])
        summary[cfg][f"{part}_f1"].append(r["f1"])
        summary[cfg][f"{part}_mae"].append(r["fhr_mae_bpm"])
        summary[cfg]["sens"].append(r["sensitivity"])
        summary[cfg]["ppv"].append(r["ppv"])

    print("\n=== DETECTOR CONFIGURATION FACTORIAL COMPARISON ===")
    print(f"{'Configuration':26s} {'Train F1':>10s} {'Val F1':>10s} {'Test F1':>10s} {'Overall F1':>12s} {'Overall MAE':>12s} {'Sens (%)':>10s} {'PPV (%)':>10s}")
    for cfg in sorted(CONFIGS.keys()):
        d = summary[cfg]
        tr_f1 = np.mean(d["train_f1"]) if d["train_f1"] else 0.0
        va_f1 = np.mean(d["val_f1"]) if d["val_f1"] else 0.0
        te_f1 = np.mean(d["test_f1"]) if d["test_f1"] else 0.0
        ov_f1 = np.mean(d["all_f1"]) if d["all_f1"] else 0.0
        ov_mae = np.mean([m for m in d["all_mae"] if m < 500]) if d["all_mae"] else 999.0
        sens = np.mean(d["sens"]) if d["sens"] else 0.0
        ppv = np.mean(d["ppv"]) if d["ppv"] else 0.0
        print(f"  {cfg:24s} {tr_f1:9.2f}% {va_f1:9.2f}% {te_f1:9.2f}% {ov_f1:11.2f}% {ov_mae:10.2f} bpm {sens:9.2f}% {ppv:9.2f}%")

if __name__ == "__main__":
    main()
