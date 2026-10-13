# Fetal ECG Extraction + FHR on FPGA — Team Implementation Plan

**Team:** Naman, Astitva, Anshu, Vivek
**Course:** EE2000 Signal Processing, IIT Hyderabad (Fall 2026)
**Plan written:** 13 Oct 2026

> The role assignment is a suggestion based on a natural split of the pipeline. Swap roles freely, but keep exactly one owner per block.
> **Verify deadlines against the professor's instruction document** (the file did not come through when this plan was drafted).

---

## 0. Deadlines (verify against professor's document)

| Date | Milestone |
|---|---|
| **25 Oct 2026 (Sun)** | Mid-term report: further literature review, replicated results, preliminary results, code |
| **13 Nov 2026 (Fri)** | Final report: algorithm, results, conclusions, code |
| TBD | Project presentation / viva on the Boolean Board |
| — | AI policy: AI-generated parts must be clearly indicated and cited; every member must be able to explain and defend them in the viva |

---

## 1. Goal of the next 12 days

Build **one common Python pipeline** in which only the maternal-ECG cancellation step is swappable, then use it to find out which cancellation method works best on FECGSYNDB (and a first check on NIFEADB).

```
load data → preprocess → [maternal cancellation: LMS | template | (wavelet/ICA)]
          → fetal QRS detector → RR / FHR → evaluate vs annotations
```

The result is a **fair comparison table** (same records, same noise levels, same metrics) that:
1. Is the main evidence for the mid-term report.
2. Decides which algorithm goes to fixed-point and Verilog.

---

## 2. Roles at a glance

| Person | Software role (13–24 Oct) | FPGA role (26 Oct onward) |
|---|---|---|
| **Naman** | **Data + evaluation harness lead**: loaders, plots, metrics, experiment runner, results tables | **RTL integration lead**: top-level, input interface (UART/BRAM), testbenches, RTL-vs-Python comparison |
| **Astitva** | **Preprocessing + fetal QRS detector + FHR** | Verilog for filters, detector, RR/FHR blocks |
| **Anshu** | **LMS / NLMS adaptive cancellation** | Fixed-point LMS model → Verilog LMS filter |
| **Vivek** | **Template subtraction** (maternal QRS detect, template, subtract); optional wavelet/ICA baseline | Fixed-point range analysis for the full chain, NIFEADB validation runs, Verilog for the remaining blocks, hardware/resource section of report |

**Why this split:** Anshu and Vivek implement your two candidate approaches, so you get a genuine comparison. Astitva's detector is shared by both. Naman's harness keeps everything comparable and later becomes the golden-reference and testbench infrastructure.

---

## 3. Shared rules (everyone)

1. **One shared GitHub repo.** Each block lives in its own file with **one owner**. Changes to someone else's file go through a pull request and that owner's review.
2. **`CONTEXT.md`** in the repo root = your three markdown files + the interface contract below. Every LLM session starts by reading it, so all four LLMs work from the same assumptions.
3. **`AI_USAGE.md`**: log of every AI-generated or AI-assisted file/section (file, tool, what it generated, who reviewed and understood it). Required by the course policy.
4. **Never tune on the validation data.** Develop and tune parameters on FECGSYNDB; use NIFEADB for validation only.
5. **Same protocol for every method:** same records, same channels, same tolerance window, same metrics. Never compare numbers from different protocols.
6. **Every function must run on a plain NumPy array and return a NumPy array**, so blocks plug together and later map cleanly to hardware.
7. **Understand your own code.** Each person must be able to explain every line of their block at the viva, including the AI-written parts.

### Suggested repo structure

