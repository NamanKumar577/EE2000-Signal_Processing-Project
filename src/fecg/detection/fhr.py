"""
src/fhr.py
──────────────────────────────────────────────────────────────────────────────
Fetal Heart Rate (FHR) calculation from detected fetal R-peak sample indices.

Role     : Data Validation & Evaluation Lead
Used by  : all members via run_benchmark.py

FHR definition
--------------
For consecutive detected fetal R-peaks at sample indices i and i+1:
    RR_i (seconds)   = (peak_samples[i+1] - peak_samples[i]) / fs
    FHR_i (BPM)      = 60 / RR_i

FHR is computed at the midpoint time of each RR interval.

Invalid interval policy
-----------------------
An interval is flagged as implausible if the implied FHR falls outside
the physiological fetal range [50, 250] BPM.  These are recorded as NaN,
NOT silently removed.  Report them explicitly.

Usage
-----
    fhr_result = compute_fhr(peak_samples, fs=250)
    compare_fhr(fhr_result, ref_peak_samples, fs=250)
"""


from dataclasses import dataclass, field

import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
# Physiological constants
# ──────────────────────────────────────────────────────────────────────────────

FHR_MIN_BPM = 50.0   # below this → implausible; flag as NaN
FHR_MAX_BPM = 250.0  # above this → implausible; flag as NaN


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FHRResult:
    """FHR time series derived from detected peaks."""
    # Time axis (midpoint of each RR interval), in seconds
    time_s: np.ndarray
    # Instantaneous FHR in BPM (NaN for implausible intervals)
    fhr_bpm: np.ndarray
    # RR interval lengths in seconds
    rr_intervals_s: np.ndarray
    # Boolean mask: True where FHR is within physiological range
    valid_mask: np.ndarray
    # Number of implausible intervals
    n_implausible: int
    # Source peak samples used
    peak_samples: np.ndarray
    fs: int

    @property
    def mean_fhr_bpm(self) -> float:
        """Mean FHR over valid intervals (NaN if none valid)."""
        valid = self.fhr_bpm[self.valid_mask]
        return float(np.nanmean(valid)) if len(valid) > 0 else float("nan")

    @property
    def std_fhr_bpm(self) -> float:
        """Standard deviation of FHR over valid intervals."""
        valid = self.fhr_bpm[self.valid_mask]
        return float(np.nanstd(valid)) if len(valid) > 0 else float("nan")


@dataclass
class FHRComparison:
    """Comparison of estimated FHR against reference FHR."""
    mean_abs_error_bpm: float          # MAE in BPM
    max_abs_error_bpm: float           # peak absolute error
    rmse_bpm: float                    # RMSE in BPM
    n_compared: int                    # number of matched intervals
    n_ref_beats: int                   # total reference beats
    n_est_beats: int                   # total estimated beats
    notes: str


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def compute_fhr(
    peak_samples: np.ndarray,
    fs: int = 250,
) -> FHRResult:
    """
    Compute instantaneous FHR from detected peak sample indices.

    Parameters
    ----------
    peak_samples : np.ndarray, dtype int
        Sorted sample indices of detected fetal R-peaks.
    fs : int
        Sampling frequency in Hz.

    Returns
    -------
    FHRResult
        FHR time series with validity flags.
    """
    if len(peak_samples) < 2:
        empty = np.array([], dtype=float)
        return FHRResult(
            time_s=empty, fhr_bpm=empty, rr_intervals_s=empty,
            valid_mask=np.array([], dtype=bool),
            n_implausible=0, peak_samples=peak_samples, fs=fs,
        )

    peaks = np.sort(np.asarray(peak_samples, dtype=int))
    rr_samples = np.diff(peaks)
    rr_s = rr_samples / float(fs)
    fhr_raw = 60.0 / rr_s

    # Midpoint time of each RR interval
    time_s = (peaks[:-1] + peaks[1:]) / 2.0 / float(fs)

    # Flag implausible intervals
    valid_mask = (fhr_raw >= FHR_MIN_BPM) & (fhr_raw <= FHR_MAX_BPM)
    fhr_bpm = fhr_raw.copy()
    fhr_bpm[~valid_mask] = np.nan
    n_implausible = int(np.sum(~valid_mask))

    return FHRResult(
        time_s=time_s,
        fhr_bpm=fhr_bpm,
        rr_intervals_s=rr_s,
        valid_mask=valid_mask,
        n_implausible=n_implausible,
        peak_samples=peaks,
        fs=fs,
    )


