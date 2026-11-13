open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target
current_hw_device [get_hw_devices xc7s50_0]
refresh_hw_device -update_hw_probes false [lindex [get_hw_devices xc7s50_0] 0]
set_property PROGRAM.FILE {C:/Users/Naman/Desktop/vivado/spartan7_uart_bringup/spartan7_uart_bringup.runs/impl_1/uart_top.bit} [get_hw_devices xc7s50_0]
program_hw_devices [get_hw_devices xc7s50_0]
refresh_hw_device [lindex [get_hw_devices xc7s50_0] 0]
close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
