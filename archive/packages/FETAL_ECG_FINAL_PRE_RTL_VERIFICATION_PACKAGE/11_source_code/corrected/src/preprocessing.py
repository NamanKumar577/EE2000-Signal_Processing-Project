"""
src/preprocessing.py
──────────────────────────────────────────────────────────────────────────────
Shared preprocessing baseline for all FECG extraction methods.

Owner    : Astitva (preprocessing module)
Used by  : all members — call preprocess() before feeding signal to extraction.

Pipeline (applied in order):
  1. Edge padding (reduce filter transients)
  2. Baseline wander removal  — 4th-order Butterworth high-pass at 0.5 Hz
  3. Band-pass filter         — 4th-order Butterworth 0.5–40 Hz, zero-phase
  4. Strip padding

IMPORTANT CAUSAL NOTE
---------------------
All filters are applied zero-phase (scipy.signal.filtfilt), which is a
non-causal offline operation.  Results labelled with this preprocessing
CANNOT be reproduced in a real-time causal FPGA pipeline without modification.
Any FPGA implementation must substitute causal (single-pass) filtering and
account for the resulting phase delay.

Configuration
-------------
Settings are read from configs/preprocessing.yaml.  This module provides a
convenience function preprocess() that uses the frozen config by default.
Pass a custom config dict to override for experiments — but document it.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch, sosfiltfilt, butter as _butter

# ──────────────────────────────────────────────────────────────────────────────
# Default frozen parameters (mirror of configs/preprocessing.yaml)
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_CONFIG = {
    "sampling_rate_hz": 250,
    "baseline_wander_removal": {
        "enabled": True,
        "filter_type": "butterworth",
        "order": 4,
        "cutoff_hz": 0.5,
    },
    "bandpass_filter": {
        "enabled": True,
        "filter_type": "butterworth",
        "order": 4,
        "lowcut_hz": 0.5,
        "highcut_hz": 40.0,
    },
    "powerline_notch": {
        "enabled": False,
        "notch_hz": 50.0,
        "quality_factor": 30.0,
    },
    "edge_handling": {
        "method": "padding",
        "pad_samples": 250,
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def preprocess(
    signal: np.ndarray,
    fs: int = 250,
    config: Optional[dict] = None,
) -> np.ndarray:
    """
    Apply the shared preprocessing pipeline to a 1-D ECG signal.

    Parameters
    ----------
    signal : np.ndarray, shape (n_samples,)
        Raw input signal (physical units, as returned by data_loader).
    fs : int
        Sampling frequency in Hz.
    config : dict, optional
        Override configuration. Uses frozen defaults if None.
        If you change config for an experiment, document the change explicitly.

    Returns
    -------
    filtered : np.ndarray, shape (n_samples,)
        Preprocessed signal, same length as input.

    Notes
    -----
    - Zero-phase filtering is used (non-causal, offline only).
    - Edge padding is stripped after filtering; output length equals input.
    """
    cfg = _DEFAULT_CONFIG if config is None else config
    pad = cfg["edge_handling"]["pad_samples"]

    x = signal.astype(np.float64)

    # ── 1. Edge padding ───────────────────────────────────────────────────────
    x_padded = np.pad(x, pad, mode="reflect")

    # ── 2. Baseline wander removal (high-pass) ────────────────────────────────
    bwr = cfg["baseline_wander_removal"]
    if bwr["enabled"]:
        sos = _highpass_sos(bwr["order"], bwr["cutoff_hz"], fs)
        x_padded = sosfiltfilt(sos, x_padded)

    # ── 3. Band-pass filter ───────────────────────────────────────────────────
    bp = cfg["bandpass_filter"]
    if bp["enabled"]:
        sos = _bandpass_sos(bp["order"], bp["lowcut_hz"], bp["highcut_hz"], fs)
        x_padded = sosfiltfilt(sos, x_padded)

    # ── 4. Power-line notch (disabled by default for FECGSYNDB) ──────────────
    notch = cfg["powerline_notch"]
    if notch["enabled"]:
        b, a = iirnotch(notch["notch_hz"], notch["quality_factor"], fs)
        x_padded = filtfilt(b, a, x_padded)

    # ── 5. Strip padding ─────────────────────────────────────────────────────
    filtered = x_padded[pad: pad + len(signal)]
    return filtered


def get_config_summary(config: Optional[dict] = None) -> str:
    """Return a human-readable summary of the preprocessing settings."""
    cfg = _DEFAULT_CONFIG if config is None else config
    bwr = cfg["baseline_wander_removal"]
    bp  = cfg["bandpass_filter"]
    ntc = cfg["powerline_notch"]
    pad = cfg["edge_handling"]["pad_samples"]

    lines = [
        "=== Preprocessing Config ===",
        f"  Sampling rate    : {cfg['sampling_rate_hz']} Hz",
        f"  Edge padding     : {pad} samples",
        f"  BWR high-pass    : {'ON' if bwr['enabled'] else 'OFF'}"
        f"  (order={bwr['order']}, fc={bwr['cutoff_hz']} Hz)",
        f"  Band-pass        : {'ON' if bp['enabled'] else 'OFF'}"
        f"  (order={bp['order']}, {bp['lowcut_hz']}–{bp['highcut_hz']} Hz, zero-phase)",
        f"  Powerline notch  : {'ON' if ntc['enabled'] else 'OFF'}"
        f"  ({ntc['notch_hz']} Hz, Q={ntc['quality_factor']})",
        "  CAUSAL NOTE      : Zero-phase (non-causal); NOT suitable for real-time FPGA.",
    ]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _highpass_sos(order: int, cutoff_hz: float, fs: int) -> np.ndarray:
    nyq = fs / 2.0
    return butter(order, cutoff_hz / nyq, btype="high", output="sos")


def _bandpass_sos(order: int, low_hz: float, high_hz: float, fs: int) -> np.ndarray:
    nyq = fs / 2.0
    return butter(order, [low_hz / nyq, high_hz / nyq], btype="band", output="sos")
