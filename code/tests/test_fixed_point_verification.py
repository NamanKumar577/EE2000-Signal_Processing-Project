"""
code/tests/test_fixed_point_verification.py
──────────────────────────────────────────────────────────────────────────────
Automated test suite and quantization verification: Floating-Point vs Fixed-Point.

Owner: Vivek
Validates: Spartan-7 fixed-point model against golden floating-point reference.
Generates: FPGA stimulus and golden output test vectors.
"""

import os
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loader import load_test_case
from src.mixture import build_mixture
from src.preprocessing import preprocess
from src.qrs_detector import detect_fetal_qrs
from src.fhr import compute_fhr, compare_fhr
from src.evaluation import compute_beat_metrics, compute_waveform_metrics
from src.methods.alternative import AlternativeExtractor
from src.fixed_point_model import FixedPointAlternativeExtractor, to_fixed

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_VECTORS_DIR = Path(__file__).resolve().parents[1] / "results" / "fpga_test_vectors"

TC1_RECORDS = {
    "fecg1": "test/test1/sub01_snr12dB_l1_c0_fecg1",
    "mecg":  "test/test1/sub01_snr12dB_l1_c0_mecg",
    "noise1": "test/test1/sub01_snr12dB_l1_c0_noise1",
    "noise2": "test/test1/sub01_snr12dB_l1_c0_noise2",
}


def test_fixed_point_vs_floating_point_on_tc1():
    """Verify fixed-point Q1.15 quantization impact on TC1."""
    # 1. Load & Preprocess TC1
    tc = load_test_case("TC1", TC1_RECORDS, repo_root=str(REPO_ROOT))
    mix = build_mixture(tc.mecg, tc.fecg_ref, tc.noise1, tc.noise2, fs=tc.fs)
    aecg_pre = preprocess(mix.aecg, fs=tc.fs)

    # 2. Run Floating-point golden model
    float_ext = AlternativeExtractor(fs=tc.fs)
    fecg_float, meta_float = float_ext.run(aecg_pre)

    # 3. Run Fixed-point Spartan-7 hardware model
    fixed_ext = FixedPointAlternativeExtractor(fs=tc.fs, frac_bits=12)
    fecg_fixed, meta_fixed = fixed_ext.run(aecg_pre)

    # 4. Waveform quantization metrics
    quant_error = fecg_float - fecg_fixed
    signal_power = float(np.mean(fecg_float ** 2))
    noise_power = float(np.mean(quant_error ** 2))
    sqnr_db = 10.0 * np.log10(signal_power / (noise_power + 1e-12))
    rmse_diff = float(np.sqrt(noise_power))

    # 5. QRS Detection Comparison
    peaks_float, _ = detect_fetal_qrs(fecg_float, fs=tc.fs)
    peaks_fixed, _ = detect_fetal_qrs(fecg_fixed, fs=tc.fs)

    bm_float = compute_beat_metrics(tc.fecg_qrs_samples, peaks_float, fs=tc.fs)
    bm_fixed = compute_beat_metrics(tc.fecg_qrs_samples, peaks_fixed, fs=tc.fs)

    # FHR Comparison
    fhr_float = compute_fhr(peaks_float, fs=tc.fs)
    fhr_fixed = compute_fhr(peaks_fixed, fs=tc.fs)
    cmp_float = compare_fhr(fhr_float, tc.fecg_qrs_samples, fs=tc.fs)
    cmp_fixed = compare_fhr(fhr_fixed, tc.fecg_qrs_samples, fs=tc.fs)

    print("\n" + "="*70)
    print("  SOFTWARE-TO-HARDWARE FIXED-POINT VERIFICATION (TC1)")
    print("="*70)
    print(f"  Signal-to-Quantization-Noise Ratio (SQNR): {sqnr_db:.2f} dB")
    print(f"  Quantization Error RMSE                 : {rmse_diff:.6f}")
    print(f"  Floating-point F1-score                 : {bm_float.f1:.4f}")
    print(f"  Fixed-point (Q1.15) F1-score            : {bm_fixed.f1:.4f}")
    print(f"  Floating-point FHR MAE                  : {cmp_float.mean_abs_error_bpm:.2f} bpm")
    print(f"  Fixed-point FHR MAE                     : {cmp_fixed.mean_abs_error_bpm:.2f} bpm")
    print("="*70)

    # Assertions: Quantization must maintain stable detection
    assert np.all(np.isfinite(fecg_fixed))
    assert len(fecg_fixed) == len(aecg_pre)
    assert bm_fixed.f1 > 0.60, f"Fixed-point F1 {bm_fixed.f1} dropped too low"

    # 6. Save FPGA Test Vectors (First 5000 samples = 20 seconds)
    TEST_VECTORS_DIR.mkdir(parents=True, exist_ok=True)
    n_vec = 5000
    x_stimulus_q = to_fixed(aecg_pre[:n_vec] * (2.0 / np.std(aecg_pre)), frac_bits=12, word_len=16)
    y_golden_q = to_fixed(fecg_fixed[:n_vec] * 1000.0, frac_bits=12, word_len=16)

    # Hex test vector for Vivado $readmemh
    hex_path = TEST_VECTORS_DIR / "input_stimulus_tc1_hex.txt"
    with open(hex_path, "w") as f:
        for val in x_stimulus_q:
            # 16-bit signed hex
            u16 = int(val) & 0xFFFF
            f.write(f"{u16:04X}\n")

    # Golden reference output
    golden_path = TEST_VECTORS_DIR / "golden_output_fecg_tc1_hex.txt"
    with open(golden_path, "w") as f:
        for val in y_golden_q:
            u16 = int(val) & 0xFFFF
            f.write(f"{u16:04X}\n")

    # Reference peak sample indices
    peaks_path = TEST_VECTORS_DIR / "expected_fetal_peaks_tc1.txt"
    valid_p = [p for p in peaks_fixed if p < n_vec]
    with open(peaks_path, "w") as f:
        for p in valid_p:
            f.write(f"{p}\n")

    print(f"\n  [VECTORS SAVED] {n_vec} vectors written to {TEST_VECTORS_DIR}")


if __name__ == "__main__":
    test_fixed_point_vs_floating_point_on_tc1()
