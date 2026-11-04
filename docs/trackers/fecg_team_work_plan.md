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

---

## 11. Added responsibilities: preprocessing, QRS detection, FHR, integration and verification

The extraction algorithms alone do not make a complete system. The following cross-cutting tasks now have named owners. Each owner is responsible for the shared module and its tests, while all members must use the same version.

### Ownership matrix

| Owner | Primary extraction work | Additional shared responsibility | Required output |
|---|---|---|---|
| **Naman** | SVD variants | **Integration lead and common interface** | Connect loader → preprocessing → extraction → QRS detector → FHR → evaluation; maintain the shared method interface and integration checklist |
| **Anshu** | Template subtraction | **Fetal QRS detector** | Implement and independently test one common fetal QRS detector, including peak indices/timestamps, duplicate-peak handling and overlap/failure analysis |
| **Astitva** | SWT–LMS–SSNF | **Shared preprocessing module** | Implement the common preprocessing baseline, validate filters and edge effects, freeze and document parameters |
| **Vivek** | Additional method compatible with available channels | **Dataset validation, mixture verification and evaluation/FHR metrics** | Verify headers, channel/reference availability, mixture construction, annotation semantics; implement FHR calculation and the shared metric/evaluation script |

This is an ownership split, not permission for one person to work in isolation. All four members must review the interface and verify that their own algorithm passes the shared automated tests.

### Naman — integration lead

In addition to the SVD work:

1. Create and maintain the shared repository structure described below.
2. Define one common function interface for every extraction method.
3. Integrate all methods with the same loader, preprocessing, QRS detector and evaluation script.
4. Ensure every test run saves its method name, variant, test ID, parameters, software version, outputs and metrics.
5. Track blockers and run the final integration test; do not silently change another member's algorithm to make it pass.

**Suggested interface:** each extraction module receives a documented input signal plus a configuration object and returns an estimated fetal waveform and metadata. A method requiring additional reference channels must declare those inputs explicitly. It must not silently read the clean fetal reference or maternal ground-truth component.

### Anshu — common fetal QRS detector

In addition to template subtraction:

1. Implement a common detector for the **extracted fetal waveform**, not a detector that uses the clean fetal signal.
2. Use the project's PPR-8 detector proposal as the initial reference: band-pass filtering, squaring, moving-window integration, adaptive thresholding and refractory-period logic. Confirm the exact frequency limits and window/threshold parameters from PPR-8 before freezing them; do not invent them.
3. Return detected R-peak sample indices and timestamps.
4. Handle duplicate detections and define how peaks that are too close together are treated.
5. Test the detector separately on the clean fetal reference as a diagnostic check, but do not use that diagnostic result as the extraction result.
6. Test the detector on outputs from every member's method using the same detector configuration.

**Deliverable:** one shared detector function, documented parameters, automated tests and a short detector-failure report.

### Astitva — common preprocessing

In addition to SWT–LMS–SSNF:

1. Inspect the sampling rate and signal units before filtering.
2. Implement the agreed baseline preprocessing pipeline. Candidate stages are baseline-wander removal, a power-line notch filter only if the dataset actually contains relevant interference, and a band-pass filter appropriate to the intended ECG/QRS analysis.
3. Use the same baseline preprocessing configuration for all extraction methods wherever technically appropriate.
4. Document each filter's type, order, cutoff frequencies, notch frequency/Q, phase behavior, and handling of signal edges. Do not apply zero-phase offline filtering and then claim the same result is available in a causal real-time FPGA pipeline.
5. Plot and test the filter's frequency response and compare waveforms before/after filtering.
6. Freeze the shared preprocessing configuration before final benchmark runs. Method-specific extra transforms must be documented separately.

**Deliverable:** one reusable preprocessing function, a configuration file, frequency-response plots, and a short note on waveform distortion and edge artifacts.

### Vivek — data validation, FHR and shared evaluation

In addition to the selected alternative extraction method:

1. Validate `.hea`/`.dat` consistency, sample frequency, sample count, gain/units, channel count, missing/non-finite values and time alignment.
2. Confirm the official mixture equation, component scaling and SNR definition from dataset documentation. Implement a pass/fail check for the shared mixture builder.
3. Verify whether `.qrs` files annotate fetal beats, maternal beats, or another signal. Record the annotation convention and index/time units.
4. Verify exact existence and case labels for all five tests, especially `c1` and `c4`.
5. Determine whether real multi-channel abdominal recordings and a real thoracic reference are available. Record the result before ICA or reference-based adaptive filtering is selected.
6. Implement FHR calculation from the detected fetal R–R intervals and compare it with reference FHR.
7. Implement the common evaluation script: TP/FP/FN matching, sensitivity, PPV, F1, waveform error, FHR error and runtime.

