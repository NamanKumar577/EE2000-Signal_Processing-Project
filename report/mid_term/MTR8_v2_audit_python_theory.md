# MTR-8 (revised version): Audit of Python, Theory, Mathematics and Technique

Report audited: `mtr-8_5e12da.pdf`. It matches the previous upload (`mtr-8_1.pdf`) in everything I checked (abstract, Tables 1-12, equations, figure captions), so this audit covers both.
Scope requested: **everything except the FPGA part** (RTL, synthesis, board, resource tables, UART, demo script), because that is not implemented yet.

**Deadline note:** the flier sets the mid-term deadline at 25.10.2026. P0 items below are mostly wording, table and caption fixes; do those first.

---

## 0. Instructions for the Antigravity agent (read first)

1. **Never invent or adjust numbers to make things agree.** Every number in the paper must come from the CSVs/logs. If a number cannot be regenerated, delete it or relabel it as "estimate" or "not measured".
2. Keep L1-L5 tags. Tag a number only with the level that produced it.
3. Keep the report anonymous (no team-member names, including in figure legends and code listings).
4. Log every edit in `CHANGELOG_MTR8.md` as `ID | file | before -> after | evidence`.
5. Tags: **[CONFIRMED]** = provable from the PDF alone. **[VERIFY IN CODE]** = suspected from the PDF; open the code or data and confirm before editing. **[EXTERNAL]** = depends on outside sources.
6. Before editing anything, confirm the helper scripts named in Sec. 20 exist and run: `tools/make_numbers_tex.py`, `tools/check_consistency.py`, `report/mid_term/build_full_report.py`. Extend `check_consistency.py` with the checks in Section 9.
7. Rebuild **all figures from the CSVs** after fixing the code. Several figures still carry old names and old formulas (see Section 6).

**What I could not see:** the Python code, CSVs and LaTeX source. Every code-level finding below is inferred from what the report says the code does. I mark those items [VERIFY IN CODE].

**Out of scope here (parked for the final report):** Sec. 7 board mapping, Sec. 11.2 cycle schedule, Sec. 12 / Table 8 resource sizing, Fig. 6, 18-21, UART numbers, Sec. 16 / Table 10 demo script, L3-L5 status wording, Q9.23 accumulator format.

---

## 1. What was fixed since the last version, and what is still open

| Earlier ID | Earlier finding | Status now |
|---|---|---|
| E-01 | Table 4 arithmetic wrong | **FIXED.** I recomputed every Table 4 value from Table 3; all match now. |
| E-02 | U-Net 90.76% used for two populations | **PARTLY FIXED.** Table 6 separates train/val/test/all and the abstract quotes 97.48% for test. Still wrong in Sec. 10.1 item 1, Sec. 15 R6 and Table 9 R6 (they still call 90.76%/80.79% "untouched test subjects"). The abstract still calls the all-10-subject mean "generalization". |
| E-03 | PCA "generalization" and tuning leakage | **PARTLY FIXED.** Test number added (93.06%). But Sec. 4 says lead selection used "all recordings" (see S-01). |
| E-04 | "SE" was a CI half-width | **PARTLY FIXED.** Abstract and Table 5 are consistent (SE 0.55, half-width 1.08). Sec. 9 Eq. (17) text still says ±0.88% / ±1.24% (see S-05). |
| E-05 | FHR numbers inconsistent | **CHANGED.** Now reported honestly (6.57 bpm overall, 58% agreement) but new anomalies appeared (S-03, S-04). |
| E-06 | Runtime numbers contradict | **OPEN** (S-15). |
| E-07 | Amplitude ratio statements | **PARTLY FIXED** (S-08). |
| E-08 | Q1.15 LSB bigger than fetal signal | **FIXED** (AFE mapping ±5 mV, 0.152 uV LSB; 20 uV = 131 LSB checks out). |
| E-11 | Filter order / Fig. 4 / group delay | **OPEN** (S-10). |
| E-12 | Overclaims | **MOSTLY FIXED** (sub01 qualifiers, "suggesting", "76% fails the target"). |
| E-14 | Row/method counts | **OPEN** (S-12). |
| E-15 | Numbers without evidence | **OPEN** (S-13) and new ones added (98.4% polarity). |
| E-16 | AI disclosure | **OPEN** (R-06). |
| E-17 | Anonymity | **PARTLY FIXED.** Roles are now generic, but names remain in Figs. 7, 9, 10, 13-16 legends and Sec. 20. |
| E-18 | EC57 misattributed | **PARTLY FIXED.** Table 1 column renamed "Project Engineering Target" but EC57 is still cited for sampling rate and the 50 ms window. |
| T-01 | Rank-3 theory vs `w = v2` | **OPEN** (T-01). |
| T-03 | "4 components = 100%" tautology | **OPEN** (T-03). |
| T-04 | SINR formulation vs PCA heuristic | **OPEN** (T-04). |
| T-11 | Detector undefined | **MOSTLY FIXED** (Sec. 5.2 added; some rules still missing, S-11). |
| C-03 | Per-subject table | **FIXED** for PCA (Table 7). Add U-Net. |
| R-01 | [17] author list | **OPEN.** |
| R-02, R-06 (old) | Kanjilal author; Pan-Tompkins uncited | **FIXED.** |

---

## 2. Priority index of items in this audit

