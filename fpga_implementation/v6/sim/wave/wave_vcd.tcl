# Batch run: dump the tb_wave signals (everything except the clock) to a VCD file.
open_vcd wave.vcd
foreach s {sample_T seq_state unit_ph raw_lead1 raw_lead2 raw_lead3 raw_lead4
           xf_we xf_addr xf_lead1 xf_lead2 xf_lead3 xf_lead4
           z_we z_addr z_lead1 z_lead2 z_lead3 z_lead4
           mat_npeaks mat_peak_t calibrated sel_track beat_t fhr_x10
           fe_go fe_done mat_go mat_done ca_go ca_done tk_go tk_done
           rx_valid rx_byte tx_valid tx_byte msg_start msg_cmd
           pca_answer gevd_answer sel_answer basis_answer train_answer} {
    log_vcd /tb_wave/$s
}
run all
close_vcd
quit
