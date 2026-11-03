# UART Communication and Telemetry Protocol Specification

**Document ID:** `validation/pre_fpga/07_fpga_specification/UART_PROTOCOL_SPEC.md`  
**Physical Layer:** RS-232 / UART over FTDI USB-UART Bridge  
**Baud Rate:** $921,600\text{ baud}$, 8 Data Bits, No Parity, 1 Stop Bit (8-N-1)  
**Byte Transmission Time:** $10.85\ \mu\text{s}$ per byte ($10\text{ bit periods}$)  
**Total Link Capacity:** $92,160\text{ bytes/sec}$  

---

## 1. Bandwidth Utilization & Margin Analysis

At a sampling frequency of $f_s = 250\text{ Hz}$ ($T_s = 4.0\text{ ms}$):

| Data Stream Direction | Packet Type | Frequency | Packet Size | Data Rate | Baud Capacity | Utilization (%) | Headroom (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Host $\rightarrow$ FPGA (Downlink)**| ECG Sample Packet | $250\text{ Hz}$ | $10\text{ bytes}$ | $2,500\text{ B/s}$ | $92,160\text{ B/s}$ | **$2.71\%$** | **$97.29\%$** |
| **Host $\rightarrow$ FPGA (Downlink)**| Calibration Weights | Once / $60\text{ s}$| $10\text{ bytes}$ | $0.17\text{ B/s}$ | $92,160\text{ B/s}$ | **$0.00\%$** | **$100.00\%$** |
| **FPGA $\rightarrow$ Host (Uplink)** | Clean FECG Telemetry | $250\text{ Hz}$ | $6\text{ bytes}$ | $1,500\text{ B/s}$ | $92,160\text{ B/s}$ | **$1.63\%$** | **$98.37\%$** |
| **FPGA $\rightarrow$ Host (Uplink)** | QRS Event Packet | $\approx 2.5\text{ Hz}$ | $8\text{ bytes}$ | $20.0\text{ B/s}$ | $92,160\text{ B/s}$ | **$0.02\%$** | **$99.98\%$** |
| **FPGA $\rightarrow$ Host (Uplink)** | Status & Diagnostics | $1.0\text{ Hz}$ | $8\text{ bytes}$ | $8.0\text{ B/s}$ | $92,160\text{ B/s}$ | **$0.01\%$** | **$99.99\%$** |
| **TOTAL BIDIRECTIONAL LINK** | **All Streams Combined** | **Real-Time** | **N/A** | **$4,028.17\text{ B/s}$** | **$92,160\text{ B/s}$** | **$4.37\%$** | **$95.63\%$** |

**Margin Verdict:** The communication link operates at **$<4.4\%$ of total channel capacity**, leaving $>95.6\%$ bandwidth headroom for host command exchanges and visual oscilloscope dumps.

---

## 2. Downlink Packet Definitions (Host to FPGA)

All multibyte integers are transmitted in **Big-Endian (MSB First)** format.

### 2.1 ECG Sample Ingestion Packet (`0xA5`)
Transmitted by host ADC driver at exactly $250\text{ Hz}$:
```
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7 | Byte 8 | Byte 9 |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xA5  |  Seq#  |  CH27_H|  CH27_L|  CH26_H|  CH26_L|  CH28_H|  CH28_L|  CH25_H|  CH25_L|
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
```
- `Byte 0`: Sync Header `0xA5`.
- `Byte 1`: 8-bit rolling sequence number ($0\dots 255$) to detect dropped samples.
- `Bytes 2–9`: 4 channels of Signed 16-bit Q1.15 samples (range $[-32768, +32767]$ representing $\pm 5.0\text{ mV}$).

### 2.2 Calibration Weights Packet (`0xC3`)
Transmitted by host calibration engine at startup and after 60-second recalibration:
```
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7 | Byte 8 | Byte 9 |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xC3  |  W0_H  |  W0_L  |  W1_H  |  W1_L  |  W2_H  |  W2_L  |  W3_H  |  W3_L  |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
```
- `Byte 0`: Sync Header `0xC3`.
- `Bytes 1–8`: 4 Signed 16-bit Q1.15 weights ($w_0, w_1, w_2, w_3$).
- `Byte 9`: CRC8-CCITT checksum over Bytes 0 through 8.

---

## 3. Uplink Packet Definitions (FPGA to Host)

### 3.1 Streaming FECG Waveform Packet (`0x5A`)
Transmitted every sample tick ($250\text{ Hz}$) for real-time oscilloscope display:
```
+--------+--------+--------+--------+--------+--------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 |
+--------+--------+--------+--------+--------+--------+
|  0x5A  |  Seq#  | FECG_23| FECG_15| FECG_7 | Status |
+--------+--------+--------+--------+--------+--------+
```
- `Byte 0`: Sync Header `0x5A`.
- `Byte 1`: Rolling sample sequence index ($0\dots 255$).
- `Bytes 2–4`: Signed 24-bit Q1.23 clean FECG biopotential sample.
- `Byte 5`: Status byte (`bit 0`=WarmupDone, `bit 1`=Calibrated, `bit 2`=SlewingWeights).

### 3.2 QRS Event & FHR Telemetry Packet (`0xAA`)
Transmitted immediately upon R-peak declaration ($\approx 1.5\text{ to }3.0\text{ Hz}$):
```
+--------+--------+--------+--------+--------+--------+--------+--------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7 |
+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xAA  | Time_H | Time_M | Time_L | FHR_H  | FHR_L  | Flags  |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+
```
- `Byte 0`: Sync Header `0xAA`.
- `Bytes 1–3`: 18-bit R-peak sample timestamp $t_R$ (compensated for filter delay).
- `Bytes 4–5`: Unsigned 12-bit instantaneous FHR in units of $\text{bpm} \times 10$ ($1402 = 140.2\text{ bpm}$).
- `Byte 6`: Telemetry status flag:
  - `bits 1:0`: Beat classification (`00`=Real, `01`=Fused, `10`=Held, `11`=Invalid).
  - `bits 7:2`: RR interval in sample periods ($60\dots 300$).
- `Byte 7`: CRC8 checksum over Bytes 0 through 6.

### 3.3 Diagnostic / Error Packet (`0xEE`)
Transmitted upon anomaly detection:
```
+--------+--------+--------+--------+--------+--------+--------+--------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7 |
+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xEE  | ErrCode| MaxSt_H| MaxSt_L| Thr_H  | Thr_L  | Resrvd |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+
```
- Error Codes: `0x01`=CRC Failure, `0x02`=Sequence Gap, `0x03`=Biquad Saturation, `0x04`=Lead Detached.

---

## 4. CRC8 Checksum Specification

To ensure error-free transmission across the serial link, all packets implement the standard **CRC-8-CCITT** algorithm:
- **Generator Polynomial:** $x^8 + x^2 + x + 1$ (`0x07`).
- **Initial Value (`Init`):** `0x00`.
- **Reflect Input (`RefIn`):** False (MSB first).
- **Reflect Output (`RefOut`):** False.
- **XOR Output (`XorOut`):** `0x00`.
- **Hardware Verilog Generator:**
  ```verilog
  function [7:0] crc8_step(input [7:0] crc, input [7:0] data);
      reg [7:0] c;
      integer i;
      begin
          c = crc ^ data;
          for (i = 0; i < 8; i = i + 1) begin
              if (c[7])
                  c = (c << 1) ^ 8'h07;
              else
                  c = c << 1;
          end
          crc8_step = c;
      end
  endfunction
  ```

---

## 5. Resynchronization and Error Recovery Protocol

1. **Header Hunting:** If a packet length mismatch or CRC failure occurs, the FPGA packet parser immediately drops the packet and enters `HEADER_HUNT` state, scanning incoming bytes for valid headers (`0xA5`, `0xC3`).
2. **Missing Sample Concealment:** If a sequence number gap is detected in the ECG sample stream ($\Delta \text{Seq} > 1$), the FPGA holds the previous sample value for up to 2 samples before asserting a `LEAD_FAULT` status flag to prevent filter impulse shock.
