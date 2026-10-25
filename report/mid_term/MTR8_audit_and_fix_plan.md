# MTR-8 (Team 8) Mid-Term Report: Error Audit and Fix Plan

Target report: `mtr-8.pdf` (Non-Invasive Fetal ECG Extraction from Multichannel Abdominal Mixtures and Real-Time FPGA Implementation).
Reference used for comparison: `mtr-22.pdf` (Team 22). Requirements source: `project.pdf` (EE2000 flier).

**Deadline note:** the flier sets the mid-term deadline at **25.10.2026**. Do the P0 items first. Most of them are text, caption, table and labelling fixes, not new experiments.

---

## 0. Instructions for the Antigravity agent (read first)

1. **Never invent, round or "adjust" numbers to make things agree.** Every number in the paper must be regenerated from the results CSV or logs (`results/mega_benchmark_results.csv`, `code/results/metrics.csv`, the fixed-point logs). If a number cannot be regenerated, delete it or relabel it as an *estimate / not measured*.
2. Keep the validation-level tags (L1 floating point, L2 bit-true fixed point, L3 RTL sim, L4 synthesis, L5 board). Tag a number only with the level that actually produced it.
3. The template is anonymous ("Anonymous EE2000 submission"). Do not put team-member names in the paper body.
4. Log every edit in `CHANGELOG_MTR8.md` as `ID | file | before -> after | evidence`.
5. Items marked **[CONFIRMED]** are provable from the PDF itself (arithmetic or internal contradiction). Items marked **[VERIFY]** are suspected from the PDF; open the code or data and confirm before editing. Items marked **[EXTERNAL]** depend on outside facts (standards, papers); check the source.
6. Work order: P0, then P1, then P2. After finishing, run the consistency checker in Section 11 and the final checklist in Section 12.
7. Stop generating paper numbers by hand. Create `tools/make_numbers_tex.py` that reads the CSVs and writes `numbers.tex` with `\newcommand{\pcaFone}{93.00}` style macros, and use those macros in the LaTeX text and tables. This removes copy/paste errors permanently.

**Limits of this audit:** I saw only the three PDFs. I did not see the LaTeX source, the Python code, the Verilog or the CSVs. Code-level problems below are inferred from what the report says the code does.

---

## 1. Priority index

| ID | Sev | Type | One-line summary |
|---|---|---|---|
| E-01 | P0 | Calculation | Table 4 averages do not match Table 3 (9 values wrong) |
| E-02 | P0 | Statistics | U-Net 90.76% is used for two different populations; CI built with the wrong N/df |
| E-03 | P0 | Protocol | PCA 93.00% called "generalization" but is averaged over all 250 records, including tuning data |
| E-04 | P0 | Statistics | "Run-level SE ±0.88%" is actually a 95% CI half-width |
| E-05 | P0 | Calculation | Population FHR MAE 0.48 bpm contradicts sub01 (2.56 bpm) and the Bland-Altman figure |
| E-06 | P0 | Calculation | Runtime numbers contradict each other (Table 3 vs Table 5 vs Fig. 21); "whereas" is backwards |
| E-07 | P0 | Calculation | Maternal/fetal amplitude ratio stated as 5-25x, 25x, 250x and FMR 0.54 |
| E-08 | P0 | Hardware | Q1.15 LSB = 30.5 uV is larger than the 20 uV fetal signal |
| E-09 | P0 | Hardware | "End-to-end latency 3.28 us" is compute time; real latency is 96 ms+ |
| E-10 | P0 | Hardware | 22-cycle single-DSP schedule is infeasible as counted |
| E-11 | P0 | Theory/Graph | Filter order, Fig. 4 curves and group-delay statement disagree |
| E-12 | P0 | Claims | Overclaims ("100% F1", "Verified", "proving", "inevitably") |
| E-13 | P0 | Consistency | L3 status, BRAM usage and switch presets contradict each other |
| E-14 | P0 | Consistency | 35-run vs 36 rows; six vs seven vs nine methods; undefined methods |
| E-15 | P0 | Traceability | Numbers quoted with no table, figure or code behind them |
| E-16 | P0 | Compliance | AI disclosure is vague and contradicted by the errors above |
| E-17 | P0 | Compliance | Team-member names appear in an anonymous submission |
| E-18 | P0 | Claims | AAMI EC57 misattributed; "clinical standard" targets are self-chosen |
| T-01..T-12 | P1 | Theory | Rank-3 vs w=v2, eigen-spectrum interpretation, polarity, null-depth bound, etc. |
| H-01..H-09 | P1 | Hardware | Missing pipeline blocks, fixed-point formats, DSP pipelining, UART, board mapping, roadmap |
| C-01..C-10 | P1 | Code/Protocol | Split discipline, LOSO, per-subject table, SNR non-monotonicity, rounding code, reproducibility |
| G-01..G-14 | P1/P2 | Graphical | Wrong labels, captions that contradict plots, overlapping legends, tiny fonts |
| R-01..R-06 | P1 | References | Wrong authors, mis-attributed models, uncited entries |
| W-01..W-06 | P2 | Writing | Abstract length, naming, structure |

---

## 2. P0 items (fix today)

### E-01 [CONFIRMED] Table 4 does not match Table 3
- **Where:** Table 4 (Reconciled Performance on Subject 1), computed from Table 3 (TC1-TC5).
- **Problem:** Averaging the per-test-case values printed in Table 3 gives different numbers from the ones in Table 4.

| Algorithm | Metric | Printed in Table 4 | Recomputed from Table 3 |
|---|---|---|---|
| Deep 1D U-Net | Agreement (+-5 bpm) | 97.6% | **98.38%** |
| MC Template Fusion | FHR MAE | 8.50 bpm | **12.50 bpm** |
| MC Template Fusion | Corr. | 0.565 | **0.553** |
| MC Template Fusion | F1 | 69.78% | 69.77% (rounding) |
| Vivek Hybrid | Agreement | 42.2% | **43.94%** |
| Template Sub. (Fixed) | Agreement | 41.4% | **43.40%** |
| Template Sub. (Fixed) | Corr. | 0.137 | **0.139** |
| SVD V1 | FHR MAE | 30.69 bpm | **29.89 bpm** |
| SVD V1 | Agreement | 41.7% | **43.68%** |
| SVD V1 | Corr. | 0.138 | **0.140** |

  Rows that check out: all F1 values, all Spatial PCA values, U-Net MAE/Corr, Vivek MAE/Corr, Template MAE, all SWT-LMS values.
- **Why it matters:** Section 19 claims every value in Tables 3-5 was independently recomputed and audited. As printed, that claim is false.
- **Fix:** Generate Table 4 programmatically from the same CSV as Table 3 (macro file, see Section 0 item 7). Decide once whether SVD V3 (which appears only in TC3 of Table 3, see E-14) is part of the table. Then fix the Section 19 wording.
- **Done when:** `tools/check_consistency.py` (Section 11) reports zero mismatches.

### E-02 [CONFIRMED] U-Net 90.76% used for two different populations, CI built with the wrong N/df
- **Where:** Abstract, contribution 4, Sec. 10.1 item 1, Table 5, Fig. 12, Table 7 (R6).
- **Problem:**
  - Abstract and R6 say 90.76% (4-ch) and 80.79% (1-ch) are *unseen test subjects* (sub09-sub10, 50 records).
  - Table 5 and Fig. 12 present the same 90.76% / 80.79% as the **full 250-record** population, which includes the 175 training records.
  - The run-level interval (+-1.24%) uses N=250 (`1.96*10.03/sqrt(250)`), and the clustered CI uses t with df=9 (10 subjects). With only 2 unseen subjects the correct t is df=1 (t = 12.71), which makes the interval huge.
  - One of the two descriptions is wrong. If Table 5 includes training subjects, the 90.76% is partly in-sample and overstates generalization.
