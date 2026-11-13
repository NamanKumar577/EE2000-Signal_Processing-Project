# Project Specification: Real-Time Fetal ECG Extraction & QRS Processor on Spartan-7 FPGA

**Repository Root:** `d:\signal_project\`  
**Target Hardware:** AMD / Xilinx Spartan-7 FPGA (`XC7S50-1CSGA324C` on RealDigital Boolean Board / Digilent Arty S7-50)  
**Operating Parameters:** Master Clock $f_{\text{clk}} = 100.0\text{ MHz}$ ($T_{\text{clk}} = 10.0\text{ ns}$), Sample Rate $f_s = 250\text{ Hz}$ ($T_s = 4.0\text{ ms} = 400{,}000\text{ cycles}$), Host Baud Rate = $921{,}600\text{ Baud}$  
**Target Dataset:** PhysioNet Fetal ECG Synthetic Database (FECGSYNDB at 250 Hz, 34 channels, 16-bit format)  
**Methodology:** Strictly Non-Machine-Learning Fixed-Point DSP Pipeline (Deep learning models excluded)

---

## 1. System Architecture & Module Dataflow

### 1.1 End-to-End System Block Diagram

```
                                      SPARTAN-7 FPGA ACCELERATOR (XC7S50)
                      ┌────────────────────────────────────────────────────────────────────────┐
                      │                                                                        │
 HOST PC (Python)     │   [ Mod 1: UART RX ] (921,600 Baud, 8-N-1, Over-sampling, 2-stage sync)│
 (Ingestion Driver)   │          │                                                             │
      │               │          ▼                                                             │
      │ 0xA5 (10B)    │   [ Mod 2: Downlink Packet Parser ] ──► CRC8 Check (Poly 0x07, Init 0) │
      │ 0xC3 (10B)    │          │                                                             │
      ├──────────────►│          ├───────────────────────────────┐                             │
      │  (uart_rxd)   │          ▼                               ▼                             │
      │               │   [ Mod 3: 4-Ch Sample Buffer ]   [ Mod 4: Weight RAM & Slew Engine ]  │
      │               │   (x0..x3: s16 Q12, 4096 LSB/mV)   (w0..w3: s16 Q1.15, 64-step slew)   │
      │               │          │                               │                             │
      │               │          └───────────────┬───────────────┘                             │
      │               │                          ▼                                             │
      │               │   [ Mod 5: Spatial PCA Beamformer ] (4 MACs, s24 Q20, 2^20 LSB/mV)     │
      │               │          │                                                             │
      │               │          ▼                                                             │
      │               │   [ Mod 6: HP1 Baseline Remover ] (k=6, fc ~ 0.62 Hz, Shift & Add)     │
      │               │          │                                                             │
      │               │          ▼                                                             │
      │               │   [ Mod 7: LP40 Lowpass Filter ] (40 Hz Butterworth, 2 Biquads DF2T)   │
      │               │          │                                                             │
      │               │          ├───────────────────────────────┐                             │
      │               │          ▼                               ▼ Clean FECG Stream           │
      │               │   [ Mod 8: Config C Bandpass ]   [ Mod 14: Telemetry Formatter ]       │
      │               │   (12-35 Hz, 4 Biquads DF2T)     (Serializes 0x5A Stream & 0xAA Event) │
      │               │          │                               ▲                             │
      │               │          ▼                               │                             │
      │               │   [ Mod 9: Nonlinear Squarer ]           │                             │
      │               │   (z16^2 -> u32 Q2.30)                   │                             │
      │               │          │                               │                             │
      │               │          ▼                               │                             │
      │               │   [ Mod 10: MWI Sliding Sum ]            │                             │
      │               │   (30-sample ring, u36 accumulator)      │                             │
      │               │          │                               │                             │
      │               │          ▼                               │                             │
      │               │   [ Mod 11: Adaptive Dual-Threshold ]    │                             │
      │               │   (EMA level updates, 50-smp refractory) │                             │
      │               │          │                               │                             │
      │               │          ▼                               │                             │
      │               │   [ Mod 12: Peak Localizer & Subtractor] │                             │
      │               │   (26-smp search, -12 smp rewind)        │                             │
      │               │          │                               │                             │
      │               │          ▼                               │                             │
      │               │   [ Mod 13: Interval Fusion & FHR ROM ] ──┘                             │
      │               │   (Split-beat merge, Median-5, 251-word FHR LUT)                       │
      │               │          │                                                             │
      │               │          ▼                                                             │
      │ 0x5A (6B)     │   [ Mod 15: UART TX ] ──► 16-Entry Elastic Circular FIFO               │
      │ 0xAA (8B)     │          │                                                             │
      │◄──────────────┤          └─────────────────────────────────────────────────────────────┘
      │  (uart_txd)   │
