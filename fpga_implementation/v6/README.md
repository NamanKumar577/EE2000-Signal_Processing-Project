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
