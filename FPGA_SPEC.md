# FPGA Implementation Spec (v0.2)

**Project:** EE2000 Team 8, fetal ECG extraction + fetal QRS/FHR on Spartan-7 XC7S50
**Status:** Step 1 of the FPGA plan, updated to match the code in `code/src/causal_pipeline.py` and `code/src/fpga_int_model.py`. Items marked **OPEN** are not yet decided; everything else is frozen.
**Rule:** the *golden model* is the integer-only causal Python model (`fpga_int_model.py`), not the existing zero-phase benchmark. RTL must match it bit-for-bit.

**Changes from v0.1** (found while writing and testing the code):
- The 0.5 Hz high-pass section cannot be built with 18-bit coefficients (about 28 dB accuracy, poles hugging the unit circle), so it is replaced by a shift-only baseline remover plus a 40 Hz low-pass.
- Coefficients are Q3.15 (not Q2.16) so that a numerator coefficient of exactly 2.0 is representable.
- PCA weights are computed on the 8-30 Hz band, because slow baseline wander otherwise takes a principal component.
- OPEN-1 candidates corrected (v0.1 listed "PC2" and "remove PC1, take the largest remainder", which are the same thing).
- Warm-up is 512 samples (a power of two, so the mean is a shift).

---

## 0. Why this spec exists (findings from the repo audit)

| # | Finding | Where | Consequence |
|---|---------|-------|-------------|
| F1 | Every filter is zero-phase (`sosfiltfilt`), including the detector's 8-30 Hz band-pass. The moving-window integrator uses `mode="same"` (centered) and peak finding looks ahead. | `preprocessing.py`, `qrs_detector.py` | All reported F1 / MAE numbers are non-causal and cannot be reproduced on an FPGA. The causal chain must be re-benchmarked and reported separately. |
| F2 | The headline Spatial PCA result (93.00% F1, 100% on TC1-3) tries all 4 principal components and keeps the one with the best F1 **against the ground-truth beats**. | `run_mega_benchmark.py::run_spatial_pca`, `multichannel_study.py` | Hardware cannot see the ground truth. A label-free component rule is required (OPEN-1). The 93% figure is an upper bound. |
| F3 | PCA covariance is computed over the whole 5-minute record (75,000 samples). The README says N = 750 samples (3 s). | `run_spatial_pca` vs README | Calibration window is undecided (OPEN-2). |
| F4 | Three different 4-lead sets appear in the docs: [27, 26, 28, 25] (README, `DEFAULT_CHANNELS_4CH`), [16, 18, 25, 27] (decision doc), [27, 26, 25, 18] (top 4 of `RANKED_CHANNELS`). | docs vs code | Frozen to [27, 26, 28, 25]. |
| F5 | Number formats disagree: test vectors and `fixed_point_model.py` use Q3.12 / Q2.14; README and SVD model use Q1.15. | code vs docs | Frozen below. Existing test vectors are single-channel Q3.12 and are replaced by the dumps from `fpga_int_model.py`. |
| F6 | The README describes a 5-beat causal median filter on FHR; `fhr.py` (what is scored) has none. | README vs `fhr.py` | Scored FHR is the raw per-beat value. The median is an optional display output only. |
| F7 | Cycle counts per sample are quoted as 45, 128 and 148 in different documents. | docs | Superseded by Section 8. |
| F8 | The two band-pass filters delay QRS-band signal by about 12.25 samples (49 ms), nearly the whole ±50 ms matching window. | measured | A fixed latency compensation is mandatory; it is computed from the filters (12 samples), not hand-tuned. |

---

## 1. System overview

```
PC (host) --UART--> [ frame RX ] -> [ 4ch projection w.x ] -> [ HP1 ] -> [ LP40 ] --+--> fecg_out
                                                                                     |
                                                       [ BP 8-30 Hz ] <--------------+
                                                         -> square -> trailing sum (20)
                                                         -> adaptive threshold + refractory
                                                         -> R-peak localisation -> RR -> FHR LUT
PC <--UART-- [ frame TX ] <------------------------------ fecg_out, beat flag, fhr
```

**Project first, then filter once.** The filters are linear and time-invariant and the weights are constant, so `filter(w.x) = w.filter(x)`; one chain instead of four. The projection accumulator must be wide enough for raw channels, including DC offset and baseline wander (Section 3).

**Weights are computed on the host**, once, from a calibration window, and loaded over UART. The sample-by-sample path never computes a covariance.

---

## 2. Signal, timing, clock

