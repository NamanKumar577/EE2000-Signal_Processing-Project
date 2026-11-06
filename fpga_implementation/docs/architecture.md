# Spartan-7 Hardware Architecture, Resource Budget & UART Diagnostic Audit

**Document Path:** `fpga_implementation/docs/architecture.md`  
**Target Device:** AMD / Xilinx Spartan-7 FPGA (`XC7S50-1CSGA324C`)  
**Package / Speed Grade:** CSGA324 ($15 \times 15\text{ mm}$, $0.8\text{ mm}$ pitch), Speed Grade -1  
**Target Platforms:** RealDigital Boolean Board (Primary), Digilent Arty S7-50 (Secondary)  
**System Clock:** $100.0\text{ MHz}$ Master Oscillator ($10.0\text{ ns}$ period)  
**Sample Rate:** $f_s = 250\text{ Hz}$ ($4.0\text{ ms} = 400{,}000\text{ clock cycles}$)

---

## 1. Executive Summary & Device Profile

The AMD/Xilinx Spartan-7 `XC7S50` is a low-power, high-performance 28nm FPGA optimized for edge signal processing and medical instrumentation.

```
                              SPARTAN-7 XC7S50 HARDWARE SILICON PROFILE
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Configurable Logic:                                                                    │
 │   - Logic Cells: 52,160                       - Slices: 8,150                          │
 │   - Configurable 6-Input LUTs: 32,600         - Slice Flip-Flops (FFs): 65,200         │
 │                                                                                        │
 │ Arithmetic & Memory:                                                                   │
 │   - Dedicated DSP48E1 Slices: 120 (25x18 MAC) - Block RAM 36k: 75 blocks (2,700 kb)    │
 │   - Distributed LUT RAM: Up to 400 kb         - Internal Shift Registers (SRL32): Yes  │
 │                                                                                        │
 │ Clocking & Mixed-Signal:                                                               │
 │   - Clock Management Tiles (CMTs): 5 (MMCM + PLL) - Max Core Clock: Up to 464 MHz      │
 │   - Dual 12-Bit 1 MSPS Analog XADC: 1         - User I/O Pins: 210 (HR Banks 1.2V-3.3V)│
 │                                                                                        │
 │ Power & Thermal:                                                                       │
 │   - Core Operating Voltage (VCCINT): 1.0 V    - Typical Static Power: ~70 mW           │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Resource Utilization Estimates: Multi-Channel vs Single-Channel

The table below contrasts the projected hardware utilization across the entire Spartan-7 `XC7S50` device for the Full Multi-Channel System, the Single-Channel Shared Variant, and the Standalone Bringup Module:

```
                      RESOURCE CONSUMPTION COMPARISON ON SPARTAN-7 XC7S50
  ┌───────────────────────┬──────────────┬──────────────┬──────────────┬──────────────────┐
  │ Resource Type         │ Device Total │ Full 4-Ch    │ Single-Ch    │ Standalone UART  │
  │                       │ (XC7S50)     │ Parallel     │ Shared DSP   │ Bringup Module   │
  ├───────────────────────┼──────────────┼──────────────┼──────────────┼──────────────────┤
  │ Configurable LUTs     │ 32,600       │ 1,732 (5.3%) │ 990 (3.0%)   │ 180 (0.5%)       │
  │ Slice Registers (FF)  │ 65,200       │ 1,804 (2.8%) │ 1,420 (2.2%) │ 160 (0.2%)       │
  │ DSP48E1 Slices        │ 120          │ 17 (14.2%)   │ 1 (0.8%)     │ 0 (0.0%)         │
  │ Block RAM (BRAM36k)   │ 75           │ 1.0 (1.3%)   │ 1.0 (1.3%)   │ 0 (0.0%)         │
  │ User I/O Pins         │ 210          │ 12 (5.7%)    │ 12 (5.7%)    │ 12 (5.7%)        │
  │ Dynamic Power (mW)    │ ~1,500 mW    │ < 28 mW      │ < 18 mW      │ < 8 mW           │
  │ Execution Latency     │ 400,000 cyc  │ 70 cycles    │ 95 cycles    │ N/A              │
  │ Idle Clock Margin     │ —            │ 99.982%      │ 99.976%      │ —                │
  └───────────────────────┴──────────────┴──────────────┴──────────────┴──────────────────┘
