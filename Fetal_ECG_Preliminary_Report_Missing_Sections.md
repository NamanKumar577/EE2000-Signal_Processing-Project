# Preliminary Report --- Non-Invasive Fetal ECG Extraction and FPGA Implementation

## 1. Introduction and Motivation

### 1.1 Fetal ECG and its clinical significance

Fetal electrocardiography (fECG) is the electrical representation of the
fetal cardiac activity. It contains information about the electrical
depolarization and repolarization of the fetal heart and can therefore
provide information about fetal cardiac rhythm and heart-rate dynamics.

The fetal heart rate (FHR) is one of the important physiological
parameters used for monitoring fetal well-being. Changes in fetal heart
rate can be associated with changes in fetal physiological state, and
reliable continuous monitoring is therefore valuable during pregnancy
and particularly during labor.

Conventional fetal monitoring methods can provide useful information,
but fetal ECG has an important advantage: it contains the electrical
cardiac information directly rather than only observing mechanical or
acoustic consequences of cardiac activity. In principle, fetal ECG can
provide information such as:

-   Fetal heart rate.
-   Fetal QRS complexes.
-   Beat-to-beat timing.
-   Fetal cardiac rhythm.
-   Potentially, additional ECG morphology and interval information if
    the signal quality is sufficient.

The focus of this project is primarily on **reliable extraction of fetal
cardiac activity and fetal heart rate**, rather than attempting to
perform complete clinical ECG diagnosis.

### 1.2 Why non-invasive fetal ECG is useful

A direct fetal ECG can be obtained using invasive fetal electrodes in
certain clinical circumstances, but an invasive approach is not
appropriate for routine continuous monitoring because it requires access
to the fetus and is associated with procedural constraints.

Non-invasive fetal ECG attempts to obtain the fetal electrical signal
using electrodes placed on the mother's abdomen. This provides several
important advantages:

-   No direct electrode placement on the fetus is required.
-   Continuous monitoring can potentially be performed without an
    invasive procedure.
-   Multiple abdominal electrodes can be used to obtain spatially
    different observations of the underlying electrical activity.
-   The same recorded data can potentially contain both maternal and
    fetal cardiac information, allowing computational signal processing
    to separate them.

The non-invasive approach is therefore attractive for developing a
compact, automated fetal monitoring system.

### 1.3 Why fetal ECG extraction is difficult

The major difficulty is that the fetal ECG is not recorded in isolation.

An abdominal electrode measures a mixture of several signal components,
including:

1.  Maternal ECG.
2.  Fetal ECG.
3.  Maternal and fetal motion artifacts.
4.  Electrode movement artifacts.
5.  Muscle activity and other physiological interference.
6.  Electrical and measurement noise.
7.  Baseline drift and other low-frequency components.

The fetal ECG is generally much weaker than the maternal ECG at the
abdominal electrodes. Consequently, a fetal QRS complex may occur while
a much larger maternal QRS complex is present in the same observation.

A simplified model of an abdominal recording can be represented as:

\[ x(t) = m(t) + f(t) + a(t) + n(t) \]

where:

-   (x(t)) = recorded abdominal ECG,
-   (m(t)) = maternal ECG contribution,
-   (f(t)) = fetal ECG contribution,
-   (a(t)) = artifacts/interference,
-   (n(t)) = measurement noise.

The central signal-processing problem is therefore not simply detecting
peaks. The system must first make the fetal component sufficiently
visible and then identify fetal cardiac events reliably.

### 1.4 Why this is a suitable FPGA problem

The processing pipeline consists of operations that can potentially be
implemented using deterministic digital hardware:

-   Digital filtering.
-   Signal conditioning.
-   Maternal QRS identification.
-   Maternal component suppression.
-   Fetal QRS detection.
-   Beat-to-beat interval calculation.
-   Fetal heart-rate calculation.

An FPGA is particularly relevant when the objective is a real-time
implementation with predictable latency and continuous streaming
operation.

However, the FPGA should not be treated as the first development
platform. The algorithms should first be validated using recorded data
and software simulation. Once the algorithm is shown to work reliably,
the computationally suitable parts can be converted into fixed-point
hardware and implemented on the FPGA.

------------------------------------------------------------------------

# 2. Problem Statement

## 2.1 Formal problem definition

The objective of this project is to develop a signal-processing pipeline
capable of extracting fetal cardiac activity from non-invasive abdominal
ECG recordings containing both maternal and fetal components, detecting
fetal QRS complexes, and estimating fetal heart rate.

The developed algorithm will first be evaluated in a software
environment using suitable fetal ECG datasets. After algorithmic
validation, the required processing stages will be mapped to FPGA
hardware to investigate real-time implementation.

The complete problem can therefore be stated as:

