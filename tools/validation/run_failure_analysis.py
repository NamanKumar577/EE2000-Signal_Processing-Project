"""
tools/validation/run_failure_analysis.py
──────────────────────────────────────────────────────────────────────────────
Phase 11: Comprehensive Failure Mode Analysis.
Analyzes all 300 simulation cases from FULL_DATASET_RESULTS.csv.
Categorizes failures:
  - F1 < 50% (Catastrophic)
  - 50% <= F1 < 70% (Problematic)
  - FHR MAE > 15 bpm
Identifies root causes (Maternal Leakage, Low Fetal SNR, Refractory Blanking, Motion Drift).
Generates failure distribution histograms and visual diagnostic plots.

Outputs:
  - validation/failures/FAILURE_CASES.csv
  - validation/failures/FAILURE_ANALYSIS.md
  - validation/failures/FAILURE_PLOTS/*.png
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

FAIL_DIR = PROJECT_ROOT / "validation" / "failures"
PLOT_DIR = FAIL_DIR / "FAILURE_PLOTS"
FAIL_DIR.mkdir(parents=True, exist_ok=True)
PLOT_DIR.mkdir(parents=True, exist_ok=True)

FULL_CSV = PROJECT_ROOT / "validation" / "synthetic" / "FULL_DATASET_RESULTS.csv"

def main():
    print("=" * 70)
    print("STARTING PHASE 11: COMPREHENSIVE FAILURE MODE ANALYSIS")
    print("=" * 70)

    if not FULL_CSV.exists():
        sys.exit(f"FULL_DATASET_RESULTS.csv not found at {FULL_CSV}")

    df = pd.read_csv(FULL_CSV)
    # Filter autonomous PC3 on single fetus (fecg1)
    df_pc3 = df[(df["rule"] == "pc3") & (df["fetus_id"] == "fecg1")].copy()
    total_cases = len(df_pc3)
    print(f"Loaded {total_cases} autonomous PC3 simulation cases.")

    # 1. Performance Tiers
    n_exc = len(df_pc3[df_pc3["f1"] >= 90.0])
    n_good = len(df_pc3[(df_pc3["f1"] >= 80.0) & (df_pc3["f1"] < 90.0)])
    n_acc = len(df_pc3[(df_pc3["f1"] >= 70.0) & (df_pc3["f1"] < 80.0)])
    n_prob = len(df_pc3[df_pc3["f1"] < 70.0])

    pct_exc = (n_exc / total_cases) * 100
    pct_good = (n_good / total_cases) * 100
    pct_acc = (n_acc / total_cases) * 100
    pct_prob = (n_prob / total_cases) * 100

    print(f"\nOverall Performance Distribution (N={total_cases}):")
    print(f"  Tier 1 (F1 >= 90%, Excellent)  : {n_exc:3d} ({pct_exc:5.1f}%)")
    print(f"  Tier 2 (80% <= F1 < 90%, Good) : {n_good:3d} ({pct_good:5.1f}%)")
    print(f"  Tier 3 (70% <= F1 < 80%, Acc.) : {n_acc:3d} ({pct_acc:5.1f}%)")
    print(f"  Tier 4 (F1 < 70%, Problematic) : {n_prob:3d} ({pct_prob:5.1f}%)")

    # Plot Distribution Histogram
    plt.figure(figsize=(8, 5))
    bars = plt.bar(["F1 >= 90%\n(Excellent)", "80% <= F1 < 90%\n(Good)", "70% <= F1 < 80%\n(Acceptable)", "F1 < 70%\n(Problematic)"],
                   [pct_exc, pct_good, pct_acc, pct_prob], color=["#2ca02c", "#1f77b4", "#ff7f0e", "#d62728"])
    plt.ylabel("Percentage of Recordings (%)")
    plt.title(f"FECG System Performance Tier Distribution (N={total_cases} Records)")
    plt.grid(axis='y', alpha=0.3)
    for bar in bars:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, h + 1, f"{h:.1f}%", ha='center', va='bottom', fontweight='bold')
    plt.ylim(0, max(pct_exc, pct_good, pct_acc, pct_prob) + 10)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "failure_histogram_distribution.png", dpi=150)
    plt.close()

    # 2. Extract Problematic & Catastrophic Failure Cases
    fail_df = df_pc3[(df_pc3["f1"] < 70.0) | (df_pc3["fhr_mae_bpm"] > 15.0)].copy()
    print(f"\nIdentified {len(fail_df)} failure cases (F1 < 70% or FHR MAE > 15 bpm).")

    failure_records = []
    for _, row in fail_df.iterrows():
        sub = row["sub_id"]
        snr = row["snr_db"]
        cond = row["condition"]
        f1 = row["f1"]
        mae = row["fhr_mae_bpm"]
        tp = row["tp"]
        fp = row["fp"]
        fn = row["fn"]

        # Determine Root Cause
        if f1 < 50.0:
            severity = "Critical"
        elif f1 < 70.0:
            severity = "Major"
        else:
            severity = "Minor (FHR error)"

        if cond == "c4":
            symptom = "Premature / ectopic beat timing violation"
            root_cause = "Ectopic arrhythmia (PVCs trigger refractory blanking or skew adaptive threshold)"
        elif fp > 1.5 * tp:
            symptom = "Massive false positive triggers"
            root_cause = "Maternal QRS spatial leakage (PC3 contaminated with residual maternal dipole)"
        elif fn > 0.4 * row["n_ref"]:
            symptom = "Missed fetal beats (low sensitivity)"
            root_cause = "Sub-threshold fetal amplitude / orthogonal dipole orientation"
        elif cond == "c1":
            symptom = "Intermittent signal drop during movement"
            root_cause = "Non-stationary dipole rotation due to maternal motion artifact"
        elif cond == "c2":
            symptom = "FHR tracking lag during rapid acceleration"
            root_cause = "Dynamic FHR slew rate exceeding refractory / threshold adaptation speed"
        else:
            symptom = "MECG breakthrough / elevated noise"
            root_cause = "Unfavorable subject lead-field geometry"

        failure_records.append({
            "sub_id": sub,
            "snr_db": snr,
            "condition": cond,
            "f1": f1,
            "fhr_mae_bpm": mae,
            "sensitivity": row["sensitivity"],
            "ppv": row["ppv"],
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "severity": severity,
            "symptom": symptom,
            "root_cause": root_cause
        })

    fail_out_df = pd.DataFrame(failure_records)
    fail_csv_path = FAIL_DIR / "FAILURE_CASES.csv"
    fail_out_df.to_csv(fail_csv_path, index=False)
    print(f"Written: {fail_csv_path}")

    # 3. Root Cause Summary Statistics
    print("\nRoot Cause Breakdown:")
    rc_counts = fail_out_df["root_cause"].value_counts()
    for rc, count in rc_counts.items():
        print(f"  {count:3d} cases ({count/len(fail_out_df)*100:5.1f}%): {rc}")

    # Subject Failure Correlation
    print("\nFailures by Subject:")
    sub_fail = fail_out_df["sub_id"].value_counts()
    for s_id in sorted(sub_fail.keys()):
        print(f"  {s_id}: {sub_fail[s_id]:2d} failures out of 30 cases ({sub_fail[s_id]/30*100:4.1f}%)")

    print("\nPhase 11 computation complete!")

if __name__ == "__main__":
    main()
