# FECG v6: hand-written RTL on the FPGA, with a PC "brain" for the low-rate decisions

v6 is the v5 algorithm, split by rate:
- **FPGA (hand-written Verilog, no soft processor):** everything that runs at the 250 Hz sample rate.
- **PC brain (`model/brain.c`):** five low-rate decisions.
  - It never sees the recording, only compact features computed by the FPGA.
  - The FPGA stalls on each request until the reply arrives, so results do not depend on link timing.

| Job | Where | Rate |
|---|---|---|
| HP / LP / maternal-band filters (4 leads) | RTL `v6_fe` | sample |
| Maternal detectors (4 PCA projections), R-peak bookkeeping | RTL `v6_mat` | sample |
| Per-lead maternal cancellation: lag search, history, projection, subtraction | RTL `v6_canc` | maternal beat |
| 16 projections, band-pass, envelopes, blanking, 12 trackers, 4 detectors, features, selection output, FHR | RTL `v6_trk` | sample |
| Maternal PCA (from the FPGA's 4×4 covariance) | PC | once, 10 s |
| Maternal train choice | PC | every 5 s |
| Template basis (mean + 2 PCs of the last 20 beats, orthonormalised) | PC | per maternal beat |
| GEVD calibration of the 16 spatial filters | PC | once, 15 s |
| Candidate selection (quality, maternal-coincidence penalty, agreement) | PC | every 2.5 s |

## Files
| Path | Content |
|---|---|
| `model/proto.h` | Constants, message protocol, envelope code |
| `model/fpga_model.c` | Bit-accurate integer model of the RTL (the specification) |
| `model/brain.c`, `brain_main.c` | PC brain; `v6_brain.exe` is a stdin/stdout frame pipe used by the board host |
| `model/sim_main.c` | System model (RTL model + brain via the protocol); `V6_DUMP` writes golden streams |
| `rtl/*.v` | RTL: `v6_top`, `v6_core`, `v6_link`, `v6_uart`, `v6_fe`, `v6_mat`, `v6_canc`, `v6_trk`, engines `v6_sos`, `v6_mwi`, `v6_det` |
| `sim/tb_core.v`, `run_tb.sh`, `regress.sh` | System testbench: emulates the host and checks every uplink byte against the model |
| `build_v6.tcl`, `program_v6.tcl`, `v6.xdc` | Bitstream build and board programming |
| `../uart_host/run_v6_board_eval.py` | Board evaluation: stream, brain pipe, scoring, bit-exact check of the whole uplink stream |
| `../uart_host/run_v6_model_eval.py` | Same scoring with the C system model only (no board) |
| `sim/wave/` | Waveform run of the system test (`run_wave.sh` -> `wave.vcd`) and Vivado GUI view (`open_wave_gui.bat`) |
| `report_power_v6.tcl` | Re-runs implementation and writes `build/power.rpt` and `build/util_hier.rpt` (per module) |

## Protocol
Frames have the form `A5 5A cmd len16 payload xor8` and run over a UART at 921600 baud. The host sends 64-sample SAMPLES frames and waits for DONE after each. The full message list is in `model/proto.h`.

## Build and run
```
cd model && gcc -O2 -std=c99 -msse2 -mfpmath=sse -ffp-contract=off -o v6_sim.exe sim_main.c fpga_model.c brain.c -lm
gcc -O2 -std=gnu99 -msse2 -mfpmath=sse -ffp-contract=off -o v6_brain.exe brain_main.c brain.c -lm
cd ../sim && V6_DUMP=G ../model/v6_sim.exe rec.i16 && ./run_tb.sh            # RTL vs model
vivado -mode batch -source build_v6.tcl ; vivado -mode batch -source program_v6.tcl
python ../uart_host/run_v6_board_eval.py --sets cdev,ad
```

## Implementation (xc7s50, 50 MHz)
| Resource | Used | Utilization |
|---|---|---|
| LUTs | 18.1k | 56% (2.1k of them as LUT RAM) |
| Flip-flops | 10.0k | 15% |
| DSP48 | 33 | 28% |
| BRAM tiles | 60 / 75 | 80% (was 74.5 before the shared ymem/emem memory, 2026-11-14) |
| Timing | WNS +0.26 ns at 50 MHz | met |
| Power (Vivado estimate) | 0.374 W on-chip | 0.299 W dynamic + 0.075 W static |

In simulation the RTL needs a median of 1,485 clock cycles per sample once all 16 tracks run (about 140x faster than real time); on the board the UART link and the PC limit the system to 4-5x real time.

## Number formats
- Raw input: int16.
- Filter data: Q8 in int32.
- SOS coefficients: Q28.
- Products and accumulators: 64-bit.
- Z and Xf: stored as int16.
- Envelopes: monotonic 16-bit codes with 8 significant bits.
- Spatial weights and maternal projections: Q14.
- Template basis: s24 Q22.
- Tracker autocorrelation: 15-bit block floating point.

## v6.1 (2026-11-14)
Two label-free, causal improvements, selected with the Verilog / C define `V61`. Without the define, the RTL and the model are the frozen v6 that matches `build/v6.bit`.
1. **Maternal detectors:**
   - the warm-up starts at sample 256, after the filter start-up transient;
   - the peak level decays after 2 s without a detection.

   Before this, one early transient could blind all four detectors for the whole recording.
2. **Recalibration every 30 s:**
   - the latest 12 s of Z/Xf go back to the PC as CALDATA, followed by a REQ_CAL;
   - the PC keeps a track's old filter unless the new one gives a more regular beat train;
   - the FPGA cross-fades to the new weights over 64 samples.

| Step | Command |
|---|---|
| Model | `gcc ... -DV61 -o v61_sim.exe sim_main.c fpga_model.c brain.c -lm` and `-DV61 -o v61_brain.exe brain_main.c brain.c -lm` |
| RTL regression | `cd sim && SIMEXE=../model/v61_sim.exe DEFS="-d V61" ./regress.sh a01.i16 r_*.i16` |
| Build / program | `vivado -mode batch -source build_v61.tcl` (writes `build/v61/v61.bit`), `vivado -mode batch -source program_v61.tcl` |
| Board evaluation | `V6_VARIANT=v61 python ../uart_host/run_v6_board_eval.py --sets cdev,ad,ctest,syn` |
| Web demo | `V6_VARIANT=v61 python ../webdemo/server.py` |

v6.1 implementation: 18,986 LUTs (58%), 11,179 flip-flops, 60/75 BRAM, 33 DSP, WNS +0.41 ns at 50 MHz, 0.386 W (estimate). Results and the full log are in `report/v61_v7/LOG.md`.

v6.1 on the board: 140/140 records bit-exact with the v6.1 C model (207 MB uplink). Mean F1 CinC dev 80.41, ADFECGDB 92.87, CinC test 71.94, FECGSYNDB subset 91.64 (`report/v61_v7/board_v61/`).

## v7-DL (2026-11-14): the look-ahead on the FPGA
v6.1 plus a new RTL unit, `rtl/v7_la.v`, that chooses the final beats with about 15 s of look-ahead. Build with the Verilog / C defines `V61` and `V7`.
- The recording is still streamed in 64-sample chunks.
- `v7_la` listens to the uplink words of the other units (BEAT, FEAT, MPK, COV) and to RSP_V / RSP_MK. It does not change the v6.1 stream; it only adds frames.
- Every 2.5 s it scores all 16 tracks from 15 s before to 10 s after the segment and runs one Viterbi step. It then cleans up the chosen beats and sends them with a centred FHR as OUT7 frames (0x8D: u32 t, u16 fhr_x10, u8 track; track 16 = filled beat).
- The delay is about 13.5 s (median), at most 17.5 s.
- At the end of the recording the host sends FLUSH (0x03). The board then finishes the last segments with the data it has and sends END7 (0x8E: u32 number of OUT7).
- `rtl/v7_disp.v` shows the final answer on the board: display 0 shows the fetal heart rate (bpm) and display 1 the number of final beats. Both are cleared at the start of each recording.
- The PC still answers only the five v6 requests. The look-ahead runs on the FPGA.

| Step | Command |
|---|---|
| Model | `gcc ... -DV7 -o v7_sim.exe sim_main.c fpga_model.c brain.c v7_post.c -lm` and `-DV7 -o v7_brain.exe brain_main.c brain.c -lm` |
| RTL regression | `cd sim && SIMEXE=../model/v7_sim.exe DEFS="-d V61 -d V7" ./regress.sh a01.i16 r_*.i16` |
| Build / program | `vivado -mode batch -source build_v7.tcl` (writes `build/v7/v7.bit`), `vivado -mode batch -source program_v7.tcl` |
| Board evaluation | `V6_VARIANT=v7 python ../uart_host/run_v6_board_eval.py --sets cdev,ad,ctest,syn` |
| Web demo | `V6_VARIANT=v7 python ../webdemo/server.py`: the page shows the final FHR and beats from the FPGA look-ahead next to the live v6.1 estimate, the current look-ahead delay, and a signal window that follows the final beats; FLUSH at the end |

v7-DL implementation: 26,701 LUTs (82%), 15,970 flip-flops, 71/75 BRAM, 43 DSP, WNS +0.05 ns at 50 MHz, 0.445 W (estimate). Details and results: `report/v61_v7/LOG.md`, Part 4.

v7-DL on the board: 140/140 records bit-exact with the v7 C model. Mean F1 CinC dev 84.68, ADFECGDB 96.10, CinC test 76.91, FECGSYNDB subset 93.39 (v6.1 in the same runs: 80.41 / 92.87 / 71.94 / 91.64).
