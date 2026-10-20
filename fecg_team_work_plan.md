# Fetal ECG Extraction Project — Team Work Plan

## 1. Objective

Four members will implement distinct fetal ECG extraction approaches and compare them under the same data, test cases, preprocessing rules, and evaluation metrics.

The aim is not to decide which paper is best by its published results. The aim is to determine which implementable method performs best on our selected FECGSYN-style synthetic records, where the clean fetal ECG is available as evaluation ground truth, and which method is practical to port to the Spartan-7 FPGA.

**Core rule:** all methods must receive the same permitted abdominal-mixture input. Clean fetal ECG must not be supplied to the extraction algorithm; it is ground truth for evaluation only.

---

## 2. Selected test cases

The initial test set has five cases. Use the same subject and repetition (`sub01`, `l1`) wherever the corresponding files exist.

| Test ID | SNR | Case | Purpose |
|---|---:|---|---|
| TC1 | 12 dB | `c0` | Easier baseline; check basic extraction |
| TC2 | 06 dB | `c0` | Moderate-noise robustness |
| TC3 | 00 dB | `c0` | Difficult baseline; signal/noise power ratio is 1:1 if the dataset's SNR definition is conventional |
| TC4 | 06 dB | `c1` | Fetal-movement condition, according to the selected test plan |
| TC5 | 06 dB | `c4` | Ectopic-beat condition, according to the selected test plan |

### Important file-availability check

The screenshots currently confirm the three `c0` filesets under the repository folders `test/snr00db/`, `test/snr06db/`, and `test/snr12db/`. They show the `.dat`, `.hea`, and `.qrs` files for `fecg1` and `mecg`, plus `.dat`/`.hea` files for `noise1` and `noise2`.

The screenshots do **not** show the `c1` or `c4` files. Before running TC4 and TC5, check that the exact files exist in `test/snr06db/`. If they are absent, obtain them from the correct dataset folder or temporarily mark those tests as pending. Do not silently substitute another case.

The likely filename pattern is:

- `sub01_snr12dB_l1_c0_fecg1.dat`
- `sub01_snr06dB_l1_c0_fecg1.dat`
- `sub01_snr00dB_l1_c0_fecg1.dat`
- `sub01_snr06dB_l1_c1_fecg1.dat`
- `sub01_snr06dB_l1_c4_fecg1.dat`

The matching `.hea` file should accompany each `.dat` file. These five exact paths are **expected names, not all verified from the screenshots**. Check the repository before coding.

---

## 3. What to load and how to build the mixture

For each test case, load the matching files for all available components:

| Component/file suffix | Purpose | May the extraction algorithm use it? |
|---|---|---|
| `fecg1.dat` and `fecg1.hea` | Clean fetal ECG reference | **No** for normal extraction; evaluation only |
| `mecg.dat` and `mecg.hea` | Maternal ECG component | Normally not directly; use for mixture construction/diagnostics only unless an explicitly labelled oracle experiment is being run |
| `noise1.dat` and `noise1.hea` | Noise component 1 | Used to reconstruct the mixture if the dataset definition requires it |
| `noise2.dat` and `noise2.hea` | Noise component 2 | Used to reconstruct the mixture if the dataset definition requires it |
| Matching `.qrs` files | Beat annotations, subject to annotation-format verification | Evaluation only; do not feed reference fetal annotations to the detector |
| Matching `.hea` files | Metadata such as sampling frequency, format, channel count and gain | Required for correct loading and unit conversion |

### Mixture construction must be centralized

The team has chosen to reconstruct the abdominal mixture from the separate components. However, **do not assume the exact mixing equation or scale factors without checking the dataset documentation and headers**.

1. Verify that the components have compatible lengths, sampling frequency, scaling and alignment.
2. Confirm the dataset's documented mixture equation and any component scaling.
3. Implement mixture construction once in a shared function; all four members must call the same function.
4. If the documented mixture is a sum, verify that the reconstructed signal matches the dataset's stated construction and SNR convention.
5. Keep the clean `fecg1` signal out of the algorithm input. It is only for evaluation.
6. Record any scaling, normalization, filtering, or time alignment performed.

