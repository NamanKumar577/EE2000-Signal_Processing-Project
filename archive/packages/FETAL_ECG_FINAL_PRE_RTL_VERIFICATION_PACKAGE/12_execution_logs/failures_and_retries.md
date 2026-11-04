# Failures, Diagnostics, and Retries Log

## 1. Priority A: Fixed-Point Projection Scaling Factor-of-128 Bug
- **Symptom:** In Phase 2, `run_fixed_point_audit_corrected.py` reported a catastrophic projection SQNR of **-42.08 dB**.
- **Root Cause Forensic:**
  - Input ADC scale: $4096\text{ LSB/mV}$ ($2^{12}$).
  - Weights scale: $32768\text{ LSB/unit}$ ($2^{15}$).
  - Hardware right-shift: $7\text{ bits}$ ($2^7$).
  - Physical scale at projection: $\frac{2^{12} \times 2^{15}}{2^7} = 2^{20}\text{ LSB/mV} = 1,048,576\text{ LSB/mV}$.
  - The Phase 2 code divided by $2^{23}$ and multiplied by $(32768 \times 128 / 4096) = 1024$, effectively dividing integer projection counts by $2^{13}$ instead of $2^{20}$.
  - Mathematical error ratio: $\frac{2^{20}}{2^{13}} = 2^7 = 128$ (or $127$ with rounding).
  - Theoretical SQNR error: $10 \log_{10}(1 / 127^2) = -42.08\text{ dB}$, exactly matching the reported failure!
- **Resolution:**
  - Corrected physical reconstruction formula: $x_{\text{mV}} = \text{proj}_q / 2^{20}$.
  - Corrected projection SQNR: **52.66 dB** (mean across 30 records, range 47.9 to 68.9 dB).
  - Corrected Clean FECG SQNR: **56.10 dB** (mean across 30 records).
  - Status: **RESOLVED (PASS)**.

---

## 2. Priority D: Validation Subject `sub08` Cold-Start Failure
- **Symptom:** Phase 2 reported 0.0% acceptance for `sub08` on cold-start calibration.
- **Root Cause Forensic:**
  - Subject `sub08` presents with an unusually low fetal heart rate of $93.5\text{ bpm}$.
  - At $f_s = 250\text{ Hz}$, $93.5\text{ bpm}$ corresponds to an R-R interval of:
    $$\tau = \frac{60 \times 250}{93.5} = 160.4\text{ samples}$$
  - The Phase 2 script constrained the autocorrelation lag search to $[83, 136]\text{ samples}$ ($110 \dots 180\text{ bpm}$), completely excluding the true fetal peak at lag $160$.
- **Resolution:**
  - Extended autocorrelation search lag range to $[83, 166]\text{ samples}$ ($90 \dots 180\text{ bpm}$).
  - Verified on `sub08`: fetal peak at lag 160 is detected with confidence margin $\ge 0.20$.
  - Status: **RESOLVED (PASS)**.

---

## 3. Priority E: Filter Group Delay Contradiction (12.4 vs 18 Samples)
- **Symptom:** Documentation stated a filter group delay of 12.4 samples, whereas empirical lag-maximization indicated 18 samples.
- **Root Cause Forensic:**
  - 12.4 samples ($49.6\text{ ms}$) was the group delay of the *legacy* 8–30 Hz 2nd-order bandpass filter.
  - Phase 2 updated the detector filter to Config C (12–35 Hz 4th-order cascade), steepening the transition band and increasing the phase delay at 15 Hz to **17.86 samples** ($71.4\text{ ms}$).
  - Documenting 12.4 samples while using Config C created a 5.5-sample (22 ms) uncompensated timing bias.
- **Resolution:**
  - Recomputed theoretical group delay: 17.86 samples @ 15 Hz.
  - Integer latency rewind subtractor locked to **18 samples**.
  - Mean temporal offset against reference annotations reduced to **-0.15 samples** (-0.6 ms).
  - Status: **RESOLVED (PASS)**.

---

## 4. Priority C: Cherry-Picked FHR Performance Claims
- **Symptom:** Phase 2 text claimed M4 corrected MAE of $4.98\text{ bpm}$ ($84.6\%$ within $\pm 5\text{ bpm}$), but the companion CSV had an average MAE of $15.63\text{ bpm}$.
- **Root Cause Forensic:**
  - In `run_fhr_stage_audit.py`, the previous author manually wrote string literals `"4.98"` and `"84.6%"` into the markdown generation block, reflecting only pristine condition c0/c2 recordings and hiding noisy condition c1 ($16.21\text{ bpm}$) and c3 ($26.79\text{ bpm}$).
  - In condition c3, severe maternal EMG noise degrades upstream QRS detection to $52.8\%$, creating irreducible FHR errors.
- **Resolution:**
  - Complete re-execution across all 150 records using causal reference model.
  - Separated macro-averaged results from clean condition vs noisy condition performance.
  - Transparently reported M4 macro MAE of **13.42 bpm** across all records, and **5.43 bpm** on clean condition c0.
  - Status: **RESOLVED (PASS)**.

---

## 5. Test Suite Collection and Syntax Errors
- **Issue 1:** Pytest command invoked system Python 3.13 without pytest installed.
  - **Resolution:** Directed invocation to `.\venv\Scripts\python -m pytest`.
- **Issue 2:** Test authoring used temporary symbol names (`ADC_SCALE` instead of `ADC_SCALE_LSB_PER_MV`, `det_bp_biquad_state_overflow` instead of `bp_biquad_state_overflow`).
  - **Resolution:** Aligned test assertions exactly with the locked reference class signatures in `bit_accurate_reference_model_final.py`.
  - Status: **RESOLVED (PASS)**.
