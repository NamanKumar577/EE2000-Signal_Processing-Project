# Final FHR & RR Range Numerical Specification

## 1. Master Parameter Specification Table

| Parameter | Value in Samples | Value in Time (ms) | Value in Heart Rate (bpm) | Hardware Representation | Register / Width |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Sampling Rate ($f_s$)** | - | $4.0\text{ ms}$ | - | Internal clock tick | 1-bit strobe @ 250 Hz |
| **Detector Refractory** | $50\text{ samples}$ | $200.0\text{ ms}$ | $300.0\text{ bpm}$ (max trigger) | Down-counter | 6-bit unsigned (`[5:0]`) |
| **Fusion Threshold** | $< 50\text{ samples}$ | $< 200.0\text{ ms}$ | $> 300.0\text{ bpm}$ (split peak) | Comparator | 9-bit unsigned (`[8:0]`) |
| **Valid RR Min** | $50\text{ samples}$ | $200.0\text{ ms}$ | $300.0\text{ bpm}$ | Lower bound | 9-bit unsigned (`[8:0]`) |
| **Valid RR Max** | $300\text{ samples}$ | $1,200.0\text{ ms}$ | $50.0\text{ bpm}$ | Upper bound | 9-bit unsigned (`[8:0]`) |
| **LUT Base Index** | Offset $= 50$ | - | - | Address offset: `rr - 50` | 8-bit unsigned (`[7:0]`) |
| **LUT Table Size** | 251 words | - | $50.0\text{ to }300.0\text{ bpm}$ | ROM (12-bit width) | $256 \times 12\text{ bit}$ |
| **Telemetry FHR Output**| - | - | $0.0\text{ to }300.0\text{ bpm}$ | Q8.4 or $0.1\text{ bpm}$ integer | 12-bit unsigned (`[11:0]`) |
| **Telemetry State Flags**| - | - | - | 2-bit classification | `[1:0]` (`00: Real`, `01: Fused`, `10: Held`, `11: Warmup`) |

---

## 2. Boundary Verification Test Cases

| Test Case | RR Input (samples) | Expected Status | Telemetry Flag | Expected FHR Output |
| :--- | :---: | :--- | :---: | :---: |
| **Severe Bradycardia Bound** | 300 | Valid (Physiological lower bound) | `00: REAL` | $50.0\text{ bpm}$ ($500$) |
| **Severe Bradycardia Exceeded**| 301 | Invalid (Bradycardia dropout) | `10: HELD` | Previous valid FHR |
| **Normal Heart Rate** | 107 | Valid (Normal baseline) | `00: REAL` | $140.2\text{ bpm}$ ($1402$) |
| **Severe Tachycardia** | 60 | Valid (High fever / distress) | `00: REAL` | $250.0\text{ bpm}$ ($2500$) |
| **Extreme Tachycardia Bound** | 50 | Valid (Physiological upper bound) | `00: REAL` | $300.0\text{ bpm}$ ($3000$) |
| **Split Beat / Double Peak** | 49 | Fused into previous beat | `01: FUSED` | Recomputed / Held |
