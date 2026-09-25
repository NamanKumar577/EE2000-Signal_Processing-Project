# Fetal ECG Extraction and Fetal Heart-Rate Detection --- Project Context & Plan

## 1. Project idea

### Working title

**Fetal ECG Extraction from Maternal Abdominal ECG and Fetal QRS
Detection on FPGA**

### Core idea

The project will process an abdominal ECG recording obtained from a
pregnant subject and try to extract the much weaker **fetal ECG (FECG)**
from the mixture of:

-   Maternal ECG (MECG)
-   Fetal ECG (FECG)
-   Noise and artifacts

The main signal model is:

\[ AECG(t) = MECG(t) + FECG(t) + Noise(t) \]

The final objective is not necessarily to reconstruct a perfect fetal
P-QRS-T waveform. A realistic first objective is:

\[
`\boxed{AECG \rightarrow maternal\ suppression \rightarrow fetal\ QRS\ detection \rightarrow FHR}`{=tex}
\]

where FHR = fetal heart rate.

------------------------------------------------------------------------

# 2. Sources/data available for the project

We currently have **two fetal-ECG data sources** and one review paper
that will guide the algorithm selection.

## Dataset 1 --- FECGSYNDB

**Type:** Synthetic fetal ECG database

This dataset is useful for the **development and controlled testing
stage** because the synthetic signals provide separate fetal, maternal,
and noise components / ground truth.

Important characteristics from the provided dataset document:

-   10 pregnancies
-   7 cases/events
-   5 SNR/noise levels
-   5 repetitions
-   1,750 signals
-   Sampling frequency: **250 Hz**
-   Resolution: **16-bit**
-   Recording duration: **5 minutes**
-   Contains abdominal ECG mixtures together with separate fetal,
    maternal and noise components/ground truth

### Why we need this dataset

Because the individual components are known, we can answer questions
such as:

-   How much maternal ECG was removed?
-   How much fetal ECG was preserved?
-   How does performance change when noise increases?
-   Does the extracted signal actually correspond to the known fetal
    signal?
-   Which algorithm parameters work best?

This makes FECGSYNDB suitable for **algorithm development, debugging and
controlled experiments**.

------------------------------------------------------------------------

## Dataset 2 --- Non-Invasive Fetal ECG Arrhythmia Database (NIFEADB)

**Type:** Real fetal ECG recordings

The provided dataset information describes:

-   **26 recordings**
-   **12 fetal-arrhythmia recordings**
-   **14 normal-rhythm recordings**
-   4--5 abdominal ECG channels
-   1 maternal chest ECG channel
-   Sampling at **500 Hz or 1 kHz**
-   Recordings provided in WFDB format such as `.dat` and `.hea`

### Why we need this dataset

This is important because the algorithm should not only work on
clean/synthetic signals.

After developing the algorithm on FECGSYNDB, we can test whether it
works on **real recorded signals** containing real maternal/fetal
interference and recording conditions.

Therefore:

``` text
FECGSYNDB
    ↓
Algorithm development + controlled testing
    ↓
NIFEADB
    ↓
Validation on real recordings
```

This gives the project a much stronger experimental structure than
testing on only synthetic data.

------------------------------------------------------------------------

# 3. What the FECG review paper tells us

## Paper

**M. A. Hasan et al., "Detection and Processing Techniques of FECG
Signal for Fetal Monitoring"**

The paper is a review of methods used to detect, extract and process
fetal ECG and to estimate fetal heart rate.

The paper states that FECG is a relatively weak signal compared with
maternal ECG and is often embedded in noise. It discusses the use of
FECG for obtaining information such as fetal heart rate and waveform
characteristics.

The paper also emphasizes that obtaining FECG from abdominal recordings
is difficult because maternal ECG and several noise sources overlap with
the fetal signal.

Source: provided paper, especially the sections on FECG characteristics,
noise/interference, detection, extraction and processing.

------------------------------------------------------------------------

# 4. Actual signal-processing problem

The abdominal ECG is not simply the fetal ECG.

Conceptually:

``` text
             Maternal ECG
                  │
                  │
                  ▼
            ┌───────────┐
Noise ─────►│           │
            │   AECG    │──────► Our algorithm
Fetal ECG ─►│           │
            └───────────┘
```

The paper identifies several important interfering components:

-   Maternal ECG
-   Power-line interference
-   Maternal muscle/EMG activity
-   Electrode-contact noise
-   Respiration/baseline variation
-   Other physiological interference

A major difficulty is that the maternal ECG and fetal ECG have
overlapping spectral content.

Therefore:

> **A simple band-pass filter cannot reliably separate maternal ECG from
> fetal ECG.**

This is one of the most important conclusions for our project.

------------------------------------------------------------------------