| ID | Sev | Type | One-line summary |
|---|---|---|---|
| S-01 | P0 | Protocol | Lead array chosen from "all recordings", contradicting the strict split |
| S-02 | P0 | Results | U-Net scores higher on unseen subjects (97.48%) than on its own training subjects (88.13%) |
| S-03 | P0 | Results/Code | PCA correlation is -0.135 in the population table; "98.4% polarity" unsupported |
| S-04 | P0 | Metric | FHR MAE 6.57 bpm / 58% agreement inconsistent with F1 93%; targets changed after results |
| S-05 | P0 | Statistics | Sec. 9 CI numbers stale; R6 and Sec. 10.1 mislabel partitions |
| S-06 | P0 | Calculation | Database size: x4 bytes gives 2.55 GB, not 5.10 GB; draft-residue sentence about 33.4 GB |
| S-07 | P0 | Math | Overlap-probability derivation (32.5% vs 12-18%) is mixed up |
| S-08 | P1 | Calculation | Amplitude ratio, dB and FMR statements still inconsistent |
| S-09 | P0 | Protocol/Code | Python evaluation mode (sliding / global) may not match the deployed algorithm |
| S-10 | P0 | Code/Theory | Filter order, SOS count, Fig. 4 and group-delay statements disagree |
| S-11 | P1 | Method | Detector spec incomplete; naming clash "PPR-8" |
| S-12 | P1 | Consistency | Methods M4-M9, SWT-LMS, NLMS undescribed; 35 vs 36 rows; counts |
| S-13 | P0 | Traceability | Numbers with no table/figure/code behind them |
| S-14 | P1 | Results | SNR trend non-monotonic (0 dB beats 3/6/9 dB) |
| S-15 | P1 | Code | Runtime numbers contradict (3 ms vs 190.7 ms; 1.78 s vs 107.5 s) |
| S-16 | P1 | Statistics | Test set has only 2 subjects; need LOSO and per-subject U-Net numbers |
| T-01..T-09 | P1 | Theory | Rank-3 vs `w=v2`, eigen-spectrum, tautology, SINR claim, power iteration, null-depth equation, rounding equation, spectral assumption, baselines |
| M-01..M-06 | P2 | Technique | Improvements and ablations worth adding before the final report |
| G-01..G-12 | P1/P2 | Figures | Labels, captions and legends that contradict text or old formulas |
| R-01..R-06 | P1 | References/compliance | Citations, EC57, AI disclosure, stale register entries |
| W-01..W-04 | P2 | Writing | Draft-residue wording |

---

## 3. P0 items (fix today)

### S-01 [CONFIRMED] Lead selection used "all recordings", but the test set is declared untouched
- **Where:** Sec. 4 ("Analysis of 34-channel FMR topography across **all recordings** (Fig. 3) reveals ...") versus the split box ("Training Partition ... used exclusively for ... lead array C_opt"; "Test Partition ... completely untouched during design and hyperparameter tuning").
- **Problem:** Both statements cannot be true. If the FMR topography used sub09-sub10, the test partition influenced the choice of [27, 26, 28, 25]. The headline "93.06% on untouched held-out test subjects" is then not clean.
- **Fix:**
  1. Recompute the FMR topography from **sub01-sub07 only** (and optionally LOSO: select on 9 subjects, test on the 10th).
  2. Check whether the selected 4-lead set is still [27, 26, 28, 25] (state the indexing convention, see G-03).
  3. Re-run Table 6 for PCA with that selection. If the set changes, use the training-only set everywhere.
  4. Rewrite the sentence in Sec. 4 to say which subjects were used.
- **Done when:** the paper says "lead selection used sub01-sub07 only" and the script `select_leads.py` has a `--subjects` argument that the paper's number reproduces.

```python
# pseudo-code, adapt names to your repo
train_subjects = [f"sub{i:02d}" for i in range(1, 8)]
fmr = compute_fmr_per_channel(load_records(train_subjects))   # shape (34,)
best_single = int(np.argmax(fmr))                              # print 1-based index
best4 = top_adjacent_subarray(fmr, k=4)                        # same rule you used before
print("training-only selection:", best4, "peak FMR", fmr[best_single])
```

### S-02 [CONFIRMED] U-Net does better on unseen subjects than on the subjects it was trained on
- **Where:** Table 6.

| Model | Train (sub01-07) | Val (sub08) | Test (sub09-10) | All |
|---|---|---|---|---|
| U-Net 4-ch | **88.13** | 95.69 | **97.48** | 90.76 |
| U-Net 1-ch | **79.17** | 85.89 | 83.93 | 80.79 |

  (I checked that the weighted average of the three partitions reproduces "All" for every row, so Table 6 is internally consistent.)
- **Problem:** A model trained for 50 epochs on subjects 1-7 should score at least as high there as on new subjects. The pattern suggests (a) under-training or an evaluation mismatch (for example BatchNorm in train mode, different windowing for train vs test), or (b) sub09-sub10 are simply easy subjects, in which case a 2-subject test set tells you little. Also sub01 alone gets 98.59% (Table 4) while the training-set average is 88.13%, which implies some training subjects score far lower.
- **Why it matters:** The headline "U-Net 97.48% on unseen test subjects" can be an artefact. It also changes the story: on the held-out subjects the U-Net (97.48%) beats PCA (93.06%) by 4.4 points. The captions "Spatial PCA achieves the highest population mean" (Fig. 13) are true only because the U-Net's training-subject scores pull its all-subject mean down.
- **Fix:**
  1. Add a per-subject U-Net table (same layout as Table 7) for 4-ch and 1-ch, plus FHR MAE per partition.
  2. Plot train/val loss curves; confirm `model.eval()` is used for every evaluation; confirm identical windowing and stitching for train/val/test.
  3. Run **leave-one-subject-out** (10 trainings; each holds out one subject and validates on another). Report the 10 held-out subject means and use df = 9 for that CI.
  4. Rewrite the narrative honestly: PCA needs no training and is hardware-friendly; U-Net is more accurate on held-out subjects but not FPGA-friendly. Reword Fig. 13's caption.

### S-03 [CONFIRMED / VERIFY IN CODE] PCA correlation is negative in the population table, and the polarity claim has no evidence
- **Where:** Table 5 (Spatial PCA Corr = **-0.135**) versus Table 4 (sub01 Corr = **0.909**); Sec. 5.1 ("resolving correct polarity in 98.4% of records; window-to-window continuity logic preserves phase stability").
- **Problems:**
  - A mean correlation of -0.135 over 250 records, while sub01 TC1-TC3 are about +0.99, means many records have strongly **negative** correlation. That contradicts "correct polarity in 98.4% of records".
  - The 98.4% figure has no table, script or log behind it.
  - The detector (derivative, then squaring) is **sign-insensitive**, so polarity does not change F1 or FHR at all. Polarity only affects the waveform correlation and any plot of the output. The justification "to enforce positive R-peak polarity" is therefore irrelevant to detection.
