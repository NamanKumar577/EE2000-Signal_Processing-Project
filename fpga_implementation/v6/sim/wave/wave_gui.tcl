# Vivado simulator GUI: add the readable v6 signals in groups, then run the whole recording.
# Opened by open_wave_gui.bat (after run_wave.sh has compiled the snapshot).
proc grp {name} { catch {add_wave_divider $name} }
proc sig {path {radix dec}} { catch {add_wave -radix $radix $path} }
proc ana {path} {
    sig $path dec
    catch {set_property display_style analog [get_waves [file tail $path]]}
}
grp "Clock and sequencer"
sig /tb_wave/clk bin
sig /tb_wave/sample_T unsigned
sig /tb_wave/seq_state unsigned
sig /tb_wave/unit_ph unsigned
grp "Input: raw abdominal leads (int16)"
ana /tb_wave/raw_lead1
ana /tb_wave/raw_lead2
grp "Front end output Xf"
ana /tb_wave/xf_lead1
ana /tb_wave/xf_lead2
grp "Maternal R peaks"
sig /tb_wave/mat_npeaks unsigned
sig /tb_wave/mat_peak_t dec
grp "Tracks and output"
sig /tb_wave/calibrated bin
sig /tb_wave/sel_track dec
sig /tb_wave/beat_t dec
ana /tb_wave/fhr_x10
grp "Unit hand-shakes"
foreach s {fe_go fe_done mat_go mat_done ca_go ca_done tk_go tk_done} { sig /tb_wave/$s bin }
grp "PC link"
sig /tb_wave/rx_valid bin
sig /tb_wave/rx_byte hex
sig /tb_wave/tx_valid bin
sig /tb_wave/tx_byte hex
sig /tb_wave/msg_start bin
sig /tb_wave/msg_cmd hex
foreach s {pca_answer train_answer basis_answer gevd_answer sel_answer} { sig /tb_wave/$s bin }
run all
