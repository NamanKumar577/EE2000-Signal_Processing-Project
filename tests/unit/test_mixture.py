"""
tests/test_mixture.py
──────────────────────────────────────────────────────────────────────────────
Tests for src/mixture.py — mixture construction and SNR validation.

Owner    : Vivek
Run from the code/ directory:
    python -m pytest tests/test_mixture.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mixture import build_mixture, check_mixture_snr, _power_ratio_db
from src.data_loader import load_test_case

REPO_ROOT = Path(__file__).resolve().parents[2]

TC1_RECORDS = {
    "fecg1": "data/FECGSD/DESTINATION/sub01/snr12dB/sub01_snr12dB_l1_c0_fecg1",
    "mecg":  "data/FECGSD/DESTINATION/sub01/snr12dB/sub01_snr12dB_l1_c0_mecg",
    "noise1": "data/FECGSD/DESTINATION/sub01/snr12dB/sub01_snr12dB_l1_c0_noise1",
    "noise2": "data/FECGSD/DESTINATION/sub01/snr12dB/sub01_snr12dB_l1_c0_noise2",
}


class TestBuildMixture:
    def test_output_shape_matches_inputs(self):
        n = 1000
        mecg   = np.random.randn(n)
        fecg   = np.random.randn(n) * 0.1
        noise1 = np.random.randn(n) * 0.3
        noise2 = np.random.randn(n) * 0.2
        result = build_mixture(mecg, fecg, noise1, noise2, fs=250)
        assert result.aecg.shape == (n,)
        assert result.n_samples == n

    def test_mixture_equals_sum(self):
        n = 500
        mecg   = np.ones(n) * 2.0
        fecg   = np.ones(n) * 0.1
        noise1 = np.ones(n) * 0.3
        noise2 = np.ones(n) * 0.2
        result = build_mixture(mecg, fecg, noise1, noise2, fs=250)
        expected = mecg + fecg + noise1 + noise2
        np.testing.assert_allclose(result.aecg, expected)

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length mismatch"):
            build_mixture(
                np.ones(100), np.ones(100), np.ones(100), np.ones(99), fs=250
            )

    def test_snr_field_is_finite(self):
        n = 1000
        mecg   = np.random.randn(n)
        fecg   = np.random.randn(n) * 0.1
        noise1 = np.random.randn(n) * 0.3
        noise2 = np.random.randn(n) * 0.2
        result = build_mixture(mecg, fecg, noise1, noise2, fs=250)
        assert np.isfinite(result.snr_fm_estimated_db)
        assert np.isfinite(result.snr_mn_estimated_db)

    def test_real_tc1_mixture(self):
        """End-to-end: load TC1 components and build mixture."""
        tc = load_test_case("TC1", TC1_RECORDS, repo_root=str(REPO_ROOT))
        result = build_mixture(tc.mecg, tc.fecg_ref, tc.noise1, tc.noise2, fs=tc.fs)
        assert result.aecg.shape == (75000,)
        assert np.all(np.isfinite(result.aecg))


class TestCheckMixtureSNR:
    def test_passes_within_tolerance(self):
        n = 5000
        mecg   = np.random.randn(n) * 10
        fecg   = np.random.randn(n) * 0.1
        noise1 = np.random.randn(n) * 1.0
        noise2 = np.zeros(n)
        result = build_mixture(mecg, fecg, noise1, noise2, fs=250)
        # Should not raise — tolerance is generous
        check_mixture_snr(result, expected_snr_mn_db=result.snr_mn_estimated_db,
                          tolerance_db=0.01)

    def test_fails_outside_tolerance(self):
        n = 1000
        mecg   = np.random.randn(n)
        fecg   = np.random.randn(n)
        noise1 = np.random.randn(n)
        noise2 = np.zeros(n)
        result = build_mixture(mecg, fecg, noise1, noise2, fs=250)
        with pytest.raises(ValueError, match="SNR check failed"):
            check_mixture_snr(result, expected_snr_mn_db=100.0, tolerance_db=1.0)


class TestPowerRatioDb:
    def test_equal_power_gives_0db(self):
        sig = np.ones(100)
        ref = np.ones(100)
        assert abs(_power_ratio_db(sig, ref)) < 1e-9

    def test_zero_reference_gives_inf(self):
        import math
        result = _power_ratio_db(np.ones(10), np.zeros(10))
        assert math.isinf(result)