- **Fix:**
  1. Compute per-record `sign(corr(f_hat, fetal_reference))` and its distribution. Report the true polarity-correct fraction.
  2. If polarity is wrong in many records, debug Eq. (6) (which signal the skewness is computed on, window length, whether the sign is updated every window and flips the output).
  3. Report correlation with polarity aligned to the reference (or `|corr|`) as a separate, clearly defined column, or drop the correlation column for PCA if it is not meaningful (the PCA output is not scaled to the fetal waveform).
  4. State plainly that polarity alignment is cosmetic for the detector; keep it only for display.
  5. Remove "98.4%" unless step 1 reproduces it.

```python
# diagnostic: polarity and correlation per record
rows = []
for rec in all_records:
    f_hat = pca_output(rec)                # your function
    r = np.corrcoef(f_hat, rec.fetal_ref)[0, 1]
    rows.append((rec.subject, rec.snr, rec.cond, r))
df = pd.DataFrame(rows, columns=["subject", "snr", "cond", "corr"])
print((df["corr"] > 0).mean(), df.groupby("subject")["corr"].mean())
```

### S-04 [CONFIRMED / VERIFY IN CODE] FHR numbers do not fit the F1 numbers, and targets were changed
- **Where:** Abstract, Table 1, Table 5, Table 7.
- **Problems:**
  - PCA: F1 = 93.00% but population FHR MAE = **6.57 bpm** and agreement = **58.0%** within +-5 bpm. On sub01 TC1-TC3 the MAE is 0.32-0.48 bpm. With a 5-beat median filter, 93% detection should not give a 58% agreement rate.
  - Back-calculation: if c0 has MAE 0.48 bpm, the other four conditions must average (6.57x5 - 0.48)/4 = **8.1 bpm**. c2 and c3 have F1 of about 97%, so c1 and c4 would need MAE around 15 bpm while their F1 is 90.8% and 83.1%. That is not consistent.
  - Likely cause: **index-based pairing** of `FHR_est[k]` and `FHR_ref[k]` (Eq. 14). If one beat is missed or falsely detected, every later pair is shifted. Eq. (16) defines FHR per beat but never says how estimated and reference beats are paired.
  - Table 1 changed relative to the previous draft: the target "FHR MAE < 1.0 bpm" gained "< 8 bpm overall" (a target written after seeing 6.57), and the row "Clinical agreement >= 95% within +-5 bpm" was **removed** while the population agreement is only 58%. The held-out test MAE is 8.00 bpm, which is not "< 8".
  - Fig. 8(b): limits of agreement [-6.75, +5.90] bpm under "noise" include records with large errors; say which records are plotted.
- **Fix:**
  1. Define pairing in the paper. Recommended: evaluate FHR on a **uniform time grid** (for example every 1 s: FHR computed from detected beats within a trailing window versus reference on the same grid), or restrict to matched true-positive beats.
  2. Produce a per-condition and per-SNR table of F1, MAE and agreement for PCA and U-Net.
  3. If MAE collapses after correct pairing, regenerate Tables 1, 4, 5, 7, 8(b) and the abstract.
  4. Restore the "agreement >= 95%" row in Table 1 and report the true value (even if it fails). Define targets before results and say so; do not change them after.
  5. State which records go into the Bland-Altman plot.

```python
# FHR on a time grid (instead of beat-index pairing)
def fhr_on_grid(peak_times_s, grid_s, win_s=10.0):
    out = []
    for t in grid_s:
        p = peak_times_s[(peak_times_s > t - win_s) & (peak_times_s <= t)]
        out.append(60.0 / np.median(np.diff(p)) if len(p) >= 3 else np.nan)
    return np.array(out)
```

### S-05 [CONFIRMED] Stale or inconsistent statistics text
| Place | Says | Should say / check |
|---|---|---|
| Sec. 9, after Eq. (17) | "+-0.88% for Spatial PCA (s_run = 7.07%) and +-1.24% for Deep U-Net (s_run = 10.03%)" | Abstract and Table 5 give +-1.08% (SE 0.55%, so s_run is about 8.7%) and +-1.97%. Use one set, generated from the CSV. |
| Abstract: "90.76% +- 7.27% population generalization F1 across all 10 subjects" | +-7.27 is the **clustered CI half-width** ((98.03 - 83.48)/2), not an SD; "generalization" is wrong because the mean includes the 7 training subjects | "population mean 90.76% (95% clustered CI [83.48, 98.03])"; use "generalization" only for held-out subjects |
| Sec. 10.1 item 1 | "population generalization F1 across all 10 subjects is 90.76%" | same fix |
| Sec. 15 R6 and Table 9 R6 | "On the untouched test subjects (sub09-sub10) ... 80.79% (1-ch) and 90.76% (4-ch)" | Table 6 gives 83.93% and 97.48% for the test subjects. 80.79/90.76 are all-subject means. Fix both numbers and the label. |
| Sec. 9, "Clustered intervals provide an anatomically rigorous measure of clinical generalization." | overclaim | "of between-subject variability on synthetic data" |

### S-06 [CONFIRMED] Database size arithmetic and a draft-residue sentence
- 250 x 75,000 x 34 x **4 bytes** = 2.55 GB, not **5.10 GB**. 5.10 GB corresponds to 8 bytes per sample (float64). The partition sizes (3.57 / 0.51 / 1.02 GB) are 70/10/20% of 5.10, so they inherit the same problem.
- **Fix:** state the real on-disk dtype and size (read it from the files), then recompute the three partition sizes.
- The sentence "The previously quoted 33.4 GB referred to total intermediate tensor memory allocated during multi-epoch PyTorch training" should be **deleted**: no earlier submitted text quoted that, and it is an unverified rationalisation. Do not keep it unless you actually measured that number (for example with `torch.cuda.max_memory_allocated()`), and even then it does not belong in the dataset description.

### S-07 [CONFIRMED] Overlap-probability derivation is mixed up
- **Where:** Sec. 1 ("(w_m + w_f)/T_f = (90+50)/430 ~ 32.5% causes complete coincidence in 12-18% of all cardiac cycles").
- **Problem:** Two different quantities are mixed.
  - Fraction of **maternal** beats that are overlapped by some fetal QRS: (w_m + w_f)/T_f = 140/430 = **32.6%**.
  - Probability that a given **fetal** beat overlaps a maternal QRS (random relative phase): (w_m + w_f)/T_m = 140/800 = **17.5%**. This is the number that matches "12-18%".
  - "Complete coincidence" (fetal QRS fully inside the maternal QRS) needs |offset| <= (w_m - w_f)/2, giving (w_m - w_f)/T_m = 40/800 = **5%**.
  - So 32.5% does not "cause" 12-18%, and "complete coincidence" is not 12-18%.