### Channel/reference availability

The screenshots show source-component files, not enough metadata to prove which observed abdominal channels or thoracic reference channels are available. Read the headers and dataset documentation before selecting channel-dependent algorithms.

- Do not create artificial “independent channels” by copying, delaying, or re-mixing one observed signal merely to make ICA work.
- A method requiring a real thoracic reference may only be called a faithful reproduction if the appropriate reference is genuinely available.
- If a clean maternal component is used as a reference, report it separately as an **oracle-assisted upper-bound experiment**, not as a realistic extraction result.
- If only one abdominal mixture is available, use a single-channel method for the main comparison.

---

## 4. Member assignments

The assignments are by implementation workstream. Review papers support the work; they are not themselves algorithms to implement.

### Naman — SVD extraction and its three variants

**Primary paper file:** `Fetal_ECG_extraction_from_single-channel_maternal_ECG_using_singular_value_decomposition.pdf`

**Supporting paper file:** `A_Review_of_Signal_Processing_Techniques_for_Non-Invasive_Fetal_Electrocardiography(3).pdf`

Tasks:

1. Read the SVD paper's proposed extraction procedure and reproduce its terminology and assumptions.
2. Implement the three SVD variants described in the paper.
3. Document matrix construction, cycle/period handling, singular-value selection, and any SVR-based step.
4. Run all available TC1–TC5 cases using the shared mixture builder.
5. Record fetal waveform error, fetal R-peak metrics, runtime, and failure cases.
6. Do not tune a method separately on the clean fetal reference.

**Deliverable:** a runnable Python module, configuration/parameter notes, plots, and a results table for all SVD variants.

### Anshu — Maternal-template subtraction

**Primary paper file:** `A_Review_of_Signal_Processing_Techniques_for_Non-Invasive_Fetal_Electrocardiography(3).pdf`

**Supporting paper file:** `libroWiley(3).pdf`

**Additional reference:** `s12575-009-9006-z(2).pdf`

Tasks:

1. From the review, select and document one implementable template-subtraction approach.
2. Detect maternal R-peaks from the permitted mixture/input, align maternal beats, estimate a template, and subtract it.
3. If time permits, compare a fixed template with an adaptive/updateable template.
4. Record how errors in maternal R-peak detection affect fetal extraction, particularly when fetal and maternal QRS complexes overlap.
5. Run all available TC1–TC5 cases using the shared mixture builder.

**Important:** do not use the clean `mecg` component to build the normal template. If you do so for diagnostic purposes, label that run as oracle-assisted and do not compare it directly with deployable methods.

**Deliverable:** a runnable template-subtraction module, plots, parameter notes, and a results table.

### Astitva — Wavelet + adaptive filtering

**Primary paper file:** `1-s2.0-S0010482513002023-main(2).pdf`

**Supporting paper files:** `Signal_Processing_Techniques_for_Removin(2).pdf` and `Digital_Filters_for_Real-Time_ECG_Signal_Processing_Using_Microprocessors(3).pdf`

Tasks:

1. Reproduce the paper's SWT–LMS–SSNF processing sequence as closely as the available inputs allow.
2. Implement the SWT decomposition and LMS stage, then add the paper's wavelet-coefficient correlation/SSNF stage and inverse SWT reconstruction.
3. Run an ablation comparison: LMS alone versus the full hybrid method.
4. Check the paper's reference-input requirement. It uses a thoracic ECG reference; verify whether the selected data provides a valid one.
5. If no valid thoracic reference is available, do not claim a faithful reproduction. Either run an explicitly labelled oracle-assisted experiment using the clean maternal component as reference, or propose a clearly documented single-channel adaptation and evaluate it as a new method.
6. Run all available TC1–TC5 cases under the agreed input condition.

**Deliverable:** a runnable implementation, ablation results, plots, and a clear note describing which input/reference condition was used.

### Vivek — Alternative extraction baseline and data/channel audit

