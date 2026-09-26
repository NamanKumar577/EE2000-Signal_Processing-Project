# Fetal ECG Signal Processing for FPGA --- Literature Notes

## Scope

These notes consolidate the five papers currently relevant to our
fetal-ECG/FPGA project:

1.  **M. L. Ahlstrom and W. J. Tompkins --- "Digital Filters for
    Real-Time ECG Signal Processing Using Microprocessors"**, IEEE
    Transactions on Biomedical Engineering, 1985.
2.  **Leif Sörnmo and Pablo Laguna --- "Electrocardiogram (ECG) Signal
    Processing"**.
3.  **Rahul Kher --- "Signal Processing Techniques for Removing Noise
    from ECG Signals"**, 2019.
4.  **Jaba Deva Krupa Abel, Samiappan Dhanalakshmi, R. Kumar --- "A
    comprehensive survey on signal processing and machine learning
    techniques for non-invasive fetal ECG extraction"**, 2022/2023.
5.  **M. A. Hasan, M. B. I. Reaz, M. I. Ibrahimy, M. S. Hussain, J.
    Uddin --- "Detection and Processing Techniques of FECG Signal for
    Fetal Monitoring"**, 2009.

The purpose is not merely to summarize the papers. The important
objective is to extract the concepts, algorithms, assumptions, datasets,
equations, implementation constraints, evaluation methods, and design
lessons that can directly affect our project.

------------------------------------------------------------------------

# 1. Problem Definition: What Are We Actually Trying to Build?

## 1.1 The raw signal

In non-invasive fetal ECG (FECG), electrodes are placed on the mother's
abdomen. The recorded abdominal ECG (AECG) is not the fetal ECG alone.

A useful abstraction is:

\[ x(t)=m(t)+f(t)+n(t) \]

where:

-   (x(t)) = recorded abdominal ECG
-   (m(t)) = maternal ECG (MECG)
-   (f(t)) = fetal ECG (FECG)
-   (n(t)) = other interference/noise

The interference can include:

-   baseline wander
-   power-line interference
-   electromyographic (EMG) noise
-   electrode/motion artifacts
-   respiration-related components
-   other physiological interference

The central difficulty is that the maternal ECG can dominate the
abdominal recording while the fetal ECG is comparatively weak.

Therefore, the project is fundamentally a **signal separation and
detection problem**, not merely an ECG filtering problem.

## 1.2 The complete processing objective

A practical system can be represented as:

``` text
Abdominal ECG
      |
      v
Preprocessing
      |
      +--> baseline-wander suppression
      |
      +--> power-line suppression
      |
      +--> bandwidth conditioning
      |
      v
Maternal ECG estimation/cancellation
      |
      v
Residual / candidate fetal ECG
      |
      v
Fetal QRS detection
      |
      v
Fetal R-peak locations
      |
      v
RR intervals
      |
      v
Fetal heart rate
```

The literature repeatedly separates the problem into these conceptual
stages.

------------------------------------------------------------------------

# 2. Paper 1 --- Ahlstrom & Tompkins

## Digital Filters for Real-Time ECG Signal Processing Using Microprocessors

### 2.1 What problem does the paper solve?

The paper asks whether ECG signal-conditioning operations traditionally
implemented with analog circuitry can instead be implemented digitally
on a microprocessor.

The authors develop a collection of real-time digital filters and
processing routines that can be cascaded to construct ECG-processing
systems.

The central engineering idea is extremely relevant to FPGA:

> Use algorithms that require little computation, preferably integer
> arithmetic, so that real-time processing can be achieved on modest
> hardware.

The paper includes:

-   adaptive 60-Hz interference filtering
-   low-pass filtering
-   high-pass filtering for DC/baseline offset
-   Hanning smoothing
-   ECG data reduction
-   band-pass filtering for QRS detection
-   derivative-based QRS detection

The algorithms were designed as subroutines that could be combined in
different sequences.

### 2.2 Why this paper matters for our FPGA project

The paper demonstrates the exact style of implementation we want:

``` text
sample
  |
  v
simple arithmetic
  |
  v
delay/register state
  |
  v
next sample
```

Instead of relying on floating-point MATLAB-style calculations, the
algorithms can be expressed using:

-   additions
-   subtractions
-   multiplications by constants
-   delays
-   comparisons
-   accumulators
-   fixed-point arithmetic

These map naturally to FPGA hardware.

------------------------------------------------------------------------

## 2.3 Adaptive 60-Hz interference filter

The paper includes an adaptive filter for approximately
constant-amplitude 60-Hz interference.

The basic principle is:

``` text
Measured ECG
     |
     +--------------------+
     |                    |
     v                    v
original signal       estimate 60-Hz
                           |
                           v
                     subtract estimate
                           |
                           v
                      filtered ECG
```

The filter maintains an estimate of the periodic interference and
adjusts the estimate according to the observed signal.

A key limitation stated by the authors is that the filter is effective
for relatively constant-amplitude interference. If the interference
changes abruptly, the filter requires a learning period to reacquire the
interference.

### Implementation lesson

The paper reports an implementation using 16-bit arithmetic with:

-   8 integer bits
-   8 fractional bits

and an estimate of the cosine-related coefficient to three decimal
places.

This is a useful historical example of fixed-point implementation of a
biomedical signal-processing algorithm.

### Important warning

The adaptation step cannot simply be made arbitrarily large.

A larger update can make the filter learn faster, but the authors report
that it can also introduce more distortion because the estimated
interference cannot follow the actual waveform accurately enough.

Therefore:

\[ `\text{faster adaptation}`{=tex}
`\neq `{=tex}`\text{automatically better filtering}`{=tex} \]

This is an important design tradeoff for our own adaptive filtering
stage.

------------------------------------------------------------------------

# 3. Hanning Filter

The paper presents a three-point weighted moving-average/Hanning filter.

Its difference equation is:

\[
y\[n\]=`\frac{1}{4}`{=tex}`\left`{=tex}(x\[n\]+2x\[n-1\]+x\[n-2\]`\right`{=tex})
\]

It is essentially a low-pass smoothing operation.

The coefficients are:

\[
`\frac14`{=tex},`\quad`{=tex}`\frac12`{=tex},`\quad`{=tex}`\frac14`{=tex}
\]

