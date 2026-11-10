# v6: RTL + PC-brain split — work log

**Goal (user, 2026-11-10):** redistribute work between the FPGA and the PC so the FPGA part is hand-written RTL (no soft processor), giving the PC the minimum work needed to keep v5-level accuracy.

## Design (2026-11-10)
The v5 algorithm was split by rate.

**FPGA (RTL), everything at the sample rate:**
- filters;
- maternal detectors, R-peak bookkeeping and per-lead cancellation (lag search, history, fit and subtraction);
- 16 projections, band-pass, envelopes and blanking;
- 12 trackers and 4 threshold detectors;
- feature capture, envelope block medians;
- output beats and FHR.

**PC brain, five low-rate decisions.** It receives only FPGA-computed messages and never the recording. The FPGA stalls on a request until the answer arrives, so the result does not depend on timing.

| Job | Rate | FPGA sends | PC returns |
|---|---|---|---|
| Maternal PCA | once, 10 s | 4×4 covariance | 4 projection vectors (Q14) |
| Maternal train choice | every 5 s | detector peak events | train index |
| Template basis | per maternal beat (~2/s) | aligned 150×4 beat segment | orthonormal basis, ≤ 3 × 150 per lead (s24 Q22) |
| GEVD calibration | once, 15 s | 12 s of Z/Xf (int16) | 16 weight vectors (Q14) |
| Candidate selection | every 2.5 s | beat events, 31-sample snapshots, envelope block medians | track index |

**Fixed-point formats** (bit-accurate C model `fpga_implementation/v6/model/fpga_model.c`):
- filter data Q8 in int32;
- SOS coefficients Q28;
- 64-bit accumulators;
- Z and Xf int16, as in v5;
- envelopes stored as 16-bit monotonic codes with 8 significant bits (same precision as v5's bf16);
- tracker autocorrelation in 15-bit block floating point;
- comparisons exact in integers (0.25 × median becomes 4e > m, or 8e > a + b).

The template least-squares fit becomes a projection onto a PC-orthonormalised basis. Its span is the same, so mathematically the fit is identical to v5's Gauss-Jordan solve.

## Results: system model (RTL model + PC brain, via the real message protocol)

| Set | v5 (board) | **v6 model** |
|---|---|---|
| FECGSYNDB subset (60) | 91.92 | **91.83** |
| FECGSYNDB all 1,248 | 91.46 (PC model) | **91.44** (c0 96.8, c1 96.9, c2 91.7, c3 93.3, c4 78.5) |
| CinC dev (38) | 75.26 | **76.04** |
| ADFECGDB (5) | 93.44 | **92.73** |

- No value left its declared hardware width on any record (overflow checks in the model).
- **Link traffic per second of recording:**
  - **downlink, about 9.4 KB/s:** samples 2 KB/s and template bases 7.3 KB/s;
  - **uplink, about 7.2 KB/s:** features 4.6 KB/s, segments 1.6 KB/s, rest about 1 KB/s.
  - At 921600 baud, about 92 KB/s per direction, so the link allows up to roughly 10× real time.