**Primary paper files:** `43407(2).pdf` and `s11042-022-13391-0(1).pdf`

**Supporting paper files:** `A_Review_of_Signal_Processing_Techniques_for_Non-Invasive_Fetal_Electrocardiography(3).pdf` and `Digital_Filters_for_Real-Time_ECG_Signal_Processing_Using_Microprocessors(3).pdf`

Tasks:

1. Inspect the `.hea` files and dataset documentation to establish the actual number and type of available channels, sample rates, gains, units and annotation format.
2. Implement one additional extraction method supported by the review and compatible with the actual input. Prefer a distinct single-channel method if only one mixture is available; if genuine multiple abdominal observations exist, ICA may be considered.
3. Treat the Sameni modeling paper primarily as background for mixture construction and evaluation. It is not, by itself, a complete ICA extraction algorithm to copy.
4. If using ICA, document the number of observed channels, number of components, component-selection rule, and how the fetal component is identified without using the clean fetal waveform as an input.
5. Run all available TC1–TC5 cases using the shared mixture builder.
6. Coordinate a shared evaluation script and final comparison table with the team.

**Deliverable:** a runnable additional-method module, data/channel audit, plots, results, and a brief FPGA feasibility note.

**Fallback:** if channel metadata does not support multichannel ICA, do not force ICA into the project. Select a single-channel method described in the review and document the choice before implementation.

---

## 5. Shared implementation rules

All members must follow these rules.

1. Use the same mixture-generation function and the same verified metadata.
2. Use the same sample interval for each test case.
3. Use the same documented preprocessing baseline where feasible. If a method requires special preprocessing, report it explicitly.
4. Do not give the clean fetal waveform or fetal reference annotations to the extraction algorithm.
5. Do not use a clean maternal component as an input in the main deployable-method comparison unless the method genuinely has a maternal reference channel in the intended setup.
6. Keep method-specific parameters in configuration files or documented constants; do not silently change them between SNR conditions.
7. Save the output waveform, detected fetal R-peaks, runtime, parameter settings, and plots for each run.
8. Report failed runs and failure cases; do not omit them from the comparison.
9. Separate algorithm development records from final evaluation records if parameters are tuned. Do not tune repeatedly against the same reference records and then report the result as an unbiased generalization test.

---

## 6. Required evaluation

### Fetal R-peak detection

Use a common fetal QRS detector for the extracted signals where practical, or document detector differences if a shared detector cannot be used. Choose and freeze a beat-matching tolerance in milliseconds before comparing results, and convert it to samples using the verified sampling frequency.

Report:

- **TP:** detected fetal beat matched to a reference fetal beat.
- **FP:** detected beat with no matching reference fetal beat.
- **FN:** reference fetal beat that was missed.
- **Sensitivity/Recall:** `TP / (TP + FN)`.
- **PPV/Precision:** `TP / (TP + FP)`.
- **F1-score:** `2 × Sensitivity × PPV / (Sensitivity + PPV)`.
- **False positives and false negatives:** report the counts as well as rates.
- **Heart-rate error:** compare fetal heart rate derived from detected R–R intervals with the reference, using the same interval/beat policy for all methods.

If a denominator is zero, report the metric as undefined rather than silently assigning a score.

### Waveform reconstruction

Because the clean fetal waveform is available in this synthetic setup, also evaluate the estimated fetal waveform against it. Before calculating waveform error:

1. Confirm the sampling rates and lengths match.
2. Document any time alignment.
3. Report raw-scale error and, separately if useful, a clearly defined normalized error.
4. Do not normalize away amplitude error without reporting that choice.
5. Use an explicitly defined SNR-improvement or reconstruction metric; do not use the name “SNR improvement” without stating its formula and signal/noise definition.

### Visual checks

For each test case, save:

1. Reconstructed abdominal mixture.
2. Clean fetal reference (evaluation only).
3. Extracted fetal waveform.
4. Reference and detected fetal R-peaks overlaid on a comparable time axis.
5. A zoomed region where maternal and fetal beats overlap, if present.
6. A short note identifying residual maternal QRS, missed fetal beats, false beats, waveform distortion, baseline drift, or other visible failures.