```
fecg/
├── CONTEXT.md
├── AI_USAGE.md
├── README.md
├── requirements.txt            # numpy scipy matplotlib wfdb pywt (as needed)
├── data/                       # NOT committed (large); README says how to download
├── src/
│   ├── io_data.py              # Naman   : loaders
│   ├── metrics.py              # Naman   : Se, PPV, F1, FHR error, SNR measures
│   ├── plotting.py             # Naman
│   ├── preprocess.py           # Astitva : baseline, notch, band-pass
│   ├── fqrs_detect.py          # Astitva : fetal QRS detector
│   ├── fhr.py                  # Astitva : RR + FHR + validation
│   ├── cancel_lms.py           # Anshu   : LMS / NLMS
│   ├── cancel_template.py      # Vivek   : template subtraction
│   ├── cancel_wavelet_ica.py   # Vivek   : optional baselines
│   └── pipeline.py             # Naman   : glue code, swappable cancellation
├── experiments/
│   ├── 01_explore_data.ipynb
│   ├── 02_detector_on_groundtruth.py
│   ├── 03_compare_methods.py
│   └── 04_nifeadb_validation.py
├── results/                    # tables, figures (committed, small)
├── fixedpoint/                 # later: fixed-point models
├── rtl/                        # later: Verilog
├── tb/                         # later: testbenches
└── report/
```

### Interface contract (agree on this on Day 1)

```python
# All signals: 1-D numpy float arrays at the dataset's native sampling rate fs.
# All detections: 1-D numpy int arrays of SAMPLE INDICES (not seconds).

# preprocess.py
def preprocess(x, fs, **params) -> np.ndarray: ...

# cancel_*.py  (every cancellation method has the SAME signature)
def cancel(x_abd, fs, x_ref=None, **params) -> np.ndarray:
    """Return residual / fetal-enhanced signal (same length as x_abd)."""

# fqrs_detect.py
def detect_fqrs(x_fetal, fs, **params) -> np.ndarray:   # R-peak sample indices

# fhr.py
def rr_and_fhr(peaks, fs, **params) -> (rr_samples, fhr_bpm, valid_mask)

# metrics.py
def evaluate(det_idx, ref_idx, fs, tol_ms=50) -> dict:
    # returns TP, FP, FN, Se, PPV, F1, mean timing error (ms)
def fhr_error(fhr_det, fhr_ref) -> dict:   # MAE, RMSE, max error
```

Decide these values once and write them in `CONTEXT.md`:
- **Tolerance window:** 50 ms (state it before any scoring; do not change it afterward to improve numbers).
- **Fetal detection plausibility range:** about 100–200 bpm (so arrhythmia records are not accidentally rejected); fetal RR ≈ 300–600 ms.
- **Refractory period:** about 150–200 ms after a fetal detection.

---

## 4. Timeline

| Dates | Phase | Goal |
|---|---|---|
| **13–15 Oct** | Foundation | Repo, loaders, first plots, metrics function, detector run on ground-truth fetal ECG |
| **16–22 Oct** | Block development | Each block works in floating point on FECGSYNDB; first end-to-end run by 19–20 Oct |
| **23–24 Oct** | Integration + mid-term report | Comparison table, figures, written report |
| **25 Oct** | **Mid-term submission** | |
| **26 Oct–1 Nov** | Validation + decision + start of hardware | NIFEADB validation, **choose FPGA algorithm**, fixed-point model, first Verilog blocks |
| **2–9 Nov** | RTL integration | Simulation vs fixed-point model, then Boolean Board |
| **10–12 Nov** | Finalize | Final report, viva preparation, buffer |
| **13 Nov** | **Final submission** | |

### Team sync points (15–20 minutes each)

| Date | Purpose |
|---|---|
| **15 Oct** | Confirm foundation works: everyone can run the same example end to end on one record |
| **19 Oct** | First end-to-end run; find interface mismatches early |
| **22 Oct** | Freeze results; assign mid-term report sections |
| **1 Nov** | **Algorithm decision meeting** for the FPGA |
| **6 Nov** | RTL status check; decide what is cut if time is short |
| **10 Nov** | Final report assembly and viva rehearsal |

---

## 5. Person-by-person plan

---

### 5.1 NAMAN — Data, evaluation harness, later RTL integration lead

**Owns:** `io_data.py`, `metrics.py`, `plotting.py`, `pipeline.py`, `experiments/`, later `tb/` and top-level RTL.