```

### 1.2 Processing Schedule and Clock Margins

At $100.0\text{ MHz}$ and $f_s = 250\text{ Hz}$, the FPGA provides **400,000 clock cycles** per biopotential sample interval ($4.0\text{ ms}$). The full causal pipelined datapath executes in **70 clock cycles** ($0.70\ \mu\text{s}$):

| Processing Stage | Execution Cycles | Latency at 100 MHz | Cumulative Latency |
|---|:---:|:---:|:---:|
| **Downlink Packet Parse & CRC8** | 1 | 10 ns | 10 ns |
| **Spatial Beamforming (4 Channels)** | 4 | 40 ns | 50 ns |
| **HP1 Baseline Wander Removal** | 2 | 20 ns | 70 ns |
| **LP40 4th-Order Butterworth Filter (2 Biquads)** | 10 | 100 ns | 170 ns |
| **Config C Bandpass Filter (4 Biquads)** | 20 | 200 ns | 370 ns |
| **Nonlinear Squaring Unit** | 1 | 10 ns | 380 ns |
| **MWI 30-Sample Running Accumulator** | 2 | 20 ns | 400 ns |
| **Adaptive Dual-Threshold Tracking FSM** | 2 | 20 ns | 420 ns |
| **Trailing Localizer & Latency Subtractor** | 27 | 270 ns | 690 ns |
| **Interval Fusion & Median-5 FHR LUT** | 2 | 20 ns | 710 ns |
| **Total Active Compute Cycles** | **70 cycles** | **0.710 µs** | **0.0178% Active Duty** |
| **Available Idle Margin per Sample** | **399,930 cycles** | **3,999.29 µs** | **99.9822% Idle Slack** |

---

## 2. Feature Inventory & Mapping to Milestones

The project features are partitioned across four sequential engineering milestones:

```
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │                                   PROJECT MILESTONES                                   │
  ├───────────────────┬───────────────────┬────────────────────────┬───────────────────────┤
  │    Milestone M0   │    Milestone M1   │      Milestone M2      │      Milestone M3     │
  │ Baseline Audit &  │ Algorithm Mapping │  Top-Level Integration │ Hardware Deployment,  │
  │ Hardware Specs    │ & RTL Generation  │ & Closed-Loop Sim      │ HIL & Benchmarking    │
  │ (Current Freeze)  │ (Submodules)      │ (Vivado Synthesis)     │ (FECGSYNDB Eval)      │
  └───────────────────┴───────────────────┴────────────────────────┴───────────────────────┘
