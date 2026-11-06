# Verilog Simulation Testbenches (`fpga_implementation/testbenches/`)

This directory will host the Verilog simulation testbenches for verifying each hardware submodule and the integrated top-level system.

## Planned Testbench Inventory (Milestones M1 & M2)

1. **`tb_biquad_df2t.v`**:
   - Stimulates single and cascaded Transposed Direct Form II biquads with impulse, step, and sinusoidal inputs.
   - Verifies 48-bit state accumulation, convergent rounding, and saturation behavior against Python bit-accurate model.

2. **`tb_hp1_filter.v`**:
   - Verifies recursive shift-and-add baseline wander remover ($k=6$, $f_c \approx 0.62\text{ Hz}$).
   - Verifies 32-bit DC tracking accumulator under heavy baseline wander signals.

3. **`tb_mwi_ring.v`**:
   - Tests 30-sample circular RAM buffer and 36-bit running summation accumulator under maximum amplitude bursts.

4. **`tb_adaptive_threshold.v`**:
   - Tests 512-sample warm-up phase, candidate peak lookahead at $m = t - 1$, EMA level adaptation ($\alpha = 1/8$), and refractory counter enforcement (50 samples / 200 ms).

5. **`tb_peak_localizer.v`**:
   - Tests 26-sample trailing window local search, tie-breaking rules, and 18-sample group delay rewind subtractor.

6. **`tb_median5_filter.v`**:
   - Tests pure integer 5-sample sorting network with permutation sweeps and boundary values ($50 \le RR \le 300$).

7. **`tb_fecg_top.v`**:
   - Full top-level closed-loop simulation testbench.
   - Streams 5,000 samples of 4-channel input stimulus from `code/results/fpga_golden/sub01_snr12_c0/` over UART at 921,600 baud.
   - Captures output packets (`0x5A` clean stream and `0xAA` FHR events) and checks bit-for-bit equivalence against golden hex reference files.