#### Phase 1 (13–15 Oct): foundation (everyone depends on this)
- [ ] Create the repo, folder structure, `CONTEXT.md`, `AI_USAGE.md`; invite all four.
- [ ] Download both datasets; write a `data/README.md` with exact download steps and paths.
- [ ] `io_data.py`:
  - [ ] Load FECGSYNDB record: abdominal channels, maternal reference channels, ground-truth fetal / maternal / noise components, and QRS annotations (check dataset documentation for exact file layout and channel numbering).
  - [ ] Load NIFEADB (WFDB `.dat` / `.hea`) with `wfdb`: abdominal channels, maternal chest channel, fs (500 Hz or 1 kHz).
  - [ ] Return a simple dict, e.g. `{"fs", "abd", "mref", "fecg_gt", "mecg_gt", "noise_gt", "fqrs_ref"}`.
- [ ] `plotting.py`: raw channels, spectra (PSD), overlay detections on signal.
- [ ] `experiments/01_explore_data.ipynb`: plot one record at each noise level; show maternal vs fetal amplitude, spectra, reference channels.
- [ ] `metrics.py`:
  - [ ] Match detections to reference within the tolerance window (one-to-one matching; each reference beat can match at most one detection).
  - [ ] TP / FP / FN, Se, PPV, F1, mean timing error.
  - [ ] FHR error: MAE, RMSE, max error, % of time within ±X bpm.
  - [ ] Signal-level (FECGSYNDB only): correlation with ground-truth FECG, MSE, SNR before/after.
  - [ ] **Unit tests** with hand-made cases (perfect, one miss, one extra, one shifted beat). Wrong metrics invalidate everything.
- [ ] `pipeline.py`: `run_pipeline(record, cancel_fn, params)` that chains preprocess → cancel → detect → FHR → evaluate.

**Deliverable by 15 Oct:** the other three can `import` the loaders and metrics and run on a record.

#### Phase 2 (16–22 Oct): experiments
- [ ] `experiments/03_compare_methods.py`: loop over the chosen set of FECGSYNDB records × noise levels × methods; save a CSV and summary table.
- [ ] Choose and document the evaluation subset (e.g., a fixed list of records and channels) and keep it constant.
- [ ] Produce figures: example before/after, Se/PPV/F1 vs noise level per method, FHR plot vs reference.
- [ ] Run a **"no cancellation" baseline** (detector applied directly on the abdominal signal) so improvement is measurable.

#### Phase 3 (23–24 Oct): mid-term report
- [ ] Assemble the results section, figures, tables; merge everyone's text; check formatting and references.

#### Phase 4 (26 Oct onward): hardware verification lead
- [ ] Python script to export test vectors (`.mem` / `.hex` / `.txt`) from the fixed-point model: input samples + expected outputs at every block boundary.
- [ ] Top-level Verilog: input interface (BRAM/ROM playback and/or UART), output interface, sample-rate enable generation.
- [ ] Testbenches: feed vectors, dump outputs, compare with expected (script `compare_rtl_vs_python.py`).
- [ ] Board bring-up on Boolean Board; capture outputs; compare with the fixed-point model.
- [ ] Viva demo flow: what is streamed in, what is displayed (LEDs/UART/etc.).

**Acceptance criteria:** metrics unit tests pass; the comparison script runs with one command; same protocol for all methods.

---

### 5.2 ASTITVA — Preprocessing, fetal QRS detector, FHR

**Owns:** `preprocess.py`, `fqrs_detect.py`, `fhr.py`. Later: Verilog for filters, detector, RR/FHR.

#### Phase 1 (13–15 Oct)
- [ ] Study the QRS detector structure (band-pass → nonlinear → decision) from Sörnmo & Laguna and Ahlstrom & Tompkins notes.
- [ ] Implement a first detector and **test it on the ground-truth fetal ECG** (clean `fecg_gt`) from FECGSYNDB. This is the **upper bound**: if it fails here, it will fail everywhere.
- [ ] Report Se/PPV/F1 on the ground truth using Naman's metrics.

#### Phase 2 (16–22 Oct)
- [ ] `preprocess.py`: 
  - [ ] Baseline-wander removal (high-pass; choose cutoff experimentally).
  - [ ] 50 Hz notch (India mains) — **test whether it is needed**; if the band-pass already attenuates 50 Hz, drop it.
  - [ ] Band-pass. Experiment with passband; fetal QRS energy is typically at higher frequencies than maternal, so check experimentally rather than assume.
  - [ ] Keep filter choices hardware-friendly: FIR with power-of-two-friendly coefficients, or the integer-arithmetic filters from Ahlstrom & Tompkins.
