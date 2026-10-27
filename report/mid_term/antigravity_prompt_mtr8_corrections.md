# ANTIGRAVITY TASK — Correct EE2000 Mid-Term Report #0008 (MTR-8)

Project: "Fetal ECG Extraction from Maternal Abdominal ECG and Fetal QRS Detection on FPGA: Mid-Term Project Report" (EE2000 2026, anonymous review copy, Paper ID 0008, 18 pages).

You are editing the report source AND the scripts that generate its numbers, tables and figures. Read this whole file before touching anything. Work in the phases in Section 1.

---

## 0. GROUND RULES (non-negotiable)

1. **Never invent a number, reference, quote, or result.** Every changed number must be recomputed from the project's own logs/CSVs/code (`results/mega_benchmark_results.csv`, the 35-run benchmark output, `src/fixed_point_model.py` golden-vector logs, etc.). If a value cannot be recomputed, do NOT guess: insert a visible `\todo{...}` (or `%% TODO-MTR8:` comment), and list it in `CHANGELOG_MTR8.md` under "UNRESOLVED".
2. **Fix at the source.** Numbers reach the PDF via `tools/make_numbers_tex.py` → generated `.tex` → `report/mid_term/build_full_report.py`. Edit the generator/plotting scripts, then regenerate. Do not hand-patch generated files (they get overwritten).
3. **Do not change the science to improve numbers.** No re-tuning, no changing detector thresholds, window sizes, lead sets, splits or seeds. If a recomputation changes a headline number, report the new number honestly.
4. **Keep validation-level tags honest.** `[L1 Software]`, `[L2 Bit-True]`, `[L3 RTL Simulation]`, `[L4 Target Sized]`, `[L5 Hardware Target]`. Never upgrade a level. Analytical estimates must not use words like "demonstrates", "verified", "achieves" (see S-15).
5. **Preserve anonymity.** No names, usernames, emails, institution names, local paths, git remotes, or PDF metadata that identify the team (see A-01, A-04).
6. **Do not add AI-disclosure claims that are not true.** Section 16 must describe what was actually done (see A-02).
7. **Keep the template/page format.** Do not shrink fonts/margins to fit. Stay within ±1 page of the current 18 pages unless the course flier states a limit (check it; if there is a limit, respect it).
8. **Log everything.** For every item ID below, add a before→after entry to `CHANGELOG_MTR8.md` (file, location, old text/value, new text/value, source of the new value).
9. Item confidence tags:
   - `[ARITH]` = I verified by arithmetic from numbers printed in the report. High confidence it is wrong.
   - `[XREF]` = two places in the report contradict each other. Decide which is right from the logs, then make all places agree.
   - `[CHECK]` = suspicious; verify against logs/code BEFORE changing. If logs confirm the report, leave the number and add an explanation sentence instead.
   - `[WRITE]` = wording/claim/structure change.
   - `[FMT]` = figure/table/layout change.

---

## 1. EXECUTION ORDER

**Phase A – Audit (no edits).** Build `tools/audit_mtr8.py` that recomputes and prints every check listed in Section 7. Run it; save the output as `audit_before.txt`.
**Phase B – Compliance & hard errors:** items A-*, N-*.
**Phase C – Consistency:** items X-*.
**Phase D – Science/claims:** items S-*.
**Phase E – Writing/structure/figures:** items W-*, F-*.
**Phase F – Rebuild & verify:** Section 7 checklist, then produce deliverables in Section 8.

---

## 2. COMPLIANCE ITEMS (do first)