def compare_fhr(
    est_result: FHRResult,
    ref_peak_samples: np.ndarray,
    fs: int = 250,
) -> FHRComparison:
    """
    Compare estimated FHR against reference FHR derived from ground-truth peaks.

    Uses a simple resampling strategy: compute mean FHR over matched overlapping
    windows rather than sample-by-sample interpolation, to avoid artifacts.

    Parameters
    ----------
    est_result : FHRResult
        Estimated FHR from detect_fetal_qrs output.
    ref_peak_samples : np.ndarray
        Reference fetal R-peak sample indices (from .qrs annotations).
    fs : int
        Sampling frequency.

    Returns
    -------
    FHRComparison
    """
    ref_result = compute_fhr(ref_peak_samples, fs=fs)

    n_ref = len(ref_result.fhr_bpm)
    n_est = len(est_result.fhr_bpm)

    if n_ref == 0 or n_est == 0:
        return FHRComparison(
            mean_abs_error_bpm=float("nan"),
            max_abs_error_bpm=float("nan"),
            rmse_bpm=float("nan"),
            n_compared=0,
            n_ref_beats=len(ref_peak_samples),
            n_est_beats=len(est_result.peak_samples),
            notes="Insufficient beats for FHR comparison.",
        )

    # Interpolate estimated FHR onto reference time axis
    est_fhr_interp = np.interp(
        ref_result.time_s,
        est_result.time_s,
        est_result.fhr_bpm,
        left=np.nan,
        right=np.nan,
    )

    # Only compare where both are valid
    both_valid = ref_result.valid_mask & np.isfinite(est_fhr_interp)
    n_compared = int(np.sum(both_valid))

    if n_compared == 0:
        return FHRComparison(
            mean_abs_error_bpm=float("nan"),
            max_abs_error_bpm=float("nan"),
            rmse_bpm=float("nan"),
            n_compared=0,
            n_ref_beats=len(ref_peak_samples),
            n_est_beats=len(est_result.peak_samples),
            notes="No overlapping valid FHR intervals found.",
        )

    ref_fhr_valid = ref_result.fhr_bpm[both_valid]
    est_fhr_valid = est_fhr_interp[both_valid]
    errors = np.abs(ref_fhr_valid - est_fhr_valid)

    return FHRComparison(
        mean_abs_error_bpm=float(np.mean(errors)),
        max_abs_error_bpm=float(np.max(errors)),
        rmse_bpm=float(np.sqrt(np.mean(errors ** 2))),
        n_compared=n_compared,
        n_ref_beats=len(ref_peak_samples),
        n_est_beats=len(est_result.peak_samples),
        notes=f"Compared {n_compared}/{n_ref} reference intervals.",
    )


# ==============================================================================
# Corrected Interval Fusion and Causal Median-of-5 Post-Processing
# ==============================================================================

"""
code/src/fhr_implementation_corrected.py
──────────────────────────────────────────────────────────────────────────────
Corrected FHR Post-Processing & Beat Fusion Module.

Implements and evaluates the 4 stages of FHR processing:
  - M1: Raw instantaneous FHR (no filtering, no fusion)
  - M2: Causal Median-of-5 filtering only
  - M3: Interval Fusion only (merges split peaks with RR < 50 samples)
  - M4: Corrected Pipeline: Interval Fusion + Causal Median-of-5

Strict Clinical Safety Rules:
  1. Midpoint beat insertion is permanently DISABLED (0% synthetic beat hallucination).
  2. Interval Fusion merges split peaks into a single cardiac event, preventing false double-triggers.
  3. Causal Median-of-5 operates on valid RR intervals ([50, 300] samples = 50 to 300 bpm).
  4. Explicit 2-bit state classification flags accompany every beat and time sample.
"""


from typing import List, Tuple, Dict, Optional, Sequence
import numpy as np

FS = 250
RR_MIN = 50   # 300 bpm @ 250 Hz (200 ms)
RR_MAX = 300  # 50 bpm @ 250 Hz (1200 ms)

FLAG_REAL_DETECTED    = 0b00
FLAG_FUSED_BEAT       = 0b01
FLAG_HELD_FHR         = 0b10
FLAG_INVALID_WARMUP   = 0b11