```

### Detailed Subsystem Breakdown (Full Multi-Channel System):

| Subsystem Module | Math / Logic Description | Slice LUTs | Slice FFs | DSP48 Slices | Block RAMs |
|:---|:---|:---:|:---:|:---:|:---:|
| **UART RX & Framer** | 8-N-1 921.6k RX, 2-stage sync, packet parser | 130 | 110 | 0 | 0 |
| **Weight RAM & Slew Engine** | 4 active/shadow registers, 64-step slew | 95 | 110 | 1 (opt) | 0 |
| **Spatial PCA Beamformer** | $\sum_{i=0}^3 w_i x_i[n]$, Q1.15 weights, signed 16x16 | 112 | 84 | 4 | 0 |
| **HP1 Baseline Wander Remover** | $y[n] = x[n] - (\text{acc} \gg 6)$, 32-bit accumulator | 48 | 56 | 0 | 0 |
| **LP40 Filter (Order 4)** | 2 Biquads Transposed DF-II, Q3.15 coeffs | 284 | 340 | 4 | 0 |
| **Config C BP Filter (Order 8)** | 4 Biquads Transposed DF-II, Q3.15 coeffs | 568 | 680 | 8 | 0 |
| **Nonlinear Squarer** | $sq = z_{16} \times z_{16}$, unsigned 16x16 multiplier | 8 | 16 | 1 | 0 |
| **MWI 30-Sample Running Sum** | 30-word circular RAM, 36-bit accumulator | 78 | 84 | 0 | 0.5 |
| **Adaptive Dual-Threshold FSM** | 1/8 EMA level updates, 50-sample refractory | 94 | 104 | 0 | 0 |
| **Trailing Localizer & Rewind** | 26-sample search comparator, 12-sample rewind subtractor (LATENCY_COMP_REG[4:0], default 12) | 55 | 74 | 0 | 0 |
| **Interval Fusion & Median-5** | Split-beat merge ($RR < 50$), 5-beat sorter | 82 | 96 | 0 | 0 |
| **FHR ROM LUT & Telemetry TX**| 251-word reciprocal ROM, CRC8 engine, FIFO, TX | 176 | 140 | 0 | 0.5 (ROM) |
| **TOTAL MULTI-CHANNEL SYSTEM** | **Complete Synchronous Pipeline** | **1,732** | **1,804** | **17** | **1.0** |

*Safety Margin:* The design occupies less than **$6\%$ of device LUTs** and **$15\%$ of DSP slices**, allowing ample space for future on-chip expansions (such as 8-channel array processing, real-time VGA/OLED display drivers, or embedded microcontrollers).

---

## 3. Clocking Architecture, Timing Budget & Buffering

### 3.1 Clock Domains & Generation Strategy
The system operates within a single primary synchronous clock domain with multi-rate clock enables:

1. **$100.0\text{ MHz}$ Master System Clock (`clk`):**
   - Sourced from onboard crystal oscillator on Pin `F14` (RealDigital Boolean Board) or Pin `R2` (Arty S7).
   - Period: $T_{\text{clk}} = 10.0\text{ ns}$ ($50\%$ duty cycle).
   - Routed globally via a dedicated `BUFG` buffer, minimizing clock skew to $< 0.1\text{ ns}$.
   - All flip-flops, DSP slices, and memory blocks are clocked by the rising edge of `clk`.
2. **$250.0\text{ Hz}$ Sample Strobe Generator (`sample_valid`):**
   - Driven either by the UART ingestion packet receiver upon successful CRC8 check or by an onboard 24-bit baud divider:
     $$\text{DIVIDER} = \frac{100{,}000{,}000\text{ Hz}}{250\text{ Hz}} = 400{,}000\text{ clock cycles}$$
   - Generates a single-cycle synchronous pulse every $4.0\text{ ms}$, initiating the 70-cycle pipeline execution.
3. **UART Baud Rate Clock-Enable Dividers:**
   - **$115{,}200\text{ Baud}$ (Bringup):**
     $$\text{CLKS\_PER\_BIT} = \left\lfloor \frac{100{,}000{,}000 + 57{,}600}{115{,}200} \right\rfloor = 868\text{ cycles} \implies \text{Timing Error: } +0.0064\%$$
   - **$921{,}600\text{ Baud}$ (Production):**
     $$\text{CLKS\_PER\_BIT} = \left\lfloor \frac{100{,}000{,}000 + 460{,}800}{921{,}600} \right\rfloor = 109\text{ cycles} \implies \text{Timing Error: } -0.452\%$$
   - Both baud rates fall well within the standard RS-232 $\pm 2.5\%$ timing tolerance.

### 3.2 Elastic Buffering & Rate Decoupling
To absorb rate jitter between the host operating system and the hardware sample strobe:
- **Downlink Ingestion:** An incoming 10-byte packet arrives in $108.5\ \mu\text{s}$ at 921,600 baud. The samples are latched into holding registers `x_sync[0..3]`, where they remain stable for the remainder of the $4.0\text{ ms}$ sample interval.
- **Uplink Telemetry FIFO:** An elastic circular FIFO with 16 entries ($16 \times 8\text{ bits}$) buffers outgoing bytes between the telemetry formatter and `uart_tx`.
  - Simultaneous read and write are fully supported without race conditions.
  - Sticky diagnostic flags latch if framing error (`led[2]`) or FIFO overflow (`led[3]`) occurs.

---

### 3.3 Programmable Configuration Registers & Latency Compensation Engine

To ensure seamless alignment with authoritative golden reference vectors while retaining clinical flexibility, the datapath incorporates a dedicated programmable latency compensation register:

#### 1. Register Specification: `LATENCY_COMP_REG[4:0]`
- **Register Name:** `LATENCY_COMP_REG[4:0]`
- **Width:** 5 bits unsigned (`[4:0]`).
- **Valid Range:** $0 \dots 31$ samples ($0.0 \dots 124.0\text{ ms}$ at $f_s = 250\text{ Hz}$, $4.0\text{ ms/LSB}$).
- **Power-On / Hardware Reset Default:** `5'd12` ($12\text{ samples} = 48.0\text{ ms}$).
- **Access:** Read/Write via UART Downlink Calibration/Config Packet (`0xC3`) or dedicated register access.
- **Clock Domain:** Synchronous $100.0\text{ MHz}$ master clock domain (`clk`).

