# Calibration Cold-Start and Recalibration Specification

## 1. Cold-Start Initialization Policy

When the FPGA boots or resets, no valid historical spatial weights exist in memory:
1. **Initial Power-On State:**
   - Active weights are initialized to unity passthrough on abdominal Channel 0: $\mathbf{w}[0] = [32767, 0, 0, 0]$.
   - Telemetry status asserts `FLAG_INVALID_WARMUP` (`11`) with Confidence Bit = `0` (`Uncertain`).
   - Clean FECG output stream is held at `0` ($0.0\text{ mV}$) to prevent host display of raw unseparated noise.
   - FHR output stream is held at `0` ($0.0\text{ bpm}$).
2. **First Calibration Window Arrival:**
   - The host collects the first 4.0-second ($1,000\text{ sample}$) buffer.
   - If confidence gate passes ($R_1 \ge 0.15$, margin $\ge 0.20$): host transmits 10-byte calibration packet (`0xC3`). FPGA latches weights and transitions to `FLAG_REAL_DETECTED` (`00`) with Confidence Bit = `1`.
   - If confidence gate fails: host asserts `0x00: UNCERTAIN` telemetry packet and immediately begins collecting the next 4.0-second window. The system **never falls back to an unverified fixed PC3**. Output remains in warmup state until a confident calibration is confirmed.

---

## 2. Continuous Recalibration Policy (Consecutive Windows)

In long-duration intrapartum monitoring, fetal and maternal movement rotate the cardiac axes.
1. **Consecutive Window Partitioning:**
   - The host maintains a running biopotential buffer and re-evaluates spatial covariance every $30.0\text{ seconds}$.
   - Calibration is evaluated strictly on the **most recent consecutive window of the current continuous recording**.
   - Under no circumstances are weights retained or borrowed from independent historical recordings.
2. **Update Decision Rule:**
   - **Confident Update:** If new window satisfies $R_1 \ge 0.15$ and margin $\ge 0.20$, new weights are transmitted to the FPGA. The FPGA activates the 64-sample linear crossfade slew engine to seamlessly blend weights over $256\text{ ms}$.
   - **Uncertain Hold:** If new window exhibits low confidence (e.g. maternal contraction or noise burst), the host **retains the current active weights from the same recording**. Output telemetry remains fully active, asserting Confidence Bit = `0` to inform clinicians of lower confidence.
