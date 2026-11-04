# Final Fixed-Point Arithmetic & Scaling Specification

## 1. Complete Binary-Point Mapping Chain

```
Biopotential (mV)
      │  * 4096 (12-bit ADC in 16-bit word)
      ▼
Input ADC: Signed 16-bit Q12 (4096 LSB/mV)
      │  * Signed 16-bit Q1.15 weights (32768 LSB/unit)
      ▼
Product: Signed 32-bit Q27 (134,217,728 LSB/mV)
      │  Accumulate 4 channels into 32-bit register (sat to 32 bits)
      ▼
Beamformer Accumulator: Signed 32-bit Q27
      │  >>> 7 Convergent Rounding (Round-to-Nearest-Even)
      ▼
Projection Output: Signed 24-bit Q20 (1,048,576 LSB/mV = 2^20 LSB/mV)
      │
      ├── HP1 Baseline Remover: 32-bit Accumulator, 24-bit Output (Q20)
      │
      └── LP40 Filter (2 Biquads): Q3.15 Coeffs, 48-bit States, 24-bit Output (Q20)
            │
            ▼ (Clean FECG Stream @ 2^20 LSB/mV)
            │
            └── Config C Bandpass Filter (4 Biquads): Q3.15 Coeffs, 48-bit States (Q20)
                  │  >>> 8 Convergent Rounding
                  ▼
            Detector Bandpass Output: Signed 16-bit Q12 (4096 LSB/mV)
                  │  Squaring (16 x 16 -> 32-bit unsigned Q24)
                  ▼
            MWI Accumulator: Unsigned 36-bit Q24 (30-sample trailing sum)
```

---

## 2. Mathematical Definition of Integer Convergent Rounding

To eliminate systematic DC drift across the recursive IIR filter cascade, all right-shift operations employ **Convergent Rounding (Round-to-Nearest-Even)**:

```verilog
function [OUT_BITS-1:0] rshift_round_nearest_even;
    input signed [IN_BITS-1:0] val;
    input integer shift;
    reg signed [IN_BITS-1:0] q;
    reg [shift-1:0] r;
    reg [shift-1:0] half;
begin
    q = val >>> shift;
    r = val & ((1 << shift) - 1);
    half = 1 << (shift - 1);
    if (r > half)
        rshift_round_nearest_even = q + 1;
    else if (r < half)
        rshift_round_nearest_even = q;
    else // Exact halfway: round to nearest even quotient
        rshift_round_nearest_even = q + (q[0] ? 1 : 0);
end
endfunction
```

---

## 3. Physical Signal Re-Scaling Equations

To convert hardware integer telemetry into physical biopotential units:

1. **Spatial Projection Waveform:**
   $$x_{\text{proj}}(\text{mV}) = \frac{\text{proj}_{s24}}{2^{20}} = \frac{\text{proj}_{s24}}{1,048,576}$$

2. **Clean Filtered FECG Waveform:**
   $$s_{\text{fecg}}(\text{mV}) = \frac{fecg_{s24}}{2^{20}} = \frac{fecg_{s24}}{1,048,576}$$

3. **Detector Bandpass Output:**
   $$x_{\text{bp}}(\text{mV}) = \frac{bp_{s16}}{4096} = \frac{bp_{s16}}{2^{12}}$$

4. **Heart Rate Telemetry:**
   $$\text{FHR}(\text{bpm}) = \frac{\text{FHR}_{\text{x10}}}{10.0}$$