- **Fix:**
  1. Open `results/mega_benchmark_results.csv` and add a column `partition` (train / val / test).
  2. Report U-Net separately for train (sub01-07), val (sub08) and test (sub09-10).
  3. Prefer **leave-one-subject-out (LOSO)** for U-Net (10 folds). It gives 10 true held-out subject means, and df=9 becomes legitimate (see C-02).
  4. Rewrite the abstract, Sec. 10.1, Table 5 caption, Fig. 12 caption and R6 so they describe the same population.
- **Done when:** every place that quotes 90.76% / 80.79% names the same partition, and the CI method matches the number of clusters.

### E-03 [CONFIRMED / VERIFY] PCA 93.00% is called "generalization" but is not a held-out number
- **Where:** Contribution 2 ("93.00% +- 2.35% generalization F1"), Table 1 ("93.00% Verified"), Sec. 4 ("test partition held out during training and lead selection").
- **Problem:** The 93.00% is the mean over all 250 records of all 10 subjects. Lead selection (Fig. 3, FMR topography), PPR-8 thresholds, window length N=750 and polarity logic were most likely tuned on sub01 (the "frozen benchmark") or on all data. The paper never says which data were used to choose them, and it never reports PCA on sub09-sub10 alone.
- **Fix:**
  1. State exactly which records were used for lead selection and for every tuned constant (N, detector thresholds, refractory period, lambda).
  2. Recompute lead selection using **sub01-sub07 only** (or LOSO) and show the chosen subset is still [27,26,28,25] (1-based indexing, see G-03).
  3. Report PCA on sub09-sub10 separately, plus the all-250 number clearly labelled "population (tuning data included)".
  4. Use the word "generalization" only for held-out subjects.
- **Done when:** the paper has a table with columns `train | val | test | all` for PCA and U-Net.

### E-04 [CONFIRMED] "Run-level SE" is a 95% CI half-width
- **Where:** Abstract, contribution 2, Table 5 caption, Eq. (20).
- **Problem:** `1.96 * 7.07 / sqrt(250) = 0.876`. That is the half-width of a 95% CI, not a standard error. The standard error is `7.07/sqrt(250) = 0.447%`. Same for U-Net (SE 0.634%, half-width 1.24%).
- **Fix:** Rename to "95% CI half-width" everywhere, or report the SE (0.45%). Do not call +-0.88% an SE.

### E-05 [CONFIRMED] FHR metrics contradict each other and the Bland-Altman plot
- **Where:** Abstract, Table 1, Table 4, Table 5, Fig. 7(b) caption.
- **Problems:**
  - Sub01 average (Table 4): PCA FHR MAE **2.56 bpm**, agreement **94.7%**, F1 92.15%.
  - Population (Table 5): PCA FHR MAE **0.48 bpm**, agreement **96.8%**, F1 93.00%.
  - Nearly equal F1 but a 5x lower MAE is not credible; Table 3 shows PCA MAE is 8.42 bpm on TC4 and 3.15 bpm on TC5. A population that includes c1 and c4 across 10 subjects (c4 F1 = 83.06%, min F1 = 59.55%) cannot average 0.48 bpm unless the metric is computed differently.
  - The number **96.8%** appears as both overall clinical agreement and the c3 (contraction) F1 (96.82%). Check this is not a copy error.
  - Fig. 7(b): the caption says limits of agreement are "[-1.96, +1.96] bpm". The figure itself prints roughly bias -0.57, +1.96 SD = +5.9 and -1.96 SD = -6.75 bpm (as I read it; verify). 1.96 is the multiplier, not a bpm value. Limits of about +-6 bpm contradict "MAE 0.48 bpm" and "96.8% within +-5 bpm".
  - Fig. 7(a) caption says PCA and U-Net "maintain sub-bpm error" across TC1-TC5. PCA is 8.42 and 3.15 bpm on TC4/TC5.
- **Fix:** Define precisely how FHR MAE is computed (per record, per beat, after which smoothing, including or excluding missed beats). Recompute from the CSV with one function used for both Table 4 and Table 5. Fix the Fig. 7 captions to match the plotted numbers.

### E-06 [CONFIRMED] Runtime numbers contradict each other
- **Where:** Table 3 (Runtime column), Table 5 (Speed), Fig. 21 plot and caption.
- **Problems:**
  - Spatial PCA: 0.003 s (Table 3), 190.7 ms (Table 5), 3 ms (Fig. 21 plot), 190.7 ms (Fig. 21 caption).
  - SWT-LMS: 1.772 s (Table 3), 1.78 s (Fig. 21 plot), 107.5 s (Fig. 21 caption). The factor ~60 suggests per 5-second window vs per 5-minute record.
  - U-Net 4-ch: 82 ms (Table 3/Fig. 21) vs 98.6 ms (Table 5).
  - Fig. 21 caption: "Spatial PCA completes in 190.7 ms ... **whereas** U-Net requires 98.6 ms on GPU". 98.6 < 190.7, so "whereas" implies the wrong direction.
  - Fig. 21 title says "per 5-minute record" but the plotted values look like per-window numbers.
- **Fix:** Decide the unit (per 5-minute record, one run, CPU/GPU named, warm-up excluded) and re-time everything with one script. Use the same table everywhere. Fix the caption wording. Say which hardware (CPU model, GPU) produced the timings.

### E-07 [CONFIRMED] Maternal/fetal amplitude ratio is stated inconsistently
- **Where:** Abstract, Sec. 1, Fig. 1, Table 1, Sec. 6, Sec. 11.1.
- **Problems:**
  - Sec. 1: "5-25x larger (1-5 mV vs 20-100 uV)". Those ranges give **10x to 250x**, not 5-25x.
  - Fig. 1: 25x (0.04 vs 1.00). Table 1: 20 uV to 5 mV (250x, 48 dB). Sec. 6: "25x (28 dB)".
  - Fig. 3: best-lead FMR = 0.54 (fetal std is 54% of maternal std). That conflicts with "25x" unless peak vs RMS is explained.
  - Using Fig. 1's own amplitudes, fetal power is about 0.16% of maternal; the paper then says the second eigenvalue (7.8% of variance) is the fetal signal (see T-02).
- **Fix:** Define two quantities explicitly: peak-amplitude ratio and RMS ratio (FMR). Quote ranges that are arithmetically correct. Use one example consistently. Explain why FMR 0.54 coexists with a 25x peak ratio.

### E-08 [CONFIRMED] Q1.15 resolution of 30.5 uV is bigger than the fetal signal
- **Where:** Sec. 6 ("Input Biopotentials: Q1.15, resolution 2^-15 ~ 30.5 uV"), Table 1 ("16-bit Q1.15 Verified" for 20 uV to 5 mV).
- **Problem:** A 30.5 uV LSB means full scale = 1 V. A 20-100 uV fetal signal would then be 0.7-3 LSB, i.e. unrepresentable. The "input dynamic range verified" claim is therefore wrong as stated.
- **Fix:** Define the analog-front-end mapping explicitly (for example full scale = +-5 mV, so 1 LSB = 5 mV / 32768 = 0.15 uV, and 20 uV = about 131 LSB). Check that the golden test vectors use that scaling. Recompute the SQNR statements with the real signal level and say what fraction of full scale the fetal component occupies.

