"""
src/mixture.py
──────────────────────────────────────────────────────────────────────────────
Centralized abdominal mixture construction from FECGSYNDB components.

Role     : Data Validation & Evaluation Lead
Used by  : all members — everyone MUST call build_mixture() rather than
           constructing their own combination.

Mixture equation (FECGSYNDB convention):
    AECG = mecg + fecg1 + noise1 + noise2

Reference: FECGSYNDB dataset documentation and .hea header comment fields
    #SNRmn  — SNR between maternal ECG and noise (dB)
    #SNRfm  — SNR between fetal ECG and maternal ECG (dB)

Validation
----------
build_mixture() checks component alignment and returns the mixture with an
audit record.  Call check_mixture_snr() to verify the reconstruction matches
the expected SNR within a tolerance.

NOTE: The clean fecg1 component is included in the mixture construction
(it is part of the abdominal recording model) but must NEVER be given to
an extraction algorithm as a reference input.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
# Data class
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class MixtureResult:
    """Output of build_mixture()."""
    aecg: np.ndarray               # Reconstructed abdominal ECG mixture (n_samples,)
    mecg: np.ndarray               # Maternal component used
    fecg_ref: np.ndarray           # Fetal component used (evaluation reference only)
    noise1: np.ndarray             # Noise 1 component used
    noise2: np.ndarray             # Noise 2 component used
    fs: int                        # Sampling frequency
    n_samples: int                 # Number of samples
    snr_fm_estimated_db: float     # Estimated fetal-to-maternal SNR from reconstruction
    snr_mn_estimated_db: float     # Estimated maternal-to-noise SNR from reconstruction
    notes: str                     # Audit notes


# ──────────────────────────────────────────────────────────────────────────────
# Core mixture builder
# ──────────────────────────────────────────────────────────────────────────────

def build_mixture(
    mecg: np.ndarray,
    fecg: np.ndarray,
    noise1: np.ndarray,
    noise2: np.ndarray,
    fs: int = 250,
) -> MixtureResult:
    """
    Reconstruct the abdominal ECG mixture from its four separate components.

    FECGSYNDB mixture equation:
        AECG(t) = mecg(t) + fecg(t) + noise1(t) + noise2(t)

    All four components must have the same length. No additional scaling is
    applied here — the components are already at their correct relative
    amplitudes as stored in the .dat files (physical units, gain applied by
    wfdb.rdrecord).

    Parameters
    ----------
    mecg, fecg, noise1, noise2 : np.ndarray, shape (n_samples,)
        Individual signal components, loaded via data_loader.load_record().
    fs : int
        Sampling frequency in Hz.

    Returns
    -------
    MixtureResult
        Contains the mixture, its components, estimated SNRs, and audit notes.
    """
    # ── Alignment check ──────────────────────────────────────────────────────
    lengths = [len(mecg), len(fecg), len(noise1), len(noise2)]
    if len(set(lengths)) != 1:
        raise ValueError(
            f"Component length mismatch — mecg:{lengths[0]}, fecg:{lengths[1]}, "
            f"noise1:{lengths[2]}, noise2:{lengths[3]}"
        )

    n = lengths[0]
    aecg = mecg + fecg + noise1 + noise2

    # ── SNR estimation ────────────────────────────────────────────────────────
    noise_combined = noise1 + noise2

    snr_fm_db = _power_ratio_db(fecg, mecg)
    snr_mn_db = _power_ratio_db(mecg, noise_combined)

    notes = (
        "Mixture: AECG = mecg + fecg + noise1 + noise2 (simple sum, no extra scaling). "
        f"Estimated SNR_fm = {snr_fm_db:.2f} dB, SNR_mn = {snr_mn_db:.2f} dB."
    )

    return MixtureResult(
        aecg=aecg,
        mecg=mecg,
        fecg_ref=fecg,
        noise1=noise1,
        noise2=noise2,
        fs=fs,
        n_samples=n,
        snr_fm_estimated_db=snr_fm_db,
        snr_mn_estimated_db=snr_mn_db,
        notes=notes,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Validation utility
# ──────────────────────────────────────────────────────────────────────────────

def check_mixture_snr(
    result: MixtureResult,
    expected_snr_mn_db: float,
    tolerance_db: float = 1.5,
) -> bool:
    """
    Verify that the reconstructed mixture SNR (maternal vs noise) matches
    the expected value from the .hea header (#SNRmn field) within a tolerance.

    Parameters
    ----------
    result : MixtureResult
    expected_snr_mn_db : float
        Expected SNR in dB from the header #SNRmn field.
    tolerance_db : float
        Acceptable absolute deviation (default 1.5 dB).

    Returns
    -------
    bool
        True if within tolerance.  Raises ValueError otherwise.
    """
    diff = abs(result.snr_mn_estimated_db - expected_snr_mn_db)
    if diff > tolerance_db:
        raise ValueError(
            f"Mixture SNR check failed: estimated {result.snr_mn_estimated_db:.2f} dB, "
            f"expected {expected_snr_mn_db:.2f} dB, difference {diff:.2f} dB "
            f"(tolerance ±{tolerance_db} dB).\n"
            f"Check component scaling or mixture equation."
        )
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _power_ratio_db(signal: np.ndarray, reference: np.ndarray) -> float:
    """Return 10·log10(power(signal) / power(reference)) in dB."""
    power_sig = float(np.mean(signal ** 2))
    power_ref = float(np.mean(reference ** 2))
    if power_ref == 0.0:
        return float("inf")
    return 10.0 * np.log10(power_sig / power_ref)
