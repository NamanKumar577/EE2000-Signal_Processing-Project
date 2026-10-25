# MTR #0008 (Fetal ECG on FPGA): Comparison with MTR #22 and Improvement Plan

Compared against: the EE2000 course flier (rules) and MTR #22 (LMS tracking on the Boolean Board), used as a reference for structure and rigor.
Date of review: 25 Oct 2026. Mid-term is due today; the final report is due **13 Nov 2026**.

How to read this: items marked **[TONIGHT]** can be fixed in the text or in a re-submit today. Items marked **[FINAL]** need new work before 13.11. Where I read a number off a figure rather than a table, I wrote *(fig)*. Please re-check every number against your own logs. Several are wrong, as shown in section 3.

---

## 0. Executive summary

**Strengths of #0008:** broad benchmark (250 records, 2,250 runs, 9 methods), standard metrics (F1 with ±50 ms tolerance), a clear hardware story (4 MACs, 1 DSP), good Pareto/heatmap figures, and a clean contributions list.

**The five problems that will cost the most marks:**

1. **No AI-usage disclosure at all.** The flier requires you to clearly indicate AI-generated parts and cite the tool. #22 has a full Sec. 19 and cites Claude as ref [37]. #0008 has nothing. This is a rules violation, and you must also be able to defend everything at the viva.
2. **"Results replicated from the literature" is essentially missing.** The flier lists it as a mid-term component. #22 has a dedicated Sec. 15 with 7 replications and a scorecard. #0008 has one sentence saying it "replicated key algorithms", with no comparison to any published number.
3. **Literature review is thin.** There are 10 references, and [6], [7], [9] and [10] are never cited in the text. The "Extended Literature Survey" is two paragraphs (U-Net, SWT). #22 has 37 references plus a reference audit.
4. **The headline claims are not safe, and several look contaminated or overstated:**
   - The U-Net was "trained on 33.4 GB (1,500 recordings)". The whole FECGSYNDB is **33.3 GB** (1,750 signals), so you very likely trained on the records you test on.
   - "As synthesized" and "830 LUTs / 1 DSP" are estimates. Your own Sec. 7 says RTL and synthesis are still to be done.
   - The chosen hardware design (Spatial PCA) has no fixed-point verification. The +85 dB SQNR belongs to the SVD model, which scores about 35% F1.
5. **No code submission is mentioned.** The flier says any code developed or experimented with must be submitted at mid-term. #22 refers to a code package, logs and seeds.

Numerical inconsistencies are listed in section 3. Those alone can embarrass you in a viva, so fix them first.

---

## 1. Rules checklist (from the flier)

| Requirement | #22 | #0008 | Action |
|---|---|---|---|
| IEEE CVF template | Yes | Yes | OK |
| Four-member team | Yes | Yes, four named | OK |
| Summary of **further literature review** (mid-term) | Sec. 14.7, 14.8: 37 refs, reading depth stated, reference audit | Sec. 3: 2 short paragraphs, 1 new reference ([8]) | **[TONIGHT]** expand (Sec. 5 below) |
| **Results replicated from the literature** | Sec. 15: R1–R7, scorecard (reproduced / partly / not) | Not present | **[TONIGHT]** add a replication table; **[FINAL]** run real replications |
| **Preliminary results** from your work | P1–P6 at L1/L2/L3, labelled by validation level | Large benchmark, but possible leakage and numeric inconsistencies | **[TONIGHT]** fix the numbers; **[FINAL]** rerun with a proper split |
| **Any code must be submitted** | Code package, logs, seeds | Not mentioned | **[TONIGHT]** zip with README and submit; cite it in the report |
| Builds on the preliminary report | Register of changes R-1 to R-27 | Only the abstract says "initially proposed LMS and template subtraction" | **[TONIGHT]** add a "Changes since the preliminary report" table |
| **AI policy**: indicate AI-generated parts, cite, be able to defend | Sec. 19, detailed, honest, with reference | **Missing** | **[TONIGHT]** add a section |
| Final: algorithm, results, conclusions, code, per-member work, commented code | n/a yet | Sec. 7 gives roles | **[FINAL]** per-member contribution table and commenting |
| Presentation on the **Boolean Board** | Sec. 8, Table 6 (switches, buttons, LEDs, 7-seg, UART) and Sec. 16 (demo script) | No board-demo plan; mentions Artix-7 and Kria/Edge NPU | **[TONIGHT]** add the board plan; **[FINAL]** build it |

