# Hardware Test Vectors & Golden Reference Data (`fpga_implementation/test_data/`)

This directory stores golden reference datasets, input stimulus files, and bit-accurate expected output vectors used for cycle-accurate simulation and physical hardware verification.

## Authoritative Reference Datasets

1. **`sub01_snr12_c0` Reference Golden Vector Set**:
   - Derived from `code/results/fpga_golden/sub01_snr12_c0/` (PhysioNet FECGSYNDB recording `sub01_snr12dB_l1_c0`).
   - 5,000 samples (20 seconds) at 250 Hz across 4 abdominal channels [27, 26, 28, 25].
   - Contains:
     * `stimulus_ch[0..3]_s16.hex`: 16-bit signed input samples ($4096\text{ LSB/mV}$, Q12).
     * `weights_s16.hex`: Spatial beamformer weights (`[8021, 21951, -12717, -19127]`).
     * `proj_s24.hex`: 24-bit signed projection output ($2^{20}\text{ LSB/mV}$, Q20).
     * `hp_s24.hex`: 24-bit highpass baseline-removed signal.
     * `fecg_s24.hex` & `fecg_out_s16.hex`: 24-bit and 16-bit clean FECG waveforms.
     * `det_bp_s16.hex`: 16-bit bandpass detector filter output.
     * `x_int_u40.hex`: Unsigned MWI energy signal.
     * `fhr_x10_hold_u16.hex`: 16-bit instantaneous FHR output in 0.1 bpm units.
     * `peaks.txt` & `raw_peaks.txt`: 43 detected fetal beats ($72.85\text{ dB}$ SQNR, 42 True Positives).

2. **Single-Channel Verification Stimulus**:
   - `tests/results/fpga_test_vectors/input_stimulus_tc1_hex.txt` (5,000 samples single-channel 16-bit).
   - `tests/results/fpga_test_vectors/golden_output_fecg_tc1_hex.txt` (5,000 samples clean single-channel output).
   - `tests/results/fpga_test_vectors/expected_fetal_peaks_tc1.txt` (49 verified R-peak sample indices).
