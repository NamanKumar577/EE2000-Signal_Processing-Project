# v2 physical FPGA validation (2026-11-07)

**Bitstream:** `fpga_implementation/bitstream/fecg_multichannel_top.bit`
- Changes: v2 RTL, `0xC4` detector restart, latency 13, `peak_localizer` fix.
- Post-route: WNS +12.58 ns, WHS +0.044 ns at 25 MHz, 3,881 LUTs (11.9%), 39 DSPs, 0 BRAM, 0 critical warnings.
- The previous bitstream is kept as `fecg_multichannel_top_prev_lat18.bit`.

**Setup:**
- RealDigital Boolean Board (XC7S50), COM5, 115,200 baud, freshly programmed before the run.
- Samples were streamed at 250 Hz.
- The host controller (`src/fecg/host/adaptive_beamformer.py`) decided the weight packets causally while streaming.
- The bit-exact model (`src/fecg/hardware/bit_accurate_reference.py`) mirrored the board with continuous state.
- Script: `fpga_implementation/uart_host/run_v2_hardware_validation.py`.

| Record | Samples | Weight pkts | ECG stream exact | Lost / CRC err | Beats board = model (timestamps identical) | Board F1 | Board PPV | Board FHR MAE |
|---|---|---|---|---|---|---|---|---|
| sub01_snr06dB_l1_c0 | 15,000 | 1 (`0xC4`) | 100% | 0 / 0 | 131 = 131 ✔ | 100.0 | 100.0 | 0.72 |
| sub04_snr00dB_l2_c1 | 15,000 | 1 | 100% | 0 / 0 | 86 = 86 ✔ | 100.0 | 100.0 | 1.55 |
| sub07_snr09dB_l3_c2 | 15,000 | 1 | 100% | 0 / 0 | 105 = 105 ✔ | 100.0 | 100.0 | 0.95 |
| sub10_snr12dB_l1_c2 | 15,000 | 1 | 100% | 0 / 0 | 125 = 125 ✔ | 99.43 | 100.0 | 0.57 |
| sub08_snr03dB_l5_c0 | 15,000 | 1 | 100% | 0 / 0 | 90 = 90 ✔ | 100.0 | 100.0 | 1.06 |
| sub05_snr03dB_l3_c3 (full 5 min, contraction) | 75,000 | 46 (1 `0xC4` + 45 gated `0xC3`) | 100% | 0 / 0 | 579 = 579 ✔ | 96.19 | 95.6 | 4.23 |

**Totals:**
- 165,000 samples with 0 LSB error and 0 lost packets.
- 1,116 beats with every timestamp identical to the model.
- FHR telemetry agrees with the model on 1,114 of 1,116 beats. The other 2 are the first two beats after power-up, before any RR interval exists: the board correctly sends FHR = 0, while the model's hold stream shows its 140.0 bpm placeholder.

F1 and FHR are computed from the **board's own telemetry** against the annotations, scored from 20 s.

**Scope:** the full-database accuracy (1,248 records) is from the bit-exact model; see `tools/accuracy/README.md`. These hardware runs show that the board reproduces that model exactly.