#### 2. Datapath Mathematical Formulation & Saturating Subtractor
Upon declaration of a candidate fetal R-peak by the trailing localizer at raw timestamp $r_{\text{raw}}$ (24-bit sample counter), the latency compensation engine calculates the compensated timestamp $t_R$:
$$t_R = \max(0, r_{\text{raw}} - \text{LATENCY\_COMP\_REG}[4:0])$$

In synthesizable Verilog, this is implemented as a 24-bit zero-floor saturating subtractor:
```verilog
// 24-bit Latency Compensation Subtractor with Zero-Floor Saturation
reg  [4:0]  latency_comp_reg; // Defaults to 5'd12; programmable via UART 0xC3
wire [23:0] latency_comp_ext = {19'b0, latency_comp_reg};
wire [23:0] t_r_compensated  = (r_raw >= latency_comp_ext) ? 
                               (r_raw - latency_comp_ext) : 24'd0;
```

#### 3. Alignment Rationale & Verification Impact
- **Golden Reference Vector Synchronization:** Authoritative golden test vectors in `code/results/fpga_golden/sub01_snr12_c0/` (`summary.json`: `"latency_samples": 12`) apply a 12-sample subtraction ($r_{\text{raw}} = 534 \rightarrow t_R = 522$). Setting `LATENCY_COMP_REG = 12` guarantees **zero LSB timestamp discrepancy** in Milestone M2 RTL simulation.
- **Empirical Passband Alignment:** Compensating for 12 samples ($48.0\text{ ms}$) aligns with the broadband spectral centroid of the fetal QRS complex ($29.2\text{ Hz}$, group delay $\approx 12.1\text{ samples}$), achieving $+0.080\text{ samples}$ ($+0.32\text{ ms}$) mean timing bias and $65.90\%$ concordance within $\pm 2$ samples across 30 PhysioNet benchmark records.
- **Hardware Cost:** The 5-bit register and 24-bit saturating subtractor require only 5 flip-flops and ~5 LUTs, fully covered by the Trailing Localizer budget (55 LUTs, 74 FFs).

