# Final Spatial Calibration Protocol Specification

## 1. System Operational Division

1. **Host Responsibility (Off-Chip):**
   - Buffers incoming 4-channel abdominal biopotential data across a 4.0-second ($1,000\text{ samples}$) calibration window.
   - Computes sample covariance matrix $\mathbf{C} = \frac{1}{N} \mathbf{X} \mathbf{X}^T$.
   - Computes eigendecomposition $\mathbf{C} \mathbf{v}_i = \lambda_i \mathbf{v}_i$ to extract 4 principal components.
   - Evaluates autocorrelation of candidate component envelopes in the narrow fetal search window $[83, 136]\text{ samples}$ ($110\text{ to }180\text{ bpm}$).
   - Verifies confidence: $\text{Confidence} = \frac{R_1 - R_2}{R_1} \ge 0.20$ and $R_1 \ge 0.15$.
   - **Continuous Recalibration Policy:**
     - If confident: pack weights into 10-byte calibration packet (`0xC3`) and transmit to FPGA.
     - If uncertain: retain previously verified weights $\mathbf{w}[n] = \mathbf{w}[n-1]$ and assert status flag `0x00: UNCERTAIN`. Never fall back to fixed PC3.

2. **FPGA Responsibility (On-Chip):**
   - Parses incoming 10-byte packet and computes CRC8-CCITT.
   - If CRC8 matches and weights are within signed Q1.15 bounds, latch weights into shadow registers.
   - **64-Sample Linear Cross-Fade Slew Engine:**
     $$\mathbf{w}_{active}[t] = \mathbf{w}_{old} + \frac{k}{64} (\mathbf{w}_{new} - \mathbf{w}_{old}) \quad \text{for } k=1\dots 64$$
     Eliminates step discontinuities that trigger false QRS alarms.
   - If CRC8 fails, drops packet and asserts error LED.
