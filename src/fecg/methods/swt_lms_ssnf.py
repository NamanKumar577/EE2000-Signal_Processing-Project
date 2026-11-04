"""
src/methods/swt_lms_ssnf.py
──────────────────────────────────────────────────────────────────────────────
SWT + LMS + SSNF hybrid fetal ECG extraction.

Owner             : Astitva
Primary reference : 1-s2.0-S0010482513002023-main.pdf
Supporting refs   : Signal_Processing_Techniques_for_Removin.pdf,
                    Digital_Filters_for_Real-Time_ECG_Signal_Processing_Using_Microprocessors.pdf

Pipeline (applied in order)
----------------------------
1.  Detect maternal R-peaks from the abdominal mixture (used for both
    single-channel synthetic reference generation and oracle mode).
2.  Build a maternal reference signal:
      - Single-channel mode (default / deployable):
          Synthesise a maternal reference by MECG template averaging and
          reconstruction from detected maternal R-peaks on the mixture.
          This avoids any use of the clean mecg ground truth.
      - Oracle-assisted mode (diagnostic / upper bound):
          Caller passes reference_channel=<clean mecg array> as a kwarg.
          Results are labelled input_condition='oracle_assisted' and must
          NOT appear in the main comparison table.
3.  Apply Stationary Wavelet Transform (SWT) to both the mixture and the
    reference simultaneously, producing shift-invariant subband coefficients.
4.  Apply LMS adaptive filtering in each wavelet subband independently to
    cancel the maternal component.  LMS-only output is also saved for ablation.
5.  Apply the SSNF (Spatial Subband Noise Filter) — inter-scale soft
    thresholding of wavelet coefficients to further suppress residual maternal
    energy and EMG noise while preserving the sharp fetal QRS spikes.
6.  Reconstruct the estimated fetal ECG via inverse SWT (ISWT).

Reference strategy note (work plan Section 4, Task 4)
------------------------------------------------------
The primary paper (Karvounis et al., 2013) uses a real thoracic ECG reference
channel.  FECGSYNDB synthetic records (sub01, l1) do NOT provide a standalone
thoracic reference file; only abdominal mixture components are present.  Two
modes are therefore offered:

  - single_channel (default):  a synthetic maternal reference is derived from
    the abdominal mixture itself by constructing a template-average maternal
    beat at detected MECG R-peaks.  This is a faithful single-channel
    adaptation reported as 'single_channel'.

  - oracle_assisted:  pass reference_channel=mecg_array as a kwarg.  The clean
    maternal component acts as the LMS reference.  This is an UPPER-BOUND
    diagnostic experiment only; never compare directly with deployable results.

Ablation variants
-----------------
  variant = 'lms_only'      -- runs steps 1-4 only (no SSNF, no ISWT)
  variant = 'swt_lms_ssnf'  -- full pipeline (default)
"""

from __future__ import annotations

import time
from typing import Any, Optional

import numpy as np
import pywt
from scipy.signal import find_peaks, butter, sosfiltfilt

from .base import BaseExtractor


# ──────────────────────────────────────────────────────────────────────────────
# Default configuration
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_CONFIG: dict = {
    # Wavelet parameters
    "wavelet": "sym4",            # mother wavelet; sym4 is smooth and close to QRS morphology
    "swt_levels": 4,              # number of SWT decomposition levels

    # LMS parameters
    "lms_mu": 0.05,               # NLMS step size (learning rate)
    "lms_filter_order": 32,       # number of adaptive filter taps

    # SSNF parameters
    "ssnf_threshold_scale": 3.0,  # soft threshold = scale x MAD-based noise std per subband
    "ssnf_interscale_corr": True, # use inter-scale product to sharpen threshold mask

    # Maternal R-peak detection (on raw mixture)
    "maternal_min_distance_ms": 400,    # min RR interval <= 150 BPM
    "maternal_height_fraction": 0.45,   # fraction of robust amplitude scale

    # Template construction for synthetic reference
    "template_half_window_ms": 300,     # half-window around each maternal R-peak (ms)

    # Variant selection
    "variant": "swt_lms_ssnf",   # 'lms_only' | 'swt_lms_ssnf'
}