- [ ] `fqrs_detect.py`: 
  - [ ] Pipeline: band-pass → square (or absolute value) → moving-window integration → threshold → peak picking → refractory period.
  - [ ] **Version 1: fixed threshold.** **Version 2: adaptive threshold** (running estimates of signal/noise peak levels).
  - [ ] Refine peak location on the filtered signal (local max within a small window) so timing error stays inside the tolerance.
- [ ] `fhr.py`: 
  - [ ] RR in samples: `N[n] = idx[n+1] - idx[n]`; `FHR = 60 * fs / N`.
  - [ ] Validation: reject out-of-range RR, flag implausible jumps relative to previous RR, handle missed beats (RR ≈ 2× expected) and extra beats.
  - [ ] Optional smoothing (median or short moving average).
- [ ] Parameter sweeps (threshold factor, window length, passband) on FECGSYNDB only; log the chosen values and why.
- [ ] Keep a **list of operations used** (multiplies, divides, comparisons, window lengths) — Vivek and Naman need it for hardware planning.

#### Phase 3 (23–24 Oct)
- [ ] Write: preprocessing and detector method description, parameter table, ground-truth upper bound result, failure-case analysis (what causes FP / FN).

#### Phase 4 (26 Oct onward): hardware
- [ ] Verilog: baseline-removal/band-pass filter blocks, squaring, moving-average, adaptive threshold, refractory counter, RR counter, FHR calculation (reciprocal LUT or integer divider).
- [ ] Block-level testbenches against the fixed-point model with Naman's vectors.

**Acceptance criteria:** on clean ground-truth fetal ECG, detector reaches near-perfect Se/PPV; detector parameters are frozen before any NIFEADB testing.

---

### 5.3 ANSHU — LMS / NLMS adaptive maternal cancellation

**Owns:** `cancel_lms.py`. Later: fixed-point LMS model and Verilog LMS filter.

#### Phase 1 (13–15 Oct)
- [ ] Understand the structure: primary input `d[n]` = abdominal channel; reference input `x[n]` = maternal reference (thoracic) channel; filter output `y[n]` = estimated maternal ECG in the abdomen; error `e[n] = d[n] − y[n]` = **fetal estimate**.
- [ ] Equations:
  ```
  y[n] = w[n]^T x_vec[n]
  e[n] = d[n] − y[n]
  w[n+1] = w[n] + μ e[n] x_vec[n]                  # LMS
  w[n+1] = w[n] + μ e[n] x_vec[n] / (ε + ||x_vec||²)  # NLMS
  ```
- [ ] Implement LMS from scratch in NumPy (not only `adaptfilt`) — you will need to replicate it in fixed point and Verilog, and you must be able to explain it in the viva. A library version can be used as a cross-check.

#### Phase 2 (16–22 Oct)
- [ ] `cancel_lms.py` with the common signature `cancel(x_abd, fs, x_ref, **params)`.
- [ ] Sweep: **filter length** (e.g., 8, 16, 32, 64 taps), **step size μ** (several decades), LMS vs NLMS.
- [ ] Check **convergence**: plot the error power over time; discard or exclude the initial convergence period consistently in the metrics (agree with Naman on how).
- [ ] Check **fetal preservation**: does the residual keep the fetal QRS (use ground-truth FECG on FECGSYNDB)? Report correlation and SNR improvement.
- [ ] Check which maternal reference works best: the two reference channels individually, and possibly both as a 2-input filter.
- [ ] Try cascading: preprocess → LMS → detector, and also LMS on the raw vs filtered signals; record which order works better.
- [ ] Record **hardware-relevant numbers**: number of taps, multiplies per sample, coefficient range seen during adaptation, error/signal dynamic ranges.

#### Phase 3 (23–24 Oct)
- [ ] Write: LMS method, equations, parameter sweep results, convergence plots, strengths/limits (needs a reference channel; step-size tradeoff: faster adaptation ≠ better, from Ahlstrom & Tompkins).

