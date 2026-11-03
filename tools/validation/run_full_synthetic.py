"""
tools/validation/run_full_synthetic.py
──────────────────────────────────────────────────────────────────────────────
Phase 2: Full Synthetic Dataset Validation Campaign.
Sweeps all 10 subjects x 5 SNRs x 6 conditions (c0 to c5) = 300 simulation cases.
Evaluates both:
  - Causal autonomous PC3 (the FPGA deployable pipeline)
  - Causal Oracle (the theoretical upper bound for 4-channel spatial projection)
For condition c5 (twins), evaluates against both fecg1 and fecg2 independently.

Outputs:
  - validation/synthetic/FULL_DATASET_RESULTS.csv
  - validation/synthetic/SNR_ANALYSIS.csv
  - validation/synthetic/CONDITION_ANALYSIS.csv
  - validation/synthetic/SUBJECT_ANALYSIS.csv
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
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
SYNTH_DIR = PROJECT_ROOT / "validation" / "synthetic"
SYNTH_DIR.mkdir(parents=True, exist_ok=True)

SUBS = [f"sub{i:02d}" for i in range(1, 11)]
SNRS = ["snr00dB", "snr03dB", "snr06dB", "snr09dB", "snr12dB"]
SNR_VALS = {"snr00dB": 0, "snr03dB": 3, "snr06dB": 6, "snr09dB": 9, "snr12dB": 12}
CONDITIONS = ["c0", "c1", "c2", "c3", "c4", "c5"]
CHANNELS = [27, 26, 28, 25]

def load_case(base_path: str, channels: list[int]):
    """Load components and construct 4-channel mixture, plus annotations."""
    fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal
    mecg = wfdb.rdrecord(base_path + "_mecg").p_signal
    n1 = wfdb.rdrecord(base_path + "_noise1").p_signal
    n2 = wfdb.rdrecord(base_path + "_noise2").p_signal
    mix = (mecg + fecg + n1 + n2)[:, channels]
    
    # Ground truth fecg1
    ref1 = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)
    
    # Check if fecg2 exists (twin condition c5)
    ref2 = None
    fecg2_hea = Path(base_path + "_fecg2.hea")
    if fecg2_hea.exists():
        try:
            ref2 = np.sort(wfdb.rdann(base_path + "_fecg2", "qrs").sample)
        except Exception:
            ref2 = None
            
    return mix, ref1, ref2

def main():
    print("=" * 70)
    print("STARTING PHASE 2: FULL SYNTHETIC DATASET VALIDATION (300 CASES)")
    print("=" * 70)
    
    full_results = []
    t_start = time.time()
    
    total_processed = 0
    total_missing = 0
    
    for sub in SUBS:
        sub_start = time.time()
        print(f"\nProcessing {sub}...")
        for snr in SNRS:
            snr_db = SNR_VALS[snr]
            for cond in CONDITIONS:
                rec_name = f"{sub}_{snr}_l1_{cond}"
                base_path = str(DATA_DIR / sub / snr / rec_name)
                
                if not Path(base_path + "_fecg1.hea").exists():
                    total_missing += 1
                    continue
                
                try:
                    mix, ref1, ref2 = load_case(base_path, CHANNELS)
                except Exception as e:
                    print(f"Error loading {rec_name}: {e}")
                    total_missing += 1
                    continue
                
                fs = 250
                # Calibration bank (whole record for theoretical upper bound, and pc3)
                bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=0)
                
                # We evaluate:
                # 1. Autonomous PC3 (target FPGA configuration)
                # 2. Causal Oracle (benchmark upper bound)
                
                # --- Evaluate on Fetus 1 ---
                for rule in ["pc3", "oracle"]:
                    j, _ = bank.select(rule, ref_qrs=ref1 if rule == "oracle" else None)
                    det_res = bank.det_full(j)
                    m = compute_beat_metrics(ref1, det_res.peaks, fs=fs)
                    fc = compare_fhr(compute_fhr(det_res.peaks, fs=fs), ref1, fs=fs)
                    
                    f1 = m.f1 or 0.0
                    mae = fc.mean_abs_error_bpm if not np.isnan(fc.mean_abs_error_bpm) else 999.0
                    
                    full_results.append({
                        "sub_id": sub,
                        "snr_db": snr_db,
                        "condition": cond,
                        "fetus_id": "fecg1",
                        "rule": rule,
                        "sel_pc": j + 1,
                        "tp": m.tp,
                        "fp": m.fp,
                        "fn": m.fn,
                        "sensitivity": round(m.sensitivity or 0.0, 4),
                        "ppv": round(m.ppv or 0.0, 4),
                        "f1": round(f1 * 100, 2),
                        "fhr_mae_bpm": round(mae, 2),
                        "n_ref": len(ref1),
                        "n_det": len(det_res.peaks)
                    })
                
                # --- Evaluate on Fetus 2 if Twin Condition (c5) ---
                if cond == "c5" and ref2 is not None and len(ref2) > 0:
                    for rule in ["pc3", "oracle"]:
                        j, _ = bank.select(rule, ref_qrs=ref2 if rule == "oracle" else None)
                        det_res = bank.det_full(j)
                        m2 = compute_beat_metrics(ref2, det_res.peaks, fs=fs)
                        fc2 = compare_fhr(compute_fhr(det_res.peaks, fs=fs), ref2, fs=fs)
                        
                        f1_2 = m2.f1 or 0.0
                        mae_2 = fc2.mean_abs_error_bpm if not np.isnan(fc2.mean_abs_error_bpm) else 999.0
                        
                        full_results.append({
                            "sub_id": sub,
                            "snr_db": snr_db,
                            "condition": cond,
                            "fetus_id": "fecg2",
                            "rule": rule,
                            "sel_pc": j + 1,
                            "tp": m2.tp,
                            "fp": m2.fp,
                            "fn": m2.fn,
                            "sensitivity": round(m2.sensitivity or 0.0, 4),
                            "ppv": round(m2.ppv or 0.0, 4),
                            "f1": round(f1_2 * 100, 2),
                            "fhr_mae_bpm": round(mae_2, 2),
                            "n_ref": len(ref2),
                            "n_det": len(det_res.peaks)
                        })
                
                total_processed += 1
                
        print(f"  {sub} finished in {time.time() - sub_start:.1f} s")
        
    print(f"\nAll cases processed in {time.time() - t_start:.1f} s! Total simulation records: {total_processed}")
    
    # Save FULL_DATASET_RESULTS.csv
    full_csv = SYNTH_DIR / "FULL_DATASET_RESULTS.csv"
    with open(full_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "sub_id", "snr_db", "condition", "fetus_id", "rule", "sel_pc",
            "tp", "fp", "fn", "sensitivity", "ppv", "f1", "fhr_mae_bpm", "n_ref", "n_det"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(full_results)
    print(f"Written: {full_csv}")
    
    # Generate Aggregations for PC3 (the primary autonomous algorithm)
    pc3_results = [r for r in full_results if r["rule"] == "pc3" and r["fetus_id"] == "fecg1"]
    
    # 1. SNR Analysis
    snr_groups = defaultdict(list)
    for r in pc3_results:
        snr_groups[r["snr_db"]].append(r)
        
    snr_rows = []
    for snr_val in sorted(snr_groups.keys()):
        grp = snr_groups[snr_val]
        f1s = [x["f1"] for x in grp]
        maes = [x["fhr_mae_bpm"] for x in grp if x["fhr_mae_bpm"] < 500]
        tps = sum(x["tp"] for x in grp)
        fps = sum(x["fp"] for x in grp)
        fns = sum(x["fn"] for x in grp)
        sens = tps / (tps + fns) if (tps + fns) > 0 else 0
        ppvs = tps / (tps + fps) if (tps + fps) > 0 else 0
        snr_rows.append({
            "snr_db": snr_val,
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
    with open(SYNTH_DIR / "SNR_ANALYSIS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(snr_rows[0].keys()))
        w.writeheader()
        w.writerows(snr_rows)
    print(f"Written: {SYNTH_DIR / 'SNR_ANALYSIS.csv'}")

    # 2. Condition Analysis
    cond_groups = defaultdict(list)
    for r in pc3_results:
        cond_groups[r["condition"]].append(r)
        
    cond_rows = []
    for cond_val in sorted(cond_groups.keys()):
        grp = cond_groups[cond_val]
        f1s = [x["f1"] for x in grp]
        maes = [x["fhr_mae_bpm"] for x in grp if x["fhr_mae_bpm"] < 500]
        tps = sum(x["tp"] for x in grp)
        fps = sum(x["fp"] for x in grp)
        fns = sum(x["fn"] for x in grp)
        sens = tps / (tps + fns) if (tps + fns) > 0 else 0
        ppvs = tps / (tps + fps) if (tps + fps) > 0 else 0
        cond_rows.append({
            "condition": cond_val,
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
    with open(SYNTH_DIR / "CONDITION_ANALYSIS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cond_rows[0].keys()))
        w.writeheader()
        w.writerows(cond_rows)
    print(f"Written: {SYNTH_DIR / 'CONDITION_ANALYSIS.csv'}")

    # 3. Subject Analysis
    sub_groups = defaultdict(list)
    for r in pc3_results:
        sub_groups[r["sub_id"]].append(r)
        
    sub_rows = []
    for sub_val in sorted(sub_groups.keys()):
        grp = sub_groups[sub_val]
        f1s = [x["f1"] for x in grp]
        maes = [x["fhr_mae_bpm"] for x in grp if x["fhr_mae_bpm"] < 500]
        tps = sum(x["tp"] for x in grp)
        fps = sum(x["fp"] for x in grp)
        fns = sum(x["fn"] for x in grp)
        sens = tps / (tps + fns) if (tps + fns) > 0 else 0
        ppvs = tps / (tps + fps) if (tps + fps) > 0 else 0
        sub_rows.append({
            "sub_id": sub_val,
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
    with open(SYNTH_DIR / "SUBJECT_ANALYSIS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sub_rows[0].keys()))
        w.writeheader()
        w.writerows(sub_rows)
    print(f"Written: {SYNTH_DIR / 'SUBJECT_ANALYSIS.csv'}")

    print("\nPhase 2 computation complete!")

if __name__ == "__main__":
    main()