The important FPGA observation is that the coefficients are powers of
two in the denominator:

\[ y\[n\]=`\frac{x[n]+2x[n-1]+x[n-2]}{4}`{=tex} \]

So division by four can be implemented as a binary right shift rather
than a general-purpose divider.

This is exactly the type of arithmetic simplification that makes an FPGA
implementation inexpensive.

The authors note that the filter can be cascaded if stronger smoothing
is required.

### FPGA structure

``` text
x[n] ----->(*)------------------+
             1                   |
                                 |
x[n-1] --->(*)--2---------------(+)-->> 2 --> y[n]
                                 |
x[n-2] --->(*)-------------------+
             1
```

No floating-point unit is required.

------------------------------------------------------------------------

# 4. Integer-Arithmetic Low-Pass Filters

Ahlstrom and Tompkins also discuss a class of digital filters that can
implement low-pass, high-pass, band-pass, and notch responses using
integer arithmetic and linear-phase structures.

A first-order form is given conceptually as:

\[ H(z)=`\frac{1-z^{-m}}{1-z^{-1}}`{=tex} \]

which gives:

\[ y\[n\]=y\[n-1\]+x\[n\]-x\[n-m\] \]

The important implementation idea is that the filter needs:

-   one previous output
-   one delayed input
-   additions/subtractions

rather than a general multiplication-heavy FIR implementation.

The paper discusses the limitations as well:

-   cutoff is not sharply defined
-   sidelobes are present
-   the response can require higher-order structures for improved
    attenuation

A second-order form is also discussed to reduce sidelobe magnitude.

### Why this matters

This gives us a family of **hardware-efficient filters** that can be
considered when a conventional FIR filter would require too many
multipliers.

------------------------------------------------------------------------

# 5. Baseline/DC Removal

The paper discusses high-pass filtering to remove DC offset and slow
baseline drift.

This is important because abdominal ECG recordings can contain
substantial slow variations.

However, baseline removal has to be designed around the information we
intend to preserve.

The general principle is:

\[ y\[n\]=x\[n\]-`\widehat{b}`{=tex}\[n\] \]

where (`\widehat{b}`{=tex}\[n\]) represents an estimated slowly varying
baseline.

A digital high-pass filter can perform this operation directly.

------------------------------------------------------------------------

# 6. QRS Detection in Ahlstrom & Tompkins

The paper uses band-pass processing to emphasize the QRS complex and
then performs derivative-based detection.

The conceptual chain is:

``` text
ECG
 |
 v
Band-pass filter
 |
 v
Derivative / slope enhancement
 |
 v
Detection logic
 |
 v
QRS events
```

The important point for our project is that **QRS detection can be
implemented as a deterministic digital pipeline**.

We do not need a neural network just to identify R-peaks.

------------------------------------------------------------------------

# 7. What We Should Take From Paper 1

### Directly useful

-   fixed-point arithmetic
-   low-cost FIR/IIR-style structures
-   moving-average/Hanning filtering
-   high-pass baseline removal
-   interference cancellation
-   QRS-oriented band-pass filtering
-   derivative-based detection
-   real-time processing architecture

### Important limitations

-   The paper is about ordinary ECG processing, not fetal ECG
    extraction.
-   Its 60-Hz interference filter is not a maternal-ECG cancellation
    algorithm.
-   Its QRS detector does not solve the problem of separating fetal ECG
    from maternal ECG.
-   The hardware target is an old microprocessor, not a modern FPGA.

Therefore, we should use this paper primarily for the **digital-filter
and real-time implementation layer**, not as the complete FECG solution.

------------------------------------------------------------------------

# 8. Paper 2 --- Sörnmo & Laguna

## Electrocardiogram (ECG) Signal Processing

## 8.1 Purpose of the paper

This paper presents the broader structure of ECG signal processing.

The authors identify a basic set of operations common to many ECG
systems:

``` text
ECG
 |
 +--> Noise filtering
 |
 +--> QRS detection
 |
 +--> Wave delineation
 |
 +--> Data compression
 |
 v
Conditioned ECG + temporal information
```

The timing information generated by the QRS detector can also be fed
back to other processing stages.

This is an important systems-level concept:

> ECG processing does not necessarily have to be a simple one-way chain.
> Information generated by one stage can improve another stage.

For our project, the most important parts are preprocessing and QRS
detection.

------------------------------------------------------------------------

# 9. ECG Preprocessing

The paper discusses several major sources of interference.

## 9.1 Baseline wander

Baseline wander is a low-frequency variation of the ECG baseline.

Possible causes include:

-   respiration
-   electrode movement
-   changes in electrode impedance
-   body movement

A high-pass filter can suppress this component, but the cutoff must be
selected carefully.

The important principle is:

> Filtering is contextual.

A filter should not be selected only because it removes the unwanted
component. It must also preserve the ECG information required by the
subsequent algorithm.

------------------------------------------------------------------------

# 10. Power-Line Interference

Power-line interference appears around the mains frequency, commonly 50
or 60 Hz depending on the electrical system.

The paper discusses the use of narrowband filtering/notch-type
techniques.

A major point is that filtering can introduce distortion.

For a system whose goal is only heart-rate estimation, removing a narrow
interference component may be acceptable.

For morphological analysis, however, the same filtering operation may
need to be evaluated much more carefully.

### Project implication

For an initial FPGA FHR project, the requirement is primarily reliable
fetal QRS timing. Therefore, the filter design can be optimized for
**QRS detectability**, but if we later claim preservation of full fetal
morphology, we must perform a much stricter distortion analysis.

------------------------------------------------------------------------

# 11. Muscle Noise

Muscle noise is more difficult because its spectrum overlaps with ECG.

This means:

``` text
ECG spectrum
      +
EMG spectrum
      |
      v
overlap
```

A simple frequency cutoff cannot perfectly separate them.

The paper discusses exploiting the repetitive nature of ECG, including
ensemble-averaging approaches.

This is a major lesson:

> Not every artifact is a frequency-filtering problem.

Some interference must be handled using temporal or statistical
information.

This becomes even more important for fetal ECG.

------------------------------------------------------------------------

# 12. QRS Detection Structure

One of the most useful sections for our project is the general QRS
detector architecture.

The paper describes a detector with:

