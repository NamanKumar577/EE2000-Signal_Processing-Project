"""
tools/validation/run_ablation_study.py
──────────────────────────────────────────────────────────────────────────────
Phase 6: Pipeline Stage Ablation Study.
Evaluates 10 configurations across a representative benchmark cohort:
  1. Full Pipeline (Baseline Reference)
  2. No HP1 Baseline Remover
  3. No LP40 Filter
  4. No Detector Bandpass Filter (BP Bypassed)
  5. Absolute Value instead of Squaring
  6. No Moving-Window Integrator (MWI Bypassed)
  7. Fixed Threshold (No Adaptive EMA)
  8. No Latency Compensation (Raw Uncompensated Timestamps)
  9. Spatial Beamforming Alone (No Preprocessing Filters)
 10. Filtering Alone without Spatial Beamforming (Single Lead 27)

Outputs:
  - Prints comparative metrics table
  - Generates validation/ablation/ABLATION_STUDY.md
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
import numpy as np
import wfdb
from scipy.signal import sosfilt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, CausalConfig, DEFAULT_CONFIG, run_causal,
    preprocess_causal, detect_causal, hp1_filter, lp_sos, det_sos,
    moving_sum_trailing, DetectionResult
)
from src.evaluation import compute_beat_metrics
from src.fhr import compute_fhr, compare_fhr

DATA_DIR = PROJECT_ROOT / "data" / "FECGSD" / "DESTINATION"
ABLATION_DIR = PROJECT_ROOT / "validation" / "ablation"
ABLATION_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS = [27, 26, 28, 25]
FS = 250

def load_case(sub: str, snr: str, cond: str):
    base_path = str(DATA_DIR / sub / snr / f"{sub}_{snr}_l1_{cond}")
    fecg = wfdb.rdrecord(base_path + "_fecg1").p_signal[:, CHANNELS]
    mecg = wfdb.rdrecord(base_path + "_mecg").p_signal[:, CHANNELS]
    n1 = wfdb.rdrecord(base_path + "_noise1").p_signal[:, CHANNELS]
    n2 = wfdb.rdrecord(base_path + "_noise2").p_signal[:, CHANNELS]
    mix = fecg + mecg + n1 + n2
    ref = np.sort(wfdb.rdann(base_path + "_fecg1", "qrs").sample)
    return mix, ref

def custom_detect(fecg, cfg=DEFAULT_CONFIG, bypass_bp=False, use_abs=False, bypass_mwi=False, fixed_thr=False, no_latency=False):
    x = np.asarray(fecg, dtype=np.float64)
    n = len(x)
    warm = cfg.warmup
    if n < warm + 4:
        return np.array([])
    
    # Detector BP
    if bypass_bp:
        x_bp = x.copy()
    else:
        x_bp = sosfilt(det_sos(cfg), x)
        
    # Energy transform
    if use_abs:
        x_energy = np.abs(x_bp)
    else:
        x_energy = x_bp * x_bp
        
    # MWI
    if bypass_mwi:
        x_int = x_energy.copy()
    else:
        x_int = moving_sum_trailing(x_energy, cfg.mwi_len)
        
    peak = float(np.max(x_int[:warm]))
    noise = float(np.mean(x_int[:warm]))
    if peak <= noise:
        return np.array([])
        
    a, b, c = x_int[:-2], x_int[1:-1], x_int[2:]
    cand = np.nonzero((a < b) & (b >= c))[0] + 1
    cand = cand[cand >= warm - 1]
    
    gain = 2.0 ** -cfg.level_shift
    abs_bp = np.abs(x_bp)
    raw_peaks = []
    last_m = -(10 ** 9)
    static_thr = 0.25 * peak + 0.75 * noise
    
    for m in cand:
        v = x_int[m]
        thr = static_thr if fixed_thr else (0.25 * peak + 0.75 * noise)
        if v > thr:
            if m - last_m >= cfg.refractory:
                n_decl = m + 1
                lo = max(0, n_decl - (cfg.loc_window - 1))
                r = lo + int(np.argmax(abs_bp[lo:n_decl + 1]))
                raw_peaks.append(r)
                last_m = m
                if not fixed_thr:
                    peak += (v - peak) * gain
        else:
            if not fixed_thr:
                noise += (v - noise) * gain
                
    raw = np.array(raw_peaks, dtype=int)
    if no_latency:
        return raw
    lat = cfg.latency() if not bypass_bp else 5  # group delay adjusted
    return np.maximum(raw - lat, 0)

def main():
    print("=" * 70)
    print("STARTING PHASE 6: PIPELINE STAGE ABLATION STUDY")
    print("=" * 70)
    
    test_cases = [
        ("sub01", "snr12dB", "c0"),
        ("sub01", "snr06dB", "c0"),
        ("sub01", "snr00dB", "c0"),
        ("sub01", "snr06dB", "c1"),
        ("sub06", "snr06dB", "c0"),
        ("sub04", "snr06dB", "c0"),
        ("sub10", "snr06dB", "c0"),
    ]
    
    cases_data = []
    for sub, snr, cond in test_cases:
        mix, ref = load_case(sub, snr, cond)
        bank = CalibrationBank(mix, DEFAULT_CONFIG, cal_seconds=0)
        j, _ = bank.select("pc3")
        w = bank.weights(j)
        cases_data.append((f"{sub}_{snr}_{cond}", mix, ref, w))
        
    ablation_defs = [
        ("1_full_baseline", "Full Pipeline (Baseline Reference)"),
        ("2_no_hp1", "No HP1 Baseline Remover"),
        ("3_no_lp40", "No LP40 Low-Pass Filter"),
        ("4_no_bp", "No Detector Bandpass Filter"),
        ("5_abs_instead_of_square", "Absolute Value instead of Square"),
        ("6_no_mwi", "No Moving Window Integrator (MWI)"),
        ("7_fixed_threshold", "Fixed Static Threshold (No EMA Adaptation)"),
        ("8_no_latency_comp", "No Latency Compensation"),
        ("9_spatial_only", "Spatial Beamformer Alone (Raw Projection)"),
        ("10_filter_only_single_ch", "Filtering Alone without Spatial Beamformer (Lead 27)")
    ]
    
    ablation_summary = []
    
    for abl_key, abl_name in ablation_defs:
        f1s, maes = [], []
        for rec_id, mix, ref, w in cases_data:
            proj = mix @ w
            
            if abl_key == "1_full_baseline":
                fecg = preprocess_causal(proj)
                peaks = detect_causal(fecg).peaks
            elif abl_key == "2_no_hp1":
                # Bypass HP1, apply LP40
                fecg = sosfilt(lp_sos(), proj)
                peaks = detect_causal(fecg).peaks
            elif abl_key == "3_no_lp40":
                # Apply HP1, bypass LP40
                fecg = hp1_filter(proj)
                peaks = detect_causal(fecg).peaks
            elif abl_key == "4_no_bp":
                fecg = preprocess_causal(proj)
                peaks = custom_detect(fecg, bypass_bp=True)
            elif abl_key == "5_abs_instead_of_square":
                fecg = preprocess_causal(proj)
                peaks = custom_detect(fecg, use_abs=True)
            elif abl_key == "6_no_mwi":
                fecg = preprocess_causal(proj)
                peaks = custom_detect(fecg, bypass_mwi=True)
            elif abl_key == "7_fixed_threshold":
                fecg = preprocess_causal(proj)
                peaks = custom_detect(fecg, fixed_thr=True)
            elif abl_key == "8_no_latency_comp":
                fecg = preprocess_causal(proj)
                peaks = custom_detect(fecg, no_latency=True)
            elif abl_key == "9_spatial_only":
                # Raw proj straight to detector
                peaks = detect_causal(proj).peaks
            elif abl_key == "10_filter_only_single_ch":
                # Lead 27
                lead27 = mix[:, 0]
                fecg = preprocess_causal(lead27)
                peaks = detect_causal(fecg).peaks
                
            m = compute_beat_metrics(ref, peaks, fs=FS)
            fc = compare_fhr(compute_fhr(peaks, fs=FS), ref, fs=FS)
            f1s.append(m.f1 or 0.0)
            if not np.isnan(fc.mean_abs_error_bpm):
                maes.append(fc.mean_abs_error_bpm)
                
        mean_f1 = float(np.mean(f1s)) * 100
        mean_mae = float(np.mean(maes)) if maes else 999.0
        ablation_summary.append({
            "key": abl_key,
            "name": abl_name,
            "mean_f1": round(mean_f1, 2),
            "mean_mae": round(mean_mae, 2)
        })
        
    base_f1 = ablation_summary[0]["mean_f1"]
    base_mae = ablation_summary[0]["mean_mae"]
    
    print("\n=== STAGE ABLATION SUMMARY ===")
    print(f"{'Stage Configuration':58s} {'Mean F1 (%)':>12s} {'Delta F1':>10s} {'FHR MAE':>10s} {'Delta MAE':>10s}")
    for row in ablation_summary:
        d_f1 = row["mean_f1"] - base_f1
        d_mae = row["mean_mae"] - base_mae
        row["delta_f1"] = round(d_f1, 2)
        row["delta_mae"] = round(d_mae, 2)
        print(f"{row['name']:58s} {row['mean_f1']:12.2f}% {d_f1:+9.2f}% {row['mean_mae']:10.2f} bpm {d_mae:+9.2f} bpm")
        
    return ablation_summary

if __name__ == "__main__":
    summary = main()