> **Given multi-channel non-invasive abdominal ECG recordings containing
> maternal ECG, fetal ECG, artifacts, and noise, develop and validate a
> digital signal-processing pipeline that suppresses or separates the
> dominant maternal cardiac component, detects fetal QRS complexes,
> calculates fetal heart rate, and implements the computationally
> suitable processing stages on an FPGA for real-time operation.**

## 2.2 Input

The system input is a recorded or streamed abdominal ECG signal.

Depending on the selected dataset and final hardware architecture, the
input may consist of:

-   One abdominal ECG channel, or
-   Multiple abdominal ECG channels.

The signal may contain:

-   Maternal ECG.
-   Fetal ECG.
-   Baseline wander.
-   Motion artifacts.
-   Noise.
-   Other physiological interference.

## 2.3 Desired output

The principal outputs are:

1.  A processed signal in which the fetal cardiac component is more
    distinguishable.
2.  Detected fetal QRS locations.
3.  Fetal beat-to-beat intervals.
4.  Estimated fetal heart rate.

A possible final output representation is:

\[ RR_f\[n\] = t_f\[n+1\] - t_f\[n\] \]

where:

-   (t_f\[n\]) = time location of the (n)-th fetal QRS detection.
-   (RR_f\[n\]) = fetal beat-to-beat interval.

The fetal heart rate can then be estimated as:

\[ FHR = `\frac{60}{RR_f}`{=tex} \]

when (RR_f) is expressed in seconds.

For a sequence of detected fetal beats:

\[ FHR\[n\] = `\frac{60f_s}{N[n]}`{=tex} \]

where:

-   (f_s) = sampling frequency.
-   (N\[n\]) = number of samples between consecutive fetal QRS
    detections.

This sample-domain representation is particularly useful for FPGA
implementation because it avoids unnecessary floating-point operations.

------------------------------------------------------------------------

# 3. Objectives

## 3.1 Primary objective

The primary objective is:

> **To develop and validate an algorithm for reliable fetal QRS
> detection and fetal heart-rate estimation from non-invasive abdominal
> ECG recordings containing strong maternal ECG interference.**

The algorithm must be evaluated on real ECG recordings rather than only
on artificially generated signals.

The main performance concern is reliable identification of fetal cardiac
beats despite maternal interference and noise.

------------------------------------------------------------------------

## 3.2 Secondary objectives

The secondary objectives are:

### A. Understand the characteristics of abdominal ECG

Study:

-   Maternal and fetal ECG morphology.
-   Relative amplitude of maternal and fetal components.
-   Frequency characteristics.
-   Inter-channel differences.
-   Typical sources of interference.
-   Effects of noise and motion artifacts.

### B. Develop preprocessing

Investigate preprocessing operations that improve the signal before QRS
detection.

Possible operations include:

-   Removal of baseline wander.
-   Band-pass filtering.
-   Noise suppression.
-   Normalization/scaling.
-   Signal conditioning.

The exact filter structure should be selected after examining the
dataset and evaluating its effect on fetal QRS preservation.

### C. Detect and suppress maternal cardiac activity

Maternal ECG is often one of the dominant components of abdominal
recordings.

The system should therefore:

1.  Detect maternal cardiac events.
2.  Estimate their locations accurately.
3.  Reduce their influence on the abdominal signal.
4.  Preserve fetal cardiac information as much as possible.

The objective is not necessarily to reconstruct a perfect maternal-free
signal. The practical objective is to produce a signal in which fetal
QRS complexes can be detected more reliably.

### D. Detect fetal QRS complexes

After preprocessing and maternal suppression, the system must identify
fetal QRS complexes.

The detector should ideally provide:

-   Correct fetal beat detections.
-   Low false-detection rate.
-   Low missed-beat rate.
-   Robustness to variation in fetal heart rate.
-   Reasonable tolerance to residual maternal interference.

### E. Estimate fetal heart rate

Once fetal QRS locations are obtained, calculate:

-   Fetal RR intervals.
-   Instantaneous fetal heart rate.
-   A stable heart-rate estimate over time.

The heart-rate stage should also handle unrealistic or erroneous
intervals caused by false or missed detections.

### F. Evaluate the algorithm quantitatively

The algorithm should not be considered successful merely because a
waveform looks visually cleaner.

Performance should be measured using appropriate metrics such as:

-   Sensitivity.
-   Positive predictive value.
-   F1-score.
-   Detection error rate.
-   Missed detections.
-   False detections.
-   Fetal heart-rate error.

Where reference annotations are available, detected fetal QRS locations
should be compared against the annotated fetal beats.

------------------------------------------------------------------------

# 4. FPGA Implementation Objective

## 4.1 Hardware objective

After the algorithm has been validated in software, the processing chain
should be mapped onto an FPGA.

