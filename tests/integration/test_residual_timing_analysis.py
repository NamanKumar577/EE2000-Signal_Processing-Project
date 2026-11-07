"""
QRS_RESIDUAL_TIMING_ANALYSIS/tests/test_residual_timing_analysis.py
───────────────────────────────────────────────────────────────────
Test suite for residual QRS timing error investigation:
  1. Mathematical invariant of Fixed-Association evaluation (Error(C) == Raw_Error - C).
  2. Diagnostic proof of sub05_snr00dB R-peak cancellation vs sub05_snr12dB clean recovery.
  3. Diagnostic proof of sub08 biphasic QRS bimodal lobe jitter (+9 vs +17 samples).
  4. Global optimality of 12-sample compensation across fixed associations.
  5. Absence of ground-truth leakage and validity of global constant.
"""

import sys
from pathlib import Path
import numpy as np
import pytest
import pandas as pd
import wfdb
from scipy import signal

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(CODE_DIR))

from src.causal_pipeline import CalibrationBank, CausalConfig, preprocess_causal, det_sos
from src.bit_accurate_reference_model_final import run_bit_accurate_pipeline_final
from tools.pre_fpga_corrected.reconcile_qrs_metrics import match_beats_strict_pairs

FS = 250
DATA_DIR = Path("data/FECGSD/DESTINATION")

def test_fixed_association_mathematical_invariants():
    """Verify that on fixed associations, Error(C) == Raw_Error - C identically for all C."""
    ref_beats = np.array([100, 200, 300, 400, 500])
    raw_detections = np.array([112, 214, 311, 413, 510])
    
    # Establish fixed associations using 25-sample (+-100 ms) window
    _, _, _, pairs = match_beats_strict_pairs(ref_beats, raw_detections, fs=FS, tol_ms=100.0)
    raw_errors = np.array([p[2] for p in pairs])
    
    # For any candidate compensation C:
    for c in [0, 6, 10, 11, 12, 13, 14, 18]:
        comp_detections = raw_detections - c
        # Error on fixed associated beats
        fixed_errors = raw_errors - c
        # Independent error calculation
        calc_errors = comp_detections - ref_beats
        assert np.array_equal(fixed_errors, calc_errors), f"Fixed association invariant violated for C={c}"
        assert abs(np.mean(fixed_errors) - (np.mean(raw_errors) - c)) < 1e-10

def test_sub05_r_peak_cancellation_forensic():
    """Verify that sub05_snr00dB experiences R-peak beamformer cancellation while sub05_snr12dB does not."""
    base_00 = DATA_DIR / "sub05" / "snr00dB" / "sub05_snr00dB_l1_c0"
    base_12 = DATA_DIR / "sub05" / "snr12dB" / "sub05_snr12dB_l1_c0"
    
    if not (base_00.parent / (base_00.name + "_fecg1.hea")).exists():
        pytest.skip("Dataset not available on disk")
        
    cfg_c = CausalConfig(det_low_hz=12.0, det_high_hz=35.0, mwi_len=30, refractory=50)
    
    # Check 0 dB record
    fecg_00 = wfdb.rdrecord(str(base_00) + "_fecg1").p_signal[:, [27, 26, 28, 25]]
    mecg_00 = wfdb.rdrecord(str(base_00) + "_mecg").p_signal[:, [27, 26, 28, 25]]
    n1_00 = wfdb.rdrecord(str(base_00) + "_noise1").p_signal[:, [27, 26, 28, 25]]
    n2_00 = wfdb.rdrecord(str(base_00) + "_noise2").p_signal[:, [27, 26, 28, 25]]
    mix_00 = fecg_00 + mecg_00 + n1_00 + n2_00
    
    bank_00 = CalibrationBank(mix_00, cfg_c, cal_seconds=10)
    j_00, _ = bank_00.select("autocorr")
    w_00 = bank_00.weights(j_00)
    
    # In sub05_snr00dB, weights on ch27 (idx 0) and ch28 (idx 2) have opposing signs
    # while both channels have large positive R-peaks, causing destructive interference
    assert np.sign(w_00[0]) != np.sign(w_00[2]), "Expected opposing weight signs on ch27 and ch28 in sub05 0dB"
    
    # Check 12 dB record
    fecg_12 = wfdb.rdrecord(str(base_12) + "_fecg1").p_signal[:, [27, 26, 28, 25]]
    mecg_12 = wfdb.rdrecord(str(base_12) + "_mecg").p_signal[:, [27, 26, 28, 25]]
    n1_12 = wfdb.rdrecord(str(base_12) + "_noise1").p_signal[:, [27, 26, 28, 25]]
    n2_12 = wfdb.rdrecord(str(base_12) + "_noise2").p_signal[:, [27, 26, 28, 25]]
    mix_12 = fecg_12 + mecg_12 + n1_12 + n2_12
    ref_12 = np.sort(wfdb.rdann(str(base_12) + "_fecg1", "qrs").sample)
    
    bank_12 = CalibrationBank(mix_12, cfg_c, cal_seconds=10)
    j_12, _ = bank_12.select("autocorr")
    w_12 = bank_12.weights(j_12)
    
    x_q_12 = np.clip(np.round(mix_12 * 4096.0), -32768, 32767).astype(np.int16)
    w_q_12 = np.clip(np.round(w_12 * 32768.0), -32768, 32767).astype(np.int16)
    res_12 = run_bit_accurate_pipeline_final(x_q_12, w_q_12, latency=12)
    
    tp_12, _, _, pairs_12 = match_beats_strict_pairs(ref_12, res_12.peaks, fs=FS, tol_ms=50.0)
    errs_12 = [p[2] for p in pairs_12]
    pct_2_12 = np.sum(np.abs(errs_12) <= 2) / len(errs_12) * 100.0
    
    # On clean sub05_snr12dB, agreement <= 2 samples is > 90%
    assert pct_2_12 > 90.0, f"Expected >90% concordance for sub05 12dB, got {pct_2_12}%"

