# Final Weight Crossfade and Dynamic Update Specification

## 1. Mathematical Formulation of the 64-Sample Linear Slew Engine

To eliminate step discontinuities in the spatial projection during dynamic recalibration, the hardware reference model and Spartan-7 RTL datapath implement a **64-Sample Linear Crossfade Slew Engine**:

$$\mathbf{w}_{\text{active}}[k] = \mathbf{w}_{\text{old}} + \text{rshift\_round\_nearest\_even}(k \times (\mathbf{w}_{\text{new}} - \mathbf{w}_{\text{old}}), 6) \quad \text{for } k = 1, 2, \dots, 64$$

Where:
- $\mathbf{w}_{\text{old}}$ is the previously active signed 16-bit Q1.15 spatial weight vector.
- $\mathbf{w}_{\text{new}}$ is the newly received validated target weight vector.
- $k \in [1, 64]$ is a 6-bit transition sample counter incremented once every ADC sample ($4.0\text{ ms}$).
- Shift by 6 represents exact integer division by $64$ ($2^6 = 64$).
- $\text{rshift\_round\_nearest\_even}$ applies convergent rounding to prevent DC offset accumulation.
- Total crossfade duration: $64 \times 4.0\text{ ms} = \mathbf{256.0\text{ ms}}$.

---

## 2. Hardware Arithmetic and Edge Case Behavior

1. **Exact Terminal Convergence:**
   At $k = 64$:
   $$\text{rshift}(64 \times \Delta\mathbf{w}, 6) = \Delta\mathbf{w} = \mathbf{w}_{\text{new}} - \mathbf{w}_{\text{old}}$$
   $$\mathbf{w}_{\text{active}}[64] = \mathbf{w}_{\text{old}} + (\mathbf{w}_{\text{new}} - \mathbf{w}_{\text{old}}) = \mathbf{w}_{\text{new}}$$
   The final weight vector reaches $\mathbf{w}_{\text{new}}$ identically with zero residue.

2. **Interrupted Transition Handling:**
   If a new valid calibration packet arrives at time $t$ while an active crossfade is in progress ($k < 64$):
   - The current instantaneous interpolated weight $\mathbf{w}_{\text{active}}[k]$ is immediately latched as the new baseline: $\mathbf{w}_{\text{old}} \leftarrow \mathbf{w}_{\text{active}}[k]$.
   - The new target is loaded: $\mathbf{w}_{\text{new}} \leftarrow \mathbf{w}_{\text{packet}}$.
   - The counter is reset: $k \leftarrow 1$.
   - Output continuity is preserved with zero step jump.

3. **Corrupted or Invalid Packet Handling:**
   - If an incoming packet fails CRC8-CCITT or contains weights outside $[-32,768, +32,767]$, the packet is dropped immediately.
   - The active slew engine continues its current trajectory towards the previously scheduled target without interruption.

4. **Hardware Multiplier-Free Realization:**
   Multiplication by $k$ ($1 \dots 64$) and division by 64 can be realized with a 6-bit accumulator:
   $$\text{acc}[k] = \text{acc}[k-1] + \Delta\mathbf{w}$$
   $$\mathbf{w}_{\text{active}}[k] = \mathbf{w}_{\text{old}} + (\text{acc}[k] \gg 6)$$
   This architecture consumes **zero DSP48 blocks**, requiring only standard slice registers and adders.