- **Fix:** write the correct formulas, state which is partial overlap and which is containment, and replace the assumed 12-18% by a number **measured from the FECGSYNDB annotations**: the fraction of reference fetal beats within +-X ms of a maternal QRS, per subject and condition. Then report F1 for colliding and non-colliding beats separately (this is the evidence your whole motivation needs, see T-09).

### S-09 [VERIFY IN CODE] Python evaluation mode may not match the deployed algorithm
- **Where:** Sec. 5.1 (covariance over a "sliding observation window", "window-to-window continuity logic") versus "System Partitioning": the host computes weights **once** from a 3 s buffer and the FPGA applies them for the whole record.
- **Problem:** The population F1 (93.00%) may come from (A) one global covariance over all 75,000 samples (non-causal, optimistic), (B) weights from the first 3 s then frozen (what the hardware plan does), or (C) sliding re-estimation (not in the hardware plan). Which one was used is not stated. Table 3 PCA runtime 0.003 s per record suggests a single global eigendecomposition, while Table 5 says 190.7 ms (S-15).
- **Fix:** implement and report all three modes on the test subjects and population:
  - A: global covariance (oracle upper bound),
  - B: first 3 s, then frozen weights (matches the hardware plan; this should be the headline),
  - C: re-estimate every K seconds (K = 3, 10, 30).
  Also state whether the preprocessing filter is causal (`sosfilt`) or zero-phase (`sosfiltfilt`); see S-10.

### S-10 [CONFIRMED / VERIFY IN CODE] Filter specification is inconsistent (Python side)
- **Where:** Sec. 4 "Preprocessing cascade", Fig. 4 and caption, Sec. 9, Table 9 R1.
- **Problems:**
  - Text: "4th-order filter implemented as two cascaded SOS". The stated attenuations (>= 40 dB at 0.1 Hz, >= 14 dB at 60 Hz) match a **4th-order high-pass plus 4th-order low-pass** (that is what `scipy.signal.butter(4, [0.5, 40], 'bandpass', output='sos')` returns: **4 SOS, 8th order overall**). Check: a 2nd-order low-pass at 40 Hz gives -7.8 dB at 60 Hz, a 4th-order gives -14.3 dB; a 2nd-order high-pass at 0.5 Hz gives -28 dB at 0.1 Hz, a 4th-order gives -56 dB. Two SOS cannot give the printed numbers.
  - Fig. 4 legend reads "HPF 0.5 Hz, Notch 50 Hz, BPF 1-100 Hz, QRS BPF 8-30 Hz". None of these is the 0.5-40 Hz band-pass named in the caption, so the 60 Hz claim cannot be read from the plot.
  - "A deterministic group delay of 24 samples (96 ms)": an IIR Butterworth has a frequency-dependent group delay, so there is no single deterministic value. In the QRS band (roughly 10-30 Hz) the delay of this filter is probably only tens of milliseconds, while near 0.5 Hz it is hundreds. Where does 96 ms come from?
  - If the Python code uses `sosfiltfilt` (zero phase), then there is no group delay in the L1 results and the L1 numbers are not those of a causal hardware filter.
- **Table 1 consequence:** "Event alarm latency <100 ms | 96 ms (24 SOS taps) [L1] Verified" is wrong: "SOS taps" has no meaning, and the 96 ms covers only the band-pass. The algorithmic delay also includes the 5-point derivative (2 samples), the 15-sample integrator (about 28 ms to its centre), the refractory logic and the 5-beat median.
- **Fix:**
  1. Print the number of SOS sections and the real order; state them in the text and in Table 9 R1.
  2. Plot the actual 0.5-40 Hz response and the notch response on separate, correctly labelled curves.
  3. Compute group delay versus frequency and report the value in the QRS band.
  4. Confirm causal vs zero-phase filtering; if you used zero-phase for L1, say so or switch to causal.
  5. **Measure** the end-to-end detection delay in Python (detected peak time minus reference R time, mean and spread) and use that in Table 1 instead of 96 ms.

```python
import numpy as np
from scipy import signal
fs = 250
sos = signal.butter(4, [0.5, 40], btype="bandpass", fs=fs, output="sos")
print("SOS sections:", sos.shape[0])                       # 4 means 8th-order overall
f = np.array([0.1, 0.5, 5, 10, 20, 40, 60])
_, h = signal.sosfreqz(sos, worN=f, fs=fs)
print("gain dB:", np.round(20*np.log10(np.abs(h)), 1))
b, a = signal.sos2tf(sos)
fg = np.array([1, 2, 5, 10, 15, 20, 30, 40])
_, gd = signal.group_delay((b, a), w=fg, fs=fs)
print("group delay ms:", np.round(gd / fs * 1000, 1))
```

### S-13 [CONFIRMED] Numbers with no table, figure or code behind them
Provide a table/script for each or remove it.

| Number | Where |
|---|---|
| NLMS with thoracic reference: 81.2% clean, 42.1% at 0 dB | Table 9 R7 (not in any results table) |
| Block-adaptive covariance: TC4 F1 72.79% -> 86.4% | Sec. 13 |
| Wavelet-after-beamformer: TC5 F1 +4.2% | Sec. 13 |
| "98.4% of records" correct polarity | Sec. 5.1 |
| 1 lead 20.6-35.8% F1, 2 leads 95.3% on TC1 | Sec. 10.2 (only visible in Fig. 12 plot) |
| "12-18%" collisions | Sec. 1 (see S-07) |
| "rank-2 truncation eliminates >90% of maternal energy" | Table 9 R2 / Sec. 15 (no measurement shown) |
| ">88% of mixture energy in v1" | Sec. 5.1 (Fig. 17 shows one array only) |

---

## 4. P1 items