**FHR calculation rules:**

- For consecutive detected fetal peaks at times \(t_i\) and \(t_{i+1}\), calculate \(RR_i=t_{i+1}-t_i\) seconds and \(FHR_i=60/RR_i\) BPM.
- Save an FHR-versus-time series.
- Define a consistent rule for implausible intervals and missed/extra beats; do not silently delete inconvenient intervals.
- Compare against reference fetal annotations using the same interval policy for every method.
- Report both beat-detection performance and FHR error. Good FHR alone does not prove good waveform extraction.

**Deliverable:** a data-validation report, verified mixture builder, FHR module, evaluation script and a machine-readable result table.

---

## 12. Shared code structure and method interface

Use one common repository structure so that methods can be run interchangeably. The names below are proposed and can be adjusted to the current repository, but the responsibilities must remain separate.

```text
project/
├── data/                     # data location/configuration; do not commit large raw data unnecessarily
├── configs/
│   ├── tests.yaml            # TC1–TC5 paths and metadata
│   └── preprocessing.yaml    # frozen common filter settings
├── src/
│   ├── data_loader.py        # read headers/data and validate metadata
│   ├── mixture.py            # verified mixture reconstruction
│   ├── preprocessing.py      # shared preprocessing (Astitva)
│   ├── qrs_detector.py       # common fetal QRS detector (Anshu)
│   ├── fhr.py                # FHR calculation (Vivek)
│   ├── evaluation.py         # common metrics (Vivek)
│   ├── methods/
│   │   ├── svd.py            # Naman
│   │   ├── template_subtraction.py  # Anshu
│   │   ├── swt_lms_ssnf.py   # Astitva
│   │   └── alternative.py    # Vivek
│   └── run_benchmark.py      # integrated execution (Naman)
├── tests/
│   ├── test_loader.py
│   ├── test_mixture.py
│   ├── test_qrs_matching.py
│   ├── test_fhr.py
│   └── test_metrics.py
└── results/
    ├── plots/
    ├── metrics.csv
    └── run_metadata.json
```

Do not commit the full database or generated outputs blindly. Keep the selected test IDs and local data paths in configuration so each member can run the same tests.

### Standard extraction interface

Each method must document:

- Input waveform(s) and required reference channels.
- Sampling frequency and units expected.
- Output waveform length and units.
- Whether the method is offline, windowed, or causal/streaming.
- Parameters and random seeds, if applicable.
- Any additional input that would make its result an oracle-assisted experiment.

Every method must return a result in the same format so the benchmark runner can call it without custom logic for each member.

---

## 13. Freeze the evaluation rules before comparing methods

### QRS matching

- Use the PPR-8 specification's **±50 ms** beat-matching tolerance as the initial rule.
- Convert milliseconds to samples using the verified sampling rate.
- Match each reference beat to at most one detection and each detection to at most one reference beat.
- Resolve duplicate detections consistently; do not count one detected beat as multiple true positives.
- If the team changes the tolerance, document the reason and rerun every method with the same new value.

### Metrics

For every method and test case, report:

- TP, FP and FN counts.
- Sensitivity/recall, PPV/precision and F1.
- False detections and missed beats.
- FHR mean absolute error in BPM and, if appropriate, error over time.
- Waveform error after documented alignment.
- Runtime under the same machine/software conditions.
- The input condition: single abdominal mixture, genuine multichannel observations, or reference-assisted experiment.

If a metric has a zero denominator, report it as undefined and explain why; do not silently assign a perfect score.

### Waveform comparison

- Verify the reference and estimate use the same sampling rate and compatible lengths.
- Document time alignment and any resampling.
- Report raw-scale error. If normalized error is also reported, show the normalization separately.
- State the exact formula for any SNR-improvement measure.
- Preserve the clean fetal component only for evaluation; never use it to tune or select a component inside the extraction algorithm.

---

## 14. Automated checks and acceptance criteria

Before the benchmark is considered ready, the following tests must pass.

| Check | Owner | Pass condition |
|---|---|---|
| Header/data loader | Vivek | Sample rate, lengths, channels and units are parsed/validated; malformed or inconsistent files produce a clear error |
| Test inventory | Vivek | Exact paths for TC1–TC5 are confirmed; unavailable cases are marked pending rather than substituted silently |
| Mixture reconstruction | Vivek | Equation/scaling are documented and the reconstruction passes a documented consistency check |
| Preprocessing | Astitva | Filter settings are frozen; frequency response and edge behavior are checked |
| QRS detector | Anshu | Returns valid, sorted sample indices; duplicate handling and tolerance are tested |
| FHR calculation | Vivek | Known synthetic peak intervals produce the expected BPM; invalid intervals are handled according to the documented policy |
| Metric calculations | Vivek | Hand-checkable TP/FP/FN examples produce correct sensitivity, PPV and F1 |
| Method interface | Each method owner; coordinated by Naman | Each method returns the common output format for a smoke-test record |
| End-to-end integration | Naman | Every available method runs through the same pipeline and produces outputs, metrics and run metadata |
| Reproducibility | All; tracked by Naman | A second run with the same code/configuration reproduces the same outputs within the stated numerical tolerance |

