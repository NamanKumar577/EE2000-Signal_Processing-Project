"""
tools/improvements/run_full_layout_benchmark.py
──────────────────────────────────────────────────────────────────────────────
Priority 1: Complete Dataset Coverage Across Layouts l1, l2, l3, l4, l5.

Runs the frozen baseline algorithm (causal pipeline, PC3, channels [27,26,28,25],
tolerance +-50 ms) across all available simulation records in FECGSYNDB:
  - 5 Layouts: l1, l2, l3, l4, l5
  - 10 Subjects: sub01 to sub10
  - 5 SNR levels: 0, 3, 6, 9, 12 dB
  - 6 Conditions: c0, c1, c2, c3, c4, c5

Parallelized using ProcessPoolExecutor for high-speed execution.

Outputs:
  - validation/improvements/FULL_LAYOUT_BENCHMARK.csv
  - validation/improvements/LAYOUT_ANALYSIS.csv
  - validation/improvements/LAYOUT_SUBJECT_ANALYSIS.csv
  - validation/improvements/LAYOUT_SNR_ANALYSIS.csv
  - validation/improvements/LAYOUT_CONDITION_ANALYSIS.csv
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
    CalibrationBank, DEFAULT_CONFIG, run_causal
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "improvements"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250
LAYOUTS = ["l1", "l2", "l3", "l4", "l5"]
SUBS = [f"sub{i:02d}" for i in range(1, 11)]
SNRS = ["snr00dB", "snr03dB", "snr06dB", "snr09dB", "snr12dB"]
SNR_VALS = {"snr00dB": 0, "snr03dB": 3, "snr06dB": 6, "snr09dB": 9, "snr12dB": 12}
CONDITIONS = ["c0", "c1", "c2", "c3", "c4", "c5"]

def evaluate_single_record(args):
    sub, snr, layout, cond = args
    base_path = str(DATA_DIR / sub / snr / f"{sub}_{snr}_{layout}_{cond}")
    hea_fecg1 = Path(base_path + "_fecg1.hea")
    if not hea_fecg1.exists():
        return None

    try:
        fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal[:, CHANNELS]
        mecg = wfdb.rdrecord(base_path + "_mecg").p_signal[:, CHANNELS]
        n1 = wfdb.rdrecord(base_path + "_noise1").p_signal[:, CHANNELS]
        n2 = wfdb.rdrecord(base_path + "_noise2").p_signal[:, CHANNELS]
        mix = fecg + mecg + n1 + n2
        ref1 = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)
    except Exception as e:
        return None

    # Check twin annotation
    ref2 = None
    if cond == "c5" and Path(base_path + "_fecg2.hea").exists():
        try:
            ref2 = np.sort(wfdb.rdann(base_path + "_fecg2", "qrs").sample)
        except Exception:
            ref2 = None

    try:
        # Baseline causal pipeline with PC3
        bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=0)
        j, _ = bank.select("pc3")
        w = bank.weights(j)
        fecg_out, det_res = run_causal(mix, w, DEFAULT_CONFIG)
        peaks = det_res.peaks

        # Evaluate Fetus 1
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

        # Evaluate Fetus 2 if twin
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

        return rows
    except Exception as e:
        return None

def aggregate_group(rows, key_fields):
    groups = defaultdict(list)
    for r in rows:
        k = tuple(r[f] for f in key_fields)
        groups[k].append(r)

    agg_rows = []
    for k in sorted(groups.keys()):
        grp = groups[k]
        f1s = [x["f1"] for x in grp]
        maes = [x["fhr_mae_bpm"] for x in grp if x["fhr_mae_bpm"] < 500]
        tps = sum(x["tp"] for x in grp)
        fps = sum(x["fp"] for x in grp)
        fns = sum(x["fn"] for x in grp)
        sens = tps / (tps + fns) if (tps + fns) > 0 else 0.0
        ppvs = tps / (tps + fps) if (tps + fps) > 0 else 0.0

        res = {f: k[idx] for idx, f in enumerate(key_fields)}
        res.update({
            "n_records": len(grp),
            "mean_f1": round(float(np.mean(f1s)), 2),
            "std_f1": round(float(np.std(f1s)), 2),
            "min_f1": round(float(np.min(f1s)), 2),
            "max_f1": round(float(np.max(f1s)), 2),
            "mean_fhr_mae": round(float(np.mean(maes)), 2) if maes else 999.0,
            "aggregate_sens": round(sens * 100, 2),
            "aggregate_ppv": round(ppvs * 100, 2),
            "total_tp": tps,
            "total_fp": fps,
            "total_fn": fns
        })
        agg_rows.append(res)
    return agg_rows

def main():
    print("=" * 70)
    print("STARTING FULL-LAYOUT BENCHMARK SWEEP (l1, l2, l3, l4, l5)")
    print("=" * 70)

    work_items = []
    for lay in LAYOUTS:
        for sub in SUBS:
            for snr in SNRS:
                for cond in CONDITIONS:
                    work_items.append((sub, snr, lay, cond))

    total_tasks = len(work_items)
    print(f"Total potential simulation records to process: {total_tasks}")

    t_start = time.time()
    all_results = []
    completed = 0

    # Parallel execution with 8 workers
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(evaluate_single_record, item): item for item in work_items}
        for future in as_completed(futures):
            res = future.result()
            if res:
                all_results.extend(res)
            completed += 1
            if completed % 250 == 0 or completed == total_tasks:
                elapsed = time.time() - t_start
                print(f"  Processed {completed}/{total_tasks} records ({elapsed:.1f} s)...")

    total_time = time.time() - t_start
    print(f"\nAll records processed in {total_time:.1f} s! Total evaluations generated: {len(all_results)}")

    # 1. Save FULL_LAYOUT_BENCHMARK.csv
    full_csv = OUT_DIR / "FULL_LAYOUT_BENCHMARK.csv"
    with open(full_csv, "w", newline="", encoding="utf-8") as f:
        fields = [
            "layout", "sub_id", "snr_db", "condition", "fetus_id", "rule", "sel_pc",
            "tp", "fp", "fn", "sensitivity", "ppv", "f1", "fhr_mae_bpm", "n_ref", "n_det"
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_results)
    print(f"Written: {full_csv}")

    # Primary analysis on single fetus (fecg1)
    single_fetus_rows = [r for r in all_results if r["fetus_id"] == "fecg1"]

    # 2. Per-Layout Summary (LAYOUT_ANALYSIS.csv)
    lay_agg = aggregate_group(single_fetus_rows, ["layout"])
    with open(OUT_DIR / "LAYOUT_ANALYSIS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lay_agg[0].keys()))
        w.writeheader()
        w.writerows(lay_agg)
    print(f"Written: {OUT_DIR / 'LAYOUT_ANALYSIS.csv'}")

    # 3. Per-Layout x Subject Summary (LAYOUT_SUBJECT_ANALYSIS.csv)
    sub_agg = aggregate_group(single_fetus_rows, ["layout", "sub_id"])
    with open(OUT_DIR / "LAYOUT_SUBJECT_ANALYSIS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sub_agg[0].keys()))
        w.writeheader()
        w.writerows(sub_agg)
    print(f"Written: {OUT_DIR / 'LAYOUT_SUBJECT_ANALYSIS.csv'}")

    # 4. Per-Layout x SNR Summary (LAYOUT_SNR_ANALYSIS.csv)
    snr_agg = aggregate_group(single_fetus_rows, ["layout", "snr_db"])
    with open(OUT_DIR / "LAYOUT_SNR_ANALYSIS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(snr_agg[0].keys()))
        w.writeheader()
        w.writerows(snr_agg)
    print(f"Written: {OUT_DIR / 'LAYOUT_SNR_ANALYSIS.csv'}")

    # 5. Per-Layout x Condition Summary (LAYOUT_CONDITION_ANALYSIS.csv)
    cond_agg = aggregate_group(single_fetus_rows, ["layout", "condition"])
    with open(OUT_DIR / "LAYOUT_CONDITION_ANALYSIS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cond_agg[0].keys()))
        w.writeheader()
        w.writerows(cond_agg)
    print(f"Written: {OUT_DIR / 'LAYOUT_CONDITION_ANALYSIS.csv'}")

    print("\n=== PER-LAYOUT PERFORMANCE SUMMARY ===")
    print(f"{'Layout':8s} {'Records':>8s} {'Mean F1 (%)':>12s} {'Std F1':>8s} {'FHR MAE':>10s} {'Sens (%)':>10s} {'PPV (%)':>10s}")
    for r in lay_agg:
        print(f"  {r['layout']:6s} {r['n_records']:8d} {r['mean_f1']:11.2f}% {r['std_f1']:7.2f}% {r['mean_fhr_mae']:9.2f} bpm {r['aggregate_sens']:9.2f}% {r['aggregate_ppv']:9.2f}%")

if __name__ == "__main__":
    main()