### S-08 [CONFIRMED] Amplitude, dB and FMR statements are still inconsistent
- Sec. 1: "peak amplitude is **10-50x** larger (1-5 mV vs 20-100 uV, corresponding to **20-28 dB**)". The stated ranges give 10x to **250x** (20-48 dB). 20-28 dB is 10-25x, which is what Fig. 1's caption says.
- "FMR ranges from 0.20 to 0.54 (-6 to -14 dB)": 20 log10(0.54) = **-5.4 dB**, 20 log10(0.20) = -14.0 dB. Write "-14 to -5.4 dB".
- Peak ratio 25x (Fig. 1: 1.00 vs 0.04) versus RMS ratio 0.2-0.54 (a ratio of only about 2-5x). ECGs of both hearts have similar crest factors, so the peak and RMS ratios should agree to within a small factor; a 5-13x difference means one set of numbers is nominal (from literature) and the other measured. The eigenvalue ratio lambda2/lambda1 = 7.8/88.4 gives an amplitude ratio of about 0.30, consistent with the **RMS FMR** and not with 25x.
- **Fix:** compute from the data, per lead, the peak ratio (for example 99.9th percentile of |component|) and the RMS ratio, using the separate maternal/fetal components if the database provides them. Redraw Fig. 1 from these measured values (or label it "literature-typical, not measured on FECGSYNDB"). Quote one consistent range.

### S-11 [CONFIRMED] Detector description still incomplete
- Missing: initial values of S and N, the update rules (Pan-Tompkins uses `SPKI = 0.125*PK + 0.875*SPKI`, `NPKI = 0.125*PK + 0.875*NPKI`), T-wave discrimination or search-back (or a statement that none is used), how the peak **time** is taken (maximum of the integrated signal or of the filtered signal) and the fixed offset applied to compensate derivative and integrator delay.
- State whether the detector runs continuously over the record or restarts its thresholds on every 5 s window (this changes results).
- The text in Sec. 9 and Fig. 2 still call it "PPR-8 detector", but Sec. 5.2 calls it the Peak-Energy Detector, and "PPR-8" is also the ID of your preliminary report. Use one name.
- The detector input is `f_hat` for PCA, a single lead for baselines, and the U-Net output for U-Net. Say so, and that all methods share identical detector settings.
- Pan-Tompkins used a 150 ms integrator for adult QRS; your W = 60 ms is a design choice for fetal QRS, so say it was chosen on the **training** subjects.

### S-12 [CONFIRMED] Methods, counts and names
- Table 2 lists 9 methods (M1-M9), but **SWT-LMS Wavelet Filter** appears in Tables 3 and 4 and Figs. 7, 9, 10 and is not in Table 2; NLMS (R7) is not listed either. Sec. 20 still says "six extraction algorithms".
- Methods M4-M9 now have only one-line descriptions. The earlier Sec. 5 text describing multi-lead template fusion, SVD windows, wavelet thresholding and ANC was removed. A reader cannot reproduce them. Add a short subsection per method: template construction (how maternal template is formed, update rule for the adaptive one, number of beats averaged), SVD (Hankel size, rank removed, window length and how it is chosen), wavelet (wavelet type, levels, thresholding rule), LMS (taps, step size, reference signal).
- Table 3 has **36** rows (TC3 has an extra "Hankel-SVD V3" row; TC1, TC2, TC4, TC5 do not) but Table 11 and Sec. 20 say "35-run". Include V3 in every test case or remove it from Table 3.
- Fig. 7 caption says "six extraction architectures"; the legend shows seven.
- Table 9 R2 writes the Hankel matrix as `A in R^{m x 174}`; with m = 174 the dimensions are `m x (N - m + 1)`.
- M5 "Wavelet-Threshold Hybrid", SWT-LMS and "Vivek hybrid" (Sec. 20, Figs.) refer to overlapping things. Use one name per method in all tables, figures and code.
- Table 12 R-05 says "(V1, V2, V3)" but V2 never appears.

### S-14 [VERIFY IN CODE] SNR trend is non-monotonic
Spatial PCA by SNR tier: 0 dB 93.68%, 3 dB 91.95%, 6 dB 92.73%, 9 dB 91.40%, 12 dB 95.22%. A 0 dB tier scoring above 3, 6 and 9 dB is suspicious. Check (a) the file-name parsing of the SNR tag, (b) whether adaptive detector thresholds make the 0 dB records easier, (c) a paired comparison per subject and condition. Add a per-SNR and per-condition table for PCA and U-Net. Until explained, state it as an unexplained observation.

### S-15 [CONFIRMED] Runtime numbers still contradict
- Fig. 22 plot: PCA 3 ms, U-Net 82 ms, SWT-LMS 1.78 s. Fig. 22 caption and Table 5: PCA 190.7 ms, U-Net 98.6 ms, SWT-LMS 107.5 s. Table 3: PCA 0.003 s, U-Net 0.082 s, SWT-LMS 1.772 s.
- The factor of roughly 60 (1.78 s vs 107.5 s; 3 ms vs 190.7 ms) suggests "per 5 s window" versus "per 5-minute record". U-Net's 98.6 ms vs 82 ms also differs.
- **Fix:** time all methods with one script (same machine, state CPU/GPU model, warm-up excluded, median of N runs) per 5-minute record; use the same numbers in Table 3, Table 5, Fig. 22 and its caption. The PCA number also depends on the evaluation mode (S-09).

### S-16 [CONFIRMED] Statistical presentation with only two test subjects
- The test partition has 2 subjects (50 records), so a t-interval is not meaningful (t = 12.7 at df = 1). Present test results as per-subject numbers, not as a CI.
- The paragraph "This arithmetic confirms zero discrepancy ... verifying that every reported subset is fully traceable" is an identity (the mean of group means equals the overall mean in a balanced design), not a verification. Rephrase to "consistency check".
- Add paired comparisons: for each subject, the paired difference PCA minus U-Net (and a Wilcoxon signed-rank test over the 10 subject means) instead of comparing overlapping CIs.

---

## 5. Theory and mathematics