**Anonymity check:** the review copy is anonymous, yet #0008 names Naman, Vivek, Anshu Ram and Astitva in the text (Secs. 4.3–4.5, 7). #22 says "a team member". Ask the TA whether names are allowed. If not, use Member A/B/C/D until the final report, where the flier requires per-member delineation.

---

## 2. What #22 does that #0008 should copy

1. **Validation levels on every number.** L1 floating point, L2 bit-true fixed point, L3 RTL simulation, L4 synthesis, L5 board. #22 states "L4/L5 do not exist yet". Do the same. Tag each table caption.
2. **Register of changes** from the preliminary report, with reasons and IDs.
3. **Colour discipline.** Black is the old text, blue is new, so the grader sees the delta.
4. **Replication scorecard** with honest verdicts (reproduced, partly, not replicated), including assumptions you had to make.
5. **Oracle and baseline bounds.** #22 compares against an oracle (the best possible filter) and against the do-nothing receivers. For you, an oracle spatial filter (best linear combination using ground-truth fetal ECG) and a "raw mixture / best single lead" floor are the equivalents.
6. **Seed discipline and parameter freezing.** Pilot seeds choose parameters, then the parameters are frozen, then you test on untouched seeds. This is the cure for your leakage risk.
7. **Statistics.** Many seeds, bootstrap CIs, "inconclusive" is allowed as a verdict. #0008 reports means with no CIs.
8. **A theory section with falsifiable predictions** (#22 Sec. 12). #0008 has almost no theory. See section 6.
9. **Risk table with status** (Table 14), **open-items list**, and **scope and validation status** section.
10. **Cautious claims.** "To the best of our knowledge", "first or novel is not claimed". #0008 uses "conclusive", "flawlessly", "fully establishing", "proving", "optimum clinical sensor configuration".
11. **Demo section** (Sec. 16) where the key result is visible on the board, with presets chosen from the results.
12. **Independent re-implementation cross-checks** and a reference audit.

---

## 3. Numerical and factual audit of #0008 (fix these first) **[TONIGHT]**

### 3.1 Table 2 averages do not match Table 1 / Fig. 7

I recomputed from your own tables:

| Method | Table 2 "Avg F1" | Recomputed from Table 1 (TC1–TC5) | Comment |
|---|---|---|---|
| Spatial PCA | 92.15 | 92.15 | OK |
| Deep U-Net | 98.59 | 98.59 | OK |
| Vivek hybrid | 39.64 | 39.64 | OK |
| Template Sub (Fixed) | **35.59** | **39.06** | mismatch |
| SVD V1 (Naman) | **35.44** | **38.95** | mismatch |
| MC Template Fusion | **79.02** (min 52.10, max 99.01) | **69.78** *(fig)* from heatmap 97.8 / 94.1 / 31.4 / 58.6 / 67.0 | mismatch; heatmap min is 31.4, not 52.10, and TC1 is 97.8 in Fig. 7 vs 99.01 in Table 1 |
| SWT-LMS | **15.47** | **about 16.97** *(fig)* (TC4 18.5 in heatmap) | mismatch; the text also says "only 15.06%", which is the TC1 value |

Fix: regenerate Tables 1, 2, Fig. 5 and Fig. 7 from one results file with one script. Never type numbers by hand.

### 3.2 Table 1 gaps
- TC3 Spatial PCA: Det = 716 but TP + FP = 715.
- TC4 and TC5 omit MC Template Fusion and SWT-LMS rows, but both appear in Fig. 5/7 and Table 2. Show all methods for all cases, or say clearly which are omitted and why.
- SVD Variant 1 and Template Subtraction have **identical** TP/FP/FN at TC1 (546/168/170) and identical correlation (0.270). A rank-1/2 SVD of fixed-period aligned beats is mathematically close to template subtraction, so these are probably not independent methods. "Six distinct paradigms" is therefore overstated (about four). SVD V2 results are never shown, and V3 appears on TC3 only.

### 3.3 Spatial PCA correlation is negative
Table 3 gives Spatial PCA correlation **−0.135** while Table 2 gives 0.909 and the abstract highlights U-Net's 0.982. A PCA component has an arbitrary sign, so correlations must be taken on the sign-aligned (or absolute) waveform. Report it that way and explain it. As written, it looks like PCA does not recover the waveform.

### 3.4 Dataset facts that disagree with PhysioNet's documentation
I checked the FECGSYNDB page (Andreotti et al., Physiol. Meas. 2016):

- Channels **1–32 are abdominal; channels 33–34 are maternal reference ECG.** Your text says "thoracic leads (Channels 32–34) exhibit negligible fetal content". Channel 32 is abdominal. Fix, and cite the dataset documentation.
- Case definitions: c0 = baseline + noise, c1 = fetal movement, c2 = **HR accelerations/decelerations**, c3 = uterine contraction, c4 = **ectopic beats (mother and fetus)**, c5 = twin pregnancy. Your Fig. 12 caption says "c2: moderate noise" and c4 as "arrhythmia". Correct the labels.
- The database has **5 repetitions** per condition (1,750 signals). Your "250 records" uses one repetition of five conditions (10 × 5 × 5 × 1). You could report all 1,250 (c0–c4) or add c5. Say plainly which subset you used.
- Cite the dataset paper (Andreotti et al. 2016) and the PhysioNet standard citation. Currently only a URL is given.
- There is a "baseline" without noise, useful as an upper-bound test.

### 3.5 U-Net training data likely overlaps the test data (critical)
You state training on "33.4 GB (1,500 recordings)". The whole database is 33.3 GB and 1,750 signals (10 subjects × 6 cases × 5 SNR × 5 reps = 1,500 for c0–c5). Unless you held out subjects, the TC1–TC5 results and the 250-record mega-benchmark are test-on-train.

The pattern in your own numbers fits this:
- 1-channel U-Net: 98.59% on the five hand-picked cases but **80.79%** on the full matrix.
- The 4-channel U-Net's minimum F1 is 27.16%.

Fix **[FINAL]**: train on subjects 01–07, validate on 08, test on 09–10 (or leave-one-subject-out), and report test-only numbers. **[TONIGHT]**: state exactly what the split was. If there was no split, say so honestly in the Limitations section and relabel the U-Net numbers as "training-set performance".

### 3.6 Same issue for the PCA weights and the 4-lead choice
- The PCA weight vector appears to be computed from the **whole 5-minute record being evaluated** (transductive, non-causal). That is not what a real-time FPGA does. Report a causal version: weights estimated from the first N seconds, or a rolling window, then applied to later data. Report time-to-lock.
- The 4-lead subarray [27, 26, 28, 25] was picked using FMR computed with **ground-truth** fetal and maternal signals, probably on the same data you evaluate on. Say which subject(s) Fig. 3 uses. Since fetal position differs by subject (your own Fig. 13 caption mentions "diverse lead orientations"), show whether the best leads vary per subject. A fixed array is only an "optimum clinical configuration" if it generalizes across subjects, and you need a rule to choose leads without ground truth.

### 3.7 Hardware claims
- "As synthesized in Tab. 4" and abstract "< 3% of FPGA resources (1 DSP48E1, 830 LUTs)": Sec. 7 says RTL and synthesis are remaining work. Relabel as estimates (L1/L2) or run Vivado before the final.
- The headline "+85.04 dB SQNR, zero beat degradation" is the **SVD model**, not the chosen Spatial PCA. The abstract implies the whole system is verified. Run a Q1.15 model for the beamformer plus Butterworth plus detector.
- Latency inconsistency: 4 MAC cycles = 0.08 µs (50 MHz), but Table 4 and the abstract say 3.28 µs. Explain what the extra cycles are (filters, detector pipeline).
- "1 DSP" for a 4-channel pipeline that includes four IIR filters: possible only with heavy time-multiplexing. Show the schedule. Report a per-module budget (Butterworth, beamformer, maternal detect, PPR-8, FHR, UART).
- Table 4 title mentions Artix-7 XC7A35T, but percentages are Spartan-7 XC7S50 ones. XC7A35T has different totals. Remove or recompute.
- 50 MHz clock: the Boolean Board's clock is 100 MHz (as #22 uses). Confirm in the board manual.
- Unsourced "32 mW", "Spartan-7 (13%)" etc. Say how these were obtained (Vivado power report?), or remove.
- "Completely avoiding iterative matrix inversions": you still need an eigen-decomposition to **get** the weights. Say where the weights come from on hardware (offline calibration vs on-chip).

### 3.8 Filter claims
- Sec. 2 says the 4th-order 0.5–40 Hz filter gives ">35 dB at 60 Hz". A 4th-order Butterworth low-pass at 40 Hz gives only about 14 dB at 60 Hz (8th-order: about 28 dB). Compute attenuation from the actual coefficients.
- Fig. 4's caption is about the 0.5–40 Hz Butterworth, but the legend shows other filters (HPF 0.5 Hz, Notch 50 Hz, BPF 1–100 Hz, QRS BPF 8–30 Hz) and there is no phase plot.
- The simulated dataset has no mains component as far as I can tell; powerline at 60 Hz (the text) vs 50 Hz (the legend, and the usual mains in India) is inconsistent.
- State whether software used zero-phase `filtfilt` (non-causal) while hardware must be causal. The causal filter delays and distorts QRS.

### 3.9 Smaller factual issues
- Sec. 1: "MECG 5–25× larger (≈20–100 µV vs ≈1–5 mV)": the quoted ranges give 10–250×, and the order is reversed. Fig. 1 shows 25×. Make text and figure agree, and cite or measure it from the data. The bars for "noise 0.15" and "baseline wander 0.08" look illustrative, so label them so or measure them.
- "Completely ruling out standard linear frequency filtering": too strong. Your own hybrid uses an 8–38 Hz subband.
- Eq. (2) uses **a_m** and **b_f** (vectors) while Eq. (1) defines scalars a_i and b_i. Unify notation.
- Sec. 5.2: "1 channel Spatial PCA yields 20.6–35.8%": PCA on one channel is the identity operation. This is trivial, so present it as "no spatial processing" rather than a PCA result.
- Table 3: U-Net 4-ch speed 98.6 ms vs 82 ms in Table 1, PCA 190.7 ms vs 0.003 s in Table 1 and 3 ms in Fig. 17. Explain (the 3 ms likely excludes the PCA estimation). The "100,000× faster than real time" claim holds only for the inner-product part.
- Sec. 4 lacks a "4.1 Method 1" heading (Methods start at 4.1 = Method 2). Number the methods consistently.
- Fig. 2's caption mentions UART output but the figure box says "FHR Estimation & Output". Align.
- Several figures are unreadable at print size (Figs. 3, 4, 9, 12, 13, 16). Fig. 5's legend hides bar labels at TC4/TC5, Fig. 14 has overlapping labels, and Fig. 15's legend covers an axis label.
- The abstract is about 400 words. Aim for 150–250 and move detail to the body.

---

## 4. Scientific and methodological gaps

### 4.1 Are the baselines strawmen?
Single-channel template subtraction giving **76% F1 at 12 dB on the baseline case** (TC1, ~160 false positives and ~160 misses) cannot be explained by QRS collisions alone, since collisions affect a minority of beats. It suggests under-tuned templates, jitter in maternal R-peak alignment, no template scaling per beat, or the PPR-8 detector counting maternal residue as fetal peaks. Your central claim is that collisions break temporal subtraction. Prove it:

- Split beats into collision vs non-collision (|maternal R − fetal R| below some threshold) and report F1 for each. If non-collision beats are also failing, the baseline is the problem.
- Add standard baselines at their best: adaptive template with per-beat scaling and time-warping, tsPCA (Kanjilal-style), proper ANC with the **maternal reference channels 33–34** (see next point).
- Give baselines the **same 4 channels** where applicable, so the comparison to a 4-channel beamformer is fair. Right now 4 channels vs 1 channel is the main difference.

### 4.2 SWT-LMS failure is an experimental setup choice
You explain 15% F1 as "abdominal mixtures lack a dedicated maternal reference lead". But FECGSYNDB **provides two maternal reference channels (33, 34)**. Classic adaptive noise cancellation (Widrow et al., 1975) uses exactly that reference. Run it as designed. #22's theory also gives tools to diagnose LMS: step size versus misadjustment, accumulator width, stalling. At the moment this baseline reflects a wrong configuration, not a property of LMS.

### 4.3 Missing standard multichannel baselines
Add at least FastICA/JADE and a standard PCA/tsPCA multi-channel method. Without ICA you cannot claim spatial beamforming is better than the field's standard blind separation. FECGSYN's own framework papers benchmarked such methods on this same dataset, so you can compare to published numbers (this doubles as your replication, section 5).

### 4.4 Evaluation metrics are incomplete
- **FHR accuracy is never reported**, although the abstract and Fig. 2 are about FHR estimation. Add MAE and RMSE in bpm, % of time within ±5 bpm, Bland–Altman plot, and time to first valid FHR.
- Report F1 **with confidence intervals** per condition and per SNR (mean ± 95% CI over subjects and repetitions), plus box plots. Fig. 10 error bars cross 100%.
- Worst-case analysis: Table 3 shows min F1 59.55% (PCA) and 27.16% (U-Net 4-ch). Which subject, condition and SNR? Show and explain.
- Report SNR improvement of the extracted waveform (output SNR vs ground-truth fetal ECG), sign-aligned correlation, and ideally fetal-QRS timing jitter.
- Define **PPR-8** (what the detector is, thresholds, refractory period, any dependence on maternal annotations). It is never explained. Likewise the maternal QRS detector. Confirm that no algorithm uses the ground-truth annotations.
- Say how the 250 records' ground truth (.qrs) was used and what the ±50 ms rule is based on.

### 4.5 All data is synthetic
Everything is on a simulator. Add at least a small test on real data, for example the PhysioNet/CinC Challenge 2013 set, the NIFEADB you already list as [10] (but never use), or the Abdominal and Direct Fetal ECG database (4 abdominal channels with scalp reference; verify channel count and sampling rate before use). Real recordings need resampling to 250 Hz. Even a few records plus a clear statement of the sim-to-real gap improves credibility.

### 4.6 Motion case (c1) failure is the interesting finding
PCA drops to 72.79% on fetal movement because the spatial mixing changes with time while your weights are static. That is the same phenomenon #22 studies (a time-varying channel and a tracking boundary). Make it a result:
- Block-adaptive weights (update every N seconds), or a recursive/Oja-style update, and plot F1 against update interval and movement rate.
- Hardware budget: at 250 Hz and 100 MHz you have about **400,000 clock cycles per sample**. Your "3.28 µs" design uses a tiny fraction. You can afford on-chip adaptation (rolling covariance, power iteration, sign-LMS), which also answers "where do the weights come from?".

### 4.7 Why four channels?
Your saturation at ~4 leads fits a theory argument that you do not make: the maternal heart is not a fixed dipole. Its vectorcardiogram loop rotates over a cardiac cycle, so the maternal contribution spans up to about 3 spatial dimensions, plus 1 for the fetal source, so about 4 channels are needed. Show the singular-value / explained-variance spectrum of the 4-channel and 8-channel data, and test it. It also exposes a gap: with 4 channels, nulling a rank-3 maternal subspace leaves a 1-D remainder. Why is the fetal signal in **PC2** (w = v2)? Show this (the explained-variance plot) and how you pick the component without ground truth. If v1 is nulled but the maternal T-wave and P-wave directions differ, v2 can still contain maternal energy. Compare with projecting out the top-k maternal components.

### 4.8 Ablations that are missing
- 1 vs 2 vs 3 vs 4 vs 8 vs 34 channels is partly done (Fig. 9). Add random lead subsets vs your chosen subset.
- Preprocessing on/off; causal vs zero-phase.
- Detector comparison (PPR-8 vs Pan–Tompkins-style).
- Oracle spatial filter (best linear weights with ground truth) to show how close PCA is to the optimum.
- Noise-type breakdown (the simulator separates noise sources).

### 4.9 Fixed-point work to add **[FINAL]**
You only test one Q format (Q1.15). #22's best result is a **word-length sweep** against performance and resources. Do the same:
- F1 and FHR error vs input bits, weight bits and accumulator bits (for example 6–16 bits).
- Theory: weight quantization limits the **maternal null depth** (residual ≈ quantization error × maternal amplitude, which is 10–250× larger than the fetal signal). Predict the needed bits, then verify. This is your equivalent of #22's accumulator-width finding.
- Report overflow and saturation counts on all four channels and for the IIR sections (IIR coefficient quantization at 0.5 Hz with fs = 250 Hz is delicate; use SOS and state the Q formats).
- Include the maternal-QRS detector, PPR-8 detector and FHR computation (needs a reciprocal or divider, or a lookup) in the bit-accurate model.

### 4.10 U-Net on the Boolean Board
Your own numbers: 1,417,073 parameters at 8 bits is about **1.42 MB**; the XC7S50 has about **337 kB** of block RAM (as #22 also states). That is about **4.2× too large** before activations. State that the U-Net runs off-board (host/GPU) as a software reference, or build a compact quantized 1D CNN (for example under 100k parameters at 8 bits) that fits. Do not list "Edge NPU / Kria" as the FPGA-viability for a project that must demo on the Boolean Board.

---

## 5. Literature review to add **[TONIGHT: text; FINAL: depth]**

Currently [6] Kanjilal and [7] De Lathauwer are listed but never cited in the text, and [9], [10] are bare dataset URLs. Cite every reference where it is used. State the depth you read each source (abstract, full text), as #22 does.

Suggested structure (each cluster 1 short paragraph plus a comparison table: method, channels, data, reported metrics, hardware?):

1. **Reviews and clinical context:** Sameni and Clifford (2010) review of fetal ECG processing; Clifford et al. and Silva et al. on PhysioNet/CinC Challenge 2013.
2. **Adaptive noise cancellation:** Widrow et al. (1975) ANC; LMS/RLS/NLMS variants. #22's references on LMS tracking and fixed-point stalling (Widrow, Haykin, Ghanassi, Shahdoosti) are directly relevant to your LMS baseline.
3. **Template subtraction and SVD/PCA:** Cerutti-type adaptive templates; Callaerts et al. (1990) SVD comparison; Kanjilal et al. (1997) (already your [6]); tsPCA family.
4. **Blind source separation:** De Lathauwer et al. (2000) (your [7]); Zarzoso and Nandi (1999) on BSS vs ANC; ICA (Cardoso JADE, FastICA); Sameni et al. periodic component analysis (πCA).
5. **Benchmark frameworks:** Andreotti et al. (2016) stress-testing framework, which is your dataset's origin; Behar, Oster and Clifford (2014) combining methods.
6. **Deep learning for fetal ECG:** you cite only Ronneberger (2D U-Net). Add 1D/encoder-decoder, CNN-LSTM and W-Net style works on fetal ECG extraction and QRS detection.
7. **Hardware/FPGA implementations of fetal-ECG or ECG processing, and fixed-point word-length design:** survey FPGA/ASIC fetal-ECG work (your "research gap" claim needs this), plus Constantinides et al. (word-length), Xilinx UG479 (DSP48E1), and the board manual.
8. **Detectors:** Pan–Tompkins for maternal QRS; cite the source of PPR-8 or define it yourselves.

**Verify every citation** (title, year, venue) before using it, since I am listing them from memory as search leads. Also state the "position of this work" the careful way #22 does ("to the best of our knowledge, no study combines …; 'first' is not claimed").

---

## 6. Replication section to add (the rules item you are missing) **[TONIGHT: table; FINAL: runs]**

Create "Sec. X: Results replicated from the literature" with a scorecard. Candidate replications, from cheapest to hardest:

| ID | What to replicate | Source | What counts as "reproduced" |
|---|---|---|---|
| R1 | FECGSYNDB reference results (F1 vs SNR / condition) for classic methods (tsPCA, ICA, ANC) | Andreotti et al. 2016 | your F1 within a stated tolerance of the published curve |
| R2 | SVD fetal ECG extraction on abdominal channels | Kanjilal et al. 1997 | separation of maternal and fetal components on a published or simulated example |
| R3 | Blind subspace separation | De Lathauwer et al. 2000 | similar rank and separation behaviour |
| R4 | LMS ANC with maternal reference (the setup you got wrong) | Widrow 1975, Zarzoso and Nandi 1999 | working cancellation with reference input |
| R5 | Real-time filters for ECG | Ahlstrom and Tompkins 1985 (your [1]) | passband and delay match published figures |
| R6 | Pan–Tompkins QRS detector sensitivity/PPV on a standard set | Pan and Tompkins 1985 | within published performance |
| R7 | U-Net result on a published 1D task | the 1D U-Net work you cite | trend reproduced |

Format each like #22: what was rebuilt, the exact numbers you matched, what you had to assume, and a verdict. If a replication fails, say so; #22 counts that as a valid result.

**For tonight**, if you cannot run them, do not claim replications. Write what you ran so far (U-Net, SWT-LMS, SVD), what you compared it with (nothing published yet), and list R1–R7 as planned for the final. An honest "planned" is better than an unsupported "replicated".

---

## 7. Missing sections to add

1. **Changes since the preliminary report** (table: statement, change, reason). The abstract mentions LMS was proposed; say what happened to it.
2. **Applications and requirements:** a short table (CTG/Doppler, scalp electrode, NI-FECG) and target requirements (latency, FHR accuracy, wearable power).
3. **Theory section:**
   - the 4-channel rank argument (4.7);
   - null depth vs weight quantization (4.9);
   - a compute-budget argument (400,000 cycles/sample);
   - explained SNR gain of the beamformer (gain = fetal power through w over maternal power through w).
4. **Detector and FHR definitions:** PPR-8, maternal detector, FHR formula (median of RR? outlier rejection?), refractory period, startup latency.
5. **RTL architecture:** block diagram with data widths, FSM, memory map, UART protocol, clock, per-module resource table, pipeline latency.
6. **Verification plan:** golden vectors (you mention 5,000), testbench, bit-exact comparison against the fixed-point model (#22 shows bit-exact L2 vs L3).
7. **Boolean Board demo plan:**
   - Input: stream 4-channel samples over UART from a PC (about 20 kbit/s needed, about 2.2% of 921,600 baud, which you computed; confirm the board's UART supports it), or store a short snippet in BRAM. A full 5-minute, 4-channel, 16-bit record is 600 kB, which does not fit in 337 kB BRAM, so streaming or a shorter clip is needed.
   - Outputs: LED blink on each fetal QRS, 7-segment display of FHR in bpm, UART return of the beamformed signal and detections for plotting on the PC.
   - Controls: switches select test case/SNR; buttons for reset/start/recalibrate weights; LED colour for "fetal lock / lost".
   - Demo preset list chosen from the results (for example c0 at 12 dB works, c1 motion shows degradation, then block-adaptive recovers).
8. **Risk table** with mitigations and current status (timing, synthesis, board bring-up, weight calibration).
9. **Limitations and threats to validity:** synthetic data only, single dataset, subject split, static weights, no hardware numbers yet, baselines under-tuned.
10. **Open items** carried to the final report.
11. **AI usage disclosure** (see section 8).
12. **Code availability** statement: repo/zip, README, commands to regenerate each table and figure, seeds, Python/package versions, dataset download script.

---

## 8. AI-usage disclosure (required) **[TONIGHT]**

The flier: indicate the parts generated by AI, provide citations, and be able to explain and defend them. Mirror #22's honest style. Be specific. Example structure (edit to match what really happened):

- Which tool and version, and cite it (as #22 does with its ref [37]).
- What it produced: code (which scripts/modules), text, figures, analysis, literature leads, debugging.
- What the team did: chose methods and experiments, ran code, checked numbers, wrote or edited which sections.
- A statement on verification: how outputs were checked (re-runs, independent calculations), and an admission that numbers in this report were found inconsistent and corrected.
- If any text, number or reference came from an AI and was not independently checked, say so or check it now.

Do not claim "no AI-generated content" if it is not true. Remove marketing-style phrasing that an examiner could read as unverified AI wording.

---

## 9. Viva preparation: questions the current report invites

Practice answers to these:

1. Was the U-Net's training data disjoint from the test records? What exactly was the split?
2. How are the PCA weights obtained on the FPGA? Offline or on-chip? What if the fetus moves?
3. Why is the fetal signal in the second principal component? How do you know without ground truth?
4. Why four leads? Why [27, 26, 28, 25]? Would this choice work on a different subject?
5. Why is Spatial PCA correlation negative in Table 3?
6. What does PPR-8 do exactly? Does it use maternal annotations?
7. Why do your averages in Table 2 differ from Table 1?
8. What is "synthesized"? Was Vivado actually run? What was the clock?
9. What does +85.04 dB SQNR refer to, and which design does it apply to?
10. Why does template subtraction fail on a baseline case with only occasional collisions?
11. Why not use the maternal reference channels for LMS?
12. How would the design fit on the Boolean Board, and what does the audience see?
13. What did the AI write, and can you re-derive it?

---

## 10. Suggested plan for 25 Oct to 13 Nov

**Tonight (25 Oct), in this order:**
1. Fix the numbers (section 3.1–3.4, 3.7 labels): regenerate tables and figures from one results file.
2. Add the AI-usage disclosure (section 8).
3. Relabel "synthesized" results as estimates and add validation levels L1–L5 to table captions.
4. Add the "Changes since the preliminary report" table and a Limitations and open-items section.
5. Rewrite the literature section with all existing references cited (section 5) and a replication-plan table (section 6).
6. Package and submit the code (README, requirements, one command to reproduce Table 1).
7. Soften over-claims and shorten the abstract.

**26–31 Oct:**
- Proper subject-wise split and retraining; causal PCA; FHR metrics with CIs.
- Collision vs non-collision analysis; ICA and ANC-with-reference baselines.
- Fixed-point model for the full beamformer chain plus word-length sweep.
- Start RTL: filters, 4-MAC beamformer, detector, UART. Reuse the bit-exact verification style from #22.

**1–7 Nov:**
- Testbench vs golden vectors; Vivado synthesis; real resource, timing and power numbers.
- Replications R1–R4; real-data check.
- Block-adaptive weights (motion case).

**8–12 Nov:**
- Boolean Board bring-up (UART in, LEDs and 7-segment out); demo script with presets.
- Per-member contribution table; comment all code per member.
- Final write-up and viva rehearsal (section 9).

---

## 11. Quick wins list (checklist)

- [ ] AI disclosure section
- [ ] Code zip with README submitted
- [ ] Table 2 vs Table 1 vs Fig. 5/7 numbers reconciled
- [ ] Channel indices (33–34 = maternal reference) and case labels (c2, c4) corrected; dataset paper cited
- [ ] U-Net split stated (and fixed in the final)
- [ ] "Synthesized" renamed to "estimated" until Vivado is run
- [ ] SQNR claim tied to the correct design
- [ ] PPR-8 defined; FHR error reported
- [ ] Negative correlation explained (sign alignment)
- [ ] Every reference cited in the text; 20+ references; comparison table
- [ ] Replication table (honest status)
- [ ] Boolean Board demo plan and I/O mapping
- [ ] Per-module resource table and latency explanation (0.08 µs vs 3.28 µs)
- [ ] Figures readable at print size; legends not covering data; captions match plots
- [ ] Names removed or replaced if the review copy must be anonymous
- [ ] Over-claim words removed ("conclusive", "flawlessly", "fully establishing", "optimum clinical")
- [ ] Limitations, risks and open-items sections

---

*Sources checked: EE2000 course flier, MTR #0008, MTR #22, and the PhysioNet FECGSYNDB page (https://physionet.org/content/fecgsyndb/1.0.0/). Literature names in section 5 are leads from memory; verify each before citing.*
