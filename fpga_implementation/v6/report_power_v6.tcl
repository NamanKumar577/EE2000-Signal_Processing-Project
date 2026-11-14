# Re-run the v6 implementation (same flow as build_v6.tcl, no bitstream) and write the
# power estimate and per-module utilisation.  vivado -mode batch -nojournal -nolog -source report_power_v6.tcl
set D [file normalize [file dirname [info script]]]
set_part xc7s50csga324-1
foreach f {v6_uart v6_link v6_sos v6_mwi v6_det v6_fe v6_mat v6_canc v6_trk v6_core v6_top} { read_verilog $D/rtl/$f.v }
read_xdc $D/v6.xdc
synth_design -top v6_top -part xc7s50csga324-1
opt_design
place_design
phys_opt_design
route_design
report_utilization -hierarchical -hierarchical_depth 3 -file $D/build/util_hier.rpt
report_power -file $D/build/power.rpt
puts "REPORTS_DONE"