### T-01 Rank-3 maternal subspace vs `w = v2` (still unresolved)
- Sec. 11.1 says the maternal contribution has rank min(C, 3) and that for C = 4 there is a **1-D orthogonal complement** into which the fetal dipole projects. The method then takes `w = v2`, the second eigenvector of the *mixture* covariance.
- If the maternal subspace really has 3 dimensions, the direction orthogonal to all of it is the eigenvector of the **maternal-only** covariance with the smallest eigenvalue. In the mixture covariance the three largest eigenvalues would then be maternal-dominated, and the fetal direction would be near the *smallest* eigenvalue (`v4`), not `v2`.
- Fig. 17(a) labels the bars "v1 (Mat. Dipole)", "v2 (Fetal Signal)", "v3 (Mat. Y-loop)", "v4 (Noise)" while the text says lambda3 and lambda4 are "residual EMG and sensor noise". The figure says v3 is maternal; the text says it is noise.
- Sec. 10.2 reports that **2 leads already give 95.3% on TC1**, but Sec. 11.1 asks "why do 4 channels saturate while 1 or 2 fail?" and the theory (rank 3) says 2 leads should fail.
- **Fix:** test it rather than assert it.
  1. Estimate the maternal subspace from maternal-only data (channels 33-34 are thoracic references, or gate the covariance to windows around detected maternal R-peaks, or use the maternal component if the database provides it).
  2. Compute principal angles between that subspace and the span of `{v1, v2, v3}` of the abdominal covariance.
  3. Compute the cosine between `w = v2` and the true fetal lead-field direction per subject.
  4. Compare detection F1 for `w = v2` against `w = v4` and against a generalized-eigenvector solution (see M-02).
  5. Rewrite Sec. 11.1 so the claim matches what you find. If `v2` works because the maternal energy is mostly 1-D at the QRS, say that, and treat the 3-D rank argument as a model, not as an explanation of `v2`. Then also reconcile it with the 2-lead result.

### T-02 "lambda2 = the fetal biopotential" needs a direct test
With RMS FMR near 0.3, a second eigenvalue of 7.8% is plausible, but the identification is still asserted. Show it: correlation of `w^T x` with the fetal reference per record, and the eigenvalue share when the fetal component is removed (if the database provides separate components). Then fix Fig. 17's v3 label (T-01).

### T-03 "4 components capture 100.0% of the signal space" is a tautology
A 4x4 covariance always has four eigenvalues summing to 100%. This sentence (Sec. 11.1, Fig. 17(b) caption) proves nothing. Replace it with a real statement, for example the share of variance in the subspace *excluding* v1, or delete.

### T-04 Problem statement promises more than the method does
Eq. (1) asks for an "unconstrained" weight vector that "maximizes fetal R-peak SINR while nulling maternal potentials". The method is `w = v2` (a heuristic, unit norm). Either (a) restate the problem as "second principal component of the 4-lead covariance" or (b) implement a true SINR objective (generalized eigenproblem `R_f w = lambda R_m w` using a maternal-gated covariance, M-02) and compare.

### T-05 Power iteration extracts v1, but the weights use v2 (Sec. 13)
Power iteration converges to the dominant eigenvector (maternal, v1). Getting `v2` needs deflation or orthogonal (subspace) iteration. The statement "Power iteration extracts the updated maternal eigenvector v1 in only 8 iterations" does not give the weight vector. Also, lambda = 0.95 per sample has an effective memory of 1/(1 - 0.95) = **20 samples = 80 ms**, shorter than one cardiac cycle and unrelated to the 3 s window (equivalent lambda about 0.99867). The section is called "Block-adaptive" but Eq. (23) is per-sample. Either implement and measure it (S-13) or mark it as an untested design idea and remove the numbers 86.4% and +4.2%.

### T-06 Null-depth equation (Eq. 10) and Fig. 5 [L2 Python]
- Eq. (10) at B = 16, C = 4 evaluates to 20 log10(sqrt(12) x 2^15 / 2) = **95.1 dB**, but the text says "93.3 dB". At B = 12 it gives 71.0 dB; at B = 10, 59.0 dB.
- Fig. 5's legend still shows the **old** formula "Theoretical Bound (6.02B + 1.76 dB)", so the plotted line is not Eq. (10). The caption's "agreement with finite-wordlength error theory" is therefore unverified. Redraw Fig. 5 with Eq. (10).
- Eq. (10) is an expected-value estimate (uniform rounding error of variance LSB^2/12), not an "upper bound". Add a two-line derivation and call it an estimate.
- The caption says ">= 12 bits achieves > 60 dB"; by Eq. (10) B = 11 already exceeds 60 dB (65 dB), and B = 10 does not (59 dB). State which is true for your simulation.
- "the 55 dB required to suppress 28 dB maternal excess below the noise floor" is unexplained. Derive: required depth = peak ratio (dB) + margin, and say what the margin is. Also use one consistent peak ratio (S-08).
- Sec. 19 still says the team verified "the theoretical null depth quantization bound (6.02B + 1.76 dB)". Update.

### T-07 Quantization model (Eq. 9) does not match its description [VERIFY IN CODE]
- `floor(x * 2^15 + 0.5)` is **round half up**, not "round-to-nearest-even".
- `clip(..., -32768, 32767)` is **asymmetric**, not "symmetric saturation" (symmetric would be +-32767).
- The expression returns an integer code; dividing by 2^15 is needed to return to a value.
- **Fix:** open `src/fixed_point_model.py`. If the code uses `np.round` it is half-to-even (matches the text, not the equation); if it uses `floor(x+0.5)` it is half-up (matches the equation, not the text). Make the equation, text and code agree, and say which rounding the hardware will use.

### T-08 Spectral assumption
"Maternal and fetal cardiac biopotentials exhibit almost identical frequency spectra in the 0.5-40 Hz band" is too strong: the fetal QRS is shorter (50 ms vs 90 ms in your own numbers), so its energy sits higher than the maternal QRS. That is an exploitable difference, and a 40 Hz low-pass may remove some fetal energy. Run a small ablation of the band-pass (for example 0.5-40, 1-70, 5-45 Hz) on training subjects and report F1; then justify the band you keep.

