# Final UART Communication Protocol Specification

**Target Platform:** RealDigital Boolean Board (AMD/Xilinx Spartan-7 XC7S50-1CSGA324C)  
**Interface:** FTDI USB-UART Bridge (`FT2232H`)  
**Baud Rate:** 921,600 baud, 8 Data Bits, 1 Stop Bit, No Parity (8-N-1)  

---

## 1. Frame Architecture Overview

All multibyte integers are transmitted in **Big-Endian (Network Byte Order, MSB First)**.

### Packet Summary Table
| Packet Name | Header | Direction | Length | Payload Description | Integrity Check |
| :--- | :---: | :---: | :---: | :--- | :---: |
| **ECG Sample Frame** | `0xA5` | Host $\to$ FPGA | 10 Bytes | Sequence # + 4x 16-bit ADC samples | Rolling Counter |
| **Calibration Frame** | `0xC3` | Host $\to$ FPGA | 10 Bytes | 4x Signed 16-bit Q1.15 spatial weights | CRC8-CCITT |
| **Clean FECG Stream** | `0x5A` | FPGA $\to$ Host | 6 Bytes | Sequence # + Signed 24-bit clean sample + status | Status Bits |
| **QRS/FHR Telemetry** | `0xAA` | FPGA $\to$ Host | 8 Bytes | 24-bit Timestamp + 16-bit FHR + 8-bit Status | CRC8-CCITT |

---

## 2. Packet Definitions

### 2.1 Calibration Weights Packet (`0xC3` — Host $\to$ FPGA)
```
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7 | Byte 8 | Byte 9 |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xC3  |  W0_H  |  W0_L  |  W1_H  |  W1_L  |  W2_H  |  W2_L  |  W3_H  |  W3_L  |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
```
- `Byte 0`: Sync Header `0xC3`.
- `Bytes 1–8`: 4 Signed 16-bit Q1.15 weights ($w_0, w_1, w_2, w_3$), range $[-32,768, +32,767]$.
- `Byte 9`: CRC8-CCITT over Bytes 0 through 8.

### 2.2 QRS Event & FHR Telemetry Packet (`0xAA` — FPGA $\to$ Host)
```
+--------+--------+--------+--------+--------+--------+--------+--------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7 |
+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xAA  | Time_H | Time_M | Time_L | FHR_H  | FHR_L  | Status |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+
```
- `Byte 0`: Sync Header `0xAA`.
- `Bytes 1–3`: 24-bit unsigned sample timestamp $t_R$ (compensated for 18-sample group delay). Max range $16,777,215\text{ samples} \approx 18.6\text{ hours}$ continuous monitoring.
- `Bytes 4–5`: 16-bit unsigned FHR in units of $0.1\text{ bpm}$ (e.g. $1402 \implies 140.2\text{ bpm}$).
- `Byte 6`: Status Byte:
  - `bits 1:0`: Beat Classification:
    - `00`: REAL_DETECTED (Normal physiological QRS event).
    - `01`: FUSED_BEAT (Split-peak fused into single event).
    - `10`: HELD_FHR (Dropout / RR interval out of bounds; holding previous FHR).
    - `11`: WARMUP (Filter initialization / warmup period).
  - `bit 2`: Calibration Confidence (`1`: Confident, `0`: Low-Confidence / Retained).
  - `bits 7:3`: Reserved (`0`).
- `Byte 7`: CRC8-CCITT over Bytes 0 through 6.

---

## 3. CRC-8-CCITT Implementation

- **Polynomial:** $x^8 + x^2 + x + 1$ (`0x07`).
- **Initial Value:** `0x00`.
- **Reflect In / Out:** False / False.
- **Final XOR:** `0x00`.
- **Golden Test Vector:** `crc8_ccitt(b"123456789") == 0xF4`.
