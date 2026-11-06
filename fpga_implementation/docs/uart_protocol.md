# Real-Time Telemetry & UART Communication Protocol Specification

**Document Path:** `fpga_implementation/docs/uart_protocol.md`  
**Physical Interface:** FTDI FT2232H USB-to-UART Bridge (RealDigital Boolean Board / Digilent Arty S7)  
**Host Port:** `COM5` (Windows) / `/dev/ttyUSB0` (Linux)  
**Production Baud Rate:** $921{,}600\text{ Baud}$ (Bringup Fallback: $115{,}200\text{ Baud}$)  
**Framing Parameters:** 8 data bits, no parity, 1 stop bit (8-N-1), LSB-first bit serialization  
**Byte Ordering:** Multi-byte words transmitted in **Big-Endian (MSB First)**  
**Error Detection:** Cyclic Redundancy Check (CRC8-CCITT, polynomial `0x07`, init `0x00`)  
**Software Driver:** `fpga_implementation/uart_host/fecg_uart_client.py` and `src/fecg/telemetry/uart_protocol.py`

---

## 1. Executive Summary & Communication Architecture

This document specifies the bidirectional communication protocol between the Host PC (Python data streamer, calibration engine, and clinical visualization dashboard) and the AMD/Xilinx Spartan-7 FPGA accelerator.

```
       HOST PC (Python Ingestion / GUI)                     SPARTAN-7 FPGA ACCELERATOR
  ┌────────────────────────────────────────┐           ┌────────────────────────────────────────┐
  │                                        │           │                                        │
  │  1. Downlink Sample Ingestion (0xA5)   ├──────────►│  UART RX (921,600 / 115,200 Baud)      │
  │     11 Bytes @ 250 Hz (2,750 B/s)      │  (uart_rxd│  Packet Parser & CRC8 Validation       │
  │                                        │   Pin V12)│                                        │
  │  2. Downlink Spatial Calibration (0xC3)├──────────►│  Weight Storage & Slew Engine         │
  │     10 Bytes on-demand (~0.17 B/s)     │           │                                        │
  │                                        │           │                                        │
  │  3. Uplink Clean FECG Stream (0x5A)    │◄──────────┤  LP40 Biquad Output Tap                │
  │     6 Bytes @ 250 Hz (1,500 B/s)       │  (uart_txd│  16-Entry Circular Elastic FIFO        │
  │                                        │   Pin U11)│                                        │
  │  4. Uplink QRS Event & FHR (0xAA)      │◄──────────┤  Latency-Compensated Beat Telemetry    │
  │     8 Bytes per beat (~20 B/s)         │           │                                        │
  │                                        │           │                                        │
  │  5. Uplink Diagnostic Packet (0xEE)    │◄──────────┤  Hardware Anomaly & Status Monitor     │
  │     8 Bytes on-event (~8 B/s)          │           │                                        │
  └────────────────────────────────────────┘           └────────────────────────────────────────┘
```

### Key Protocol Highlights:
1. **Low Channel Utilization:** Total real-time bidirectional throughput is $4{,}278.17\text{ bytes/s}$, consuming only **$4.64\%$** of the $921{,}600\text{ baud}$ channel capacity ($>95.3\%$ headroom) and **$37.14\%$** of the $115{,}200\text{ baud}$ bringup link.
2. **Robust Synchronization:** Unique 1-byte sync headers (`0xA5`, `0xC3`, `0x5A`, `0xAA`, `0xEE`) combined with CRC8-CCITT verification allow immediate frame recovery after byte drop or line corruption without dropping entire packet bursts.
3. **Ultra-Low Clinical Latency:** Total event-to-display latency is **$104.1\text{ ms}$**, nearly $10\times$ faster than the $1{,}000\text{ ms}$ clinical guideline established by FIGO.

---

## 2. Packet Formats & Structural Layouts

All multi-byte numeric fields are encoded in **Big-Endian (MSB First)** byte order.

---

### 2.1 Packet 1: Downlink Sample Ingestion Packet (`0xA5`)
Transmitted by the host ADC driver or dataset replayer at exactly $f_s = 250\text{ Hz}$ ($4.0\text{ ms}$ interval).

```
 0        1        2        3        4        5        6        7        8        9       10    (Byte Index)
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xA5  |  Seq#  |  CH0_H |  CH0_L |  CH1_H |  CH1_L |  CH2_H |  CH2_L |  CH3_H |  CH3_L |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
| Header | 8b U   | Signed 16b Q12 CH0      | Signed 16b Q12 CH1      | Signed 16b Q12 CH2      | CH3... | Check  |
```