### T-09 Baselines and the motivating argument
- The motivation says template subtraction fails because 12-18% of cycles collide, but at 12 dB (TC1) fixed template subtraction already has 168 FP and 170 FN out of 716 beats (about 24%). That is more than collisions explain, so the baseline may be weak (fixed template, threshold, no scaling). Show F1 for colliding vs non-colliding beats (S-07) and tune the baseline fairly on the training subjects.
- "SWT-LMS ... because single-channel mixtures lack a pure maternal reference" explains the no-reference variant only. The fair ANC baseline is NLMS with the thoracic reference (R7); it is mentioned (81.2%, 42.1%) but not tabulated. Add it to Tables 3 and 5.
- ICA/JADE are discussed in the survey but not run. Add FastICA (or JADE) on the same 4 leads as an accuracy reference, then say it is not hardware-friendly.
- Sec. 14 / R3: "isolating the fetal dipole into v2 while eliminating the maternal subspace" is not shown; see T-01.

---

## 6. Figures and tables (non-FPGA)

| ID | Item | Problem | Fix |
|---|---|---|---|
| G-01 | Fig. 1 | Bars (1.00 / 0.04 / 0.15 / 0.08) look nominal; peak ratio vs RMS FMR mismatch (S-08) | Draw from measured data or label as literature-typical |
| G-02 | Fig. 2 | Caption mentions dual notch and "polarity-aligned beamforming"; figure has a "Maternal QRS Detection" block feeding PCA and no notch; input says "4-Ch" while several methods are single-channel | Redraw to match the actual Python pipeline (Python/host vs FPGA parts can be shown separately) |
| G-03 | Fig. 3 | x-axis 0-33 (0-based) vs text "Lead 27", "channels 25-28", "33-34 thoracic" (1-based). In the page image the tallest bar looks to be near index ~17 and the axis tops out near 0.5, while the text says peak FMR 0.54 on lead 27; bars in channels 1-12 also look higher than the "FMR < 0.15" stated in Sec. 4 (VERIFY by printing the FMR vector) | One indexing convention; annotate the chosen 4 leads; show the 0.54 value; recompute from training subjects (S-01) |
| G-04 | Fig. 4 | Legend does not show the 0.5-40 Hz filter (S-10) | Replot |
| G-05 | Fig. 5 | Legend shows old bound 6.02B + 1.76 dB; caption claims agreement (T-06) | Redraw with Eq. (10) |
| G-06 | Figs. 7, 9, 10, 13-16 | Legends still contain "Vivek Hybrid" / "Vivek_Hybrid_Alt" and "SVD V1" naming that differs from the tables | Regenerate with the neutral names from Table 2 |
| G-07 | Fig. 7 | Caption says "six" architectures; legend shows seven; legend overlaps the TC4/TC5 bars and value labels; U-Net bars are in-sample | Move the legend outside; fix the count; mark in-sample |
| G-08 | Fig. 8 | Which records enter the Bland-Altman plot? LoA [-6.75, +5.90] does not match "MAE 0.48 bpm" (S-04) | State the subset; recompute after fixing FHR evaluation |
| G-09 | Fig. 10 | "Reconciled values confirm ... dominance" while U-Net is in-sample on sub01 | Remove "reconciled"; mark in-sample |
| G-10 | Fig. 12 | Caption says 4 leads reach 100% on TC1-TC3 and performance "saturates beyond 8 leads"; the page image appears to show one curve falling sharply at the largest lead counts (VERIFY); a 1-lead "PCA" has no v2 | Explain or fix; state the lead-addition order; note that channels 33-34 are maternal-only |
| G-11 | Fig. 13 | Caption says "population F1 distributions" but the plot is a bar chart of mean +- 1 SD; "highest population mean" is misleading (S-02) | Use box/violin plots or fix caption |
| G-12 | Fig. 15 | x-axis labels c2 as "(Mod Noise)" while the caption says c2 is HR dynamics | Fix label |
| G-13 | Fig. 17 | v3 labelled "Mat. Y-loop" but text says noise; tautology claim (T-01, T-03) | Fix |
| G-14 | Fig. 22 | Plot values contradict caption and Table 5 (S-15) | Re-time and redraw |
| G-15 | Table 1 | "Event alarm latency 96 ms (24 SOS taps) [L1] Verified" (S-10); "Cold-start buffer" row is merged with the next row in the PDF layout | Replace latency by measured end-to-end delay; fix table layout |
| G-16 | Tables 3-5 | Table 3 has 36 rows (S-12); Table 4 caption still uses "Reconciled"; some Table 4/5 rows are visually merged in the PDF text layer | Regenerate from CSV; check layout |

General figure advice: fonts in Figs. 3, 8, 12, 16, 17 are too small at print size; keep one colour per method across all figures; export vector PDFs.

---

## 7. References and compliance

| ID | Item | Action |
|---|---|---|
| R-01 | [17] Andreotti et al. 2016 | Author list in the bibliography looks wrong (as I recall: Andreotti, Behar, Zaunseder, Oster, Clifford). Check the paper page. |
| R-02 | [13] Sameni et al. 2007 | Bayesian ECG denoising paper, but cited for "the 3D dipole vectorcardiogram model" (Sec. 14 item 4). Cite the correct source for the model used by FECGSYN/FECGSYNDB or reword. |
| R-03 | [20] Lee et al. (single-channel), [21] Zhong et al. | R6 attributes ">90% (4-ch)" and "82.3% (1-ch)" to them; [20] is titled "single-channel". Open both papers, confirm they exist, and copy their actual numbers and metric definitions into Table 9. If you cannot verify, drop "reproducing Lee et al.". |
| R-04 | [14], [9], [22] | JADE originates from Cardoso and Souloumiac; check [14] supports the sentence. Verify [9] (title, venue, pages). [22] is about real-time ECG digital filters; "matches Ahlstrom exactly" (R1) is not a replication of a published number. |
| R-05 | Standards | Sec. 9 and Table 1 still cite ANSI/AAMI EC57 for the +-50 ms window and the >= 250 Hz sampling rate [EXTERNAL, verify]. As I recall EC57 is a testing-methodology standard and the 50 ms fetal tolerance comes from the PhysioNet/CinC Challenge 2013 evaluation. Cite the Challenge paper. Uncited entries: [16], [18], [26], [27], [28], [29]; cite or remove. |
| R-06 | Sec. 19 AI disclosure | Still the old text: tool list only (Claude 3.5 Sonnet, GPT-4o with a single citation [30]), no per-part detail, the claim that "every numerical value in Tab. 3, 4, 5 was recomputed and audited" and "every cited reference was retrieved and verified", and a mention of the old 6.02B+1.76 dB bound. The flier asks you to "clearly indicate the parts of the work that were generated by AI". Rewrite: name the code files, report sections, figures and tables that were AI-drafted; what you ran and checked yourselves; add a citation per tool (including OpenAI); confirm the model versions really used. Only claim checks that were actually done. |
| R-07 | Table 12 (register) | Stale entries: R-08 still says "22 clock cycles" (paper now says 128); R-09 says "requires 0 BRAM" (Table 8 shows 1); R-05 mentions V2; R-12 repeats EC57; R-13 says "30 verified references"; R-15 says "complete academic integrity". Update or soften. |
| R-08 | Sec. 20 | Lists "six extraction algorithms" and "Vivek hybrid"; says "35-run" benchmark; make consistent with Table 2 and Table 3. |

