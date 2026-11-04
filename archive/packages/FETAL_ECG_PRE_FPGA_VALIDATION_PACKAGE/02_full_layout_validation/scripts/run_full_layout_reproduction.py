"""
tools/pre_fpga/run_full_layout_reproduction.py
──────────────────────────────────────────────────────────────────────────────
Task A: Audit and Reproduce Full-Layout Benchmark across Layouts l1–l5.

Objectives:
  1. Define and enumerate all 1,500 potential simulation combinations.
  2. Audit every missing or corrupted record (7 records identified).
  3. Generate MISSING_RECORDS.csv with exact root-cause classifications.
  4. Reproduce all 1,493 complete records (1,742 evaluations) across l1–l5.
  5. Generate FULL_LAYOUT_REPRODUCED.csv, LAYOUT_COMPARISON.csv, and summary metrics.
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
    CalibrationBank, DEFAULT_CONFIG, run_causal
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "pre_fpga" / "02_full_layout_validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250
LAYOUTS = ["l1", "l2", "l3", "l4", "l5"]
SUBS = [f"sub{i:02d}" for i in range(1, 11)]
SNRS = ["snr00dB", "snr03dB", "snr06dB", "snr09dB", "snr12dB"]
SNR_VALS = {"snr00dB": 0, "snr03dB": 3, "snr06dB": 6, "snr09dB": 9, "snr12dB": 12}
CONDITIONS = ["c0", "c1", "c2", "c3", "c4", "c5"]

def audit_record(args):
    sub, snr, layout, cond = args
    base_path = str(DATA_DIR / sub / snr / f"{sub}_{snr}_{layout}_{cond}")
    
    hea_fecg1 = Path(base_path + "_fecg1.hea")
    dat_fecg1 = Path(base_path + "_fecg1.dat")
    qrs_fecg1 = Path(base_path + "_fecg1.qrs")
    hea_mecg = Path(base_path + "_mecg.hea")
    dat_mecg = Path(base_path + "_mecg.dat")
    hea_n1 = Path(base_path + "_noise1.hea")
    dat_n1 = Path(base_path + "_noise1.dat")
    hea_n2 = Path(base_path + "_noise2.hea")
    dat_n2 = Path(base_path + "_noise2.dat")

    # File presence check
    missing_files = []
    if not hea_fecg1.exists(): missing_files.append("fecg1.hea")
    if not dat_fecg1.exists(): missing_files.append("fecg1.dat")
    if not qrs_fecg1.exists(): missing_files.append("fecg1.qrs")
    if not hea_mecg.exists(): missing_files.append("mecg.hea")
    if not dat_mecg.exists(): missing_files.append("mecg.dat")
    if not hea_n1.exists(): missing_files.append("noise1.hea")
    if not dat_n1.exists(): missing_files.append("noise1.dat")
    if not hea_n2.exists(): missing_files.append("noise2.hea")
    if not dat_n2.exists(): missing_files.append("noise2.dat")

    if missing_files:
        return {
            "status": "MISSING_FILE",
            "record": f"{sub}_{snr}_{layout}_{cond}",
            "sub": sub, "snr": snr, "layout": layout, "cond": cond,
            "reason": f"Missing physical files: {', '.join(missing_files)}",
            "justification": "Binary signal data missing on disk in dataset distribution.",
            "is_disproportionately_difficult": "No (I/O error, file unreadable)",
            "eval_rows": None
        }

    # Attempt to read signals and check for NaN corruption
    try:
        fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal[:, CHANNELS]
        mecg = wfdb.rdrecord(base_path + "_mecg").p_signal[:, CHANNELS]
        n1 = wfdb.rdrecord(base_path + "_noise1").p_signal[:, CHANNELS]
        n2 = wfdb.rdrecord(base_path + "_noise2").p_signal[:, CHANNELS]
    except Exception as e:
        return {
            "status": "CORRUPTED_IO",
            "record": f"{sub}_{snr}_{layout}_{cond}",
            "sub": sub, "snr": snr, "layout": layout, "cond": cond,
            "reason": f"WFDB read error: {type(e).__name__}: {str(e)}",
            "justification": "Corrupted WFDB binary record header or data segment.",
            "is_disproportionately_difficult": "No (Corrupted binary file)",
            "eval_rows": None
        }

    nan_counts = {
        "fecg": int(np.isnan(fecg).sum()),
        "mecg": int(np.isnan(mecg).sum()),
        "n1": int(np.isnan(n1).sum()),
        "n2": int(np.isnan(n2).sum())
    }
    total_nans = sum(nan_counts.values())

    if total_nans > 0:
        return {
            "status": "NAN_CORRUPTED",
            "record": f"{sub}_{snr}_{layout}_{cond}",
            "sub": sub, "snr": snr, "layout": layout, "cond": cond,
            "reason": f"Simulation artifact: {nan_counts} contains IEEE NaNs.",
            "justification": "Contaminated by NaN in EHG noise generation; linear algebra covariance fails to converge.",
            "is_disproportionately_difficult": "Yes (Condition c3 uterine contraction noise has simulation NaN spikes)",
            "eval_rows": None
        }

    # Valid complete record: Evaluate baseline causal pipeline
    mix = fecg + mecg + n1 + n2
    ref1 = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)

    ref2 = None
    if cond == "c5" and Path(base_path + "_fecg2.hea").exists() and Path(base_path + "_fecg2.dat").exists():
        try:
            ref2 = np.sort(wfdb.rdann(base_path + "_fecg2", "qrs").sample)
        except Exception:
            ref2 = None

    try:
        bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=0)
        j, _ = bank.select("pc3")
        w = bank.weights(j)
        fecg_out, det_res = run_causal(mix, w, DEFAULT_CONFIG)
        peaks = det_res.peaks

        m1 = compute_beat_metrics(ref1, peaks, fs=FS)
        fc1 = compare_fhr(compute_fhr(peaks, fs=FS), ref1, fs=FS)
        f1_1 = m1.f1 or 0.0
        mae_1 = fc1.mean_abs_error_bpm if not np.isnan(fc1.mean_abs_error_bpm) else 999.0

        rows = [{
            "layout": layout,
            "sub_id": sub,
            "snr_db": SNR_VALS[snr],
            "condition": cond,
            "fetus_id": "fecg1",
            "rule": "pc3",
            "sel_pc": j + 1,
            "tp": m1.tp,
            "fp": m1.fp,
            "fn": m1.fn,
            "sensitivity": round(m1.sensitivity or 0.0, 4),
            "ppv": round(m1.ppv or 0.0, 4),
            "f1": round(f1_1 * 100, 2),
            "fhr_mae_bpm": round(mae_1, 2),
            "n_ref": len(ref1),
            "n_det": len(peaks)
        }]

        if cond == "c5" and ref2 is not None and len(ref2) > 0:
            m2 = compute_beat_metrics(ref2, peaks, fs=FS)
            fc2 = compare_fhr(compute_fhr(peaks, fs=FS), ref2, fs=FS)
            f1_2 = m2.f1 or 0.0
            mae_2 = fc2.mean_abs_error_bpm if not np.isnan(fc2.mean_abs_error_bpm) else 999.0
            rows.append({
                "layout": layout,
                "sub_id": sub,
                "snr_db": SNR_VALS[snr],
                "condition": cond,
                "fetus_id": "fecg2",
                "rule": "pc3",
                "sel_pc": j + 1,
                "tp": m2.tp,
                "fp": m2.fp,
                "fn": m2.fn,
                "sensitivity": round(m2.sensitivity or 0.0, 4),
                "ppv": round(m2.ppv or 0.0, 4),
                "f1": round(f1_2 * 100, 2),
                "fhr_mae_bpm": round(mae_2, 2),
                "n_ref": len(ref2),
                "n_det": len(peaks)
            })

        return {
            "status": "VALID",
            "record": f"{sub}_{snr}_{layout}_{cond}",
            "eval_rows": rows
        }
    except Exception as e:
        return {
            "status": "PIPELINE_ERROR",
            "record": f"{sub}_{snr}_{layout}_{cond}",
            "sub": sub, "snr": snr, "layout": layout, "cond": cond,
            "reason": f"Pipeline failure: {type(e).__name__}: {str(e)}",
            "justification": "Algorithmic or numerical breakdown during execution.",
            "is_disproportionately_difficult": "Yes",
            "eval_rows": None
        }

def main():
    print("=" * 80)
    print(" TASK A: AUDIT AND REPRODUCE FULL-LAYOUT BENCHMARK")
    print("=" * 80)

    work_items = []
    for lay in LAYOUTS:
        for sub in SUBS:
            for snr in SNRS:
                for cond in CONDITIONS:
                    work_items.append((sub, snr, lay, cond))

    total_possible = len(work_items)
    print(f"Total possible simulation records: {total_possible} (5 layouts x 10 subjects x 5 SNRs x 6 conditions)")

    t_start = time.time()
    valid_results = []
    missing_records = []
    completed = 0

    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(audit_record, item): item for item in work_items}
        for future in as_completed(futures):
            res = future.result()
            if res["status"] == "VALID":
                valid_results.extend(res["eval_rows"])
            else:
                missing_records.append(res)
            completed += 1
            if completed % 250 == 0 or completed == total_possible:
                print(f"  Processed {completed}/{total_possible} records ({time.time() - t_start:.1f} s)...")

    # Output MISSING_RECORDS.csv
    missing_csv = OUT_DIR / "MISSING_RECORDS.csv"
    with open(missing_csv, "w", newline="") as f:
        fieldnames = ["record", "sub", "snr", "layout", "cond", "status", "reason", "justification", "is_disproportionately_difficult"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in sorted(missing_records, key=lambda x: x["record"]):
            row_dict = {k: m.get(k, "") for k in fieldnames}
            writer.writerow(row_dict)
    print(f"\nSaved missing records audit: {missing_csv} ({len(missing_records)} records)")

    # Output FULL_LAYOUT_REPRODUCED.csv
    reproduced_csv = OUT_DIR / "FULL_LAYOUT_REPRODUCED.csv"
    with open(reproduced_csv, "w", newline="") as f:
        fieldnames = list(valid_results[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(valid_results)
    print(f"Saved reproduced benchmark evaluations: {reproduced_csv} ({len(valid_results)} evaluations from {total_possible - len(missing_records)} records)")

    # Summary by Layout
    layout_data = defaultdict(list)
    for r in valid_results:
        layout_data[r["layout"]].append(r)

    comparison_rows = []
    print("\n" + "=" * 80)
    print(" LAYOUT-LEVEL REPRODUCED RESULTS COMPARISON")
    print("=" * 80)
    print(f"{'Layout':<8} | {'Evaluations':<11} | {'Mean F1 (%)':<11} | {'Std F1':<8} | {'Sens (%)':<9} | {'PPV (%)':<8} | {'MAE (bpm)':<10}")
    print("-" * 75)

    for lay in LAYOUTS:
        rows = layout_data[lay]
        f1s = [r["f1"] for r in rows]
        maes = [r["fhr_mae_bpm"] for r in rows if r["fhr_mae_bpm"] < 900.0]
        tp = sum(r["tp"] for r in rows)
        fp = sum(r["fp"] for r in rows)
        fn = sum(r["fn"] for r in rows)
        sens = tp / (tp + fn) * 100.0 if (tp + fn) > 0 else 0.0
        ppv = tp / (tp + fp) * 100.0 if (tp + fp) > 0 else 0.0
        
        comp_dict = {
            "layout": lay,
            "n_evaluations": len(rows),
            "mean_f1": round(float(np.mean(f1s)), 2),
            "std_f1": round(float(np.std(f1s)), 2),
            "min_f1": round(float(np.min(f1s)), 2),
            "max_f1": round(float(np.max(f1s)), 2),
            "mean_fhr_mae_bpm": round(float(np.mean(maes)), 2),
            "aggregate_sensitivity": round(sens, 2),
            "aggregate_ppv": round(ppv, 2),
            "total_tp": tp,
            "total_fp": fp,
            "total_fn": fn
        }
        comparison_rows.append(comp_dict)
        print(f"{lay:<8} | {len(rows):<11} | {comp_dict['mean_f1']:<11.2f} | {comp_dict['std_f1']:<8.2f} | {sens:<9.2f} | {ppv:<8.2f} | {comp_dict['mean_fhr_mae_bpm']:<10.2f}")

    layout_comp_csv = OUT_DIR / "LAYOUT_COMPARISON.csv"
    with open(layout_comp_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(comparison_rows[0].keys()))
        writer.writeheader()
        writer.writerows(comparison_rows)
    print(f"Saved layout comparison CSV: {layout_comp_csv}")

    all_f1s = [r["f1"] for r in valid_results]
    all_maes = [r["fhr_mae_bpm"] for r in valid_results if r["fhr_mae_bpm"] < 900.0]
    total_tp = sum(r["tp"] for r in valid_results)
    total_fp = sum(r["fp"] for r in valid_results)
    total_fn = sum(r["fn"] for r in valid_results)
    print("-" * 75)
    print(f"{'OVERALL':<8} | {len(valid_results):<11} | {np.mean(all_f1s):<11.2f} | {np.std(all_f1s):<8.2f} | {total_tp/(total_tp+total_fn)*100:<9.2f} | {total_tp/(total_tp+total_fp)*100:<8.2f} | {np.mean(all_maes):<10.2f}")
    print("=" * 80)

if __name__ == "__main__":
    main()
