# Pre-FPGA Automated Regression Test Coverage Report

**Document ID:** `validation/pre_fpga/10_regression_tests/TEST_COVERAGE.md`  
**Execution Command:** `pytest code/tests/test_pre_fpga_regression.py -v`  
**Total Tests:** 26 / 26 passing ($100.0\%$)  
**Execution Duration:** $1.68\text{ seconds}$  
**Overall Repository Test Suite:** 171 / 171 passing ($100.0\%$)  

---

## 1. Test Coverage Matrix

Every item specified in Task J was explicitly codified and verified:

| Test ID | Test Function Name | Functional Area Covered | Test Assertion / Standard | Result |
| :---: | :--- | :--- | :--- | :---: |
| **01** | `test_01_channel_ordering` | Channel Configuration | Validates channel array `[27, 26, 28, 25]` ordering | **PASS** |
| **02** | `test_02_sample_rate` | Timing & Sampling | $f_s = 250\text{ Hz}$ ($T_s = 4.0\text{ ms}$, $400,000$ cycles @ $100\text{ MHz}$) | **PASS** |
| **03** | `test_03_projection_weights` | Weight Representation | Verifies Signed 16-bit Q1.15 normalization ($[-32768, 32767]$) | **PASS** |
| **04** | `test_04_invalid_calibration_rejection` | Weight Validation | Rejects all-zero and invalid weight vectors | **PASS** |
| **05** | `test_05_calibration_packet_crc` | Communications CRC | Validates CRC8-CCITT ($0x07$) and corrupt packet detection | **PASS** |
| **06** | `test_06_projection_arithmetic` | Spatial Math | Bit-accurate dot product with symmetric rounding >>> 7 | **PASS** |
| **07** | `test_07_filter_impulse_response` | IIR Stability | Unit impulse injection decays stably without limit cycles | **PASS** |
| **08** | `test_08_filter_frequency_response` | Bandpass Selectivity | Confirms $12\text{--}35\text{ Hz}$ passband attenuation at $5\text{ Hz}$ and $60\text{ Hz}$ | **PASS** |
| **09** | `test_09_filter_startup_behavior` | Warm-up Logic | Confirms zero beat declarations during $512\text{ sample}$ warm-up | **PASS** |
| **10** | `test_10_mwi_window_length` | Energy Integration | Validates 30-sample ring buffer addition and subtraction | **PASS** |
| **11** | `test_11_peak_detection` | QRS Detection | Detects fetal R-peaks on multi-channel mixture | **PASS** |
| **12** | `test_12_refractory_timing` | Blanking Logic | Enforces minimum $50\text{ sample}$ ($200\text{ ms}$) interval | **PASS** |
| **13** | `test_13_duplicate_detection_suppression` | Duplicate Blanking | Zero duplicate timestamps in detected peak list | **PASS** |
| **14** | `test_14_missed_beats_handling` | Signal Dropout | Correctly flags missing beats and holds FHR | **PASS** |
| **15** | `test_15_rr_interval_calculation` | RR Arithmetic | Correct sample differences ($t_R[n] - t_R[n-1]$) | **PASS** |
| **16** | `test_16_beat_repair_interval_fusion` | Quality Engine | Fuses split biphasic peaks ($RR < 60\text{ samples}$) | **PASS** |
| **17** | `test_17_fhr_lut_calculation` | FHR Conversion | Validates 241-word LUT mapping $RR \rightarrow \text{bpm} \times 10$ | **PASS** |
| **18** | `test_18_fixed_point_overflow_stress` | Saturation Stress | Injects continuous rails ($\pm 32,767$) with 48-bit DSP margin | **PASS** |
| **19** | `test_19_uart_packet_parsing` | UART Protocol | Verifies framing headers `0xA5` and `0xC3` | **PASS** |
| **20** | `test_20_uart_resynchronization` | Fault Recovery | Hunts and re-locks to frame header after byte corruption | **PASS** |
| **21** | `test_21_continuous_streaming_causality`| Causality Proof | Future sample perturbations do not affect past outputs | **PASS** |
| **22** | `test_22_reset_behavior` | Hardware Reset | Clean reset restores initial states and default $\text{PC}_3$ | **PASS** |
| **23** | `test_23_edge_case_all_zero_input` | Flatline Protection | Zero output, zero false detections, no divide-by-zero | **PASS** |
| **24** | `test_24_edge_case_saturated_square_wave`| Nyquist Square Stress | Alternating $\pm 32767$ at $125\text{ Hz}$ handled cleanly | **PASS** |
| **25** | `test_25_edge_case_abrupt_signal_step` | Transient Step | $+5\text{ mV}$ step transient absorbed without numerical overflow | **PASS** |
| **26** | `test_26_edge_case_tachycardia_and_bradycardia`| Rate Extremes | Full coverage from $50\text{ bpm}$ ($RR=300$) to $250\text{ bpm}$ ($RR=60$) | **PASS** |