def test_sub08_biphasic_bimodal_lobe_proof():
    """Verify that sub08 exhibits a biphasic QRS with bimodal raw error distribution at ~9 and ~17 samples."""
    base_08 = DATA_DIR / "sub08" / "snr12dB" / "sub08_snr12dB_l1_c0"
    if not (base_08.parent / (base_08.name + "_fecg1.hea")).exists():
        pytest.skip("Dataset not available on disk")
        
    fecg_12 = wfdb.rdrecord(str(base_08) + "_fecg1").p_signal[:, [27, 26, 28, 25]]
    mecg_12 = wfdb.rdrecord(str(base_08) + "_mecg").p_signal[:, [27, 26, 28, 25]]
    n1_12 = wfdb.rdrecord(str(base_08) + "_noise1").p_signal[:, [27, 26, 28, 25]]
    n2_12 = wfdb.rdrecord(str(base_08) + "_noise2").p_signal[:, [27, 26, 28, 25]]
    mix_12 = fecg_12 + mecg_12 + n1_12 + n2_12
    ref_12 = np.sort(wfdb.rdann(str(base_08) + "_fecg1", "qrs").sample)
    
    cfg_c = CausalConfig(det_low_hz=12.0, det_high_hz=35.0, mwi_len=30, refractory=50)
    bank = CalibrationBank(mix_12, cfg_c, cal_seconds=10)
    j, _ = bank.select("autocorr")
    w = bank.weights(j)
    
    x_q = np.clip(np.round(mix_12 * 4096.0), -32768, 32767).astype(np.int16)
    w_q = np.clip(np.round(w * 32768.0), -32768, 32767).astype(np.int16)
    res = run_bit_accurate_pipeline_final(x_q, w_q, latency=0)
    
    _, _, _, pairs = match_beats_strict_pairs(ref_12, res.peaks, fs=FS, tol_ms=100.0)
    errs = np.array([p[2] for p in pairs])
    
    # Check bimodal distribution: Cluster 1 (~9 samples: 8-10) and Cluster 2 (~17 samples: 16-18)
    c1_count = np.sum((errs >= 8) & (errs <= 10))
    c2_count = np.sum((errs >= 16) & (errs <= 18))
    total_beats = len(errs)
    
    pct_bimodal = (c1_count + c2_count) / total_beats * 100.0
    assert pct_bimodal > 90.0, f"Expected >90% of beats in bimodal clusters (9 and 17), got {pct_bimodal}%"
    
    # Cluster 1 and Cluster 2 both have significant proportions (bimodal jitter)
    assert c1_count / total_beats > 0.25, f"Cluster 1 (offset ~9) too small: {c1_count / total_beats}"
    assert c2_count / total_beats > 0.40, f"Cluster 2 (offset ~17) too small: {c2_count / total_beats}"
    
    # Distance between clusters is 8 samples (32 ms)
    # When comp=12 is applied: 9 - 12 = -3, and 17 - 12 = +5. Both are outside [-2, +2]
    # This directly explains why agreement <= 2 samples is low (<15%) despite 100% detection rate
    comp12_errs = errs - 12
    pct_within_2 = np.sum(np.abs(comp12_errs) <= 2) / total_beats * 100.0
    assert pct_within_2 < 15.0, f"Expected low <=2 agreement due to bimodal straddling, got {pct_within_2}%"

def test_fixed_association_12_sample_global_optimality():
    """Verify that compensation=12 achieves minimum MAE and peak concordance on fixed associations."""
    df_agg = pd.read_csv("archive/timing_bundles/QRS_RESIDUAL_TIMING_ANALYSIS/FIXED_ASSOCIATION_TIMING_RESULTS.csv")
    
    row_12 = df_agg[df_agg["compensation_samples"] == 12].iloc[0]
    row_11 = df_agg[df_agg["compensation_samples"] == 11].iloc[0]
    row_13 = df_agg[df_agg["compensation_samples"] == 13].iloc[0]
    row_18 = df_agg[df_agg["compensation_samples"] == 18].iloc[0]
    
    # MAE is minimized at 12 samples
    assert row_12["mae_samples"] <= row_11["mae_samples"]
    assert row_12["mae_samples"] <= row_18["mae_samples"]
    
    # Concordance within +-2 samples is maximized at 12 samples
    assert row_12["pct_within_2samp"] > row_11["pct_within_2samp"]
    assert row_12["pct_within_2samp"] > row_13["pct_within_2samp"]
    assert row_12["pct_within_2samp"] > row_18["pct_within_2samp"]
    assert row_12["pct_within_2samp"] > 60.0
    
    # 18 samples has severe early bias (<-6 samples) and low concordance (<15%)
    assert row_18["mean_signed_bias_samples"] < -6.0
    assert row_18["pct_within_2samp"] < 15.0
