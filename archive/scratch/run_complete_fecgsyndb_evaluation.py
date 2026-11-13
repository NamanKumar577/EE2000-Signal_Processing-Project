#!/usr/bin/env python3
"""
scratch/run_complete_fecgsyndb_evaluation.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive FECGSYNDB Coverage Audit & Full-Database Evaluation.
Evaluates the complete 1,500-case parameter space:
  - 10 Subjects: sub01 to sub10
  - 5 SNR Levels: snr00dB, snr03dB, snr06dB, snr09dB, snr12dB (0, 3, 6, 9, 12 dB)
  - 5 Layouts: l1, l2, l3, l4, l5
  - 6 Conditions: c0, c1, c2, c3, c4, c5
Cross-references all historical evaluation records and runs the frozen
bit-accurate reference pipeline on all available and eligible recordings.
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import csv
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(r"D:\signal_project")
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fpga_implementation.uart_host.validate_real_datasets import (
    HostSpatialCalibrator, read_wfdb_qrs, CHANNELS_4CH
)
from fecg.hardware.bit_accurate_reference import run_bit_accurate_pipeline_final
from src.evaluation import match_beats

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "complete_dataset_validation_20261106"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / "FECGSYNDB_COVERAGE_MATRIX.csv"

SUBS = [f"sub{i:02d}" for i in range(1, 11)]
SNRS = ["snr00dB", "snr03dB", "snr06dB", "snr09dB", "snr12dB"]
SNR_DB_MAP = {"snr00dB": 0, "snr03dB": 3, "snr06dB": 6, "snr09dB": 9, "snr12dB": 12}
LAYOUTS = [f"l{i}" for i in range(1, 6)]
CONDS = [f"c{i}" for i in range(6)]

FS = 250
TOL_SAMPLES = 13  # +-50 ms at 250 Hz is +-12.5 -> 13 samples
WARMUP_SAMPLES = 512

# Load historical evaluation data sets
print("Loading historical evaluation databases...")
hist_phase5 = set()
p5_path = PROJECT_ROOT / "fpga_implementation" / "reports" / "phase5_expanded_fecgsyndb_results.csv"
if p5_path.exists():
    df_p5 = pd.read_csv(p5_path)
    for _, r in df_p5.iterrows():
        # case_id: sub01_snr12dB_c0 (layout was l1)
        sub = r['sub_id']
        snr = f"snr{int(r['snr_db']):02d}dB"
        cond = r['condition']
        hist_phase5.add((sub, snr, "l1", cond))

hist_prefpga_full = set()
pre_full_path = PROJECT_ROOT / "validation" / "pre_fpga" / "02_full_layout_validation" / "FULL_LAYOUT_REPRODUCED.csv"
if pre_full_path.exists():
    df_pre = pd.read_csv(pre_full_path)
    for _, r in df_pre.iterrows():
        sub = r['sub_id']
        snr = f"snr{int(r['snr_db']):02d}dB"
        lay = r['layout']
        cond = r['condition']
        hist_prefpga_full.add((sub, snr, lay, cond))

hist_prefpga_corr = set()
corr_path = PROJECT_ROOT / "results" / "validation_reports" / "pre_fpga_corrected" / "06_benchmark_correction" / "FINAL_CONFIGURATION_FULL_LAYOUT.csv"
if corr_path.exists():
    df_corr = pd.read_csv(corr_path)
    for _, r in df_corr.iterrows():
        sub = r['subject']
        snr = f"snr{int(r['snr_db']):02d}dB"
        lay = r['layout']
        cond = r['condition']
        hist_prefpga_corr.add((sub, snr, lay, cond))

hist_phase4_hw = {
    ("sub01", "snr12dB", "l1", "c0"),
    ("sub01", "snr06dB", "l1", "c0"),
    ("sub01", "snr00dB", "l1", "c0"),
    ("sub04", "snr06dB", "l1", "c0"),
    ("sub08", "snr06dB", "l1", "c0"),
}

KNOWN_NAN_RECORDS = {
    ("sub03", "snr12dB", "l2", "c3"),
    ("sub04", "snr03dB", "l2", "c3"),
    ("sub07", "snr12dB", "l5", "c3"),
    ("sub08", "snr03dB", "l4", "c3")
}

KNOWN_MISSING_FILES = {
    ("sub09", "snr00dB", "l4", "c5"),
    ("sub09", "snr00dB", "l5", "c0"),
    ("sub09", "snr00dB", "l5", "c1")
}

def load_case_data(sub: str, snr: str, lay: str, cond: str):
    """Loads 4-channel mixture, ground truth components, and fetal/maternal QRS annotations."""
    base = DATA_DIR / sub / snr / f"{sub}_{snr}_{lay}_{cond}"
    
    # Check essential files
    fecg_dat = Path(str(base) + "_fecg1.dat")
    mecg_dat = Path(str(base) + "_mecg.dat")
    n1_dat = Path(str(base) + "_noise1.dat")
    n2_dat = Path(str(base) + "_noise2.dat")
    
    if not (fecg_dat.exists() and mecg_dat.exists() and n1_dat.exists() and n2_dat.exists()):
        return None, "MISSING_BINARY_DATA"
        
    try:
        fecg_raw = np.fromfile(str(base) + "_fecg1.dat", dtype=np.int16).reshape(-1, 34)
        mecg_raw = np.fromfile(str(base) + "_mecg.dat", dtype=np.int16).reshape(-1, 34)
        n1_raw = np.fromfile(str(base) + "_noise1.dat", dtype=np.int16).reshape(-1, 34)
        n2_raw = np.fromfile(str(base) + "_noise2.dat", dtype=np.int16).reshape(-1, 34)
    except Exception as e:
        return None, f"FILE_READ_ERROR: {e}"
        
    # Check NaNs
    if np.isnan(fecg_raw).any() or np.isnan(mecg_raw).any() or np.isnan(n1_raw).any() or np.isnan(n2_raw).any():
        return None, "CORRUPT_NAN_SAMPLES"
        
    fecg_4ch = fecg_raw[:, CHANNELS_4CH].astype(np.float64)
    mecg_4ch = mecg_raw[:, CHANNELS_4CH].astype(np.float64)
    noise_4ch = (n1_raw[:, CHANNELS_4CH] + n2_raw[:, CHANNELS_4CH]).astype(np.float64)
    
    # If c3 (uterine contractions), add noise3 if present
    if cond == "c3":
        n3_dat = Path(str(base) + "_noise3.dat")
        if n3_dat.exists():
            try:
                n3_raw = np.fromfile(str(base) + "_noise3.dat", dtype=np.int16).reshape(-1, 34)
                if not np.isnan(n3_raw).any():
                    noise_4ch += n3_raw[:, CHANNELS_4CH].astype(np.float64)
            except Exception:
                pass
                
    # If c5 (twins), add fecg2 if present
    if cond == "c5":
        f2_dat = Path(str(base) + "_fecg2.dat")
        if f2_dat.exists():
            try:
                f2_raw = np.fromfile(str(base) + "_fecg2.dat", dtype=np.int16).reshape(-1, 34)
                if not np.isnan(f2_raw).any():
                    noise_4ch += f2_raw[:, CHANNELS_4CH].astype(np.float64)
            except Exception:
                pass

    mix_4ch = fecg_4ch + mecg_4ch + noise_4ch
    
    f_qrs = read_wfdb_qrs(str(base) + "_fecg1.qrs")
    m_qrs = read_wfdb_qrs(str(base) + "_mecg.qrs")
    
    fhr_nom = 140.0
    hea_path = Path(str(base) + "_fecg1.hea")
    if hea_path.exists():
        with open(hea_path, "r", errors="ignore") as f:
            for line in f:
                if line.startswith("#fhr:"):
                    try:
                        fhr_nom = float(line.strip().split(":")[1].split()[0])
                    except Exception:
                        pass
                        
    return {
        "mix_4ch": mix_4ch,
        "fecg_4ch": fecg_4ch,
        "mecg_4ch": mecg_4ch,
        "f_qrs": f_qrs,
        "m_qrs": m_qrs,
        "fhr_nominal": fhr_nom
    }, "OK"

def main():
    print("=" * 80)
    print("STARTING FECGSYNDB COMPLETE COVERAGE AUDIT & EVALUATION")
    print("=" * 80)
    
    matrix_rows = []
    total_grid = len(SUBS) * len(SNRS) * len(LAYOUTS) * len(CONDS)
    print(f"Total theoretical grid combinations: {total_grid}")
    
    tested_count = 0
    skipped_count = 0
    t0 = time.time()
    
    for sub in SUBS:
        for snr in SNRS:
            snr_db = SNR_DB_MAP[snr]
            for lay in LAYOUTS:
                for cond in CONDS:
                    rec_id = f"{sub}_{snr}_{lay}_{cond}"
                    key = (sub, snr, lay, cond)
                    
                    # 1. On-disk and corruption status
                    if key in KNOWN_MISSING_FILES:
                        on_disk_status = "MISSING_ON_DISK"
                        eligibility = "INELIGIBLE_MISSING_FILES"
                    elif key in KNOWN_NAN_RECORDS:
                        on_disk_status = "CORRUPT_NAN_SAMPLES"
                        eligibility = "INELIGIBLE_NUMERICAL_ARTIFACT"
                    elif cond == "c5":
                        on_disk_status = "AVAILABLE"
                        eligibility = "UNSUPPORTED_TWIN_PREGNANCY"
                    else:
                        on_disk_status = "AVAILABLE"
                        eligibility = "ELIGIBLE_SINGLE_FETUS"
                        
                    # 2. Historical Evaluation Domains
                    hist_domains = []
                    if key in hist_prefpga_full:
                        hist_domains.append("SW_Float_Initial_PC3")
                    if key in hist_prefpga_corr:
                        hist_domains.append("SW_Float_Proposed_Autocorr")
                    if key in hist_phase5:
                        hist_domains.append("BitAccurate_Phase5_L1")
                    if key in hist_phase4_hw:
                        hist_domains.append("Physical_FPGA_COM5")
                    hist_domain_str = "; ".join(hist_domains) if hist_domains else "UNTESTED_HISTORICALLY"
                    
                    # 3. Evaluate using frozen bit-accurate pipeline if available and valid
                    row_data = {
                        "record_id": rec_id,
                        "subject": sub,
                        "snr_db": snr_db,
                        "layout": lay,
                        "condition": cond,
                        "on_disk_status": on_disk_status,
                        "architectural_eligibility": eligibility,
                        "historical_eval_domains": hist_domain_str,
                        "frozen_bitaccurate_evaluated": False,
                        "pc_selected": -1,
                        "weights_q15": "[]",
                        "tp": 0,
                        "fp": 0,
                        "fn": 0,
                        "m_fp": 0,
                        "sensitivity_pct": 0.0,
                        "ppv_pct": 0.0,
                        "f1_pct": 0.0,
                        "fhr_mae_bpm": 0.0,
                        "maternal_suppression_db": 0.0,
                        "failure_mode": "NONE"
                    }
                    
                    if on_disk_status == "AVAILABLE":
                        case_data, status_msg = load_case_data(sub, snr, lay, cond)
                        if case_data is None:
                            row_data["on_disk_status"] = status_msg
                            row_data["failure_mode"] = status_msg
                            skipped_count += 1
                        else:
                            # Evaluate with frozen pipeline!
                            mix_4ch = case_data["mix_4ch"]
                            fecg_4ch = case_data["fecg_4ch"]
                            mecg_4ch = case_data["mecg_4ch"]
                            f_qrs = case_data["f_qrs"]
                            m_qrs = case_data["m_qrs"]
                            fhr_nom = case_data["fhr_nominal"]
                            n_samples = len(mix_4ch)
                            
                            x_q12 = np.clip(np.round(mix_4ch), -32768, 32767).astype(np.int64)
                            cal_len = min(2500, n_samples)
                            calibrator = HostSpatialCalibrator()
                            w_q15, pc_idx, conf_score, debug_info = calibrator.calibrate(mix_4ch[:cal_len], rule="autocorr")
                            
                            # Maternal suppression
                            w_float = w_q15 / 32768.0
                            m_proj = mecg_4ch @ w_float
                            p_m_in = np.mean(mecg_4ch[:, 0] ** 2) + 1e-12
                            p_m_out = np.mean(m_proj ** 2) + 1e-12
                            m_supp_db = 10.0 * np.log10(p_m_in / p_m_out)
                            
                            # Run frozen bit-accurate pipeline
                            res = run_bit_accurate_pipeline_final(x_q12, w_q15)
                            det_peaks = np.array(list(res.peaks), dtype=np.int64)
                            
                            f_eval = f_qrs[(f_qrs >= WARMUP_SAMPLES) & (f_qrs < n_samples)]
                            m_eval = m_qrs[(m_qrs >= WARMUP_SAMPLES) & (m_qrs < n_samples)]
                            d_eval = det_peaks[(det_peaks >= WARMUP_SAMPLES) & (det_peaks < n_samples)]
                            
                            tp, fp, fn = match_beats(f_eval, d_eval, fs=FS, tolerance_ms=50.0)
                            
                            # Maternal false alarms
                            det_matched = np.zeros(len(d_eval), dtype=bool)
                            for ri, r in enumerate(f_eval):
                                best_dist = TOL_SAMPLES + 1
                                best_di = -1
                                for di, d in enumerate(d_eval):
                                    if det_matched[di]:
                                        continue
                                    dist = abs(int(r) - int(d))
                                    if dist <= TOL_SAMPLES and dist < best_dist:
                                        best_dist = dist
                                        best_di = di
                                if best_di >= 0:
                                    det_matched[best_di] = True
                            fp_beats = d_eval[~det_matched]
                            m_tp, _, _ = match_beats(m_eval, fp_beats, fs=FS, tolerance_ms=50.0)
                            m_fp = m_tp
                            
                            sens = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
                            ppv = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
                            f1 = (2.0 * sens * ppv / (sens + ppv)) if (sens + ppv) > 0 else 0.0
                            
                            # FHR MAE
                            if len(d_eval) > 5:
                                rr = np.diff(d_eval)
                                fhr_inst = 60.0 * FS / rr
                                fhr_mae = float(np.mean(np.abs(fhr_inst - fhr_nom)))
                            else:
                                fhr_mae = abs(140.0 - fhr_nom)
                                
                            row_data["frozen_bitaccurate_evaluated"] = True
                            row_data["pc_selected"] = pc_idx
                            row_data["weights_q15"] = str(w_q15.tolist())
                            row_data["tp"] = tp
                            row_data["fp"] = fp
                            row_data["fn"] = fn
                            row_data["m_fp"] = m_fp
                            row_data["sensitivity_pct"] = round(sens, 2)
                            row_data["ppv_pct"] = round(ppv, 2)
                            row_data["f1_pct"] = round(f1, 2)
                            row_data["fhr_mae_bpm"] = round(fhr_mae, 2)
                            row_data["maternal_suppression_db"] = round(m_supp_db, 2)
                            
                            tested_count += 1
                            if tested_count % 100 == 0:
                                print(f"  Evaluated {tested_count} records... (Elapsed: {time.time()-t0:.1f}s)")
                    else:
                        row_data["failure_mode"] = eligibility
                        skipped_count += 1
                        
                    matrix_rows.append(row_data)

    df_out = pd.DataFrame(matrix_rows)
    df_out.to_csv(OUT_CSV, index=False)
    print(f"\nCoverage matrix generated: {OUT_CSV}")
    print(f"Total combinations evaluated in bit-accurate model: {tested_count}")
    print(f"Total skipped/ineligible: {skipped_count}")
    print(f"Total rows in matrix: {len(df_out)}")
    print(f"Total runtime: {time.time()-t0:.1f}s")
    
    # Summary statistics
    df_valid_single = df_out[df_out["architectural_eligibility"] == "ELIGIBLE_SINGLE_FETUS"]
    print("\n--- Eligible Single-Fetus Performance Summary ---")
    print(f"Records: {len(df_valid_single)}")
    print(f"Mean F1: {df_valid_single['f1_pct'].mean():.2f}%")
    print(f"Mean Sensitivity: {df_valid_single['sensitivity_pct'].mean():.2f}%")
    print(f"Mean PPV: {df_valid_single['ppv_pct'].mean():.2f}%")
    print(f"Mean Maternal Suppression: {df_valid_single['maternal_suppression_db'].mean():.2f} dB")
    print(f"Mean FHR MAE: {df_valid_single['fhr_mae_bpm'].mean():.2f} bpm")
    
    print("\n--- Breakdown by Layout (l1 - l5) for Eligible Single-Fetus ---")
    print(df_valid_single.groupby("layout")[["f1_pct", "sensitivity_pct", "ppv_pct", "fhr_mae_bpm", "maternal_suppression_db"]].mean())

    print("\n--- Breakdown by Condition (c0 - c4) for Eligible Single-Fetus ---")
    print(df_valid_single.groupby("condition")[["f1_pct", "sensitivity_pct", "ppv_pct", "fhr_mae_bpm", "maternal_suppression_db"]].mean())

    print("\n--- Breakdown by SNR for Eligible Single-Fetus ---")
    print(df_valid_single.groupby("snr_db")[["f1_pct", "sensitivity_pct", "ppv_pct", "fhr_mae_bpm", "maternal_suppression_db"]].mean())

if __name__ == "__main__":
    main()