### E-09 [CONFIRMED] "End-to-end latency 3.28 us" is not latency
- **Where:** Table 1 (<100 ms alarm latency vs 3.28 us), Table 6, Sec. 12, objective O3.
- **Problems:**
  - 3.28 us is the sum of per-stage compute times (0.16+0.04+0.02+0.01+3.05).
  - The paper itself states a **24-sample (96 ms) filter group delay**, a **3 s (N=750) covariance window**, and a **5-beat median FHR filter** (about 2 s at 142 bpm). The true alarm latency is seconds, not microseconds.
  - UART latency of 3.05 us is wrong: one byte at 921,600 baud takes `10/921600 = 10.85 us`; one 4-lead sample (8 bytes) takes about 87 us.
  - The viva script claims the display "stabilizes at 142 within 1.2 s", which is shorter than the 3 s covariance window plus the 5-beat median.
- **Fix:** Split into (a) per-sample compute time (a throughput/margin number) and (b) algorithmic latency (filter delay + window + median). Put the real alarm latency in Table 1 and explain whether it meets the 100 ms target (it probably does not for the full chain; say so). Correct the UART time. Correct the viva timing.

### E-10 [CONFIRMED] The 22-cycle single-DSP schedule cannot be correct as counted
- **Where:** Sec. 11.2, Fig. 17, Table 6, abstract.
- **Problems:**
  - A direct-form-II biquad (SOS) needs 5 multiplies (b0, b1, b2, a1, a2). One DSP48E1 does one MAC per cycle, so one SOS per channel needs at least 5 cycles, not 4.
  - The filter in Fig. 4 behaves like 4 SOS sections per channel (see E-11): 4 ch x 4 SOS x 5 = **80 cycles**, plus the 50/60 Hz notch (4 ch x 5 = 20 cycles). The report budgets **16 cycles** for the whole preprocessing.
  - Derivative filter "5-point in 2 cycles": a 5-tap FIR is 5 MACs on one DSP.
  - DSP48E1 has input/multiplier/output register stages (2-4 cycles of latency depending on configuration). IIR recursion has a loop dependency, so back-to-back dependent MACs cannot issue every cycle without handling that latency.
  - FHR = 60*fs/interval needs a division. "0.01 us" (1 cycle) for the FHR estimator is not achievable; multi-cycle per-beat division is fine but must be stated.
  - PPR-8 uses squaring (energy) but is listed as "0 DSP (logic)" with 180 LUTs; a 16x16 multiplier in LUTs costs more than that.
- **Good news:** the conclusion survives. Even with ~120-150 cycles the design uses about 0.04% of the 400,000-cycle sample budget, so a single DSP is still plausible.
- **Fix:** Recount the cycle schedule per stage, with pipeline latency, from the actual filter structure. Update 22 cycles / 0.22 us / 0.0055% / 99.99% everywhere. Add a timing diagram that matches the recount.

### E-11 [CONFIRMED] Filter order, Fig. 4 and the group-delay statement disagree
- **Where:** Eq. (4), Sec. 4 text, Fig. 4 and caption, Fig. 2 caption, Sec. 11.2.
- **Problems:**
  - Text: "4th-order Butterworth bandpass, two cascaded SOS". Printed attenuations (>40 dB at 0.1 Hz, >14 dB at 60 Hz) match a **4th-order high-pass plus 4th-order low-pass**, i.e. `scipy.signal.butter(4, [0.5,40], 'bandpass')`, which returns an **8th-order** filter = **4 SOS**. Quick check: a 2nd-order low-pass at 40 Hz gives only -7.8 dB at 60 Hz; a 4th-order gives -14.3 dB.
  - Fig. 4 caption says it shows the 0.5-40 Hz bandpass, but the legend lists "HPF 0.5 Hz, Notch 50 Hz, BPF 1-100 Hz, QRS BPF 8-30 Hz". None of these is the 0.5-40 Hz filter; the 60 Hz claim cannot be read from the plot.
  - "Causal direct-form II introduces a **constant** 24-sample (96 ms) group delay that is fully compensated". An IIR Butterworth has **non-constant** group delay (nonlinear phase), and near the 0.5 Hz corner the delay is far larger than 96 ms. Exact compensation is impossible.
  - SOS coefficients with `a1` near -2 do not fit Q1.15 (range -1 to +1). Coefficients need Q2.14 or scaled sections.
- **Fix:** State the true order and number of SOS. Plot the actual 0.5-40 Hz response (`scipy.signal.sosfreqz`) and the notch separately, with correct axis in Hz up to 125. Compute group delay with `scipy.signal.group_delay` and report it versus frequency. Verify detected peaks are aligned with the reference (see C-05). Define the coefficient Q-format per stage.

### E-12 [CONFIRMED] Overclaims
Fix each sentence or add the missing qualifier.

| Sentence / location | Problem | Rewrite direction |
|---|---|---|
| Contribution 1, Sec. 10.1 item 3, abstract: "100.0% F1 across TC1-TC3" | This is **sub01 only** (one subject, c0 only). Population at 0 dB is 93.68%, minimum record 59.55%. | Say "on subject 1 (in-sample for tuning)". |
| Table 1: F1 >= 90% at >= 0 dB "93.00% Verified" | Requirement is per condition; c4 = 83.06%, sub01 TC4 = 72.79%, TC5 = 87.95%. | Show per-SNR/per-condition values and mark failing ones. |
| Table 1: "Form factor: Wearable patch, 4 leads [L1] Verified"; "Input range Verified" | Form factor cannot be verified by simulation; range is wrong (E-08). | Remove or relabel as "design intent". |
| Sec. 10.2: "proving that our 4-lead subarray provides the optimal trade-off" | A plateau of 90-93.4% from 8-34 leads does not prove optimality. | "suggests", and add the lead-count sweep with CIs. |
| Sec. 1: collapse "inevitably" / "fatal mathematical failure" | Template subtraction handles overlap partially; failure is implementation-specific. | Tone down; see T-08. |
| Sec. 10.1 item 2: "acceptable performance only at 12 dB (76.36%)" | 76% fails your own O1 (>= 90%). | "reaches only 76%". |
| Title: "Real-Time FPGA Implementation" | No RTL synthesis, timing or board result exists. | Retitle, e.g. "...and Bit-True Fixed-Point Design for FPGA Implementation". |
| Fig. 8 caption: PCA/U-Net "maintain 100%"; single-channel "<24%" | U-Net is 99.37% at 0 dB; Vivek is 24.64%, SVD V3 24.09% at 0 dB. | Use exact values. |
| Fig. 15 caption: PCA ">90% across diverse lead orientations" | Subject mean 93.00 with SD 3.28 implies some subjects < 90. | Show per-subject table; fix the claim. |

