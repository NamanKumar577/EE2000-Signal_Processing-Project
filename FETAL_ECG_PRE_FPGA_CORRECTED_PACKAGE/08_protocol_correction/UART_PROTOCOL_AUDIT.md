# UART Communication & Hardware Telemetry Protocol Audit

## 1. Executive Summary & Protocol Inconsistencies Corrected

An independent technical audit of `UART_PROTOCOL_SPEC.md` and `CALIBRATION_PROTOCOL_SPEC.md` from the previous package identified three critical protocol inconsistencies that would have caused FPGA/Host communication failures:

### Inconsistency 1: Impossible Bit-Packing in FHR Telemetry Packet
- **Original Claim:** In the 8-byte QRS/FHR packet (`0xAA`), `Byte 6` was documented as:
  - `bits 1:0`: Beat classification flags (`00: Real`, `01: Fused`, `10: Held`, `11: Warmup`).
  - `bits 7:2` (6 bits): *"RR interval in sample periods (60 to 300)"*.
- **Root Cause & Mathematical Impossibility:**
  A 6-bit unsigned integer can represent values from $0$ to $63$ ($2^6 - 1 = 63$).
  The RR interval range of $50\dots 300\text{ samples}$ requires at least **9 bits** ($\lceil \log_2(300) \rceil = 9$). Fitting $300$ into 6 bits is a mathematical impossibility and would have caused arithmetic truncation and corrupted telemetry.
- **Correction Applied:**
  `Byte 6` is re-architected as a clean Status & Diagnostics field:
  - `bits 1:0`: 2-bit beat classification (`00: Real`, `01: Fused`, `10: Held`, `11: Warmup`).
  - `bit 2`: 1-bit Calibration Confidence flag (`1: Confident`, `0: Uncertain / Retained`).
  - `bit 3`: 1-bit Refractory Lockout indicator.
  - `bits 7:4`: Reserved for hardware fault indicators (lead-off, clipping).
  FHR is transmitted directly in `Bytes 4–5` as a 16-bit integer in units of $0.1\text{ bpm}$ ($500\text{ to }3000$ for $50.0\text{ to }300.0\text{ bpm}$), which completely eliminates any need for host RR conversion.

---

### Inconsistency 2: Calibration Packet Sync Header Discrepancy
- **Original Claim:** The calibration sequence diagram showed a 10-byte packet with header `0xC3`, while text in another section mentioned a 2-byte sync word (`0xAA, 0x55`).
- **Correction Applied:**
  Locked to the standardized **10-Byte Calibration Packet**:
  - `Byte 0`: Sync Header `0xC3`.
  - `Bytes 1–8`: 4 Signed 16-bit Q1.15 spatial weights ($w_0, w_1, w_2, w_3$) in **Big-Endian (MSB First)** format.
  - `Byte 9`: CRC8-CCITT checksum over Bytes 0 through 8.

---

### Inconsistency 3: CRC8-CCITT Polynomial and Test Vector Definition
- **Original Claim:** Specified polynomial $0x07$, but omitted reflection and XOR out test vectors.
- **Correction Applied:**
  Formally locked and verified against international standard test vector:
  - Polynomial: $x^8 + x^2 + x + 1$ (`0x07`).
  - Initial Value: `0x00`.
  - Reflect Input: False.
  - Reflect Output: False.
  - Final XOR: `0x00`.
  - Test Vector Verification: String `b"123456789"` produces exact CRC `0xF4`. Verified in automated regression test.

---

## 2. Real-Time Link Budget and Latency Breakdown

At $921,600\text{ baud}$ (8-N-1):
- Byte transfer time: $10\text{ bits} / 921,600\text{ baud} = 10.85\ \mu\text{s}$.
- Maximum link capacity: $92,160\text{ bytes/second}$.

### Detailed Bandwidth Consumption Table
| Packet Type | Direction | Rate | Packet Size | Data Rate | Channel Utilization (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **ECG Sample Ingestion (`0xA5`)** | Host $\to$ FPGA | 250 Hz | 10 Bytes | 2,500 B/s | **2.71%** |
| **Calibration Weights (`0xC3`)** | Host $\to$ FPGA | Once / 60s | 10 Bytes | 0.17 B/s | **0.00%** |
| **Streaming FECG Waveform (`0x5A`)** | FPGA $\to$ Host | 250 Hz | 6 Bytes | 1,500 B/s | **1.63%** |
| **QRS Event & FHR Telemetry (`0xAA`)** | FPGA $\to$ Host | ~2.5 Hz | 8 Bytes | 20.0 B/s | **0.02%** |
| **TOTAL LINK UTILIZATION** | Bidirectional | Real-Time | - | **4,020.17 B/s** | **4.36%** |

### Latency Budget Hierarchy
1. **Algorithmic Detection Latency:**
   - Filter Group Delay: **$18\text{ samples}$** ($72.0\text{ ms}$ @ $250\text{ Hz}$).
   - MWI Window Delay: $W/2 = 30/2 = **15\text{ samples}$** ($60.0\text{ ms}$).
   - Trailing Local Peak Window: **$26\text{ samples}$** ($104.0\text{ ms}$).
   - Latency Compensation Subtractor: Automatically rewinds $-18\text{ samples}$ to align detected peak timestamp with true physical R-wave.
2. **FPGA Pipelined Datapath Latency:**
   - Total synchronous processing cycles: **55 clock cycles** at $100\text{ MHz} = \mathbf{550\text{ ns}}$ ($0.00055\text{ ms}$).
3. **UART Serialization Latency:**
   - 8-byte telemetry frame transmission: $8 \times 10.85\ \mu\text{s} = \mathbf{86.8\ \mu\text{s}}$ ($0.0868\text{ ms}$).
4. **Total Clinical Event-to-Display Latency:**
   - $104.0\text{ ms} + 0.00055\text{ ms} + 0.0868\text{ ms} \approx \mathbf{104.1\text{ ms}}$.
   - **FIGO Compliance:** Well below the maximum allowable $1,000\text{ ms}$ ($1.0\text{ s}$) FIGO intrapartum clinical guideline.
