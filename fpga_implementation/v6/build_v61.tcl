# Build the v6.1 bitstream (same flow as build_v6.tcl, Verilog define V61).
#   vivado -mode batch -nojournal -nolog -source build_v61.tcl     -> build/v61/
set D [file normalize [file dirname [info script]]]
set O $D/build/v61
file mkdir $O
set_part xc7s50csga324-1
foreach f {v6_uart v6_link v6_sos v6_mwi v6_det v6_fe v6_mat v6_canc v6_trk v6_core v6_top} { read_verilog $D/rtl/$f.v }
read_xdc $D/v6.xdc
synth_design -top v6_top -part xc7s50csga324-1 -verilog_define V61
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
write_bitstream -force $O/v61.bit
puts "BUILD_DONE"