### E-13 [CONFIRMED] Status and configuration contradictions
- **L3 status:** the abstract, Sec. 8, Sec. 17 and the roadmap (26-31 Oct) say Verilog coding is *future work*; Table 9 says L3 is **40% done, SOS and 4-MAC beamformer RTL coded**. Choose the truth and use it everywhere.
- **BRAM:** Table 10 R-09 says "requires 0 BRAM"; Sec. 7 and Table 6 use 1 BRAM. The 3 s covariance window (750 x 4 x 2 bytes = 6 kB) and detector buffers also need memory, so 0 is wrong.
- **Switches/presets:** Table 2 gives SW[2:0] = Normal, Noise, Movement, Arrhythmia, **Contraction**, with bypass on **SW[4]**. Table 8 gives P1-P5 with **Raw Bypass at SW[2:0] = 100** and no Contraction preset. The viva script flips **SW[4]** for bypass. Unify (a 3-bit field holds 8 presets, so both can fit).
- **Demo FHR values:** Table 8 lists 142/138/143/146 bpm, but sub01 TC1/TC3/TC4/TC5 reference counts (716/715/716/716 beats in 300 s) all give about 143.2 bpm. Fill the table from measured values.
- **Fig. 2:** caption mentions notch filter and maternal-QRS-free PCA, but the figure shows a maternal QRS detection block feeding PCA and has no notch block. Make the figure match the caption.

### E-14 [CONFIRMED] Row counts and method counts disagree
- Table 3 has **36 rows** (TC3 has an extra "SVD Variant 3" row; TC1, TC2, TC4, TC5 do not), but the text, M5 and Sec. 20 say the "frozen **35-run** benchmark".
- Methods: "six distinct paradigms" (Sec. 5), "all six extraction architectures" (Fig. 6 caption) while the Fig. 6 legend shows **seven** and Table 5 shows **nine** rows. "2,250 runs" = 250 records x 9 methods; SWT-LMS is not in Table 5 at all.
- "Template Sub. (Adapt.)", "SVD V2", "SVD V3" appear in tables or the register but are **never described** in Sec. 5.
- One method has three names: "SSNF", "SWT-LMS", "single-lead LMS". Method 5 is described as a wavelet *thresholding* method, Method 6 as plain LMS, yet the table row is "SWT-LMS Wavelet Filter".
- **Fix:** Build one method table (ID, name, input channels, trained or not, description subsection) and use those IDs in every table and figure. Run all methods on the same rows (decide on SVD V3 everywhere or nowhere). Either add SWT-LMS to the population benchmark (it is slow, ~107 s per record, so state why it is excluded) or say it is excluded.

### E-15 [CONFIRMED] Numbers with no table, figure or code behind them
Add a table and script for each, or remove the number:

| Number | Where | Missing |
|---|---|---|
| NLMS with thoracic reference: 81.2% clean, 42.1% at 0 dB | Sec. 5.6, Table 7 R7 | No table row, not in benchmark |
| Block-adaptive covariance: TC4 F1 72.79% -> 86.4% | Sec. 13 | No experiment shown |
| Hybrid wavelet: TC5 F1 +4.2% | Sec. 13 | No experiment shown |
| 1 lead: 20.6-35.8%, 2 leads: 95.3% | Sec. 10.2 | Only in Fig. 11 plot, no table |
| Maternal/fetal QRS coincidence 12-18% of cycles | Sec. 1 | No derivation or citation (rough check: ~13-21% depending on QRS widths, so derive it) |
| ">88% of mixture energy in v1" | Sec. 5.1 | Fig. 16 only on one array |
| "FPGA Power < 0.15 W core" | Table 1 | No power analysis (needs Vivado `report_power`) |
| FPGA LUT/DSP figures for MC Fusion, Vivek, SVD (e.g. "13% LUT, 48 DSPs") | Table 4 | No derivation |
| FHR 142/138/143/146 and "072" | Table 8, viva | Not measured |

### E-16 [CONFIRMED] AI disclosure
- **Flier requirement:** "clearly indicate the parts of the work that were generated by AI tools and provide appropriate citations" and be able to defend them.
- **Problems:** The disclosure lists three broad areas (boilerplate code, review, language), not which sections, figures, code files or numbers were AI-generated. It claims every value in Tables 3-5 was recomputed (false as printed, E-01), every reference was "retrieved, verified" (R-01 shows wrong authors), and cites only Claude 3.5 Sonnet ([30]) even though ChatGPT is also named (no citation for it). The report is dated Oct 2026; confirm which models/versions were really used.
- **Fix:** Rewrite Section 19 in the style of Team 22's section: say plainly which code files, which report sections and which figures were AI-drafted, what the team ran and checked, and how. Add a citation for each tool. Only claim verification that actually happened, and soften or remove the claim until E-01 and R-01 are fixed.

### E-17 [CONFIRMED] Anonymity
The template says "Anonymous EE2000 submission", but Sec. 21 lists Naman, Vivek, Anshu Ram, Astitva, and Table 4 uses "Naman SVD (V1)" while the methods are called "Vivek Hybrid Alternative". Remove names from the body and tables (use "Hankel-SVD V1", "Wavelet hybrid"). The flier asks for per-member work delineation in the **final** report; keep a roles section only if the template allows it, without names, or keep it for the final report.

### E-18 [EXTERNAL / VERIFY] Standards and "clinical requirement" claims
- **AAMI EC57:** the report says the +-50 ms matching window follows ANSI/AAMI EC57 and that EC57 gives the >= 250 Hz sampling rate. As I recall, EC57 is a methodology standard for testing arrhythmia/ST algorithms and uses a different (150 ms) matching window for adult QRS; the 50 ms fetal tolerance comes from the PhysioNet/CinC Challenge 2013 evaluation. Verify in the sources and cite the correct one.
- **Targets labelled "Clinical Standard / Requirement"** (F1 >= 90%, MAE < 1 bpm, agreement >= 95%, <100 ms alarm latency, <1.5 W for 12 h) are self-chosen. Either cite a clinical source or relabel the column "Project target".
- **"Latency must remain strictly below 100 ms to trigger emergency alerts"** (Sec. 2) has no citation and is not how FHR alarms work (decelerations are judged over tens of seconds). Remove or cite.

---

## 3. P1 theory and concept items

### T-01 Rank-3 maternal subspace vs `w = v2` vs the figure vs the data
- Eq. (24) says the maternal dipole spans rank min(C,3), so with C=4 only a 1-D orthogonal complement remains. That complement is **one** direction, not `v2`.
- In Fig. 16(a) the bars are labelled "v1 (Mat. Dipole)", "v2 (Fetal Signal)", "v3 (Mat. Y-loop)", "v4 (Noise)", while the text says lambda3 and lambda4 are "residual EMG and sensor noise". The figure says v3 is maternal; the text says it is noise. These cannot both be true.
- Sec. 11 asks "why do 4 channels saturate while 1 or 2 fail", but Sec. 10.2 reports that 2 leads already give 95.3% on TC1. Rank-3 theory predicts that 2 leads should fail.
- Eq. (6) defines `P_perp = I - v1 v1^T` but it is never used (the code uses `w = v2`, which only removes v1).
- **Fix:** Pick one model and test it. Compute the principal angles between `span(v1,v2,v3)` of the maternal-only reference leads (channels 33-34 or a maternal-only simulation) and the abdominal subspace. Report the cosine between `w` and the true fetal lead-field direction per subject. Rewrite the theory section to say "heuristic: second principal component of the 4-lead covariance", unless you can show the maternal subspace is exactly what `v1` captures. Either use `P_perp` or delete Eq. (6).