``` text
ECG
 |
 v
Linear band-pass filter
 |
 v
Nonlinear transformation
 |
 v
Decision rule
 |
 v
QRS location
```

## 12.1 Band-pass stage

The linear filter is designed to preserve the spectral content of the
QRS complex while suppressing unwanted components such as P and T waves.

The paper gives typical detector filter characteristics around:

-   center frequency: approximately 10--25 Hz
-   bandwidth: approximately 5--10 Hz

These values are detector-oriented rather than universal ECG filtering
specifications.

## 12.2 Nonlinear transformation

The purpose is to make QRS complexes more prominent relative to the
background.

Examples include:

\[ y\[n\]=\|x\[n\]\| \]

or

\[ y\[n\]=x\^2\[n\] \]

Squaring has two useful properties:

1.  negative and positive slopes both become positive;
2.  large amplitudes are emphasized relative to small amplitudes.

Therefore:

``` text
band-pass ECG
       |
       v
     square
       |
       v
positive QRS peaks
       |
       v
threshold
```

This is extremely FPGA-friendly.

------------------------------------------------------------------------

# 13. Decision Logic

After filtering and nonlinear transformation, the detector needs a
decision mechanism.

A simple version is:

\[ y\[n\] \> T `\Rightarrow `{=tex}QRS \]

But a fixed threshold can fail when signal amplitude changes.

Therefore practical QRS detectors commonly use adaptive or dynamically
updated thresholds.

For our project, this is an important design decision:

### Fixed threshold

Advantages:

-   very simple
-   deterministic
-   minimal hardware

Disadvantages:

-   sensitive to amplitude variation

### Adaptive threshold

Advantages:

-   more robust to amplitude variation
-   better suited to real recordings

Disadvantages:

-   requires additional state and update logic

We should first implement the fixed-threshold version for validation and
then introduce adaptive thresholding if necessary.

------------------------------------------------------------------------

# 14. QRS Detection Errors

The paper emphasizes that missed beats are particularly problematic.

A missed fetal beat can alter the RR sequence and therefore the
estimated fetal heart rate.

False detections can sometimes be rejected later, but missed detections
can be more difficult to recover.

This suggests that our evaluation should not focus only on the
appearance of the filtered waveform.

We need to evaluate:

-   missed fetal R-peaks
-   false fetal R-peaks
-   RR interval errors
-   FHR errors

------------------------------------------------------------------------

# 15. Paper 3 --- Rahul Kher

## Signal Processing Techniques for Removing Noise from ECG Signals

This paper is much more introductory than the FECG surveys, but it is
useful for establishing the basic preprocessing stage.

The paper identifies four common ECG artifact classes:

1.  baseline wander
2.  power-line interference
3.  EMG noise
4.  electrode-motion artifacts

------------------------------------------------------------------------

# 16. Baseline Wander

The paper describes baseline wander as a very low-frequency component,
around 0.5--0.6 Hz in the context discussed.

A high-pass filter around this region can be used for suppression.

The conceptual operation is:

\[ x\[n\]=ECG\[n\]+baseline\[n\] \]

and

\[ y\[n\]=HPF{x\[n\]} \]

The critical issue is that the cutoff cannot be chosen blindly.

The fetal ECG problem makes this more important because fetal components
may have different relative amplitudes and the abdominal signal contains
additional low-frequency physiological components.

------------------------------------------------------------------------

# 17. Power-Line Noise

The paper discusses 50/60-Hz interference and notch filtering.

Conceptually:

\[ y\[n\]=Notch\_{50Hz}{x\[n\]} \]

For our Indian laboratory environment, 50 Hz is the relevant mains
frequency.

A notch filter can be implemented as an FIR or IIR structure.

### FPGA consideration

A notch filter is attractive because:

-   its structure is deterministic
-   coefficients are fixed
-   it can operate sample-by-sample
-   the required arithmetic can be fixed-point

But if our later processing already uses a band-pass that strongly
attenuates 50 Hz, a separate notch filter may not be necessary.

The final architecture should be based on measured data rather than
blindly stacking filters.

------------------------------------------------------------------------

# 18. EMG Noise

The paper describes EMG noise as relatively high-frequency interference.

A low-pass filter can suppress part of this interference.

However, this is only a partial solution because physiological noise can
overlap the useful ECG spectrum.

This point agrees with Sörnmo & Laguna: **frequency overlap limits what
conventional filtering can accomplish.**

------------------------------------------------------------------------

# 19. MATLAB Material

One useful aspect of the Kher paper is that it includes MATLAB examples.

For us, MATLAB/Python should be used as the **reference implementation
environment** before Verilog.

The development process should therefore be:

``` text
Dataset
  |
  v
MATLAB/Python
  |
  +--> visualize raw signal
  |
  +--> design filters
  |
  +--> test filtering
  |
  +--> test FECG extraction
  |
  +--> detect R-peaks
  |
  +--> calculate metrics
  |
  v
Reference output
  |
  v
Verilog implementation
```

The MATLAB/Python implementation is not the final project. It is the
software reference against which the FPGA implementation can be
compared.

------------------------------------------------------------------------

# 20. Paper 4 --- Abel et al.

## A Comprehensive Survey on Signal Processing and Machine Learning Techniques for Non-Invasive Fetal ECG Extraction

## 20.1 This is the most directly relevant paper

Unlike the first three papers, this paper is specifically about
extracting fetal ECG from abdominal recordings.

The paper emphasizes that non-invasive fetal ECG is attractive because
abdominal electrodes can acquire information without directly contacting
the fetus.

The main problem is the poor signal-to-noise ratio of the fetal
component due to dominant maternal ECG and other interference.

------------------------------------------------------------------------

# 21. Generic FECG Extraction Pipeline

The paper gives a general architecture:

``` text
Abdominal ECG
      |
      v
Preprocessing
      |
      +--> power-line suppression
      +--> baseline-wander suppression
      |
      v
Maternal ECG separation/cancellation
      |
      v
Noisy FECG
      |
      v
FECG denoising
      |
      v
Fetal QRS detection
      |
      v
FHR / morphology analysis
```

This is the architecture that should guide our project.

------------------------------------------------------------------------

# 22. Single-Channel vs Multi-Channel Processing

The survey makes an important distinction.

## Single-channel methods

Use one abdominal ECG signal.

### Advantages

