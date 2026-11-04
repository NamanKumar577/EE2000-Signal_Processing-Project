# FPGA Module Interface and Pin-Level Signal Specification

**Document ID:** `validation/pre_fpga/07_fpga_specification/FPGA_MODULE_INTERFACE_SPEC.md`  
**Target Hardware:** AMD/Xilinx Spartan-7 XC7S50-1CSGA324C  
**Author:** Biomedical Signal Processing & FPGA Verification Team  

---

## 1. Top-Level External Pin Interface (`fecg_top.v`)

```verilog
module fecg_top (
    input  wire        clk_100m,    // 100 MHz oscillator input (Pin H16)
    input  wire        rst_btn_n,   // Active-low push-button reset (Pin V15)
    input  wire        uart_rxd,    // UART Serial In from Host / FTDI (Pin T14)
    output wire        uart_txd,    // UART Serial Out to Host / FTDI (Pin T15)
    output wire [3:0]  led_status,  // Status LEDs: [0]=Calibrated, [1]=BeatPulse, [2]=Warmup, [3]=Error
    output wire        dbg_sync     // Oscilloscope trigger pulse on valid QRS detection
);
```

---

## 2. Module-by-Module Signal Interface Tables

### Module 1: UART Receiver (`uart_rx.v`)
| Port Name | Direction | Width | Clock Domain | Description |
| :--- | :---: | :---: | :---: | :--- |
| `clk` | Input | 1 | `clk_100m` | Master 100 MHz clock |
| `rst_n` | Input | 1 | Async / Sync | Active-low system reset |
| `rxd` | Input | 1 | Async | Serial input from host |
| `rx_data` | Output | 8 | `clk_100m` | Parallel deserialized byte |
| `rx_valid` | Output | 1 | `clk_100m` | 1-clock-cycle pulse when `rx_data` is valid |
| `framing_err`| Output | 1 | `clk_100m` | High if stop bit not detected (baud error) |

### Module 2: Packet Parser (`packet_parser.v`)
| Port Name | Direction | Width | Description |
| :--- | :---: | :---: | :--- |
| `rx_data` | Input | 8 | Input byte from UART receiver |
| `rx_valid` | Input | 1 | Input byte strobe |
| `sample_valid`| Output | 1 | Strobe asserting that a full 4-channel ECG sample was unpacked |
| `ch0..ch3` | Output | $4 \times 16$ | Signed 16-bit Q1.15 samples for channels $27, 26, 28, 25$ |
| `cal_valid` | Output | 1 | Strobe asserting valid calibration packet with correct CRC8 |
| `w0..w3` | Output | $4 \times 16$ | Signed 16-bit Q1.15 spatial weights |
| `crc_err` | Output | 1 | 1-clock-cycle pulse if packet CRC8 check failed |

### Module 4: Weight Storage & Slew Engine (`weight_storage.v`)
| Port Name | Direction | Width | Description |
| :--- | :---: | :---: | :--- |
| `cal_valid` | Input | 1 | New calibration packet arrival strobe |
| `w_in` | Input | $4 \times 16$ | New candidate weights |
| `sample_tick`| Input | 1 | 250 Hz sample arrival tick |
| `w_active` | Output | $4 \times 16$ | Current active weights feeding the beamformer |
| `is_slewing` | Output | 1 | High during the 64-sample linear cross-fade transition |

### Module 5: Spatial Beamformer (`spatial_beamformer.v`)
| Port Name | Direction | Width | Description |
| :--- | :---: | :---: | :--- |
| `sample_tick`| Input | 1 | 250 Hz computation trigger |
| `ch_in` | Input | $4 \times 16$ | 4-channel Signed 16-bit Q1.15 input samples |
| `w_in` | Input | $4 \times 16$ | 4-channel Signed 16-bit Q1.15 spatial weights |
| `proj_out` | Output | 24 | Signed 24-bit Q1.23 projected signal |
| `proj_valid` | Output | 1 | Valid strobe 3 clock cycles after `sample_tick` |

### Module 6: HP1 Baseline Remover (`hp1_filter.v`)
| Port Name | Direction | Width | Description |
| :--- | :---: | :---: | :--- |
| `proj_in` | Input | 24 | Signed 24-bit Q1.23 input |
| `proj_valid` | Input | 1 | Input strobe |
| `hp_out` | Output | 24 | Signed 24-bit Q1.23 highpass output |
| `hp_valid` | Output | 1 | Valid strobe 2 clock cycles after input |

### Module 7: LP40 Low-Pass Filter (`lp40_filter.v`)
| Port Name | Direction | Width | Description |
| :--- | :---: | :---: | :--- |
| `hp_in` | Input | 24 | Signed 24-bit Q1.23 input |
| `hp_valid` | Input | 1 | Input strobe |
| `fecg_out` | Output | 24 | Signed 24-bit Q1.23 clean FECG output |
| `lp_valid` | Output | 1 | Valid strobe 4 clock cycles after input |

### Module 8: Detector Bandpass Filter (`bp12_35_filter.v`)
| Port Name | Direction | Width | Description |
| :--- | :---: | :---: | :--- |
| `fecg_in` | Input | 24 | Signed 24-bit Q1.23 input |
| `lp_valid` | Input | 1 | Input strobe |
| `bp16_out` | Output | 16 | Signed 16-bit Q1.15 bandpass output (scaled >>> 8) |
| `bp_valid` | Output | 1 | Valid strobe 8 clock cycles after input |

### Module 11: Adaptive Threshold FSM (`threshold_fsm.v`)
| Port Name | Direction | Width | Description |
| :--- | :---: | :---: | :--- |
| `mwi_in` | Input | 36 | Unsigned 36-bit integrated energy |
| `mwi_valid` | Input | 1 | Input strobe |
| `cand_tick` | Output | 1 | 1-clock-cycle pulse when candidate peak exceeds threshold |
| `warmup_done`| Output | 1 | High when 512-sample warm-up phase has finished |

### Module 13: FHR Engine (`fhr_engine.v`)
| Port Name | Direction | Width | Description |
| :--- | :---: | :---: | :--- |
| `peak_strobe`| Input | 1 | Peak declared pulse from localizer |
| `peak_time` | Input | 18 | 18-bit R-peak sample timestamp |
| `fhr_x10` | Output | 12 | Instantaneous fetal heart rate in bpm x 10 ($500\text{ to }2500$) |
| `rr_samples` | Output | 9 | RR interval in sample periods ($60\text{ to }300$) |
| `beat_flag` | Output | 2 | 2-bit state classification tag (`00`=Real, `01`=Fused, `10`=Held, `11`=Warmup) |
| `fhr_valid` | Output | 1 | High when FHR stream is ready |