**Midterm acceptance criteria:** no method is considered integrated merely because its algorithm works in an isolated notebook. It must load the shared test input, return the required output format, run through the common detector/evaluation path, and save results for at least TC1. The final benchmark milestone requires all available TC1–TC5 cases, with any unavailable test explicitly documented.

---

## 15. Schedule and progress tracking

Use milestone-based deadlines relative to the team's actual project schedule rather than inventing calendar dates.

| Milestone | Owner(s) | Completion evidence |
|---|---|---|
| M1 — Data and channel audit | Vivek; all members review | Verified headers, mixture equation, channel availability, annotation semantics and test inventory |
| M2 — Shared pipeline skeleton | Naman | Common interface, configuration, runner and output format committed |
| M3 — First baseline works | Anshu + Vivek | Template baseline and detector/FHR/evaluation run on TC1 |
| M4 — All primary methods run on TC1 | All method owners | Saved waveform, peaks, metrics and run metadata for each method |
| M5 — Preprocessing and test suite frozen | Astitva + Vivek | Filter config, automated tests and metric definitions committed |
| M6 — Full initial benchmark | All; Naman integrates | Results for every available TC1–TC5 case and failure analysis |
| M7 — Selection and FPGA preparation | All; Naman coordinates | Winner decision table, runtime/memory profile and fixed-point test plan |

Track every task as **Not started / In progress / Blocked / Complete**. A task can be marked complete only when its code or report, test evidence and parameter/configuration notes are committed or shared with the team.

---

## 16. Algorithm priority and selection rule

The PPR-8 project description makes template subtraction and LMS adaptive filtering the core comparison, with PCA/ICA as future extensions. Therefore:

1. **Required core comparison:** template subtraction versus LMS adaptive filtering, using the same valid input condition.
2. **Research extension:** SVD variants and the complete SWT–LMS–SSNF method.
3. **Conditional extension:** Vivek's alternative method, selected only after channel availability is verified.
4. If the project schedule becomes tight, finish the core comparison and full evaluation pipeline before adding more methods.

Do not call a method the overall winner based only on F1 or on one high-SNR case. Compare performance across the test matrix, waveform preservation, false/missed beats, runtime, memory, robustness, and FPGA suitability. Agree on any minimum performance requirement before inspecting the final results; do not invent a threshold after seeing which method wins.

---

## 17. FPGA preparation and software-to-hardware verification

Once the software benchmark is stable, the team must prepare a reproducible hardware reference.

- Profile runtime and estimate operations per sample, memory and buffering needs.
- Identify matrix decompositions, divisions, adaptive updates and other expensive operations.
- Choose a proposed fixed-point format, word lengths, scaling and rounding/saturation policy.
- Compare fixed-point Python results against floating-point outputs on identical test vectors.
- Quantify changes in waveform error, QRS sensitivity/PPV/F1 and FHR error.
- Save test vectors and expected outputs for later RTL simulation and hardware verification.
- Clearly distinguish estimated hardware feasibility from measured synthesis/timing results; do not claim FPGA performance before implementation.

---

## 18. Final checklist

- [ ] Confirm all five selected test paths, especially `c1` and `c4`.
- [ ] Verify metadata, units, lengths and sampling frequency.
- [ ] Verify mixture equation, scaling and SNR convention.
- [ ] Verify QRS annotation meaning and time/index convention.
- [ ] Confirm actual abdominal and thoracic reference channels.
- [ ] Freeze common preprocessing settings.
- [ ] Freeze QRS matching tolerance at ±50 ms unless formally revised.
- [ ] Implement and test fetal QRS detection and FHR calculation.
- [ ] Run automated tests for loader, mixture, detector, FHR and metrics.
- [ ] Integrate every method through the same pipeline.
- [ ] Record failed cases, parameter settings and run metadata.
- [ ] Compare template subtraction versus LMS as the core experiment.
- [ ] Complete all available initial test cases before selecting a winner.
- [ ] Prepare fixed-point and software-to-hardware test vectors only after the software reference is stable.

**Final principle:** reliable input construction, shared detection and evaluation, and integration ownership are just as important as the extraction algorithms. A method comparison is valid only when differences in results are caused by the methods—not by different input signals, preprocessing, reference information or scoring rules.
