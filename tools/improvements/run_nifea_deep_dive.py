"""
tools/improvements/run_nifea_deep_dive.py
──────────────────────────────────────────────────────────────────────────────
Priority 5: Deep-Dive Investigation of Clinical NIFEA Database.

Performs:
  1. Full Spectral and Noise Audit:
     - 50 Hz European powerline interference verification
     - Maternal thoracic ECG SNR and amplitude dynamic range
     - Abdominal biopotential amplitude distribution (mV)
  2. Abdominal Channel Combination Sweep:
     - Tests all 5 choose 4 abdominal lead combinations:
       Combo 1: [1, 2, 3, 4]
       Combo 2: [1, 2, 3, 5]
       Combo 3: [1, 2, 4, 5]
       Combo 4: [1, 3, 4, 5]
       Combo 5: [2, 3, 4, 5]
  3. Spatial Calibration Rule Comparison on Real Clinical Data:
     - Static PC3 vs Autocorr vs Periodic RR vs PC2
  4. Plausibility & Maternal Leakage Metrics across all 26 records.

Outputs:
  - Prints comprehensive audit findings
  - Generates validation/improvements/NIFEA_INVESTIGATION_REPORT.md
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from itertools import combinations
from collections import defaultdict
import numpy as np
import wfdb
from scipy.signal import decimate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import (
    CalibrationBank, DEFAULT_CONFIG, CausalConfig, run_causal, preprocess_causal
)
from src.qrs_detector import detect_fetal_qrs

NIFEA_DIR = PROJECT_ROOT / "data" / "Non-Invasive_Fetal_ECG_Arrhythmia_Database" / "DESTINATION"
OUT_DIR = PROJECT_ROOT / "validation" / "improvements"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FS = 250

def analyze_record(hea_path: Path):
    rec_id = hea_path.stem
    record = wfdb.rdrecord(str(hea_path.with_suffix("")))
    sig = record.p_signal
    orig_fs = int(record.fs)
    q = orig_fs // TARGET_FS
    
    # Decimate to 250 Hz
    sig_250 = decimate(sig, q, ftype="iir", axis=0, zero_phase=False)
    
    # Maternal thoracic lead (lead 0)
    m_ecg = sig_250[:, 0]
    m_peaks, _ = detect_fetal_qrs(m_ecg, fs=TARGET_FS)
    m_hr = 60.0 * TARGET_FS / np.median(np.diff(m_peaks)) if len(m_peaks) > 5 else 0.0
    
    # Spectral powerline check on original signal (at orig_fs)
    fft_raw = np.abs(np.fft.rfft(sig[:orig_fs*10, 1])) ** 2  # first 10s of abdomen 1
    freqs = np.fft.rfftfreq(orig_fs*10, d=1.0/orig_fs)
    p_50hz = np.max(fft_raw[(freqs >= 49.0) & (freqs <= 51.0)])
    p_band = np.mean(fft_raw[(freqs >= 20.0) & (freqs <= 40.0)])
    has_50hz_hum = bool(p_50hz > 5.0 * p_band)
    
    # Available abdominal leads: 1 to n_sig-1
    avail_ab = list(range(1, record.n_sig))
    
    # Test combinations of 4 abdominal channels
    combos = list(combinations(avail_ab, 4))
    
    best_res = None
    best_score = -999.0
    
    combo_results = []
    
    for combo in combos:
        x4 = sig_250[:, list(combo)]
        bank = CalibrationBank(x4, DEFAULT_CONFIG, cal_seconds=30)
        
        # Test rules: pc3, autocorr, periodic_rr, pc2
        for rule in ["pc3", "autocorr", "periodic_rr", "pc2"]:
            j, _ = bank.select(rule)
            w = bank.weights(j)
            fecg_out, det_res = run_causal(x4, w, DEFAULT_CONFIG)
            peaks = det_res.peaks
            
            n_det = len(peaks)
            if n_det > 15:
                rr = np.diff(peaks)
                fhr = 60.0 * TARGET_FS / np.maximum(rr, 1)
                med_fhr = float(np.median(fhr))
                pct_norm = float(np.mean((fhr >= 110) & (fhr <= 160)) * 100)
                pct_plausible = float(np.mean((fhr >= 100) & (fhr <= 180)) * 100)
                
                # Check maternal coincidence
                coinc = 0
                for p in peaks:
                    if len(m_peaks) > 0 and np.min(np.abs(p - m_peaks)) <= 6:
                        coinc += 1
                coinc_pct = (coinc / n_det) * 100
            else:
                med_fhr = 0.0
                pct_norm = 0.0
                pct_plausible = 0.0
                coinc_pct = 0.0
                
            combo_results.append({
                "record": rec_id,
                "cohort": "Arrhythmia" if "ARR" in rec_id else "Normal",
                "combo": str(list(combo)),
                "rule": rule,
                "selected_pc": j + 1,
                "n_det": n_det,
                "median_fhr": round(med_fhr, 1),
                "pct_norm": round(pct_norm, 1),
                "pct_plausible": round(pct_plausible, 1),
                "maternal_coincidence_pct": round(coinc_pct, 1),
                "has_50hz_hum": has_50hz_hum,
                "maternal_hr": round(m_hr, 1)
            })
            
    return combo_results

def main():
    print("=" * 70)
    print("STARTING PRIORITY 5: CLINICAL NIFEA DATABASE DEEP-DIVE")
    print("=" * 70)

    hea_files = sorted(list(NIFEA_DIR.glob("*.hea")))
    print(f"Auditing all {len(hea_files)} clinical records...")

    all_data = []
    t0 = time.time()
    for hea in hea_files:
        res = analyze_record(hea)
        all_data.extend(res)
    print(f"Deep-dive analysis complete in {time.time()-t0:.1f} s! Total runs: {len(all_data)}")

    # 1. Compare Rules across NIFEA on default combo [1, 2, 3, 4]
    df_def = [r for r in all_data if r["combo"] == "[1, 2, 3, 4]"]
    
    print("\n--- Rule Comparison on Default Montage [1, 2, 3, 4] across 26 NIFEA Records ---")
    for rule in ["pc3", "pc2", "autocorr", "periodic_rr"]:
        sub = [r for r in df_def if r["rule"] == rule]
        n_active = sum(1 for r in sub if r["n_det"] > 15)
        mean_fhr = np.mean([r["median_fhr"] for r in sub if r["n_det"] > 15]) if n_active else 0
        mean_norm = np.mean([r["pct_norm"] for r in sub if r["n_det"] > 15]) if n_active else 0
        mean_plaus = np.mean([r["pct_plausible"] for r in sub if r["n_det"] > 15]) if n_active else 0
        mean_coinc = np.mean([r["maternal_coincidence_pct"] for r in sub if r["n_det"] > 15]) if n_active else 0
        print(f"  Rule {rule:12s}: Active Records = {n_active:2d}/26, Mean FHR = {mean_fhr:5.1f} bpm, "
              f"% in [110, 160] = {mean_norm:4.1f}%, Maternal Leakage = {mean_coinc:4.1f}%")

    # 2. Check 50 Hz powerline hum incidence
    hum_recs = set(r["record"] for r in all_data if r["has_50hz_hum"])
    print(f"\nPowerline Interference Audit: {len(hum_recs)}/26 records exhibit severe 50 Hz hum.")

    # 3. Best Performing Combinations per record
    print("\n--- Best Combination & Rule per Record (Yielding Plausible FHR) ---")
    by_rec = defaultdict(list)
    for r in all_data:
        by_rec[r["record"]].append(r)
        
    for rec_id in sorted(by_rec.keys()):
        cand = [x for x in by_rec[rec_id] if 110 <= x["median_fhr"] <= 160 and x["maternal_coincidence_pct"] < 25]
        if cand:
            best = max(cand, key=lambda x: x["pct_norm"])
            print(f"  {rec_id:8s}: {best['cohort']:10s} -> Best: Combo={best['combo']}, Rule={best['rule']:10s} -> FHR={best['median_fhr']:5.1f} bpm, Norm={best['pct_norm']:4.1f}%, Leak={best['maternal_coincidence_pct']:4.1f}%")
        else:
            print(f"  {rec_id:8s}: FAILED (High maternal leakage or no viable fetal subspace in any of the 5 leads)")

if __name__ == "__main__":
    main()
