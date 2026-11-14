# Build the v7-DL bitstream (v6.1 + look-ahead unit v7_la; Verilog defines V61 and V7).
#   vivado -mode batch -nojournal -nolog -source build_v7.tcl     -> build/v7/
set D [file normalize [file dirname [info script]]]
set O $D/build/v7
file mkdir $O
set_part xc7s50csga324-1
foreach f {v6_uart v6_link v6_sos v6_mwi v6_det v6_fe v6_mat v6_canc v6_trk v6_core v7_la v7_disp v6_top} { read_verilog $D/rtl/$f.v }
read_xdc $D/v6.xdc
read_xdc $D/v7.xdc
synth_design -top v6_top -part xc7s50csga324-1 -verilog_define V61 -verilog_define V7
report_utilization -file $O/util_synth.rpt
opt_design
place_design
phys_opt_design
route_design
report_utilization -file $O/util.rpt
report_utilization -hierarchical -hierarchical_depth 3 -file $O/util_hier.rpt
report_timing_summary -file $O/timing.rpt
report_power -file $O/power.rpt
report_drc -file $O/drc.rpt
write_bitstream -force $O/v7.bit
puts "BUILD_DONE"