The FPGA implementation should aim to demonstrate:

-   Streaming signal processing.
-   Deterministic processing latency.
-   Real-time or near-real-time operation.
-   Reduced dependence on a general-purpose processor.
-   Hardware implementation of computationally important stages.

The final implementation does not necessarily need to reproduce every
software operation exactly. Algorithmic modifications may be required to
make the system appropriate for digital hardware.

## 4.2 FPGA-oriented design considerations

The following issues must be considered during hardware conversion:

### Fixed-point representation

Software prototypes may use floating-point numbers, whereas FPGA
hardware is generally more efficient when using fixed-point arithmetic.

The required process is:

\[ `\text{Floating-point algorithm}`{=tex} `\rightarrow`{=tex}
`\text{Numerical analysis}`{=tex} `\rightarrow`{=tex}
`\text{Fixed-point representation}`{=tex} `\rightarrow`{=tex}
`\text{Hardware validation}`{=tex} \]

Quantization must be studied carefully because excessive reduction in
numerical precision can change filter outputs or QRS detection
decisions.

### Memory requirements

The architecture may require storage for:

-   Filter delay elements.
-   Signal windows.
-   Previous QRS locations.
-   Running thresholds.
-   Intermediate values.
-   Reference templates, if the selected algorithm uses them.

The memory requirement should be quantified before final hardware
architecture selection.

### Computational complexity

Operations such as:

-   Multiplication.
-   Division.
-   Square root.
-   Absolute value.
-   Comparisons.
-   Moving-window calculations.

have different hardware costs.

Where appropriate, expensive operations can be reformulated using:

-   Integer arithmetic.
-   Shift operations.
-   Lookup tables.
-   Comparators.
-   Counters.
-   Reciprocal approximations.

### Streaming architecture

The preferred architecture is potentially a streaming pipeline:

``` text
ADC / Input Stream
        |
        v
Preprocessing
        |
        v
Maternal QRS Detection
        |
        v
Maternal Suppression
        |
        v
Fetal QRS Detection
        |
        v
RR Interval Calculation
        |
        v
FHR Calculation
        |
        v
Output
```

This allows samples to move through the system continuously rather than
requiring the entire ECG recording to be stored before processing.

------------------------------------------------------------------------

# 5. Methodology

## 5.1 Overall methodology

The proposed methodology consists of two major phases:

### Phase 1 --- Software algorithm development and validation

The complete algorithm will first be developed and tested using
Python/MATLAB or another suitable numerical environment.

### Phase 2 --- FPGA implementation

Once the algorithm is validated, the hardware-compatible processing
stages will be implemented using HDL and tested on the target FPGA.

The complete conceptual workflow is:

``` text
Dataset
   |
   v
Data Loading
   |
   v
Preprocessing
   |
   v
Maternal QRS Detection
   |
   v
Maternal Component Suppression
   |
   v
Fetal ECG Enhancement
   |
   v
Fetal QRS Detection
   |
   v
RR Interval Calculation
   |
   v
Fetal Heart Rate
   |
   v
Performance Evaluation
   |
   v
Fixed-Point Conversion
   |
   v
FPGA Implementation
   |
   v
Hardware Validation
```

------------------------------------------------------------------------

# 6. Dataset and Signal Preparation

## 6.1 Dataset selection

A suitable publicly available fetal ECG dataset should be selected for
initial algorithm development.

The dataset should preferably provide:

-   Abdominal ECG recordings.
-   Multiple channels where available.
-   Known sampling frequency.
-   Sufficient recording duration.
-   Reference fetal QRS annotations or fetal heart-rate information.
-   Maternal annotations if available.

The availability of annotations is important because the algorithm
requires an objective reference for evaluating fetal QRS detection.

## 6.2 Data inspection

Before designing the algorithm, the dataset should be inspected to
determine:

-   Number of channels.
-   Sampling frequency.
-   Signal duration.
-   Signal amplitude range.
-   Data format.
-   Presence of missing samples.
-   Annotation format.
-   Typical maternal-to-fetal signal ratio.
-   Amount of motion/noise contamination.

This step prevents designing an algorithm around assumptions that do not
match the actual dataset.

## 6.3 Signal visualization

Representative segments should be plotted before processing.

At minimum, the analysis should include:

-   Raw abdominal ECG.
-   Maternal-dominant regions.
-   Fetal-dominant or fetal-visible regions.
-   Filtered signal.
-   Detected maternal QRS locations.
-   Maternal-suppressed signal.
-   Detected fetal QRS locations.

Visual inspection is useful for understanding failure cases, but it
should not replace quantitative evaluation.

------------------------------------------------------------------------

# 7. Preprocessing

The preprocessing stage prepares the raw abdominal ECG for subsequent
cardiac-event detection.

