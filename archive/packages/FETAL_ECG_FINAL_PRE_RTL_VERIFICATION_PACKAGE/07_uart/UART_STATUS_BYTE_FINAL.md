# Authoritative UART Status-Byte Bit Allocation Specification

**Document Version:** 3.0 (Pre-RTL Final Freeze)  
**Applies to:** Byte 6 of the 8-Byte QRS Event & FHR Telemetry Packet (`0xAA`)  

---

## 1. Master Bit Allocation Table

| Bit Position | Field Name | Type | Value | Meaning | Hardware Source Register |
| :---: | :--- | :---: | :---: | :--- | :--- |
| **Bit 0** | `CLASS[0]` | Unsigned | `0` or `1` | LSB of 2-bit Beat Classification | QRS Post-Processing Engine |
| **Bit 1** | `CLASS[1]` | Unsigned | `0` or `1` | MSB of 2-bit Beat Classification | QRS Post-Processing Engine |
| **Bit 2** | `CONFIDENCE` | Boolean | `1` | Confident spatial calibration ($R_1 \ge 0.15$, margin $\ge 0.20$) | Host Calibration Latch |
| | | | `0` | Low-confidence calibration / Retained prior weights | Host Calibration Latch |
| **Bit 3** | `SATURATION` | Boolean | `1` | Internal datapath saturation or ADC clipping asserted | Overflow Accounting OR-Gate |
| | | | `0` | Nominal dynamic range across all stages | Overflow Accounting OR-Gate |
| **Bit 4** | `RESERVED` | Constant | `0` | Reserved for future lead-off detection | Hardwired to Ground (`1'b0`) |
| **Bit 5** | `RESERVED` | Constant | `0` | Reserved for future electrode impedance alert | Hardwired to Ground (`1'b0`) |
| **Bit 6** | `RESERVED` | Constant | `0` | Reserved | Hardwired to Ground (`1'b0`) |
| **Bit 7** | `RESERVED` | Constant | `0` | Reserved | Hardwired to Ground (`1'b0`) |

---

## 2. Beat Classification Encoding (Bits 1:0)

| Bit 1 (`CLASS[1]`) | Bit 0 (`CLASS[0]`) | Hex Representation | State Name | Clinical & Engineering Description |
| :---: | :---: | :---: | :--- | :--- |
| `0` | `0` | `0x00` | **REAL_DETECTED** | Normal physiological fetal QRS detection ($RR \in [50, 300]\text{ samples}$). Verified by adaptive threshold. |
| `0` | `1` | `0x01` | **FUSED_BEAT** | Split-peak event ($RR < 50\text{ samples} = 200\text{ ms}$). Merged with previous detection to prevent false tachycardia trigger. |
| `1` | `0` | `0x02` | **HELD_FHR** | Physiological bradycardia dropout ($RR > 300\text{ samples} = 1.2\text{ s}$). Telemetry holds previous verified FHR. |
| `1` | `1` | `0x03` | **WARMUP** | System initialization / filter settling phase ($t < 512\text{ samples} \approx 2.05\text{ s}$). FHR is invalid. |

---

## 3. Discrepancy Resolution & Audit Alignment

In Phase 2, `UART_PROTOCOL_AUDIT.md` described Bit 3 as a "Refractory Lockout indicator" and Bits 7:4 as "hardware fault indicators", whereas `UART_PROTOCOL_SPEC_FINAL.md` and the implementation reserved Bits 7:3.

**Locked Pre-RTL Rule:**
1. Bits 1:0 represent the 2-bit beat classification.
2. Bit 2 represents the 1-bit Calibration Confidence flag.
3. Bit 3 is formally assigned as the **Stage Saturation & Clipping Alert** (asserted if any intermediate DSP accumulator or ADC register saturates).
4. Bits 7:4 are strictly **Reserved (`0000`)** and tied to logic `0`.
5. The encoder, decoder, specifications, and test suites are 100% unified to this bit definition.