# 5. What do we actually want to extract?

The fetal ECG contains:

-   P wave
-   QRS complex
-   T wave

However, because the fetal component is weak and mixed with maternal ECG
and noise, extracting the complete fetal P-QRS-T morphology is
considerably harder.

The review paper notes that many non-invasive FECG algorithms primarily
detect the **R waves/QRS complexes**, while P and T waves may remain
hidden.

Therefore our primary target should be:

``` text
Fetal QRS detection
       ↓
R-R intervals
       ↓
Fetal Heart Rate (FHR)
```

The fetal heart rate can be calculated from consecutive fetal R peaks:

\[ FHR = `\frac{60}{RR}`{=tex} \]

when RR is measured in seconds.

------------------------------------------------------------------------

# 6. Candidate algorithms discussed in the paper

The review discusses a large range of methods.

### 6.1 Conventional filtering

Examples:

-   High-pass filtering
-   Low-pass filtering
-   Band-pass filtering
-   Notch filtering

Useful for removing some noise, but **not sufficient by itself** for
maternal/fetal separation because MECG and FECG overlap in frequency.

------------------------------------------------------------------------

### 6.2 Wavelet transform

Wavelet transform is particularly relevant because ECG is a
non-stationary signal.

The paper describes a wavelet-based approach involving:

``` text
Abdominal ECG
      ↓
Wavelet decomposition
      ↓
Suppress unwanted components/noise
      ↓
Maternal QRS identification
      ↓
Maternal template / pattern matching
      ↓
Maternal QRS subtraction
      ↓
Fetal QRS detection
```

The paper describes wavelet multiresolution decomposition followed by
pattern matching and template subtraction as one approach to FECG
extraction.

------------------------------------------------------------------------

### 6.3 Adaptive filtering

Another approach is adaptive maternal-noise cancellation.

Conceptually:

``` text
                 Maternal reference
                        │
                        ▼
                 ┌─────────────┐
AECG ───────────►│ Adaptive    │
                 │ filter      │
                 └──────┬──────┘
                        │
                Estimated MECG
                        │
                        ▼
AECG ───────────────── (−)
                        │
                        ▼
                      FECG
```

LMS/adaptive filtering is attractive for FPGA implementation because the
algorithm can be expressed as a sample-by-sample recursive computation.

------------------------------------------------------------------------

### 6.4 Blind Source Separation / ICA

With multiple abdominal electrodes, each channel contains a different
mixture of the underlying sources.

Conceptually:

``` text
Abdominal channel 1 ─┐
Abdominal channel 2 ─┤
Abdominal channel 3 ─┼──► BSS / ICA ──► independent components
Abdominal channel 4 ─┤
                      ┘
```

ICA attempts to separate statistically independent sources.

The review discusses PCA, ICA and other blind-source-separation
approaches for separating maternal and fetal components.

This approach is particularly relevant because our real dataset contains
**multiple abdominal channels**.

However, ICA is mathematically and computationally more demanding than a
simple adaptive filter.

------------------------------------------------------------------------

### 6.5 Other methods mentioned in the review

The paper also discusses:

-   Fourier/transform methods
-   Template subtraction
-   Matched filtering
-   SVD
-   Neural networks
-   Fuzzy systems
-   Genetic-algorithm-based adaptive filtering
-   Blind-adaptive filtering
-   Other statistical and time-frequency methods

These methods should be treated as the research background rather than
trying to implement all of them.

------------------------------------------------------------------------

# 7. Proposed project scope

The project should be divided into stages.

## Stage 1 --- Understand and visualize the data

First load both datasets and plot:

-   Raw abdominal ECG channels
-   Maternal reference channel where available
-   Ground-truth fetal ECG where available in FECGSYNDB
-   Noise component where available
-   Time-domain waveforms
-   Frequency spectra

Goal:

> Understand exactly what enters the algorithm.

------------------------------------------------------------------------

# 8. Stage 2 --- Basic preprocessing

Start with simple digital preprocessing.

Possible blocks:

``` text
Raw AECG
   ↓
Remove DC / baseline component
   ↓
Band-pass filtering
   ↓
Optional power-line notch filtering
   ↓
Preprocessed AECG
```

The exact filter limits should be selected experimentally rather than
assumed to be universally correct.

The general ECG review also emphasizes the importance of preserving
clinically relevant waveform morphology when filtering.

------------------------------------------------------------------------

# 9. Stage 3 --- Maternal ECG suppression

This is the main research component.

We should initially investigate two approaches:

### Approach A --- Adaptive filtering

Implement LMS/adaptive cancellation.

Pipeline:

``` text
AECG + maternal reference
          ↓
      LMS filter
          ↓
Estimated maternal ECG
          ↓
AECG − estimated MECG
          ↓
Residual / FECG
```

