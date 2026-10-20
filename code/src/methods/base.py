"""
src/methods/base.py
──────────────────────────────────────────────────────────────────────────────
Standard extraction interface contract.

Owner    : Naman (integration lead)
All extraction method classes MUST inherit from BaseExtractor and implement
extract().  This guarantees the benchmark runner can call every method
identically without method-specific logic.

Interface contract
------------------
Input  : 1-D preprocessed abdominal mixture signal + config dict
Output : (fecg_est, metadata) where
    fecg_est  : np.ndarray, shape (n_samples,)  — estimated fetal waveform
    metadata  : dict containing at minimum the keys defined in OUTPUT_KEYS

Forbidden inputs
----------------
The clean fetal reference (fecg_ref) and clean maternal component (mecg)
MUST NOT be passed to extract() in the normal evaluation path.
If a method uses them for diagnostic purposes, this must be declared by
setting metadata['input_condition'] = 'oracle_assisted', and the result
MUST NOT appear in the main comparison table.

Documentation requirements per method
--------------------------------------
Each concrete class must fill in:
    DESCRIPTION     : one-line description
    INPUT_SIGNALS   : what signals the method expects
    REFERENCE_NEEDED: whether a real thoracic reference is required
    IS_CAUSAL       : whether the method can run causally/streaming
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
# Required metadata keys every method must return
# ──────────────────────────────────────────────────────────────────────────────

OUTPUT_KEYS = [
    "method_name",        # str: method identifier
    "variant",            # str: variant label (e.g. 'variant_1', 'default')
    "input_condition",    # str: 'single_channel' | 'multichannel' | 'oracle_assisted'
    "runtime_s",          # float: wall-clock seconds for extract() call
    "parameter_notes",    # str: description of key parameters used
    "is_causal",          # bool: True if method supports causal/streaming operation
]


# ──────────────────────────────────────────────────────────────────────────────
# Base class
# ──────────────────────────────────────────────────────────────────────────────

class BaseExtractor(ABC):
    """
    Abstract base class for all FECG extraction methods.

    Subclasses must implement extract() and fill in the class-level
    documentation attributes.
    """

    # ── Class-level documentation (fill in each subclass) ────────────────────
    DESCRIPTION: str = "Undescribed method"
    INPUT_SIGNALS: str = "Single-channel abdominal mixture"
    REFERENCE_NEEDED: bool = False   # True if real thoracic reference required
    IS_CAUSAL: bool = False          # True if method is streaming-compatible

    def __init__(self, fs: int = 250, config: dict | None = None):
        """
        Parameters
        ----------
        fs : int
            Sampling frequency in Hz.
        config : dict, optional
            Method-specific parameters.  Must be documented in DESCRIPTION.
        """
        self.fs = fs
        self.config = config or {}

    @abstractmethod
    def extract(
        self,
        mixture: np.ndarray,
        **kwargs: Any,
    ) -> tuple[np.ndarray, dict]:
        """
        Run fetal ECG extraction.

        Parameters
        ----------
        mixture : np.ndarray, shape (n_samples,)
            Preprocessed single-channel abdominal mixture signal.
            Units: physical (same as loaded from .dat/.hea files).
        **kwargs
            Optional additional inputs that must be explicitly declared.
            Example: reference_channel=... for methods needing thoracic ECG.
            If any kwarg makes the result oracle-assisted, the method MUST
            set metadata['input_condition'] = 'oracle_assisted'.

        Returns
        -------
        fecg_est : np.ndarray, shape (n_samples,)
            Estimated fetal ECG waveform.  Must have the same length as mixture.
        metadata : dict
            Must contain all keys listed in OUTPUT_KEYS.
        """
        ...

    def validate_output(
        self,
        fecg_est: np.ndarray,
        mixture: np.ndarray,
        metadata: dict,
    ) -> None:
        """
        Validate that the output conforms to the interface contract.
        Raises ValueError if any requirement is violated.
        """
        if len(fecg_est) != len(mixture):
            raise ValueError(
                f"{self.__class__.__name__}.extract() returned fecg_est with "
                f"length {len(fecg_est)}, expected {len(mixture)} (same as mixture)."
            )

        missing = [k for k in OUTPUT_KEYS if k not in metadata]
        if missing:
            raise ValueError(
                f"{self.__class__.__name__}.extract() metadata is missing required "
                f"keys: {missing}"
            )

        if not np.isfinite(fecg_est).all():
            n_bad = int(np.sum(~np.isfinite(fecg_est)))
            raise ValueError(
                f"{self.__class__.__name__}.extract() produced {n_bad} non-finite "
                "values in fecg_est. Check for divide-by-zero or NaN propagation."
            )

    def run(
        self,
        mixture: np.ndarray,
        **kwargs: Any,
    ) -> tuple[np.ndarray, dict]:
        """
        Validated wrapper around extract().
        Prefer calling run() from the benchmark runner so validation always fires.
        """
        import time
        t0 = time.perf_counter()
        fecg_est, metadata = self.extract(mixture, **kwargs)
        elapsed = time.perf_counter() - t0

        # Inject runtime if method did not set it
        if "runtime_s" not in metadata or metadata["runtime_s"] is None:
            metadata["runtime_s"] = elapsed

        self.validate_output(fecg_est, mixture, metadata)
        return fecg_est, metadata

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"fs={self.fs}, "
            f"causal={self.IS_CAUSAL}, "
            f"reference_needed={self.REFERENCE_NEEDED})"
        )