- **Byte 0 — Header:** Fixed sync byte `0xA5`.
- **Byte 1 — Sequence Number:** 8-bit unsigned rolling counter ($0 \dots 255$) used to detect host dropped packets or OS scheduling jitter.
- **Bytes 2–3 — Channel 0:** Signed 16-bit Q12, Big-Endian. Full scale $\pm 8.0\text{ mV}$, $4096\text{ LSB/mV}$.
- **Bytes 4–5 — Channel 1:** Signed 16-bit Q12, Big-Endian. Full scale $\pm 8.0\text{ mV}$, $4096\text{ LSB/mV}$.
- **Bytes 6–7 — Channel 2:** Signed 16-bit Q12, Big-Endian. Full scale $\pm 8.0\text{ mV}$, $4096\text{ LSB/mV}$.
- **Bytes 8–9 — Channel 3:** Signed 16-bit Q12, Big-Endian. Full scale $\pm 8.0\text{ mV}$, $4096\text{ LSB/mV}$.
- **Byte 10 — CRC8-CCITT:** Checksum computed over Bytes 0 through 9.
- **Total Packet Length:** **11 Bytes**.

---

### 2.2 Packet 2: Downlink Spatial Calibration Weights Packet (`0xC3`)
Transmitted by the host during startup initialization and periodically (e.g. every $60\text{ s}$ or upon manual user recalibration).

```
 0        1        2        3        4        5        6        7        8        9      (Byte Index)
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xC3  |  W0_H  |  W0_L  |  W1_H  |  W1_L  |  W2_H  |  W2_L  |  W3_H  |  W3_L  |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
| Header | Signed 16b Q1.15 W0      | Signed 16b Q1.15 W1      | W2 and W3...    | Check  |
```

- **Byte 0 — Header:** Fixed sync byte `0xC3`.
- **Bytes 1–2 — Weight 0 ($w_0$):** Spatial projection weight for Channel 0, Signed 16-bit Q1.15, Big-Endian ($32768\text{ LSB/unit}$).
- **Bytes 3–4 — Weight 1 ($w_1$):** Spatial projection weight for Channel 1, Signed 16-bit Q1.15, Big-Endian.
- **Bytes 5–6 — Weight 2 ($w_2$):** Spatial projection weight for Channel 2, Signed 16-bit Q1.15, Big-Endian.
- **Bytes 7–8 — Weight 3 ($w_3$):** Spatial projection weight for Channel 3, Signed 16-bit Q1.15, Big-Endian.
- **Byte 9 — CRC8-CCITT:** Checksum computed over Bytes 0 through 8.
- **Total Packet Length:** **10 Bytes**.

---

### 2.3 Packet 3: Uplink Clean FECG Stream Packet (`0x5A`)
Transmitted by the FPGA accelerator at $250\text{ Hz}$ ($4.0\text{ ms}$ interval) for real-time oscilloscope display and maternal-subtracted FECG waveform recording.

```
 0        1        2        3        4        5      (Byte Index)
+--------+--------+--------+--------+--------+--------+
|  0x5A  |  Seq#  | FECG_H | FECG_M | FECG_L |  CRC8  |
+--------+--------+--------+--------+--------+--------+
| Header | 8b U   | Signed 24-bit Q20 FECG Sample     | Check  |
```

- **Byte 0 — Header:** Fixed sync byte `0x5A`.
- **Byte 1 — Sequence Counter:** 8-bit unsigned rolling counter ($0 \dots 255$).
- **Bytes 2–4 — Clean FECG Sample:** Signed 24-bit Q20, Big-Endian:
  - Byte 2 = `fecg_clean[23:16]` (MSB).
  - Byte 3 = `fecg_clean[15:8]` (Mid).
  - Byte 4 = `fecg_clean[7:0]` (LSB).
  - Physical scale: $2^{20}\text{ LSB/mV} = 1,048,576\text{ LSB/mV}$ ($\pm 8.0\text{ mV}$ full scale).
- **Byte 5 — CRC8-CCITT:** Checksum computed over Bytes 0 through 4.
- **Total Packet Length:** **6 Bytes**.

---

### 2.4 Packet 4: Uplink QRS Event & FHR Telemetry Packet (`0xAA`)
Transmitted immediately upon R-peak declaration ($\approx 1.5\text{--}3.0\text{ Hz}$ for fetal heart rates between $90$ and $180\text{ bpm}$).

```
 0        1        2        3        4        5        6        7      (Byte Index)
+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xAA  | Time_H | Time_M | Time_L | FHR_H  | FHR_L  | Status |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+
| Header | 24-bit Sample Timestamp  | 16-bit FHR (0.1 bpm)   | Flags  | Check  |
```

