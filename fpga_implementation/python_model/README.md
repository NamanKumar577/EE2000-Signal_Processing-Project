# Python Reference Models (`fpga_implementation/python_model/`)

This directory houses the cycle-accurate and bit-accurate Python verification models that serve as the digital twins and golden behavioral references for the FPGA RTL implementation.

## Purpose & Scope

The models in this directory bridge the gap between floating-point scientific algorithm exploration and bit-accurate digital hardware synthesis:

1. **Bit-Accurate Reference Model**:
   - Mirrors `src/fecg/hardware/bit_accurate_reference.py`.
   - Enforces exact signed and unsigned saturation limits, convergent rounding (`round-to-nearest-even`), 18-sample group delay rewind, and pure integer median-5 sorting.
   - Operates with integer-only arithmetic to guarantee zero divergence from hardware registers.

2. **Integer Simulation Model**:
   - Mirrors `src/fecg/hardware/fpga_int_model.py`.
   - Simulates fixed-point quantization effects, filter state transitions, and generates stage-by-stage hexadecimal stimulus vectors for Verilog testbenches.

3. **Software Digital Twin for Co-Simulation**:
   - Provides verification hooks for comparing cycle-by-cycle Verilog simulation logs against Python predicted state.
   - Validates Signal-to-Quantization-Noise Ratio (SQNR) targets ($>40.0\text{ dB}$ requirement, $>70.0\text{ dB}$ observed).