# ──────────────────────────────────────────────────────────────────────────────
# Main extractor class
# ──────────────────────────────────────────────────────────────────────────────

class SWTLMSSNFExtractor(BaseExtractor):
    """
    SWT + LMS + SSNF hybrid fetal ECG extractor (Astitva's method).

    Parameters
    ----------
    fs : int
        Sampling frequency in Hz (default 250).
    config : dict, optional
        Override any key from _DEFAULT_CONFIG.  Document any changes.

    Usage (benchmark runner)
    ------------------------
    extractor = SWTLMSSNFExtractor(fs=250)
    fecg_est, meta = extractor.run(mixture)                          # single-channel mode
    fecg_est, meta = extractor.run(mixture, reference_channel=mecg)  # oracle-assisted mode
    """

    DESCRIPTION = (
        "SWT-LMS-SSNF hybrid extraction: Stationary Wavelet Transform subband "
        "decomposition + per-subband LMS adaptive maternal cancellation + "
        "Spatial Subband Noise Filter (SSNF) inter-scale soft-thresholding + "
        "Inverse SWT reconstruction.  (Karvounis et al. 2013 adaptation)"
    )
    INPUT_SIGNALS = "Single-channel abdominal mixture; optional thoracic/maternal reference"
    REFERENCE_NEEDED = True   # original paper requires thoracic reference
    IS_CAUSAL = False         # uses SWT (offline) and zero-phase operations

    def __init__(self, fs: int = 250, config: dict | None = None):
        super().__init__(fs=fs, config=config)
        # Merge caller config over defaults
        self._cfg: dict = {**_DEFAULT_CONFIG, **(config or {})}

    # ──────────────────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────────────────

    def extract(
        self,
        mixture: np.ndarray,
        **kwargs: Any,
    ) -> tuple[np.ndarray, dict]:
        """
        Run SWT-LMS-SSNF fetal ECG extraction.

        Parameters
        ----------
        mixture : np.ndarray, shape (n_samples,)
            Preprocessed single-channel abdominal mixture.
        reference_channel : np.ndarray, optional kwarg
            If provided, treated as oracle-assisted maternal reference (clean mecg).
            Results will be labelled input_condition='oracle_assisted'.

        Returns
        -------
        fecg_est : np.ndarray, shape (n_samples,)
            Estimated fetal ECG waveform.
        metadata : dict
            Conforming to BaseExtractor OUTPUT_KEYS contract.
        """
        t_start = time.perf_counter()
        cfg = self._cfg
        fs = self.fs
        variant = cfg["variant"]

        oracle_ref: Optional[np.ndarray] = kwargs.get("reference_channel", None)
        input_condition = "oracle_assisted" if oracle_ref is not None else "single_channel"

        # ── Step 1: Detect maternal R-peaks ───────────────────────────────────
        maternal_peaks = self._detect_maternal_peaks(mixture, fs, cfg)

        # ── Step 2: Build maternal reference signal ────────────────────────────
        if oracle_ref is not None:
            reference = np.asarray(oracle_ref, dtype=np.float64)
            if reference.shape != mixture.shape:
                raise ValueError(
                    f"reference_channel shape {reference.shape} does not match "
                    f"mixture shape {mixture.shape}."
                )
        else:
            # Single-channel: synthesise maternal reference from detected peaks
            reference = self._build_synthetic_reference(mixture, maternal_peaks, fs, cfg)

        # ── Step 3 + 4 (+ 5 + 6): Run the chosen variant ──────────────────────
        if variant == "lms_only":
            fecg_est = self._run_lms_only(mixture, reference, cfg)
        else:
            # Full SWT-LMS-SSNF pipeline
            fecg_est = self._run_swt_lms_ssnf(mixture, reference, fs, cfg)

        runtime = time.perf_counter() - t_start

        metadata = {
            "method_name": "SWT_LMS_SSNF",
            "variant": variant,
            "input_condition": input_condition,
            "runtime_s": runtime,
            "parameter_notes": (
                f"wavelet={cfg['wavelet']}, levels={cfg['swt_levels']}, "
                f"lms_mu={cfg['lms_mu']}, lms_order={cfg['lms_filter_order']}, "
                f"ssnf_threshold_scale={cfg['ssnf_threshold_scale']}, "
                f"n_maternal_peaks={len(maternal_peaks)}, "
                f"mode={input_condition}"
            ),
            "is_causal": self.IS_CAUSAL,
        }
        return fecg_est, metadata

    # ──────────────────────────────────────────────────────────────────────────
    # Step 1: Maternal R-peak detection
    # ──────────────────────────────────────────────────────────────────────────

    def _detect_maternal_peaks(
        self, signal: np.ndarray, fs: int, cfg: dict
    ) -> np.ndarray:
        """
        Detect maternal R-peaks from the abdominal mixture.
        Uses amplitude-threshold peak detection on the absolute signal.
        The maternal QRS is typically the dominant high-amplitude component.
        """
        min_dist = max(1, int(cfg["maternal_min_distance_ms"] / 1000.0 * fs))
        # Robust amplitude scale (98th percentile of absolute values)
        scale = float(np.percentile(np.abs(signal), 98))
        if scale < 1e-10:
            return np.array([], dtype=int)
        height_thresh = cfg["maternal_height_fraction"] * scale
        peaks, _ = find_peaks(signal, height=height_thresh, distance=min_dist)
        # Also check negative polarity
        neg_peaks, _ = find_peaks(-signal, height=height_thresh, distance=min_dist)
        all_peaks = np.sort(np.concatenate([peaks, neg_peaks]))
        # Re-apply distance constraint after merging positive and negative peaks
        if len(all_peaks) > 1:
            keep = [all_peaks[0]]
            for p in all_peaks[1:]:
                if p - keep[-1] >= min_dist:
                    keep.append(p)
            all_peaks = np.array(keep, dtype=int)
        return all_peaks

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Synthetic maternal reference construction (single-channel mode)
    # ──────────────────────────────────────────────────────────────────────────

    def _build_synthetic_reference(
        self,
        mixture: np.ndarray,
        maternal_peaks: np.ndarray,
        fs: int,
        cfg: dict,
    ) -> np.ndarray:
        """
        Construct a synthetic maternal reference signal for single-channel LMS.

        Strategy
        --------
        For each detected maternal R-peak, extract a window of the mixture,
        align all windows, compute the median template (robust to fetal
        contamination), then reconstruct a continuous maternal reference by
        placing the template at each detected R-peak location.

        The reconstructed reference retains the gross MECG morphology and is
        suitable as the LMS reference input.  This avoids requiring a real
        thoracic lead and is reported as input_condition='single_channel'.
        """
        n = len(mixture)
        hw = int(cfg["template_half_window_ms"] / 1000.0 * fs)  # half window in samples

        if len(maternal_peaks) < 3:
            # Fallback: high-pass the mixture as a rough maternal proxy
            from scipy.signal import butter, sosfiltfilt
            sos = butter(4, 0.5 / (fs / 2.0), btype="high", output="sos")
            return sosfiltfilt(sos, mixture)

        # Collect aligned beat windows
        segments = []
        for pk in maternal_peaks:
            lo, hi = pk - hw, pk + hw + 1
            if lo >= 0 and hi <= n:
                segments.append(mixture[lo:hi])

        if len(segments) == 0:
            return np.zeros_like(mixture)

        # Template = median across aligned segments (robust to fetal contamination)
        template = np.median(np.stack(segments, axis=0), axis=0)

        # Reconstruct continuous reference
        reference = np.zeros(n, dtype=np.float64)
        counts = np.zeros(n, dtype=np.float64)
        for pk in maternal_peaks:
            lo, hi = pk - hw, pk + hw + 1
            if lo >= 0 and hi <= n:
                reference[lo:hi] += template
                counts[lo:hi] += 1.0

        # Normalise overlapping regions
        mask = counts > 0
        reference[mask] /= counts[mask]

        return reference

    # ──────────────────────────────────────────────────────────────────────────
    # Ablation baseline: LMS only (no SWT, no SSNF)
    # ──────────────────────────────────────────────────────────────────────────

    def _run_lms_only(
        self, mixture: np.ndarray, reference: np.ndarray, cfg: dict
    ) -> np.ndarray:
        """
        Ablation baseline: time-domain LMS adaptive filter applied directly
        to the mixture with the maternal reference as the LMS input.
        No wavelet decomposition or SSNF stage.

        LMS formulation
        ---------------
        error(n) = mixture(n) - w^T(n) * ref_window(n)
        w(n+1)   = w(n) + mu * error(n) * ref_window(n)
        Output   = error  (residual ~ estimated FECG after maternal cancellation)
        """
        return _lms_filter(mixture, reference, cfg["lms_mu"], cfg["lms_filter_order"])

    # ──────────────────────────────────────────────────────────────────────────
    # Full SWT-LMS-SSNF pipeline
    # ──────────────────────────────────────────────────────────────────────────

    def _run_swt_lms_ssnf(
        self,
        mixture: np.ndarray,
        reference: np.ndarray,
        fs: int,
        cfg: dict,
    ) -> np.ndarray:
        """
        Full pipeline:
          3. SWT decompose mixture + reference
          4. Per-subband LMS adaptive cancellation
          5. SSNF inter-scale soft thresholding on residual coefficients
          6. ISWT reconstruct fetal ECG
        """
        wavelet = cfg["wavelet"]
        levels = cfg["swt_levels"]
        mu = cfg["lms_mu"]
        order = cfg["lms_filter_order"]

        # Pad signal length to be divisible by 2^levels (required by pywt.swt)
        n_orig = len(mixture)
        pad_len = _next_swt_length(n_orig, levels)
        mix_pad = _pad_signal(mixture, pad_len)
        ref_pad = _pad_signal(reference, pad_len)

        # ── Step 3: SWT ───────────────────────────────────────────────────────
        # pywt.swt returns [(cA_n, cD_n), ..., (cA_1, cD_1)]
        mix_coeffs = pywt.swt(mix_pad, wavelet, level=levels)
        ref_coeffs = pywt.swt(ref_pad, wavelet, level=levels)

        # ── Step 4: Per-subband LMS ───────────────────────────────────────────
        residual_coeffs = []
        for (mix_cA, mix_cD), (ref_cA, ref_cD) in zip(mix_coeffs, ref_coeffs):
            # LMS on detail coefficients (maternal energy concentrated here)
            res_cD = _lms_filter(mix_cD, ref_cD, mu, order)
            # LMS on approximation coefficients for thorough cancellation
            res_cA = _lms_filter(mix_cA, ref_cA, mu, order)
            residual_coeffs.append((res_cA, res_cD))

        # ── Step 5: SSNF — inter-scale soft thresholding ─────────────────────
        if cfg["ssnf_interscale_corr"]:
            ssnf_coeffs = _apply_ssnf(residual_coeffs, cfg["ssnf_threshold_scale"])
        else:
            ssnf_coeffs = _apply_soft_threshold_only(
                residual_coeffs, cfg["ssnf_threshold_scale"]
            )

        # ── Step 6: ISWT reconstruction ──────────────────────────────────────
        fecg_padded = pywt.iswt(ssnf_coeffs, wavelet)

        # Strip padding and return original length
        fecg_raw = fecg_padded[:n_orig]

        # Multi-scale sub-band filter (8-38 Hz) to isolate fetal QRS
        if len(fecg_raw) > int(fs * 0.1):
            nyq = 0.5 * fs
            low = max(0.01, min(8.0 / nyq, 0.95))
            high = max(low + 0.01, min(38.0 / nyq, 0.99))
            sos = butter(3, [low, high], btype="band", output="sos")
            fecg_est = sosfiltfilt(sos, fecg_raw)
            std_f = float(np.std(fecg_est))
            std_r = float(np.std(fecg_raw))
            if std_f > 1e-9 and std_r > 1e-9:
                fecg_est = fecg_est * (std_r / std_f)
        else:
            fecg_est = fecg_raw.copy()

        return fecg_est