```

### Feature Catalog

| Feature ID | Subsystem / Feature Description | Relevant Files & Modules | Target Milestone | Status |
|:---:|:---|:---|:---:|:---:|
| **FEAT-01** | Authoritative Non-ML Pipeline Identification & ML Isolation | `src/fecg/hardware/bit_accurate_reference.py`, `causal_pipeline.py` | M0 | Complete |
| **FEAT-02** | Resolution of Group Delay Latency Discrepancy (12-sample lock to golden vectors) | `src/fecg/hardware/bit_accurate_reference.py`, `fpga_implementation/docs/` | M0 | Complete |
| **FEAT-03** | Resolution of -42 dB Fixed-Point Scaling Bug ($2^{20}\text{ LSB/mV}$ locked) | `bit_accurate_reference.py`, `fpga_int_model.py` | M0 | Complete |
| **FEAT-04** | Directory Structure & Root Project Architecture Initialization | `fpga_implementation/**`, `PROJECT.md` | M0 | Complete |
| **FEAT-05** | Master Fixed-Point Parameter Specification & DSP48 Alignment | `fpga_implementation/docs/fixed_point_specification.md` | M0 | Complete |
| **FEAT-06** | Algorithm-to-Hardware Mapping & Single-Channel Feasibility | `fpga_implementation/docs/algorithm_mapping.md` | M0 | Complete |
| **FEAT-07** | UART Transceiver Audit, Framing & Watchdog Bug Remediation | `archive/uart_bringup/`, `fpga_implementation/docs/uart_protocol.md` | M0 | Complete |
| **FEAT-08** | Spartan-7 Resource, Power & Clocking Architecture Specification | `fpga_implementation/docs/architecture.md` | M0 | Complete |
| **FEAT-09** | Parameterized Transposed Direct Form II Biquad Core (`biquad_df2t.v`)| `fpga_implementation/rtl/datapath/biquad_df2t.v` | M1 | Planned |
| **FEAT-10** | Cascaded LP40 Lowpass and Config C Bandpass Filters | `fpga_implementation/rtl/datapath/lp40_filter.v`, `bp_filter.v` | M1 | Planned |
| **FEAT-11** | Spatial PCA Beamformer with 64-Sample Linear Crossfade Engine | `fpga_implementation/rtl/datapath/beamformer.v` | M1 | Planned |
| **FEAT-12** | Multiplier-Free HP1 Baseline Wander Remover ($k=6$) | `fpga_implementation/rtl/datapath/hp1_filter.v` | M1 | Planned |
| **FEAT-13** | Non-Linear Squarer and 30-Sample MWI Ring Buffer | `fpga_implementation/rtl/datapath/mwi_ring.v` | M1 | Planned |
| **FEAT-14** | Adaptive Dual-Threshold Peak Detector & Refractory FSM | `fpga_implementation/rtl/datapath/adaptive_threshold.v` | M1 | Planned |
| **FEAT-15** | Trailing R-Peak Localizer & Group Delay Latency Rewind Subtractor | `fpga_implementation/rtl/datapath/peak_localizer.v` | M1 | Planned |
| **FEAT-16** | Interval Fusion Engine & Pure Integer Median-5 Sorter | `fpga_implementation/rtl/datapath/interval_fusion.v`, `median5.v` | M1 | Planned |
| **FEAT-17** | 251-Word Reciprocal FHR Lookup Table (ROM LUT) | `fpga_implementation/rtl/datapath/fhr_rom_lut.v` | M1 | Planned |
| **FEAT-18** | Production UART Transceiver & Elastic FIFO (`uart_top.v` @ 921.6k) | `fpga_implementation/rtl/uart/` | M1 | Planned |
| **FEAT-19** | Downlink & Uplink Telemetry Packet Framing Engines with CRC8 | `fpga_implementation/rtl/uart/packet_parser.v`, `telemetry.v` | M1 | Planned |
| **FEAT-20** | Top-Level FPGA Processor Integration (`fecg_top.v`) | `fpga_implementation/rtl/fecg_top.v` | M2 | Planned |
| **FEAT-21** | Full Closed-Loop Cycle-Accurate Verilog Testbench (`tb_fecg_top.v`)| `fpga_implementation/testbenches/tb_fecg_top.v` | M2 | Planned |
| **FEAT-22** | Vivado Synthesis, Placement, Routing & Timing Closure (100 MHz) | `fpga_implementation/reports/` | M2 | Planned |
| **FEAT-23** | Host Streaming Driver & Real-Time Visualization GUI | `fpga_implementation/uart_host/` | M3 | Planned |
| **FEAT-24** | Physical Hardware Deployment & In-System Telemetry Validation | Target Hardware: RealDigital Boolean Board | M3 | Planned |
| **FEAT-25** | Comprehensive PhysioNet FECGSYNDB 10-Subject Benchmark Evaluation | `fpga_implementation/reports/benchmark_report.md` | M3 | Planned |

---

## 3. Milestones Table

| Milestone | Title | Scope & Objectives | Key Deliverables | Acceptance Criteria | Target Status |
|:---:|:---|:---|:---|:---|:---:|
| **M0** | **Baseline Audit & Architecture Freeze** | Audit non-ML Python pipeline; freeze mathematical equations, golden hex vectors, and fixed-point specifications; document UART protocol and Spartan-7 constraints; pause before RTL generation. | - `PROJECT.md`<br>- `fpga_implementation/docs/` (6 docs)<br>- Directory tree with READMEs<br>- Verification logs | 100% test pass on active suites; zero modifications to protected directories; bit-exact mathematical specifications locked. | **Current Milestone (Complete)** |
| **M1** | **Algorithm Mapping & Submodule RTL** | Implement parameterized Verilog RTL for all 14 processing blocks; build unit testbenches; verify submodules bit-for-bit against Python models. | - `fpga_implementation/rtl/`<br>- `fpga_implementation/testbenches/`<br>- Submodule simulation passes | 100% equivalence on impulse/step responses; zero overflow in biquad state registers; CRC8 matching standard vector. | Ready for Phase 2 |
| **M2** | **Top-Level Integration & Synthesis** | Integrate full pipeline in `fecg_top.v`; run closed-loop simulation on 5,000-sample benchmark; synthesize in Vivado; achieve timing closure at 100 MHz. | - `fecg_top.v`<br>- `tb_fecg_top.v`<br>- Vivado synthesis & timing reports | 0 LSB mismatch against golden hex vectors; WNS $\ge 0.5\text{ ns}$ at 100 MHz; $<12\%$ Spartan-7 LUT utilization. | Planned |
| **M3** | **Hardware Deployment & Evaluation** | Program Spartan-7 bitstream; execute real-time streaming at 921,600 baud; evaluate detection F1-score across 10 PhysioNet subjects. | - Bitstream (`.bit`)<br>- Host streaming suite<br>- Clinical benchmark report | Real-time streaming sustained with zero dropped packets; F1-score $\ge 90\%$ on SNR $\ge 6\text{ dB}$; clinical latency $< 110\text{ ms}$. | Planned |

---

## 4. Interface Contracts

### 4.1 Host-to-FPGA Physical & Framing Contract

- **Physical Media:** USB-to-UART via onboard FTDI FT2232H chip.
- **Baud Rate:** $921{,}600\text{ Baud} \pm 0.46\%$ (Bringup fallback: $115{,}200\text{ Baud}$).
- **Framing:** 8 data bits, no parity, 1 stop bit (8-N-1), LSB-first transmission.
- **Byte Order:** All multi-byte numerical fields are **Big-Endian (MSB First)**.
- **Error Detection:** CRC8-CCITT with polynomial $G(x) = x^8 + x^2 + x + 1$ (`0x07`), initial value `0x00`, no input/output reflection, final XOR `0x00`. Verified by standard vector: `b"123456789"` $\rightarrow$ `0xF4`.

### 4.2 Telemetry Packet Protocol Data Units (PDUs)

```
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │                            TELEMETRY PACKET FORMAT SUMMARY                             │
  ├──────┬──────┬────────────────────────┬─────────────┬───────────┬───────────────────────┤
  │ PDU  │ Sync │ Direction              │ Byte Length │ Frequency │ Description           │
  ├──────┼──────┼────────────────────────┼─────────────┼───────────┼───────────────────────┤
  │ 0xA5 │ 0xA5 │ Host -> FPGA (Downlink)│ 10 Bytes    │ 250 Hz    │ 4-Ch Ingestion Samples│
  │ 0xC3 │ 0xC3 │ Host -> FPGA (Downlink)│ 10 Bytes    │ On-demand │ 4 Spatial PCA Weights │
  │ 0x5A │ 0x5A │ FPGA -> Host (Uplink)  │ 6 Bytes     │ 250 Hz    │ Clean FECG Waveform   │
  │ 0xAA │ 0xAA │ FPGA -> Host (Uplink)  │ 8 Bytes     │ Event-rate│ QRS Event & FHR Telemetry│
  │ 0xEE │ 0xEE │ FPGA -> Host (Uplink)  │ 8 Bytes     │ On-error  │ Hardware Diagnostics  │
  └──────┴──────┴────────────────────────┴─────────────┴───────────┴───────────────────────┘
```

#### Detailed Byte Formats:

1. **Downlink Ingestion Packet (`0xA5`, 10 Bytes):**
   - `[0]`: `0xA5` (Sync Header)
   - `[1]`: `seq_num[7:0]` (Rolling counter $0 \dots 255$)
   - `[2:3]`: `ch27[15:0]` (Channel 27, Signed 16-bit Q12, Big-Endian)
   - `[4:5]`: `ch26[15:0]` (Channel 26, Signed 16-bit Q12, Big-Endian)
   - `[6:7]`: `ch28[15:0]` (Channel 28, Signed 16-bit Q12, Big-Endian)
   - `[8]`: `ch25_msb[7:0]` (or single-channel data)
   - `[9]`: `crc8[7:0]` (Computed over bytes 0 through 8)

2. **Downlink Calibration Packet (`0xC3`, 10 Bytes):**
   - `[0]`: `0xC3` (Sync Header)
   - `[1:2]`: `w0[15:0]` (Weight 0, Signed 16-bit Q1.15, Big-Endian)
   - `[3:4]`: `w1[15:0]` (Weight 1, Signed 16-bit Q1.15, Big-Endian)
   - `[5:6]`: `w2[15:0]` (Weight 2, Signed 16-bit Q1.15, Big-Endian)
   - `[7:8]`: `w3[15:0]` (Weight 3, Signed 16-bit Q1.15, Big-Endian)
   - `[9]`: `crc8[7:0]` (Computed over bytes 0 through 8)

3. **Uplink Clean FECG Stream Packet (`0x5A`, 6 Bytes):**
   - `[0]`: `0x5A` (Sync Header)
   - `[1]`: `seq_num[7:0]` (Rolling counter $0 \dots 255$)
   - `[2:4]`: `fecg_clean[23:0]` (Signed 24-bit Q20, Big-Endian, scale $2^{20}\text{ LSB/mV}$)
   - `[5]`: `crc8[7:0]` (Computed over bytes 0 through 4)

4. **Uplink QRS Event & FHR Packet (`0xAA`, 8 Bytes):**
   - `[0]`: `0xAA` (Sync Header)
   - `[1:3]`: `timestamp[23:0]` (Latency-compensated sample timestamp $t_R = \max(0, r_{\text{peak}} - 12)$)
   - `[4:5]`: `fhr_x10[15:0]` (Instantaneous FHR in $0.1\text{ bpm}$ units, Big-Endian: e.g. $1402 \implies 140.2\text{ bpm}$)
   - `[6]`: `status_byte[7:0]`:
     * `bits[1:0]`: Beat Classification (`00`=REAL, `01`=FUSED, `10`=HELD, `11`=WARMUP)
     * `bit[2]`: Calibration Confidence (`1`=High, `0`=Low)
     * `bit[3]`: Filter Saturation Indicator (`1`=Saturated, `0`=Normal)
     * `bits[7:4]`: Reserved (`0000`)
   - `[7]`: `crc8[7:0]` (Computed over bytes 0 through 6)

5. **Uplink Diagnostic Packet (`0xEE`, 8 Bytes):**
   - `[0]`: `0xEE` (Sync Header)
   - `[1]`: `err_code[7:0]` (`0x01`=CRC Error, `0x02`=Sequence Gap, `0x03`=Biquad Saturation, `0x04`=FIFO Overflow)
   - `[2:3]`: `max_state[15:0]` (Peak filter state value)
   - `[4:5]`: `threshold[15:0]` (Current adaptive threshold)
   - `[6]`: Reserved (`0x00`)
   - `[7]`: `crc8[7:0]` (Computed over bytes 0 through 6)

### 4.3 Master Fixed-Point Numeric Sizing Matrix

| Signal / Register | Type | Width | Fractional | Q-Format | Physical Scale | Clamping Rule |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `x_adc[0..3]` | Signed | 16 | 12 | $s16\text{ Q12}$ | $4096\text{ LSB/mV}$ ($\pm 8.0\text{ mV}$) | $\text{sat}_{s16}$ |
| `w_pca[0..3]` | Signed | 16 | 15 | $s16\text{ Q1.15}$ | $32768\text{ LSB/unit}$ | $\text{sat}_{s16}$ |
| `proj_acc` | Signed | 32 (48 DSP) | 27 | $s32\text{ Q27}$ | Accumulates 4x Q27 | $\text{sat}_{s32}$ |
| `proj_s24` | Signed | 24 | 20 | $s24\text{ Q20}$ | $2^{20} = 1,048,576\text{ LSB/mV}$ | $\text{sat}_{s24}$, Nearest-Even $\gg 7$ |
| `hp_acc` | Signed | 32 | 20 | $s32\text{ Q20}$ | DC offset accumulator | $\text{sat}_{s32}$ |
| `biquad_coef` | Signed | 18 | 15 | $s18\text{ Q3.15}$ | $32768\text{ LSB/unit}$ ($b=2.0 \implies 65536$) | Exact representation |
| `biquad_state` | Signed | 48 | 35 | $s48\text{ Q35}$ | 48-bit DSP48 accumulator | $\text{sat}_{s48}$ |
| `fecg_clean` | Signed | 24 | 20 | $s24\text{ Q20}$ | $2^{20}\text{ LSB/mV}$ | $\text{sat}_{s24}$, Nearest-Even $\gg 15$ |
| `det_bp16` | Signed | 16 | 12 | $s16\text{ Q12}$ | $4096\text{ LSB/mV}$ | $\text{sat}_{s16}$, Nearest-Even $\gg 8$ |
| `squarer_out` | Unsigned | 32 | 24 | $u32\text{ Q24}$ | $(4096\text{ LSB/mV})^2$ | Multiplier pipeline |
| `mwi_sum` | Unsigned | 36 | 24 | $u36\text{ Q24}$ | 30-sample rolling sum | $\text{sat}_{u36}$ |
| `threshold` | Unsigned | 36 | 24 | $u36\text{ Q24}$ | $0.25 \cdot \text{peak} + 0.75 \cdot \text{noise}$ | Shift and add |
| `rr_fifo` | Unsigned | 9 | 0 | $u9\text{ Q0}$ | Samples ($50 \dots 300$, $200 \dots 1200\text{ ms}$) | Range check |
| `fhr_x10` | Unsigned | 12 | 0 | $u12\text{ Q0}$ | $0.1\text{ bpm}$ ($500 \dots 3000$) | 251-word ROM LUT |

---

## 5. Codebase Layout & Workspace Boundaries

```
d:\signal_project/
├── PROJECT.md                               # Root Project Specification (This document)
├── README.md                                # Repository Overview
├── docs/hardware_spec/                      # Hardware specifications and reports (was hardware/spec/)
│   ├── FPGA_SPEC.md                         # Authoritative FPGA Specification v0.2
│   ├── MASTER_FPGA_IMPLEMENTATION_AND_FEASIBILITY_REPORT.md
│   └── DATASHEETS_AND_HARDWARE_SPECS.md
├── fpga_implementation/                     # Exclusive Workspace for FPGA Implementation
│   ├── README.md                            # FPGA root readme
│   ├── docs/                                # Authoritative documentation deliverables
│   │   ├── README.md
│   │   ├── python_reference_baseline.md     # Non-ML Python execution path & golden vectors
│   │   ├── algorithm_mapping.md             # Difference equations, registers & DSP mapping
│   │   ├── fixed_point_specification.md     # Numeric sizing, rounding & saturation matrix
│   │   ├── uart_protocol.md                 # Packet framing, CRC8, and baud rate specs
│   │   ├── architecture.md                  # Spartan-7 resources, clocking & watchdog fixes
│   │   └── implementation_status.md         # Status report pausing before RTL generation
│   ├── rtl/                                 # Synthesizable Verilog HDL (Paused for M0 review)
│   │   └── README.md
│   ├── python_model/                        # Bit-accurate and integer Python reference models
│   │   └── README.md
│   ├── testbenches/                         # Submodule and top-level Verilog testbenches
│   │   └── README.md
│   ├── simulation/                          # Simulation runners and regression harnesses
│   │   └── README.md
│   ├── uart_host/                           # Host-side Python streaming & GUI tools
│   │   └── README.md
│   ├── test_data/                           # Golden stimulus hex files & reference vectors
│   │   └── README.md
│   ├── reports/                             # Vivado synthesis, timing & utilization reports
│   │   └── README.md
│   └── constraints/                         # Board constraint files (.xdc)
│       └── README.md
├── archive/uart_bringup/                    # Standalone verified UART reference infrastructure (moved)
│   ├── rtl/                                 # Verified uart_rx.v, uart_tx.v, uart_top.v
│   ├── tb/                                  # Verified simulation testbenches
│   ├── sim/                                 # run_sim.py, adversarial_stress_check.py
│   └── constraints/                         # boolean_board.xdc (Pins F14, J2, V12, U11)
├── src/fecg/                                # Active modular Python package (Protected read-only)
│   ├── hardware/                            # bit_accurate_reference.py, fpga_int_model.py
│   ├── pipelines/                           # causal_pipeline.py
│   ├── detection/                           # fhr.py, qrs.py
│   ├── telemetry/                           # uart_protocol.py
│   └── models/                              # fecg_unet.py (Excluded from FPGA)
├── code/                                    # Legacy code and golden test vectors (Protected read-only)
│   └── results/fpga_golden/sub01_snr12_c0/  # 17 authoritative golden hex vector files
├── data/FECGSD/DESTINATION/                 # PhysioNet FECGSYNDB benchmark data (Protected read-only)
├── tests/                                   # Existing test suites (Protected read-only)
│   ├── hardware/                            # 26 passed tests
│   └── regression/                          # 26 passed tests
└── archive/agent_sessions/                  # Agent metadata only (was .agents/teamwork/)
    ├── worker_baseline_1/                   # DISPATCH.md, BRIEFING.md, progress.md, handoff.md
    ├── explorer_survey_1/                   # Non-ML pipeline audit findings
    ├── explorer_survey_2/                   # Hardware models & difference equations findings
    └── explorer_survey_3/                   # UART bringup & Spartan-7 architecture findings
```
