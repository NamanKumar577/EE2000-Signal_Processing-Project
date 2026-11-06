# Synthesizable RTL Modules (`fpga_implementation/rtl/`)

This directory is reserved for the synthesizable Verilog HDL (`.v`) source modules implementing the Fetal ECG FPGA extraction and QRS detection processor on the Spartan-7 FPGA (`XC7S50-1CSGA324C`).

## STATUS: HALTED FOR ARCHITECTURAL REVIEW (MILESTONE M0)

In strict accordance with the project constraints and Phase 1 roadmap, **no synthesizable Verilog RTL files (`.v`) are generated in this directory yet**. RTL generation will commence in Milestone M1 following formal approval of the architecture, fixed-point sizing matrix, and algorithm mapping documented in `fpga_implementation/docs/`.

## Planned RTL Module Architecture (Milestone M1)

When RTL generation is initiated, this directory will host:

1. **`fecg_top.v`**: Top-level system integration module wiring UART, packet parsing, datapath pipeline, and telemetry formatting.
2. **`uart/`**:
   - `uart_rx.v`: 8-N-1 UART receiver with 2-stage synchronizer and false start-bit glitch rejection.
   - `uart_tx.v`: 8-N-1 UART transmitter with boundary-aligned bit serialization.
   - `uart_fifo.v`: 16-entry circular elastic FIFO buffer.
   - `crc8_engine.v`: Synthesizable byte-serial CRC8-CCITT engine (poly `0x07`).
   - `packet_parser.v`: Downlink frame parser for `0xA5` (samples) and `0xC3` (weights).
   - `telemetry_formatter.v`: Uplink frame serializer for `0x5A` (stream) and `0xAA` (FHR).
3. **`datapath/`**:
   - `beamformer.v`: 4-channel spatial projection MAC with 64-sample linear crossfade engine.
   - `hp1_filter.v`: Multiplier-free baseline wander remover ($k=6$, $f_c \approx 0.62\text{ Hz}$).
   - `biquad_df2t.v`: Parameterized Second-Order Section in Transposed Direct Form II with Q3.15 coefficients and 48-bit internal accumulation.
   - `lp40_filter.v`: 4th-order Butterworth lowpass filter (2 cascaded biquads, $40\text{ Hz}$).
   - `bp_detector_filter.v`: 8th-order Config C Butterworth bandpass filter (4 cascaded biquads, $12\text{--}35\text{ Hz}$).
   - `squarer.v`: DSP48-mapped 16x16 unsigned squarer.
   - `mwi_ring.v`: 30-sample trailing rectangular sum with circular RAM buffer.
   - `adaptive_threshold.v`: Causal dual-threshold tracking FSM with 1/8 EMA updates.
   - `peak_localizer.v`: 26-sample trailing window local maximum search with 18-sample rewind subtractor.
   - `interval_fusion.v`: Split-peak merge logic ($RR < 50$) and duplicate suppression.
   - `median5_filter.v`: Pure integer 5-element sorting network.
   - `fhr_rom_lut.v`: 251-word lookup table translating RR interval to FHR in $0.1\text{ bpm}$ units.