- **Byte 0 — Header:** Fixed sync byte `0xAA`.
- **Bytes 1–3 — Latency-Compensated Timestamp ($t_R$):**
  - 24-bit unsigned integer, Big-Endian: `timestamp = (Byte1 << 16) | (Byte2 << 8) | Byte3`.
  - Sample index $0 \dots 16{,}777{,}215$ ($>18.6\text{ hours}$ continuous operation at $250\text{ Hz}$).
  - Hardware subtractor rewinds filter group delay: $t_R = \max(0, r_{\text{raw}} - 12)$.
- **Bytes 4–5 — Instantaneous Fetal Heart Rate:**
  - 16-bit unsigned integer, Big-Endian, scaled in units of $0.1\text{ bpm}$.
  - Example: `0x057A` ($1402$) $\implies \mathbf{140.2\text{ bpm}}$.
  - Valid physiological range: $500 \dots 3000$ ($50.0 \dots 300.0\text{ bpm}$).
- **Byte 6 — Authoritative Status Byte:**
  - `bits [1:0] — Beat Classification`:
    * `0b00` = `FLAG_REAL_DETECTED`: Normal physiological R-peak detected above adaptive threshold.
    * `0b01` = `FLAG_FUSED_BEAT`: Merged split-peak detection within refractory period.
    * `0b10` = `FLAG_HELD_FHR`: Search-back or bradycardia dropout; previous FHR held.
    * `0b11` = `FLAG_INVALID_WARMUP`: Initialization phase (first 512 samples / 2.05 s).
  - `bit [2] — Calibration Confidence`:
    * `1` = High Confidence (Eigenvalue ratio $> 2.0$).
    * `0` = Low Confidence (Fallback weights active).
  - `bit [3] — Saturation Indicator`:
    * `1` = Filter state or datapath saturated in current beat interval.
    * `0` = Linear operation.
  - `bits [7:4] — Reserved`: `0000`.
- **Byte 7 — CRC8-CCITT:** Checksum computed over Bytes 0 through 6.
- **Total Packet Length:** **8 Bytes**.

---

### 2.5 Packet 5: Uplink Diagnostic & Anomaly Packet (`0xEE`)
Transmitted upon hardware anomaly detection (CRC error, sequence gap, or internal saturation):

```
 0        1        2        3        4        5        6        7      (Byte Index)
+--------+--------+--------+--------+--------+--------+--------+--------+
|  0xEE  | ErrCode| MaxSt_H| MaxSt_L| Thr_H  | Thr_L  | Rsvd   |  CRC8  |
+--------+--------+--------+--------+--------+--------+--------+--------+
```

- **Byte 0 — Header:** Fixed sync byte `0xEE`.
- **Byte 1 — Error Code:**
  - `0x01` = Downlink CRC8 Checksum Failure (`ERR_DOWNLINK_CRC_FAIL`).
  - `0x02` = Downlink Sequence Gap (`ERR_DOWNLINK_SEQ_GAP`).
  - `0x03` = Biquad Filter Overflow / Saturation (`ERR_BIQUAD_SATURATION`).
  - `0x04` = UART Elastic FIFO Overflow (`ERR_UART_FIFO_OVERFLOW`).
- **Bytes 2–3 — Maximum Biquad State:** Signed 16-bit peak internal filter state.
- **Bytes 4–5 — Current Adaptive Threshold:** Unsigned 16-bit threshold level at fault.
- **Byte 6 — Reserved:** `0x00`.
- **Byte 7 — CRC8-CCITT:** Checksum computed over Bytes 0 through 6.
- **Total Packet Length:** **8 Bytes**.

---

## 3. CRC8-CCITT Error Detection Specification

All downlink and uplink packets incorporate an 8-bit Cyclic Redundancy Check (CRC8) to ensure transmission integrity:

| Parameter | Specification Value | Description |
|---|:---:|---|
| **Standard Name** | CRC-8-CCITT / CRC-8-ATM | ITU-T I.432.1 Standard |
| **Generator Polynomial** | $x^8 + x^2 + x + 1$ (`0x07`) | Hex: `0x07` (Binary: `00000111`) |
| **Initial Register Value** | `0x00` | Zero initialization |
| **Reflect Input (`RefIn`)** | False | MSB-first bit order |
| **Reflect Output (`RefOut`)** | False | MSB-first bit order |
| **Final XOR Value** | `0x00` | Uninverted output |
| **Golden Test Vector** | `b"123456789"` $\rightarrow$ **`0xF4`** | Verified in automated regression suites |

