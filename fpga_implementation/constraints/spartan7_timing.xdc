# =============================================================================
# Timing Constraints for Spartan-7 XC7S50-1CSGA324C
# Master System Clock: 100.0 MHz (10.0 ns period)
# =============================================================================

create_clock -period 10.000 -name clk -waveform {0.000 5.000} [get_ports clk]
set_input_delay -clock [get_clocks clk] -min 1.000 [get_ports {adc_data_in[*] sample_valid_in enable rst_n}]
set_input_delay -clock [get_clocks clk] -max 3.000 [get_ports {adc_data_in[*] sample_valid_in enable rst_n}]
set_output_delay -clock [get_clocks clk] -min 1.000 [get_ports {fecg_clean_out[*] hp_filtered_out[*] det_bp_out[*] mwi_energy_out[*] waveform_valid_out beat_valid_strobe fused_beat_strobe raw_peak_timestamp[*] comp_peak_timestamp[*] raw_rr_interval[*] median_rr_interval[*] fhr_instant_out[*] fhr_stream_out[*] telemetry_flags[*] n_fused_count[*] detector_active}]
set_output_delay -clock [get_clocks clk] -max 3.000 [get_ports {fecg_clean_out[*] hp_filtered_out[*] det_bp_out[*] mwi_energy_out[*] waveform_valid_out beat_valid_strobe fused_beat_strobe raw_peak_timestamp[*] comp_peak_timestamp[*] raw_rr_interval[*] median_rr_interval[*] fhr_instant_out[*] fhr_stream_out[*] telemetry_flags[*] n_fused_count[*] detector_active}]
