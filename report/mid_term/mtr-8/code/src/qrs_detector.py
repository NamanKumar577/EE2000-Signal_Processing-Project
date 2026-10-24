"""
src/qrs_detector.py
──────────────────────────────────────────────────────────────────────────────
Common fetal QRS detector applied to the EXTRACTED fetal waveform.

Owner    : Anshu (QRS detector module)
Used by  : all members via run_benchmark.py

Algorithm (from PPR-8 Section 5.3 Specification & Sörnmo & Laguna [2]):
  1. Filter 4 (QRS-specific BPF): 4th-order Butterworth, 8–30 Hz.
     Distinct from preprocessing BPF; isolates QRS energy from P/T waves
     and residual baseline noise.
  2. Non-linear stage: Instantaneous energy via squaring y[n] = x^2[n].
  3. Moving-window integrator: W = round(0.08 * fs) samples ≈ 80 ms (20 samples at 250 Hz).
  4. Adaptive dual-threshold detection:
       T[n] = alpha * peak_level[n] + (1 - alpha) * noise_level[n]
     with alpha = 0.25 and exponential updates on candidate peak events.
  5. Refractory blanking: 200 ms blanking (50 samples at 250 Hz) prevents
     double-detection of wide QRS complexes.
  6. Peak localization: Within each detected region, locate the true R-peak as
     max |x_bp[n]| in a ±25 ms window around candidate threshold crossing.

This detector is applied to the EXTRACTED fetal waveform, NOT to the
clean reference signal. The reference is used for diagnostic checks only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import butter, sosfiltfilt, find_peaks


# ──────────────────────────────────────────────────────────────────────────────
# Configuration (frozen; verified from PPR-8 Section 5.3 spec)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class QRSDetectorConfig:
    fs: int = 250                         # sampling frequency (Hz)
    bp_low_hz: float = 8.0               # band-pass lower edge (PPR-8: 8 Hz)
    bp_high_hz: float = 30.0             # band-pass upper edge (PPR-8: 30 Hz)
    bp_order: int = 4                    # 4th-order Butterworth
    integration_window_ms: float = 80.0  # moving-window integrator (PPR-8: 80 ms)
    refractory_ms: float = 200.0         # post-detection blanking (PPR-8: 200 ms)
    threshold_alpha: float = 0.25        # adaptive threshold alpha (PPR-8: alpha=0.25)
    search_window_ms: float = 25.0       # true R-peak localization window (PPR-8: ±25 ms)
    # Backward compatibility attributes
    threshold_fraction: float = 0.5
    threshold_window_ms: float = 1000.0


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
    Detect fetal R-peaks in an extracted fetal ECG waveform according to PPR-8 Section 5.3.

    Parameters
    ----------
    extracted_fecg : np.ndarray, shape (n_samples,)
        Estimated fetal ECG output from an extraction method.
        Must NOT be the clean ground-truth reference.
    fs : int
        Sampling frequency in Hz.
    config : QRSDetectorConfig, optional
        Detector parameters. Uses frozen PPR-8 defaults if None.

    Returns
    -------
    peak_samples : np.ndarray, dtype int
        Sorted sample indices of detected fetal R-peaks.
    peak_times_s : np.ndarray, dtype float
        Corresponding time instants in seconds.

    Notes
    -----
    - Duplicate peaks within the 200 ms refractory period are suppressed.
    - True R-peaks are localized by finding max |x_bp| in a ±25 ms window.
    - If no peaks are found or input is degenerate, empty arrays are returned.
    """
    cfg = config if config is not None else _DEFAULT_DETECTOR_CONFIG

    if extracted_fecg is None or len(extracted_fecg) < 50:
        return np.array([], dtype=int), np.array([], dtype=float)

    if not np.all(np.isfinite(extracted_fecg)):
        # Replace non-finites or return empty if all non-finite
        if not np.any(np.isfinite(extracted_fecg)):
            return np.array([], dtype=int), np.array([], dtype=float)
        extracted_fecg = np.nan_to_num(extracted_fecg, nan=0.0, posinf=0.0, neginf=0.0)

    # Flatline check
    if np.all(extracted_fecg == 0.0) or np.ptp(extracted_fecg) == 0.0:
        return np.array([], dtype=int), np.array([], dtype=float)

    x = extracted_fecg.astype(np.float64)
    n = len(x)

    # ── Step 1: Band-pass filter (8–30 Hz, 4th-order Butterworth) ────────────
    sos = _bandpass_sos(cfg.bp_order, cfg.bp_low_hz, cfg.bp_high_hz, fs)
    x_bp = sosfiltfilt(sos, x)

    # ── Step 2: Instantaneous energy via squaring ─────────────────────────────
    x_sq = x_bp ** 2

    # ── Step 3: Moving-window integration (W ≈ 80 ms) ─────────────────────────
    win_samples = max(1, int(round(cfg.integration_window_ms * fs / 1000.0)))
    kernel = np.ones(win_samples) / win_samples
    x_int = np.convolve(x_sq, kernel, mode="same")

    # ── Step 4: Candidate peak detection and adaptive dual-threshold ─────────
    min_cand_dist = max(1, int(round(cfg.integration_window_ms * fs / 1000.0)))
    cand_indices, _ = find_peaks(x_int, distance=min_cand_dist)

    if len(cand_indices) == 0:
        return np.array([], dtype=int), np.array([], dtype=float)

    # Initial running estimates from the first 2 seconds (or whole record if short)
    init_win = min(n, int(2.0 * fs))
    init_slice = x_int[:init_win] if init_win > 0 else x_int
    peak_level = float(np.percentile(init_slice, 95))
    noise_level = float(np.percentile(init_slice, 50))
    if peak_level <= noise_level:
        peak_level = noise_level + 1e-6

    refractory_samples = max(1, int(round(cfg.refractory_ms * fs / 1000.0)))
    search_win = max(1, int(round(cfg.search_window_ms * fs / 1000.0)))
    alpha = cfg.threshold_alpha

    detected_peaks: list[int] = []
    last_r_sample = -refractory_samples

    for idx in cand_indices:
        v = x_int[idx]
        thr = alpha * peak_level + (1.0 - alpha) * noise_level

        if v > thr:
            if (idx - last_r_sample) >= refractory_samples:
                # Localize true R-peak in |x_bp| around candidate
                w_start = max(0, idx - search_win)
                w_end = min(n, idx + search_win + 1)
                r_peak = int(w_start + np.argmax(np.abs(x_bp[w_start:w_end])))

                detected_peaks.append(r_peak)
                last_r_sample = r_peak
                # Update running peak level estimate
                peak_level = 0.125 * v + 0.875 * peak_level
            elif len(detected_peaks) > 0 and v > x_int[detected_peaks[-1]]:
                # If a taller peak occurs within refractory window, replace it
                w_start = max(0, idx - search_win)
                w_end = min(n, idx + search_win + 1)
                r_peak = int(w_start + np.argmax(np.abs(x_bp[w_start:w_end])))

                detected_peaks[-1] = r_peak
                last_r_sample = r_peak
                peak_level = 0.125 * v + 0.875 * peak_level
        else:
            # Below threshold: update running noise level estimate
            noise_level = 0.125 * v + 0.875 * noise_level

    # ── Step 5: Refractory blanking guarantee & sorting ────────────────────────
    peak_samples = _apply_refractory(np.array(detected_peaks, dtype=int), refractory_samples)
    peak_samples = np.sort(np.unique(peak_samples)).astype(int)
    peak_times_s = peak_samples / float(fs)

    return peak_samples, peak_times_s


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _bandpass_sos(order: int, low_hz: float, high_hz: float, fs: int) -> np.ndarray:
    nyq = fs / 2.0
    low = max(0.01, min(low_hz / nyq, 0.98))
    high = max(low + 0.01, min(high_hz / nyq, 0.99))
    return butter(order, [low, high], btype="band", output="sos")


def _moving_average(x: np.ndarray, window: int) -> np.ndarray:
    """Causal/centered moving-window integration via convolve."""
    w = max(1, window)
    return np.convolve(x, np.ones(w) / w, mode="same")


def _apply_refractory(peaks: np.ndarray, refractory: int) -> np.ndarray:
    """
    Remove duplicate peaks within the refractory period.
    Keep the first peak in each cluster; discard any peak that falls within
    `refractory` samples of the previous accepted peak.
    """
    if len(peaks) == 0:
        return peaks

    peaks_sorted = np.sort(peaks)
    kept = [peaks_sorted[0]]
    for p in peaks_sorted[1:]:
        if p - kept[-1] >= refractory:
            kept.append(p)

    return np.array(kept, dtype=int)