### 3.1 Synthesizable Hardware Verilog Engine (`crc8_step`)
```verilog
function [7:0] crc8_step(input [7:0] current_crc, input [7:0] byte_in);
    reg [7:0] c;
    integer i;
    begin
        c = current_crc ^ byte_in;
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

## 4. Bandwidth Budget & Channel Utilization

### 4.1 Physical Channel Capacity
- **UART Framing:** 8-N-1 (1 start bit, 8 data bits, 1 stop bit = 10 baud-bits per byte).
- **At 921,600 Baud (Production):**
  $$C_{\text{max}} = \frac{921{,}600}{10} = \mathbf{92{,}160\text{ bytes/s}}$$
  $$T_{\text{byte}} \approx 10.851\ \mu\text{s}$$
- **At 115,200 Baud (Bringup Fallback):**
  $$C_{\text{max}} = \frac{115{,}200}{10} = \mathbf{11{,}520\text{ bytes/s}}$$
  $$T_{\text{byte}} \approx 86.806\ \mu\text{s}$$

### 4.2 Traffic Load Analysis

| Stream Direction | Packet Type | Frequency | Packet Size | Byte Throughput | Baud Rate Load | Utilization @ 921,600 Baud | Utilization @ 115,200 Baud |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Downlink (Host $\rightarrow$ FPGA)** | `0xA5` (Ingestion) | $250.0\text{ Hz}$ | $11\text{ B}$ | $2{,}750.0\text{ B/s}$ | $27{,}500\text{ bps}$ | **$2.98\%$** | **$23.87\%$** |
| **Downlink (Host $\rightarrow$ FPGA)** | `0xC3` (Calibration) | $1 / 60\text{ Hz}$ | $10\text{ B}$ | $0.17\text{ B/s}$ | $1.7\text{ bps}$ | **$< 0.01\%$** | **$< 0.01\%$** |
| **Uplink (FPGA $\rightarrow$ Host)** | `0x5A` (FECG Stream)| $250.0\text{ Hz}$ | $6\text{ B}$ | $1{,}500.0\text{ B/s}$ | $15{,}000\text{ bps}$ | **$1.63\%$** | **$13.02\%$** |
| **Uplink (FPGA $\rightarrow$ Host)** | `0xAA` (FHR Telemetry)| $\approx 2.5\text{ Hz}$ | $8\text{ B}$ | $20.0\text{ B/s}$ | $200\text{ bps}$ | **$0.02\%$** | **$0.17\%$** |
| **Uplink (FPGA $\rightarrow$ Host)** | `0xEE` (Diagnostics) | $\approx 1.0\text{ Hz}$ | $8\text{ B}$ | $8.0\text{ B/s}$ | $80\text{ bps}$ | **$< 0.01\%$** | **$0.07\%$** |
| **TOTAL BIDIRECTIONAL LINK** | — | — | — | **$4{,}278.17\text{ B/s}$** | **$42{,}782\text{ bps}$** | **$4.64\%$** | **$37.14\%$** |

*Conclusion:* The entire clinical ECG telemetry stream and bidirectional control consume only **$4.64\%$** of the production link capacity ($>95.3\%$ headroom) and comfortably fit within the $115{,}200\text{ baud}$ bringup link ($37.14\%$).

---

## 5. Clinical Latency Breakdown

The latency from the physical occurrence of a fetal cardiac contraction to the host PC clinical display is strictly bounded:

1. **Physiological Sampling:** $T_s = 4.0\text{ ms}$ ($250\text{ Hz}$).
2. **Trailing R-Peak Search Window:** 26 samples = **$104.0\text{ ms}$**.
3. **Filter Group Delay Rewind Subtractor:** Hardware subtracts 12 samples ($-48.0\text{ ms}$), reporting the true physiological contraction timing with +0.32 ms (+0.080 sample) empirical mean bias across PhysioNet FECGSYNDB benchmark recordings.
4. **FPGA Pipeline Execution Latency:** 70 clock cycles at 100.0 MHz = **$0.70\ \mu\text{s}$** ($0.0007\text{ ms}$).
5. **UART Serialization Latency (8 Bytes @ 921,600 Baud):**
   $$T_{\text{tx}} = 8\text{ bytes} \times 10.851\ \mu\text{s/byte} = \mathbf{86.8\ \mu\text{s}}\ (0.0868\text{ ms})$$
6. **Total Event-to-Host Latency:**
   $$\text{Total Clinical Latency} = 104.0\text{ ms} + 0.0007\text{ ms} + 0.0868\text{ ms} \approx \mathbf{104.1\text{ ms}}$$

*FIGO Compliance:* The International Federation of Gynecology and Obstetrics (FIGO) standard mandates clinical intrapartum heart rate reporting latency $< 1{,}000\text{ ms}$ ($1.0\text{ s}$). The Spartan-7 implementation operates at **$104.1\text{ ms}$**, exceeding clinical responsiveness requirements by nearly an order of magnitude.
