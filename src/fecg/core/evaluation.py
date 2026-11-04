"""
src/evaluation.py
──────────────────────────────────────────────────────────────────────────────
Shared evaluation script: QRS matching, beat-detection metrics, waveform error.

Role     : Data Validation & Evaluation Lead
Used by  : all members via run_benchmark.py

Beat-matching rule (from Section 13 of team work plan)
------------------------------------------------------
  Tolerance   : ±50 ms  →  ±12 samples at 250 Hz  (FREEZE before benchmark)
  Matching     : each reference beat → at most one detected beat
                 each detected beat  → at most one reference beat
                 greedy nearest-neighbour within tolerance
  Duplicates  : one detected beat cannot count as multiple TPs

Metrics reported per method per test case
-----------------------------------------
  TP, FP, FN counts
  Sensitivity / Recall  = TP / (TP + FN)
  PPV / Precision       = TP / (TP + FP)
  F1-score              = 2 × Sens × PPV / (Sens + PPV)
  FHR MAE (BPM)         — from fhr.compare_fhr()
  Waveform error        — RMSE and optionally normalised SNR improvement
  Runtime (seconds)

All metrics with zero denominator are reported as None (undefined), not 0 or 1.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from fecg.detection.fhr import FHRResult, FHRComparison, compare_fhr


# ──────────────────────────────────────────────────────────────────────────────
# Constants (frozen; verify from PPR-8 before benchmark)
# ──────────────────────────────────────────────────────────────────────────────

QRS_TOLERANCE_MS = 50.0    # ±50 ms beat-matching window  (CONFIRM_FROM_PPR8)
DEFAULT_FS = 250


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class BeatMetrics:
    """QRS detection performance for one method on one test case."""
    tp: int
    fp: int
    fn: int
    sensitivity: Optional[float]   # None if denominator is 0
    ppv: Optional[float]           # None if denominator is 0
    f1: Optional[float]            # None if denominator is 0
    tolerance_ms: float = QRS_TOLERANCE_MS
    n_ref_beats: int = 0
    n_det_beats: int = 0


@dataclass
class WaveformMetrics:
    """Waveform reconstruction quality for one method on one test case."""
    rmse: float                          # raw-scale RMSE (same units as signal)
    snr_improvement_db: Optional[float]  # SNR improvement (if computable; see formula below)
    # SNR_improvement = 10·log10(power(fecg_ref) / power(fecg_ref - fecg_est))
    # This measures reconstruction quality, not signal-to-noise in a traditional sense.
    correlation: float                   # Pearson correlation (−1 to 1)
    notes: str = ""


@dataclass
class EvalResult:
    """Complete evaluation result for one method on one test case."""
    method_name: str
    variant: str
    test_id: str
    snr_db: int
    case: str
    input_condition: str               # e.g. 'single_channel', 'oracle_assisted'
    beat_metrics: BeatMetrics
    waveform_metrics: WaveformMetrics
    fhr_comparison: FHRComparison
    runtime_s: float
    parameter_notes: str = ""
    failure_notes: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def match_beats(
    ref_samples: np.ndarray,
    det_samples: np.ndarray,
    fs: int = DEFAULT_FS,
    tolerance_ms: float = QRS_TOLERANCE_MS,
) -> tuple[int, int, int]:
    """
    Match detected beats to reference beats using greedy nearest-neighbour
    within a ±tolerance window.

    Parameters
    ----------
    ref_samples : np.ndarray, dtype int
        Sorted reference R-peak sample indices (ground truth).
    det_samples : np.ndarray, dtype int
        Sorted detected R-peak sample indices.
    fs : int
        Sampling frequency in Hz (used to convert tolerance to samples).
    tolerance_ms : float
        Half-window for matching in milliseconds.

    Returns
    -------
    tp, fp, fn : int
        True positives, false positives, false negatives.
    """
    tol_samples = int(round(tolerance_ms * fs / 1000.0))

    ref = np.sort(ref_samples).astype(int)
    det = np.sort(det_samples).astype(int)

    ref_matched = np.zeros(len(ref), dtype=bool)
    det_matched = np.zeros(len(det), dtype=bool)

    # Greedy: for each reference beat, find the nearest unmatched detection
    for ri, r in enumerate(ref):
        best_dist = tol_samples + 1
        best_di = -1
        for di, d in enumerate(det):
            if det_matched[di]:
                continue
            dist = abs(int(r) - int(d))
            if dist <= tol_samples and dist < best_dist:
                best_dist = dist
                best_di = di
        if best_di >= 0:
            ref_matched[ri] = True
            det_matched[best_di] = True

    tp = int(np.sum(ref_matched))
    fp = int(np.sum(~det_matched))
    fn = int(np.sum(~ref_matched))
    return tp, fp, fn


def compute_beat_metrics(
    ref_samples: np.ndarray,
    det_samples: np.ndarray,
    fs: int = DEFAULT_FS,
    tolerance_ms: float = QRS_TOLERANCE_MS,
) -> BeatMetrics:
    """Compute TP/FP/FN and derived metrics."""
    tp, fp, fn = match_beats(ref_samples, det_samples, fs, tolerance_ms)

    sens = tp / (tp + fn) if (tp + fn) > 0 else None
    ppv  = tp / (tp + fp) if (tp + fp) > 0 else None
    f1   = (2 * sens * ppv / (sens + ppv)
            if (sens is not None and ppv is not None and (sens + ppv) > 0)
            else None)

    return BeatMetrics(
        tp=tp, fp=fp, fn=fn,
        sensitivity=sens, ppv=ppv, f1=f1,
        tolerance_ms=tolerance_ms,
        n_ref_beats=len(ref_samples),
        n_det_beats=len(det_samples),
    )


def compute_waveform_metrics(
    fecg_ref: np.ndarray,
    fecg_est: np.ndarray,
    fs: int = DEFAULT_FS,
) -> WaveformMetrics:
    """
    Compute waveform reconstruction quality metrics.

    Requires fecg_ref and fecg_est to have the same length.
    Time alignment must already have been applied by the caller.

    Formula for SNR improvement:
        SNR_imp = 10·log10( power(fecg_ref) / power(fecg_ref − fecg_est) )
    """
    if len(fecg_ref) != len(fecg_est):
        raise ValueError(
            f"Reference length {len(fecg_ref)} ≠ estimate length {len(fecg_est)}. "
            "Verify sampling rates and time alignment before calling this function."
        )

    ref = fecg_ref.astype(np.float64)
    est = fecg_est.astype(np.float64)
    error = ref - est

    rmse = float(np.sqrt(np.mean(error ** 2)))

    power_ref = float(np.mean(ref ** 2))
    power_err = float(np.mean(error ** 2))
    snr_imp: Optional[float] = None
    if power_ref > 0 and power_err > 0:
        snr_imp = 10.0 * np.log10(power_ref / power_err)

    # Pearson correlation
    if np.std(ref) > 0 and np.std(est) > 0:
        corr = float(np.corrcoef(ref, est)[0, 1])
    else:
        corr = 0.0

    notes = (
        f"SNR_imp = 10·log10(power(ref)/power(ref−est)) = "
        f"{snr_imp:.2f} dB" if snr_imp is not None else "SNR_imp undefined (zero power)"
    )

    return WaveformMetrics(
        rmse=rmse,
        snr_improvement_db=snr_imp,
        correlation=corr,
        notes=notes,
    )


def eval_result_to_row(result: EvalResult) -> dict:
    """Convert an EvalResult to a flat dict for CSV export."""
    bm = result.beat_metrics
    wm = result.waveform_metrics
    fhr = result.fhr_comparison
    return {
        "method":           result.method_name,
        "variant":          result.variant,
        "test_id":          result.test_id,
        "snr_db":           result.snr_db,
        "case":             result.case,
        "input_condition":  result.input_condition,
        "tp":               bm.tp,
        "fp":               bm.fp,
        "fn":               bm.fn,
        "sensitivity":      bm.sensitivity,
        "ppv":              bm.ppv,
        "f1":               bm.f1,
        "n_ref_beats":      bm.n_ref_beats,
        "n_det_beats":      bm.n_det_beats,
        "fhr_mae_bpm":      fhr.mean_abs_error_bpm,
        "fhr_rmse_bpm":     fhr.rmse_bpm,
        "waveform_rmse":    wm.rmse,
        "snr_improvement_db": wm.snr_improvement_db,
        "correlation":      wm.correlation,
        "runtime_s":        result.runtime_s,
        "parameter_notes":  result.parameter_notes,
        "failure_notes":    result.failure_notes,
    }
