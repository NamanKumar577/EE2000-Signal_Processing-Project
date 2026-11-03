# Final UART Communication Protocol Specification

**Target Platform:** RealDigital Boolean Board (AMD/Xilinx Spartan-7 XC7S50-1CSGA324C)  
**Interface:** FTDI USB-UART Bridge (`FT2232H`)  
**Baud Rate:** 921,600 baud, 8 Data Bits, 1 Stop Bit, No Parity (8-N-1)  
**Byte Transmission Order:** Big-Endian (Network Byte Order, MSB First)  

---

## 1. Frame Architecture Overview

All packets utilize single-byte synchronization headers and strict CRC8-CCITT integrity validation:

| Packet Name | Header | Direction | Length | Payload Description | Integrity Mechanism |
| :--- | :---: | :---: | :---: | :--- | :---: |
| **Ingestion Sample Frame** | `0xA5` | Host $\to$ FPGA | 10 Bytes | 8-bit seq + 4x signed 16-bit ADC samples | CRC8-CCITT |
| **Calibration Frame** | `0xC3` | Host $\to$ FPGA | 10 Bytes | 4x Signed 16-bit Q1.15 spatial weights | CRC8-CCITT |
| **Clean FECG Stream** | `0x5A` | FPGA $\to$ Host | 6 Bytes | 8-bit seq + Signed 24-bit clean sample | CRC8-CCITT |
| **QRS/FHR Telemetry** | `0xAA` | FPGA $\to$ Host | 8 Bytes | 24-bit Timestamp + 16-bit FHR + Status Byte | CRC8-CCITT |

---

## 2. Complete Packet Definitions

### 2.1 Calibration Weights Packet (`0xC3` — Host to FPGA, 10 Bytes)
```
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7 | Byte 8 | Byte 9 |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xC3  |  W0_H  |  W0_L  |  W1_H  |  W1_L  |  W2_H  |  W2_L  |  W3_H  |  W3_L  |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
```
- `Byte 0`: Sync Header `0xC3`.
- `Bytes 1–8`: 4 Signed 16-bit Q1.15 weights ($w_0, w_1, w_2, w_3$) in range $[-32,768, +32,767]$.
- `Byte 9`: CRC8-CCITT over Bytes 0 through 8.

### 2.2 QRS Event & FHR Telemetry Packet (`0xAA` — FPGA to Host, 8 Bytes)
```
+--------+--------+--------+--------+--------+--------+--------+--------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7 |
+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xAA  | Time_H | Time_M | Time_L | FHR_H  | FHR_L  | Status |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+
```
- `Byte 0`: Sync Header `0xAA`.
- `Bytes 1–3`: 24-bit unsigned sample timestamp $t_R$ (compensated for 18-sample group delay). Max range $16,777,215\text{ samples} \approx 18.6\text{ hours}$ continuous monitoring.
- `Bytes 4–5`: 16-bit unsigned FHR in units of $0.1\text{ bpm}$ ($500\dots 3,000$ for $50.0\dots 300.0\text{ bpm}$).
- `Byte 6`: Status Byte (bits 1:0 = Class, bit 2 = Conf, bit 3 = Sat, bits 7:4 = 0).
- `Byte 7`: CRC8-CCITT over Bytes 0 through 6.

### 2.3 Streaming Clean FECG Waveform Packet (`0x5A` — FPGA to Host, 6 Bytes)
```
+--------+--------+--------+--------+--------+--------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 |
+--------+--------+--------+--------+--------+--------+
|  0x5A  | Sequence | FECG_H | FECG_M | FECG_L |  CRC8  |
+--------+--------+--------+--------+--------+--------+
```
- `Byte 0`: Sync Header `0x5A`.
- `Byte 1`: 8-bit rolling sequence counter ($0\dots 255$).
- `Bytes 2–4`: Signed 24-bit clean filtered biopotential sample (scale $= 2^{20}\text{ LSB/mV}$).
- `Byte 5`: CRC8-CCITT over Bytes 0 through 4.

---

## 3. CRC-8-CCITT Algorithm Definition

- **Generator Polynomial:** $x^8 + x^2 + x + 1$ (`0x07`).
- **Initial Register Value:** `0x00`.
- **Reflection:** None (Reflect Input = False, Reflect Output = False).
- **Final XOR:** `0x00`.
- **Golden International Test Vector:** `crc8_ccitt(b"123456789") == 0xF4`.
