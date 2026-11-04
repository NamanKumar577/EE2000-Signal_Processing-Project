"""
src/data_loader.py
──────────────────────────────────────────────────────────────────────────────
Loads WFDB records and validates metadata against expected values.

Role     : Data Validation & Evaluation Lead
Used by  : all members via run_benchmark.py

Public API
----------
load_record(record_path, channel=0) -> (signal_1d, fs, metadata_dict)
load_annotations(record_path, extension) -> annotation_samples_array
validate_record(record_path, expected_fs, expected_n_samples) -> bool

Notes
-----
- Returns physical signals in native units (nu) as stored in the .hea gain field.
- The clean fetal signal (fecg1) is loaded here but MUST NOT be passed to
  any extraction algorithm.  Pass it only to the evaluation layer.
- All validation failures raise ValueError with a clear message.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import wfdb


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RecordMetadata:
    """Parsed metadata from a WFDB .hea file."""
    record_name: str
    fs: int                        # sampling frequency (Hz)
    n_samples: int                 # samples per signal
    n_channels: int                # number of channels
    units: list[str]               # physical units per channel
    adc_gain: list[float]          # ADC gain per channel
    baseline: list[int]            # baseline offset per channel
    comments: dict[str, str] = field(default_factory=dict)   # #key:value pairs from header


@dataclass
class TestCaseData:
    """All components for a single test case, ready for mixture building."""
    test_id: str
    fs: int
    n_samples: int
    # Mixture input components (used to build AECG)
    mecg: np.ndarray               # maternal ECG component  (n_samples,)
    noise1: np.ndarray             # noise component 1       (n_samples,)
    noise2: np.ndarray             # noise component 2       (n_samples,)
    # Ground truth — evaluation only; NEVER feed to extraction algorithm
    fecg_ref: np.ndarray           # clean fetal ECG reference (n_samples,)
    fecg_qrs_samples: np.ndarray   # reference fetal R-peak sample indices
    mecg_qrs_samples: np.ndarray   # reference maternal R-peak sample indices
    metadata: dict                 # raw header comments for audit


# ──────────────────────────────────────────────────────────────────────────────
# Core loading functions
# ──────────────────────────────────────────────────────────────────────────────

def load_record(
    record_path: str,
    channel: int = 0,
) -> tuple[np.ndarray, int, RecordMetadata]:
    """
    Load a single WFDB record and return one channel of the physical signal.

    Parameters
    ----------
    record_path : str
        Path to the record WITHOUT extension (wfdb convention).
        Example: 'test/test1/sub01_snr12dB_l1_c0_mecg'
    channel : int
        Channel index to extract from the multi-channel file.

    Returns
    -------
    signal : np.ndarray, shape (n_samples,)
        1-D physical signal for the requested channel.
    fs : int
        Sampling frequency in Hz.
    meta : RecordMetadata
        Parsed header metadata.
    """
    record = wfdb.rdrecord(record_path)

    if record.p_signal is None:
        raise ValueError(f"No physical signal data in record: {record_path}")
    if channel >= record.n_sig:
        raise ValueError(
            f"Requested channel {channel} but record '{record_path}' "
            f"only has {record.n_sig} channels."
        )

    signal = record.p_signal[:, channel].astype(np.float64)

    # Parse key:value comment lines from the header
    comments: dict[str, str] = {}
    if record.comments:
        for line in record.comments:
            line = line.strip()
            if line.startswith("#"):
                line = line[1:].strip()
            if ":" in line:
                key, _, value = line.partition(":")
                comments[key.strip()] = value.strip()
            elif line:
                comments[line.strip()] = ""

    meta = RecordMetadata(
        record_name=record.record_name,
        fs=record.fs,
        n_samples=record.sig_len,
        n_channels=record.n_sig,
        units=list(record.units) if record.units else [],
        adc_gain=list(record.adc_gain) if record.adc_gain else [],
        baseline=list(record.baseline) if record.baseline else [],
        comments=comments,
    )

    return signal, record.fs, meta


def load_annotations(
    record_path: str,
    extension: str = "qrs",
) -> np.ndarray:
    """
    Load WFDB beat annotations and return sample indices.

    Parameters
    ----------
    record_path : str
        Path to the record WITHOUT extension.
    extension : str
        Annotation file extension (default 'qrs').

    Returns
    -------
    samples : np.ndarray, shape (n_beats,), dtype int
        Sorted sample indices of annotated beats.
    """
    ann = wfdb.rdann(record_path, extension)
    samples = np.array(ann.sample, dtype=int)
    samples.sort()
    return samples


# ──────────────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────────────

def validate_record(
    record_path: str,
    expected_fs: int = 250,
    expected_n_samples: int = 75000,
    channel: int = 0,
) -> bool:
    """
    Validate a record's metadata against expected values.

    Raises ValueError on any mismatch or data quality issue.
    Returns True if all checks pass.
    """
    signal, fs, meta = load_record(record_path, channel=channel)

    errors: list[str] = []

    if fs != expected_fs:
        errors.append(
            f"Sampling rate mismatch: got {fs} Hz, expected {expected_fs} Hz"
        )
    if meta.n_samples != expected_n_samples:
        errors.append(
            f"Sample count mismatch: got {meta.n_samples}, expected {expected_n_samples}"
        )
    if not np.isfinite(signal).all():
        n_bad = int(np.sum(~np.isfinite(signal)))
        errors.append(f"Signal contains {n_bad} non-finite values (NaN/Inf)")
    if len(signal) == 0:
        errors.append("Signal is empty")

    if errors:
        raise ValueError(
            f"Validation failed for '{record_path}':\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return True


# ──────────────────────────────────────────────────────────────────────────────
# High-level convenience loader
# ──────────────────────────────────────────────────────────────────────────────

def load_test_case(
    test_id: str,
    records: dict[str, str],
    channel: int = 0,
    expected_fs: int = 250,
    expected_n_samples: int = 75000,
    repo_root: Optional[str] = None,
) -> TestCaseData:
    """
    Load all components for one test case and validate consistency.

    Parameters
    ----------
    test_id : str
        Identifier, e.g. 'TC1'.
    records : dict
        Mapping of component name -> record path (no extension).
        Expected keys: 'fecg1', 'mecg', 'noise1', 'noise2'.
    channel : int
        Channel index used for all components.
    expected_fs : int
        Expected sampling frequency.
    expected_n_samples : int
        Expected number of samples per component.
    repo_root : str, optional
        If provided, prepend to all record paths.

    Returns
    -------
    TestCaseData
    """
    def _path(key: str) -> str:
        p = records[key]
        if repo_root:
            p = os.path.join(repo_root, p)
        return p

    # Validate each component
    for key in ("fecg1", "mecg", "noise1", "noise2"):
        if key not in records:
            raise KeyError(f"Test case '{test_id}' missing required record key: '{key}'")
        validate_record(_path(key), expected_fs, expected_n_samples, channel)

    # Load signals
    mecg, fs, mecg_meta   = load_record(_path("mecg"),   channel)
    fecg, _,  _           = load_record(_path("fecg1"),  channel)
    noise1, _, _          = load_record(_path("noise1"), channel)
    noise2, _, _          = load_record(_path("noise2"), channel)

    # Verify length alignment across components
    lengths = {"mecg": len(mecg), "fecg1": len(fecg),
               "noise1": len(noise1), "noise2": len(noise2)}
    if len(set(lengths.values())) > 1:
        raise ValueError(
            f"Component length mismatch in '{test_id}': {lengths}"
        )

    n = len(mecg)

    # Load annotations (fetal QRS — evaluation only; maternal QRS — optional)
    fecg_qrs = load_annotations(_path("fecg1"), extension="qrs")
    mecg_qrs = load_annotations(_path("mecg"),  extension="qrs")

    return TestCaseData(
        test_id=test_id,
        fs=fs,
        n_samples=n,
        mecg=mecg,
        noise1=noise1,
        noise2=noise2,
        fecg_ref=fecg,           # ground truth — evaluation ONLY
        fecg_qrs_samples=fecg_qrs,
        mecg_qrs_samples=mecg_qrs,
        metadata=mecg_meta.comments,
    )
