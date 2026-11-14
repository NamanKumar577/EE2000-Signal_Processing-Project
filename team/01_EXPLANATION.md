# Fetal ECG on an FPGA: the whole project, explained from zero

Private study notes for Team 8 (EE2000, IIT Hyderabad): Naman, Vivek, Anshu, Astitva.
Written on 14 Nov 2026, before the final presentation and viva.

**How to use this file.**
- Read sections 1 to 3 even if you think you know them. The viva will test the basics.
- Sections 4 to 9 tell the story and explain the final design.
- Section 10 says what each of us must revise. Section 11 is a glossary.
- Every number comes from our own files:
  - the final report `report/final_report/fpr-8.tex`. It now covers everything up to v7-DL. The newest work is in the section **"Final Phase IV: Accuracy Improvements and On-Chip Look-Ahead (v6.1, v7)"** (subsections v6.1, v7-LA, v7-DL, results, "Where the Remaining Error Is"). Everyone should read that section;
  - the newest work log `report/v61_v7/LOG.md` (v6.1 and v7);
  - the confidence-interval table `report/final_report/tables/board_v7_f1_ci.csv`;
  - `fpga_implementation/v6/README.md` and `PLANNED_CHANGES.md`;
  - the older logs `report/rtl_pc_split/LOG.md` (v6) and `report/night_20261109/` (v5);
  - the result files in `tools/accuracy/`.
- If a number here disagrees with a source file, the source file wins. Tell the others.

**Version names you will hear:**

| Name | One-line meaning |
|---|---|
| Mid-term design | Spatial PCA beamformer + threshold detector, tested on synthetic data only |
| v2 | Mid-term hardware with better weights (GEVD) computed by the PC |
| v3, v4 | Python prototypes of the new real-data algorithm |
| v5 | The whole new algorithm in C on a MicroBlaze soft processor inside the FPGA |
| v6 | Hand-written Verilog for all sample-rate work + a PC "brain" for 5 slow decisions |
| v6.1 | v6 + two small fixes (maternal detector, recalibration every 30 s) |
| v7-LA | "Look-ahead", offline: runs on the PC after the recording, uses the future |
| **v7-DL** | **"Delayed live", the final design: v6.1 + a look-ahead unit on the FPGA, about 13.5 s delay** |

---

## Contents