## 7.1 Baseline-wander removal

Low-frequency baseline variation can arise from:

-   Respiration.
-   Electrode movement.
-   Changes in electrode-skin impedance.
-   Other physiological effects.

A high-pass component or another baseline-removal method can be used if
required.

The selected cutoff must not distort important ECG morphology.

## 7.2 Band-pass filtering

A band-pass filter can reduce unwanted low-frequency drift and
high-frequency noise while retaining the frequency content required for
QRS detection.

The exact passband should be determined experimentally based on:

-   Dataset sampling frequency.
-   Fetal QRS characteristics.
-   Maternal QRS characteristics.
-   Noise spectrum.
-   Requirements of the chosen QRS detector.

The final filter should also be selected with FPGA implementation in
mind.

Possible implementation structures include:

-   FIR filters.
-   IIR filters.
-   Cascaded simple filters.

A filter that performs well in software but requires excessive FPGA
resources may need to be redesigned.

## 7.3 Normalization and scaling

Signal normalization may be useful for algorithms involving adaptive
thresholds.

However, normalization must be designed carefully for hardware because
operations such as division by a dynamically calculated maximum can
increase implementation complexity.

If normalization is used, a hardware-compatible formulation should be
developed.

------------------------------------------------------------------------

# 8. Maternal QRS Detection and Maternal Suppression

## 8.1 Why maternal suppression is required

The maternal ECG can be substantially larger than the fetal ECG in
abdominal recordings.

If fetal QRS detection is applied directly to the raw abdominal ECG, a
detector may primarily detect maternal beats.

Therefore, the system should first estimate the locations of maternal
cardiac events and reduce their contribution.

The conceptual process is:

``` text
Abdominal ECG
      |
      v
Maternal QRS Detection
      |
      v
Maternal Beat Locations
      |
      v
Maternal Component Estimation/Suppression
      |
      v
Residual Signal
      |
      v
Fetal QRS Detection
```

## 8.2 Maternal QRS detection

The maternal QRS detector identifies the dominant maternal cardiac
events.

This can be based on a suitable QRS detection technique using features
such as:

-   Signal amplitude.
-   Slope.
-   Energy.
-   Moving-window statistics.
-   Adaptive thresholds.
-   Temporal constraints.

The specific method should be selected through comparison on the chosen
dataset.

## 8.3 Maternal component suppression

Several approaches can potentially be investigated.

### Template-based suppression

A maternal QRS template can be estimated from detected maternal beats
and used to estimate the maternal contribution around subsequent
maternal events.

### Cancellation/subtraction

An estimate of the maternal component can be subtracted from the
abdominal signal:

\[ r(t) = x(t) - `\hat{m}`{=tex}(t) \]

where:

-   (x(t)) = abdominal ECG.
-   (`\hat{m}`{=tex}(t)) = estimated maternal component.
-   (r(t)) = residual signal.

The residual is then processed for fetal QRS detection.

### Multi-channel methods

If multiple abdominal channels are available, their different mixtures
of maternal and fetal ECG can potentially be exploited.

Possible signal-processing approaches include:

-   Linear combinations.
-   Adaptive filtering.
-   Source-separation methods.
-   Statistical decomposition methods.

The final technique should be selected based on both performance and
FPGA feasibility.

------------------------------------------------------------------------

# 9. Fetal QRS Detection

## 9.1 Objective

The fetal QRS detector operates on the processed/residual signal and
identifies the temporal locations of fetal ventricular depolarization
events.

A successful detector should distinguish fetal QRS complexes from:

-   Residual maternal QRS activity.
-   T-waves.
-   Noise.
-   Motion artifacts.
-   Other transient disturbances.

## 9.2 General detection process

A generic detection pipeline may be:

``` text
Fetal-enhanced signal
        |
        v
Feature extraction
        |
        v
Candidate generation
        |
        v
Threshold / decision logic
        |
        v
Temporal validation
        |
        v
Fetal QRS locations
```

The detector may use:

-   Amplitude.
-   Slope.
-   Energy.
-   Squared signal.
-   Moving-window integration.
-   Adaptive thresholding.
-   Refractory-period constraints.

The exact algorithm should be selected after evaluating candidate
approaches on the dataset.

## 9.3 Temporal constraints

Physiological timing constraints can help reject impossible detections.

For example, after detecting a fetal QRS, a short refractory period can
prevent the same QRS complex from being detected multiple times.

Similarly, excessively short or long RR intervals can be flagged as
potentially erroneous.

These constraints are also attractive for FPGA implementation because
they can often be implemented using counters and comparisons.

------------------------------------------------------------------------

# 10. Fetal Heart-Rate Estimation

After fetal QRS locations are obtained, fetal RR intervals are
calculated.

For two consecutive fetal detections:

