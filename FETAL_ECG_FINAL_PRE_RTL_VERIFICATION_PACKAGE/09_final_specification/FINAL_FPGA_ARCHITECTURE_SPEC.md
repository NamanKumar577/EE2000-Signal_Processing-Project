# Final FPGA Architecture and Resource Utilization Specification

**Target Device:** AMD/Xilinx Spartan-7 XC7S50-1CSGA324C  
**Evaluation Platform:** RealDigital Boolean Board  
**Target Clock Frequency:** 100.0 MHz  
**Sampling Rate:** 250 Hz ($4.0\text{ ms}$)  

---

## 1. Top-Level Module Hierarchy

```
fecg_top
├── clk_wiz_0 (100 MHz System Clock Generator)
├── uart_rx (921,600 Baud Receiver + Deserializer)
├── uart_framer (Header Detect: 0xA5, 0xC3 + CRC8 Check)
├── calibration_shadow_reg (16-bit x 4 Target Weights)
├── weight_slew_engine (64-Sample Linear Crossfade)
├── beamformer (4x Multiplier + 32-bit Accumulator + >>> 7)
├── hp1_remover (32-bit Accumulator, k=6)
├── biquad_cascade_lp40 (2x DF-II Transposed Biquads, 48-bit States)
├── biquad_cascade_bp (4x DF-II Transposed Biquads, 48-bit States)
├── energy_squarer (16x16 Unsigned Squarer)
├── mwi_accumulator (30-sample Sliding Sum, 36-bit Accumulator)
├── peak_detector_adaptive (Local Max + Adaptive Threshold)
├── interval_fusion_engine (RR < 50 comparator + Split Peak Arbitrator)
├── latency_subtractor (-18 Sample Timestamp Rewind)
├── median5_sorter (Pure Integer 5-Beat FIFO + 9-Comparator Sorting Net)
├── fhr_rom (251 x 12-bit Precomputed ROM)
├── uart_packetizer (0x5A Stream + 0xAA Telemetry Frames)
├── crc8_engine (Polynomial 0x07)
└── uart_tx (921,600 Baud Serializer)
```

---

## 2. FPGA Resource Budget on Spartan-7 XC7S50

| Hardware Resource | Available on XC7S50 | Required by Design | Utilization (%) | Safety Margin |
| :--- | :---: | :---: | :---: | :---: |
| **Logic LUTs** | 32,600 | ~3,420 | **10.49%** | **89.5% Free** |
| **Slice Registers (FF)**| 65,200 | ~4,180 | **6.41%** | **93.5% Free** |
| **DSP48E1 Slices** | 120 | 17 | **14.17%** | **85.8% Free** (103 DSPs free) |
| **Block RAM (BRAM 36k)**| 75 | 2.5 | **3.33%** | **96.6% Free** |
| **MMCM / PLLs** | 5 | 1 | **20.00%** | **4 Free** |
| **IOB Pins** | 210 | 8 | **3.81%** | - |

### DSP48 Allocation Breakdown:
- Beamformer: 4 DSP48 slices (4 channels $\times$ signed $16 \times 16$).
- LP40 Filter: 4 DSP48 slices (2 biquads $\times$ 2 DSPs per section).
- Config C Bandpass: 8 DSP48 slices (4 biquads $\times$ 2 DSPs per section).
- Energy Squarer: 1 DSP48 slice ($16 \times 16$ unsigned).
- Total: **17 DSP48 slices** (out of 120 available on Spartan-7).

---

## 3. Real-Time Latency & Timing Budget

1. **Processing Clock Cycles per Sample:**
   At 100 MHz system clock, the datapath pipeline executes in **55 clock cycles** ($550\text{ ns}$).
   Available budget between samples @ 250 Hz: $400,000\text{ clock cycles}$ ($4.0\text{ ms}$).
   **Clock Slack:** $> 99.98\%$ idle time per sample.
2. **Clinical Event Latency:**
   - Group delay latency: $18\text{ samples}$ ($72.0\text{ ms}$).
   - MWI window delay: $15\text{ samples}$ ($60.0\text{ ms}$).
   - Local peak search window: $26\text{ samples}$ ($104.0\text{ ms}$).
   - Total algorithmic event-to-declaration time: **$104.0\text{ ms}$**, well below the 1.0-second clinical threshold.