A visually clean trace is not enough by itself. The metrics and plots must agree, and failure cases must be discussed.

---

## 7. Common result table

Fill one row per method and test case. Include variants as separate rows.

| Member/method | Test | SNR | Case | Sensitivity | PPV | F1 | FP | FN | HR error | Waveform error | Runtime |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SVD variant 1 | TC1 | 12 dB | c0 | | | | | | | | |
| SVD variant 2 | TC1 | 12 dB | c0 | | | | | | | | |
| Template subtraction | TC1 | 12 dB | c0 | | | | | | | | |
| SWT–LMS–SSNF | TC1 | 12 dB | c0 | | | | | | | | |
| Vivek's selected method | TC1 | 12 dB | c0 | | | | | | | | |

Repeat for all available test cases. Add columns for preprocessing, channel/reference condition, and notes if a method's assumptions differ.

---

## 8. Final comparison and FPGA decision

Do not select the winner based on a single plot or only on F1-score.

Compare:

- Fetal beat sensitivity, PPV and F1 across all SNRs and cases.
- False positives and false negatives, especially around overlapping maternal/fetal beats.
- Waveform reconstruction error and preservation of fetal morphology.
- Robustness to the `c1` movement case and `c4` ectopic-beat case, if their files are available and those labels are confirmed by the dataset documentation.
- Runtime, memory, matrix dimensions, arithmetic complexity and parameter sensitivity.
- Whether the method supports streaming or requires a complete record/window.
- Fixed-point feasibility for the Spartan-7 FPGA.

The initial five tests are a development set, not sufficient evidence of broad generalization. Once the code works, extend testing across more subjects, SNRs, cases and repetitions. Keep the extension set separate from data used to tune parameters where possible.

---

## 9. Paper inventory and intended use

The filenames below are used as they appear in the project-file inventory. Check the repository if local copies use slightly different suffixes.

| Paper file | Intended use |
|---|---|
| `1-s2.0-S0010482513002023-main(2).pdf` | Reproduce SWT + LMS + SSNF |
| `43407(2).pdf` | Understand ECG mixture modeling and the paper's ICA illustration; support data/channel reasoning |
| `A_Review_of_Signal_Processing_Techniques_for_Non-Invasive_Fetal_Electrocardiography(3).pdf` | Main method taxonomy, assumptions and limitations |
| `Fetal_ECG_extraction_from_single-channel_maternal_ECG_using_singular_value_decomposition.pdf` | Reproduce the three SVD variants |
| `s11042-022-13391-0(1).pdf` | Cross-check extraction methods, metrics and dataset constraints |
| `s12575-009-9006-z(2).pdf` | Method inventory and detection/extraction background |
| `Digital_Filters_for_Real-Time_ECG_Signal_Processing_Using_Microprocessors(3).pdf` | Real-time digital filtering and implementation considerations |
| `libroWiley(3).pdf` | General ECG filtering, QRS detection and preprocessing |
| `Signal_Processing_Techniques_for_Removin(2).pdf` | Noise-removal/preprocessing reference |

The reviews are for finding and understanding methods. Do not try to implement every algorithm they mention in this first round.

---

## 10. Before declaring the benchmark ready

- [ ] Confirm exact paths for all five selected tests, especially `c1` and `c4`.
- [ ] Read the matching `.hea` files and verify format, sampling frequency, gain, units and lengths.
- [ ] Verify the `.qrs` annotation format and whether annotations are maternal or fetal.
- [ ] Confirm the documented mixture equation and scaling.
- [ ] Determine which genuine abdominal and thoracic channels are available.
- [ ] Freeze the shared preprocessing, beat-matching tolerance and evaluation definitions.
- [ ] Run a basic loader/mixer validation before comparing algorithms.
- [ ] Ensure all members use the same common test cases and report failed cases.

**Decision principle:** first make the input and evaluation protocol reliable; then compare methods. Otherwise, apparent algorithm improvements may actually come from different inputs, references, preprocessing or scoring rules.