\[ RR_n = t_n - t\_{n-1} \]

If the sampling frequency is (f_s) and the difference is (N_n) samples:

\[ RR_n = `\frac{N_n}{f_s}`{=tex} \]

Therefore:

\[ FHR_n = `\frac{60}{RR_n}`{=tex} = `\frac{60f_s}{N_n}`{=tex} \]

This calculation can be implemented in a hardware-compatible way.

## 10.1 Handling incorrect detections

False or missed QRS detections can create incorrect RR intervals.

Therefore, the FHR stage should include validation logic.

Potential checks include:

-   Physiological range checking.
-   Comparison with previous RR intervals.
-   Rejection of extremely short intervals.
-   Detection of implausibly long intervals.
-   Optional smoothing of the final FHR estimate.

The exact limits should be justified using the selected dataset and
relevant physiological literature rather than chosen arbitrarily.

------------------------------------------------------------------------

# 11. Performance Evaluation

## 11.1 Why evaluation is essential

A fetal ECG extraction system cannot be validated simply by showing a
visually improved waveform.

The algorithm must demonstrate that the detected fetal beats correspond
to actual fetal cardiac events.

Therefore, reference annotations should be used whenever available.

## 11.2 QRS detection metrics

Important metrics include:

### Sensitivity

\[ Sensitivity = `\frac{TP}{TP+FN}`{=tex} \]

where:

-   (TP) = correctly detected fetal beats.
-   (FN) = missed fetal beats.

Sensitivity measures how many true fetal beats were successfully
detected.

### Positive Predictive Value

\[ PPV = `\frac{TP}{TP+FP}`{=tex} \]

where:

-   (FP) = false detections.

PPV measures how many detected beats were actually fetal beats.

### F1-score

\[ F1 = 2`\frac{Sensitivity \times PPV}`{=tex} {Sensitivity + PPV} \]

This combines sensitivity and PPV into a single detection metric.

## 11.3 Detection tolerance

A detected QRS should not necessarily be required to occur at exactly
the same sample as the reference annotation.

A defined temporal tolerance window should be used.

For example:

``` text
Reference QRS
      |
      |<---- acceptable timing tolerance ---->|
      |
Detected QRS
```

The tolerance must be specified before calculating performance.

## 11.4 FHR evaluation

The estimated fetal heart rate should be compared with the reference FHR
or reference fetal beat locations.

Possible measurements include:

-   Mean absolute error.
-   Maximum error.
-   Root mean square error.
-   Percentage of time within a defined error range.
-   Beat-to-beat interval error.

The exact metric should depend on what reference information is
available in the selected dataset.

------------------------------------------------------------------------

# 12. Software Validation Before FPGA

The FPGA implementation should not be attempted before the algorithm is
sufficiently validated in software.

The recommended progression is:

``` text
Dataset
   ↓
Python/MATLAB prototype
   ↓
Visual verification
   ↓
Quantitative QRS evaluation
   ↓
Parameter optimization
   ↓
Fixed-point model
   ↓
Fixed-point verification
   ↓
HDL implementation
   ↓
RTL simulation
   ↓
FPGA synthesis
   ↓
Hardware testing
```

This separation is important because debugging algorithmic errors and
hardware errors simultaneously makes the project unnecessarily
difficult.

------------------------------------------------------------------------

# 13. Fixed-Point Conversion

## 13.1 Why fixed-point conversion is required

A MATLAB/Python implementation may use floating-point arithmetic.

An FPGA implementation can use floating-point hardware, but doing so may
consume significantly more resources than a carefully designed
fixed-point implementation.

Therefore, the numerical range and precision of every major signal
should be analyzed.

## 13.2 Fixed-point analysis

For each processing stage, determine:

-   Minimum value.
-   Maximum value.
-   Required integer bits.
-   Required fractional bits.
-   Quantization error.
-   Overflow possibility.
-   Saturation behavior.

The fixed-point version should first be simulated in software.

The outputs of the floating-point and fixed-point models should then be
compared.

## 13.3 Acceptance criterion

The fixed-point implementation should produce sufficiently similar:

-   Filtered waveforms.
-   Maternal detections.
-   Fetal detections.
-   RR intervals.
-   FHR estimates.

The acceptance criterion should be defined quantitatively rather than
based only on visual similarity.

------------------------------------------------------------------------

# 14. FPGA Architecture

## 14.1 Proposed high-level architecture

A possible architecture is:

``` text
                +----------------+
Input ECG ----> | Input Interface|
                +-------+--------+
                        |
                        v
                +----------------+
                | Preprocessing  |
                +-------+--------+
                        |
                        v
                +----------------+
                | Maternal QRS   |
                | Detection      |
                +-------+--------+
                        |
                        v
                +----------------+
                | Maternal       |
                | Suppression    |
                +-------+--------+
                        |
                        v
                +----------------+
                | Fetal QRS      |
                | Detection      |
                +-------+--------+
                        |
                        v
                +----------------+
                | RR Interval    |
                | Calculation    |
                +-------+--------+
                        |
                        v
                +----------------+
                | FHR Calculation |
                +-------+---------+
                        |
                        v
                    Output
```

## 14.2 Hardware blocks

The final architecture may contain:

-   Input/sample interface.
-   Filter blocks.
-   Delay registers.
-   Moving-window blocks.
-   Threshold calculation.
-   Peak/candidate detector.
-   Timing counters.
-   QRS decision logic.
-   RR interval counter.
-   FHR calculation block.
-   Output interface.

The exact architecture depends on the final software algorithm.

## 14.3 Pipelining

Pipelining can allow multiple samples to be processed simultaneously at
different stages.

For example:

``` text
Cycle n:
Sample A → Filter

Cycle n+1:
Sample B → Filter
Sample A → QRS processing

Cycle n+2:
Sample C → Filter
Sample B → QRS processing
Sample A → Decision
```

This can improve throughput while maintaining continuous streaming
operation.

------------------------------------------------------------------------

# 15. FPGA Resource and Timing Analysis

The hardware implementation should be evaluated using:

-   LUT utilization.
-   Flip-flop utilization.
-   Block RAM usage.
-   DSP slice utilization.
-   Maximum operating frequency.
-   Processing latency.
-   Throughput.
-   Power, if measurable.

The FPGA should be able to process incoming ECG samples at least as fast
as they arrive.

For an input sampling frequency (f_s), the hardware must provide
sufficient throughput so that:

\[ Throughput\_{hardware} `\geq `{=tex}f_s \]

for a streaming implementation.

The design should also have sufficient timing margin for reliable
operation.

------------------------------------------------------------------------

# 16. Verification Strategy

## 16.1 Software-level verification

For the software algorithm:

1.  Load a known ECG recording.
2.  Run preprocessing.
3.  Detect maternal QRS complexes.
4.  Perform maternal suppression.
5.  Detect fetal QRS complexes.
6.  Compare detections with annotations.
7.  Calculate performance metrics.
8.  Analyze failure cases.

## 16.2 RTL simulation

The same input samples used by the software reference model should be
supplied to the HDL simulation.

The outputs should be compared between:

``` text
Software Reference
        vs.
RTL Simulation
```

Important comparison points include:

-   Filter output.
-   Detection signals.
-   QRS locations.
-   RR intervals.
-   FHR.

## 16.3 FPGA hardware verification

After RTL verification:

``` text
RTL Simulation
      ↓
Synthesis
      ↓
Implementation
      ↓
Bitstream
      ↓
FPGA
      ↓
Hardware Output
```

The hardware output should be captured and compared with the software
reference.

------------------------------------------------------------------------

# 17. Expected Outcomes

The project is expected to demonstrate the following:

## 17.1 Signal-processing outcome

A processing pipeline capable of reducing the effect of maternal ECG and
other interference sufficiently to expose fetal cardiac activity.

## 17.2 Fetal QRS outcome

The system should identify fetal QRS complexes from the processed
abdominal ECG with measurable sensitivity and positive predictive value.

## 17.3 FHR outcome

The detected fetal QRS locations should allow fetal RR intervals and
fetal heart rate to be calculated.

## 17.4 Hardware outcome

A hardware implementation should demonstrate that the selected algorithm
can be mapped to an FPGA using an appropriate fixed-point and streaming
architecture.

## 17.5 Validation outcome

The final system should be supported by quantitative comparison between:

-   Reference fetal annotations.
-   Software algorithm output.
-   Fixed-point model output.
-   FPGA output.

The goal is not merely to produce an ECG waveform that looks reasonable.
The important demonstration is that the complete processing chain
produces objectively measurable fetal cardiac information.

------------------------------------------------------------------------

# 18. Current Status

The current project can be divided into completed, ongoing, and
remaining work.

## 18.1 Work already completed

The project has progressed through the literature and
problem-understanding stage.

The work completed so far includes:

-   Identification of non-invasive fetal ECG as the target problem.
-   Study of the fetal ECG extraction problem.
-   Examination of relevant fetal ECG research papers.
-   Understanding that abdominal recordings contain both maternal and
    fetal components.
-   Identification of maternal suppression as an important processing
    stage.
-   Identification of fetal QRS detection as the main event-detection
    task.
-   Identification of fetal heart-rate estimation as a final
    signal-level output.
-   Initial consideration of FPGA implementation.
-   Consideration of software simulation before hardware implementation.
-   Identification of the need to validate the algorithm against
    reference data.