| Item | Value |
|------|-------|
| Sampling rate | 250 Hz (4 ms/sample) |
| FPGA clock | 100 MHz (400,000 cycles per sample) |
| Target device | XC7S50-CSGA324 (Boolean Board). Must also fit XC7S25. |
| Channels | 4, in this order: **[27, 26, 28, 25]** (0-based FECGSYNDB lead indices) |
| Input source (v1) | **UART from the PC**, replaying dataset samples (OPEN-3 for a real ADC) |
| Input word | 16-bit signed, full scale ±5.0 mV, 0.1526 uV/LSB (Q1.15 of 5 mV) |

---

## 3. Number formats (integer arithmetic, no floats in the golden model)

| Signal | Format | Notes |
|--------|--------|-------|
| Input sample | s16 Q1.15 | |
| Projection weights `w[0..3]` | s16 Q1.15 | Unit-norm eigenvector. |
| Projection accumulator | s48 (measured need: 27 bits on the synthetic test) | 4 products Q2.30, rounded `>> 7` to s24, saturating. |
| Data path | s24 Q1.23 (same 5 mV full scale, 8 extra fractional bits) | |
| HP1 accumulator | s32 (measured need: 25 bits) | |
| Biquad coefficients | s18 **Q3.15** | `round(c * 2^15)`; a numerator coefficient of 2.0 is exact. |
| Biquad states | full-precision accumulators, up to s48 (measured need: 35 bits) | Transposed direct form II; output rounded `>> 15`, saturating s24. |
| Detector input | s16 = s24 `>> 8`, saturating | |
| Squared value | u32 | |
| Moving-window sum | u40 register (measured need: 19 bits on the synthetic test), **not divided by 20** | Threshold is linear, so the 1/20 cancels. |
| Thresholds / levels | same width as the sum | |
| RR interval | u9 (valid 60..300 samples) | |
| FHR output | u12, bpm x 10 | |

---

## 4. Causal filter chain (replaces zero-phase filtering)

| Stage | Definition | Cost |
|-------|-----------|------|
| **HP1** baseline remover | `y = x - (acc >> 6)`; `acc += x - (acc >> 6)`. Cutoff about 0.62 Hz. Shifts and adds only. | no multiplier |
| **LP40** | Butterworth low-pass 40 Hz, order 4 = 2 biquads (`butter(4, 40/125, 'low')`). Output of this stage is `fecg_out`. | 2 biquads |
| **BP** (detector) | Butterworth band-pass 8-30 Hz, order 4 = 4 biquads (`butter(4, [8/125, 30/125], 'band')`) | 4 biquads |

Measured accuracy of Q3.15 coefficients against float: LP40 -73 dB, BP -69 dB relative error. Total group delay of HP1 + LP40 + BP at 15 Hz: **12.25 samples**, so `L_comp = 12`.

All 6 biquads time-share one multiplier: 6 x 5 = 30 multiply-cycles per sample.

---

## 5. QRS detector (causal redefinition of `qrs_detector.py`)

| Stage | Definition |
|-------|-----------|
| Square | `x_sq = x_bp * x_bp` |
| Moving-window sum | **Trailing** sum of the last 20 samples (80 ms), not centered. |
| Candidate | Sample m = n-1 is a candidate if `x_int[m-1] < x_int[m] >= x_int[n]` (one-sample lookahead). |
| Threshold | `thr = (peak >> 2) + noise - (noise >> 2)` (alpha = 0.25, shifts only) |
| Level updates | Candidate above `thr` and outside refractory: `peak += (v - peak) >> 3`. Candidate at or below `thr`: `noise += (v - noise) >> 3`. |
| Refractory | A candidate is accepted only if at least 50 samples (200 ms) have passed since the previous accepted candidate. |
| Dropped rule | The "replace the previous peak if a taller one arrives inside the refractory window" rule is removed (it would retract an already-output beat). |
| Warm-up | First **512** samples: no beats. `peak_0 = max(x_int)`, `noise_0 = sum(x_int) >> 9` over the warm-up. Replaces the 95th/50th percentile initialisation. The detector stays off if `peak_0 <= noise_0`. |
| R-peak localisation | Ring buffer of the last 32 values of `abs(x_bp)` (s16). On acceptance at sample n, R is the argmax over samples n-25..n (26 samples); the **earliest** maximum wins ties. |
| Latency compensation | Reported peak = R - 12 (`L_comp`, from the filter group delay, clipped at 0). |
| Beat flag | One-sample pulse at the sample where the beat is declared (n = m + 1). |

---

## 6. FHR

- `RR = R[k] - R[k-1]` in samples (raw R positions; the constant latency cancels).
- Valid if 60 <= RR <= 300 (50-250 bpm, same as `fhr.py`); otherwise flagged invalid, not dropped.
- `fhr_x10 = (300000 + RR) // (2 * RR)` = round(150000 / RR), from a 241-entry ROM (max 2500, fits 12 bits). No divider.
- The FHR value is held between beats. Scored output = raw per-beat FHR. A 5-beat median is an optional display output.