-   simpler hardware
-   fewer ADC channels
-   lower data throughput
-   lower memory requirement
-   simpler FPGA architecture

### Disadvantages

-   less spatial information
-   harder separation problem
-   potentially lower robustness

## Multi-channel methods

Use multiple abdominal channels, sometimes together with maternal
thoracic reference channels.

### Advantages

-   more information about the sources
-   potentially better source separation
-   can exploit spatial differences

### Disadvantages

-   more ADC channels
-   more storage
-   more computation
-   more complicated FPGA architecture
-   more complicated electrode setup

This distinction is extremely important when defining our project scope.

------------------------------------------------------------------------

# 23. Adaptive Filtering

The survey describes adaptive noise cancellation as one of the major
FECG extraction approaches.

The conceptual system is:

``` text
              Reference
                  |
                  v
             Adaptive
              filter
                  |
                  v
AECG ---------- subtract ----------> FECG estimate
```

The adaptive filter attempts to estimate the maternal component
contained in the abdominal signal.

If:

\[ x\[n\]=f\[n\]+m\[n\]+n\[n\] \]

and the adaptive filter produces:

\[ `\widehat{m}`{=tex}\[n\] \]

then:

\[ `\widehat{f}`{=tex}\[n\]=x\[n\]-`\widehat{m}`{=tex}\[n\] \]

The entire problem therefore becomes:

> How accurately can we estimate the maternal ECG without removing fetal
> ECG?

This is the central tradeoff.

------------------------------------------------------------------------

# 24. What Reference Signal Can Be Used?

Depending on the algorithm, the reference can be:

-   maternal thoracic ECG
-   another abdominal channel
-   an estimated maternal component
-   a derived maternal template

This creates two broad project possibilities.

### Option A --- Reference-assisted adaptive filtering

``` text
Thoracic maternal ECG
        |
        v
 adaptive filter
        |
AECG --> subtract --> FECG
```

This is conceptually simpler because a reference correlated with
maternal ECG is available.

### Option B --- Single-channel/template-based processing

``` text
AECG
 |
 v
detect maternal beats
 |
 v
construct maternal template
 |
 v
subtract template
 |
 v
FECG
```

This avoids needing a dedicated maternal reference but requires reliable
maternal QRS detection first.

------------------------------------------------------------------------

# 25. Template Subtraction

The survey describes template subtraction as a relatively
straightforward method.

The general sequence is:

1.  detect maternal R-peaks;
2.  segment maternal PQRST complexes;
3.  align repeated maternal beats;
4.  average them to construct a maternal template;
5.  subtract the template from the abdominal signal;
6.  analyze the residual for fetal QRS complexes.

Mathematically:

\[
`\widehat{m}`{=tex}(n)=`\text{average of aligned maternal beats}`{=tex}
\]

then:

\[ `\widehat{f}`{=tex}(n)=x(n)-`\widehat{m}`{=tex}(n) \]

The method can be applied to single-channel or multichannel abdominal
recordings.

### Important limitation

The maternal ECG is not perfectly identical from beat to beat.

Therefore, a fixed template can leave maternal residuals.

Also, fetal beats may overlap temporally with maternal beats.

This overlap is one of the difficult cases for template subtraction.

------------------------------------------------------------------------

# 26. Blind Source Separation

The survey discusses PCA and ICA as source-separation methods.

The underlying assumption is that the abdominal ECG is a mixture of
several sources.

A simplified model is:

\[ `\mathbf{x}`{=tex}(t)=A`\mathbf{s}`{=tex}(t) \]

where:

-   (`\mathbf{x}`{=tex}) = measured signals
-   \(A\) = mixing matrix
-   (`\mathbf{s}`{=tex}) = underlying source signals

The objective of blind source separation is to estimate the original
components from their mixtures.

## PCA

Principal Component Analysis finds orthogonal directions explaining
large amounts of variance.

A large maternal component may appear strongly in one or more principal
components.

## ICA

Independent Component Analysis attempts to separate statistically
independent sources.

This can be more appropriate when the sources have different statistical
properties.

### FPGA implication

PCA/ICA are substantially more complicated than simple FIR filters or
adaptive cancellation.

They involve:

-   matrices
-   covariance/statistical calculations
-   normalization
-   iterative or decomposition operations
-   multiple channels

Therefore, they should not automatically become our first FPGA
implementation.

They are valuable as reference algorithms and possible future
extensions.

------------------------------------------------------------------------

# 27. Wavelet Transform

The survey repeatedly discusses wavelets.

Wavelets are useful because ECG is a **non-stationary signal**.

A Fourier transform tells us mainly which frequencies are present.

A wavelet transform gives information about:

-   frequency scale
-   time location

This is useful when ECG events are transient.

A wavelet-based FECG pipeline can look like:

``` text
AECG
 |
 v
Wavelet decomposition
 |
 +--> remove selected components
 |
 v
denoised signal
 |
 v
MECG estimation/removal
 |
 v
FECG
```

### FPGA implications

Wavelets can be implemented in hardware, but they require:

-   multiple filtering stages
-   downsampling
-   memory
-   coefficient storage
-   careful boundary handling

A small discrete wavelet transform is feasible, but a sophisticated
multilevel wavelet + ICA system would substantially increase project
complexity.

------------------------------------------------------------------------

# 28. Hybrid Techniques

The survey contains many hybrid methods.

Examples include combinations of:

-   ICA + ANFIS + wavelet
-   adaptive filtering + wavelet
-   Kalman filtering + ANFIS
-   differential evolution + Kalman smoother + ANFIS
-   EMD + MUSIC
-   ICA + RLS + wavelet

These demonstrate the breadth of research in FECG extraction.

They also show why we should define a strict project boundary.

A paper describing a sophisticated hybrid method does **not** imply that
reproducing the whole method is necessary for an undergraduate FPGA
project.

------------------------------------------------------------------------

# 29. Databases Listed by the Survey

One of the most useful sections for our project is the database section.

## Daisy Database / DDB / DLDB

The survey describes:

-   8 ECG channels
-   5 abdominal
-   3 thoracic
-   single fetus
-   approximately 10 s records
-   250 Hz sampling frequency

## NIFECGDB

-   55 multichannel recordings
-   3--4 abdominal channels
-   2 thoracic channels
-   gestational ages approximately 21--40 weeks
-   1 kHz sampling