# ──────────────────────────────────────────────────────────────────────────────
# Internal helper functions
# ──────────────────────────────────────────────────────────────────────────────

def _lms_filter(
    desired: np.ndarray,
    reference: np.ndarray,
    mu: float,
    order: int,
) -> np.ndarray:
    """
    Normalized FIR LMS (NLMS) adaptive filter.
    """
    n = len(desired)
    w = np.zeros(order, dtype=np.float64)
    error = np.zeros(n, dtype=np.float64)

    # Normalise reference amplitude to avoid step-size sensitivity
    ref_power = float(np.var(reference))
    if ref_power < 1e-20:
        return desired.copy()
    ref_norm = reference / (np.sqrt(ref_power) + 1e-10)

    for i in range(order, n):
        x = ref_norm[i - order: i][::-1]   # flip for convolution convention
        y = np.dot(w, x)                    # filter output (maternal estimate)
        e = desired[i] - y                  # error ~ fetal signal
        norm_x = float(np.dot(x, x)) + 1e-4
        w += (mu / norm_x) * e * x          # NLMS weight update
        error[i] = e

    # Edges (first `order` samples) -- copy input to avoid zero artifact
    error[:order] = desired[:order]
    return error


def _next_swt_length(n: int, levels: int) -> int:
    """Return smallest integer >= n divisible by 2**levels (required by pywt.swt)."""
    divisor = 2 ** levels
    return int(np.ceil(n / divisor) * divisor)