#### Phase 4 (26 Oct onward)
- [ ] Fixed-point LMS model in Python: choose Q-format for samples, weights, accumulator; handle saturation/rounding; compare to float via detections and FHR.
- [ ] Verilog LMS: delay line, MAC (DSP slice), weight update, weight memory; test against the fixed-point model.
- [ ] Note: NLMS needs a division; consider a power-of-two step size or a normalization approximation if division is too costly.

**Acceptance criteria:** LMS improves Se/PPV vs the no-cancellation baseline on FECGSYNDB across noise levels; parameters selected only on FECGSYNDB.

---

### 5.4 VIVEK — Template subtraction (+ optional wavelet/ICA), fixed-point analysis, validation

**Owns:** `cancel_template.py`, optionally `cancel_wavelet_ica.py`. Later: fixed-point range analysis, NIFEADB validation, hardware/resource section.

#### Phase 1 (13–15 Oct)
- [ ] Understand the template-subtraction pipeline from the literature notes:
  ```
  detect maternal QRS → segment PQRST around each → align → average → template
  → subtract (scaled) from each maternal beat region → residual
  ```
- [ ] Prototype maternal R-peak detection. **Easiest first step:** detect on the maternal reference channel (maternal QRS is large there). Later, test maternal detection on the abdominal channel alone (the single-channel case).

#### Phase 2 (16–22 Oct)
- [ ] `cancel_template.py` with the common signature `cancel(x_abd, fs, x_ref=None, **params)`.
  - [ ] Segment window around each maternal R-peak (cover P, QRS, T; check lengths using maternal RR).
  - [ ] Template = average of the last N aligned beats (N = 5 to 20 sweeps) — a **causal, running** template, since hardware cannot see future beats.
  - [ ] Per-beat amplitude scaling (least-squares fit of template to the beat) to handle beat-to-beat variation.
  - [ ] Test alignment accuracy: a one-sample misalignment leaves a large residual.
- [ ] Study failure cases: fetal QRS overlapping a maternal QRS; maternal morphology change; maternal detection errors.
- [ ] Compare: reference-channel-based maternal detection vs abdominal-only.
- [ ] **Optional baseline (software only):** wavelet denoising + template, or PCA/ICA across abdominal channels, to show how the simple methods compare with the more complex ones. Do this only if the main task is done.
- [ ] Record **hardware-relevant numbers**: template length in samples, memory needed, operations per sample.

#### Phase 3 (23–24 Oct)
- [ ] Write: template-subtraction method, results, failure analysis. Also write the extended literature-review portion (BSS/ICA, wavelets, hybrid methods; datasets) for the mid-term.

#### Phase 4 (26 Oct onward)
- [ ] **NIFEADB validation:** run the frozen pipeline and parameters on the real recordings (normal and arrhythmia); report Se/PPV/F1 and FHR error; no re-tuning on these.
- [ ] **Fixed-point range analysis for the whole chain:** table of min/max values at every stage → integer bits, fractional bits, accumulator widths.
- [ ] Verilog for remaining blocks as needed (if LMS is selected for hardware: help with detector-side blocks or the template-based fallback).
- [ ] Hardware/resource section of the final report (LUT, FF, BRAM, DSP, Fmax, latency, throughput vs fs).

**Acceptance criteria:** template method runs on the same records and metrics as LMS; the template is causal (usable in streaming); NIFEADB results are reported without tuning.

---

## 6. Week-by-week checklist

### 13–15 Oct — foundation
| Who | Task |
|---|---|
| Naman | Repo, loaders, plots, metrics + unit tests, `CONTEXT.md`; share by 15 Oct |
| Astitva | First detector on ground-truth fetal ECG (upper bound) |
| Anshu | LMS from scratch on one record, one channel |
| Vivek | Maternal R-peak detection on the reference channel; first template |
| All | Read the relevant literature notes; log AI use |

