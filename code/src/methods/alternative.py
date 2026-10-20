"""
src/methods/alternative.py
──────────────────────────────────────────────────────────────────────────────
Alternative extraction method — SCAFFOLD for Vivek.

Owner    : Vivek
Primary references : 43407.pdf (Sameni ECG modeling),
                     s11042-022-13391-0.pdf (comprehensive survey)
Supporting refs    : A_Review paper, Digital Filters paper

Tasks for Vivek (from work plan Section 4 & 11)
-----------------------------------------------
1. Inspect .hea files to confirm actual channel count, sample rates, gains.
2. Select one additional extraction method compatible with confirmed inputs.
   - If only one abdominal mixture is available → single-channel method.
   - If genuine multi-channel abdominal observations exist → ICA may be used;
     document component count, selection rule, identification method.
3. Treat the Sameni paper as background for mixture/evaluation, not as an ICA
   extraction algorithm to copy.
4. Run TC1–TC5 using shared mixture builder.
5. Provide FPGA feasibility note.

Fallback: if ICA is not supported by channel metadata, select a single-channel
method from the review and document the choice before implementation.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.methods.base import BaseExtractor


class AlternativeExtractor(BaseExtractor):
    """Alternative extraction method (Vivek's method)."""

    DESCRIPTION = "Alternative extraction — method TBD by Vivek pending channel audit"
    INPUT_SIGNALS = "TBD — depends on channel audit result"
    REFERENCE_NEEDED = False   # update after audit
    IS_CAUSAL = False

    def extract(
        self,
        mixture: np.ndarray,
        **kwargs: Any,
    ) -> tuple[np.ndarray, dict]:
        raise NotImplementedError(
            "AlternativeExtractor.extract() not yet implemented. "
            "Owner: Vivek.  Confirm channel availability first (M1 milestone)."
        )