## ADFECGDB

-   4 abdominal signals
-   scalp ECG
-   recordings from 5 women during labor
-   fetal QRS annotations available

## PhysioNet / Computing in Cardiology Challenge Database

-   4 abdominal channels per record
-   public training data
-   reference fetal QRS annotations

This database is particularly useful because it allows algorithm
evaluation against reference annotations.

## FECGSYNDB

Synthetic fetal ECG database based on a synthetic generator and
volume-conductor modeling.

Useful for controlled experiments because signal characteristics can be
varied systematically.

## NIFEADB

Contains fetal arrhythmia and normal recordings.

## NIMFECGDD

The survey describes a multimodal database containing:

-   abdominal ECG
-   maternal respiration
-   fetal cardiac Doppler

with abdominal signals sampled at high frequency.

------------------------------------------------------------------------

# 30. Evaluation Metrics

The survey emphasizes that extraction quality is often ultimately
evaluated through fetal R-peak detection.

Let:

-   TP = correctly detected fetal R-peaks
-   FP = false fetal R-peaks
-   FN = missed fetal R-peaks

## Sensitivity

\[ Se=`\frac{TP}{TP+FN}`{=tex} \]

This measures how many actual fetal R-peaks were detected.

## Positive Predictive Value

\[ PPV=`\frac{TP}{TP+FP}`{=tex} \]

This measures how many detected peaks were actually correct.

## F1 Score

\[ F1= `\frac{2(Se)(PPV)}`{=tex} {Se+PPV} \]

This combines sensitivity and PPV.

## Accuracy

The survey also gives:

\[ Acc= `\frac{TP}`{=tex} {TP+FP+FN} \]

These metrics should be part of our validation framework.

------------------------------------------------------------------------

# 31. Important Warning About Comparing Papers

The survey explicitly points out that direct comparison of published
algorithms is difficult because papers may use:

-   different databases
-   different records
-   different recording durations
-   different channel configurations
-   different sampling frequencies
-   different preprocessing
-   different evaluation protocols

Therefore:

> A performance percentage from one paper cannot automatically be
> compared with a percentage from another paper.

For our project, we should select one database and evaluate all versions
of our algorithm on the same records.

------------------------------------------------------------------------

# 32. Survey Conclusions

The survey identifies two major future directions that are directly
relevant to us:

1.  better digital preprocessing/filter design;
2.  hardware-level implementation of FECG extraction systems and
    signal-acquisition systems with better SNR.

It also emphasizes the difficulty of obtaining a clean fetal ECG because
the fetal component is weak relative to maternal and other interference.

This is strong justification for a project focused on digital FECG
extraction and FPGA implementation.

------------------------------------------------------------------------

# 33. Paper 5 --- Hasan et al.

## Detection and Processing Techniques of FECG Signal for Fetal Monitoring

This is an older review focused specifically on fetal ECG detection,
processing and monitoring.

It provides a broad historical view of the algorithms used for FECG.

------------------------------------------------------------------------

# 34. Algorithms Listed by Hasan et al.

The paper discusses methods including:

-   averaged-pattern subtraction
-   matched filtering
-   adaptive filtering
-   orthogonal basis functions
-   fractal methods
-   temporal-structure methods
-   frequency tracking
-   polynomial networks
-   wavelets
-   real-time signal processing
-   threshold methods
-   spectral analysis
-   linear combinations
-   weighted sums
-   PCA
-   ICA
-   SVD
-   IIR adaptive filtering
-   genetic algorithms
-   neural networks
-   fuzzy logic

This is useful as a map of the research field.

It should not be interpreted as a requirement to implement all of them.

------------------------------------------------------------------------

# 35. Blind Source Separation

The paper identifies PCA and ICA as important approaches for separating
maternal and fetal components.

The conceptual idea is:

\[ `\mathbf{x}`{=tex}=A`\mathbf{s}`{=tex} \]

where the abdominal signals are mixtures of several physiological
sources.

Multiple channels make this problem more informative because different
electrodes observe different mixtures.

This is one reason multichannel FECG systems are common in research.

------------------------------------------------------------------------

# 36. Wavelets

The paper notes that wavelet methods are well suited to non-stationary
ECG signals.

The important advantage is time-frequency localization.

For example:

``` text
AECG
 |
 v
wavelet decomposition
 |
 +--> low-frequency components
 |
 +--> mid-frequency components
 |
 +--> high-frequency components
 |
 v
select/reconstruct useful components
```

Wavelets can therefore be used for:

-   denoising
-   QRS localization
-   separation
-   feature extraction

------------------------------------------------------------------------

# 37. Real-Time Processing

A particularly relevant point is that Hasan et al. include real-time
signal processing and hardware implementations among the research
directions.

This is directly aligned with an FPGA project.

However, there is a major distinction:

### Software prototype

The algorithm can use:

-   floating point
-   MATLAB functions
-   matrix operations
-   iterative optimization

### FPGA implementation

We need to replace these with:

-   fixed-point representation
-   streaming data paths
-   finite-state machines
-   finite-length memories
-   pipelined arithmetic
-   fixed coefficients
-   deterministic latency

This conversion is itself an important engineering part of our project.

------------------------------------------------------------------------

# 38. Relationship Between the Five Papers

The papers form a hierarchy.

## Layer 1 --- Basic ECG noise filtering

**Kher**

``` text
baseline
powerline
EMG
motion
```

Provides basic preprocessing concepts.

## Layer 2 --- General ECG processing

**Sörnmo & Laguna**

``` text
noise filtering
      ↓
QRS detection
      ↓
wave delineation
      ↓
measurements
```

Provides the general signal-processing architecture.

## Layer 3 --- Hardware-efficient digital processing

**Ahlstrom & Tompkins**

``` text
integer filters
      ↓
real-time processing
      ↓
QRS detection
```

Provides implementation ideas suitable for limited hardware.

## Layer 4 --- Fetal ECG extraction

**Hasan et al.**

``` text
AECG
 ↓
MECG/FECG separation
 ↓
FECG
```

Provides the FECG algorithm landscape.

## Layer 5 --- Modern FECG survey and datasets

**Abel et al.**

``` text
AECG
 ↓
preprocessing
 ↓
MECG separation
 ↓
FECG denoising
 ↓
FQRS detection
 ↓
FHR
```