### 16–22 Oct — blocks
| Who | Task |
|---|---|
| Naman | Experiment runner, baseline (no cancellation), figures |
| Astitva | Full preprocessing + adaptive-threshold detector + FHR validation |
| Anshu | LMS/NLMS sweeps, convergence, fetal preservation |
| Vivek | Causal template with per-beat scaling, failure analysis |
| All | **19 Oct:** first end-to-end run through `pipeline.py` |

### 23–24 Oct — integrate and report
| Who | Task |
|---|---|
| Naman | Comparison table, figures, assemble the report |
| Astitva | Detector + preprocessing sections |
| Anshu | LMS section |
| Vivek | Template section + extended literature review |
| All | Proofread; AI-usage statement; code cleanup; push to repo |

### 26 Oct–1 Nov — decide and prepare hardware
| Who | Task |
|---|---|
| Naman | Test-vector export, top-level skeleton, testbench framework |
| Astitva | Verilog filters + detector start; detector fixed-point model |
| Anshu | Fixed-point LMS model |
| Vivek | NIFEADB validation; range-analysis table |
| All | **1 Nov:** algorithm decision |

### 2–9 Nov — RTL
| Who | Task |
|---|---|
| Naman | Integration, board bring-up, RTL-vs-model comparison |
| Astitva | Detector + RR/FHR RTL verified |
| Anshu | LMS RTL verified |
| Vivek | Resource/timing analysis, fixes, extra validation |

### 10–12 Nov — finish
All: final report, code cleanup, demo rehearsal, viva Q&A practice (each person explains every block).

---

## 7. Mid-term report outline (25 Oct)

1. Introduction and problem statement (reuse the preliminary report, shortened)
2. Extended literature review (adaptive filtering, template subtraction, wavelets, BSS/ICA; datasets; metrics)
3. Datasets and experimental protocol (records, channels, tolerance, metrics, development/validation split)
4. Methods: preprocessing, LMS cancellation, template subtraction, fetal QRS detection, FHR
5. Replicated / preliminary results: comparison table (no-cancellation vs LMS vs template), figures per noise level, FHR plots
6. Discussion: strengths, failure cases, implications for hardware
7. Remaining work and plan to the final report
8. References + **AI usage statement**
9. Code link/appendix

---

## 8. Decision rule for the FPGA algorithm (1 Nov)

Pick the method using **both** performance and hardware cost:

| Criterion | LMS | Template subtraction |
|---|---|---|
| Needs a maternal reference channel | Yes | Optional (can use abdominal only) |
| Streaming-friendly | Yes (sample by sample) | Needs maternal beat detection + stored template |
| Hardware resources | Delay line + MAC + weight update | Template memory + alignment logic + scaling |
| Risk | Step-size tuning, fixed-point weights | Alignment errors, beat overlap |

Choose the one with a clearly better Se/PPV; if they are close, choose the simpler one in hardware. Keep the other as a software comparison result in the report.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Interfaces don't match when integrating | 15 Oct and 19 Oct sync points; everyone uses `pipeline.py` early |
| Metrics bugged | Unit tests first; second person re-derives one example by hand |
| Overfitting parameters to test data | Tune on FECGSYNDB only; freeze before NIFEADB |
| Cancellation works on synthetic but fails on real | Report honestly; use failure analysis in the report |
| Hardware work pushed to the last week | Detector/FHR Verilog starts 26 Oct, independent of which cancellation wins |
| Quantization breaks detection | Fixed-point model compared against float using detections and FHR, not just waveforms |
| One person blocked | Daily 5-line status in the group chat: done / doing / blocked |
| Viva: member can't explain AI-written code | Each person explains their block to another member before submission |

---

## 10. Daily working habit

Post in the group chat each day:
```
Done: ...
Doing: ...
Blocked on: ...
```
Commit small and often; pull before starting; do not edit another person's file directly.

---

## 11. Prompt to give each person's LLM at the start of a session

```
Read CONTEXT.md in the repo (project goal, datasets, interface contract).
My role: <Naman | Astitva | Anshu | Vivek>. My files: <list>.
Follow the function signatures exactly. Do not change other people's files.
Write code I can explain line by line; add comments. Use only NumPy/SciPy/wfdb/matplotlib
unless I say otherwise. Log what you generated in AI_USAGE.md.
```
