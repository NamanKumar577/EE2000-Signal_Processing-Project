# Build the v6 bitstream (non-project flow).   vivado -mode batch -nojournal -nolog -source build_v6.tcl
set D [file normalize [file dirname [info script]]]
set_part xc7s50csga324-1
foreach f {v6_uart v6_link v6_sos v6_mwi v6_det v6_fe v6_mat v6_canc v6_trk v6_core v6_top} { read_verilog $D/rtl/$f.v }
read_xdc $D/v6.xdc
synth_design -top v6_top -part xc7s50csga324-1
report_utilization -file $D/build/util_synth.rpt
opt_design
place_design
phys_opt_design
route_design
report_utilization -file $D/build/util.rpt
report_timing_summary -file $D/build/timing.rpt
report_drc -file $D/build/drc.rpt
write_bitstream -force $D/build/v6.bit
puts "BUILD_DONE"