### Approach B --- Wavelet + maternal template subtraction

Pipeline:

``` text
AECG
 ↓
Wavelet decomposition
 ↓
Preprocessing
 ↓
Maternal QRS detection
 ↓
Create maternal template
 ↓
Template subtraction
 ↓
Fetal QRS detection
```

These two approaches give us a useful comparison between an adaptive
time-domain method and a time-frequency/template-based method.

------------------------------------------------------------------------

# 10. Stage 4 --- Fetal QRS detection

After maternal suppression:

``` text
Estimated FECG
       ↓
QRS enhancement
       ↓
Peak detection
       ↓
Fetal R peaks
```

The detector should produce:

-   R-peak locations
-   RR intervals
-   Fetal heart rate

The fetal QRS detection stage should be evaluated against available
annotations/ground truth.

------------------------------------------------------------------------

# 11. Stage 5 --- FHR calculation

From detected fetal R peaks:

\[ RR_i = t\_{i+1}-t_i \]

and:

\[ FHR_i = `\frac{60}{RR_i}`{=tex} \]

The output can be plotted as:

``` text
Time (s)
   │
   │      /\      /\       /\
FHR│─────/──\────/──\─────/──\──
   │
   └─────────────────────────────
```

The goal is to obtain a reliable sequence of fetal heart-rate estimates.

------------------------------------------------------------------------

# 12. Stage 6 --- MATLAB/Python reference implementation

Before FPGA implementation:

``` text
Dataset
   ↓
Python/MATLAB
   ↓
Floating-point algorithm
   ↓
Plots + measurements
   ↓
Correctness verified
```

This becomes the **golden/reference model**.

We should not immediately write the FPGA version.

------------------------------------------------------------------------

# 13. Stage 7 --- Fixed-point conversion

FPGA hardware will normally use fixed-point arithmetic rather than
arbitrary floating-point calculations.

Therefore:

``` text
Floating-point algorithm
          ↓
Determine signal ranges
          ↓
Choose word length
          ↓
Choose fractional bits
          ↓
Fixed-point MATLAB/Python model
          ↓
Compare with floating-point result
```

We need to quantify the effect of quantization.

------------------------------------------------------------------------

# 14. Stage 8 --- Spartan-7 FPGA implementation

The final hardware pipeline can look like:

``` text
                ECG sample stream
                       │
                       ▼
              ┌─────────────────┐
              │ Input / BRAM /  │
              │ sample interface│
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Preprocessing / │
              │ Digital Filter │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ FECG extraction │
              │ / MECG removal  │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Fetal QRS       │
              │ detector        │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ RR / FHR        │
              │ calculation     │
              └─────────────────┘
```

The FPGA does not have to acquire ECG directly from a person for the
first version.

The dataset samples can be streamed into the FPGA as if they were
arriving from an ADC.

------------------------------------------------------------------------

# 15. Dataset-to-FPGA flow

This is important for understanding what the FPGA is actually doing.

``` text
Real/synthetic ECG dataset
          │
          ▼
Python/MATLAB
          │
          ▼
Convert samples into a simple stream
          │
          ▼
BRAM / ROM / UART / other input
          │
          ▼
Spartan-7
          │
          ▼
Signal-processing algorithm
          │
          ▼
Output FECG / R-peaks / FHR
```

So the FPGA is acting as the **real-time digital signal-processing
engine**.

We are not required to build the complete medical ECG acquisition system
just to demonstrate the signal-processing algorithm.

------------------------------------------------------------------------

# 16. Development and validation strategy

## Dataset A --- FECGSYNDB

Use for:

-   Algorithm development
-   Parameter tuning
-   Controlled SNR experiments
-   Comparing extracted FECG with known ground truth
-   Testing fixed-point effects
-   FPGA verification

Example experiment:

``` text
Same fetal ECG
     │
     ├── Low noise
     ├── Medium noise
     ├── High noise
     └── Different repetitions
```

This allows systematic testing.

## Dataset B --- NIFEADB

Use after the algorithm is developed.

Purpose:

-   Test on real recordings
-   Test across different recordings
-   Test normal and arrhythmia cases
-   Check robustness to real maternal/fetal interference
-   Compare detected fetal QRS against available annotations

This separation between **development data** and **real-data
validation** should be maintained as much as possible to avoid tuning
the algorithm directly to the final test recordings.

------------------------------------------------------------------------

# 17. Evaluation metrics

The project should not only show attractive ECG plots.

We should measure performance.

Possible metrics:

### Fetal R-peak detection

-   Sensitivity
-   Positive Predictive Value (PPV)
-   F1 score
-   Detection error / timing error

### FHR

Compare:

\[ FHR\_{detected} \]

