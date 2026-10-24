"""
tests/test_method_interface.py
──────────────────────────────────────────────────────────────────────────────
Smoke tests to verify that each method module conforms to the BaseExtractor
interface contract.

Owner    : Naman (integration lead)
Run from the code/ directory:
    python -m pytest tests/test_method_interface.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.methods.base import BaseExtractor, OUTPUT_KEYS
from src.methods.svd import SVDExtractorV1, SVDExtractorV2, SVDExtractorV3
from src.methods.template_subtraction import TemplatSubtractionExtractor
from src.methods.swt_lms_ssnf import SWTLMSSNFExtractor
from src.methods.alternative import AlternativeExtractor

FS = 250
N  = 1000   # short smoke-test signal length


def _make_synthetic_mixture(n: int = N, fs: int = FS) -> np.ndarray:
    """Simple synthetic ECG-like signal for interface testing."""
    t = np.linspace(0, n / fs, n)
    maternal = np.sin(2 * np.pi * 1.5 * t) * 1.0    # ~90 BPM
    fetal    = np.sin(2 * np.pi * 2.3 * t) * 0.1    # ~138 BPM
    noise    = np.random.default_rng(seed=0).normal(0, 0.05, n)
    return maternal + fetal + noise


class TestBaseExtractorInheritance:
    """Verify all concrete classes inherit from BaseExtractor."""

    @pytest.mark.parametrize("ExtractorClass", [
        SVDExtractorV1, SVDExtractorV2, SVDExtractorV3,
        TemplatSubtractionExtractor, AlternativeExtractor,
    ])
    def test_is_subclass(self, ExtractorClass):
        assert issubclass(ExtractorClass, BaseExtractor)

    @pytest.mark.parametrize("ExtractorClass", [
        SVDExtractorV1, SVDExtractorV2, SVDExtractorV3,
        TemplatSubtractionExtractor, AlternativeExtractor,
    ])
    def test_has_required_class_attributes(self, ExtractorClass):
        assert hasattr(ExtractorClass, "DESCRIPTION")
        assert hasattr(ExtractorClass, "INPUT_SIGNALS")
        assert hasattr(ExtractorClass, "REFERENCE_NEEDED")
        assert hasattr(ExtractorClass, "IS_CAUSAL")
        assert isinstance(ExtractorClass.DESCRIPTION, str)
        assert len(ExtractorClass.DESCRIPTION) > 5

    @pytest.mark.parametrize("ExtractorClass", [
        SVDExtractorV1, SVDExtractorV2, SVDExtractorV3,
    ])
    def test_svd_variants_instantiate(self, ExtractorClass):
        extractor = ExtractorClass(fs=FS)
        assert extractor.fs == FS

    def test_template_subtraction_runs_and_returns_correct_shape(self):
        from src.methods.base import OUTPUT_KEYS
        extractor = TemplatSubtractionExtractor(fs=FS)
        mixture = _make_synthetic_mixture()
        fecg_est, metadata = extractor.run(mixture)
        assert fecg_est.shape == (N,)
        assert np.all(np.isfinite(fecg_est))
        for key in OUTPUT_KEYS:
            assert key in metadata
        assert metadata["method_name"] == "template_subtraction"
        assert metadata["input_condition"] == "single_channel"
        assert metadata["variant"] == "adaptive_ema"
        assert metadata["runtime_s"] > 0

    def test_template_subtraction_fixed_ensemble_variant(self):
        extractor = TemplatSubtractionExtractor(fs=FS, config={"variant": "fixed_ensemble"})
        mixture = _make_synthetic_mixture()
        fecg_est, metadata = extractor.run(mixture)
        assert fecg_est.shape == (N,)
        assert np.all(np.isfinite(fecg_est))
        assert metadata["variant"] == "fixed_ensemble"

    def test_template_subtraction_oracle_mode_labelled_correctly(self):
        extractor = TemplatSubtractionExtractor(fs=FS)
        mixture = _make_synthetic_mixture()
        oracle_ref = np.random.randn(N) * 0.5
        fecg_est, metadata = extractor.run(mixture, reference_channel=oracle_ref)
        assert fecg_est.shape == (N,)
        assert np.all(np.isfinite(fecg_est))
        assert metadata["input_condition"] == "oracle_assisted"

    def test_alternative_runs_and_returns_correct_shape(self):
        from src.methods.base import OUTPUT_KEYS
        extractor = AlternativeExtractor(fs=FS)
        mixture = _make_synthetic_mixture()
        fecg_est, metadata = extractor.run(mixture)
        assert fecg_est.shape == (N,)
        assert np.all(np.isfinite(fecg_est))
        for key in OUTPUT_KEYS:
            assert key in metadata
        assert metadata["method_name"] == "alternative"
        assert metadata["input_condition"] == "single_channel"
        assert metadata["runtime_s"] > 0

    def test_swt_lms_ssnf_runs_and_returns_correct_shape(self):
        from src.methods.base import OUTPUT_KEYS
        extractor = SWTLMSSNFExtractor(fs=FS)
        mixture = _make_synthetic_mixture()
        fecg_est, metadata = extractor.run(mixture)
        assert fecg_est.shape == (N,)
        assert np.all(np.isfinite(fecg_est))
        for key in OUTPUT_KEYS:
            assert key in metadata
        assert metadata["input_condition"] == "single_channel"
        assert metadata["runtime_s"] > 0

    def test_swt_lms_ssnf_lms_only_variant(self):
        extractor = SWTLMSSNFExtractor(fs=FS, config={"variant": "lms_only"})
        mixture = _make_synthetic_mixture()
        fecg_est, metadata = extractor.run(mixture)
        assert fecg_est.shape == (N,)
        assert np.all(np.isfinite(fecg_est))
        assert metadata["variant"] == "lms_only"

    def test_swt_lms_ssnf_oracle_mode_labelled_correctly(self):
        extractor = SWTLMSSNFExtractor(fs=FS)
        mixture = _make_synthetic_mixture()
        oracle_ref = np.random.randn(N) * 0.5
        fecg_est, metadata = extractor.run(mixture, reference_channel=oracle_ref)
        assert fecg_est.shape == (N,)
        assert np.all(np.isfinite(fecg_est))
        assert metadata["input_condition"] == "oracle_assisted"


class TestSVDInterface:
    """Smoke tests for SVD methods on a short synthetic signal."""

    mixture = _make_synthetic_mixture(N)

    @pytest.mark.parametrize("ExtractorClass", [
        SVDExtractorV1, SVDExtractorV2, SVDExtractorV3,
    ])
    def test_run_returns_correct_output_shape(self, ExtractorClass):
        extractor = ExtractorClass(fs=FS)
        fecg_est, metadata = extractor.run(self.mixture)
        assert fecg_est.shape == (N,)

    @pytest.mark.parametrize("ExtractorClass", [
        SVDExtractorV1, SVDExtractorV2, SVDExtractorV3,
    ])
    def test_run_output_is_finite(self, ExtractorClass):
        extractor = ExtractorClass(fs=FS)
        fecg_est, _ = extractor.run(self.mixture)
        assert np.all(np.isfinite(fecg_est)), (
            "Extracted signal must not contain NaN or Inf values"
        )

    @pytest.mark.parametrize("ExtractorClass", [
        SVDExtractorV1, SVDExtractorV2, SVDExtractorV3,
    ])
    def test_run_metadata_has_required_keys(self, ExtractorClass):
        extractor = ExtractorClass(fs=FS)
        _, metadata = extractor.run(self.mixture)
        for key in OUTPUT_KEYS:
            assert key in metadata, f"Metadata missing required key: '{key}'"

    @pytest.mark.parametrize("ExtractorClass", [
        SVDExtractorV1, SVDExtractorV2, SVDExtractorV3,
    ])
    def test_run_reports_runtime(self, ExtractorClass):
        extractor = ExtractorClass(fs=FS)
        _, metadata = extractor.run(self.mixture)
        assert metadata["runtime_s"] > 0

    @pytest.mark.parametrize("ExtractorClass", [
        SVDExtractorV1, SVDExtractorV2, SVDExtractorV3,
    ])
    def test_input_condition_is_single_channel(self, ExtractorClass):
        extractor = ExtractorClass(fs=FS)
        _, metadata = extractor.run(self.mixture)
        assert metadata["input_condition"] == "single_channel"


class TestValidateOutput:
    """Test that validate_output() catches contract violations."""

    def test_length_mismatch_raises(self):
        extractor = SVDExtractorV1(fs=FS)
        mixture = np.ones(100)
        wrong_length_est = np.ones(50)
        with pytest.raises(ValueError, match="length"):
            extractor.validate_output(wrong_length_est, mixture, {k: None for k in OUTPUT_KEYS})

    def test_missing_metadata_key_raises(self):
        extractor = SVDExtractorV1(fs=FS)
        mixture = np.ones(100)
        partial_meta = {"method_name": "test"}  # missing many keys
        with pytest.raises(ValueError, match="missing required keys"):
            extractor.validate_output(np.ones(100), mixture, partial_meta)

    def test_nan_in_output_raises(self):
        extractor = SVDExtractorV1(fs=FS)
        mixture = np.ones(100)
        bad_est = np.ones(100)
        bad_est[5] = np.nan
        full_meta = {k: "ok" for k in OUTPUT_KEYS}
        full_meta["runtime_s"] = 0.1
        full_meta["is_causal"] = False
        with pytest.raises(ValueError, match="non-finite"):
            extractor.validate_output(bad_est, mixture, full_meta)