### A-01 [ARITH-visible] Name leak: "Vivek" in figure legends — anonymity violation
- **Where:** legends of Fig. 6 ("Vivek Hybrid Alternative"), Fig. 8 ("Vivek Hybrid (1-Ch)"), Fig. 9 ("Vivek Hybrid (1-Ch)" row), Fig. 12 ("Vivek_Hybrid_Alt"), Fig. 13, Fig. 14, Fig. 15 (legend "Vivek_Hybrid_Alt"), Fig. 19/20 if present.
- **Problem:** The paper is submitted as "Anonymous EE2000 submission"; a person's name appears in figures. Also the same method is called "Wavelet-Threshold Hybrid" in Tables 2, 3, 4, 5, 6.
- **Fix:**
  1. `grep -rniE "vivek" .` across the whole repo (scripts, CSV column names, figure code, LaTeX, notebooks, `results/`, `figures/`). Rename every occurrence to `Wavelet-Threshold Hybrid` (short: `Wavelet-Thr. Hybrid`) in labels, CSV headers (keep a mapping so scripts don't break), and plotting code.
  2. Regenerate all affected figures. Verify with `pdftotext` + `pdfimages`/visual check that no legend still shows the old name.
  3. Also grep for any other personal names, GitHub usernames, local paths like `/home/<name>/`.

### A-02 [WRITE] AI Usage Disclosure (Sec. 16) must be accurate and consistent with the evidence in this report
- **Where:** Section 16, bullet "Human Verification and Independent Validation", and Table 13 row R-15.
- **Problems:**
  1. It claims *"Every numerical value in Tab. 1, 3, 4, 5, 6, 7, 8 was independently recomputed from CSV logs via automated consistency checkers"*, but this review found at least two numbers that do not recompute (N-01, N-02). Either run the checkers and fix, or delete the claim.
  2. It claims *"Every cited literature reference was retrieved, verified, and checked for author names, venue, publication year"*. Several references look unverified (see A-03). Do not keep this sentence unless it is true after A-03.
  3. It lists "Claude 3.5 Sonnet" and "GPT-4o". The tools/versions named must be the ones actually used (check the team's real usage; do not guess). If Antigravity (or any model inside it) is used for this correction pass or for any part of the work, add it to the list.
  4. The disclosed areas ("boilerplate code", "architectural review", "LaTeX formatting") must reflect actual usage. If AI wrote analysis code, benchmark code, text, or figures, say so plainly.
- **Fix:** Rewrite Sec. 16 as: (a) tools & versions actually used; (b) per-activity list of what AI did (code, text, figures, literature search, numeric checks); (c) what humans verified and how (only things actually done — e.g., "numbers regenerated by `tools/make_numbers_tex.py` and compared by `tools/check_consistency.py`, which checks X, Y, Z"); (d) viva-readiness sentence (keep). **Leave a `\todo{team to confirm}` where facts are unknown.**

### A-03 [CHECK] Reference list problems
Do each step; log results in `refs_audit.md`.
1. **Count mismatch:** Table 13 row R-13 says "31 verified literature references"; the bibliography has **29** entries. Replace the number with the real count (ideally auto-generated from the .bib).
2. **Uncited entries:** [13] (Sameni Bayesian filtering), [16] (FECGSYNDB), [18] (NIFEADB) have no back-references in the text. Either cite them where appropriate or delete them (and update the count).
3. **Wrong citation targets in text:**
   - Sec. 4 "PhysioNet FECGSYNDB benchmark … [3, 17]" → the dataset entry is **[16]**; use **[16, 17]** ([3] is the Clifford 2014 review).
   - Sec. 14 limitation 1 "PhysioNet/CinC Challenge 2013 [3]" → should be **[26]** (Silva et al.).
4. **Wrong title:** [24] Constantinides, Cheung, Luk, IEEE TCAD 22(10):1432–1442, 2003 — the title is *"Wordlength optimization for linear digital signal processing"* (not "…for digital signal processing systems"). Fix.
5. **Verify existence (DOI / publisher / Google Scholar / IEEE Xplore / PubMed) of every reference, especially these that the reviewer could not confirm from memory:** [5] Abel, Dhanalakshmi, Kumar 2023 (*Multimedia Tools and Applications* 82:1373–1400); [9] Agostinelli, Morelli, Fioretti, *Physiol. Meas.* 35(8):1577–1590, 2014 (title "adaptive template subtraction method"); [20] Lee, Shin, Park, *IEEE Access* 8:120015–120024, 2020; [21] Zhong, Liao, Guo, *BSPC* 71:103185, 2022. For each: confirm title, authors, venue, volume, pages, year, and that the paper really contains the claim it is cited for. **If a reference cannot be found, delete it and every sentence/Table 10 row that depends on it; do not "fix" it by guessing.** Add DOIs to all entries.
6. Fix inconsistent citation spacing (`[4,5]` vs `[4, 5]`) globally.

### A-04 [FMT] Metadata & anonymity scan
Run `pdfinfo`, `exiftool` on the final PDF; clear Author/Creator fields. Check the LaTeX for `\author`, `\thanks`, `\hypersetup{pdfauthor=...}`. The repository description in Sec. 17 must stay path-only (no URL with a username).

---

## 3. NUMERICAL ERRORS (Phase B)

### N-01 [ARITH] Table 6, Spatial PCA, Train (sub01–07) FHR MAE is wrong
- **Report says:** `92.90% (6.16 bpm)`.
- **Evidence:** Table 7 per-subject PCA MAE for sub01–sub07 = 5.47, 5.07, 5.38, 11.39, 7.73, 4.48, 5.49 → sum 45.01 → mean **6.43 bpm**. Cross-check: All-data mean 6.57 = (7×train + 4.66 + 2×8.00)/10 only if train = 6.43 (with 6.16 the all-data mean would be 6.38).
- **Fix:** Recompute from `results/mega_benchmark_results.csv` (mean over the 175 training records). Expected ≈ **6.43**. Update Table 6, and any text using 6.16. Add an automated check that Table 6 "All" = weighted mean of Train/Val/Test (7:1:2 weights) for **every** method column, F1 and MAE.

### N-02 [ARITH] Deep U-Net (4-Ch) between-subject SD and clustered CI are wrong
- **Report says (Sec. 7, Table 5, abstract-level claims):** s_subj = 10.16% → 90.76% ± 7.27%, CI [83.48, 98.03].
- **Evidence:** Table 7 U-Net F1 per subject: 97.47, 94.13, 92.93, 78.85, 71.95, 90.07, 91.53, 95.69, 97.90, 97.07. Mean = 90.76 ✓. Sample SD (n−1 = 9) = **8.65**, not 10.16. Half-width = 2.262 × 8.65/√10 = **±6.18**, CI ≈ **[84.58, 96.94]**.
- **Fix:** Recompute from the CSV (per-subject means → SD → t-interval). If the CSV agrees with Table 7, replace 10.16 → ~8.65, ±7.27 → ~±6.18, [83.48, 98.03] → ~[84.58, 96.94] in Sec. 7 (Eq. 21 paragraph), Table 5 and anywhere else (`grep -n "10.16\|7.27\|83.48\|98.03"`). If the CSV disagrees with Table 7, then Table 7 is wrong — fix Table 7 and re-verify Tables 5, 6, 8.
- (The PCA numbers were verified: SD 3.28, ±2.35, [90.65, 95.35] ✓ — do not touch them.)

### N-03 [ARITH] Fig. 21: FPGA bar is off by 1000×
- **Report says:** FPGA pipeline "0.096 ms (1.28 µs/sample)" for a 5-minute record.
- **Evidence:** 75,000 samples × 1.28 µs = 96,000 µs = **96 ms** (0.096 **s**).
- **Fix:** Correct the bar and the label to `96 ms`; replot on the log axis. Add a caption sentence: *"FPGA figure is pure compute time for 75,000 samples at the sized 1.28 µs/sample; in real time the record still takes 300 s because samples arrive at 250 Hz."* Remove any language implying a large wall-clock speed-up vs the CPU (CPU Spatial PCA = 190.7 ms, i.e., only ≈2× slower than the sized FPGA compute). The FPGA's benefit is determinism, power and real-time operation, not raw throughput — say that.

### N-04 [XREF] Runtime/speed numbers disagree across Table 3, Table 5 and Fig. 21
- Table 5 "Speed": Hankel-SVD V1 = **75.9 ms**; Template Sub (Adapt.) = **44.7 ms**; PCA = 190.7 ms; U-Net 4-Ch = 98.6 ms.
- Fig. 21 / Sec. 10 text: Hankel SVD = **107.5 s**; Adaptive EMA TS = **245.0 ms**.
- Table 3 "Runtime": PCA **0.003 s**, U-Net 0.082 s, Hankel 0.026 s … (while Table 5 says 190.7 ms for the same PCA, a 60× difference = 5-min vs 5-s window?).
- **Fix:** Define one metric: *wall-clock seconds per 5-minute record (75,000 samples), single CPU thread, excluding disk I/O; GPU time for U-Net on RTX 4060 stated separately; report CPU model.* Re-measure with one script, write to one CSV, and regenerate Table 3 "Runtime" column, Table 5 "Speed" column and Fig. 21 from that CSV. State in each caption what the number is (per 5-min record vs per 5-s window). Delete the unsupported "107.5 s" unless the new measurement reproduces it.

### N-05 [ARITH/XREF] Cycle budget: 2 SOS vs 4 SOS; "exactly 128" is not derived
- **Where:** Abstract, Sec. 1 contribution 6, Table 1 row "Per-Sample Compute Time", Sec. 9.2 + Fig. 17, Sec. 10, Table 9 row 1, Table 12, Table 13 (R-08), Fig. 21 label, Sec. 13.
- **Problem 1:** Sec. 4 and Fig. 2/4 say the Butterworth bandpass is **4 cascaded SOS biquads** (8th-order). Sec. 9.2 counts "4 channels × **2** SOS × 5 MACs = 40 cycles". With 4 SOS it is 4 × 4 × 5 = **80** cycles.
- **Problem 2:** The remaining 59 cycles are labelled "pipeline staging/overhead" — a plug number that makes the total exactly 128 (a convenient power of two). Also not counted: squaring, 15-sample moving integration, threshold update/compare, refractory logic, FHR = 15000/interval division, 5-beat median, UART TX, 7-segment drive.
- **Fix (do in this order):**
  1. Determine from the actual RTL/schedule (or write the schedule down explicitly): number of SOS sections, MACs per biquad, DSP48E1 pipeline latency (use UG479 for the real number of pipeline stages), per-stage cycle counts.
  2. Rebuild Sec. 9.2 as a table: Stage | Operations | Cycles | How derived. Minimum rows: bandpass SOS (4 ch × N_sos × 5), notch SOS (4 × 1 × 5 = 20), beamformer (4), derivative (5), squaring (1), moving-integration (add/subtract), threshold/compare, FHR divide (state whether a divider IP or reciprocal LUT is used, and its latency, or state that it runs outside the per-sample budget), median-of-5, pipeline latency, control. Mark which stages use the DSP48E1 and which use LUT logic only.
  3. Illustrative arithmetic (use only if the real schedule confirms): 80 + 20 + 4 + 5 = 109 cycles of MAC work; if the 59-cycle overhead stays, total = 168 cycles → 1.68 µs at 100 MHz → margin 400,000/168 ≈ 2,381×. If the design is instead *budgeted* to ≤128 cycles, say "budgeted ≤128 cycles (including a X-cycle reserve)" — do NOT say "exactly 128".
  4. Propagate the final cycle count, µs, % of budget (=cycles/400,000) and margin (=400,000/cycles) to **every** location above. Verified-correct formulas: 1 cycle = 10 ns at 100 MHz; budget = 4,000 µs = 400,000 cycles.
  5. Fig. 17: see F-05.

### N-06 [ARITH] "< 3% LUTs" contradicts 3.0% / 3.04%
- Sec. 1 contribution 6 says "< 3% LUTs"; Table 4 says "(<3% LUT, 1 DSP)"; Table 9 and Sec. 10 say 990 LUTs = 3.0% (990/32,600 = 3.04%).
- **Fix:** write "≈3.0% LUTs (990 of 32,600)" everywhere. Keep the O4 objective (<5%) as is.

### N-07 [ARITH] Amplitude-disparity statements are internally inconsistent
- Text: maternal **1–5 mV** vs fetal **20–100 µV** ⇒ ratio spans 1 mV/100 µV = 10× up to 5 mV/20 µV = **250×** (20–48 dB), but the report says "**10–50×**, 20–34 dB" (Abstract, Fig. 1 caption, Sec. 1).
- Fig. 1 callouts: maternal 2.50 mV vs fetal 0.04 mV = **62.5×** (≈35.9 dB), but the figure says "(20–50× weaker)".
- Fig. 1 y-axis says "peak-to-peak" while the text says "peak".
- **Fix:** Recompute from **training subjects only (sub01–sub07)**: per lead and per record, maternal peak (|max|) and fetal peak from the ground-truth component files; report median and 5–95% range of the ratio (×, dB). Then rewrite consistently in the Abstract, Fig. 1 (labels, callouts, axis wording), Fig. 1 caption, Sec. 1 and Table 1. If you keep "1–5 mV vs 20–100 µV" as literature ranges, say "10–250×"; if you keep "10–50×" it must be labelled "measured on FECGSYNDB training leads". Use either peak or peak-to-peak consistently. Keep the verified RMS values: FMR 0.20–0.54 ⇔ −14.0 to −5.4 dB.

### N-08 [ARITH] Figure captions that contradict their own tables
- Fig. 13 caption: "Spatial PCA and **4-Ch U-Net maintain > 91%** across all noise tiers". Table 8 U-Net SNR tiers: 91.06, **90.35**, 91.14, **90.18**, 91.05 ⇒ two tiers < 91. Fix to "> 90%" (PCA's minimum, 91.40%, stays "> 91%"). State them separately.
- Fig. 8 caption: "single-channel baselines degrade to **< 24%**". Table 3 TC3: Wavelet-Threshold 24.64%, Template Sub 23.88%, Hankel 23.72%. Fix to "< 25%".
- Sec. 8.3 / Fig. 13: also "single-channel baselines drop to 35–46%" — verify against Table 5 per-SNR values (regenerate from CSV).

### N-09 [XREF] Fig. 18 title says "50 MHz clock"; everything else is 100 MHz
- **Fix:** regenerate Fig. 18 at 100 MHz (or, if the board clock/derived clock really is 50 MHz somewhere, state that explicitly and make all latency numbers consistent). Re-check the UART-bandwidth curve (86.8 µs per 8-byte frame at 921,600 baud with 10 bits/byte = verified correct; 2.17% of 4,000 µs verified).

### N-10 [WRITE/XREF] Table 1 "Max Clock Frequency Supported by Spartan-7 Speed Grade −1: 100 MHz"
- 100 MHz is the **Boolean Board's on-board clock**/our target, not the device's maximum (DSP48E1 and fabric limits in a −1 device are much higher; see Xilinx DS189 — look up and cite the actual numbers; do not guess).
- **Fix:** rename the row "Target clock frequency", value "100 MHz (board oscillator); timing closure at 100 MHz to be shown at L4", and cite DS189 for the device limits only if you have read the number.

### N-11 [XREF] Fig. 19 mixes metrics and places the U-Net inconsistently
- Fig. 19 y-axis uses **92.15%** (Subject-1 stress average) for PCA, while the headline population F1 is **93.00%**. U-Net is plotted at ≈98.6% (in-sample 1-Ch) — different configuration/population again.
- U-Net x-position appears beyond the XC7S50 capacity line although Table 9 says 28,400 LUTs (87.1%) fits.
- **Fix:** plot population mean F1 (Table 5) for every method with Table 9 LUT counts (log axis), draw the XC7S50 limit at 32,600 LUTs, update the caption ("93.00% F1" not "92.15%"), and see S-07 on whether the U-Net point should exist at all.

### N-12 [WRITE] "3.29 bpm under normal rhythm" is c0 only
- 3.29 is the **c0 (baseline normal)** MAE. The mean over normal-rhythm conditions c0, c2, c3 is (3.29+2.99+3.27)/3 = **3.18 bpm**. Abstract/Table 1 label 3.29 as "normal rhythm"/"pop".
- **Fix:** say "3.29 bpm on c0 (baseline); 2.99–3.29 bpm on c0/c2/c3" or use 3.18 and define it. Keep Sub-1 numbers as "0.32–0.48 bpm (sub01, TC1–TC3)" and state which range (not "0.48 bpm on Subject 1 baseline" alone).

### N-13 [ARITH] Group delay samples vs ms
- Text: "τg ≈ 11.4–15.4 ms (2.9–3.9 samples at 250 Hz)". 2.9 samples = 11.6 ms; 3.9 = 15.6 ms (1 sample = 4 ms).
- **Fix:** recompute from the actual SOS coefficients (`scipy.signal.sosfreqz` → group delay over 10–30 Hz) and print consistent samples and ms (e.g., "2.85–3.85 samples = 11.4–15.4 ms" if that is what the filter gives). Maximum 24 samples = 96 ms ✓.

### N-14 [XREF] Fig. 17 axis label "408k"
- The x-axis end label looks like "408k (4 ms)" while the budget is 400,000 cycles = 4 ms. Check and fix the label (see F-05).

### N-15 [CHECK] Suspicious duplicate values in Table 3 (looks like copy-paste)
- TC1: Template Subtraction (Fixed) and Hankel-SVD V1 have **identical** TP/FP/FN (546/168/170) and identical Correlation 0.270 to the Wavelet-Threshold row (0.270). TC2: Wavelet and Hankel both corr 0.109, Template 0.106. TC3: Wavelet, Template, Hankel all corr 0.017. TC4: Wavelet & Hankel corr 0.199. TC5: Wavelet & Template corr 0.113.
- **Task:** open the raw 35-run benchmark output; confirm each row independently. If genuinely identical (different algorithms producing identical beat lists is plausible only if all three reduce to the same maternal-template subtraction) then add one explanatory sentence under Table 3; otherwise fix the rows. Also re-derive every PPV/Se/F1 from TP/FP/FN with a script (I verified all printed counts satisfy Det = TP+FP and FN = Ref−TP, and Table 4 averages match Table 3 — keep those).

### N-16 [CHECK] PCA correlation 0.998 (Table 3) vs |ρ| = 0.513 (Table 5) vs "signed mean −0.135"
- Table 3 reports PCA correlation 0.998/0.997/0.994 on TC1–TC3 (including **0 dB** SNR), which is not credible for a 4-lead linear projection of a noisy mixture against the clean fetal reference unless correlation is computed on something other than the extracted waveform (e.g., the integrated energy envelope or the detected-beat impulse train).
- **Task:** state precisely in the text how "Corr." is computed (what signal, what reference, filtered or not, after polarity alignment or not). Recompute it for all methods the same way. If Table 3's PCA value is computed after skewness alignment but Table 5/Sec. 5.1 on raw signs, report both (raw signed, aligned signed, |ρ|) in Table 5. Resolve the gap between 0.998 and 0.513 with one explanatory sentence backed by numbers (e.g., Subject 1 vs population).

### N-17 [WRITE] Define "2,250 runs"
- "250 records" and "2,250 runs" are never reconciled. 250 records × 9 methods = 2,250 (this fits only if SWT-LMS is **not** in the mega-benchmark; see X-01). Add one sentence: "run = one method on one record (250 records × 9 methods)".

---

## 4. CROSS-REFERENCE / CONSISTENCY ITEMS (Phase C)

### X-01 [XREF] Method inventory: "nine methods" vs the methods actually shown
- Table 2 lists M1–M9 (PCA, U-Net 4-Ch, U-Net 1-Ch, MC Template Fusion, Wavelet-Threshold Hybrid, Fixed TS, Adaptive TS, Hankel V1, Hankel V3).
- Table 3/4, Figs. 6, 8, 9 also include **"SWT-LMS Wavelet Filter"** (a tenth method, absent from Tables 2, 5, 6, 7) and omit M7, M9, and U-Net 4-Ch.
- M5 "Wavelet-Threshold Hybrid" is *already* described as SWT + adaptive subband LMS + thresholding (Sec. 5.4), so "SWT-LMS" looks like a duplicate/variant.
- **Fix:** decide (from the code in `src/methods/`) whether SWT-LMS is a distinct implementation. If yes: add it to Table 2 as M10, include it in the mega-benchmark (then runs = 250 × 10 = 2,500, update everywhere) or explicitly state it was run only on Subject 1. If no: delete the SWT-LMS rows/legend entries or relabel them as the same method. In Table 3's caption replace "7 classical methods × 5 test cases" with "7 methods (2 non-classical: Spatial PCA, U-Net) × 5 test cases".

### X-02 [XREF] U-Net configuration changes between tables
- Table 3/4 and Sec. 8.1(1) use **U-Net 1-Ch** (98.59%, "in-sample on sub01") while the abstract/contributions/Table 1/Table 6/7 headline numbers use **U-Net 4-Ch** (97.48% test, 90.76% population, 3.57 bpm).
- **Fix:** label the configuration (1-Ch/4-Ch) every time a U-Net number appears. In Table 3 add the 4-Ch U-Net row (or state why only 1-Ch is shown). In Sec. 8.1(1) make clear which U-Net 98.59% refers to. Table 1 FHR-MAE row currently mixes PCA (6.57) with U-Net 4-Ch (3.57): label them.

### X-03 [XREF] Table 4 "FPGA Viability" vs Table 9
- Table 4 gives resources for "Template Sub. (Fixed): 3% LUT, 2 DSPs" which does not exist in Table 9. Add that row to Table 9 (with its estimation method) or remove the numbers from Table 4.
- Table 4 "(<3% LUT)" → see N-06.

### X-04 [XREF] L3 status vs roadmap
- Table 12 says L3 is "In Progress: preprocessing SOS and 4-MAC beamformer RTL simulated; top-level integration under test", yet the roadmap says "26–31 Oct: Synthesizable Verilog coding for Butterworth SOS, 4-MAC Spatial Beamformer, and Peak-Energy QRS detector; testbench simulation".
- **Fix:** make the two statements consistent (state exactly which modules have passing testbenches today and vs which golden vectors; schedule only what remains). Do NOT claim L3 for anything without a passing simulation log in the repo.

### X-05 [XREF] Sec. 11 says U-Net "necessitates host GPU co-processing" but Table 9 shows it fitting the XC7S50
- Reconcile together with S-07 (the U-Net row is not credible).

### X-06 [WRITE] Orphan/unclear labels "PPR" and "PPR-8"
- Fig. 2 block "Fetal QRS Detector (PPR-8)" and Fig. 17 block "PPR & Energy & Det." use a leftover token (PPR-8 is the *Preliminary Project Report* ID in Table 13). The detector is the **Peak-Energy (PE) detector** (Sec. 5.2).
- **Fix:** relabel as "Peak-Energy QRS Detector" in both figures; keep "PPR-8" only in Table 13's header if wanted.

### X-07 [XREF] Fig. 2 vs text
- Fig. 2 shows a "Maternal Detection" block and a parallel "Template Sub. / SVD / U-Net" branch, but the dual 50/60 Hz notch (listed in the caption and Sec. 4) is not shown, and "Maternal Detection" is never described in the text.
- **Fix:** redraw: Input → BPF → Notch → {Spatial PCA beamformer (primary) | baseline methods (need maternal QRS detector)} → PE detector → median FHR → 7-seg/UART. Add one sentence describing the maternal QRS detector used by baselines.

### X-08 [XREF] Objectives (O1–O5) vs results
- O1 requires FHR MAE < 1.0 bpm under normal rhythms and F1 ≥ 90% at 0 dB; population results are 3.29 bpm (c0) and 93.68% (0 dB).
- Table 1 marks these rows "Verified" in the validation column even though the target is not met on the population. See S-10 for the required status column.

### X-09 [WRITE] Section/table numbering and orphan references
- "15. Register of Changes to the Preliminary Report" heading appears with no body on its page; Table 13 appears later after Table 12. Move Table 13 directly under heading 15 (or merge headings).
- Add in-text references for Table 11 (in Sec. 13), Table 12 (in Sec. 14), Table 13 (in Sec. 15), Fig. 20 and Fig. 21 (in Sec. 10/11). Every table/figure must be cited at least once.

---

## 5. SCIENTIFIC / CLAIM ITEMS (Phase D)

### S-01 [WRITE] The "rank-3 maternal subspace" theory contradicts using v2 (Sec. 3, 5.1, 9.1)
- Sec. 9.1 argues the maternal source spans a **3-D** subspace (Eq. 22), so with C = 4 channels there is a **1-D orthogonal complement** where the fetal signal should live — that would be the **smallest** eigenvector (v4) under ideal conditions, not v2. The method uses w = v2, and Sec. 9.1 itself assigns λ3 = 2.6%, λ4 = 1.2% to "residual EMG and sensor noise".
- Also Sec. 3 says w "projects into the orthogonal null space of the dominant maternal interference" (a null space of what? PCA's v2 only removes the v1 direction, not the 3-D maternal subspace; "wᵀA_m = 0" is not achieved).
- **Fix:**
  1. Reword Sec. 3 and 9.1: the beamformer is a **heuristic second-principal-component** projection that suppresses the dominant maternal direction v1; it does *not* null the full 3-D maternal subspace. Remove "null space" phrasing, or restrict it to "v1".
  2. Add **empirical evidence** that v2 carries fetal energy: for each training record compute, for k = 1..4, corr(v_kᵀx, ground-truth fetal ECG) and the fraction of fetal-component energy in each v_k. Report as a new panel in Fig. 16 or a small table. If v2 does not dominate in some subjects (e.g., sub04, sub05, sub10 where F1 is lower), say so — it explains the failures.
  3. Explain why the rank-3 theory predicts F1 improvements from C = 2 → 4 and how that is compatible with using v2 (e.g., maternal energy is strongly concentrated in v1 for this lead set; residual maternal components in v2/v3 explain the drop in c1/c4 where the dipole axes rotate). State the limitation.
  4. Qualify "2 leads cancel the planar projection (95.3%)" — Eq. 22 says C ≤ 3 has no non-trivial null solution; the 2-lead result is a planar approximation.

### S-02 [CHECK] Lead selection vs Fig. 3
- Fig. 3 (training FMR topography) appears to show bars at roughly channel ~19–20 that are as high as or higher than Lead 27 (0.46), yet the text says Leads 25–28 "peak" and are "optimal".
- **Task:** read the per-lead training FMR values from the CSV. If other leads have higher FMR, rewrite the selection claim: say what *actually* selected [27, 26, 28, 25] (e.g., best contiguous 4-lead subset by a stated criterion, or best F1 on the training/validation partition, or spatial diversity/conditioning) and show that criterion. Provide the training-only top-10 leads table. Do not use test subjects for any of this.

### S-03 [WRITE/CHECK] Fixed-point model: filter-coefficient and state formats are unspecified, and Q1.15 cannot hold biquad a1/a2
- Sec. 6 defines Q1.15 only for samples and beamformer weights (|w|₂ ≤ 1). A 0.5 Hz high-pass section at 250 Hz has poles at radius ≈ 0.987 and a1 ≈ −1.97; the allowed range of Q1.15 is [−1, 1). Also Direct Form II with such poles is highly sensitive to coefficient and state quantization.
- **Task:** read `src/fixed_point_model.py`. State in a new table (Table 1b in Sec. 6): coefficient format for b/a (e.g., Q2.14 or scaled by 0.5), state-variable (w[n]) width, guard bits, product/accumulator formats, rounding (round-to-nearest-even) and saturation per stage. If the model currently *does not* quantize the SOS filters, either add it and re-run the 5,000-vector SQNR test (report the new number honestly) or state explicitly that the SQNR figures cover only the beamformer (+detector if included).

### S-04 [WRITE] SQNR claims need a precise definition
- Eq. 14 uses f_float as the signal. Which signal is f? (SOS output, beamformer output, detector output?) A fetal peak of 131 LSBs against ±0.29 LSB rounding noise gives an SQNR ≈ 50 dB for a fetal-only waveform, so 74.52 dB is plausible only if the measured signal is dominated by the maternal component or is measured at a different node.
- "+85.04 dB for **Hankel SVD**": Hankel SVD is not the FPGA architecture (Table 9 gives 48 DSPs), so explain why it is in the bit-true test or drop it from the abstract (keep it in the body as a secondary model).
- **Fix:** define the node, the signal, the window, and report SQNR at (i) beamformer output, (ii) detector input, plus beat-level concordance. Update the abstract so it states only the PCA/beamformer-chain number unless the others are defined.

### S-05 [WRITE] "55 dB required" is unjustified
- Sec. 6 says 55 dB null depth is required "to suppress 20–34 dB maternal excess with > 20 dB margin below the noise floor". 20–34 dB of excess does not imply 55 dB; and "margin below the noise floor" is unclear.
- **Fix:** derive the requirement (e.g., maternal residual must be below the fetal level by X dB ⇒ required rejection = disparity + X) or remove the 55 dB figure. Note Eq. 13 only bounds *weight quantization*; ADC/data quantization and noise limit the practical null (say so). Verified: Eq. 13 gives 95.1 dB (B=16), 71.0 dB (B=12), 59.0 dB (B=10).

### S-06 [WRITE] The "real-time" claim depends on the host: be explicit
- Weights come from a 3.0 s calibration done on the **host PC** and then stay fixed; data is **streamed over UART from the PC**; there is no analog front end in the demo. Sec. 6 describes G = 200, ±5 mV AFE scaling as if hardware exists.
- **Fix:** add a "Scope of the hardware demo" paragraph (Sec. 6.1 or 13): what runs on FPGA vs host; that AFE/ADC are modeled, not built; that 16-bit sample resolution is an assumption (if a real ADC were used, note that the Boolean Board's on-board XADC is 12-bit — check the board manual [27] and say so; 12-bit would give ≈2.44 µV/LSB, i.e., a 20 µV fetal peak ≈ 8 LSB — add a sentence or a short quantization study at 12 bits). Add: static weights ⇒ no tracking of fetal/maternal movement; periodic recalibration is a limitation.

### S-07 [WRITE] Table 9 is analytical; two rows are not credible as written
- Add a "How estimated" paragraph: which formulas/IP (UG479), what per-method schedule, what was *not* counted. Label every row "estimate".
- **Hankel SVD V1: 48 DSP, 4,200 LUT, 1,840 cycles (18.4 µs):** an SVD of a 174-row Hankel matrix in 1,840 cycles is implausible; the CPU needs 75.9 ms per record in Table 5 (or 107.5 s in Fig. 21 — see N-04). Either justify the architecture (algorithm, matrix sizes, iterations) or mark the row "not sized; not directly comparable".
- **Deep 1D U-Net (Edge FPGA): 28,400 LUT / 112 DSP / 65 BRAM / 45,000 cycles:** the network has **1.42 M parameters**; at 16 bits that is ≈2.84 MB, but the XC7S50 has only ≈2.7 Mb (75 × 36 kb ≈ 0.34 MB) of block RAM. It cannot be held on chip; MAC count per window also does not fit 112 DSPs × 45,000 cycles. Fix by: (a) computing parameters, MACs/window, memory footprint; (b) either removing the row, or marking it "infeasible without external memory/quantization; shown for comparison", with the numbers that show why.
- Update Sec. 11 item 4, Sec. 10 and Fig. 19 accordingly (X-05, N-11).

### S-08 [WRITE] U-Net generalization claims are overstated
- Table 6: U-Net 4-Ch F1 is **88.13% on its own training subjects** but **97.48% on held-out** — with sub04 = 78.85% and sub05 = 71.95% (both training subjects). That indicates **under-fitting on some anatomies** (or an evaluation issue), not "favorable anatomical coupling" of sub09–sub10, which is asserted without evidence. The 10-subject "population mean 90.76%" **includes the training subjects**, so it is not a generalization estimate, and calling it "the definitive indicator of model capability" (Sec. 8.3) is statistically wrong. Test set n = 2 subjects.
- **Fix:**
  1. Replace the "favorable electrode coupling" sentence with a testable statement: compute per-subject FMR for all 10 subjects (FMR is a dataset property, not training) and report whether sub09/sub10 really have higher FMR. If not, remove the explanation.
  2. Rewrite the Sec. 8.3 closing paragraph: held-out estimates (97.90 and 97.07 per subject) have n = 2 and wide uncertainty; the 10-subject mean mixes train/val/test for the U-Net; therefore U-Net vs PCA ranking depends on the slice (PCA 93.06 vs U-Net 97.48 on test; PCA 93.00 vs U-Net 90.76 overall). State this plainly.
  3. Discuss the training-subject shortfall (sub04, sub05) and state that training used 50 epochs (see S-16). Remove "verified generalization on held-out test subjects" from Table 10 R6; use "evaluated on 2 held-out subjects".
  4. (Optional, if time) leave-one-subject-out evaluation for PCA hyperparameters; do not start new training runs without a log.

### S-09 [WRITE] F1 is non-monotonic in SNR; explain it
- PCA F1: 0 dB 93.68%, 3 dB 91.95%, 6 dB 92.73%, 9 dB 91.40%, 12 dB 95.22%. U-Net is nearly flat (90.2–91.1%). A reader will ask why 0 dB beats 3/6/9 dB.
- **Fix:** from the CSV compute the per-tier standard error and 95% CI (n = 50 records/tier, but clustered by 10 subjects); state that differences between tiers are within noise if so; note that FECGSYNDB's SNR definition and added noise types determine this; mention that condition (c4 etc.) and subject dominate the variance. Add 2 sentences to Sec. 8.3. Do not change any number.

### S-10 [WRITE] Table 1 needs a "Status vs target" column; objectives need honest status
Add a new column with values computed from the numbers (do not soften):
| Row | Target | Our number | Status |
|---|---|---|---|
| Detection F1 | ≥ 90% at ≥ 0 dB | 93.00% pop (93.06% test); c4 83.06%; min record 59.55% | **Met on population mean; not met for c4 / worst records** |
| FHR MAE normal | < 1.0 bpm clean baseline | sub01 TC1–TC3 0.32–0.48; population c0 3.29 | **Met on Subject 1 only; not met on population** |
| FHR MAE challenging | < 8.0 bpm all 5 conditions | 6.57 mean; c4 16.10; held-out test 8.00 | **Met on mean only; not met for c4; test at limit** |
| Clinical agreement | ≥ 95% baseline; > 50% overall | 74.0% c0; 58.0% overall | **Baseline not met; overall met** |
| Compute time | < 4,000 µs | (updated per N-05) | **Estimate (L4 sized)** |
| Group delay | < 100 ms | 11.4–15.4 ms in-band; 96 ms edge | **Met (edge borderline)** |
| Power | < 1.5 W board | < 0.15 W core (estimate) | **Estimate only** |
- Rename the last column from "Validation Level … Verified" to "Evidence level (measured L1 / bit-true L2 / estimate L4)"; "Verified" must not be used for a target that is not met.
- In Sec. 3 add an "Objective status" table (O1 partially met, O2 met for the beamformer chain under S-03/S-04 conditions, O3/O4 sized/estimate, O5 not started). If any target is changed to fit results, record it in Table 13 with a reason — never silently.
- Sec. 2 clinical mode 3 ("fetal arrhythmia screening … TPR > 95%"): the system only detects QRS timing (6% ±5-bpm agreement on c4); remove the claim that it supports screening or state it as future work.
- Sec. 2 "latency < 100 ms to trigger alerts": define latency (per-sample group delay vs beat-to-display) and cite a source; the 5-beat median alone adds ≈ 2 s.
- Sec. 2 battery requirement: add the arithmetic (1.5 W × 12 h = 18 Wh ≈ 4.9 Ah at 3.7 V) and state that the Boolean Board power has not been measured.

### S-11 [WRITE] Rebuild the replication scorecard (Table 10 / Sec. 12) — currently weak
Problems: R1 (Ahlstrom & Tompkins 1985) is a microprocessor ECG-filter paper, not a Butterworth specification, and the "verification" compares the design to the report's own Fig. 4 (circular). R2, R3, R4 have no published numbers to compare. R7's "Our Obtained Metric" column contains **literature** values (81.2%, 42.1%), i.e., nothing was measured. R4 claims "32-tap transversal LMS … TC1 F1 15.06%", but 15.06% is the **SWT-LMS** row of Table 3, not a 32-tap LMS. R5/R6 quote published numbers (≈78% at 12 dB; 82.3%/>90%) without page/table locators.
**Fix:**
1. Columns: ID | Source [ref] | Published claim (value + page/table/figure) | Our setup | Our value | Ratio or Δ | Tolerance | Status ∈ {Reproduced, Partially reproduced, Documented mismatch (explained), Not replicated}.
2. Keep a row only if a **numerical or functional-form claim** from the source is located in the paper (give the locator). Delete or relabel rows without it (R1 → move to "implementation checks", not replication).
3. R7: implement it — FECGSYNDB provides the two maternal thoracic channels (0-based 32, 33); run a 32-tap NLMS maternal-reference canceller on Lead 27 with the same detector and the same TC1–TC3; report **our** numbers. If you cannot run it before the deadline, mark "Not replicated" and delete the literature numbers from the "Our" column.
4. R4: either run an actual single-lead 32-tap LMS and report its numbers, or relabel the row to what was run (SWT-LMS).
5. Mark any published number you cannot re-find as `\todo` and do not print it.
6. Align the narrative in Sec. 12 and Table 13 R-14 ("7 published algorithms replicated") with the number of rows that remain.

### S-12 [WRITE] Related work / research gap
- Sec. 1 "existing FPGA architectures often implement trivial thresholding or rely on expensive off-chip floating-point coprocessors" has **no citation**, and Sec. 11 lists no FPGA/embedded NIFECG work.
- **Fix:** add 2–4 *verified* references on hardware/embedded fetal-ECG or ECG-QRS FPGA/ASIC implementations (search IEEE Xplore/PubMed; cite only what you read at least at abstract level; follow A-03) and add a sixth paradigm bullet "Hardware/embedded implementations" to Sec. 11. If none can be verified, rewrite the sentence as "To the best of our knowledge, we did not find…" and do **not** claim novelty. Add a Table 12-style position sentence.

### S-13 [WRITE] Demo script timing and claims (Sec. 13, Table 11)
- "7-segment display stabilizes at 143 bpm within ≈ 2.5 s" ignores the **3.0 s calibration** + UART transfer of weights. Total time-to-first-valid-FHR = calibration + weight return + ≥ 5 beats ≈ 3 s + ~2.1 s ⇒ ≈ 5+ s. Fix the number or say "after calibration".
- Add what happens when switching presets (does the host re-run calibration? yes/no).
- State that "143 bpm" is the ground-truth rate of sub01 c0 and how the displayed value is compared to it.

### S-14 [WRITE] Roadmap realism
- "11–13 Nov: real-world clinical validation on PhysioNet Challenge 2013 recordings and final report" is not realistic as the last 3 days. Also, the 4-lead array [27, 26, 28, 25] is specific to FECGSYNDB geometry; Challenge 2013 recordings have their own 4 abdominal channels (different sampling rate), so lead selection does not transfer; only PCA calibration does.
- **Fix:** move real-data validation earlier (software-only, L1) or mark it "stretch goal"; add "resample to 250 Hz; use the 4 provided abdominal channels; recalibrate PCA per record" and list the risk. Keep dates consistent with Table 12.

### S-15 [WRITE] Claim-strength edits (apply literally)
| Location | Replace | With |
|---|---|---|
| Abstract | "Analytical architectural sizing [L4 Target] **demonstrates** that a single DSP48E1 slice … executes in 128 clock cycles" | "Analytical sizing **estimates** that a single time-multiplexed DSP48E1 slice would complete the per-sample chain in N cycles (N from N-05; not yet synthesized)" |
| Abstract/Sec. 1 | "providing a 3,125× compute margin" | "an estimated compute margin of M× (M = 400,000/N)" |
| Table 1 / all validation columns | "Verified" (where target not met or L4) | "Measured (L1)" / "Bit-true (L2)" / "Estimate (L4)" |
| Sec. 4 | "completely preserving the untouched status of held-out test subjects" | "no sub09–sub10 data were used for lead selection, hyperparameters or training" |
| Sec. 8.1(3) | "Spatial nulling isolates the fetal signal in coordinate space regardless of temporal coincidence" | "Spatial projection reduces the dependence on temporal coincidence of maternal/fetal QRS; it still degrades under fetal movement (c1: 72.79% on TC4) and arrhythmia (c4)" |
| Sec. 8.3 | "…remain the definitive indicator of model capability" | delete (see S-08) |
| Table 10 R6 | "verified generalization on held-out test subjects" | "evaluated on two held-out subjects (n = 2)" |
| Sec. 1 | "Our project directly bridges this gap by realizing an end-to-end, bit-accurate, and latency-deterministic … pipeline" | "This project works toward … (bit-true L2 complete; RTL/board pending)" |
| Sec. 14 | any "rigorous" without evidence | remove the adjective |

### S-16 [WRITE] U-Net reproducibility details (Sec. 5.3)
- Sec. 4 says validation is used "for early stopping" but Sec. 5.3 says "50 epochs". State: was early stopping used, patience, best epoch, final train/val loss. Add window length, stride, normalization, augmentation, and which lead the 1-Ch network uses (Lead 27?). Say which checkpoint was evaluated on the test set and that the test set was evaluated once.

### S-17 [WRITE] Detector notation and ambiguity
- The symbols **N** (calibration window 750 samples), **N** (noise level in Sec. 5.2 text "signal peak level S and noise level N") and **N_run/N_subj** collide. Use SPKI/NPKI consistently (already used in Eq. 9–10) and remove the bare "S" and "N" there. Eq. 9 and 10 use the same form for SPKI and NPKI; add one sentence that SPKI is updated on accepted peaks and NPKI on rejected ones (PK = the current peak).

---

## 6. WRITING, STRUCTURE AND FIGURE ITEMS (Phase E)

### W-01 [WRITE] Abstract is ~330 words with ~25 numbers
- Rewrite to ≤ 200 words. Keep: problem; approach (4-lead suprapubic spatial PCA, host calibration + FPGA streaming); evaluation protocol (subject-wise split 70/10/20, 250 records); headline results (held-out 93.06% F1, population 93.00% [90.65, 95.34], FHR MAE 6.57 bpm; U-Net comparison with correct numbers per N-02); fixed-point result (+SQNR with its definition); hardware **estimate** (per N-05); status (L3 in progress, L4/L5 pending). Move CI mechanics (SE, df, half-width) to Sec. 7.

### W-02 [WRITE] Add a "Conclusions and Objective Status" section
- The report has no conclusion section. Add it after Sec. 14 (before AI disclosure): 5–7 numbered findings with the *final* numbers, the objective-status table from S-10, three honest limitations (synthetic data only; 2-subject test set; no synthesis/board results yet), and the remaining-work list (link to the roadmap).

### W-03 [WRITE] Table 3 readability and ordering
- Rows within each TC are ordered differently (e.g., TC4/TC5 list U-Net before PCA; TC2/TC3 order of Hankel/Template/Wavelet varies). Use a fixed method order everywhere (Tables 3, 4, 5, 6; Figs. 6, 8, 9, 12–15): PCA, U-Net, MC Fusion, Wavelet-Thr., Fixed TS, Hankel V1, SWT-LMS (if kept).
- The table is too small to read at print size; split into Table 3a (TC1–TC3) and 3b (TC4–TC5) or move TP/FP/FN/Det/Ref to an appendix and keep PPV/Se/F1/MAE/Agr./Corr./Runtime in the body.

### W-04 [WRITE] Typos/format
- Unify "Tab./Table", "Fig./Figure" usage; unify "0-based/1-based" lead notation and always say which (R7 says "Lead 33 (thoracic)" — specify 0-based channel 32 or 1-based 33).
- Section 4 list numbering: preprocessing item "2. Dual-Mode Notch Filter" is separated from item 1 by figures; keep list items together.
- Make sure underscores render in `fixed_point_model.py`, `run_benchmark.py`, `run_mega_benchmark.py`, `mega_benchmark_results.csv` (check in the final PDF text).

### F-01 [FMT] Fig. 1
- The callout box and arrow overlap the "0.04 mV (40 µV)" label; move annotations so every number is readable; fix numbers per N-07; use consistent peak vs peak-to-peak wording.

### F-02 [FMT] Fig. 6
- The legend covers the TC4/TC5 U-Net and PCA bars (value labels hidden); the TC4 U-Net bar touches the axis top. Move the legend below/outside the axes and extend ylim to 110; add value labels for **all** bars or none.

### F-03 [FMT] Fig. 20 (radar chart)
- Legend overlaps the "Worst-…" axis label (text truncated); six axes are not defined anywhere. Add a short definition of each axis (how scored 0–100%: F1, noise robustness, arrhythmia resilience (c4 F1), speed, HW efficiency, …) in the caption, move the legend out of the plot area, and ensure values match Tables 5, 8, 9.

### F-04 [FMT/CHECK] Fig. 11
- Panel A lines appear to drop sharply at high lead counts while Sec. 8.2 says performance plateaus at 90–93.4% for 8–34 leads. State in the caption how leads are added (order: by training FMR rank? fixed list?), and verify that the plotted curves match the text numbers; fix whichever is wrong.

### F-05 [FMT] Fig. 17 (single-DSP schedule) and Fig. 18
- Fig. 17 draws five 4-cycle blocks plus an ≈18-cycle block (≈22–38 cycles), while the caption/text claim 128 cycles with 40/20/4/5/59 breakdown. Redraw to the final schedule from N-05 with a Gantt of the real stage cycle counts, correct x-axis end label (400k cycles = 4 ms), and say "all five IIR sections (bandpass ×4 + notch)" instead of "all four IIR filters".
- Fig. 18: regenerate at 100 MHz (N-09); enlarge fonts.

### F-06 [FMT] Final PDF checks
- No overfull hbox warnings, no figure text smaller than ≈7 pt at print size, all captions carry level tags, every table fits the page width.

---

## 7. VERIFICATION SCRIPT AND CHECKLIST (Phase A and F)

Create/extend `tools/audit_mtr8.py` (and call it from `tools/check_consistency.py`). It must fail the build if any check fails. Required checks:

1. **Table 3 internal:** Det = TP+FP; FN = Ref − TP; PPV = TP/Det; Se = TP/Ref; F1 = 2·PPV·Se/(PPV+Se) (tolerance 0.05 pt).
2. **Table 4 = unweighted mean of Table 3** per method (F1, FHR MAE, Agr., Corr.).
3. **Table 6 vs Table 7:** per-partition means from per-subject values (Train = sub01–07, Val = sub08, Test = sub09–10); **All = mean of the 10 subjects**; check F1 and MAE for PCA and U-Net 4-Ch (currently PCA Train MAE fails).
4. **CIs:** per-subject mean → SD (n−1) → t(0.025, 9) = 2.262 → half-width; compare with Table 5/Sec. 7 for PCA and U-Net (U-Net currently fails). Run-level SE = s/√250, half-width = 1.96·SE.
5. **Table 8 vs Table 5:** condition means and SNR means average to the population mean (currently pass: 93.00 / 93.00; MAE 6.57).
6. **Fixed-point:** Eq. 13 values (95.1, 71.0, 59.0 dB for B = 16, 12, 10; C = 4); Δ = 5 mV/32768 = 0.1526 µV; 20 µV → 131 LSB; 2.5 mV → 16,384 LSB.
7. **Hardware sizing:** utilisation % = count / device totals (XC7S50: 32,600 LUT, 65,200 FF, 120 DSP48E1, 75 BRAM36); recompute every % in Table 9 and in text; cycles → µs (×10 ns) → % of 400,000 → margin; sum of stage cycles equals the stated total (after N-05).
8. **UART:** 8 bytes × 10 bits = 80 bits / 921,600 = 86.8 µs; /4,000 µs = 2.17%.
9. **Data-size arithmetic:** 75,000 × 34 × 2 B = 5.1 MB/record; ×250 = 1.275 GB; ×2 for 32-bit = 2.55 GB; partition sizes 1.79/0.26/0.51 GB.
10. **Detector constants:** W = 15 samples = 60 ms; refractory 50 samples = 200 ms; offset W/2 + 2 = 9.5 samples = 38 ms; group delay samples ↔ ms (N-13).
11. **Eigen-spectrum:** λ shares sum to 100% (88.4 + 7.8 + 2.6 + 1.2) and first two = 96.2%.
12. **Probabilities in Eq. 1:** 140/800 = 17.5%; 140/430 = 32.6%; 40/800 = 5.0%.
13. **Text-vs-table greps:** list every number that appears both in prose/captions and in a table (F1, MAE, counts, %), and assert equality. Include "< 24%", "> 91%", "< 3%", "3,125×", "31 references", "35 runs", "2,250 runs".
14. **Anonymity grep:** `vivek`, any author names, `/home/`, `github.com/<user>`, email patterns → must return nothing.
15. **Citation check:** every `\cite` key exists; every bib entry is cited; count printed and equals the number quoted in Table 13 R-13.

Final manual checklist:
- [ ] `python tools/make_numbers_tex.py && python tools/check_consistency.py && python report/mid_term/build_full_report.py` all pass.
- [ ] PDF text search: "Vivek" → 0 hits; "exactly 128" → 0 hits (unless N-05 concluded otherwise with a derivation); "< 3%" → 0 hits.
- [ ] Every figure/table cited in text; every caption carries its [L#] tag.
- [ ] Table 1 has the Status column; Sec. 3 has the objective-status table; Conclusions section exists.
- [ ] Sec. 16 matches reality; `\todo`s resolved or listed.

---

## 8. DELIVERABLES

1. Updated LaTeX/PDF (`mtr8_corrected.pdf`) and all changed scripts.
2. `CHANGELOG_MTR8.md` — one entry per ID (A-*, N-*, X-*, S-*, W-*, F-*): file, location, before → after, data source.
3. `audit_before.txt` and `audit_after.txt` from `tools/audit_mtr8.py`.
4. `refs_audit.md` — per-reference status (confirmed / corrected / removed) with DOI/URL.
5. `UNRESOLVED.md` — every `\todo` and every `[CHECK]` item where logs did not settle the question, each with the exact question for the team.

---

## 9. DO NOT CHANGE (verified correct — leave as is)

- Table 4 averages (all methods): they equal the unweighted means of Table 3.
- Table 3 count identities (Det = TP + FP, FN = Ref − TP) and every PPV/Se/F1 derived from them.
- PCA between-subject statistics: mean 93.00%, SD 3.28, ±2.35, CI [90.65, 95.34]; run-level SE 0.55%, ±1.08%.
- U-Net per-subject mean 90.76%; Train 88.13%, Val 95.69%, Test 97.48% F1; U-Net MAE 3.97/3.03/2.43/3.57.
- Table 8 condition and SNR means (93.00% for both; MAE 6.57; agreement 58.0%).
- Eq. 1 probabilities (17.5%, 32.6%, 5.0%); Eq. 13 values; Δ = 0.152 µV/LSB; 131 and 16,384 LSB; 86.8 µs and 2.17% UART numbers; 400,000/128 = 3,125 (as arithmetic — the *cycle count* is what N-05 revisits); data sizes (1.28 GB, 2.55 GB, 1.79/0.26/0.51 GB); XC7S50 percentages in Table 9 (990/32,600 = 3.04%, 720/65,200 = 1.10%, 1/120 = 0.83%, 1/75 BRAM = 1.33%, etc.); eigenvalue shares; Pan–Tompkins constants (W = 15 = 60 ms, 200 ms refractory, 9.5-sample offset = 38 ms); the 0-based ↔ 1-based lead mapping [27, 26, 28, 25] ↔ [28, 27, 29, 26].