---

## 4. Root-Cause Analysis & Fix for UART Bringup Watchdog Timeout and Stuck-High Signal

A critical finding from the survey audit is the resolution of the historical simulation watchdog timeouts ($30.0\text{ ms}$ and $2.5\text{ ms}$) and stuck-high signal anomalies in `uart_bringup/`.

### 4.1 Bug 1: Transmitter Non-Blocking Assignment Phase Lag in `uart_tx.v`

#### The Anomaly:
In `uart_production_timing_tb.v`, bit duration measurements across data bits $D_0 \dots D_7$ occasionally failed or exhibited 1-clock-cycle jitter. When serializing data words ending in `1` followed by STOP bit, `uart_txd` appeared "stuck high" or shifted out of phase by 1 clock cycle relative to the bit duration counter.

#### Root Cause:
Prior to commit `1df759f`, `uart_tx.v` evaluated `tx_serial <= tx_shift[bit_idx];` continuously at the top of `STATE_DATA`. When `clk_cnt == CLKS_PER_BIT - 1`, `bit_idx` was scheduled to increment on the upcoming clock edge, but `tx_serial` was assigned using the *un-incremented* `bit_idx`. This created a 1-clock-cycle phase lag on every bit transition, extending bit 0 to $\text{CLKS\_PER\_BIT} + 1$ cycles and delaying the stop bit transition.

#### Verified Fix (Commit `1df759f`):
Removed continuous assignment to `tx_serial` in `STATE_DATA`. Replaced with explicit boundary updates:
```verilog
STATE_START: begin
    tx_serial <= 1'b0;
    if (clk_cnt == CLKS_PER_BIT - 1) begin
        clk_cnt   <= 0;
        tx_serial <= tx_shift[0]; // Drive bit 0 (LSB) exactly on boundary
        state     <= STATE_DATA;
    end else begin
        clk_cnt <= clk_cnt + 1'b1;
    end
end

STATE_DATA: begin
    if (clk_cnt == CLKS_PER_BIT - 1) begin
        clk_cnt <= 0;
        if (bit_idx == 3'd7) begin
            bit_idx   <= 0;
            tx_serial <= 1'b1; // Drive STOP bit exactly on boundary
            state     <= STATE_STOP;
        end else begin
            bit_idx   <= bit_idx + 1'b1;
            tx_serial <= tx_shift[bit_idx + 1'b1]; // Explicitly drive next bit
        end
    end else begin
        clk_cnt <= clk_cnt + 1'b1;
    end
end
```
All bits now endure for **exactly $\text{CLKS\_PER\_BIT}$ clock cycles** ($868$ cycles at 115,200 baud, $109$ cycles at 921,600 baud) with $0\text{ ns}$ jitter.

---

### 4.2 Bug 2: Testbench `fork...join` Race Condition & Unbounded While Loops

#### The Anomaly:
In simulation of `uart_production_timing_tb.v`, the simulator hung indefinitely until the global watchdog timer terminated the process:
```
[FATAL ERROR] Production Timing Watchdog Expired (30.0 ms)!
DUT State at Watchdog: fifo_count=0, wr_ptr=0, rd_ptr=0, rx_busy=0, tx_busy=0
```

#### Root Cause:
1. In `uart_production_timing_tb.v`, a `fork...join` parallel block launched `host_send_byte` and `proc_measure_rx` concurrently on time tick 0. If `host_send_byte` executed first in Verilog delta scheduling, `uart_rxd` was pulled low *before* `proc_measure_rx` executed `@(negedge uart_rxd)`. The falling edge was permanently missed.
2. Subsequent `while` loops waiting for internal FSM states had no cycle bounds (`while (uut.u_uart_rx.state !== 3'b001) @(posedge clk);`). Spinning indefinitely with zero progress, the simulation stalled until the $30.0\text{ ms}$ watchdog tripped.