Provides modern algorithm categories, public databases and evaluation
metrics.

------------------------------------------------------------------------

# 39. What the Papers Collectively Tell Us to Build

The literature supports a project architecture like:

``` text
                    ┌─────────────────────┐
                    │ FECG DATABASE       │
                    └──────────┬──────────┘
                               |
                               v
                    Abdominal ECG samples
                               |
                               v
                    ┌─────────────────────┐
                    │ PREPROCESSING       │
                    │                     │
                    │ Baseline removal    │
                    │ Power-line removal  │
                    │ Band limiting       │
                    └──────────┬──────────┘
                               |
                               v
                    ┌─────────────────────┐
                    │ MECG CANCELLATION   │
                    │                     │
                    │ Template subtraction│
                    │ OR adaptive filter  │
                    └──────────┬──────────┘
                               |
                               v
                    ┌─────────────────────┐
                    │ FECG CLEANUP        │
                    └──────────┬──────────┘
                               |
                               v
                    ┌─────────────────────┐
                    │ FQRS DETECTOR       │
                    │                     │
                    │ Band-pass           │
                    │ Nonlinear transform │
                    │ Threshold            │
                    └──────────┬──────────┘
                               |
                               v
                    ┌─────────────────────┐
                    │ RR INTERVAL         │
                    └──────────┬──────────┘
                               |
                               v
                    ┌─────────────────────┐
                    │ FETAL HEART RATE    │
                    └─────────────────────┘
```

------------------------------------------------------------------------

# 40. The Most Important Algorithmic Decision

The papers give us several possible approaches for maternal ECG
cancellation.

## Approach A --- Template subtraction

### Processing

``` text
AECG
 |
 v
Maternal QRS detection
 |
 v
Beat alignment
 |
 v
Average maternal beats
 |
 v
Maternal template
 |
 v
Subtract template
 |
 v
FECG
```

### Advantages

-   conceptually understandable
-   relatively simple arithmetic
-   suitable for single-channel processing
-   relatively hardware-friendly

### Problems

-   requires reliable maternal QRS detection
-   maternal morphology changes
-   fetal/maternal QRS overlap is difficult
-   template quality affects the residual

------------------------------------------------------------------------

# 41. Approach B --- LMS/RLS-Type Adaptive Filtering

Conceptually:

``` text
reference maternal signal
          |
          v
    adaptive filter
          |
          v
estimated maternal ECG
          |
AECG -----subtract-----> FECG
```

For an LMS-style adaptive filter, a generic update is:

\[ y\[n\]=`\mathbf{w}`{=tex}\^T\[n\]`\mathbf{x}`{=tex}\[n\] \]

\[ e\[n\]=d\[n\]-y\[n\] \]

\[ `\mathbf{w}`{=tex}\[n+1\] = `\mathbf{w}`{=tex}\[n\] +
`\mu `{=tex}e\[n\]`\mathbf{x}`{=tex}\[n\] \]

where:

-   (d\[n\]) = desired/primary signal
-   (`\mathbf{x}`{=tex}\[n\]) = reference input vector
-   (`\mathbf{w}`{=tex}\[n\]) = adaptive coefficients
-   (y\[n\]) = estimated interference
-   (e\[n\]) = residual
-   (`\mu`{=tex}) = adaptation step size

This is not presented here as an exact equation from the FECG survey; it
is the standard LMS formulation that corresponds to the adaptive-filter
architecture discussed in the literature.

### FPGA issues

The algorithm needs:

-   coefficient memory
-   sample delay line
-   multipliers
-   accumulation
-   coefficient update
-   fixed-point scaling

It is still feasible on a Spartan-7, but more involved than a fixed FIR
filter.

------------------------------------------------------------------------

# 42. Approach C --- PCA/ICA

These methods become attractive when multiple abdominal channels are
available.

Example:

``` text
AECG1 ----+
AECG2 ----+
AECG3 ----+----> source separation ----> components
AECG4 ----+
```

Possible output components:

``` text
Component 1 → maternal
Component 2 → fetal
Component 3 → noise
...
```

### FPGA complexity

Higher because of:

-   matrices
-   covariance calculations
-   iterative operations
-   multiple channels
-   normalization
-   numerical precision requirements

For an initial FPGA implementation, this is a substantial increase in
complexity.

------------------------------------------------------------------------

# 43. Approach D --- Wavelet-Based Processing

Wavelet processing is useful for:

-   denoising
-   transient detection
-   QRS enhancement
-   multiscale decomposition

But implementation requires:

-   filter banks
-   coefficient memory
-   decimation/interpolation
-   boundary handling
-   multiple scales

It is feasible on FPGA, but it is not the minimum-complexity path.

------------------------------------------------------------------------

# 44. QRS Detector We Can Derive From the Literature

A compact detector can be:

``` text
FECG estimate
     |
     v
Band-pass filter
     |
     v
Squaring
     |
     v
Moving-window integration
     |
     v
Adaptive threshold
     |
     v
R-peak decision
     |
     v
RR interval
     |
     v
FHR
```

The first three stages are strongly supported by the general
QRS-processing literature.

Moving-window integration is a standard enhancement, but if we use it we
should document the exact chosen detector rather than attributing the
entire block directly to one paper.

------------------------------------------------------------------------

# 45. Fetal Heart Rate Calculation

Once fetal R-peaks are detected:

\[ RR_i=t\_{i+1}-t_i \]

If (RR_i) is measured in seconds:

\[ FHR_i=`\frac{60}{RR_i}`{=tex} \]

If samples are used:

\[ RR_i\^{(samples)}=n\_{i+1}-n_i \]

and with sampling frequency (f_s):

\[ FHR_i= `\frac{60f_s}`{=tex} {RR_i\^{(samples)}} \]

This calculation is trivial in software but should be deliberately
designed in FPGA.

For example, instead of a general floating-point division, an
implementation can use:

-   integer/fixed-point division
-   reciprocal lookup table
-   scaling and integer arithmetic

------------------------------------------------------------------------

# 46. Validation Strategy

This is one of the strongest conclusions from the papers.

## Stage 1 --- Software reference

Use Python or MATLAB.

Input:

``` text
public FECG dataset
```

Generate:

-   filtered signal
-   estimated maternal component
-   residual fetal ECG
-   fetal R-peaks
-   FHR

Store the exact output.

## Stage 2 --- Fixed-point software model

Before Verilog:

``` text
floating-point model
        |
        v
quantize to fixed point
        |
        v
fixed-point model
```

Compare the two.

This catches numerical problems before hardware.

## Stage 3 --- Verilog simulation

Feed the same samples to the Verilog design.

Compare:

``` text
Python reference
       vs
Verilog simulation
```

Compare sample-by-sample where appropriate.

## Stage 4 --- FPGA

Load the same test sequence into the FPGA.

Capture:

-   filtered output
-   fetal ECG estimate
-   QRS detection signal
-   R-peak events
-   FHR

Then compare with the software reference.

------------------------------------------------------------------------

# 47. Metrics We Should Report

At minimum:

### Signal-level

-   waveform comparison
-   noise suppression
-   residual maternal ECG
-   timing alignment

### Peak-level

\[ Sensitivity=`\frac{TP}{TP+FN}`{=tex} \]

\[ PPV=`\frac{TP}{TP+FP}`{=tex} \]

\[ F1=`\frac{2Se\cdot PPV}{Se+PPV}`{=tex} \]

### Heart-rate level

Compare:

\[ FHR\_{FPGA} \]

against:

\[ FHR\_{reference} \]

Possible quantities:

\[ Error\_{FHR}=FHR\_{FPGA}-FHR\_{reference} \]

and

\[ \|Error\_{FHR}\| \]

The exact final metrics should be selected according to the dataset
annotations and project requirements.

------------------------------------------------------------------------

# 48. FPGA Implementation Considerations

## 48.1 Streaming architecture

The FPGA should ideally process samples as a stream:

``` text
sample[n]
   |
   v
filter
   |
   v
MECG cancellation
   |
   v
QRS detector
   |
   v
output
```

This avoids storing an entire ECG record on-chip.

## 48.2 Fixed-point arithmetic

The FPGA design should use fixed-point values such as:

\[ Qm.n \]

where:

-   \(m\) = integer bits
-   \(n\) = fractional bits

The number of bits must be determined from:

-   ADC/sample range
-   filter coefficient range
-   accumulation growth
-   adaptive-filter coefficient range
-   required numerical precision

Do not choose the width arbitrarily.

## 48.3 Quantization

If a floating-point coefficient is:

\[ c=0.1234 \]

and we use (N) fractional bits:

\[ c\_{int}=round(c2\^N) \]

Then the FPGA uses:

\[ c`\approx`{=tex}`\frac{c_{int}}{2^N}`{=tex} \]

This makes multiplication possible using integer hardware.

------------------------------------------------------------------------

# 49. FPGA Resources We Need to Think About

A Spartan-7-class FPGA provides the basic resources needed for this type
of streaming DSP:

-   LUTs
-   flip-flops
-   block RAM
-   DSP slices
-   clocking resources
-   I/O

The main design question is not simply:

> "Can the FPGA run it?"

It is:

> "Can we represent the algorithm accurately enough in fixed point while
> meeting the required sample rate and latency?"

For ECG sampling rates in the hundreds or low thousands of samples per
second, the raw throughput requirement is modest compared with the clock
speed of a modern FPGA. The challenge is therefore primarily
**algorithmic correctness and numerical implementation**, not raw sample
throughput.

------------------------------------------------------------------------

# 50. What We Should Not Do

## Do not start with ICA + wavelets + neural networks

That creates a large verification problem immediately.

## Do not start with FPGA

First establish:

``` text
dataset
  ↓
algorithm
  ↓
software output
  ↓
metrics
```

Only then implement hardware.

## Do not judge the algorithm by waveform appearance alone

A waveform that visually looks cleaner can still produce incorrect fetal
R-peaks.

The final test must be based on annotated reference data.

## Do not compare results from different datasets as if they were directly comparable

The Abel survey explicitly identifies this as a problem in the
literature.

## Do not assume that a generic ECG filter is automatically suitable for FECG

The fetal ECG extraction problem is dominated by maternal ECG and source
separation, not merely baseline and power-line noise.

------------------------------------------------------------------------

# 51. Recommended Development Sequence

## Phase 1 --- Understand the signal

Take one public FECG record and plot:

``` text
abdominal channel
maternal reference if available
reference fetal QRS annotations
```

Determine:

-   sampling frequency
-   amplitude range
-   number of channels
-   record duration
-   annotation format

## Phase 2 --- Preprocessing

Implement:

1.  baseline removal
2.  50-Hz suppression if necessary
3.  appropriate band limitation

Plot before/after.

## Phase 3 --- Maternal cancellation

Start with the simplest defensible method.

Possible first implementation:

``` text
maternal QRS detection
      ↓
maternal beat alignment
      ↓
template creation
      ↓
template subtraction
```

Alternatively, if the selected database/reference configuration supports
it:

``` text
AECG + maternal reference
      ↓
LMS adaptive cancellation
      ↓
FECG
```

## Phase 4 --- Fetal QRS detector

Start with:

``` text
band-pass
   ↓
square
   ↓
integration / smoothing
   ↓
threshold
   ↓
R-peaks
```

## Phase 5 --- Metrics

Calculate:

-   TP
-   FP
-   FN
-   sensitivity
-   PPV
-   F1
-   FHR error

## Phase 6 --- Fixed-point conversion

Convert each block from floating point to fixed point.

Validate again.

## Phase 7 --- Verilog

Implement each block separately.

Recommended modules:

``` text
baseline_filter.v
notch_filter.v
bandpass_filter.v
adaptive_filter.v / maternal_template.v
square.v
moving_average.v
peak_detector.v
rr_calculator.v
fhr_calculator.v
```

## Phase 8 --- Integration

``` text
input
 ↓
preprocessing
 ↓
MECG cancellation
 ↓
FQRS detector
 ↓
FHR
```

## Phase 9 --- FPGA validation

Use the same known test sequence and compare FPGA outputs against the
fixed-point software model.

------------------------------------------------------------------------