with reference/annotated FHR where available.

Possible measurements:

-   Mean absolute error
-   Mean error
-   Percentage error

### Signal extraction

For FECGSYNDB, where components are available:

-   Correlation with ground-truth FECG
-   Mean squared error
-   SNR improvement
-   Residual maternal interference

### FPGA implementation

Also report:

-   Clock frequency
-   Latency
-   Throughput
-   LUT utilization
-   Flip-flop utilization
-   BRAM utilization
-   DSP utilization
-   Power if available

------------------------------------------------------------------------

# 18. What we should NOT try to do initially

The paper covers many advanced methods, but our project should have a
controlled scope.

Do not initially attempt:

-   Complete fetal P-QRS-T morphology reconstruction
-   Neural-network-based FECG extraction
-   Genetic-algorithm optimization
-   Full clinical diagnostic system
-   Direct medical-device development
-   Multiple algorithms simultaneously on FPGA
-   Real-time electrode acquisition as the first milestone

First make one algorithm work correctly in software.

Then make it fixed-point.

Then implement it on FPGA.

------------------------------------------------------------------------

# 19. Recommended project progression

### Phase 1 --- Literature + data

``` text
Read FECG paper
      ↓
Understand AECG = MECG + FECG + noise
      ↓
Understand both datasets
```

### Phase 2 --- Software baseline

``` text
Load FECGSYNDB
      ↓
Preprocess
      ↓
FECG extraction
      ↓
Fetal QRS detection
      ↓
FHR
```

### Phase 3 --- Validation

``` text
Test on NIFEADB
      ↓
Measure QRS/FHR performance
```

### Phase 4 --- Fixed-point

``` text
Floating point
      ↓
Fixed point
      ↓
Error analysis
```

### Phase 5 --- FPGA

``` text
Fixed-point algorithm
      ↓
Verilog
      ↓
Simulation
      ↓
Spartan-7
      ↓
Hardware results
```

------------------------------------------------------------------------

# 20. Final project architecture

The overall project can therefore be summarized as:

``` text
                   FECG PROJECT
                        │
          ┌─────────────┴─────────────┐
          │                           │
   FECGSYNDB                    NIFEADB
   Synthetic data                Real data
          │                           │
          └─────────────┬─────────────┘
                        ↓
                Preprocessing
                        ↓
              Maternal suppression
                        ↓
                 Fetal ECG
                        ↓
               Fetal QRS detection
                        ↓
                RR interval
                        ↓
               Fetal heart rate
                        ↓
             MATLAB/Python result
                        ↓
                 Fixed-point
                        ↓
                  Spartan-7 FPGA
                        ↓
             Hardware verification
```

------------------------------------------------------------------------

# 21. What signal-processing concepts this project covers

This project connects directly to several signal-processing topics:

-   Sampling and discrete-time signals
-   Digital filters
-   FIR/IIR filtering
-   Band-pass filtering
-   Notch filtering
-   Noise reduction
-   Frequency-domain analysis
-   Fourier transform
-   Time-frequency analysis
-   Wavelet transform
-   Correlation
-   Template matching
-   Adaptive filtering
-   LMS algorithm
-   Blind source separation
-   Independent Component Analysis (ICA)
-   Peak/QRS detection
-   Statistical signal processing
-   Fixed-point implementation
-   Real-time digital signal processing
-   FPGA hardware implementation

Not all of these need to be implemented. They are the concepts
surrounding the problem.

------------------------------------------------------------------------

# 22. Central research question

The project can be framed around one question:

> **Can we design a computationally practical signal-processing pipeline
> that extracts fetal cardiac activity from multichannel maternal
> abdominal ECG, detects fetal QRS complexes, estimates fetal heart
> rate, and implements the selected algorithm on a Spartan-7 FPGA?**

The answer should be established experimentally using:

1.  **FECGSYNDB** for controlled development and ground-truth-based
    testing.
2.  **NIFEADB** for validation on real fetal ECG recordings.
3.  The Hasan et al. review as the literature basis for understanding
    and selecting FECG extraction/detection methods.

------------------------------------------------------------------------

# 23. Main takeaway from the three sources

### FECGSYNDB

Tells us **how we can develop and quantitatively test the algorithm when
the individual signal components are known**.

### NIFEADB

Tells us **whether the developed algorithm can handle real fetal ECG
recordings**.

### Hasan et al. FECG review

Tells us **what the actual signal-processing problem is and what
approaches have historically been used to solve it**, including
wavelets, adaptive filtering, template subtraction, BSS/ICA and other
approaches.

Together:

\[ `\boxed{
\text{Literature}
+
\text{Controlled synthetic data}
+
\text{Real data}
+
\text{FPGA implementation}
}`{=tex} \]

form the basis of the project.