The literature review should be used to narrow the candidate algorithms
rather than attempting to implement every technique encountered in the
papers.

## 18.2 Work currently in progress

The next development stage is algorithm selection and software
prototyping.

This includes:

-   Selecting an appropriate dataset.
-   Understanding its channel structure and annotations.
-   Loading and visualizing the recordings.
-   Establishing preprocessing parameters.
-   Implementing maternal QRS detection.
-   Testing maternal suppression approaches.
-   Implementing fetal QRS detection.
-   Calculating FHR.
-   Establishing quantitative evaluation metrics.

## 18.3 Work remaining

The major remaining tasks are:

### Dataset and reference setup

-   Finalize the dataset.
-   Understand its annotations.
-   Establish the reference fetal QRS locations.
-   Define the evaluation protocol.

### Algorithm development

-   Finalize preprocessing.
-   Select maternal QRS detection method.
-   Select maternal suppression method.
-   Select fetal QRS detector.
-   Implement FHR estimation.
-   Test on multiple recordings.

### Algorithm evaluation

-   Calculate sensitivity.
-   Calculate PPV.
-   Calculate F1-score.
-   Analyze false positives.
-   Analyze missed fetal beats.
-   Analyze difficult signal segments.
-   Evaluate FHR accuracy.

### Hardware conversion

-   Determine numerical ranges.
-   Convert floating-point processing to fixed-point.
-   Validate fixed-point behavior.
-   Design RTL architecture.
-   Implement individual hardware blocks.
-   Perform RTL simulation.
-   Integrate the complete pipeline.

### FPGA validation

-   Synthesize the design.
-   Analyze resource utilization.
-   Analyze timing.
-   Program the FPGA.
-   Feed ECG samples to the hardware.
-   Capture hardware outputs.
-   Compare FPGA output with the software reference.

------------------------------------------------------------------------

# 19. Project Development Plan

A practical development sequence is:

## Stage 1 --- Dataset understanding

``` text
Select dataset
      ↓
Load ECG
      ↓
Understand channels
      ↓
Understand annotations
      ↓
Plot representative segments
```

## Stage 2 --- Baseline processing

``` text
Raw ECG
   ↓
Baseline correction
   ↓
Band-pass filtering
   ↓
Initial signal inspection
```

## Stage 3 --- Maternal detection

``` text
Preprocessed ECG
      ↓
Maternal QRS detector
      ↓
Maternal beat locations
      ↓
Evaluate maternal detection
```

## Stage 4 --- Maternal suppression

``` text
Maternal beat locations
          +
Abdominal ECG
          ↓
Maternal estimation/suppression
          ↓
Residual/fetal-enhanced signal
```

## Stage 5 --- Fetal detection

``` text
Fetal-enhanced signal
        ↓
Fetal QRS detector
        ↓
Fetal QRS locations
        ↓
Compare with annotations
```

## Stage 6 --- FHR

``` text
Fetal QRS locations
        ↓
RR intervals
        ↓
FHR calculation
        ↓
FHR validation
```

## Stage 7 --- Hardware preparation

``` text
Validated floating-point model
            ↓
Fixed-point model
            ↓
Numerical verification
            ↓
HDL architecture
```

## Stage 8 --- FPGA

``` text
HDL
 ↓
RTL simulation
 ↓
Synthesis
 ↓
Implementation
 ↓
FPGA
 ↓
Hardware validation
```

------------------------------------------------------------------------

# 20. Important Technical Risks

## 20.1 Maternal ECG dominance

The fetal ECG can be significantly weaker than the maternal ECG. A fetal
detector operating directly on the abdominal signal may therefore
produce many maternal detections.

**Mitigation:** robust maternal detection and suppression should precede
fetal QRS detection.

## 20.2 Motion artifacts

Movement can distort abdominal ECG significantly.

**Mitigation:** evaluate the algorithm on recordings containing
realistic artifacts rather than only clean examples.

## 20.3 False fetal detections

Residual maternal ECG, T-waves, and noise may be detected as fetal QRS
complexes.

**Mitigation:** combine signal features with adaptive thresholds and
temporal constraints.

## 20.4 Missed fetal beats

Weak fetal QRS complexes may fall below the detection threshold.

**Mitigation:** avoid overly aggressive thresholding and evaluate
sensitivity separately from PPV.

## 20.5 Dataset dependence

An algorithm that works on one recording may fail on another because of
differences in:

-   Electrode placement.
-   Maternal-fetal signal ratio.
-   Noise.
-   Fetal heart rate.
-   Signal amplitude.
-   Recording conditions.

Therefore, evaluation should include multiple recordings and, where
possible, multiple subjects.

## 20.6 FPGA resource limitations

An algorithm that works in MATLAB/Python may be inefficient in hardware.

