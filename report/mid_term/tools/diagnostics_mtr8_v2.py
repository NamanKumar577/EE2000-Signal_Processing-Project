"""
diagnostics_mtr8_v2.py
Comprehensive diagnostic tool implementing all checks requested in MTR8_v2_audit_python_theory.md.
"""

import os
import glob
import numpy as np
import pandas as pd
from scipy import signal, stats
import wfdb

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'FECGSD', 'DESTINATION')
MEGA_CSV = os.path.join(PROJECT_ROOT, 'code', 'results', 'mega_benchmark_results.csv')

def run_diagnostics():
    print("=" * 80)
    print("MTR-8 V2 AUDIT DIAGNOSTICS")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. Lead Selection on Training Subjects sub01-sub07 only (S-01, G-03)
    # -------------------------------------------------------------------------
    print("\n--- 1. Lead Selection & FMR Topography (sub01-sub07 only) ---")
    train_subs = [f'sub0{i}' for i in range(1, 8)]
    fmr_per_sub = []
    
    for sub in train_subs:
        sub_dir = os.path.join(DATA_DIR, sub)
        fecg_files = glob.glob(os.path.join(sub_dir, '*_fecg1.hea'))
        sub_fmr = []
        for f_hea in fecg_files:
            base = f_hea.replace('_fecg1.hea', '')
            base_m = base + '_mecg'
            if os.path.exists(base + '_fecg1.dat') and os.path.exists(base_m + '.dat'):
                try:
                    f_sig = wfdb.rdrecord(base + '_fecg1').p_signal
                    m_sig = wfdb.rdrecord(base_m).p_signal
                    f_rms = np.sqrt(np.mean(f_sig**2, axis=0))
                    m_rms = np.sqrt(np.mean(m_sig**2, axis=0))
                    sub_fmr.append(f_rms / (m_rms + 1e-12))
                except Exception:
                    pass
        if sub_fmr:
            fmr_per_sub.append(np.mean(sub_fmr, axis=0))
            
    if fmr_per_sub:
        train_fmr = np.mean(fmr_per_sub, axis=0) # shape (34,)
        print(f"Computed FMR across {len(fmr_per_sub)} training subjects (sub01-sub07).")
        ranked_0based = np.argsort(train_fmr)[::-1]
        print(f"Top 10 leads (0-based): {ranked_0based[:10].tolist()}")
        print(f"Top 10 leads (1-based): {[r+1 for r in ranked_0based[:10]]}")
        print(f"Lead 27 (0-based) FMR: {train_fmr[27]:.4f} (Peak lead is {ranked_0based[0]} with FMR {train_fmr[ranked_0based[0]]:.4f})")
        print(f"4-Ch Sub-array [27, 26, 28, 25] (0-based) FMRs: {train_fmr[[27, 26, 28, 25]].round(4).tolist()}")
        print(f"Thoracic leads 32, 33 (0-based) FMRs: {train_fmr[[32, 33]].round(4).tolist()}")

    # -------------------------------------------------------------------------
    # 2. PCA Correlation and Polarity Audit (S-03)
    # -------------------------------------------------------------------------
    print("\n--- 2. PCA Correlation & Polarity Audit in mega_benchmark_results.csv ---")
    mega = pd.read_csv(MEGA_CSV)
    pca = mega[mega['method'] == 'Spatial_PCA_4ch']
    
    pos_corr_frac = (pca['correlation'] > 0).mean() * 100
    mean_corr = pca['correlation'].mean()
    mean_abs_corr = pca['correlation'].abs().mean()
    print(f"Spatial PCA (4-Ch) 250 records:")
    print(f"  Positive correlation fraction: {pos_corr_frac:.1f}%")
    print(f"  Raw Mean Correlation: {mean_corr:.3f}")
    print(f"  Mean Absolute Correlation |corr|: {mean_abs_corr:.3f}")
    print("  Per-subject mean correlation:")
    for sub, grp in pca.groupby('sub_id'):
        print(f"    {sub}: raw corr = {grp['correlation'].mean():.3f}, |corr| = {grp['correlation'].abs().mean():.3f}, pos% = {(grp['correlation'] > 0).mean()*100:.1f}%")

    # -------------------------------------------------------------------------
    # 3. FHR MAE and Clinical Agreement Breakdown (S-04)
    # -------------------------------------------------------------------------
    print("\n--- 3. FHR Performance Breakdown by Condition and SNR ---")
    print("Spatial PCA (4-Ch) by Condition:")
    cond_stats = pca.groupby('case_id').agg(
        f1=('f1', lambda x: x.mean() * 100),
        mae=('fhr_mae_bpm', 'mean'),
        rmse=('fhr_rmse_bpm', 'mean'),
        agr=('fhr_mae_bpm', lambda x: (x <= 5.0).mean() * 100)
    ).round(2)
    print(cond_stats)
    
    print("\nSpatial PCA (4-Ch) by SNR Tier:")
    snr_stats = pca.groupby('snr_db').agg(
        f1=('f1', lambda x: x.mean() * 100),
        mae=('fhr_mae_bpm', 'mean'),
        rmse=('fhr_rmse_bpm', 'mean'),
        agr=('fhr_mae_bpm', lambda x: (x <= 5.0).mean() * 100)
    ).round(2)
    print(snr_stats)

    print("\nDeep U-Net (4-Ch) by Condition:")
    unet4 = mega[mega['method'] == 'Deep_UNet_4ch']
    u_cond = unet4.groupby('case_id').agg(
        f1=('f1', lambda x: x.mean() * 100),
        mae=('fhr_mae_bpm', 'mean'),
        rmse=('fhr_rmse_bpm', 'mean'),
        agr=('fhr_mae_bpm', lambda x: (x <= 5.0).mean() * 100)
    ).round(2)
    print(u_cond)

    # -------------------------------------------------------------------------
    # 4. Database Size Arithmetic (S-06)
    # -------------------------------------------------------------------------
    print("\n--- 4. Database Size Arithmetic ---")
    # 250 records x 75,000 samples x 34 channels
    n_samples_total = 250 * 75000 * 34
    size_int16_gb = (n_samples_total * 2) / (1024**3)
    size_float32_gb = (n_samples_total * 4) / (1024**3)
    size_float64_gb = (n_samples_total * 8) / (1024**3)
    print(f"Total scalar points: {n_samples_total:,}")
    print(f"At 16-bit int (2 bytes/sample): {size_int16_gb:.2f} GiB ({n_samples_total*2/1e9:.2f} GB)")
    print(f"At 32-bit float (4 bytes/sample): {size_float32_gb:.2f} GiB ({n_samples_total*4/1e9:.2f} GB)")
    print(f"At 64-bit float (8 bytes/sample): {size_float64_gb:.2f} GiB ({n_samples_total*8/1e9:.2f} GB)")
    
    # Check actual size on disk of DESTINATION
    dat_files = glob.glob(os.path.join(DATA_DIR, 'sub*', '*.dat'))
    total_disk_bytes = sum(os.path.getsize(f) for f in dat_files)
    print(f"Actual .dat files on disk in FECGSD/DESTINATION: {len(dat_files)} files, {total_disk_bytes / (1024**3):.2f} GiB ({total_disk_bytes / 1e9:.2f} GB)")

    # -------------------------------------------------------------------------
    # 5. Overlap Probability Derivations (S-07)
    # -------------------------------------------------------------------------
    print("\n--- 5. Overlap Probability Derivations ---")
    T_m, T_f = 800.0, 430.0 # ms
    w_m, w_f = 90.0, 50.0   # ms
    prob_fetal_overlap = (w_m + w_f) / T_m
    prob_maternal_overlap = (w_m + w_f) / T_f
    prob_complete_containment = (w_m - w_f) / T_m
    print(f"Fetal beat overlaps maternal QRS: (w_m + w_f)/T_m = ({w_m}+{w_f})/{T_m} = {prob_fetal_overlap*100:.1f}%")
    print(f"Maternal beat overlaps fetal QRS: (w_m + w_f)/T_f = ({w_m}+{w_f})/{T_f} = {prob_maternal_overlap*100:.1f}%")
    print(f"Fetal QRS fully contained in maternal QRS: (w_m - w_f)/T_m = ({w_m}-{w_f})/{T_m} = {prob_complete_containment*100:.1f}%")

    # -------------------------------------------------------------------------
    # 6. Filter Specifications & Group Delay (S-10)
    # -------------------------------------------------------------------------
    print("\n--- 6. Filter Specifications & Frequency Response ---")
    fs = 250
    # Check what scipy produces for 4th order bandpass
    sos_bp = signal.butter(4, [0.5, 40], btype='bandpass', fs=fs, output='sos')
    print(f"signal.butter(4, [0.5, 40], 'bandpass'): shape = {sos_bp.shape} -> {sos_bp.shape[0]} SOS sections ({sos_bp.shape[0]*2}th order overall)")
    
    freqs = np.array([0.1, 0.5, 10.0, 20.0, 40.0, 50.0, 60.0])
    _, h_bp = signal.sosfreqz(sos_bp, worN=freqs, fs=fs)
    gain_db = 20 * np.log10(np.abs(h_bp))
    for f, g in zip(freqs, gain_db):
        print(f"  Freq {f:4.1f} Hz: {g:6.1f} dB")
        
    # Group delay in passband
    b, a = signal.sos2tf(sos_bp)
    fg = np.array([5, 10, 15, 20, 25, 30, 35])
    _, gd = signal.group_delay((b, a), w=fg, fs=fs)
    print("Group delay in QRS passband (ms):")
    for f, d in zip(fg, gd / fs * 1000):
        print(f"  {f:2d} Hz: {d:.1f} ms ({d/1000*fs:.1f} samples)")

    # -------------------------------------------------------------------------
    # 7. Null Depth Equation Verification (T-06)
    # -------------------------------------------------------------------------
    print("\n--- 7. Null Depth Verification (Eq. 10) ---")
    B, C = 16, 4
    null_depth_16 = 20 * np.log10(np.sqrt(12) * (2**(B - 1)) / np.sqrt(C))
    null_depth_12 = 20 * np.log10(np.sqrt(12) * (2**(12 - 1)) / np.sqrt(C))
    null_depth_10 = 20 * np.log10(np.sqrt(12) * (2**(10 - 1)) / np.sqrt(C))
    print(f"Eq. (10) Null Depth for B=16, C=4: {null_depth_16:.2f} dB (Paper previously said 93.3 dB)")
    print(f"Eq. (10) Null Depth for B=12, C=4: {null_depth_12:.2f} dB")
    print(f"Eq. (10) Null Depth for B=10, C=4: {null_depth_10:.2f} dB")

    # -------------------------------------------------------------------------
    # 8. Fixed-Point Model Rounding in fixed_point_model.py (T-07)
    # -------------------------------------------------------------------------
    print("\n--- 8. Checking code in fixed_point_model.py ---")
    fp_path = os.path.join(PROJECT_ROOT, 'code', 'src', 'fixed_point_model.py')
    if os.path.exists(fp_path):
        with open(fp_path, 'r', encoding='utf-8') as f:
            code = f.read()
        for term in ['round', 'floor', 'clip', 'Q1.15', '32768', '32767']:
            matches = [line.strip() for line in code.split('\n') if term in line]
            print(f"  Term '{term}' matches in fixed_point_model.py: {len(matches)} occurrences")
            if matches:
                print(f"    Example: {matches[0]}")

    print("\nDiagnostics complete!")

if __name__ == '__main__':
    run_diagnostics()