### T-02 "lambda2 = fetal signal (7.8%)" is unsupported
Using Fig. 1's amplitudes, fetal power is about 0.16% of maternal, and muscle noise (0.15 amplitude) is about 2.3% of maternal power. A 7.8% second eigenvalue is more plausibly the second maternal axis plus noise. **Fix:** compute `corr(w^T x, fetal reference)` on the record and show lambda2's share when the fetal source is switched off (FECGSYNDB provides separate maternal/fetal/noise components). Only then label v2 as fetal.

### T-03 "4 components capture 100% of the signal space" is a tautology
A 4x4 covariance always has 4 eigenvalues summing to 100%. Fig. 16(b)'s claim and the text sentence prove nothing. Remove it or replace it with a meaningful statement (for example, the cumulative variance *without* the noise subspace).

### T-04 Problem formulation promises SINR maximisation, method does not do it
Eq. (1) says the weight vector maximises fetal SINR while nulling maternal potentials, and calls `w` "unconstrained". The method is `w = v2` (a heuristic) and the weights are later constrained (`||w||2 <= 1`). Rewrite the problem statement honestly, or implement a true SINR/GEVD formulation and compare it with `v2` (a useful ablation: generalized eigenvector of the pair (window covariance, maternal-only covariance estimated from detected maternal beats)).