#### Verified Fix:
1. Added a 5-clock-cycle startup delay (`repeat (5) @(posedge clk);`) in `proc_send` to guarantee all concurrent monitoring tasks are actively waiting on their sensitive edges.
2. Wrapped all polling loops with explicit cycle-bounded timeout counters (`timeout_cnt < 50`):
```verilog
timeout_cnt = 0;
while (uut.u_uart_rx.state !== 3'b001 && timeout_cnt < 50) begin
    @(posedge clk);
    timeout_cnt = timeout_cnt + 1;
end
if (timeout_cnt >= 50) begin
    $display("  [%0t ns] [TIMEOUT] RX monitor timed out waiting for STATE_START entry!", $time);
    err_cnt = err_cnt + 1;
end
```

---

### 4.3 Bug 3: Synchronizer Reset Invariant & False Start Bit Triggering

#### The Anomaly:
If reset initialized synchronizer flip-flops `rx_sync_stage1` and `rx_sync` to `0`, the receiver triggered a false start bit immediately upon reset deassertion.

#### Root Cause:
The UART serial line idles high (`1'b1`). If `rx_sync` is initialized to `1'b0`, `STATE_IDLE` detects `rx_sync == 0` on cycle 0 and immediately enters `STATE_START`, asserting `rx_busy` and generating a spurious framing error.

#### Verified Fix:
Synchronizer flip-flops and serial lines are explicitly initialized to `1'b1` (MARK state):
```verilog
if (rst) begin
    rx_sync_stage1 <= 1'b1;
    rx_sync        <= 1'b1;
    tx_serial      <= 1'b1;
end
```
Verified in `adversarial_stress_check.py` Check 4.3.

---

## 5. Board Physical Constraints & Pin Mapping

The FPGA processor is constrained for two hardware platforms in `fpga_implementation/constraints/`:

```
                           PHYSICAL PIN CONNECTIONS TABLE
 ┌───────────────────────┬───────────────────────┬──────────────────────┬─────────────┐
 │ Signal Port Name      │ RealDigital Boolean   │ Digilent Arty S7-50  │ I/O Standard│
 ├───────────────────────┼───────────────────────┼──────────────────────┼─────────────┤
 │ Master Clock (clk)    │ Pin F14 (100.0 MHz)   │ Pin R2 (100.0 MHz)   │ LVCMOS33    │
 │ Master Reset (rst_pin)│ Pin J2 (BTN0, Act-H)  │ Pin G15 (BTN0, Act-H)│ LVCMOS33    │
 │ UART RX (uart_rxd)    │ Pin V12 (FTDI Pin 38) │ Pin V12 (FTDI TXD)   │ LVCMOS33    │
 │ UART TX (uart_txd)    │ Pin U11 (FTDI Pin 39) │ Pin R12 (FTDI RXD)   │ LVCMOS33    │
 │ Diagnostic LED 0      │ Pin G1 (RX Activity)  │ Pin E18              │ LVCMOS33    │
 │ Diagnostic LED 1      │ Pin G2 (TX Activity)  │ Pin F13              │ LVCMOS33    │
 │ Diagnostic LED 2      │ Pin F1 (Framing Err)  │ Pin E13              │ LVCMOS33    │
 │ Diagnostic LED 3      │ Pin F2 (FIFO Overflow)│ Pin H14              │ LVCMOS33    │
 │ Diagnostic LEDs [7:4] │ Pins E5, E3, E2, E1   │ Pins J15, G17, F15   │ LVCMOS33    │
 └───────────────────────┴───────────────────────┴──────────────────────┴─────────────┘
```

*Pin Polarity Resolution:* Cross-checking the FTDI FT2232H schematic confirms:
- FTDI TXD (pin 38, BDBUS0) routes to FPGA **Pin `V12`** $\rightarrow$ FPGA Input (`uart_rxd`).
- FTDI RXD (pin 39, BDBUS1) routes to FPGA **Pin `U11`** $\rightarrow$ FPGA Output (`uart_txd`).
- Master Clock on the RealDigital Boolean Board is **Pin `F14`** (not `E3`, which connects to `LED[6]`).
