# WS2 notes: literature survey rewrite (Sec. 12)

## Done
- New section file `report/final_report/sections/ws2_literature.tex` ("Literature Survey and Positioning of the Final Design", label kept `sec:literature_survey`), blue finalpart. Organised by final-design blocks: template subtraction (used), periodic component analysis / GEVD (used), ICA (compared, not used), CinC 2013 methods (compared), beat tracking and track selection (ours), adaptive filtering with a maternal reference (rejected), embedded/FPGA fetal ECG (compared), mid-term paradigms (superseded). Each item points to a section.
- Removed: "delivering deterministic single-DSP edge execution" (final design uses 43 DSP); "iterative ICA algorithms exhibit convergence latency incompatible with real-time FPGA execution" (unsupported; ICA methods top Tab. v7_literature and JADE has run in real time on a DSP); "1D U-Net ... exceeds on-chip BRAM capacity" and "Hankel SVD requires high DSP overhead" (unsourced, mid-term).
- `apply.py` (run from anywhere: `venv/Scripts/python.exe report/final_report/fixes/WS2/apply.py`): replaces the old Sec. 12 by `\input{sections/ws2_literature}`, corrects bibitems edwin2022 and delathauwer2000 (DOI), replaces bibitem pani2016 by muceli2007 (renames the one remaining citation, in the Introduction research-gap sentence that WS1 rewrites) and adds vasudeva2020. Dry run on a copy: OK.

## Register rows to add (Table 23)
- C: Sec. 12 / bibliography: edwin2022 title and DOI. Old: "Hardware-efficient neural-coprocessor-based adaptive filtering for real-time fetal ECG extraction on FPGA", 10.1109/TBCAS.2022.3204439. New: "Extraction of fetal ECG from abdominal and thorax ECG using a non-causal adaptive filter architecture", 10.1109/TBCAS.2022.3204993. Reason: the old title/DOI do not exist (Crossref).
- C: bibliography: pani2016 "Real-time embedded JADE ..." BSPC 2016 -> muceli2007 (Electronics Letters 2007). Reason: paper not found; DOI resolved to an unrelated article.
- C: bibliography: delathauwer2000 DOI 10.1109/10.841333 -> 10.1109/10.841326. Reason: old DOI resolves to an unrelated paper.
- C: Sec. 12: "single-DSP edge execution" -> removed. Reason: final design uses 43 DSP slices.
- C: Sec. 12: "ICA ... incompatible with real-time FPGA execution" -> removed. Reason: unsupported; ICA methods top Tab. v7_literature.
- F: Sec. 12: survey reorganised around the final design (uses / rejects / compares).

## Not done / open
- No full texts read; depth is Crossref metadata, plus abstracts for vasudeva2020. silva2013 has no DOI and was not re-checked.
- The Introduction sentence "embedded and FPGA implementations ... frequently depend on multi-DSP architectures or require dedicated maternal thoracic reference leads" (WS1's scope) cites edwin2022 and muceli2007 after apply.py; WS1 should make sure it matches the corrected references.
- No verified published reference for beat-tracking/track-selection schemes in fetal ECG was added (none verified in the time available); the text says so.