**Mitigation:** consider hardware cost during algorithm selection rather
than only after the algorithm is finalized.

## 20.7 Fixed-point degradation

Quantization can alter thresholds and filter outputs.

**Mitigation:** create a fixed-point software model before implementing
the HDL version.

------------------------------------------------------------------------

# 21. Scope of the Preliminary Project

The project should remain focused on the following chain:

\[ `\boxed{
Abdominal\ ECG
\rightarrow
Preprocessing
\rightarrow
Maternal\ Suppression
\rightarrow
Fetal\ QRS
\rightarrow
FHR
\rightarrow
FPGA
}`{=tex} \]

The primary deliverable is a validated fetal QRS/FHR extraction pipeline
with an FPGA implementation.

Advanced clinical interpretation should remain outside the initial scope
unless sufficient time and validated data are available.

The project does **not** need to solve every aspect of fetal ECG
analysis. In particular, the initial system does not need to provide:

-   Complete fetal ECG clinical diagnosis.
-   Automatic diagnosis of fetal cardiac abnormalities.
-   Full morphological interpretation.
-   Clinical-grade medical-device certification.
-   Universal performance across every possible recording condition.

These are substantially larger problems than fetal QRS detection and FHR
estimation.

------------------------------------------------------------------------

# 22. Preliminary Report Deliverables

The preliminary report should ultimately demonstrate the following:

### Literature understanding

-   Why fetal ECG is important.
-   Why non-invasive extraction is useful.
-   Why abdominal fetal ECG extraction is difficult.
-   What existing methods have attempted.
-   What approach is being selected and why.

### Problem definition

-   Clearly defined input.
-   Clearly defined output.
-   Explicit problem statement.
-   Defined project scope.

### Algorithm

-   Dataset.
-   Preprocessing.
-   Maternal QRS detection.
-   Maternal suppression.
-   Fetal QRS detection.
-   FHR calculation.
-   Evaluation methodology.

### Hardware

-   FPGA target.
-   Hardware architecture.
-   Fixed-point strategy.
-   Streaming/pipelining strategy.
-   Resource and timing considerations.

### Validation

-   Reference annotations.
-   QRS detection metrics.
-   FHR error.
-   Software-versus-fixed-point comparison.
-   Software-versus-FPGA comparison.

### Status

-   Completed work.
-   Current work.
-   Remaining work.
-   Planned milestones.

------------------------------------------------------------------------

# 23. Final Proposed System

The final conceptual system can be summarized as:

``` text
                    NON-INVASIVE ABDOMINAL ECG
                              |
                              v
                    +-------------------+
                    | Data Acquisition  |
                    | / Dataset Input   |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |   Preprocessing   |
                    | Filter / Denoise  |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Maternal QRS      |
                    | Detection         |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Maternal ECG      |
                    | Suppression       |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Fetal ECG         |
                    | Enhancement       |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Fetal QRS         |
                    | Detection         |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | RR Interval       |
                    | Calculation       |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Fetal Heart Rate  |
                    | Estimation        |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Performance       |
                    | Evaluation        |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Fixed-Point Model |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | FPGA RTL Design   |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | FPGA Hardware     |
                    | Validation        |
                    +-------------------+
```

------------------------------------------------------------------------

# 24. Conclusion

The proposed project addresses the extraction of fetal cardiac
information from non-invasive abdominal ECG recordings and its
implementation on FPGA hardware.

The central challenge is that the abdominal ECG is a mixture of maternal
ECG, fetal ECG, noise, and artifacts. Because the maternal component can
dominate the fetal signal, the system requires a processing chain that
first conditions the signal, identifies maternal cardiac activity,
suppresses the maternal contribution, and then detects fetal QRS
complexes.

The detected fetal QRS locations provide the basis for fetal RR-interval
and fetal heart-rate estimation. These outputs can be objectively
evaluated against reference annotations using quantitative detection
metrics.

The FPGA portion of the project begins only after the signal-processing
algorithm has been validated in software. The validated algorithm can
then be converted to fixed-point arithmetic and mapped onto a streaming
hardware architecture. RTL simulation and FPGA testing should be used to
verify that the hardware produces results consistent with the software
reference.

The complete project therefore follows a clear progression:

\[ `\boxed{
\text{Literature}
\rightarrow
\text{Dataset}
\rightarrow
\text{Algorithm}
\rightarrow
\text{Validation}
\rightarrow
\text{Fixed-Point}
\rightarrow
\text{FPGA}
}`{=tex} \]

The most important immediate task is **not FPGA coding**. It is to
establish a reliable software reference pipeline and quantitatively
demonstrate that the selected fetal QRS detection method works on real
abdominal ECG data. Once that reference is stable, the FPGA
implementation becomes a hardware-engineering problem rather than an
unresolved signal-processing problem.
