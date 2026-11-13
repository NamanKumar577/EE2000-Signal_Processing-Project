# Standalone UART Protocol & Timing Specification

**Project:** Spartan-7 XC7S50 UART Bringup  
**Default Configuration:** 115,200 baud, 8 data bits, no parity, 1 stop bit (8-N-1)  
**Supported Baud Rates:** 115,200 / 230,400 / 460,800 / 921,600 bps  

---

## 1. Frame Architecture (8-N-1)

Each transmitted and received symbol follows the universal asynchronous framing format:

```
Idle (1'b1) ──┐      ┌───┬───┬───┬───┬───┬───┬───┬───┐      ┌── Idle (1'b1)
              │START │D0 │D1 │D2 │D3 │D4 │D5 │D6 │D7 │ STOP │
              └──0───┴───┴───┴───┴───┴───┴───┴───┴───┴──1───┘
              |<--- 1 bit --->|                       |< 1 bit >|
```

- **Idle Line:** `1'b1` (Mark state).
- **Start Bit:** `1'b0` (Space state, duration = 1 baud period).
- **Data Bits:** 8 bits, transmitted **LSB first** ($D_0 \to D_7$).
- **Parity:** None.
- **Stop Bit:** `1'b1` (Mark state, duration $\ge 1$ baud period).
- **Total Frame Duration:** 10 baud periods per byte.

---

## 2. Baud Rate Generation & Error Analysis

The system clock frequency is $f_{\text{clk}} = 100.000\,\text{MHz}$ ($T_{\text{clk}} = 10.0\,\text{ns}$).
The integer divider value is calculated in RTL as:

$$\text{CLKS\_PER\_BIT} = \left\lfloor \frac{f_{\text{clk}} + \frac{\text{Baud}}{2}}{\text{Baud}} \right\rfloor$$

| Baud Rate (bps) | Exact Ideal Cycles | Synthesized Integer Divider | Actual Baud Rate | Timing Error (%) | Standard Margin Tolerance |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **115,200** | $868.055$ | **868** | $115{,}207.4$ | **$+0.0064\%$** | $<\pm 2.5\%$ (Excellent) |
| **230,400** | $434.028$ | **434** | $230{,}414.7$ | **$+0.0064\%$** | $<\pm 2.5\%$ (Excellent) |
| **460,800** | $217.014$ | **217** | $460{,}829.5$ | **$+0.0064\%$** | $<\pm 2.5\%$ (Excellent) |
| **921,600** | $108.507$ | **109** | $917{,}431.2$ | **$-0.452\%$** | $<\pm 2.5\%$ (Excellent) |

*Conclusion:* Across all candidate baud rates, the timing deviation on a 100 MHz clock is well under 0.5%, guaranteeing zero sampling drift over the 10-bit frame.

---

## 3. Receiver Architecture & Noise Rejection

### 3.1 Metastability Protection
The asynchronous serial line (`uart_rxd`) enters a 2-stage D-flip-flop synchronizer clocked by `clk` before reaching any FSM logic. This prevents metastability from propagating into the state registers.

### 3.2 False Start-Bit Glitch Rejection
When a falling edge (`1 \to 0`) is detected in `STATE_IDLE`, the receiver does not immediately assume a valid byte. Instead:
1. It waits for the **mid-bit point** ($\text{HALF\_BIT} = \text{CLKS\_PER\_BIT} / 2$).
2. It re-samples the synchronized RX line.
3. If the line is still `0`, it validates the start bit and advances to `STATE_DATA`.
4. If the line has returned to `1` (indicating a noise spike or transient glitch $< \text{HALF\_BIT}$), the state machine rejects the event and immediately resets to `STATE_IDLE` with zero false triggers.

### 3.3 Mid-Bit Data Sampling
All 8 data bits and the stop bit are sampled precisely at the center of each bit window ($T = \text{CLKS\_PER\_BIT}$), ensuring maximum noise margin against slew rate asymmetry and jitter.

### 3.4 Framing Error Detection
At the stop bit sampling point, if the RX line is `0` instead of `1`, a stop-bit violation has occurred. The receiver asserts `rx_frame_err` for 1 clock cycle and latches the diagnostic LED flag (`led[2]`).

---

## 4. Elastic Buffering & Echo Dataflow

In `uart_top.v`, incoming validated bytes are queued into a 16-entry circular FIFO:
- Eliminates dropped bytes when host sends burst streams (e.g. continuous strings) with minimal or zero inter-byte dead time.
- Simultaneous write and read are arbitrated hazard-free.
- If the host sends more than 16 bytes while transmission is blocked, `led[3]` latches an overflow warning.

---

## 5. Integration Roadmap with Fetal ECG System

This standalone 8-N-1 transceiver forms the physical link layer (`OSI Layer 1/2`) for the full project. Once verified on hardware:
1. The 10-byte Ingestion Packet (`0xA5` sync header, 4x 16-bit ADC leads, CRC-8-CCITT) will decode directly on top of `uart_rx`.
2. The 10-byte Calibration Packet (`0xC3` sync header, 4x 16-bit Q1.15 weights, CRC-8-CCITT) will update the spatial beamformer register bank.
3. The 8-byte QRS/FHR Telemetry Packet (`0xAA`) and 6-byte Clean FECG Stream Packet (`0x5A`) will serialize through `uart_tx`.
