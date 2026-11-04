"""
tests/test_loader.py
──────────────────────────────────────────────────────────────────────────────
Tests for src/data_loader.py

Owner    : Vivek (verify these pass after data audit)

Run from the code/ directory:
    python -m pytest tests/test_loader.py -v
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

# Add code/ to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loader import load_record, load_annotations, validate_record, load_test_case

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]  # project root
TC1_MECG  = str(REPO_ROOT / "test/test1/sub01_snr12dB_l1_c0_mecg")
TC1_FECG  = str(REPO_ROOT / "test/test1/sub01_snr12dB_l1_c0_fecg1")

EXPECTED_FS       = 250
EXPECTED_SAMPLES  = 75000


# ──────────────────────────────────────────────────────────────────────────────
# load_record
# ──────────────────────────────────────────────────────────────────────────────

class TestLoadRecord:
    def test_returns_correct_shape(self):
        signal, fs, meta = load_record(TC1_MECG, channel=0)
        assert signal.ndim == 1
        assert len(signal) == EXPECTED_SAMPLES

    def test_correct_sampling_rate(self):
        _, fs, _ = load_record(TC1_MECG)
        assert fs == EXPECTED_FS

    def test_signal_is_finite(self):
        signal, _, _ = load_record(TC1_MECG)
        assert np.all(np.isfinite(signal))

    def test_metadata_populated(self):
        _, _, meta = load_record(TC1_MECG)
        assert meta.fs == EXPECTED_FS
        assert meta.n_samples == EXPECTED_SAMPLES
        assert meta.n_channels > 0

    def test_header_comments_parsed(self):
        _, _, meta = load_record(TC1_MECG)
        # #SNRmn should be present in TC1 mecg header
        assert "SNRmn" in meta.comments
        assert meta.comments["SNRmn"] == "12"

    def test_invalid_channel_raises(self):
        with pytest.raises(ValueError, match="channel"):
            load_record(TC1_MECG, channel=999)


# ──────────────────────────────────────────────────────────────────────────────
# load_annotations
# ──────────────────────────────────────────────────────────────────────────────

class TestLoadAnnotations:
    def test_returns_sorted_array(self):
        samples = load_annotations(TC1_FECG, extension="qrs")
        assert samples.ndim == 1
        assert np.all(np.diff(samples) >= 0), "Annotations must be sorted"

    def test_annotation_count_reasonable(self):
        # At 143 BPM for 5 minutes → ~715 fetal beats expected
        samples = load_annotations(TC1_FECG, extension="qrs")
        assert 500 < len(samples) < 1000, (
            f"Expected ~715 fetal beats at 143 BPM; got {len(samples)}"
        )

    def test_all_samples_in_range(self):
        samples = load_annotations(TC1_FECG, extension="qrs")
        assert np.all(samples >= 0)
        assert np.all(samples < EXPECTED_SAMPLES)


# ──────────────────────────────────────────────────────────────────────────────
# validate_record
# ──────────────────────────────────────────────────────────────────────────────

class TestValidateRecord:
    def test_passes_for_correct_record(self):
        assert validate_record(TC1_MECG, expected_fs=EXPECTED_FS,
                               expected_n_samples=EXPECTED_SAMPLES) is True

    def test_fails_on_wrong_fs(self):
        with pytest.raises(ValueError, match="Sampling rate"):
            validate_record(TC1_MECG, expected_fs=500)

    def test_fails_on_wrong_sample_count(self):
        with pytest.raises(ValueError, match="Sample count"):
            validate_record(TC1_MECG, expected_n_samples=99999)


# ──────────────────────────────────────────────────────────────────────────────
# load_test_case
# ──────────────────────────────────────────────────────────────────────────────

class TestLoadTestCase:
    TC1_RECORDS = {
        "fecg1": "test/test1/sub01_snr12dB_l1_c0_fecg1",
        "mecg":  "test/test1/sub01_snr12dB_l1_c0_mecg",
        "noise1": "test/test1/sub01_snr12dB_l1_c0_noise1",
        "noise2": "test/test1/sub01_snr12dB_l1_c0_noise2",
    }

    def test_loads_all_components(self):
        tc = load_test_case("TC1", self.TC1_RECORDS, repo_root=str(REPO_ROOT))
        assert tc.mecg.shape == (EXPECTED_SAMPLES,)
        assert tc.fecg_ref.shape == (EXPECTED_SAMPLES,)
        assert tc.noise1.shape == (EXPECTED_SAMPLES,)
        assert tc.noise2.shape == (EXPECTED_SAMPLES,)

    def test_fecg_qrs_annotations_loaded(self):
        tc = load_test_case("TC1", self.TC1_RECORDS, repo_root=str(REPO_ROOT))
        assert len(tc.fecg_qrs_samples) > 0

    def test_missing_key_raises(self):
        bad_records = {k: v for k, v in self.TC1_RECORDS.items() if k != "noise2"}
        with pytest.raises(KeyError, match="noise2"):
            load_test_case("TC1", bad_records, repo_root=str(REPO_ROOT))