1. [The problem in one page](#1-the-problem-in-one-page)
2. [Background you need](#2-background-you-need)
3. [The data sets](#3-the-data-sets)
4. [The story, version by version](#4-the-story-version-by-version)
5. [The final algorithm, step by step](#5-the-final-algorithm-step-by-step)
6. [The hardware, step by step](#6-the-hardware-step-by-step)
7. [Testing](#7-testing)
8. [Results and how to read them](#8-results-and-how-to-read-them)
9. [Limitations and honest caveats](#9-limitations-and-honest-caveats)
10. [What each member must learn before the viva](#10-what-each-member-must-learn-before-the-viva)
11. [Glossary](#11-glossary)

---

## 1. The problem in one page

**What we want.** A pregnant mother wears four electrodes on her belly. From these four signals we want to find every heartbeat of the baby (the fetus) and report the **fetal heart rate (FHR)**. It must run in real time on an FPGA.

**Why it matters.** Doctors watch the FHR to check that the baby gets enough oxygen, especially during labour. The usual tools have problems:
- **Doppler ultrasound (CTG):** non-invasive, but it gives no ECG waveform. It needs repositioning when the baby moves and works worse in overweight mothers.
- **Fetal scalp electrode:** very accurate, but invasive. The membranes must be ruptured, and there is a risk of infection.
- **Non-invasive fetal ECG (NIFECG)** from belly electrodes is safe and could be worn for a long time. That is our approach.

**Why it is hard.**
1. **The baby's signal is tiny.** Fetal ECG is about 20–100 µV. The mother's ECG is about 1–5 mV. The mother is 10 to 250 times bigger.
2. **Same frequencies.** Both ECGs live in about 0.5–40 Hz. So a normal filter cannot keep the baby and remove the mother.
3. **Same time.** The two hearts beat independently, so their beats often overlap. With a mother at 75 bpm and a baby at 140 bpm, a fetal beat touches a maternal QRS about 17.5% of the time (report, Introduction).
4. **Noise.** Muscle activity, movement, electrode contact and powerline hum are added on top.
5. **Real recordings differ from simulated ones.** This surprised us most (section 4).

```
mother  :  ____/\________/\________/\________     big (1-5 mV), about 75 bpm
baby    :  __^____^____^____^____^____^____^_     small (20-100 uV), about 140 bpm
noise   :  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
---------------------------------------------
one lead:  ~~^~/\~~^~~~^/\~~^~~~^~/\~^~~~^~~~     what the electrode actually records
```

**What the device must output.**
- A list of fetal beat times, and the FHR in beats per minute (bpm).
- **Causal:** at each moment, use only the past. (v7-DL relaxes this by waiting about 13.5 s, see section 2.9.)
- **Label-free:** the algorithm never sees the correct answers. They are used only to score it.
- **On the FPGA, in real time:** our board is a RealDigital Boolean Board with a Xilinx (AMD) Spartan-7 XC7S50 chip.

---

## 2. Background you need

### 2.1 The ECG

- The heart muscle makes small electrical currents when it contracts. An **ECG (electrocardiogram)** is the voltage between electrodes on the skin, plotted against time.
- One heartbeat has three main parts:
  - **P wave:** small bump, the upper chambers (atria) contract.
  - **QRS complex:** the sharp, large spike, the main chambers (ventricles) contract. This is what we detect.
  - **T wave:** a slower bump, the ventricles recover.
- The **R peak** is the top of the QRS. We use its time as "the time of the beat".
- The **RR interval** is the time between two R peaks. Heart rate = 60 / RR (RR in seconds).
- At our sampling rate of 250 Hz, heart rate in bpm = 60 × 250 / RR in samples = 15000 / RR. Example: RR = 107 samples gives about 140 bpm.
- A fetal QRS is narrower than a maternal one (about 50 ms against 90 ms in the report's calculation), and the fetal heart beats faster.
- **FHR** = fetal heart rate. In our device, FHR = 60 × 250 / (median of the last 5 RR intervals). The median ignores one wrong interval.
- An **ectopic beat** is an extra beat that comes early, outside the normal rhythm. **Bradycardia** is a slow heart rate; for the fetus the report uses "below about 110 bpm".

```
        R
        |
        /\
  P    /  \      T
 _/\__/    \/\__/ \____      one beat
       Q    S
 |<------ RR interval ------>| next R
```

### 2.2 Signals and sampling

- An electrode gives a continuous voltage. An **ADC** (analogue-to-digital converter) measures it at a fixed rate and gives numbers. Our input numbers are **int16** (16-bit signed integers, −32768 to 32767).
- The **sampling rate** (fs) is how many numbers per second. We use **250 Hz**, so one sample every 4 ms.
  - A 60-s record has 15,000 samples per lead. A 5-min record has 75,000.
  - The highest frequency that 250 Hz can represent is half of it, 125 Hz (Nyquist). ECG content is below 40 Hz, so this is enough.
- CinC recordings come at 1 kHz. We **decimate** them to 250 Hz (low-pass filter, then keep every 4th sample), causally.
- A **lead** is one electrode channel. We use 4 leads, so each sample is a vector of 4 numbers: x[n] = (x1, x2, x3, x4).

### 2.3 Filters

- A **frequency** is how fast something wiggles, in hertz (cycles per second).
  - Baseline wander (breathing, movement) is very slow, below about 0.5 Hz.
  - The QRS is fast, roughly 10–40 Hz.
  - Powerline hum is 50 Hz (India) or 60 Hz (USA).
- A **filter** keeps some frequencies and reduces others:
  - **High-pass (HP):** keeps fast changes, removes slow drift. We use it to remove baseline wander.
  - **Low-pass (LP):** keeps slow changes, removes fast noise.
  - **Band-pass (BP):** keeps one band. We use 5–25 Hz to find the mother's QRS and 15–40 Hz for the fetal QRS during calibration.
  - **Notch:** removes one frequency (the mid-term design had a 50/60 Hz notch).
- **IIR filter, biquad, SOS.** Our filters are recursive (IIR): each output uses a few past inputs and past outputs. A long filter is split into a chain of small 2nd-order pieces called **biquads** or **second-order sections (SOS)**. This is more stable in fixed point. **Butterworth** is a classic, smooth filter design.
- **Delay (group delay).** A causal filter always delays the signal a little. The mid-term band-pass delayed the QRS band by 11.4–15.4 ms. The final design compensates known fixed delays (for example, 13 samples are subtracted from each output beat time).
- **Zero-phase filtering** runs a filter forward and then backward, so there is no delay. But the backward pass needs the future, so it is **non-causal**. The mid-term evaluation used this kind of batch processing.
- **Why filtering alone fails:** the mother and the baby share 0.5–40 Hz. You cannot remove one by frequency without destroying the other.

### 2.4 Noise and SNR

- **SNR (signal-to-noise ratio)** compares signal power to noise power, in decibels: SNR(dB) = 10·log10(P_signal / P_noise).
  - 0 dB: equal power. +3 dB: about 2×. +10 dB: 10×.
- The synthetic data set (FECGSYNDB) has five noise levels: 0, 3, 6, 9 and 12 dB. 0 dB is the noisiest.
- **SQNR** (signal-to-quantisation-noise ratio) is the same idea for the error caused by rounding numbers in fixed point. The mid-term fixed-point model reached +74.52 dB.

### 2.5 Many leads: covariance, PCA, eigenvectors, GEVD, beamformer

This is the maths behind the "spatial" methods. Intuition first.

- **Why several leads help.** The mother's heart and the baby's heart sit in different places. So each one appears on the 4 leads with a different *pattern* of sizes and signs. Even when they overlap in time and frequency, they differ in this spatial pattern.
- **Beamformer (spatial filter).** Make one new signal as a weighted sum of the leads:
  `y[n] = w1·x1[n] + w2·x2[n] + w3·x3[n] + w4·x4[n] = wᵀx[n]`.
  Choosing the weights w is like building a "virtual electrode" that listens in one direction. Good weights make the mother cancel out and keep the baby.
- **Covariance matrix R (4×4).** Entry R_ij is the average of x_i·x_j over a time window. The diagonal is the power on each lead. Off-diagonal entries say how much two leads move together.
- **Eigenvector.** A direction v with R·v = λ·v. The number λ (eigenvalue) is the signal power along that direction.
- **PCA (principal component analysis).** Find the eigenvectors and sort them by power. The first principal component (PC1) is the direction with the most power.
  - On the belly the mother dominates, so PC1 is roughly "the mother's direction". At mid-term it held 88.4% of the energy.
  - The mid-term design used w = v2, the second eigenvector, which is perpendicular to the mother's main direction.
- **The weakness of PCA.** PCA looks only at power. It does not know where the fetal beats are. On real data the second direction is often noise, not the baby.
- **GEVD (generalised eigenvalue decomposition).** Choose w to maximise a *ratio*:
  `(power around fetal beats) / (total power) = (wᵀ R_QRS w) / (wᵀ R_x w)`.
  R_QRS is the covariance measured only in short windows around fetal beats. R_x is the covariance of everything. The best w solves R_QRS·w = λ·R_x·w.
  - **Self-referencing:** we do not have labels, so the design uses its *own* detected beats to build R_QRS. It drops beats that coincide with maternal R peaks, solves, detects again with the new filter, and repeats 3 times. It starts from each PCA direction, so it gets 4 filters per signal.

```
lead 2
  ^          . . .
  |       . .:::::. .        v1 = most power (mostly mother)
  |     . ::::::::::/
  |    .:::::::::/:::.
  |     .:::::/::::::.       v2 = perpendicular to v1
  |       ./::::::.
  +-------------------------> lead 1
  Each dot is one sample (x1, x2). PCA finds the long axis of the cloud.
  GEVD instead finds the direction where the fetal beats stand out most.
```

### 2.6 Template subtraction

- The mother's beats all look similar. Average many aligned maternal beats to get a **template**. At every new maternal beat, subtract the template. What is left is baby + noise.
- On a single lead this fails when a fetal beat overlaps a maternal beat: the subtraction damages the fetal beat. At mid-term, single-lead template subtraction scored 76.36% at 12 dB and 23.88% at 0 dB on subject 1.
- **Our final version** is better in three ways:
  - It works per lead and per beat, before any spatial filtering.
  - The template is not one average. It is the **mean plus the top 2 principal components** of the last 20 beats, so it can follow shape changes.
  - It is fitted to each new beat by least squares and subtracted with tapered (smooth) edges.

### 2.7 Finding beats: detectors and trackers

- **Energy envelope.** Square (or rectify) the band-passed signal and smooth it. Beats become clear bumps.
- **Threshold detector** (Pan–Tompkins style, used at mid-term): derivative, squaring, moving-window integration, then an adaptive threshold between a running "signal level" and a running "noise level". After a detection, a **refractory period** blocks a second detection.
- **Tracker** (RR-predictive, used in the final design):
  1. Estimate the rhythm: autocorrelation of 4 s (1,000 samples) of the envelope, looking for a period between 90 and 200 bpm.
  2. Expect the next beat about one RR after the last one. Search the window 70%–130% of RR.
  3. Accept the strongest peak if it is bigger than 0.25 × the median of recent beat sizes.
  4. Update RR as the median of the last 5 intervals.
  5. After 4 misses in a row, restart from step 1.
  - Strength: it uses the rhythm, so it survives noise. Weakness: it assumes a regular rhythm, so ectopic beats hurt it.
- **Blanking.** Right after each maternal R peak, some tracks hold the envelope for a short time (45 samples in the C model). Maternal leftovers then do not look like fetal beats.

### 2.8 How we score

- **Reference annotations (labels):** the true beat times. They come from the simulator (synthetic data), from experts (CinC), or from a scalp electrode (ADFECGDB).
- **Matching:** each true beat is matched to at most one detected beat within **±50 ms**. In code this is 13 samples at 250 Hz (`TOL = 13` in `tools/accuracy/harness.py`). ±50 ms is the standard of the PhysioNet/CinC 2013 challenge.
  - **TP** (true positive): a detection matched to a true beat.
  - **FP** (false positive): a detection with no true beat.
  - **FN** (false negative): a true beat with no detection.
- **Se (sensitivity)** = TP / (TP + FN): what fraction of true beats we found.
- **PPV (positive predictive value)** = TP / (TP + FP): what fraction of our detections are real.
- **F1** = 2·Se·PPV / (Se + PPV). It is high only if both are high. This is our main number.
- **Worked example:** 100 true beats. We output 90 beats, 80 of them correct. TP = 80, FP = 10, FN = 20. Se = 80%, PPV = 88.9%, F1 = 84.2%.
- **Scoring starts at 20 s.** The design needs the first 20 s to calibrate, so beats before 20 s are not scored.
- **FHR MAE (mean absolute error, bpm).** At every true beat, take the device's FHR 0.5 s later, and compare it with the true FHR (60·fs / median of the last 5 true RR). If the device shows nothing, that counts as a full error. So gaps in the output hurt MAE a lot.
- **Mean F1** is the average of the per-record F1 values.
- **Records ≥ 90%** counts records with F1 of at least 90%.
- **95% confidence interval (CI)** for v6 was computed by bootstrap: resample the records with replacement 10,000 times and look at the spread of the mean.

### 2.9 Causal, non-causal, look-ahead and delay

- **Causal:** a decision at sample n uses only samples up to n. A live device must be causal: the future has not happened yet.
- **Non-causal tricks:** zero-phase filtering, windows centred on "now", calibrating on the whole recording.
- **The mid-term numbers were batch (non-causal).** Run causally, the same design fell from 93.0% to 82.2% (section 4).
- **Look-ahead with a delay.** You may use "future" samples if you simply *wait* for them. The answer then comes later.
  - v7-DL waits about 13.5 s (median), at most 17.5 s. It still processes a live stream, with a fixed delay.
  - v7-LA needs the whole recording, so it is offline only.
- **Latency** is this delay between a beat happening and the device reporting it. v6/v6.1: about 1.5–2 s. v7-DL final beats: about 13.5 s.

### 2.10 Labels, dev/test split, and overfitting to the test set

- **Label-free:** the algorithm never reads the annotations. Only the scoring script does. This is a rule we kept from v2 on.
- **Development (dev) set:** records we use to try ideas and choose parameters.
- **Test (held-out) set:** records we use only to report the final number of a frozen design.
- **Overfitting to the test set:** if you try many ideas and keep those that raise the *test* score, you tune the design to those particular records. The test score then looks better than the truth.
- **Our split for CinC 2013:** odd record numbers = **CinC dev** (38 records); even record numbers = **CinC test** (37 records). CinC test was scored once per frozen design.
- **Mid-term split (synthetic):** subjects sub01–sub07 for training, sub08 for validation, sub09–sub10 for test.

---

## 3. The data sets

| | FECGSYNDB | CinC 2013 set-a | ADFECGDB |
|---|---|---|---|
| Type | Synthetic (simulated) | Real | Real |
| Records | 1,250 (1,248 usable) | 75 | 5 |
| Length | 5 min | 60 s | 5 min |
| Leads we use | 4 of 34: [27, 26, 28, 25] (0-based) | the 4 abdominal leads | the 4 abdominal leads |
| Sampling | 250 Hz | 1 kHz, decimated to 250 Hz | decimated to 250 Hz when needed |
| Reference | exact, from the simulator | annotations; 7 records flagged unreliable | fetal scalp electrode (very reliable) |
| Our use | dev: 60-record subset (every 21st record); final check: all 1,248 | odd 38 = dev, even 37 = test | dev set from v4 on |

**FECGSYNDB (PhysioNet Fetal ECG Synthetic Database).**
- 10 simulated mother–baby subjects × 5 noise levels (0–12 dB) × 5 conditions × 5 repetitions (l1–l5 in the file names).
- Conditions:
  - c0: baseline;
  - c1: fetal movement;
  - c2: heart-rate changes (accelerations and decelerations);
  - c3: uterine contractions;
  - c4: ectopic beats.
- 34 channels: 32 abdominal and 2 maternal reference leads.
- The 4 leads were chosen at mid-term from a fetal-to-maternal ratio map on the training subjects only.
- **What it tells us:** behaviour under controlled noise and clinical conditions, with perfect labels.
- **What it hides:** it is easier and cleaner than real recordings. It misled us at mid-term.

**CinC 2013 (PhysioNet/Computing in Cardiology Challenge 2013, set-a).**
- 75 real 60-s recordings with reference fetal QRS annotations.
- 7 records have references flagged as unreliable: a33, a38, a47, a52, a54, a71, a74. Three are odd (dev), four are even (test). So "reliable references only" means 35 dev and 33 test records.
- **What it tells us:** real-world accuracy on many different mothers. It is our main real benchmark.
- **Weak points:** records are short. With 20 s of start-up, only about 40 s are scored. Some labels are wrong.

**ADFECGDB (Abdominal and Direct Fetal ECG Database).**
- 5 real 5-min recordings. 4 abdominal leads and a simultaneous electrode on the baby's scalp, which gives a very reliable reference.
- **What it tells us:** if we are right, we are really right; the labels are trustworthy.
- **Weak points:** only 5 records, and we used it during development from v4 on. So it is not an independent test.

---

## 4. The story, version by version

### Summary table (mean beat F1, %)

| Version | Date | What runs where | CinC test (37) | CinC dev (38) | ADFECGDB (5) | FECGSYNDB all |
|---|---|---|---|---|---|---|
| Mid-term design, batch | Oct | Python, non-causal | – | – | – | 93.0 (250 records) |
| Mid-term design, causal re-run | 31 Oct–6 Nov | same design, causal scoring | 16.7 | 22.8 | – | 82.2 |
| v2 | 7 Nov | FPGA filters + beamformer + detector; PC computes GEVD weights | 41.2 | 42.0 | 37.0 | 95.6 |
| v3 | 8 Nov | Python prototype | 49.9 | 59.4 | 78.6 | 95.0 |
| v4 | 9 Nov | Python prototype | 53.1 | 68.4 | 91.3 | 92.1 (subset) |
| v5 | 9–10 Nov | C on a MicroBlaze in the FPGA | 65.8 | 75.3 | 93.4 | 91.5 |
| v6 | 10–14 Nov | hand-written RTL + PC brain | 65.48 | 76.04 | 92.73 | 91.44 |
| v6.1 | 14 Nov | v6 + 2 fixes | 71.94 | 80.41 | 92.87 | 91.89 |
| v7-LA | 14 Nov | offline, PC, whole recording | 75.64 | 84.55 | 95.80 | 94.34 |
| **v7-DL (final)** | 14 Nov | **v6.1 + look-ahead unit on the FPGA** | **76.91** | **84.68** | **96.10** | **93.69** |

The two big jumps on real data: the new algorithm (v2 → v5) and the look-ahead (v6.1 → v7).

### 4.1 Proposal (September 2026)

- Literature survey, choice of FECGSYNDB as the benchmark, a work plan (`report/preliminary/PPR-8.pdf`).

### 4.2 Mid-term (October 2026)

**What we did.**
- We compared 9 methods on FECGSYNDB:
  - M1: 4-lead spatial PCA beamformer (the main design);
  - M2, M3: 1D U-Net, a deep neural network (4-channel and 1-channel);
  - M4: multi-lead template fusion;
  - M5: wavelet-threshold hybrid;
  - M6, M7: fixed and adaptive template subtraction;
  - M8, M9: Hankel-matrix SVD variants.
- The detector for all methods was a Pan–Tompkins-style threshold detector.
- We built a bit-true fixed-point model (Q1.15) and estimated the hardware cost.

**Results.**
- Spatial PCA: 93.00% population mean F1 on 250 records; 93.06% on the held-out test subjects; 100% on subject 1 at 12, 6 and 0 dB.
- U-Net: 97.48% test F1 (90.76% population mean). But it has 1.42 million parameters, about 8× more than the on-chip block RAM can hold.
- Single-lead methods collapsed under noise and overlap (for example, template subtraction 23.88% at 0 dB).
- Fixed point: +74.52 dB SQNR on 5,000 golden vectors.
- Hardware *estimate* only: 148 clock cycles per sample, about 990 LUTs and 1 DSP slice.

**Validation levels.** The report grades evidence from L1 to L5:
- L1 = floating-point software;
- L2 = bit-true fixed-point model;
- L3 = RTL simulation;
- L4 = synthesis and timing;
- L5 = running on the board.

At mid-term we had L1 and L2, and L4 only as an estimate.

**What we learned later:** everything was synthetic and batch (non-causal). Both turned out to matter.

### 4.3 The causal re-run and the real-data shock (31 Oct – 6 Nov)

**Four new evaluation rules from here on:**
1. strictly causal;
2. label-free;
3. ±50 ms scoring from 20 s, with the corrected FHR error;
4. dev/test split, with test scored once per frozen design.

**Results.**
- The same mid-term design dropped from 93.0% to **82.2%** on all 1,248 FECGSYNDB records, with FHR MAE 18.8 bpm.
- Three things changed at once here: causal processing, corrected scoring, and all 1,248 records instead of 250. The report does not split the drop between them.
- On real CinC data it reached only **16.7%** (test) and 22.8% (dev).

**Lesson:** synthetic batch numbers hugely overstate real accuracy. Judge a design on real recordings with a held-out split.

### 4.4 v2 (7 Nov): better weights, same architecture

**What changed.**
- The PC computes the beamformer weights by **self-referencing GEVD** (section 2.5), with a maternal-aware component choice and gated interference nulling.
- RTL fixes:
  - a hard-coded latency in the peak localiser (18) was replaced by the parameter;
  - the latency compensation went from 18 to 13 samples;
  - the detector warm-up became restartable.

**Results.**
- FECGSYNDB 82.2% → **95.6%** (FHR MAE 18.8 → 2.5 bpm).
- On the board (25 MHz, 3,881 LUTs, 39 DSP): 165,000 samples with 0 difference from the model.
- But on real data: CinC test 41.2%, CinC dev 42.0%, ADFECGDB 37.0%.

**Two diagnostics (using labels, only to understand the problem).**
- **Best possible single filter.** For each CinC record we computed the best 4-lead linear filter. It reaches only **60%** mean F1, and 65% if maternal template subtraction is done first. So no choice of weights can save this architecture on real data.
- **U-Net check.** The mid-term U-Net scored 90.0% on 179 FECGSYNDB records but **17.7%** on ADFECGDB. Changing lead polarity or scaling did not help. Its training records were not fully documented, so its synthetic score may include records it saw in training. Together with its memory needs, this confirmed: continue with a classical, explainable method.

**Lesson:** the front end itself had to change.

### 4.5 v3 and v4 (8–9 Nov): the new algorithm in Python

**New ideas:**
- remove the mother **beat by beat on each lead** first;
- keep **many candidate fetal signals ("tracks")** instead of trusting one filter;
- follow each with an **RR-predictive tracker**;
- choose the best track **without labels**.

**Results.**
- v3: 95.2 / 59.4 / 78.6 (FECGSYNDB subset / CinC dev / ADFECGDB).
- v4 (wider band, a maternal train that is re-chosen over time): 92.1 / 68.4 / 91.3.
- Held-out CinC test: v3 49.9, v4 53.1.

### 4.6 v5 (night of 9–10 Nov): the whole algorithm inside the FPGA, on a soft processor

**Why a soft processor.** Writing hand-made RTL for GEVD, SVD template fitting and 12 trackers in one night was not feasible. So the C program ran on a **MicroBlaze**: a processor built from FPGA logic, with a hardware floating-point unit, at 73.7 MHz. The PC only streamed the recording.

**Accuracy changes that night (dev numbers):**
- Removed the PC-dependent v2 track, added raw-lead GEVD candidates, and added a **maternal-coincidence penalty** (a track whose beats sit on maternal R peaks is probably the mother). Together: CinC dev 68.4 → 72.8.
- **10% maternal-energy gate:** use that penalty only if the maternal train comes from a component with ≥ 10% of the maternal-band energy. Otherwise the "mother" may really be the baby. FECGSYNDB subset 78.7 → 91.3, real data unchanged.
- **Better selection quality:**
  - RR-regularity squared, a 20-s window, a 2.5-s hop;
  - agreement between tracks;
  - a mild FHR prior.
  - Together: CinC dev +4.6.
- **Fitting the FPGA:**
  - int16 sample rings, bf16 envelopes, int8 beat snapshots, shared buffers;
  - an incremental eigen-solver instead of a 20×20 Jacobi solver.
  - Accuracy stayed within 0.3 points, and it ran 3.5× faster: about 47k cycles per sample, 5.4× real time.

**Rejected ideas (all with numbers in the night log):**
- a running (EMA) template: −1.1 on CinC dev;
- a rate-continuity rule for the maternal train;
- a longer maternal refractory period;
- penalty floors;
- tracker parameter changes;
- output gap filling: +0.5, not worth the extra delay.

**Results.**
- 65.8 (CinC test) / 75.3 (dev) / 93.4 (ADFECGDB) / 91.5 (FECGSYNDB all).
- Board bit-exact with the PC build of the same C code on all 140 records.

**Lessons.**
- A diagnostic on CinC dev showed: our selection 73.9%, best single track 82.6%, per-window oracle 85.0%. **Choosing the track was now the main loss.**
- Synthetic accuracy fell about 4 points from v2. Real data had priority.

### 4.7 v6 (10–14 Nov): our own RTL plus a PC brain

**Why.**
- v5 ran our algorithm on a processor we did not design.
- Its memory was full: 254.6 of 256 KB.

**The final architecture.**
- Every operation that runs at the sample rate is **hand-written Verilog**.
- The **PC answers only 5 low-rate decisions** and never receives the recording (section 6.3).
- Before writing Verilog, we wrote a **bit-accurate integer C model** of exactly what the FPGA computes. It became the specification.

**Results.**
- Accuracy equals v5 within ±0.8 points: 65.48 / 76.04 / 92.73 / 91.44.
- **140/140 board records bit-exact** with the C model.
- 18,127 LUTs, 33 DSP, 60/75 BRAM, 50 MHz, timing met (+0.26 ns).
- **BRAM 99% → 80%.** Two big memories are never used at the same time:
  - the 10-s maternal store (used only before 10 s);
  - the envelope rings (written only after calibration).
  - They now share one 32K × 13 memory, and not one output byte changed.
- A local **web demo** streams any recording to the board in real time.

**Failure analysis (75 CinC records).** 58 of 75 records reached F1 ≥ 50%. The 17 others:
- 7 "followed the mother": in 5 of them the maternal detector never found the mother (fixed in v6.1, see 4.8);
- 5 followed a wrong fetal-range track;
- 5 have unreliable references.

### 4.8 v6.1 (14 Nov): three ideas, two adopted

All decisions on dev sets: CinC dev, ADFECGDB, FECGSYNDB subset.

| Idea | What | Dev result (CinC dev / ADFECGDB / FECGSYNDB subset) | Decision |
|---|---|---|---|
| 1 | Maternal detectors: warm-up starts at sample 256 (after the filter start-up transient); the detector's peak level decays after 2 s without a detection | 76.0 / 92.7 / 91.8 → 79.5 / 93.3 / 91.1 | **adopted** |
| 2 | Smarter selection: maternal-rate penalty, rate voting, FHR continuity, window and weight sweeps, a logistic selector trained on 120 other synthetic records | best +0.5 on CinC dev, but −0.6 to −1.4 on FECGSYNDB; learned selector −0.5 | rejected |
| 3 | Recalibrate the 16 filters every 30 s on the latest 12 s; keep a track's old filter unless the new one gives a better beat train by a label-free score (regularity × completeness × (1 − maternal coincidence)) | 79.5 / 93.3 / 91.1 → 80.4 / 92.9 / 91.6 | **adopted** |

**Why idea 1 mattered.** In 4 of 5 CinC failures where no maternal train was found, all four maternal detectors fired **zero times** in the whole recording. The peak level was only updated on a detection. So one big early transient set a threshold that was never crossed again. Example: a73 now finds the mother at 96 bpm.

**Why idea 2 failed.** After idea 1, the chooser still lost about 5 points to the best single track (CinC dev: selected 79.5, best track 84.7, per-window oracle 87.2). No label-free rule closed this gap reliably. That gap is what v7 attacks.

**Results v6.1 (board, 140/140 bit-exact):**
- CinC test 71.94 (FHR MAE 18.37 → 11.16 bpm);
- CinC dev 80.41;
- ADFECGDB 92.87;
- FECGSYNDB all 91.89.
- With v6.1 (and v7-DL), the maternal train is found in **all 75** CinC records. In v6 it was missing in several of the failed records.

### 4.9 v7-LA (14 Nov): what if we may look into the future?

A post-processing version on the PC. It uses the whole recording but still no labels.

**How it works.**
1. Run the v6.1 front end (C model = board) to get the 16 candidate tracks.
2. Score every track in windows **centred** on each moment (±15 s: past *and* future).
3. Choose a track path over the whole recording with **Viterbi** (section 5.8). A switch costs 1, unless the two tracks agree on more than 80% of the beats.
4. Clean up beats using the rhythm on both sides.
5. Compute FHR from a centred 5-beat median.

**Dev results.**
- CinC dev 80.41 → 84.55, ADFECGDB 92.87 → 95.80, FECGSYNDB subset 91.64 → 93.91.
- The first version had no maternal confidence gate and fell to 78.43 on FECGSYNDB; with the gate it reached 93.79.

**Test results.**
- CinC test 75.64 (reliable references only: 80.94).
- FECGSYNDB all 94.34. The biggest gain was on ectopic beats: c4 77.9 → 85.8. The cause was not analysed record by record. The log names the centred windows and the two-sided clean-up as the likely reasons.

**Limit:** it needs the whole recording (or at least 15 s of look-ahead), so it is for offline review, not live monitoring.

### 4.10 v7-DL (14 Nov): the look-ahead on the FPGA (final design)

**The request.**
- Run the look-ahead **on the FPGA itself**.
- Keep sending the recording in small 64-sample parts.
- Compute the final answer on the board. A 15–20 s delay is acceptable.

**Design.**
- v6.1 plus a new RTL unit, `v7_la.v`. It only *listens* to the other units, so the v6.1 output is untouched.
- It adds new output frames (OUT7, END7).
- The PC does no extra work.

**Choosing the delay (dev sets only, integer C model):**

| Variant | CinC dev | ADFECGDB | FECGSYNDB subset | Median / max delay |
|---|---|---|---|---|
| v6.1 causal | 80.41 | 92.87 | 91.64 | 1.5–2 s |
| future 3 segments, lag 0, 1 clean-up pass | 84.68 | 96.10 | 93.39 | 13.5 / 24.1 s |
| future 3, lag 1, 2 passes | 84.87 | 96.11 | 93.45 | 17.9 / 30.4 s |
| future 4, lag 0, 1 pass | 84.59 | 96.17 | 93.51 | 16.0 / 27.5 s |
| **frozen: future 3, lag 0, 1 pass, deadline 15 s** | **84.68** | **96.10** | **93.39** | **13.5 / 17.5 s** |

**Why this choice.** The bigger options gain at most about 0.2 points but cost several seconds more delay. The deadline caps the worst case at 17.5 s with no loss on dev.

**The area problem.**
- The first RTL version of `v7_la` needed **13.2k LUTs** on its own. The full design needed 101% of the LUTs, so it **did not fit**.
- The fix: do the shifts, divisions and log2 **one bit per clock cycle** (sequentially), and give the small buffers a single read port. The output stayed identical.
- After the fix the unit needs **8.4k LUTs stand-alone** (out-of-context synthesis of the unit alone) and **7,297 LUTs inside the routed full design**.
- Together with the display unit, v7-DL adds **7.7k LUTs and 11 BRAM tiles** to v6.1 (82% of the LUTs in total).
- This is fine because the unit runs only once per 2.5 s of signal. Extra cycles cost nothing.

**Results (board, 140/140 bit-exact):**
- CinC test **76.91** (reliable only 81.95);
- CinC dev 84.68;
- ADFECGDB 96.10;
- FECGSYNDB all 93.69.

Details in section 8.

---

## 5. The final algorithm, step by step

This is v7-DL. Steps 1–7 are v6.1, step 8 is the look-ahead.

**Timeline of one recording** (from `proto.h` and the report's start-up figure):

```
time (s)  0    1     3              10              15   15.5        19.5  20
          |----|-----|---------------|---------------|----|-----------|-----|------------>
          filters run from the first sample
               maternal covariance collected (sample 256 .. 2500)
                                     PCA request -> PC; stored 10 s replayed
                                     maternal detectors, cancellation start
                     calibration data [3 s, 15 s) ----->  GEVD request -> PC
                                                          16 tracks start; trackers need 4 s
                                                                       first selected beat (~19.5 s)
                                                                             scoring starts at 20 s
  v6.1: filters recalibrated every 30 s           v7-DL: final beat leaves ~13.5 s after it happens
```

### Step 1. Front end (per lead, every sample, RTL `v6_fe`)

- **Wide-band signal xf:** a one-pole high-pass (removes baseline wander), then a Butterworth low-pass at 60 Hz.
- **Maternal band:** the same high-pass, then a 5–25 Hz band-pass. The maternal QRS is strong here.
- Integer arithmetic: data in Q8, coefficients in Q28, 64-bit accumulators (section 6.4).

### Step 2. Maternal R peaks (RTL `v6_mat` + PC)

1. The FPGA collects the 4×4 covariance of the maternal band over samples 256–2,500 (about the first 10 s). It sends it to the PC as a **COV** frame.
2. The PC does a **PCA** and returns 4 projection vectors (RSP_V, Q14).
3. The FPGA runs 4 adaptive-threshold detectors, one per projection. It replays the 2,500 stored samples through them.
4. **Every 5 s**, the PC picks which of the 4 detector trains is the mother: the slowest *regular* train (≥ 60% of RR intervals within 15% of the median) between 40 and 130 bpm (REQ_MK → RSP_MK).
5. **v6.1 fix:** the detectors start warming up at sample 256 (after the filter's start-up transient). Their peak level decays after 2 s without a detection, so one early spike cannot blind them forever.

### Step 3. Maternal cancellation, per lead (RTL `v6_canc` + PC)

1. For each new maternal R peak, take a 150-sample segment from −160 ms to +440 ms.
2. Align it (±4 samples) with the stored history, and send it to the PC (**SEG** frame).
3. The PC keeps the last 20 beats. It returns an orthonormal basis: the mean + top 2 principal components, at most 3 × 150 numbers per lead (RSP_BASIS).
4. The FPGA projects the new beat onto the basis (Q·Qᵀ·s), which is the least-squares fit. It subtracts the fit with tapered edges.
5. The result **z** is the abdominal signal with the mother removed beat by beat, including her shape changes.

### Step 4. GEVD calibration at 15 s (PC), and recalibration every 30 s (v6.1)

1. The FPGA sends 12 s (3–15 s) of z and xf as int16 (**CALDATA**), then **REQ_CAL**.
2. On the 15–40 Hz band, the PC detects beats and drops those that coincide with maternal peaks. It solves the GEVD (section 2.5), iterating 3 times from each PCA direction.
3. It returns 16 weight vectors (Q14) with flags for each track (RSP_CAL).
4. **v6.1:** every 30 s the FPGA sends the latest 12 s again (read back from its sample rings). The PC computes new filters but **keeps a track's old filter unless the new one gives a better beat train** by a label-free score: regularity × completeness × (1 − maternal coincidence). The FPGA cross-fades from the old to the new weights over 64 samples, so there is no jump. The message protocol does not change.

### Step 5. Sixteen candidate tracks (RTL `v6_trk`)

| How many | Input | Spatial filter | Beat finder |
|---|---|---|---|
| 4 | z (mother removed) | each lead alone ("unit lead") | tracker |
| 4 | z | GEVD filters of z | tracker |
| 4 | xf (mother not removed) | GEVD filters of xf | tracker |
| 4 | xf | the same 4 GEVD filters of xf | threshold detector |

- So there are 12 trackers + 4 threshold detectors.
- For each track the FPGA does:
  - the projection (4 multiply-adds);
  - a band-pass;
  - the energy envelope;
  - maternal blanking (on the tracks that use it);
  - the tracker or detector.
- What it sends to the PC:
  - **BEAT** (track, time);
  - **FEAT** (a 31-sample beat snapshot + peak energy);
  - **BMED** (medians of 125-sample envelope blocks).
- **Why keep 16 tracks?** On real data, no single filter is reliably right (the 60% diagnostic). Different tracks win on different records and at different times.

### Step 6. Label-free selection every 2.5 s (PC, live part)

Each track k gets a quality over the trailing 20 s:

```
Q_k = shape_k × acceptance_k × log(1 + prominence_k) × regularity_k² × (0.5 + agreement_k) × prior(FHR_k) × maternal_penalty_k
```

- **shape:** median correlation between beat snapshots. Real beats look alike.
- **acceptance:** how often the tracker accepted the beat it looked for.
- **prominence:** how much the beats stand out from the envelope.
- **regularity:** fraction of RR intervals within 15% of their median. Squared, so it matters a lot.
- **agreement:** how many of its beats other tracks also found.
- **FHR prior:** a mild physiological weight. It is 0.2 at 80 bpm and rises to 1 at ≥ 120 bpm. It was kept mild on purpose so that a true slow fetal heart is not punished too much. A stronger prior gained +0.4 on CinC dev and was rejected.
- **maternal penalty:** clip((0.6 − c)/0.3, 0, 1), where c is the fraction of the track's beats within ±48 ms of a maternal R peak. It is applied only if the maternal train comes from a PCA component holding ≥ 10% of the maternal-band energy (the "gate").

The best track's beats go out as **OUT** frames, with 13 samples of latency compensation, together with FHR = 15000 / (median of the last 5 RR). Delay: about 1.5–2 s.

### Step 7. What the v6.1 live output is

- These are the **live** beats. In v7-DL they still come out unchanged. The web page shows them as the "live estimate".

### Step 8. The v7 look-ahead (RTL `v7_la`, model `v7_post.c`)

**What it listens to.**
- It taps every frame the other units write: BEAT, FEAT, MPK (maternal peaks), COV.
- It also taps two PC answers: RSP_V and RSP_MK.
- It keeps recent beats of all 16 tracks. For the beat shapes it keeps only one sum of normalised snapshots per 2.5-s slot (31 sums), which saves memory.

**Segments and window.**
- The recording is cut into 2.5-s segments (625 samples). The first one used is segment 7, which covers 17.5–20 s.
- Segment i is judged on a window from **6 segments before** to **3 segments after**: from 15 s before the segment to 7.5 s after it (the report's wording). The work log says the same thing as "15 s before to 10 s after", counting from the segment's start.
- The unit runs for segment i when the sample counter reaches 9 s after the segment's end: 7.5 s of future plus a 1.5-s margin for beats that are reported late.

```
           window used to score the tracks for segment i (25 s)
   |<------------- 15 s past ------------>|<- seg i ->|<-- 7.5 s future -->|<1.5 s>|
   ---------------------------------------[ 2.5 s   ]---------------------------- decide segment i
```

**Quality, in log2.** For each track, over the window:
- **shape consistency:** the length of the mean of the *normalised* beat snapshots. If all beats have the same shape, the unit vectors point the same way and the mean is long. Random shapes give a short mean.
- **completeness:** beats × median RR / window length, capped at 1. Is the window covered by beats at the track's own rhythm?
- **regularity²**, the **rate prior**, the **maternal penalty** (gate test 10·vᵀCv ≥ trace(C), from the COV frame and RSP_V), and **(0.5 + agreement)**.
- Multiplying many factors is turned into adding their **log2** values. The log2 uses a 64-entry table, in Q8 integers. Additions are cheap in hardware.

**Viterbi step.** Viterbi is a classic dynamic-programming method that finds the best *path* through states over time.
- Here a state is "which track is right now".
- For each track y it keeps a running score = (best previous score over all tracks x, minus a switch cost if x ≠ y) + quality of y.
- The **switch cost** is 1 (in natural-log units). It is free if the two tracks agree on more than 80% of this segment's beats, because then switching changes nothing.
- This stops the output from jumping between tracks because of one noisy window.
- With **lag 0** the unit decides segment i at once from the current best score. Most of the look-ahead comes from the window, which already contains 7.5 s of future.

**Beat clean-up (one pass).**
- If a gap is 1.6–2.5× the local RR, one beat is missing. Fill it with the nearest candidate beat from any track (within RR/5 of the midpoint). If there is none, use the midpoint; such beats are marked as track 16.
- If a beat splits an interval (gap < 0.55 RR) and the next beat fits better without it, drop it.

**Centred FHR.** The FHR of each beat is the median of 5 intervals *around* it (2 before, 2 after), not just the last 5. This is why it is smoother.

**Delay and deadline.**
- The clean-up and FHR stages wait for a few later beats (4 and 3).
- A beat that is already 15 s old (deadline 3,750 samples) is released at the next 2.5-s step anyway. So no beat waits more than **17.5 s**.
- Median delay: **13.5 s**.

**Output.**
- **OUT7** frame (0x8D): beat time, FHR × 10, and the track.
- At the end of the recording the PC sends **FLUSH** (0x03). The board finishes the last segments with the data it has (less future context) and sends **END7** (0x8E) with the number of OUT7 frames.
- `v7_disp.v` shows the final FHR (display 0) and the number of final beats (display 1) on the board's two 4-digit seven-segment displays. So the answer is visible on the board itself.

---

## 6. The hardware, step by step

### 6.1 What an FPGA is

- An **FPGA** (field-programmable gate array) is a chip full of small logic blocks and wires that you can *configure* to become any digital circuit. You describe the circuit; the tools turn it into a configuration file (**bitstream**) that you load into the chip.
- The main resources:
  - **LUT (look-up table):** a tiny programmable truth table, the basic logic element. It can also be used as a small memory ("LUT RAM").
  - **Flip-flop (FF):** stores one bit, updated on each clock edge. Registers are made of flip-flops.
  - **BRAM (block RAM):** larger on-chip memories, 36 kb per tile.
  - **DSP slice (DSP48E1):** a hard-wired multiplier-accumulator, for fast multiplications.
- Our chip, the **XC7S50**, has 32,600 LUTs, 65,200 FFs, 75 BRAM tiles and 120 DSP slices.
- **Clock:** the circuit does one step per clock edge. The board has a 100 MHz oscillator. A **PLL** (phase-locked loop) makes our 50 MHz clock, so one cycle is 20 ns.
  - At 250 samples/s we have 4 ms per sample = 200,000 cycles per sample.
  - The RTL needs a median of 1,485 cycles (about 30 µs). That is about 140× faster than real time.
- **Timing slack:** after placing and routing, the tools measure the slowest signal path between two flip-flops.
  - Slack = (time available in one clock period) − (time the path needs).
  - Positive slack means timing is met. Negative means the circuit may compute wrong values at that clock.
  - **WNS** (worst negative slack) is the worst path's slack.
  - Ours: v6 +0.26 ns, v6.1 +0.41 ns, v7-DL **+0.05 ns** (met, but with almost no margin).

### 6.2 Why hand-written RTL

- **RTL (register-transfer level)** describes hardware as registers and the logic between them. We write it in **Verilog**.
- **v2:** our own RTL, but only a simple chain (filters, beamformer, detector); the PC computed the weights.
- **v5:** the full algorithm on a MicroBlaze soft processor. It worked and was bit-exact, but it was a processor we did not design, and the memory was full.
- **v6:** for the final design we moved every sample-rate operation into our own RTL. This is the actual hardware design of the project.
- The 5 decisions that remain on the PC are slow (once per recording up to a few times per second) and use floating-point eigen-solvers. In RTL these would be large. The report lists moving them to the FPGA (a small processor or more RTL) as future work.
- **Style:** a sequential datapath that processes one sample at a time in the same order as the C model. Several engines (filter, integrator, detector) are **time-multiplexed**: one piece of hardware serves many channels one after the other. This saves area.
- v6 is about 1,800 lines of Verilog in 11 files. v7 adds `v7_la.v` (654 lines) and `v7_disp.v`.

### 6.3 Modules

```
                         PC (laptop)
            run_v6_board_eval.py / webdemo/server.py  +  brain (v6_brain.exe)
                              |  UART 921,600 baud, USB
 ============================ | ========================== FPGA (XC7S50, 50 MHz)
   v6_top  (clock PLL, pins)  |
    └─ v6_core  (sequencer, Xf/Z sample rings, shared memory umem, port muxes)
        ├─ v6_link  (v6_uart; frame parser, 512-sample input FIFO, PC-answer buffers, TX FIFO)
        ├─ v6_fe    front-end filters ............. uses v6_sos (biquad engine)
        ├─ v6_mat   maternal covariance, PCA hand-shake, 2,500-sample replay, 4 detectors
        │                                          uses v6_mwi (integrators), v6_det (detectors)
        ├─ v6_canc  lag search, projection on the PC basis, tapered subtraction, 20-beat history
        ├─ v6_trk   16 tracks: projections + cross-fade, band-pass, envelopes, blanking,
        │           12 trackers, 4 detectors, features, selection output, FHR divider
        ├─ v7_la    look-ahead unit (v7-DL only): taps the uplink, scores, Viterbi, clean-up, OUT7/END7
        └─ v7_disp  final FHR and beat count on the two 4-digit displays (v7-DL only)
```

**Who uses what in v6** (post-implementation, from the report):

| Module | LUTs | FFs | BRAM | DSP |
|---|---|---|---|---|
| `v6_trk` (16 tracks) | 10,046 | 3,400 | 14 | 10 |
| `v6_mat` (maternal) | 4,921 | 2,582 | 3 | 4 |
| `v6_canc` (cancellation) | 1,144 | 948 | 10.5 | 15 |
| `v6_link` (frames, FIFOs) | 883 | 1,825 | 3.5 | 0 |
| `v6_fe` (filters) | 799 | 959 | 1 | 4 |
| `v6_core` (own: sequencer, rings, shared memory) | 291 | 231 | 28 | 0 |
| **Total** | **18,127** | **10,015** | **60** | **33** |

**Sequencer.** For each sample, `v6_core` starts fe, mat, canc and trk one after another with a go/done hand-shake. Example from simulation: one sample at T = 6,100 took 2,348 cycles (47 µs).

### 6.4 The PC–FPGA protocol

- **UART:** a simple serial link. One byte = 1 start bit + 8 data bits + 1 stop bit = 10 bits (8-N-1).
  - **Baud** = bits per second. At 921,600 baud that is about 92 KB/s in each direction.
- **Traffic per second of recording:**
  - down: about 9.4 KB/s (samples 2 KB/s, template bases 7.3 KB/s);
  - up: about 7.2 KB/s.
  - So the link allows up to about 10× real time.
- **Frame format:**

```
 A5 5A | cmd | len_lo len_hi | payload (len bytes) | xor8
 start   type   length (16 bit, little-endian)       checksum = XOR of cmd, len bytes, payload
```

- **Checksums.** The FPGA keeps a sticky error flag on a bad checksum or a FIFO overflow. The host stops with an error on a bad checksum.

**Messages:**

| Direction | Code | Name | Meaning |
|---|---|---|---|
| PC → FPGA | 0x01 | RESET | start a new recording |
| | 0x02 | SAMPLES | up to 256 samples × 4 leads, int16 (we send 64 at a time) |
| | 0x03 | FLUSH | (v7) end of recording: finish and send END7 |
| | 0x10 | RSP_V | maternal PCA: 4 projection vectors (Q14) |
| | 0x11 | RSP_MK | chosen maternal train |
| | 0x12 | RSP_BASIS | template basis per lead (s24, Q22) |
| | 0x13 | RSP_CAL | 16 spatial filters (Q14) + track flags |
| | 0x14 | RSP_SEL | selected track |
| FPGA → PC | 0x80 | COV | maternal-band 4×4 covariance (10 numbers, 64-bit) |
| | 0x81, 0x82 | MDET, REQ_MK | maternal detector peaks; "choose the maternal train" |
| | 0x83 | MPK | a maternal R peak |
| | 0x84 | SEG | aligned 150 × 4 maternal beat segment |
| | 0x85, 0x86 | CALDATA, REQ_CAL | 12 s of z and xf; "calibrate" |
| | 0x87, 0x88, 0x89 | BEAT, FEAT, BMED | track beats, beat snapshots, envelope medians |
| | 0x8A | REQ_SEL | "choose a track" |
| | 0x8B | OUT | live beat: time, FHR × 10, track |
| | 0x8C | DONE | all samples received so far are processed |
| | 0x8D, 0x8E | OUT7, END7 | (v7) final beat; count of final beats |

**The five PC decisions:**

| Decision | How often | FPGA sends | PC returns |
|---|---|---|---|
| Maternal PCA | once, at 10 s | 4×4 covariance | 4 projection vectors |
| Maternal train | every 5 s | detector peak events | train index |
| Template basis | every maternal beat | aligned 150×4 segment | orthonormal basis |
| GEVD calibration | at 15 s (v6.1: + every 30 s) | 12 s of z and xf | 16 weight vectors |
| Track selection | every 2.5 s | beats, snapshots, envelope medians | track index |

**Two flow-control rules make results independent of timing:**
1. The PC sends a 64-sample SAMPLES frame (0.256 s of signal) and waits for **DONE** before sending the next.
2. When the FPGA asks the PC something, it **stalls** (stops processing) until the answer arrives. So a slow PC or a USB hiccup changes the speed, never the result.

### 6.5 Fixed-point formats

- **Fixed point:** store a real number as an integer with an agreed number of fraction bits. In **Qn** format, value = integer / 2ⁿ.
  - Example: in Q14, 16384 means 1.0 and 8192 means 0.5.
  - Floating point (like `float` in C) is expensive in FPGA logic. Integers are cheap and exactly repeatable.
- **Rounding:** add half of the last kept bit, then shift right.
- **Saturation:** clip to the largest or smallest value instead of wrapping around.
- **Overflow:** a value too large for its bits. It wraps around and gives garbage. The C model checks every value against its declared width (`fm_overflow`). No value overflowed on any record.

**Formats in v6:**

| Data | Format |
|---|---|
| Raw input | int16 |
| Filter data | Q8 in int32 |
| SOS filter coefficients | Q28 |
| Products, accumulators | 64-bit |
| z and xf rings | int16 |
| Envelopes | 16-bit "monotonic code" with 8 significant bits (a tiny floating point: bigger value → bigger code, so comparisons still work; the largest code is 7,423, so 13 bits are enough) |
| Spatial weights, maternal projections | Q14 |
| Template basis | s24, Q22 |
| Tracker autocorrelation | 15-bit block floating point (the whole block shares one scale) |
| v7 quality | log2 in Q8 |

**Comparisons become exact integer tests.** Example: "e > 0.25 × median" becomes 4e > m. No rounding doubt is left.

### 6.6 The C model is the specification

- `fpga_model.c` is an integer model of *exactly* what the RTL computes, in the same order. `brain.c` is the PC brain. `sim_main.c` connects them through the real protocol. `v7_post.c` models `v7_la`.
- Build switches select the version: no define = v6 (frozen), `-DV61` = v6.1, `-DV7` = v7-DL (implies V61). The Verilog uses the same defines.
- **Rule for every change:** C model first → RTL → simulation → build → board.

### 6.7 Verification flow and "bit-exact"

```
 idea, tested on dev sets (Python / float)
        |
        v
 C model (integer)  --V6_DUMP-->  golden byte stream for a record
        |                                   |
        v                                   v
 Verilog RTL  ---- xsim system testbench: sends the record in 64-sample chunks,
        |          replays the PC brain's answers, compares EVERY uplink byte
        v
 Vivado build: synthesis -> place & route -> timing -> bitstream
        |
        v
 Board: stream 140 records, run the brain, compare the whole uplink stream with the C model
```

- **Testbench:** Verilog code that is not hardware. It drives the design's inputs and checks its outputs in simulation. Ours (`sim/tb_core.v`) plays the role of the PC host.
- **xsim:** the Vivado simulator.
- **Unit tests in xsim:** SOS engine 9,000 outputs; detector/integrator engines 2 × 20,000 samples; 0 errors.
- **System regression (`sim/regress.sh`):** 8 records for v6 and v6.1, 9 records for v7, all 0 byte errors.
- **Bit-exact** means every byte the board sends equals the byte the C model produces for the same input.
  - v6.1 run: 207,020,008 uplink bytes.
  - v7 run: 207,603,379 uplink bytes, including OUT7, FLUSH and END7.
  - All 140/140 records matched in both runs.
- **Why it matters:**
  1. The accuracy measured with the C model **is** the accuracy of the hardware. That is how we can quote all 1,248 FECGSYNDB records: we ran the C model, not the board.
  2. Debugging becomes easy: the first differing byte points to the bug. The tests found real bugs this way, for example a wrong SEG frame length (604 instead of 1,204 bytes).
  3. Any later change can be checked against a fixed reference (MD5 of the output stream).

### 6.8 Resources, timing and power

| | v6 | v6.1 | **v7-DL** | Available |
|---|---|---|---|---|
| LUTs | 18,127 (56%) | 18,986 (58%) | **26,701 (82%)** | 32,600 |
| Flip-flops | 10,015 | 11,179 | **15,970** | 65,200 |
| BRAM tiles | 60 | 60 | **71** | 75 |
| DSP | 33 | 33 | **43** | 120 |
| Clock / worst slack | 50 MHz / +0.26 ns | +0.41 ns | **+0.05 ns** | – |
| Power (Vivado estimate) | 0.374 W | 0.386 W | **0.445 W** | – |

- **Power is an estimate.** Vivado's default activity was used and the board was not measured. It is on-chip power only, well inside the 1.5 W wearable budget from the mid-term.
- **Speed on the board:** 4–5× real time for v6, and 4.0–4.5× for v6.1 and v7-DL. The UART and the PC answers limit it, not the FPGA logic.
- **The BRAM story (v6):**
  - 74.5/75 tiles (99%) → 60 (80%) by sharing one memory between two buffers that are never alive at the same time.
  - Proof that stale data is never read:
    1. the C model with the envelope rings filled with garbage gave identical outputs on 80 records;
    2. all 140 board streams had the same MD5 before and after the change.
  - Two other ideas were checked and **dropped**:
    - shrinking the 4096-deep sample rings: they are needed for the burst of cancellations at about 10.4 s;
    - halving the envelope rings: a tracker restart looks back about 1,057 samples.
- **The v7_la area story:**
  - The first version did not fit (13.2k LUTs alone, 101% in total).
  - The sequential rewrite fits: 8.4k LUTs stand-alone (out-of-context synthesis), 7,297 LUTs in the routed design, 82% in total.
  - Look-ahead + display units together add 7.7k LUTs and 11 BRAM tiles to v6.1.

---

## 7. Testing

**Python test suite** (`tests/`, run with `venv/Scripts/python.exe -m pytest tests -q`). Latest full run in the log: **270 passed, 3 skipped**.

| Folder | What it protects |
|---|---|
| `tests/unit/` | metrics and beat matching (±50 ms), FHR computation and median-5, data loaders, mixture builder, preprocessing, QRS detector, method interface; `test_v7_offline_and_scoring.py`: v7-LA clean-up fills a missed beat and drops a split beat, the centred FHR, the Viterbi follows the consistent track, frame parsing |
| `tests/integration/` | causal pipeline, UART protocol and client, benchmark runner, QRS timing correction |
| `tests/hardware/` | bit-accurate reference, exact filter coefficients, fixed-point arithmetic, integer model, v2 causal system; `test_v6_rtl_regression.py` runs the v6, v6.1 and v7 RTL in xsim against the C model (opt-in, `RUN_RTL=1`, needs Vivado; about 1 min per design) |
| `tests/regression/` | mid-term pre-FPGA results do not drift |
| `tests/system/test_v6_system_model.py` | the final design (see below) |

**System tests of the final design** (they need the compiled model programs and cached recordings, otherwise they are skipped):
- **Board match:** the v6, v6.1 and v7 C models give the same output MD5 as the board did.
- **Causality:** cutting a recording short never changes output that was already produced. This proves there is no hidden look-ahead (for v7, in the part before FLUSH).
- **Determinism:** two runs give the same bytes.
- **v6.1 fix:** a large start-up spike no longer blinds the maternal detectors.
- **Robustness:** inverted polarity, halved gain, a dead lead.
- **v7:**
  - it leaves the v6.1 stream untouched;
  - END7 equals the OUT7 count;
  - the delay is ≤ 17.5 s.
- **Accuracy guards on ADFECGDB** for v6, v6.1, v7-DL (≥ 95.5) and v7-LA. A change that silently drops accuracy fails the suite.

**Board evaluation** (`fpga_implementation/uart_host/run_v6_board_eval.py`, `V6_VARIANT=v61` or `v7`):
- streams each record in 64-sample frames and runs the brain pipe;
- scores the beats;
- compares the board's complete uplink byte stream with the C model (bit-exact flag and MD5);
- reports the speed.
- `run_v6_model_eval.py` does the same scoring with the C model only (no board).

**Web demo** (`fpga_implementation/webdemo/server.py`, http://localhost:8050):
- It first checks that the board answers (a reset plus one empty frame must be acknowledged within 1 s). Otherwise it refuses to run: there is no software fallback.
- Checks done:
  - v6 on CinC a01 gave F1 95.05%, 101 beats, FHR MAE 3.51 bpm, identical to the batch board run;
  - v7 on a01: the 102 final beats on the page (F1 98.02) are identical to the model's OUT7 beats;
  - v7 on a03: the first final beat appeared 14.4 s after its beat time.

---

## 8. Results and how to read them

### 8.1 Main table: mean beat F1 (%), measured on the board (bit-exact with the C model)

| Data set | Records | v6 | v6.1 | **v7-DL** |
|---|---|---|---|---|
| **CinC test (held out, scored once per design)** | 37 | 65.48 | 71.94 | **76.91** |
| CinC test, reliable references only | 33 | 70.45 | 77.19 | **81.95** |
| CinC dev | 38 | 76.04 | 80.41 | **84.68** |
| ADFECGDB | 5 | 92.73 | 92.87 | **96.10** |
| FECGSYNDB subset | 60 | 91.83 | 91.64 | **93.39** |
| FECGSYNDB all (C model = board) | 1,248 | 91.44 | 91.89 | **93.69** |

- v7-LA (offline): CinC test 75.64 (reliable 80.94), CinC dev 84.55, ADFECGDB 95.80, FECGSYNDB all 94.34.
- CinC test, records with F1 ≥ 90%: v6 13, v6.1 15, v7-LA 18, v7-DL 18.
- v7-DL Se / PPV: CinC test 76.22 / 77.83; ADFECGDB 96.37 / 95.84.
- Against the live v6.1 output of the same board runs:
  - CinC test: **33 records better, 1 worse** by more than 1 point;
  - all 75 CinC records: 63 better, 2 worse.
- The report's summary: v7-DL (on the FPGA, fixed delay) is at least as good as the offline v7-LA on all real data sets and within 0.7 points on FECGSYNDB.

### 8.2 FHR error (MAE, bpm)

| Data set | v6 | v6.1 | v7-DL |
|---|---|---|---|
| CinC test | 18.37 | 11.16 | 11.53 |
| CinC dev | 12.52 | 8.91 | 6.45 |
| ADFECGDB | 2.03 | 1.72 | 2.13 |
| FECGSYNDB subset | 5.24 | 5.36 | 4.23 |
| FECGSYNDB all | 5.20 | 4.85 | 3.98 |

- v7-DL improves F1 everywhere, but its FHR MAE is slightly *worse* on CinC test (11.53 vs 11.16) and ADFECGDB (2.13 vs 1.72). The logs do not analyse why. Do not invent a reason in the viva; say it was not analysed.
- FECGSYNDB subset for the frozen v7-DL is **4.23 bpm** (board and frozen C model). The 4.21 in `LOG.md` belongs to the variant without the deadline. Always quote 4.23.

### 8.3 FECGSYNDB by condition (all 1,248 records)

| Model | c0 baseline | c1 movement | c2 rate changes | c3 contractions | c4 ectopic |
|---|---|---|---|---|---|
| v6 | 96.8 | 96.9 | 91.7 | 93.3 | 78.5 |
| v6.1 | 97.2 | 96.9 | 91.5 | 96.0 | 77.9 |
| v7-DL | 98.0 | 97.8 | 91.9 | 96.8 | 84.0 |
| v7-LA | 98.7 | 98.9 | 91.7 | 96.7 | 85.8 |

**The synthetic weak spot.**
- In v7-DL, c4 stays at about 82–86% at every noise level and c2 at about 91–93% (per-record file `tools/accuracy/results_v7dl_synall.csv`). So these losses are not caused by noise.
- The reason: the quality score (RR regularity, rate prior) and the beat clean-up assume a regular rhythm.
  - An ectopic beat breaks the rhythm, so the true track is penalised or the beat is "cleaned" away.
  - Accelerations and decelerations bend the rhythm in a similar way.

### 8.4 How confident are the numbers?

- The test sets are small, so the report gives 95% bootstrap intervals: records resampled with replacement 10,000 times (seed 2026), the same method for all three versions.
- Sources: the v6 table in the report; `report/final_report/tables/board_v7_f1_ci.csv` for v6.1 and v7-DL (also the report's v6.1/v7-DL results table).

  | Set | v6 mean F1 [95% CI] | v6.1 [95% CI] | **v7-DL [95% CI]** |
  |---|---|---|---|
  | FECGSYNDB subset (60) | 91.8 [88.1, 95.2] | 91.6 [87.3, 95.4] | **93.4 [89.3, 96.7]** |
  | ADFECGDB (5) | 92.7 [88.5, 96.1] | 92.9 [88.6, 96.3] | **96.1 [92.8, 98.9]** |
  | CinC dev (38) | 76.0 [68.5, 82.7] | 80.4 [73.9, 85.8] | **84.7 [78.6, 89.8]** |
  | CinC test (37) | 65.5 [55.9, 75.0] | 71.9 [63.2, 80.2] | **76.9 [68.3, 84.7]** |
  | CinC test, reliable refs (33) | 70.4 [61.2, 79.4] | 77.2 [69.5, 84.2] | **82.0 [74.7, 88.5]** |

- Medians (same files): CinC test v6 73.6, v6.1 82.4, v7-DL 87.3.
- On CinC test the interval is still about ±8 points wide for v7-DL. The v6.1 and v7-DL intervals overlap.
- **Single number vs comparison.** Overlapping intervals do not mean "no difference". Each interval describes one mean on its own. A comparison on the *same* records is much stronger: v7-DL beat v6.1 on 33 of 37 test records and lost on 1. That is good evidence that the gain is real.
- **Mean vs median.** CinC per-record F1 spreads from 0 to 99%. A few failed records pull the mean far down, so the median is higher than the mean.

### 8.5 Why CinC is still low

A diagnostic with labels on v7-DL, over all 75 CinC records (report: Final Phase IV, "Where the Remaining Error Is"):
- **The chooser is no longer the problem.** Mean final F1 80.8, best single candidate track 82.1, a gap of about 1 point. Before the look-ahead the gap was about 5 points (CinC dev after v6.1 idea 1: selected 79.5, best track 84.7).
- **The maternal train is found in all 75 records** (v6.1 and v7-DL).
- **All 15 records with F1 < 70, by cause:**

  | Cause | Records | Count |
  |---|---|---|
  | Reference marked unreliable by the challenge | a38, a52, a54, a71, a74 | 5 |
  | No candidate track above 70% (best track 42–69%): no spatial filter recovers the fetal beats | a29, a30, a34, a18, a16, a73, a02, a46 | 8 |
  | Best track only 71–73% | a06, a27 | 2 |
  | A good track (≥ 85%) existed but was not chosen | – | 0 |
- **Short records:** CinC records are 60 s, and the first 20 s are start-up. Only about 40 s are scored. Recalibration happens at most once.
- **So the next gains must come from better candidates** (the front end), not from smarter choosing.

### 8.6 Why the dev/test gap?

- CinC dev is about 8 points higher than CinC test for v7-DL (84.68 vs 76.91).
- Part is natural variation between the two halves. The dev half was already easier for older designs that were never tuned on it: v2 42.0 vs 41.2; the mid-term design 22.8 vs 16.7.
- Part is the effect of choosing the design on dev.
- Four of the seven unreliable-reference records are in the test half (three in dev).

### 8.7 Speed and latency

- **RTL alone:** a median of 1,485 cycles per sample, about 140× real time (simulation).
- **Whole system on the board:** 4–5× real time (UART + PC).
- **Live beats** (v6/v6.1 output): about 1.5–2 s after they happen.
- **Final beats** (v7-DL): median 13.5 s, at most 17.5 s.

---

## 9. Limitations and honest caveats

1. **CinC test is not fresh any more.**
   - It was scored once per frozen design, but for many designs. The report lists v5, v6, v6.1, v7-LA and v7-DL. The night log shows that the first touch (with v5) also scored the older designs (mid-term, v2, v3, v4) at the same time.
   - No decision used it directly. But knowing earlier test results can indirectly steer what we work on.
   - A brand-new held-out set would be needed for a clean number. Say this openly if asked.
2. **Small real test sets.** 37 CinC test records of 60 s, and ADFECGDB has only 5 records. ADFECGDB was used during development from v4 on, so it is not an independent test.
3. **Not clinical grade.** 76.91% on held-out CinC (82.0% on reliable references) is far better than 16.7%, but it is not good enough for clinical use. Most remaining failures have no good candidate track (section 8.5).
4. **The delay of v7-DL.**
   - Final beats come out about 13.5 s late (max 17.5 s). That is fine for watching FHR trends. It is not fine for anything beat-synchronous.
   - The live v6.1 estimate is still available with 1.5–2 s delay.
   - At the end of a recording, FLUSH finishes the last segments with less future context.
5. **The PC is still in the loop.** Five low-rate decisions (eigen-solvers, template basis, selection) run on a laptop. A stand-alone device would need a small processor or more RTL.
6. **No analogue front end.**
   - Recordings are streamed from files. We did not build electrodes, an amplifier or an ADC.
   - Power is a Vivado estimate for the chip only. The board was not measured.
7. **Display and demo.**
   - The mid-term switch presets, 50/60 Hz notch toggle and bypass switch belonged to the mid-term design. The final design's pin files (`v6.xdc`, `v7.xdc`) have no switch inputs.
   - v6 showed the FHR only on the web page.
   - With v7-DL the final FHR and the number of final beats are also shown on the board's two 4-digit seven-segment displays (`v7_disp`), as planned at mid-term. The report's demo section ("Final Demonstration: Live Web Page and On-Board Display") describes both.
8. **Hard clinical cases.**
   - Ectopic beats (c4 about 84%) and rate changes (c2 about 92%).
   - Possible under-selection of a slow fetal heart because of the FHR prior (below about 110 bpm).
   - Twins are not supported.
9. **Little timing margin.**
   - v7-DL uses 82% of the LUTs and 71/75 BRAM, with +0.05 ns slack at 50 MHz.
   - The report says more logic would need pipelining or a lower clock.
10. **Calibration.** The maternal PCA is computed once (first 10 s). The spatial filters are recalibrated every 30 s from v6.1 on, but a 60-s CinC record gets at most one recalibration.
11. **Mid-term objectives not met.**
    - "<5% LUT, 1 DSP" was set for the tiny beamformer and does not apply to the real-data design.
    - "F1 ≥ 90%" is met on synthetic data and ADFECGDB, not on CinC.
12. **Mid-term U-Net caveat.** Its training records were not fully documented, so its synthetic score may include training records.

---

## 10. What each member must learn before the viva

The report's contribution table ("Contribution of Each Member (Whole Project)") now includes the v6.1 and v7 work. Make sure you can explain every line of your own row. **Everyone should read the report's "Final Phase IV" section**, as well as the "Observations and Discussion", "Limitations of the final design", "Final conclusions" and "Future Work" parts.

### 10.1 Everyone must know

**The one-minute pitch:**
1. The fetal ECG is 10–250× smaller than the mother's and shares her frequencies, so filters cannot separate them.
2. Our mid-term beamformer scored 93% on synthetic data but only 16.7% on real held-out recordings once we tested causally.
3. So we redesigned the algorithm:
   - remove the mother beat by beat on each lead;
   - build 16 candidate fetal tracks from self-calibrated GEVD filters;
   - follow them with beat trackers;
   - choose without labels.
4. We implemented it as hand-written Verilog on a Spartan-7, with a PC answering only 5 slow questions. The board is bit-exact with our C model on 140/140 records.
5. The final v7-DL adds a look-ahead unit on the FPGA that waits about 13.5 s and uses future context to pick and clean the beats.
6. Held-out CinC F1 is 76.91% (95% CI [68.3, 84.7]; from 65.48% in v6), ADFECGDB 96.10%, all 1,248 synthetic records 93.69%.
7. With look-ahead the chosen track is close to the best single track (80.8% vs 82.1% on all CinC). The remaining failures are recordings where no candidate track contains the fetal beats, or unreliable references.

**Key numbers to memorise:**
- **Signal:** 20–100 µV vs 1–5 mV; 0.5–40 Hz overlap; 250 Hz; 4 leads.
- **Scoring:** ±50 ms; from 20 s; dev = odd CinC (38), test = even CinC (37).
- **Accuracy:** 16.7 → 41.2 → 65.5 → 71.9 → 76.9 on CinC test (mid-term causal → v2 → v6 → v6.1 → v7-DL).
- **Hardware:** 50 MHz; 26,701 LUTs (82%); 71/75 BRAM; 43 DSP; +0.05 ns; 0.445 W estimate; 4–4.5× real time on the board; 1,485 cycles per sample in RTL.
- **Delay:** live 1.5–2 s; final median 13.5 s, max 17.5 s.

**Rules we never broke:**
- causal processing (v7-DL: causal with a fixed delay);
- no labels inside the algorithm;
- decisions on dev only;
- C model first, then RTL, then board.

**Likely general questions, with short answers:**

| Question | Answer |
|---|---|
| Why not just filter out the mother? | Same frequency band (0.5–40 Hz). Filtering would remove the baby too. |
| Why did mid-term results not hold? | They were batch (non-causal) and synthetic. Causal: 82.2% synthetic, 16.7% real. Even perfect single-filter weights reach only 60% on CinC. |
| Did you train on labels? | No. Labels are used only by the scoring script. GEVD uses the design's own detections. |
| Did you tune on the test set? | No decision used CinC test; it was scored once per frozen design. But it has been scored for many designs, so it is not fresh. |
| What does the PC do? | 5 slow decisions: maternal PCA, maternal train choice, template basis, GEVD calibration (and recalibration), track selection. It never receives the recording. |
| Does the result depend on the PC's speed? | No. The FPGA stalls on each request, and the host waits for DONE after each 64-sample frame. |
| What is bit-exact and how do you check it? | Every output byte equals the C model's. We compare the whole uplink stream (and MD5) for all 140 records on the board and every byte in xsim. |
| Is it real time? | Yes. 4–4.5× faster than real time on the board, about 140× for the RTL alone. v7-DL adds a fixed delay, not a slowdown. |
| Why is v7 not "cheating"? | It uses the future only by waiting for it (about 13.5 s). Output before FLUSH is causal; a test checks that cutting a record short never changes earlier output. |
| Why drop the U-Net? | 17.7% on real ADFECGDB, and about 8× too big for on-chip memory. |
| Where does it still fail? | Of the 15 CinC records below 70%: 5 unreliable references, 8 with no candidate track above 70%, 2 with a best track of only 71–73%; none had a good track that was not chosen. On synthetic data: ectopic beats (c4). |

### 10.2 Naman — data, test set-up, integration, test suite, web demo, report assembly

Your own part is the least algorithm-heavy. So expect general questions from all areas. Know the "everyone" list above very well, and your own part in depth.

**Topics to revise:**
- **The three data sets** (section 3):
  - FECGSYNDB structure: subjects, SNR, conditions, repetitions, lead choice [27, 26, 28, 25];
  - CinC 1 kHz → 250 Hz causal decimation; the 7 unreliable records;
  - ADFECGDB scalp reference; unit conversion and annotations.
  - Where the CinC files are: under `data/noninvasive-fetal-ecg-the-physionet-computing-in-cardiology-challenge-2013-1.0.0/extracted/`. Records up to a25 are in `set-a/`; records after a25 (for example a73) are in `set-a-ext/`.
- **Scoring** (`harness.py`):
  - greedy one-to-one matching in time order, TOL = 13 samples;
  - TP/FP/FN, Se, PPV, F1;
  - scoring from 20 s;
  - FHR MAE at true beat + 0.5 s; "no output = full error".
- **Dev/test protocol:** odd/even split, test once per design, why that matters.
- **Mid-term:** your SVD methods (Hankel SVD, M8/M9; rank-2 reconstruction removes the dominant maternal part); the shared mixture builder and test cases TC1–TC5.
- **The test suite** (section 7): what each folder protects, the causality "prefix" test, accuracy guards, opt-in RTL regression. Latest run: 270 passed, 3 skipped.
- **Web demo:**
  - board check (no software fallback);
  - upload (WFDB or CSV) and real-time streaming (one 64-sample frame every 0.256 s);
  - the v7 page: final FHR from the FPGA with the live v6.1 estimate under it, the delay card, the "not final yet" area, FLUSH;
  - the a01 checks.

**Files:**
- `tools/accuracy/harness.py`, `tools/accuracy/eval_cinc2013.py`;
- `tests/system/test_v6_system_model.py`, `tests/unit/test_v7_offline_and_scoring.py`;
- `fpga_implementation/webdemo/server.py` and `index.html`;
- `report/final_report/tools/check_final_numbers.py`;
- `report/final_report/fpr-8.tex`: "Final Phase IV", the demo section "Final Demonstration: Live Web Page and On-Board Display", and your row in the contribution table (it now mentions the v6.1/v7 tests and the v7 web view);
- `README.md`.

**Likely questions:**
- *Why ±50 ms?* It is the PhysioNet/CinC 2013 standard.
- *Why start scoring at 20 s?* The design calibrates until about 15 s, and the first selected beat comes at about 19.5 s.
- *How do you know the web page shows hardware results?* It refuses to run if the board does not answer, and the a01 results equal the batch board run.
- *What would a test catch if someone broke causality?* The prefix test: output already produced must not change when the record is cut.
- *Why are 2 of 1,250 FECGSYNDB records missing?* 1,248 are "usable": the loader skips records with missing parts or non-finite values. Check the exact reason before the viva if you want to quote it.

### 10.3 Vivek — fixed point, UART, protocol, v5 MicroBlaze, board evaluation

**Topics to revise:**
- **Fixed point** (section 6.5):
  - Qn meaning, rounding, saturation vs overflow;
  - why integers make bit-exactness possible;
  - mid-term Q1.15 and SQNR +74.52 dB;
  - the v6 formats table;
  - envelope code and block floating point.
- **UART:**
  - 8-N-1, 10 bits per byte, 921,600 baud ≈ 92 KB/s;
  - traffic 9.4 KB/s down and 7.2 KB/s up, so about 10× real time is possible;
  - the bring-up steps: loop-back echo, then framed packets.
- **Protocol** (section 6.4):
  - frame format and xor8 checksum;
  - all message codes, including FLUSH/OUT7/END7;
  - DONE after each 64-sample frame;
  - the FPGA stalls on requests.
- **v5:**
  - why MicroBlaze that night;
  - 73.7 MHz with an FPU; memory fitting (int16 rings, bf16 envelopes, int8 snapshots, shared buffers);
  - incremental Gram + subspace iteration instead of Jacobi; 3.5× faster, 47k cycles per sample;
  - 140/140 bit-exact; why we moved on to RTL.
- **Board evaluation:**
  - how `run_v6_board_eval.py` streams, runs the brain pipe, scores, and checks bit-exactness (MD5 of the uplink);
  - the `V6_VARIANT` switch;
  - the v6.1 and v7 board runs you did: 207,020,008 and 207,603,379 uplink bytes, 140/140.

**Files:**
- `fpga_implementation/v6/model/proto.h`;
- `rtl/v6_link.v`, `rtl/v6_uart.v`;
- `uart_host/run_v6_board_eval.py`;
- `fpga_implementation/v5/README.md`, `v5/algo/README.md`;
- `report/night_20261109/LOG.md` and `RESULTS.md`;
- `report/v61_v7/LOG.md` (Parts 3 and 4);
- `report/final_report/fpr-8.tex`: "Final Phase III" and "Final Phase IV" (results subsection and CI table); your contribution row now lists the FLUSH/OUT7 extension of the evaluation script and the v6.1/v7-DL board runs.

**Likely questions:**
- *Why 921,600 baud?* The logs give no reason beyond "fast enough": the link needs about 9.4 KB/s against a capacity of about 92 KB/s. Have your own answer ready.
- *What if a byte is corrupted?* The xor8 checksum detects it. The FPGA sets a sticky error flag, and the host stops with an error. The run is not silently wrong.
- *Why is the board only 4–5× real time when the RTL is 140×?* Every sample and every PC request crosses the UART and waits for the PC.
- *Why Q14 for weights?* Weights are normalised numbers of magnitude about 1 or below; 14 fraction bits in 16 bits give fine resolution. (This is our reasoning; the logs only state the format.)
- *Why does the result not depend on timing?* Lock-step: wait for DONE; the FPGA stalls on every request.

### 10.4 Anshu — real-time algorithm and accuracy (v2–v5, CinC protocol, U-Net, v6.1 ideas, v7 algorithm)

**Topics to revise:**
- **The causal re-run** and why the mid-term numbers fell (93.0 → 82.2 → 16.7 on real data).
- **v2:**
  - self-referencing GEVD: the maths R_QRS·w = λ·R_x·w, 3 iterations from PCA seeds, dropping maternal-coincident beats;
  - the "best single filter = 60%" diagnostic.
- **The final algorithm** (section 5):
  - maternal train choice rule;
  - template basis: mean + 2 PCs of 20 beats, −160..+440 ms, ±4-sample alignment, tapered subtraction;
  - the 16-track table; the tracker steps;
  - the selection quality formula with each factor;
  - the 10% gate and why (FECGSYNDB 78.7 → 91.3);
  - the FHR prior and bradycardia.
- **CinC dev/test protocol** and the corrected scoring.
- **U-Net:** 90.0% synthetic vs 17.7% ADFECGDB; the training-record caveat.
- **v6.1:**
  - idea 1 (detector warm-up + decay; the "fired zero times" finding);
  - idea 2 (what was tried, why rejected);
  - idea 3 (30 s, keep-if-better).
- **v7-LA and v7-DL:**
  - centred window; log quality; Viterbi with switch cost and the 80% agreement rule;
  - clean-up rules (1.6–2.5× fill, split-beat drop); centred FHR;
  - the delay table and why the frozen choice;
  - the CinC "why low" diagnostic.

**Files:**
- `report/final_report/fpr-8.tex`: sections "Final Phase I", "II" and especially "IV" (v6.1 ideas table, v7-LA, v7-DL, "Where the Remaining Error Is");
- `report/night_20261109/LOG.md`;
- `report/v61_v7/LOG.md` (Parts 1, 2, 4);
- `tools/accuracy/v7_offline.py`;
- `fpga_implementation/v6/model/brain.c`, `model/v7_post.c`;
- `fpga_implementation/v5/algo/README.md`.

**Likely questions:**
- *Why GEVD and not PCA?* PCA maximises power, and the mother has the most power. GEVD maximises power *around the fetal beats* relative to total power.
- *How can GEVD work without labels?* It uses its own detections, drops beats at maternal peaks, and iterates.
- *Why 16 tracks instead of one best filter?* No single filter is reliably right on real data. Different tracks win on different records and times.
- *What does the Viterbi add over picking the best quality each step?* A switch cost, so one noisy window does not make the output jump. Switching is free when the tracks agree.
- *Why didn't the learned selector help?* It was trained on synthetic records and did not transfer: −0.5 on CinC dev.
- *Why is v7-DL slightly better than v7-LA on CinC test although LA sees more?* The report states the fact: v7-DL is at least as good as the offline version on all real data sets and within 0.7 points on FECGSYNDB (94.34 vs 93.69). It does not analyse why. Our reading: the differences are small, the two use different windows (−15/+7.5 s around the segment vs ±15 s) and integer vs float maths, and on 37 records such differences are within the CI width.
- *Where should future work go?* Better candidates, not better choosing. 8 of the 15 weak CinC records have no candidate track above 70%. The report suggests adding recalibrated filters as extra tracks and stronger maternal cancellation.
- *Why does c4 stay low?* Regularity, the prior and the clean-up assume a regular rhythm.

### 10.5 Astitva — final hardware (v6 RTL, C model, testbenches, BRAM, v6.1 RTL, v7_la)

**Topics to revise:**
- **The hardware/PC split by rate**, and why each of the five decisions stays on the PC.
- **The C model as the specification;** defines V61/V7; the overflow check.
- **Every RTL module** (section 6.3): the sequencer hand-shake, time-multiplexed engines (SOS, MWI, detectors), rings, `umem`, sorting networks in the trackers, the FHR divider.
- **Verification:**
  - unit xsim tests; the system testbench `tb_core.v` (emulates the host, replays brain answers, compares every byte);
  - `regress.sh`; the bugs it found;
  - the waveform run (30 s of a01: 164,447 bytes, 2,721 frames, all matched).
- **Implementation:**
  - PLL 100 → 50 MHz;
  - the two fixes needed for v6 (z ring merged to one write port to map to BRAM; a sorting-network loop rewritten);
  - resources per module; timing; power.
- **BRAM sharing:** why it is safe (lifetimes, 13-bit codes, garbage test, MD5); the two dropped ideas.
- **v6.1 RTL:**
  - `v6_det` decay input (peak drops by 1/8 at sub-threshold maxima after 500 samples without a detection);
  - `v6_mat` warm-up at 256;
  - `v6_trk` recalibration states 220–229 (keep weights, read 3,000 samples back from the rings, CALDATA 2,048 + 952, REQ_CAL, cross-fade with per-track previous weights).
- **v7_la RTL:**
  - taps; once per 625 samples;
  - integer log2 (64-entry table, Q8); shape sums per slot; lower medians by counting; the maternal gate;
  - OUT7/END7/FLUSH;
  - the area problem: 13.2k LUTs, did not fit (101%) → after doing shifts, divisions and log2 one bit per cycle and single-read-port buffers: 8.4k LUTs stand-alone (out-of-context synthesis), 7,297 LUTs in the routed design;
  - `v7_disp`. Look-ahead + display add 7.7k LUTs and 11 BRAM tiles to v6.1.

**Files:**
- `fpga_implementation/v6/README.md`, `PLANNED_CHANGES.md`;
- `rtl/*.v` (start with `v6_core.v`, then `v6_trk.v`, `v7_la.v`);
- `sim/tb_core.v`, `sim/regress.sh`, `sim/run_tb.sh`;
- `model/fpga_model.c`, `model/v7_post.c`;
- `report/rtl_pc_split/LOG.md`;
- `report/v61_v7/LOG.md` (Parts 3 and 4);
- `report/final_report/fpr-8.tex`: "Final Phase III" and "Final Phase IV" (v6.1 in the RTL, the v7-DL unit, the hardware table of v6 / v6.1 / v7-DL), and your contribution row (now with v6.1 recalibration RTL, `v7_la` and its area reduction, the display unit);
- `build/` reports.

**Likely questions:**
- *Why not keep the MicroBlaze?* It was a processor we did not design, its memory was full, and the course project is the hardware design.
- *Why 50 MHz, not 100 MHz?* The logs do not record the reason. What we do know: the design needs about 1,485 of the 200,000 cycles available per sample, so 50 MHz is far more than enough. Confirm your own reason before the viva.
- *Why is the slack only +0.05 ns in v7-DL?* The logs do not analyse it. A likely reason is that the chip is now 82% full, so routing gets longer. Timing is still met; the report says more logic would need pipelining or a lower clock. Look up the worst path in the v7 timing report (`build/v7/`) before the viva.
- *Why do the report and the logs give different LUT numbers for `v7_la`?* 8.4k is the unit synthesised alone (out of context); 7,297 is its share inside the routed full design. (Optimisation across module boundaries usually explains such a difference; our logs do not analyse it.) The increase of the whole design over v6.1 is 7.7k LUTs, which includes the display unit.
- *What happens in hardware during a PC request?* The unit sends the frame, and the sequencer waits until the answer is in the link buffers (shown in the PCA-request waveform).
- *How do you know `v7_la` does not disturb v6.1?* It only listens. A system test removes the OUT7/END7 frames from the v7 output and checks that what is left equals the v6.1 output byte for byte (CinC a29). The board stream also matched the model.
- *What made the first `v7_la` too big?* Parallel shifters, dividers and log2 units. Making them sequential traded cycles (which are free here) for area.

---

## 11. Glossary

| Term | Meaning |
|---|---|
| Accumulator | A register that adds up many products (for example, in a filter). |
| ADC | Analogue-to-digital converter: turns a voltage into numbers. |
| ADFECGDB | Real database: 5 recordings, 5 min, abdominal leads + fetal scalp electrode reference. |
| Annotation / label | The correct beat times, used only for scoring. |
| Autocorrelation | Similarity of a signal with a shifted copy of itself; peaks at the rhythm's period. |
| Band-pass filter | Keeps one frequency band (e.g. 5–25 Hz). |
| Baud | Bits per second on a serial link (921,600 for us). |
| Beamformer / spatial filter | Weighted sum of leads, w1·x1 + … + w4·x4, a "virtual electrode". |
| Biquad / SOS | Second-order section: small recursive filter block; long filters are chains of them. |
| Bit-exact | Every output byte of the board equals the C model's. |
| Bitstream | The configuration file loaded into the FPGA. |
| Blanking | Holding a track's envelope briefly after a maternal R peak. |
| Block floating point | A block of numbers sharing one scale factor (one exponent). |
| Bootstrap CI | Confidence interval from resampling records with replacement many times. |
| BRAM | Block RAM: on-chip memory tiles (36 kb each; 75 on the XC7S50). |
| Bradycardia | Slow heart rate (fetal: below about 110 bpm in our report). |
| C model | Our integer C program that computes exactly what the RTL computes; the specification. |
| Causal | Uses only past and present samples. |
| CinC 2013 | PhysioNet/Computing in Cardiology Challenge 2013, set-a: 75 real 60-s recordings. |
| Clock / clock period | The steady pulse that steps the circuit; 50 MHz = 20 ns per cycle. |
| Covariance matrix | 4×4 table of average products of leads; diagonal = power per lead. |
| Cross-fade | Moving gradually from old to new weights (64 samples) to avoid a jump. |
| CTG | Cardiotocography, the usual Doppler-ultrasound FHR monitor. |
| Decimation | Lowering the sampling rate (low-pass, then keep every k-th sample). |
| Deadline (v7) | A beat 15 s old is released anyway, so the delay is at most 17.5 s. |
| Dev set | Records used to develop and tune. |
| DSP slice | Hard multiplier-accumulator block on the FPGA (120 on the XC7S50). |
| ECG | Electrocardiogram: the heart's electrical activity measured on the skin. |
| Ectopic beat | An early extra beat outside the regular rhythm (FECGSYNDB c4). |
| Eigenvector / eigenvalue | Direction v with R·v = λ·v; λ is the power along v. |
| Envelope | Smoothed energy of a signal; beats become bumps. |
| F1 | 2·Se·PPV/(Se+PPV), our main accuracy number. |
| FECGSYNDB | PhysioNet Fetal ECG Synthetic Database (1,250 simulated 5-min records). |
| FHR | Fetal heart rate, in beats per minute. |
| FIFO | First-in-first-out buffer (e.g. the 512-sample input FIFO). |
| Fixed point / Qn | Integer with n fraction bits; value = integer / 2ⁿ. |
| Flip-flop (FF) | One-bit storage element updated on a clock edge. |
| FLUSH | v7 command (0x03) at the end of a recording: finish and send END7. |
| FMR | Fetal-to-maternal ratio (used at mid-term to pick leads). |
| FPGA | Field-programmable gate array: configurable digital chip. |
| Frame | One protocol message: A5 5A, command, length, payload, xor8 checksum. |
| GEVD | Generalised eigenvalue decomposition; here: maximise (fetal-beat power)/(total power). |
| Group delay | How much a filter delays a signal (per frequency). |
| Held-out / test set | Records used only to report the final number of a frozen design. |
| High-pass filter | Removes slow drift (baseline wander). |
| IIR filter | Recursive filter that uses past outputs as well as inputs. |
| Label-free | The algorithm never uses annotations. |
| Latency / delay | Time between a beat happening and being reported. |
| Lead | One electrode channel. |
| Look-ahead | Using samples after "now", by waiting for them (v7). |
| Low-pass filter | Removes fast noise. |
| LUT | Look-up table: the FPGA's basic logic element. |
| MAE | Mean absolute error (FHR error in bpm). |
| Maternal coincidence penalty | Lowers the quality of a track whose beats sit on maternal R peaks. |
| Median | Middle value of a sorted list; robust to outliers. |
| MicroBlaze | A soft processor built from FPGA logic (used in v5). |
| NIFECG | Non-invasive fetal ECG from abdominal electrodes. |
| Notch filter | Removes one frequency (e.g. 50/60 Hz mains). |
| Nyquist | Half the sampling rate; the highest frequency representable. |
| Oracle | A diagnostic that uses labels to pick the best track; shows the upper limit of choosing. |
| Overfitting to the test set | Tuning on test records, which makes the test score optimistic. |
| Overflow | A value too big for its bits; wraps around and gives garbage. |
| PCA | Principal component analysis: eigenvectors of the covariance, sorted by power. |
| PLL | Phase-locked loop: makes the 50 MHz clock from the 100 MHz oscillator. |
| PPV | Positive predictive value = TP/(TP+FP). |
| Prior (FHR prior) | Mild weight favouring physiological fetal rates (0.2 at 80 bpm → 1 at ≥ 120 bpm). |
| QRS complex | The sharp main spike of a heartbeat. |
| R peak | Top of the QRS; the time of a beat. |
| Refractory period | Time after a detection when no new detection is allowed. |
| RR interval | Time between consecutive R peaks. |
| RTL | Register-transfer level: hardware described as registers and logic between them. |
| Sampling rate | Samples per second (250 Hz = one every 4 ms). |
| Saturation | Clipping to the max/min value instead of overflowing. |
| Se (sensitivity) | TP/(TP+FN). |
| Self-referencing | Using the design's own detections instead of labels. |
| SNR | Signal-to-noise ratio in dB. |
| SQNR | Signal-to-quantisation-noise ratio (rounding error of fixed point). |
| Stall | The FPGA waits for the PC's answer before continuing. |
| Synthesis / implementation | Vivado steps: logic to gates, then placement and routing, then timing. |
| Template subtraction | Subtracting an averaged maternal beat at each maternal beat. |
| Testbench | Simulation-only Verilog that drives the design and checks its outputs. |
| Time-multiplexed | One hardware unit serving several channels in turn. |
| Timing slack / WNS | Spare time on the slowest path in one clock period; positive = met. |
| Track | One candidate fetal beat train (16 of them). |
| Tracker | Beat finder that predicts the next beat from the rhythm (RR). |
| UART | Simple serial link (8 data bits, 1 start, 1 stop). |
| Unreliable reference | 7 CinC records whose labels the dataset flags as unreliable. |
| Verilog | The hardware description language we wrote the RTL in. |
| Viterbi | Dynamic programming to find the best path of states over time, with switch costs. |
| Vivado | AMD's FPGA tool (synthesis, implementation, xsim simulator). |
| xsim | The Vivado simulator. |
| Zero-phase filtering | Forward + backward filtering: no delay, but non-causal. |
