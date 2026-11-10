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

## RTL (2026-11-10)
Hand-written Verilog in `fpga_implementation/v6/rtl/`. There is no soft processor: a sequential datapath runs one sample at a time, in the order of the C model.

| File | Function |
|---|---|
| `v6_uart.v` | UART 8-N-1 receiver and transmitter |
| `v6_link.v` | Frame parser, 512-sample FIFO, PC response buffers (basis RAM 1800×24), message writer, 4 KB TX FIFO |
| `v6_sos.v` | Time-multiplexed DF2T biquad cascade (Q28, 64-bit state), LP / maternal / BP sets |
| `v6_mwi.v` | Time-multiplexed moving-window integrators |
| `v6_det.v` | Time-multiplexed adaptive-threshold peak detectors |
| `v6_fe.v` | HP1 + LP + maternal band, 4 leads → Xf / Z rings |
| `v6_mat.v` | Maternal covariance, PCA handshake, 2,500-sample replay, 4 detectors, train rings, segment choice, R-peak queue |
| `v6_canc.v` | Lag search, segment, projection on the PC basis, tapered subtraction, 20-beat history, SEG |
| `v6_trk.v` | 16 tracks: projection with crossfade, BP, envelope code, blanking, trackers (block-floating autocorrelation, sorting networks), detectors, features, radix-select median, selection, output + FHR divider |
| `v6_core.v` | Xf / Z rings (4096×64 each), sequencer, CALDATA, DONE, port muxes |

### Verification
- Unit tests (xsim) against the C model:
  - SOS engine: 9,000 outputs, 0 errors;
  - MWI + detector engines: 20,000 samples × 2 instances, 0 errors.
- **System test (`sim/tb_core.v`):** the testbench acts as the board host. It sends the recording in 64-sample chunks, replays the PC brain's responses when their trigger frame arrives, and compares every uplink byte with the C system model.

| Record | Length | Uplink bytes | Frames | Errors |
|---|---|---|---|---|
| CinC a01 | 60 s | 406,454 | 6,580 | **0** |
| CinC a07 | 60 s | 409,771 | 6,473 | **0** |
| CinC a29 | 60 s | 394,992 | 6,104 | **0** |
| CinC a65 | 60 s | 427,056 | 6,114 | **0** |
| CinC a71 | 60 s | 417,980 | 6,707 | **0** |
| ADFECGDB r01 | 120 s | 838,652 | 13,532 | **0** |
| FECGSYNDB sub01 l1 c0 | 120 s | 976,056 | 14,660 | **0** |
| FECGSYNDB sub01 l5 c1 | 120 s | 1,047,441 | 15,669 | **0** |

The RTL is bit-exact with the system model, whose accuracy is in the table above.

Bugs found by the tests:
- the SEG frame length (604 → 1204);
- review-time fixes before simulation:
  - signedness of the detector constants;
  - a 4-bit loop index that could not reach 16;
  - byte packing of the track id.

## Implementation (2026-11-10)
`build_v6.tcl` → `v6/build/v6.bit` (xc7s50, PLL 100 → 50 MHz, UART 921600 baud).

| Resource | Used | Utilization |
|---|---|---|
| LUTs | 19.0k (3.4k as LUT RAM) | 58% |
| Flip-flops | 10.1k | 16% |
| DSP48 | 33 | 28% |
| BRAM tiles | 74.5 / 75 | 99% |
| Timing | WNS +0.49 ns at 50 MHz | met |

Fixes needed for implementation (the built bitstream contains them and is bit-exact on all 140 board records below):
- the Z ring was merged to a single write port so it maps to block RAM (distributed-RAM overuse);
- the sorting-network loop was rewritten for synthesis error 8-3380.

## Board results (2026-11-10)
`uart_host/run_v6_board_eval.py`: the PC streams the record and runs the brain pipe; the RTL does everything else. Every record's complete uplink byte stream was compared with the C system model.

| Set | Records | **v6 board F1** | Se | PPV | FHR MAE | Bit-exact | Speed | v5 board F1 |
|---|---|---|---|---|---|---|---|---|
| FECGSYNDB subset | 60 | **91.83** | 90.67 | 93.65 | 5.24 | 60/60 | 4.3× real time | 91.92 |
| CinC dev (odd) | 38 | **76.04** | 74.45 | 77.98 | 12.52 | 38/38 | 4.8× | 75.26 |
| ADFECGDB | 5 | **92.73** | 91.16 | 94.37 | 2.03 | 5/5 | 4.5× | 93.44 |
| CinC test (even, held out) | 37 | **65.48** | 64.39 | 67.00 | 18.37 | 37/37 | 5.0× | 65.75 |

- **140/140 records bit-exact**: the board equals the model, so the board F1 equals the model F1 on every set.
- CinC test was scored once with the frozen design; no v6 decision was tuned on it.
- Accuracy matches v5 within ±0.8 points on every set, now with all sample-rate work in hand-written RTL and no soft processor.
- Logs: `board_cdev_ad_ctest.log`, `board_syn.log`; per-record CSVs in `board/`.
