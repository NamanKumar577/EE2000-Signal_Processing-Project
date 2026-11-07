# Accuracy improvement (v2): causal, label-free

Everything here is **causal and label-free**. The deployed algorithm only ever uses:
- samples the device has already received;
- its own beat detections.

Annotations (`.qrs`) are used only to score results.

## Files
| File | Purpose |
|---|---|
| `harness.py` | FECGSYNDB loader and the corrected scorer (see "Scoring fixes" below) |
| `pipeline.py` | Float mirror of the FPGA datapath, with a numba detector, for fast experiments |
| `calib.py` | Research versions of the host calibrators |
| `exp_baseline.py`, `exp_diag.py`, `exp_spatial.py` | Experiments: baseline, best-possible-filter diagnostic, calibrator variants |
| `eval_bitaccurate.py` | **Final evaluation**: host controller (`src/fecg/host/adaptive_beamformer.py`) plus the bit-exact FPGA model, on all 1,248 single-fetus records |
| `eval_nifea.py` | Real clinical NIFEA data, surrogate metrics only (no fetal annotations exist) |

## Scoring fixes vs `scratch/run_complete_fecgsyndb_evaluation.py`
1. **Causal timeline.** The old evaluation computed the weights from the first 10 s of data and applied them from sample 0. Now:
   - the device starts with unity weights;
   - the host calibrates on samples already seen and sends a `0xC4` packet at 12 s;
   - beats are scored from 20 s to the end of each 5-minute record.
2. **FHR error.** The old metric compared every instantaneous detector RR with the record's single *nominal* header FHR, which is meaningless for accelerations, and any missed or extra beat produced a huge outlier. Now the device's reported FHR (median-of-5 stream) is compared with the true FHR (median-of-5 of the true RR) at every true beat.

## Bugs found and fixed
| # | Where | Bug | Effect |
|---|---|---|---|
| 1 | Detector design | The warm-up ran only at power-up. A real device gets its weights later, so the threshold was learned on the unity-weight (maternal-dominated) signal and stayed locked out. | Causal F1 collapsed to 14–31% |
| 2 | Latency compensation | Set to 18, which is the group delay at 15 Hz. The fetal QRS energy sits at 20–30 Hz, where the delay is 11–13 samples. | Every beat was reported about 4.3 samples (17 ms) early |
| 3 | `peak_localizer.v` | Hard-coded `6'd18` and ignored the `LATENCY_COMP` parameter. The testbenches and the xsim harness also pinned 18, which hid it. | Changing the parameter had no effect |
| 4 | `adaptive_detector.v` vs golden model | The RTL enabled the detector unconditionally (Python requires peak > noise) and skipped detection on the first post-warm-up sample. | Latent RTL/model mismatch |
| 5 | Calibration ridge | Diagonal loading was set relative to the covariance trace, which is dominated by the maternal ECG. A 0.1–1% ridge swamped the fetal and noise directions. | About 2 F1 points, and adaptive nulling was unusable |
| 6 | Calibrator assumptions | It assumed the strongest component is always maternal (wrong for sub10, maternal 36 bpm) and hard-limited plausible fetal rates to 95–210 bpm (excluding sub08's 93 bpm fetus). | Systematic failures on those subjects |

## Algorithm (host side, `src/fecg/host/adaptive_beamformer.py`)
The **self-referencing gated beamformer**:
- **Initial calibration (12 s):** detect beats with a candidate filter and drop beats that coincide with maternal R-peaks. Estimate the fetal-QRS covariance from the remaining detections, then take the top generalized eigenvector against the total covariance. Iterate from PCA and maternal-nulling seeds. Pick the candidate with a regular, periodic, fetal-rate beat train that is not time-locked to the maternal beats.
- **Every 2 s:** if recent power, whitened by the calibration covariance, exceeds 4×, null the new interference (for example a uterine contraction) while holding the fetal response constant. Otherwise keep the calibration weights.

The FPGA is unchanged apart from the `0xC4` restart and latency 13.

## Results: bit-accurate FPGA model, 1,248 FECGSYNDB records (c0–c4, all SNRs and layouts)
| | Frozen v1 (corrected causal eval) | **v2** |
|---|---|---|
| Mean F1 | 82.2% | **95.6%** (pooled 96.0%) |
| Sensitivity / PPV | 84.0 / 81.3% | **93.2 / 98.8%** |
| FHR MAE | 18.8 bpm | **2.5 bpm** |
| FHR within ±5 bpm | 64.7% | **93.9%** |

**v2 by condition (F1):**

| Condition | F1 |
|---|---|
| c0 baseline | 98.9% |
| c1 fetal movement | 96.0% |
| c2 accelerations | 99.97% |
| c3 contractions | 99.3% |
| c4 ectopic beats | 83.7% |

**c4:** even the best possible single 4-lead spatial filter, computed with knowledge of the true components, reaches only about 85%. The ectopic beats have a different electrical axis.

## Known limits
- **NIFEA (real clinical recordings):**
  - No fetal annotations exist, so only surrogate metrics are possible.
  - v2 no longer locks onto the maternal beat: maternal coincidence is 24% vs 33% for v1, with chance at about 15%.
  - Detections stay noisy (RR CV around 0.3). 50 Hz hum is *not* the cause: it carries about 0% of the power in the detection band.
  - An annotated real-data set is needed to make further progress: PhysioNet/CinC Challenge 2013 set-a, or ADFECGDB.
- **Twins (c5)** are not supported (single beamformer).

## Real clinical data with annotations: PhysioNet/CinC Challenge 2013, set-a (`eval_cinc2013.py`)
**Data:**
- 75 recordings (a01–a75), 60 s each, 4 abdominal leads, 1 kHz, reference `.fqrs` annotations.
- Extracted to `data/noninvasive-fetal-ecg-the-physionet-computing-in-cardiology-challenge-2013-1.0.0/extracted/`.

**Protocol:**
- Downsampled with a causal anti-alias filter to 250 Hz and scaled to 3,000 LSB/mV.
- Same device timeline as FECGSYNDB: `0xC4` at 12 s, then scoring from 20 s to 60 s (±50 ms).
- Run on the bit-exact FPGA model.

| | Old frozen design | **v2** |
|---|---|---|
| Mean F1 (75 records) | 19.8% | **41.6%** |
| Pooled F1 | 25.1% | **43.8%** |
| Mean F1 excluding the 7 records with unreliable reference (a33, a38, a47, a52, a54, a71, a74) | 20.7% | **43.5%** |
| Records with F1 ≥ 95% | 2 | 4 |

**Diagnostics** (`exp_cinc.py`, `exp_c3.py`, `exp_mts.py`; these use the true annotations and are *not* deployable):
- **Ceiling of the architecture:** the best possible single 4-lead linear filter, chosen with the true annotations and run through the same detector, averages only **60%** F1 on CinC (62% median). On FECGSYNDB the same diagnostic gives 96%. On real recordings the architecture itself is the limit, not just how the filter is estimated.
- **Template subtraction:** causal maternal template subtraction per lead (EMA template, alignment and amplitude matching) removes a median of only 8 dB of maternal energy. It raises that ceiling to 65%, but the label-free calibration does worse on its output (33%).
- **"Fastest regular train" selection (FHR > MHR):** 32%. Rejected.

**Conclusion:** v2 doubles real-data accuracy, but real-data F1 above 90% needs a stronger front end than one linear spatial filter. That is a redesign, not tuning.
