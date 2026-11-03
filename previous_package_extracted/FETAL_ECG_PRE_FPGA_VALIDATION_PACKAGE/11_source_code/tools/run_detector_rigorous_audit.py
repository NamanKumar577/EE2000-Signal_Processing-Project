"""
tools/pre_fpga/run_detector_rigorous_audit.py
──────────────────────────────────────────────────────────────────────────────
Task D: Rigorous Audit and Validation of Detector Configurations.

Compares 2x2 Factorial Grid:
  - Config A: 8–30 Hz, MWI 20 (80 ms), Refractory 200 ms
  - Config B: 8–30 Hz, MWI 20 (80 ms), Refractory 220 ms
  - Config C: 12–35 Hz, MWI 30 (120 ms), Refractory 200 ms
  - Config D: 12–35 Hz, MWI 30 (120 ms), Refractory 220 ms

Across identical records in layouts l1, l2, l3 (450 records x 4 configs = 1,800 runs).
Strict subject reporting: sub09 and sub10 isolated as held-out test subjects.
Parallel execution with ProcessPoolExecutor.
"""

import sys
import csv
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
OUT_DIR = PROJECT_ROOT / "validation" / "pre_fpga" / "05_detector_validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250

CONFIGS = {
    "Config A (8-30Hz, MWI20, Ref200)": CausalConfig(det_low_hz=8.0, det_high_hz=30.0, mwi_len=20, refractory=50),
    "Config B (8-30Hz, MWI20, Ref220)": CausalConfig(det_low_hz=8.0, det_high_hz=30.0, mwi_len=20, refractory=55),
    "Config C (12-35Hz, MWI30, Ref200)": CausalConfig(det_low_hz=12.0, det_high_hz=35.0, mwi_len=30, refractory=50),
    "Config D (12-35Hz, MWI30, Ref220)": CausalConfig(det_low_hz=12.0, det_high_hz=35.0, mwi_len=30, refractory=55),
}

PARTITIONS = {
    "train": {f"sub{i:02d}" for i in range(1, 8)},
    "val": {"sub08"},
    "test_sub09": {"sub09"},
    "test_sub10": {"sub10"},
}

def partition_of(sub: str) -> str:
    for name, subs in PARTITIONS.items():
        if sub in subs:
            return name
    return "other"

def evaluate_record_configs(args):
    sub, snr, layout, cond = args
    base_path = str(DATA_DIR / sub / snr / f"{sub}_{snr}_{layout}_{cond}")
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

    if np.isnan(mix).any():
        return None

    part = partition_of(sub)
    snr_db = int(snr[3:5])
    rec_results = []

    # Calibration is fixed to autocorr
    bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=10)
    sel_j, _ = bank.select("autocorr")
    w = bank.weights(sel_j)

    for cfg_name, cfg in CONFIGS.items():
        try:
            _, det = run_causal(mix, w, cfg)
            bm = compute_beat_metrics(ref, det.peaks, fs=FS, tolerance_ms=50.0)
            fhr = compute_fhr(det.peaks, fs=FS)
            cmp = compare_fhr(fhr, ref, fs=FS)

            f1 = bm.f1 or 0.0
            mae = cmp.mean_abs_error_bpm if not np.isnan(cmp.mean_abs_error_bpm) else 999.0

            rec_results.append({
                "record": f"{sub}_{snr}_{layout}_{cond}",
                "layout": layout,
                "subject": sub,
                "partition": part,
                "snr_db": snr_db,
                "condition": cond,
                "config": cfg_name,
                "tp": bm.tp,
                "fp": bm.fp,
                "fn": bm.fn,
                "sensitivity": round(bm.sensitivity or 0.0, 4),
                "precision": round(bm.ppv or 0.0, 4),
                "f1": round(f1 * 100, 2),
                "fhr_mae_bpm": round(mae, 2),
                "n_ref": len(ref),
                "n_det": len(det.peaks)
            })
        except Exception:
            continue

    return rec_results

def main():
    print("=" * 80)
    print(" TASK D: RIGOROUS DETECTOR CONFIGURATION AUDIT")
    print("=" * 80)

    work_items = []
    layouts = ["l1", "l2", "l3"]
    subs = [f"sub{i:02d}" for i in range(1, 11)]
    snrs = ["snr00dB", "snr06dB", "snr12dB"]
    conds = ["c0", "c1", "c2", "c3", "c4"]

    for lay in layouts:
        for sub in subs:
            for snr in snrs:
                for cond in conds:
                    work_items.append((sub, snr, lay, cond))

    total_tasks = len(work_items)
    print(f"Total records to evaluate: {total_tasks} (3 layouts x 10 subjects x 3 SNRs x 5 conditions)")

    t_start = time.time()
    all_results = []
    completed = 0

    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(evaluate_record_configs, item): item for item in work_items}
        for future in as_completed(futures):
            res = future.result()
            if res:
                all_results.extend(res)
            completed += 1
            if completed % 100 == 0 or completed == total_tasks:
                print(f"  Processed {completed}/{total_tasks} records ({time.time() - t_start:.1f} s)...")

    # Save CSV
    out_csv = OUT_DIR / "DETECTOR_CONFIGURATION_RESULTS.csv"
    with open(out_csv, "w", newline="") as f:
        fieldnames = list(all_results[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    print(f"Saved detector configuration results CSV: {out_csv} ({len(all_results)} runs)")

    # Summary by Config
    print("\n" + "=" * 95)
    print(" DETECTOR CONFIGURATION SUMMARY ACROSS PARTITIONS")
    print("=" * 95)
    print(f"{'Configuration':<34} | {'Overall F1':<10} | {'Train F1':<9} | {'Val sub08':<9} | {'Test sub09':<10} | {'Test sub10':<10} | {'FHR MAE':<8}")
    print("-" * 95)

    for cfg_name in CONFIGS.keys():
        rows = [r for r in all_results if r["config"] == cfg_name]
        f1_all = [r["f1"] for r in rows]
        f1_train = [r["f1"] for r in rows if r["partition"] == "train"]
        f1_val = [r["f1"] for r in rows if r["partition"] == "val"]
        f1_sub09 = [r["f1"] for r in rows if r["partition"] == "test_sub09"]
        f1_sub10 = [r["f1"] for r in rows if r["partition"] == "test_sub10"]
        maes = [r["fhr_mae_bpm"] for r in rows if r["fhr_mae_bpm"] < 900.0]

        print(f"{cfg_name:<34} | {np.mean(f1_all):<10.2f} | {np.mean(f1_train):<9.2f} | {np.mean(f1_val):<9.2f} | {np.mean(f1_sub09):<10.2f} | {np.mean(f1_sub10):<10.2f} | {np.mean(maes):<8.2f}")

    # Inspect Biphasic QRS split lobes (False Positives)
    print("\n" + "=" * 95)
    print(" BIPHASIC QRS FALSE POSITIVE SUPPRESSION (MWI 20 vs MWI 30)")
    print("=" * 95)
    for cfg_name in CONFIGS.keys():
        rows = [r for r in all_results if r["config"] == cfg_name]
        tot_fp = sum(r["fp"] for r in rows)
        tot_tp = sum(r["tp"] for r in rows)
        ppv = tot_tp / (tot_tp + tot_fp) * 100.0
        print(f"{cfg_name:<34} | Total False Positives: {tot_fp:6d} | Precision (PPV): {ppv:.2f}%")

if __name__ == "__main__":
    main()
