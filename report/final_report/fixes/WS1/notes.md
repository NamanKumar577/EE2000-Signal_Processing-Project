# WS1 notes

Done: everything in the WS1 brief. Tested by running apply.py on a scratch copy of report/final_report and compiling 3x: 46 pages, no LaTeX errors, no undefined/multiply-defined references, figures and tables in page order. fpr-8.tex itself was not touched.

Order: run apply.py FIRST (before WS2..WS5); it matches exact strings of the current fpr-8.tex (commit 7256a63).

Label changes: sec:problem_statement and sec:dataset now belong to the NEW Secs. 3 and 4; the moved mid-term sections are sec:midterm_problem (A.1) and sec:midterm_dataset (A.2). Only reference elsewhere: sections/threats.tex cites sec:dataset for the anatomical 4-lead choice; that discussion is now in App. A.2 / Fig. fmr_topography, so WS6 may want to change that \ref to sec:midterm_dataset.

Front end verified against the C model: tools/report_stats/front_end_check.py (new) -> tools/report_stats/out/front_end.csv. The comment in tools/accuracy/fe3.py ("HP1 (0.62 Hz) + LP40") is stale: the Q28 coefficients give a 60 Hz low-pass, as the report says.

Not done / caveats:
- The moved App. A.2 still contains the mid-term dipole equation and FECGSYNDB paragraph (kept verbatim as the mid-term record; the new Sec. 4 restates them).
- The board 7-segment output of the final FHR is described as what the RTL drives (v7_disp.v); it has not been confirmed by looking at the board (open check from earlier).
- Word count effect: roughly neutral (text moved, two short sections added).

Register rows (for tab:register):
| Item | Old | New | Section | Reason |
|---|---|---|---|---|
| C | Sec. 2: "Boolean Board total power is estimated analytically" | Vivado estimate 0.445 W; board not measured | Sec. 2 | power is now a Vivado estimate (Tab. hw_summary) |
| C | Sec. 2: latency "must remain below 100 ms" | original target; re-baselined in Tab. o3o4 | Sec. 2 | final design reports beats after 1.5-2 s / 13.5 s |
| C | Intro: FPGA designs "depend on multi-DSP architectures" (implied criticism) | removed; final design uses 43 DSP | Sec. 1 | statement contradicted our own design |
| F | Secs. 3-5 described the mid-term beamformer | moved to App. A.1-A.3; new Secs. 3-4 describe the final design and its front end | Secs. 3-4, App. A | main body describes only the final design |
| F | Preprocessing: 0.5-40 Hz Butterworth + 50/60 Hz notch | one-pole HP 0.63 Hz, 60 Hz LP, 5-25 Hz maternal band, 15-40 Hz track band, no notch | Sec. 4 | final front end from fpga_model.c / coef_q28.h |