---

## 7. UART protocol (921,600 baud, 8N1)

**PC to FPGA, 10 bytes per sample:** `0xA5` | ch27 lo, hi | ch26 lo, hi | ch28 lo, hi | ch25 lo, hi | XOR of the 8 data bytes. At 250 Hz this is 2,500 B/s, about 2.7% of the link.

**FPGA to PC, 7 bytes per sample (one reply per input frame):** `0x5A` | flags (bit0 = beat declared on this sample, bit1 = FHR valid, bit2 = warm-up) | fecg_out lo, hi (s16 = s24 `>> 8`) | fhr_x10 lo, hi | XOR of bytes 1..5.

**Control frame (weights), PC to FPGA:** `0xC3` | 4 x s16 weights lo/hi | XOR checksum. Sent once before streaming. The sample counter on the PC gives the sample index of each reply.

---

## 8. Resource and timing budget (acceptance limits)

| Resource | Limit on XC7S50 |
|----------|------------------|
| LUTs | at most 5,000 (11.5%) |
| DSP48E1 | at most 8 |
| BRAM36 | at most 4 |
| Timing | 100 MHz, WNS >= 0 after implementation |
| Cycles per sample | under 10,000 (about 30 multiply-cycles for the filters plus bookkeeping) |
| Power | measured on the board (static + dynamic while streaming); analytic estimate only until then |

---

## 9. Verification and acceptance criteria

1. **Golden model** = `fpga_int_model.py` (Python ints only in the sample loop). `python src/fpga_int_model.py --record <prefix> ...` dumps hex files for the stimulus, weights and every stage (`proj_s24`, `hp_s24`, `fecg_s24`, `fecg_out_s16`, `det_bp_s16`, `x_int_u40`, `beat_flag`, `fhr_x10_hold_u16`, `fhr_lut_u16`) plus `peaks.txt` and `summary.json`.
2. **RTL vs golden model: bit-exact (0 LSB difference)**, per stage and at the output.
3. **Golden int model vs causal float model** (same quantised input and weights): fecg SQNR above 40 dB (71 dB on the synthetic test) and at most 3% of beats differing. Borderline beats whose energy sits on the threshold can flip once values are rounded; the RTL must match the integer model, not the float one.
4. **Reporting:** causal numbers are reported separately from the existing zero-phase numbers and labelled. Oracle-selected PCA is labelled as an upper bound.
5. **Board test:** the PC replays the same vectors over UART; beats and FHR from the FPGA must equal the golden model's output exactly.

---

## 10. OPEN decisions (need the data / the team)

| ID | Decision | Candidates (all implemented in `causal_pipeline.py`) | How to close it |
|----|----------|------------|-----------------|
| OPEN-1 | **Label-free component rule** replacing the oracle choice (F2) | `pc2` (fixed), `pc3` (fixed), `periodic_rr` (most regular beat train at 100-200 bpm), `autocorr` (strongest energy-envelope autocorrelation at 100-200 bpm lags) | `python src/run_causal_benchmark.py --with-legacy`. Choose using the TRAIN partition (sub01-07), sanity-check on sub08, report sub09-10 once. |
| OPEN-2 | **Calibration window** for the weights (F3) | 3, 10, 30, 60 s after the 2 s warm-up, or the whole record | Same run. Pick the shortest window within 1 F1 point of the whole-record result. |
| OPEN-3 | **Real ADC** | on-chip 12-bit XADC (about 8 LSB for a fetal peak) vs external 16-bit ADC | v1 stays UART/PC-fed. If a real front end is demoed, run the 12-bit study first (`UNRESOLVED.md`, Item 2). |

Also to confirm from the first real run: the `median_offset` column of the benchmark summary. If it is far from 0, adjust `CausalConfig.latency_comp`.

These three do not block the RTL for the filters, detector, FHR, or UART, which can start now. Only the weight values change, and they are loaded at run time.

---

## 11. Code map

| File | Purpose |
|------|---------|
| `code/src/causal_pipeline.py` | Float causal reference, PCA weights, label-free component rules, `CalibrationBank` |
| `code/src/fpga_int_model.py` | Integer golden model, hex dumps, `compare_with_float`, golden-vector CLI |
| `code/src/run_causal_benchmark.py` | Rule x calibration-window sweep over FECGSYNDB, train/val/test summary, optional legacy comparison |
| `code/tests/test_causal_pipeline.py`, `test_fpga_int_model.py`, `test_run_causal_benchmark.py` | 33 dataset-free tests on a synthetic mixture (`tests/_synth.py`) |

The existing zero-phase code is untouched, so the old benchmark stays reproducible.
