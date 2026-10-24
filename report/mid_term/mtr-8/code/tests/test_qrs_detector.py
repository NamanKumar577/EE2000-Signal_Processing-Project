"""
tests/test_qrs_detector.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the common fetal QRS detector (src/qrs_detector.py).

Owner    : Anshu (QRS detector module)
Run from project root:
    PYTHONPATH=code .venv/bin/pytest code/tests/test_qrs_detector.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.qrs_detector import QRSDetectorConfig, detect_fetal_qrs, _DEFAULT_DETECTOR_CONFIG
from src.evaluation import match_beats, compute_beat_metrics


FS = 250


class TestQRSDetectorConfig:
    """Verify QRS detector parameters are frozen and match PPR-8 Section 5.3."""

    def test_ppr8_default_parameters(self):
        cfg = _DEFAULT_DETECTOR_CONFIG
        assert cfg.fs == 250
        assert cfg.bp_low_hz == 8.0          # Filter 4: 8 Hz
        assert cfg.bp_high_hz == 30.0        # Filter 4: 30 Hz
        assert cfg.bp_order == 4             # 4th-order Butterworth
        assert cfg.integration_window_ms == 80.0  # W ≈ 80 ms
        assert cfg.refractory_ms == 200.0    # 200 ms blanking
        assert cfg.threshold_alpha == 0.25   # alpha = 0.25


class TestQRSDetectorRobustness:
    """Verify detector handles edge cases, empty, flatline, and non-finite signals."""

    def test_empty_input_returns_empty_arrays(self):
        peaks, times = detect_fetal_qrs(np.array([]), fs=FS)
        assert len(peaks) == 0
        assert len(times) == 0
        assert peaks.dtype == int
        assert times.dtype == float

    def test_short_input_returns_empty_arrays(self):
        peaks, times = detect_fetal_qrs(np.zeros(30), fs=FS)
        assert len(peaks) == 0
        assert len(times) == 0

    def test_all_zeros_returns_empty_arrays(self):
        peaks, times = detect_fetal_qrs(np.zeros(1000), fs=FS)
        assert len(peaks) == 0
        assert len(times) == 0

    def test_constant_dc_returns_empty_arrays(self):
        peaks, times = detect_fetal_qrs(np.ones(1000) * 5.0, fs=FS)
        assert len(peaks) == 0
        assert len(times) == 0

    def test_nan_and_inf_handled_without_crash(self):
        x = np.random.randn(1000)
        x[100] = np.nan
        x[200] = np.inf
        x[300] = -np.inf
        peaks, times = detect_fetal_qrs(x, fs=FS)
        assert isinstance(peaks, np.ndarray)
        assert isinstance(times, np.ndarray)
        assert np.all(np.isfinite(peaks))
        assert np.all(np.isfinite(times))


class TestQRSDetectorOutputContract:
    """Verify sorting, indexing, and timing contracts."""

    def test_peaks_sorted_and_timestamps_match(self):
        # Create synthetic periodic pulse train (~140 BPM, period = 107 samples)
        t = np.arange(2500)
        x = np.zeros(2500)
        pulse_indices = np.arange(100, 2400, 107)
        for idx in pulse_indices:
            # Add narrow bi-phasic QRS spike
            x[idx - 1:idx + 2] = [-0.2, 1.0, -0.2]

        peaks, times = detect_fetal_qrs(x, fs=FS)
        assert len(peaks) > 0
        # Check strictly sorted
        assert np.all(np.diff(peaks) > 0)
        # Check timestamps match sample / fs
        np.testing.assert_allclose(times, peaks / float(FS), rtol=1e-5)

    def test_refractory_period_suppresses_double_detections(self):
        # Create spikes separated by 100 ms (25 samples) < 200 ms refractory
        x = np.zeros(1000)
        x[200] = 1.0
        x[225] = 0.9   # 100 ms later, should be blanked
        x[500] = 1.0
        x[520] = 0.8   # 80 ms later, should be blanked

        peaks, _ = detect_fetal_qrs(x, fs=FS)
        # Only 2 distinct events should be detected
        assert len(peaks) == 2
        assert np.all(np.diff(peaks) >= int(0.200 * FS))


class TestQRSDetectorDiagnosticTC1:
    """Diagnostic check on clean FECGSYNDB reference signal."""

    def test_diagnostic_clean_reference_detection(self):
        from src.data_loader import load_test_case
        import yaml

        repo_root = Path(__file__).resolve().parents[2]
        config_path = repo_root / "code" / "configs" / "tests.yaml"
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        tc_cfg = cfg["test_cases"]["TC1"]
        data = load_test_case("TC1", tc_cfg["records"], channel=0, expected_fs=FS, repo_root=str(repo_root))

        # Run detector on clean reference
        peaks, times = detect_fetal_qrs(data.fecg_ref, fs=FS)

        # Evaluate against reference annotations
        ref = data.fecg_qrs_samples
        m = compute_beat_metrics(ref, peaks, fs=FS, tolerance_ms=50.0)

        # High diagnostic performance expected on clean ground-truth signal
        assert m.sensitivity > 0.95, f"Sensitivity too low: {m.sensitivity:.3f}"
        assert m.ppv > 0.95, f"PPV too low: {m.ppv:.3f}"
        assert m.f1 > 0.95, f"F1-score too low: {m.f1:.3f}"
