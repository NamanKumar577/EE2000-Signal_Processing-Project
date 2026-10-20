"""
src/qrs_detector.py
──────────────────────────────────────────────────────────────────────────────
Common fetal QRS detector applied to the EXTRACTED fetal waveform.

Owner    : Anshu (QRS detector module)
Used by  : all members via run_benchmark.py

Algorithm (from PPR-8 specification):
  1. Band-pass filter the extracted signal (5–20 Hz for fetal QRS energy)
  2. Square the filtered signal to obtain instantaneous power
  3. Moving-window integration (window = refractory_ms converted to samples)
  4. Adaptive threshold detection
  5. Refractory period blanking to suppress duplicate detections

This detector is applied to the EXTRACTED fetal waveform, NOT to the
clean reference signal.  The reference may be used for diagnostic checks
only (clearly labelled).

Parameters (frozen before benchmark — do not change between methods):
  - Band-pass: 5–20 Hz
  - Integration window: 150 ms  → 38 samples at 250 Hz
  - Refractory period: 200 ms   → 50 samples at 250 Hz (min fetal RR interval
    at physiological max ~300 BPM)
  - Threshold: adaptive (0.5 × running 1-second maximum of integrated signal)

NOTE: Confirm all frequency limits and window/threshold values from PPR-8
before the final benchmark run. Parameters marked CONFIRM_FROM_PPR8 below.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import butter, sosfiltfilt


# ──────────────────────────────────────────────────────────────────────────────
# Configuration (frozen; from PPR-8 spec — verify before benchmark)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class QRSDetectorConfig:
    fs: int = 250                  # sampling frequency (Hz)
    bp_low_hz: float = 5.0        # band-pass lower edge  (CONFIRM_FROM_PPR8)
    bp_high_hz: float = 20.0      # band-pass upper edge  (CONFIRM_FROM_PPR8)
    bp_order: int = 4
    integration_window_ms: float = 150.0  # moving-window integration  (CONFIRM_FROM_PPR8)
    refractory_ms: float = 200.0          # post-detection blanking     (CONFIRM_FROM_PPR8)
    threshold_fraction: float = 0.5       # fraction of running max     (CONFIRM_FROM_PPR8)
    threshold_window_ms: float = 1000.0   # running max window (1 second)


_DEFAULT_DETECTOR_CONFIG = QRSDetectorConfig()


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def detect_fetal_qrs(
    extracted_fecg: np.ndarray,
    fs: int = 250,
    config: Optional[QRSDetectorConfig] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Detect fetal R-peaks in an extracted fetal ECG waveform.

    Parameters
    ----------
    extracted_fecg : np.ndarray, shape (n_samples,)
        Estimated fetal ECG output from an extraction method.
        Must NOT be the clean ground-truth reference.
    fs : int
        Sampling frequency in Hz.
    config : QRSDetectorConfig, optional
        Detector parameters. Uses frozen defaults if None.

    Returns
    -------
    peak_samples : np.ndarray, dtype int
        Sorted sample indices of detected fetal R-peaks.
    peak_times_s : np.ndarray, dtype float
        Corresponding time instants in seconds.

    Notes
    -----
    - Duplicate peaks within the refractory period are suppressed.
    - If no peaks are found, both arrays are empty (not an error; report it).
    """
    cfg = config if config is not None else _DEFAULT_DETECTOR_CONFIG

    x = extracted_fecg.astype(np.float64)

    # ── Step 1: Band-pass filter ──────────────────────────────────────────────
    sos = _bandpass_sos(cfg.bp_order, cfg.bp_low_hz, cfg.bp_high_hz, fs)
    x_bp = sosfiltfilt(sos, x)

    # ── Step 2: Squaring ──────────────────────────────────────────────────────
    x_sq = x_bp ** 2

    # ── Step 3: Moving-window integration ─────────────────────────────────────
    win_samples = max(1, int(round(cfg.integration_window_ms * fs / 1000.0)))
    x_int = _moving_average(x_sq, win_samples)

    # ── Step 4: Adaptive threshold detection ──────────────────────────────────
    thr_win = max(1, int(round(cfg.threshold_window_ms * fs / 1000.0)))
    peaks_raw = _adaptive_threshold_detect(x_int, thr_win, cfg.threshold_fraction)

    # ── Step 5: Refractory blanking ───────────────────────────────────────────
    refractory_samples = max(1, int(round(cfg.refractory_ms * fs / 1000.0)))
    peak_samples = _apply_refractory(peaks_raw, refractory_samples)

    peak_samples = np.sort(peak_samples).astype(int)
    peak_times_s = peak_samples / float(fs)

    return peak_samples, peak_times_s


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _bandpass_sos(order: int, low_hz: float, high_hz: float, fs: int) -> np.ndarray:
    nyq = fs / 2.0
    return butter(order, [low_hz / nyq, high_hz / nyq], btype="band", output="sos")


def _moving_average(x: np.ndarray, window: int) -> np.ndarray:
    """Causal moving-window integration via cumsum."""
    cs = np.cumsum(np.insert(x, 0, 0.0))
    return (cs[window:] - cs[:-window]) / window


def _adaptive_threshold_detect(
    x_int: np.ndarray,
    thr_window: int,
    fraction: float,
) -> np.ndarray:
    """
    Simple peak detection above an adaptive threshold.
    Threshold at each sample = fraction × max of x_int in preceding thr_window.
    Returns array of candidate peak sample indices.
    """
    n = len(x_int)
    threshold = np.zeros(n)
    for i in range(n):
        start = max(0, i - thr_window)
        threshold[i] = fraction * np.max(x_int[start: i + 1])

    above = x_int > threshold

    # Find rising edges (candidate peaks = first sample above threshold after gap)
    candidates = []
    in_peak = False
    peak_val = -np.inf
    peak_idx = -1
    for i in range(n):
        if above[i]:
            if not in_peak:
                in_peak = True
                peak_val = x_int[i]
                peak_idx = i
            elif x_int[i] > peak_val:
                peak_val = x_int[i]
                peak_idx = i
        else:
            if in_peak:
                candidates.append(peak_idx)
                in_peak = False
                peak_val = -np.inf
                peak_idx = -1
    if in_peak:
        candidates.append(peak_idx)

    return np.array(candidates, dtype=int)


def _apply_refractory(peaks: np.ndarray, refractory: int) -> np.ndarray:
    """
    Remove duplicate peaks within the refractory period.
    Keep the first peak in each cluster; discard any peak that falls within
    `refractory` samples of the previous accepted peak.
    """
    if len(peaks) == 0:
        return peaks

    kept = [peaks[0]]
    for p in peaks[1:]:
        if p - kept[-1] >= refractory:
            kept.append(p)

    return np.array(kept, dtype=int)
