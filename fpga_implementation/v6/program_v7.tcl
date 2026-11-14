# Program the Boolean board with the v7-DL RTL bitstream.
#   vivado -mode batch -nojournal -nolog -source program_v7.tcl
set BIT [file normalize [file dirname [info script]]/build/v7/v7.bit]
open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target
set dev [lindex [get_hw_devices xc7s50_0] 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $BIT $dev
program_hw_devices $dev
puts "PROGRAMMED $BIT"
close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