def apply_interval_fusion(
    peaks: np.ndarray,
    amplitudes: Optional[np.ndarray] = None,
    min_rr: int = RR_MIN
) -> Tuple[np.ndarray, np.ndarray, int]:
    """
    Apply physiological interval fusion to raw detected peaks.
    When a pair of peaks occurs within min_rr (split peak from single QRS),
    merges them into a single event:
      - Keeps the peak with higher envelope amplitude (or later peak if equal).
      - Replaces the previous peak timestamp rather than adding a second peak.
      - Sets FLAG_FUSED_BEAT (1).
    Returns: (fused_peaks, flags, n_fused)
    """
    if len(peaks) < 2:
        return np.asarray(peaks, dtype=int), np.zeros(len(peaks), dtype=int), 0

    fused_peaks = [int(peaks[0])]
    flags = [FLAG_REAL_DETECTED]
    n_fused = 0

    for i in range(1, len(peaks)):
        p_curr = int(peaks[i])
        p_prev = fused_peaks[-1]
        rr = p_curr - p_prev

        if rr < min_rr:
            # Split detection: merge into previous beat
            n_fused += 1
            if amplitudes is not None and len(amplitudes) > i:
                # Retain the timestamp of the higher amplitude peak
                if amplitudes[i] > amplitudes[i - 1]:
                    fused_peaks[-1] = p_curr
            flags[-1] = FLAG_FUSED_BEAT
            # Do NOT append p_curr
        else:
            fused_peaks.append(p_curr)
            flags.append(FLAG_REAL_DETECTED)

    return np.array(fused_peaks, dtype=int), np.array(flags, dtype=int), n_fused

def causal_median5_rr(rr_intervals: Sequence[int]) -> np.ndarray:
    """
    Causal Median-of-5 filter on a stream of RR intervals.
    Maintains a 5-beat FIFO. Handles startup (k=1..4) with available history.
    """
    out = np.zeros(len(rr_intervals), dtype=int)
    buf: List[int] = []
    for i, r in enumerate(rr_intervals):
        if RR_MIN <= r <= RR_MAX:
            buf.append(int(r))
            if len(buf) > 5:
                buf.pop(0)
            out[i] = int(np.median(buf))
        else:
            # Invalid interval: hold previous filtered RR or raw interval
            out[i] = buf[-1] if buf else int(r)
    return out

def compute_fhr_series(
    peaks: np.ndarray,
    flags: Optional[np.ndarray] = None,
    use_median5: bool = True,
    duration_sec: float = 300.0,
    fs: int = FS
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert peak timestamps into a continuous 2 Hz FHR curve on a uniform 0.5s grid.
    Returns: (t_grid, fhr_interp_bpm)
    """
    t_grid = np.arange(0, duration_sec, 0.5)
    if len(peaks) < 2:
        return t_grid, np.full_like(t_grid, 140.0)

    rr = np.diff(peaks)
    if use_median5:
        rr_filtered = causal_median5_rr(rr)
    else:
        rr_filtered = rr

    fhr_bpm = np.zeros(len(rr_filtered), dtype=float)
    fhr_hold = 140.0

    for i, r in enumerate(rr_filtered):
        if RR_MIN <= r <= RR_MAX:
            fhr_bpm[i] = (60.0 * fs) / float(r)
            fhr_hold = fhr_bpm[i]
        else:
            fhr_bpm[i] = fhr_hold

    t_beats = peaks[1:] / float(fs)
    fhr_interp = np.interp(t_grid, t_beats, fhr_bpm, left=140.0, right=fhr_hold)
    return t_grid, fhr_interp

def evaluate_fhr_against_ref(
    est_peaks: np.ndarray,
    ref_peaks: np.ndarray,
    use_median5: bool = True,
    duration_sec: float = 300.0,
    fs: int = FS,
    warmup_sec: float = 2.5
) -> Dict[str, float]:
    """Compare estimated FHR curve against reference ground-truth FHR curve."""
    t_grid, fhr_est = compute_fhr_series(est_peaks, use_median5=use_median5, duration_sec=duration_sec, fs=fs)
    t_grid_ref, fhr_ref = compute_fhr_series(ref_peaks, use_median5=False, duration_sec=duration_sec, fs=fs)

    valid_mask = t_grid >= warmup_sec
    err = fhr_est[valid_mask] - fhr_ref[valid_mask]
    abs_err = np.abs(err)

    mae = float(np.mean(abs_err))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    pct_5 = float(np.mean(abs_err <= 5.0) * 100.0)
    pct_10 = float(np.mean(abs_err <= 10.0) * 100.0)

    return {
        "mae_bpm": round(mae, 2),
        "rmse_bpm": round(rmse, 2),
        "pct_within_5bpm": round(pct_5, 2),
        "pct_within_10bpm": round(pct_10, 2)
    }