---

## 8. Writing and wording

- **W-01:** Remove internal-process wording that reads oddly to reviewers: "Audited Performance Analysis and Reconciliations" (Sec. 10.1 title), "Reconciled" in Table 4 and Fig. 10 captions, "audited register", "previously quoted 33.4 GB". Use "Analysis", "Summary".
- **W-02:** The abstract is very long and number-heavy; cut it to about 200 words and put the partition (held-out test vs all subjects) next to each headline number.
- **W-03:** Use "generalization" only for held-out subjects; use "population mean" otherwise.
- **W-04:** In the abstract and Sec. 1 do not describe FPGA numbers as achievements ("proving", "verifying") when they are [L4 Target] sizing; keep them clearly labelled as estimates.

---

## 9. Recommended techniques and ablations (use the time before the final report)

| ID | Item | Why |
|---|---|---|
| M-01 | Three PCA modes: global, first-3-s-then-frozen, sliding every K s (S-09) | Matches what hardware will do; gives an honest headline |
| M-02 | Maternal-gated generalized eigenproblem: estimate the maternal covariance from windows around detected maternal R-peaks, then solve `R_mix w = lambda R_mat w` and take the smallest-lambda direction | Directly nulls the maternal subspace (T-01, T-04); may improve c1/c4 |
| M-03 | Window and hop ablation: N in {250, 500, 750, 1500}, hop in {1, 3, 10 s}; report F1 and cold-start delay | Justifies N = 750 using training subjects only |
| M-04 | Failure analysis: list the 10 worst PCA records (min F1 = 59.55%); show their subject, SNR, condition, eigen-spectrum and polarity | Explains sub04/sub05 (85.9%, 89.1%) |
| M-05 | FastICA / JADE baseline and NLMS-with-thoracic-reference baseline in the same tables | Closes the gap between survey and results (T-09) |
| M-06 | LOSO for U-Net and for lead selection; per-subject tables for every method | Valid generalization claims (S-02, S-16) |

---

## 10. Extra checks to add to `tools/check_consistency.py`

```python
import numpy as np, pandas as pd
from scipy import stats

pop = pd.read_csv("results/mega_benchmark_results.csv")   # assumed: subject, snr, cond, method, f1, mae, agr, corr, partition

# 1. Table 6 weighted means must reproduce the "All" column
w = {"train": 175, "val": 25, "test": 50}
for m, g in pop.groupby("method"):
    parts = g.groupby("partition").f1.mean()
    allm = sum(parts[k] * w[k] for k in w) / 250
    print(m, round(allm, 2), "vs overall", round(g.f1.mean(), 2))

# 2. Per-subject table (Table 7) and SD used in the clustered CI
sub = pop[pop.method == "Spatial PCA (4-Ch)"].groupby("subject").f1.mean()
print(sub.round(2).to_dict(), "sd:", round(sub.std(ddof=1), 2),
      "CI half-width:", round(stats.t.ppf(0.975, len(sub) - 1) * sub.std(ddof=1) / np.sqrt(len(sub)), 2))

# 3. Run-level numbers used in the text (SE, 95% half-width)
x = pop[pop.method == "Spatial PCA (4-Ch)"].f1
print("SE:", round(x.std(ddof=1) / np.sqrt(len(x)), 2), "half-width:", round(1.96 * x.std(ddof=1) / np.sqrt(len(x)), 2))

# 4. Polarity and correlation
d = pop[pop.method == "Spatial PCA (4-Ch)"]
print("fraction with corr > 0:", (d["corr"] > 0).mean(), "mean corr:", d["corr"].mean())

# 5. Per-condition FHR MAE (must be consistent with F1)
print(d.groupby("cond")[["f1", "mae", "agr"]].mean().round(2))

# 6. Dataset size
n_bytes = 250 * 75000 * 34 * 4
print("size at 4 bytes/sample (GB):", n_bytes / 1e9, " at 8 bytes:", 2 * n_bytes / 1e9)

# 7. Closed-form checks
Tm, wm, wf = 800.0, 90.0, 50.0
print("partial overlap per fetal beat:", (wm + wf) / Tm, "containment:", (wm - wf) / Tm)
B, C = 16, 4
print("Eq.10 null depth (dB):", 20 * np.log10(np.sqrt(12) * 2 ** (B - 1) / np.sqrt(C)))
```

---

## 11. Order of work

1. **Today (text, tables, captions):** S-05, S-06, S-07, S-08, S-12 (counts and names), S-13 (remove or label unsupported numbers), S-10 text corrections, G-06 (regenerate legends), R-05, R-06, R-07, W-01 to W-04.
2. **Today or tomorrow (quick code checks):** S-01 (lead selection on training only), S-03 (polarity and correlation), S-04 (FHR on a time grid, per-condition table), S-09 (state which PCA mode was used), S-10 (print SOS count, group delay), T-07 (rounding in the fixed-point model).
3. **Before the final report:** S-02 / S-16 (U-Net per-subject and LOSO), T-01 and M-02 (subspace test), M-01, M-03, M-04, M-05, T-09 baselines, S-14, S-15.
4. **Final check:** rerun `tools/check_consistency.py`, rebuild all figures from CSVs, re-read the PDF for every number that appears in more than one place (abstract, Sec. 1, Tables 1, 4, 5, 6, captions, Sec. 15, Sec. 19, Table 12).
