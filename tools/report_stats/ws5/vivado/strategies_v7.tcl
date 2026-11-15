# WS5: v7-DL implementation with 3 placement/routing strategies (same RTL, same constraints).
# Writes only into this folder. vivado -mode batch -nojournal -source strategies_v7.tcl
set D [file normalize [file dirname [info script]]/../../../../fpga_implementation/v6]
set O [file normalize [file dirname [info script]]]
set_part xc7s50csga324-1
foreach f {v6_uart v6_link v6_sos v6_mwi v6_det v6_fe v6_mat v6_canc v6_trk v6_core v7_la v7_disp v6_top} { read_verilog $D/rtl/$f.v }
read_xdc $D/v6.xdc
read_xdc $D/v7.xdc
synth_design -top v6_top -part xc7s50csga324-1 -verilog_define V61 -verilog_define V7
opt_design
write_checkpoint -force $O/opt.dcp
foreach dir {Default Explore ExtraNetDelay_high} {
  open_checkpoint $O/opt.dcp
  place_design -directive $dir
  phys_opt_design
  route_design
  report_timing_summary -file $O/timing_$dir.rpt
  set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
  puts "STRATEGY $dir WNS $wns"
  close_design
}
puts "ALL_DONE"
