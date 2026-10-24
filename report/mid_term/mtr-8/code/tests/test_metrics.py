"""
tests/test_metrics.py
──────────────────────────────────────────────────────────────────────────────
Tests for waveform error metrics in src/evaluation.py.

Owner    : Vivek
Run from the code/ directory:
    python -m pytest tests/test_metrics.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation import compute_waveform_metrics


class TestComputeWaveformMetrics:
    def test_perfect_reconstruction_rmse_zero(self):
        ref = np.sin(np.linspace(0, 2 * np.pi, 1000))
        m = compute_waveform_metrics(ref, ref.copy(), fs=250)
        assert m.rmse == pytest.approx(0.0, abs=1e-12)

    def test_perfect_reconstruction_snr_infinite(self):
        ref = np.sin(np.linspace(0, 2 * np.pi, 1000))
        m = compute_waveform_metrics(ref, ref.copy(), fs=250)
        # SNR_imp = 10·log10(power(ref)/power(ref−est))
        # power of error = 0 → SNR = +inf; but we guard against log(0)
        # In practice, floating-point error keeps power_err > 0 but tiny.
        # Accept either None (if power_err=0 was caught) or very large value.
        if m.snr_improvement_db is not None:
            assert m.snr_improvement_db > 60  # dB

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="length"):
            compute_waveform_metrics(np.ones(100), np.ones(99), fs=250)

    def test_correlation_perfect(self):
        ref = np.random.randn(1000)
        m = compute_waveform_metrics(ref, ref.copy(), fs=250)
        assert m.correlation == pytest.approx(1.0, abs=1e-10)

    def test_correlation_anticorrelated(self):
        ref = np.random.randn(1000)
        m = compute_waveform_metrics(ref, -ref, fs=250)
        assert m.correlation == pytest.approx(-1.0, abs=1e-10)

    def test_known_rmse(self):
        ref = np.zeros(100)
        est = np.ones(100)       # constant offset of 1.0 → RMSE = 1.0
        m = compute_waveform_metrics(ref, est, fs=250)
        assert m.rmse == pytest.approx(1.0)

    def test_snr_formula_matches_manual_calculation(self):
        """Verify SNR_imp = 10·log10(power(ref)/power(ref−est))."""
        ref = np.array([1.0, 2.0, 3.0, 4.0])
        est = np.array([1.1, 2.0, 3.0, 4.0])
        error = ref - est
        expected_snr = 10 * np.log10(np.mean(ref ** 2) / np.mean(error ** 2))
        m = compute_waveform_metrics(ref, est, fs=250)
        assert m.snr_improvement_db == pytest.approx(expected_snr, rel=1e-6)

    def test_waveform_noise_addition(self):
        """Adding noise should lower SNR improvement."""
        rng = np.random.default_rng(seed=42)
        ref  = np.sin(np.linspace(0, 4 * np.pi, 2000))
        est_low_noise  = ref + rng.normal(0, 0.01, len(ref))
        est_high_noise = ref + rng.normal(0, 0.5,  len(ref))
        m_low  = compute_waveform_metrics(ref, est_low_noise,  fs=250)
        m_high = compute_waveform_metrics(ref, est_high_noise, fs=250)
        assert m_low.snr_improvement_db > m_high.snr_improvement_db
        assert m_low.rmse < m_high.rmse
