"""
src/fhr.py
──────────────────────────────────────────────────────────────────────────────
Fetal Heart Rate (FHR) calculation from detected fetal R-peak sample indices.

Owner    : Vivek (FHR and shared evaluation metrics)
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

from __future__ import annotations

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