def _pad_signal(signal: np.ndarray, target_len: int) -> np.ndarray:
    """Reflect-pad signal to target_len samples."""
    n = len(signal)
    if n == target_len:
        return signal.astype(np.float64)
    pad_right = target_len - n
    return np.pad(signal.astype(np.float64), (0, pad_right), mode="reflect")


def _mad_std(x: np.ndarray) -> float:
    """Robust noise std estimate from Median Absolute Deviation (Donoho 1994)."""
    return float(np.median(np.abs(x - np.median(x))) / 0.6745)


def _apply_ssnf(
    coeffs: list[tuple[np.ndarray, np.ndarray]],
    threshold_scale: float,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Spatial Subband Noise Filter (SSNF) with inter-scale product sharpening.

    For each detail subband (cD), compute an inter-scale product between
    adjacent levels to distinguish true signal spikes (correlated across
    scales) from noise (not correlated across scales).  Apply soft thresholding
    with an adaptive, data-driven threshold — relaxed where inter-scale
    product is high (fetal QRS), tight where it is low (noise).

    Reference: Mallat & Hwang (1992) -- inter-scale product for signal detection.
    """
    n_levels = len(coeffs)
    out_coeffs = []

    for lvl in range(n_levels):
        cA, cD = coeffs[lvl]

        # Estimate noise std from this subband's detail coefficients
        sigma = _mad_std(cD)
        thresh = threshold_scale * sigma

        # Inter-scale product: use adjacent levels' details for sharpening
        if 0 < lvl < n_levels - 1:
            _, cD_prev = coeffs[lvl - 1]
            _, cD_next = coeffs[lvl + 1]
            inter_scale = np.abs(cD * cD_prev) * np.abs(cD * cD_next)
            is_max = np.max(inter_scale)
            if is_max > 1e-20:
                inter_scale /= is_max
        else:
            # Boundary levels: self-product
            inter_scale = np.abs(cD ** 2)
            is_max = np.max(inter_scale)
            if is_max > 1e-20:
                inter_scale /= is_max

        # Adaptive threshold: relax where inter-scale product is high (signal)
        # Coefficients with high inter-scale product are kept; others shrunk.
        effective_thresh = thresh * (1.0 - inter_scale)
        cD_ssnf = np.sign(cD) * np.maximum(np.abs(cD) - effective_thresh, 0.0)

        # Suppress approximation coefficients (cA) to eliminate low-frequency maternal T-waves (0-7.8 Hz)
        out_coeffs.append((np.zeros_like(cA), cD_ssnf))

    return out_coeffs


def _apply_soft_threshold_only(
    coeffs: list[tuple[np.ndarray, np.ndarray]],
    threshold_scale: float,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Simple uniform soft thresholding of detail coefficients per subband.
    Used when ssnf_interscale_corr is disabled.
    """
    out = []
    for cA, cD in coeffs:
        sigma = _mad_std(cD)
        thresh = threshold_scale * sigma
        cD_soft = np.sign(cD) * np.maximum(np.abs(cD) - thresh, 0.0)
        out.append((np.zeros_like(cA), cD_soft))
    return out