### T-05 Skewness polarity rule (Eq. 8) is over-claimed
"Skewness is strictly positive, uniquely resolving polarity" is not guaranteed: the residual maternal component, T-waves, EMG and biphasic fetal QRS can reverse the skewness sign. Also, recomputing the sign every sliding window can flip the output polarity between windows. **Fix:** measure the polarity-error rate over all 250 records against the fetal reference, report it, and add continuity logic (keep the sign that maximises correlation with the previous window's `w`).

### T-06 Eigenvector continuity and window design
- N=750 samples (3 s) is stated but not the hop/update rate, so streaming behaviour is unknown.
- lambda2 (7.8%) and lambda3 (2.6%) can cross, swapping v2/v3 between windows.
- **Fix:** state window length, hop, initialisation delay (nothing is output until the first window completes), and add a sweep over N and hop with F1 and latency.

### T-07 Quantization "bound" `R_null <= 6.02 B + 1.76 dB` is not a bound on null depth
- 6.02B+1.76 is the SQNR of a full-scale sine through a B-bit quantiser. It is not derived for a quantised weight vector null depth, and no derivation is given.
- Numbers disagree: at B=16 the formula gives **98.1 dB**, the text says "85.0 dB reached", and 85.04 dB is also the SQNR of SVD V1 (possible mix-up of two metrics).
- "B < 10 gives < 50 dB" contradicts the formula (B=9 gives 55.9 dB, B=10 gives 62.0 dB). "Precision >= 12 bits gives > 60 dB" is also loose because B=10 already exceeds 60 dB.
- "Requires at least 55 dB of null depth" is unexplained (28 dB maternal excess plus what margin?).
- Fig. 5 caption claims "agreement between the theoretical bound and the simulation", but the simulated curve saturates near 85 dB while the bound keeps rising.
- **Fix:** derive the null-depth bound for `w_q = w + e` (leakage ~ `||e||*||a_m||`, so depth ~ `20 log10(1/(2^-B * sqrt(C)/sqrt(12)))` style expressions) or drop the "bound" language and present it as an empirical curve. Show why saturation occurs (floor from other error sources). State the 55 dB derivation.

### T-08 Single-channel baselines look like straw men
- The paper explains the collapse by the 12-18% of beats where maternal and fetal QRS coincide. But at 12 dB, TC1, template subtraction already has **168 FP and 170 FN out of 716** (about 24% of beats), more than collisions can explain. That points to implementation or detector problems (fixed template, threshold, no adaptive scaling).
- SSNF-style LMS **without a reference** is expected to fail; calling it "LMS failure" generalises beyond what you tested. The fair ANC baseline is NLMS with the thoracic reference (channels 33-34), which you say reaches 81.2%, but it is not in any table.
- **Fix:** add a stronger, properly tuned template-subtraction/adaptive baseline and the thoracic-reference NLMS to Tables 3 and 5 with the same detector. Show the F1 split between "collision beats" and "non-collision beats" to support the 12-18% argument.

### T-09 No comparison to the standard multichannel alternatives
The literature survey names ICA/FastICA/JADE and says they are unsuitable for FPGAs, but no ICA/GEVD baseline is run. Add FastICA (or JADE) on the same 4 leads as an L1 accuracy reference, and say "not hardware-friendly" only after showing accuracy.

### T-10 Lead selection needs ground truth; the blind rule is untested
FMR = sigma_fetal / sigma_maternal needs the fetal reference, so Fig. 3 is a supervised analysis. The "blind" rule (maximise lambda2/lambda1 over candidate 4-lead subsets during a 3 s calibration) is never evaluated. **Fix:** evaluate the blind rule on all records (leave-subject-out): how often does it pick the supervised-best subset, and what F1 does it give compared with the fixed [27,26,28,25]?

### T-11 The PPR-8 fetal QRS detector is never described
All F1 and FHR numbers depend on the detector, yet its algorithm, thresholds, refractory period, window lengths and tuning data are not given. "PPR-8" is also the name of the preliminary report (PPR-8 vs MTR-8). Add a subsection with the exact algorithm (derivative, squaring, integration window, adaptive threshold rule, refractory period), cite Pan-Tompkins (ref [25] is in the bibliography but never cited), and say which records the thresholds were tuned on. Rename the detector to avoid the clash.

### T-12 Equation and notation errors
- Eq. (2): `n[n]` uses `n` as both noise vector and time index. Rename the noise vector.
- Eq. (3): `A` and `s[n]` are never defined (`A = [a_m b_f]`, `s = [m, f]^T`).
- Eq. (5): assumes zero-mean data; say so (the high-pass makes it hold approximately).
- Eq. (10): see H-02 (missing `/2^15`, half-up rounding vs "round-to-nearest-even", asymmetric clipping).
- Eq. (12): fine, but say whether the "signal" is the beamformer output or the final FHR chain.
- Eq. (26): `lambda = 0.95` per sample means a memory of `1/(1-lambda) = 20 samples = 80 ms`, shorter than one cardiac cycle and not comparable to a 3 s window. A 3 s equivalent is `lambda ~ 0.99867`. Re-derive or call the update block-wise with the block length stated.
- "Einthoven-Burger electrical volume conduction model" (Sec. 11.1) is not a standard name for the dipole model used by FECGSYNDB; cite the model's real source (see R-02).

---

## 4. P1 hardware and architecture items

### H-01 Major pipeline blocks are missing from the resource and timing tables
Table 6 and Fig. 17 contain only: Butterworth SOS, 4-MAC beamformer, PPR-8 detector, FHR median, UART. They do **not** contain:
- covariance accumulation (Eq. 5: 10 unique products per sample over a 750-sample window, or Eq. 26),
- eigen-decomposition / power iteration (Sec. 5.1, Sec. 13),
- skewness-based polarity (Eq. 8),
- the 3 s blind lead-subset selection with lambda2/lambda1,
- maternal QRS detector (LD1 blinker in Table 2, Fig. 2 block),
- 50/60 Hz notch filter,
- signal-quality index (SQI) bar graph (LD[7:4], never defined),
- recalibration control (BTN1).

**Fix (decide and write down):**
- **Option A (recommended given the time left):** the host (Python) computes `w` from the covariance and sends four Q1.15 weights over UART at calibration. The FPGA does notch + bandpass + 4-MAC beamformer + detector + FHR. BTN1 then requests a new calibration from the host. State this partition explicitly, keep the single-DSP claim, and mark covariance/eigen as a *host* function.
- **Option B:** implement covariance accumulation and a 4x4 Jacobi or power-iteration eigensolver on the FPGA, size it honestly (extra DSPs/cycles), and update Table 6 and Fig. 17.

### H-02 Fixed-point formats are incomplete or inconsistent
- Eq. (10): the code should return an integer code `clip(round(x*2^15), -32768, 32767)`; the equation lacks `/2^15` to return to value. `floor(x*2^15 + 0.5)` is **round-half-up**, not "round-to-nearest-even" as claimed. Clipping to [-32768, 32767] is **asymmetric**, not "symmetric saturation" (symmetric means +-32767). Make the text and the model agree (see C-07).
- Q9.23 (32-bit) accumulator: a Q1.15 x Q1.15 product is Q2.30; summing 4 products needs Q4.30. A Q9.23 format throws away 7 fractional bits that the DSP48E1's 48-bit accumulator would keep for free. Justify, or use the full-width accumulator and round once at the output.
- IIR sections with the 0.5 Hz high-pass have poles very close to the unit circle (pole radius about 0.987 at fs=250 Hz); direct-form II is noise-sensitive. State the section structure, state/coefficient Q-formats, and measure the per-stage SQNR (not only the final output).
- 5,000 golden vectors = 5,000 samples = 20 s of data, roughly 50 beats and only 6-7 non-overlapping 750-sample windows. Add vectors that cover the worst cases: 0 dB, c3, c4, saturation, start-up transients, plus a few complete records.

### H-03 DSP pipelining and recursion
Account for DSP48E1 pipeline registers and the IIR feedback dependency when the schedule is written (see E-10). Provide a cycle table that lists, per stage, MACs, pipeline stalls and total cycles.

### H-04 Resource and power numbers are guesses presented as sized results
Table 6 cites UG479 and "register count estimation", but UG479 does not give LUT/FF costs for your design. Run Vivado synthesis now on the pieces that already exist (SOS, 4-MAC beamformer) to replace the estimates with `report_utilization` and `report_timing_summary` numbers (that is L4 and is worth far more than analytical sizing). For power, either run `report_power` or delete the "< 0.15 W core" figure. The "Form factor / wearable / 12 hour battery" rows should be marked as out of scope for a Boolean Board demo.

### H-05 UART and memory budgeting
- UART throughput numbers (16 kbps, 20 kbps framed, 2.17% of 921,600 baud) are arithmetically fine, but they ignore packet headers, resend of weights, and the return telemetry path. Add them.
- Correct the UART timing (E-09). Show the packet format (start byte, sequence number, 4 x int16, checksum).
- BRAM: list every memory (750x4 window if on-chip, delay lines, detector buffers, UART FIFO) and give a total (see E-13).

### H-06 Boolean Board mapping must be checked against the board manual and the XDC
Verify: number of slide switches, buttons and LEDs, LED colours (is LD0 green and LD1 red?), the 7-segment display structure and multiplexing, and the USB-UART bridge name. Remove the vague pin column entries ("Bank 34/35", "Dedicated IO") unless taken from the XDC file. Ref [29] is a manual that is never cited in the text.

### H-07 Demo script realism
Fix timing (E-09), preset coding (E-13) and expected FHR values (take them from measured outputs). Define "SQI" (what metric drives LD[7:4]?). The statement "display jumps to 072 tracking maternal heart rate" must be checked against the actual maternal HR in the chosen record.

### H-08 Roadmap risk
Everything hardware (Verilog, RTL sim, synthesis, timing closure, board bring-up, viva rehearsal) is scheduled in the 19 days between 26 Oct and 13 Nov, with RTL not started. Team 22 already has a bit-exact RTL chain in simulation. **Fix:** add a risk table like Team 22's Table 14 with fallbacks (for example, if the eigen step stays on the host; if the board is not ready, report L1-L4 honestly), start RTL immediately, and keep the L2 golden vectors as the regression test bench.

### H-09 Power and battery claims
"<1.5 W for 12 h battery life" and "<0.15 W core" need a source. A Boolean Board is not a wearable; separate board power from core power.

---

## 5. P1 code and evaluation-protocol items

### C-01 Separate tuning data from evaluation data
Team 22 uses pilot seeds to choose parameters, "FREEZE-1", then untouched seeds for the final results, and logs every later change. Do the same: define `tune_records.txt` (for example sub01, or sub01-sub07) and `eval_records.txt` (sub09-sub10, then all), freeze every constant in `config_frozen.yaml` before the final run, and log any change.

### C-02 Add leave-one-subject-out (LOSO) for learned models
With only 2 unseen subjects, test statistics are weak (t at df=1 is 12.7). Train the U-Net 10 times (each time hold out one subject, validate on another), and report the 10 held-out subject means. This also makes df=9 valid for the clustered CI.

### C-03 Report per-subject results
Add a table: rows = sub01-sub10, columns = PCA F1, U-Net-4ch F1, FHR MAE. This supports or kills the ">90% across all subjects" statement and the "93.00% +- 2.35%" interval.

### C-04 SNR trend is non-monotonic
Table: 0 dB 93.68%, 3 dB 91.95%, 6 dB 92.73%, 9 dB 91.40%, 12 dB 95.22%. A 0 dB tier beating 3/6/9 dB is suspicious. **Check:** file-name parsing of SNR tags (for example `snr00dB`, `snr03dB`), how the five conditions are balanced within each SNR tier, and whether detector thresholds adapt to noise. Add a paired comparison per subject and condition.

### C-05 Matching and alignment details
Confirm in the evaluation code: one-to-one beat matching within +-50 ms (a TP must consume exactly one reference beat), exclusion of start-up transients (filter settling, first covariance window), and application of the filter group-delay compensation. Print a histogram of (detected - reference) time offsets per method. A mis-compensated delay of 96 ms would zero F1 under a 50 ms tolerance, so alignment must be demonstrated.

### C-06 U-Net training and evaluation details
- State the input channels (1-ch vs 4-ch are used inconsistently across tables), normalisation, window length and overlap (5 s non-overlapping), how outputs are stitched, early-stopping criterion (a fixed 50 epochs is stated, but sub08 is for early stopping), seeds, and the number of repeats.
- The loss `0.1*||f - f_hat||_1` should be a mean, not a sum over 1,250 samples, otherwise the weighting differs from what the equation suggests.
- Verify the parameter count with `sum(p.numel() for p in model.parameters())` (1,417,073 stated).
- A U-Net that needs the fetal reference to train is supervised; say so, and note that the PCA needs none.

### C-07 Fixed-point model code
Open `src/fixed_point_model.py` and check: rounding is half-even if you claim it (`np.round` is half-even; `floor(x+0.5)` is half-up); saturation bounds; accumulator width and rounding order; that the model covers the whole chain (notch, SOS, beamformer, derivative), not just the beamformer; that SQNR is computed per stage and per vector set; that the 5,000 vectors include saturation cases. Then make the paper equations match the code.

### C-08 Reproducibility and file paths
- "frozen 35-run" vs 36 rows (E-14); `code/results/metrics.csv` vs `results/mega_benchmark_results.csv` (two different roots). Use one results root.
- Add `make reproduce` (or a single script) that runs the benchmark, regenerates Tables 3-5, regenerates `numbers.tex`, and re-draws all figures from the CSVs (no hand-edited plots).
- The flier requires submitting the code with the mid-term report. State the exact submission artefact (zip name or private repo) and make sure it is attached.
- `src/methods/` is described as holding "all six algorithms" but there are 7-9 methods.

### C-09 Missing experiments referred to in the text
See E-15. Add runners such as `src/run_nlms_thoracic.py`, `src/run_adaptive_cov.py`, `src/run_lead_sweep.py` and tables for each, or remove the claims.

### C-10 Data-size arithmetic
33.4 GB for 250 records x 75,000 samples x 34 leads is **52 bytes per sample**; float64 would give about 5.1 GB and float32 about 2.6 GB. Recompute from the actual on-disk files, or drop GB figures. Also, M6 says the U-Net was "trained over 33.4 GB" while Sec. 4 says the training partition is 23.3 GB.

---

## 6. Graphical errors and figure fixes

| ID | Figure/Table | Problem | Fix |
|---|---|---|---|
| G-01 | Fig. 1 | Maternal/fetal 25x and relative bars use peak amplitude; the rest of the paper uses RMS/FMR | Add a note or a second panel with RMS; keep units consistent (E-07) |
| G-02 | Fig. 2 | Caption describes notch filter and polarity-aligned PCA; figure shows a maternal QRS block feeding PCA and no notch; "4-Ch" input while several methods use 1 channel | Redraw figure to match caption and the real pipeline; show which blocks are host vs FPGA |
| G-03 | Fig. 3 | x-axis is 0-33 (0-based) while the text uses channels 1-34 (Lead 27, thoracic 33-34). The tallest FMR bar looks to be near index ~17, not 27, and the axis reaches only about 0.5 while the text says FMR = 0.54 (VERIFY on the full-resolution figure) | Use one indexing convention everywhere, annotate lead 27 and the 4-lead subset on the plot, make the 0.54 value visible, enlarge fonts |
| G-04 | Fig. 4 | Legend shows HPF 0.5 Hz, Notch 50 Hz, BPF 1-100 Hz, QRS BPF 8-30 Hz; caption says 0.5-40 Hz Butterworth with >14 dB at 60 Hz (E-11) | Plot the real 0.5-40 Hz filter, notch separately, annotate 0.1 Hz and 60 Hz points |
| G-05 | Fig. 5 | Caption says bound and simulation "agree", but the simulated null depth saturates near 85 dB; "Target Hardware (15, ~16)" label is ambiguous (B=16 including sign) | Fix caption; explain saturation; unify B definition (T-07) |
| G-06 | Fig. 6 | Legend overlaps the TC4/TC5 bars and their value labels; caption says "six architectures" but seven are shown; U-Net in-sample (sub01) bars are presented as comparable | Move legend outside, fix count, add an "in-sample" hatch or footnote |
| G-07 | Fig. 7 | (a) caption says PCA has sub-bpm error but PCA is 8.42 bpm on TC4; (b) caption limits [-1.96,+1.96] bpm contradict the plotted limits (about -6.75 / +5.9 bpm); tiny fonts | Fix captions to match plot numbers; enlarge fonts (E-05) |
| G-08 | Fig. 8 | Legend overlaps data at 12 dB; "100% down to 0 dB" and "<24%" not exactly true | Move legend; use exact numbers |
| G-09 | Fig. 9 | Caption "confirm Spatial PCA and Deep U-Net dominance" while U-Net is in-sample on sub01 | Mark U-Net as in-sample or replace with a held-out subject |
| G-10 | Fig. 11 | Text says 8-34 leads "plateau 90-93.4%", but panel A appears to show one curve collapsing at the largest lead counts (VERIFY); the single-lead "Spatial PCA" is undefined (C=1 has no v2) | Explain the collapse or fix the plot; call the 1-lead case "raw lead" |
| G-11 | Fig. 12 | Caption says "distributions" but the figure is a bar chart with mean +- 1 SD, while the paper otherwise reports 95% CIs | Replace with box/violin plots or fix the caption; use CIs consistently |
| G-12 | Fig. 14 | x-axis labels c2 as "(Mod Noise)", text says c2 is heart-rate dynamics | Fix label |
| G-13 | Fig. 16 | v3 labelled "Mat. Y-loop" but text says noise; "4 components capture 100%" is a tautology (T-01, T-03) | Fix labels and statement |
| G-14 | Fig. 19, Fig. 20, Fig. 21 | Fig. 19 labels overlap (Vivek / Template Sub.); Fig. 20 legend overlaps an axis label and the normalisation of each axis is not defined; Fig. 21 unit problem (E-06) | Separate labels, define radar normalisation, fix units |

General: several figures (3, 7, 11, 18) have unreadable fonts at print size. Use at least 7-8 pt text after scaling, export vector PDF, and use one colour per method across all figures (Fig. 6, 8, 9, 13, 14 currently differ).

---

## 7. References and citations

| ID | Item | Problem / action |
|---|---|---|
| R-01 | [17] Andreotti et al. 2016 | Author list in the bibliography looks wrong (it lists "F. Grasser, F. Behar" etc.). As I recall the authors are Andreotti, Behar, Zaunseder, Oster and Clifford. Check the paper page and fix. |
| R-02 | [11] Kanjilal et al. | Middle author is Palit, not "Palguna" (as I recall; check). |
| R-03 | [13] Sameni et al. 2007 | This is the Bayesian ECG denoising paper, but the text cites it for the 3-D dipole volume-conductor/vectorcardiogram model. Cite the model's real source (for example the FECGSYN/Behar/Andreotti simulator papers) or change the sentence. |
| R-04 | [20] Lee et al., [21] Zhong et al. | [20] is titled "single-channel", but R6 attributes "> 90% (4-Ch)" and "82.3% 1-Ch" to [20]/[21]. Open both papers, confirm they exist, and copy the actual reported numbers with their metric definition. If you cannot verify, remove R6's "reproduces Lee et al." wording. |
| R-05 | [14] Cardoso, [9] Agostinelli, [22] Ahlstrom | JADE originates from Cardoso & Souloumiac; check [14] supports the sentence. Verify [9] (title, venue, pages). Ahlstrom & Tompkins is about real-time ECG digital filters; "matches Ahlstrom exactly" (R1) is not a literature replication of a published number. |
| R-06 | Uncited entries | [18] NIFEADB, [25] Pan-Tompkins, [26] Haykin, [27] Zarzoso & Nandi, [28] Kher, [29] board manual are in the bibliography but never cited in the text (no back-reference pages). Cite them where used (Pan-Tompkins for the detector, Zarzoso & Nandi for BSS vs ANC) or remove them. |

Also: Sec. 14 should explicitly say which parts are *new* since the preliminary report (the flier asks for "a summary of any further literature review"). Team 22 does this with a separate "Further literature review" subsection and a reference audit.

Replication scorecard (Sec. 15, Table 7): adopt Team 22's rule that "reproduced" is declared only when a number or functional form **stated in the source** is matched within a stated tolerance. Currently R1 (filter), R3 (subspace principle), R4 (LMS failure) and R7 have no published number being compared. R5 compares to "about 78% at 12 dB, <35% at 0 dB" without a quoted table/figure. Mark such items "partially/not replicated" and give the exact source location (table/figure/page) for every published number.

---

## 8. Writing and format

- **W-01:** The abstract is far too long (about 400 words of dense numbers, repeated in Sec. 1 "contributions"). Cut to about 150-200 words: problem, method, 3 headline numbers (with the correct partition), hardware status, honest limits.
- **W-02:** Define terms once: "frozen benchmark", "TC1-TC5", "PPR-8" (rename detector), L1-L5.
- **W-03:** Team 22 has a "How to read this report" paragraph (black = preliminary text, blue = new). Add one for MTR-8 if you keep blue text for new content.
- **W-04:** Floats split sentences across pages (for example Sec. 10.3 list continues after Tables 3-5). Place floats at section boundaries.
- **W-05:** Replace "Verified/Target Sized/Estimated" status words with one consistent vocabulary: Measured (L1-L5), Estimated (analytic), Planned.
- **W-06:** Remove promotional wording ("rock-solid", "optimal", "proving", "fully preserving") and keep it factual.

---

## 9. What to copy from Team 22 (structure, not content)

1. **Honest validation ledger:** every number tagged by level, and a statement that L4/L5 do not exist yet. Team 8 already uses tags but then labels estimates "Verified".
2. **Register of changes with the original wording** of each corrected sentence (Team 22 Sec. 18), including corrections to their own earlier claims. Team 8's register lists upgrades but not corrections.
3. **Frozen seeds/pilot vs final split** and a log of every change after freezing.
4. **Replication scorecard with tolerances** and verdicts such as "Partly" and "Not replicated" (Team 22 Table 13).
5. **Reference audit** (what was confirmed at record level vs full text).
6. **Theory model that predicts the measured result** with no fitted constant (their S* ~ 0.085/mu law). A PCA analogue would be a predicted F1-vs-SNR/leak relationship from the eigen-spectrum, checked against measurements.
7. **RTL already bit-exact against the fixed-point model** in simulation. Team 8 should reach this by the final report.
8. **Risk table** with status per risk (their Table 14).
9. **Open-items list** carried to the final report, including things they could not explain.
10. **AI disclosure** that names which code, text and figures were AI-generated and what the team verified (Sec. 19).

---

## 10. Suggested replacement text (use after fixing the numbers)

**Abstract skeleton (fill in numbers from `numbers.tex`):**
> Non-invasive fetal ECG (NIFECG) extraction is hard because the maternal ECG is much larger than the fetal ECG and the two spectra overlap. We study a 4-lead spatial-subspace beamformer (second principal component of a 3 s sliding covariance) on the PhysioNet FECGSYNDB (10 subjects, 250 records). On held-out subjects sub09-sub10 it reaches F1 = `\pcaFoneTest`% (FHR MAE `\pcaMaeTest` bpm); averaged over all 250 records it reaches `\pcaFoneAll`% (95% subject-clustered CI [`\lo`, `\hi`], df = 9). A supervised 1-D U-Net reaches `\unetFoneLoso`% under leave-one-subject-out evaluation. A bit-true Q1.15 model of the filter and beamformer chain gives SQNR of `\sqnr` dB over `\nvec` golden vectors. A time-multiplexed single-DSP design is sized at `\cycles` cycles per sample (analytic estimate, not yet synthesised). RTL, synthesis and board results are planned for the final report.

**Latency statement for Table 1 (replace "3.28 us"):**
> Per-sample compute time: `\cycles` cycles = `\us` us at 100 MHz (margin x`\margin` against the 4 ms sample period). Algorithmic latency: filter group delay (`\gd` ms, see Fig. 4), plus a 3 s covariance window at start-up, plus a 5-beat median (about 2 s). The 100 ms alarm target is therefore *not* met by the full chain; it applies to the beat-to-beat detector output only.

**Status sentence (use consistently):**
> Level L3 (RTL): the SOS filter and 4-MAC beamformer modules are coded and under test in simulation; the remaining modules are scheduled for 26-31 Oct. No synthesis (L4) or board (L5) result exists.

(Adjust the L3 sentence to whatever is actually true on the day.)

---

## 11. Consistency checker to create (`tools/check_consistency.py`)

Adapt column names to your CSV. The goal is that Table 4, the CI numbers and the partition counts are recomputed from data, never typed.

```python
import pandas as pd, numpy as np
from scipy import stats

# --- Table 4 from Table 3 (per-TC results for sub01) ---
t3 = pd.read_csv("code/results/metrics.csv")  # columns assumed: tc, method, f1, mae, agr, corr
t4 = t3.groupby("method")[["f1", "mae", "agr", "corr"]].mean().round(3)
print(t4)  # compare with the paper's Table 4, any mismatch > 0.01 is an error

# --- Population CI (clustered by subject) ---
pop = pd.read_csv("results/mega_benchmark_results.csv")  # assumed: subject, method, f1, partition
def clustered_ci(df, method):
    m = df[df.method == method].groupby("subject").f1.mean()
    n = len(m)
    h = stats.t.ppf(0.975, n - 1) * m.std(ddof=1) / np.sqrt(n)
    return m.mean(), m.mean() - h, m.mean() + h, n

def run_level_halfwidth(df, method):
    x = df[df.method == method].f1
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)), x.std(ddof=1) / np.sqrt(len(x))  # (CI half-width, SE)

for meth in pop.method.unique():
    print(meth, clustered_ci(pop, meth), run_level_halfwidth(pop, meth))

# --- Partition-specific numbers (E-02, E-03) ---
for part in ["train", "val", "test"]:
    sub = pop[pop.partition == part]
    print(part, sub.groupby("method").f1.mean().round(2).to_dict())

# --- Partition invariance (paper Eq. 22-23) ---
print(pop.groupby("condition").f1.mean().mean(), pop.groupby("snr").f1.mean().mean())

# --- Row count checks (E-14) ---
print("Table 3 rows:", len(t3), "(paper claims 35-run benchmark)")
```

Also add checks that: the number of records is 250 (10 x 5 x 5), windows per partition are 10,500 / 1,500 / 3,000, `TP + FP == Det` and `TP + FN == Ref` for every Table 3 row (they currently all pass; keep it that way), and the U-Net parameter count equals 1,417,073.

---

## 12. Final checklist before submission

- [ ] Table 4 regenerated from CSV; all E-01 mismatches gone
- [ ] One partition label for every U-Net and PCA number; CI df matches number of clusters
- [ ] "SE" renamed or corrected everywhere
- [ ] FHR MAE/agreement recomputed with one function; Fig. 7 captions match plots
- [ ] Runtime table unified (unit, hardware, warm-up) and Fig. 21 caption fixed
- [ ] Amplitude ratios and FMR explained consistently
- [ ] Q1.15 full-scale mapping stated; LSB in uV correct
- [ ] Latency split into compute time and algorithmic latency; UART timing corrected
- [ ] Filter order, SOS count, Fig. 4, group delay, coefficient Q-format fixed
- [ ] Cycle schedule recounted; resource table consistent with the recount
- [ ] Covariance/eigen/polarity/lead selection placement (host or FPGA) stated
- [ ] L3 status, BRAM count, switch presets, Fig. 2 all consistent
- [ ] Method list, row counts and names consistent (35 vs 36, 6/7/9)
- [ ] Every unsupported number has a table/script or is removed
- [ ] Standards, "clinical requirement" wording fixed; citations corrected (R-01..R-06)
- [ ] Names removed; AI disclosure rewritten with per-part detail and citations
- [ ] Code package attached and reproducible with one command
- [ ] Final PDF re-read once end-to-end for numbers that appear in more than one place (abstract, Sec. 1, tables, captions, Sec. 17, Sec. 19, register)
