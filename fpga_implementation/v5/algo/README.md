# FECG v5 algorithm (runs on the FPGA)

`fecg_v5.c` is the complete fetal-ECG algorithm.

On the board it runs on the MicroBlaze soft core inside the Spartan-7 (xc7s50). The PC only streams the raw 4-lead abdominal recording: int16, 250 Hz.

The same source compiled on the PC (`host_main.c` → `fecg_v5_host.exe`) is the reference model. Board output is **bit-exact** with it.

## Properties
- **Strictly causal.** Every decision at input sample T uses samples ≤ T only.
- **Fixed latencies:**
  - the processing timeline ("Z-time") runs 176 samples (0.70 s) behind the input;
  - a selection decision for the window ending at t is made at t + 150;
  - beat reports therefore arrive about 1.5–2 s after the beat.
- **Label-free.** Annotations are used only by the scoring scripts.
- **Deterministic float32.**
  - No libm transcendentals: there is an own `mylogf`; `sqrtf` and `+ − × ÷` are IEEE.
  - The PC build sets FTZ/DAZ like the MicroBlaze FPU.
- **Memory:** 254.6 KB of the 256 KB LMB (code plus a 16 KB stack) and 30.4 KB of the 32 KB AXI BRAM.
- **Compute:**
  - about 47k cycles per sample at 73.728 MHz, which is 5.4× real time (16% of the 294k-cycle real-time budget);
  - the start-up calibration burst is one-off.

## Pipeline
1. **Front end, per lead.**
   - HP1 (one-pole baseline removal) followed by a Butterworth LP at 60 Hz gives Xf.
   - HP1 followed by a 5–25 Hz band-pass gives the maternal band.
2. **Maternal R peaks.**
   - PCA of the maternal band over the first 10 s.
   - One FPGA-style adaptive-threshold detector per principal component.
   - Every 5 s, choose the train that looks like a mother: the slowest regular train (≥ 60% of RR within 15%) at 40–130 bpm.
3. **Maternal cancellation, per lead.**
   - Keep the last 20 aligned maternal beats: −160 ms to +440 ms, aligned over ±4 samples.
   - Basis = their mean + the top-2 principal components, from an incremental Gram matrix and a warm-started subspace iteration.
   - Least-squares fit of the basis to each new beat, then subtract it (tapered edges). The result is Z.
4. **Calibration at 15 s.** Candidate spatial filters on the 15–40 Hz band of Z and of Xf over [3 s, 15 s):
   - unit leads;
   - self-referencing GEVD: detect beats, drop beats coincident with maternal peaks, take the QRS covariance against the total covariance, iterate 3 times from each PCA seed.
5. **16 candidate tracks.**
   - Z: 4 leads and 4 GEVD filters, each with an RR-predictive beat tracker on a maternal-blanked energy envelope.
   - Xf: 4 GEVD filters with the tracker, and the same 4 with the FPGA threshold detector.
6. **Selection** every 2.5 s, over the trailing 20 s. Quality is the product of:
   - median beat-morphology correlation;
   - acceptance;
   - log(1 + prominence);
   - RR-regularity²;
   - (0.5 + cross-track agreement);
   - an FHR prior: weight 0.2 at 80 bpm, rising to 1 at ≥ 120 bpm;
   - a maternal-coincidence penalty. It is applied only when the maternal reference comes from a component holding ≥ 10% of the maternal-band energy.
7. **Output.** The selected track's beats (−13 samples latency compensation). FHR = 60·250 / median of the last 5 RR intervals.

## Build
```
gcc -O2 -std=c99 -msse2 -mfpmath=sse -ffp-contract=off [-DFECG_DEBUG] -o fecg_v5_host.exe host_main.c fecg_v5.c -lm
cd .. && bash build_fw.sh -Ialgo -DFECG_MB algo/fecg_v5.c     # firmware + download.bit
```

Configuration knobs (`fecg_cfg_t`) exist only for development sweeps. The defaults in `fecg_v5.c` are the frozen design.