# 52. What Each Paper Contributes to Our Final Project

  -----------------------------------------------------------------------
  Paper                               Main contribution to our project
  ----------------------------------- -----------------------------------
  **Ahlstrom & Tompkins**             Efficient real-time digital
                                      filtering, integer arithmetic,
                                      adaptive interference cancellation,
                                      QRS processing

  **Sörnmo & Laguna**                 General ECG-processing
                                      architecture, preprocessing
                                      principles, QRS detector structure,
                                      importance of detection errors

  **Kher**                            Practical baseline, power-line and
                                      EMG noise-removal concepts and
                                      MATLAB-oriented experimentation

  **Abel et al.**                     FECG-specific extraction
                                      architecture, adaptive filtering,
                                      template subtraction, PCA/ICA,
                                      wavelets, databases, metrics

  **Hasan et al.**                    Historical FECG algorithm
                                      landscape, source-separation
                                      methods, wavelets, adaptive
                                      filters, real-time/hardware
                                      directions
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 53. Most Important Concepts We Need to Learn

Before implementing the project, we need to understand these topics.

## Signal processing

-   sampling theorem
-   discrete-time signals
-   FIR filters
-   IIR filters
-   frequency response
-   cutoff frequency
-   notch filters
-   band-pass filters
-   baseline wander
-   power-line interference
-   fixed-point arithmetic
-   quantization

## ECG processing

-   P wave
-   QRS complex
-   T wave
-   R-peak
-   RR interval
-   heart rate
-   QRS detection

## FECG-specific processing

-   abdominal ECG
-   maternal ECG
-   fetal ECG
-   source separation
-   adaptive noise cancellation
-   LMS
-   template subtraction
-   PCA
-   ICA
-   wavelet transform

## FPGA

-   streaming architecture
-   registers
-   delay lines
-   counters
-   finite-state machines
-   fixed-point multiplication
-   DSP slices
-   block RAM
-   pipelining
-   latency
-   testbench design

## Validation

-   TP
-   FP
-   FN
-   sensitivity
-   PPV
-   F1
-   FHR error
-   sample-by-sample comparison

------------------------------------------------------------------------

# 54. Final Technical Picture

The literature does **not** point to one universally correct FECG
algorithm.

Instead, it shows a hierarchy of increasingly sophisticated approaches:

``` text
Simple
 |
 +-- filtering
 |
 +-- template subtraction
 |
 +-- adaptive filtering
 |
 +-- wavelet methods
 |
 +-- PCA/ICA
 |
 +-- hybrid source-separation methods
 |
 +-- machine-learning methods
 |
Complex
```

For our project, the important engineering task is to select an
algorithm whose:

-   assumptions match the selected dataset,
-   computational requirements are manageable,
-   fixed-point representation is practical,
-   output can be validated,
-   architecture can be implemented on the Spartan-7,
-   and performance can be demonstrated quantitatively.

A reasonable project architecture to investigate first is:

``` text
                 PUBLIC FECG DATA
                        |
                        v
                ┌───────────────┐
                │ Preprocessing │
                │               │
                │ baseline      │
                │ power-line    │
                │ band limiting │
                └───────┬───────┘
                        |
                        v
              ┌───────────────────┐
              │ Maternal removal  │
              │                   │
              │ template or LMS   │
              └─────────┬─────────┘
                        |
                        v
                  FECG estimate
                        |
                        v
              ┌───────────────────┐
              │ Fetal QRS detector│
              │                   │
              │ band-pass         │
              │ nonlinear stage   │
              │ threshold         │
              └─────────┬─────────┘
                        |
                        v
                    R-peaks
                        |
                        v
                   RR intervals
                        |
                        v
                       FHR
```

The most important methodological rule is:

> **First establish a correct floating-point reference implementation.
> Then establish a fixed-point reference implementation. Only then
> implement the same processing chain in Verilog and compare the FPGA
> output against the fixed-point reference.**

That gives us a defensible path from published signal-processing methods
to a working FPGA demonstration.

------------------------------------------------------------------------

# 55. Source Notes

### Ahlstrom & Tompkins

M. L. Ahlstrom and W. J. Tompkins, "Digital Filters for Real-Time ECG
Signal Processing Using Microprocessors," *IEEE Transactions on
Biomedical Engineering*, vol. BME-32, no. 9, September 1985.

Relevant sections: - adaptive 60-Hz interference filter - Hanning
filter - integer-arithmetic low-pass/high-pass/band-pass structures -
offset removal - QRS processing

### Sörnmo & Laguna

Leif Sörnmo and Pablo Laguna, "Electrocardiogram (ECG) Signal
Processing."

Relevant sections: - ECG preprocessing - baseline wander - power-line
interference - QRS detection - nonlinear transformation - filtering and
distortion considerations

### Kher

Rahul Kher, "Signal Processing Techniques for Removing Noise from ECG
Signals," *Journal of Biomedical Engineering and Research*, 2019.

Relevant sections: - baseline wander - power-line interference - EMG
noise - electrode-motion artifacts - MATLAB filtering examples

### Abel et al.

Jaba Deva Krupa Abel, Samiappan Dhanalakshmi and R. Kumar, "A
comprehensive survey on signal processing and machine learning
techniques for non-invasive fetal ECG extraction," *Multimedia Tools and
Applications*, published online 2022; volume publication 2023.

Relevant sections: - general FECG processing pipeline - adaptive
filtering - template subtraction - PCA/ICA - wavelets - hybrid methods -
databases - performance metrics - conclusions and future hardware
directions

### Hasan et al.

M. A. Hasan, M. B. I. Reaz, M. I. Ibrahimy, M. S. Hussain and J. Uddin,
"Detection and Processing Techniques of FECG Signal for Fetal
Monitoring," *Biological Procedures Online*, 2009.

Relevant sections: - FECG clinical background - extraction algorithms -
adaptive filtering - PCA/ICA - wavelets - real-time processing -
hardware/FPGA-related implementations

------------------------------------------------------------------------

# 56. Bottom Line for the Project

The literature establishes that the project is fundamentally composed of
**three different problems**:

1.  **clean the abdominal ECG,**
2.  **separate/remove the maternal ECG,**
3.  **detect fetal QRS complexes and calculate FHR.**

The first problem is relatively standard digital signal processing.

The second is the core research problem.

The third is a well-established ECG detection problem and is
comparatively hardware-friendly.

The project should therefore be designed around a **controlled,
measurable subset of the FECG literature**, rather than attempting to
reproduce the entire research field.
