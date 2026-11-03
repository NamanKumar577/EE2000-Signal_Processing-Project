open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target
set devices [get_hw_devices]
puts "FOUND_DEVICES: $devices"
foreach dev $devices {
    current_hw_device $dev
    refresh_hw_device $dev
    set is_prog [get_property IS_PROGRAMMED $dev]
    set done_pin [get_property PROGRAM.DONE_PIN $dev]
    puts "DEV_STATUS: $dev | IS_PROGRAMMED=$is_prog | DONE_PIN=$done_pin"
}
close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
