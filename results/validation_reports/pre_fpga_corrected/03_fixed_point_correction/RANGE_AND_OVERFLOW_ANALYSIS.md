# Dynamic Range and Overflow Safety Analysis

## 1. Worst-Case Analytical Headroom Bounds

1. **HP1 Baseline Accumulator (32 Bits):**
   - Maximum input is $\pm 8,388,607$ ($2^{23}-1$ in signed 24-bit).
   - In steady-state DC offset, $\text{base} = \text{accum} \gg 6 \implies \text{accum} = 64 \times \text{offset}$.
   - Max steady-state accumulation: $64 \times 2^{23} = 2^{29}$.
   - A 32-bit signed accumulator ($[-2^{31}, 2^{31}-1]$) provides **$3\text{ bits}$ ($18\text{ dB}$) of dynamic margin** above the theoretical maximum DC offset.

2. **Biquad 48-Bit State Registers:**
   - Input signal $|x[n]| \le 2^{23}-1$.
   - Maximum coefficient is $65,536 = 2^{16}$.
   - Single-product bound: $(2^{23}) \times (2^{16}) = 2^{39}$.
   - Under worst-case resonant peaking ($Q \approx 4$), state values reach at most $2^{41}$.
   - The 48-bit DSP48E1 accumulator ($2^{47}$) provides **$6\text{ full bits}$ ($36\text{ dB}$) of headroom**. Overflow is mathematically impossible under bounded inputs.
