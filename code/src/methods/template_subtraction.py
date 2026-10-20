"""
src/methods/template_subtraction.py
──────────────────────────────────────────────────────────────────────────────
Maternal template subtraction — SCAFFOLD for Anshu.

Owner    : Anshu
Primary reference : A_Review_of_Signal_Processing_Techniques_for_Non-Invasive_
                    Fetal_Electrocardiography.pdf  (taxonomy, Section on
                    template subtraction approaches)
Supporting ref    : libroWiley.pdf, s12575-009-9006-z.pdf

Tasks for Anshu (from work plan Section 4 & 11)
----------------------------------------------
1. Select and document one implementable template-subtraction approach from
   the review.
2. Detect maternal R-peaks from the permitted mixture input.
3. Align maternal beats, estimate a template, subtract it.
4. Optionally compare fixed template vs. adaptive/updateable template.
5. Run on TC1–TC5.

IMPORTANT: Do NOT use the clean mecg component to build the normal template.
If done for diagnostic purposes, label the run oracle_assisted.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.methods.base import BaseExtractor


class TemplatSubtractionExtractor(BaseExtractor):
    """Maternal template subtraction (Anshu's method)."""

    DESCRIPTION = "Maternal template subtraction — to be implemented by Anshu"
    INPUT_SIGNALS = "Single-channel abdominal mixture (preprocessed)"
    REFERENCE_NEEDED = False
    IS_CAUSAL = False

    def extract(
        self,
        mixture: np.ndarray,
        **kwargs: Any,
    ) -> tuple[np.ndarray, dict]:
        raise NotImplementedError(
            "TemplatSubtractionExtractor.extract() not yet implemented. "
            "Owner: Anshu.  See method docstring for tasks."
        )
