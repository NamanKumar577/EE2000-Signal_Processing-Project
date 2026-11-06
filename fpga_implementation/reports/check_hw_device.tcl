open_hw_manager
puts "CONNECTING TO HARDWARE SERVER..."
if {[catch {connect_hw_server} err]} {
    puts "HW_SERVER_CONNECT_ERROR: $err"
    exit 0
}
puts "GETTING TARGETS..."
set targets [get_hw_targets]
puts "AVAILABLE_TARGETS: $targets"
if {[llength $targets] > 0} {
    open_hw_target [lindex $targets 0]
    set devs [get_hw_devices]
    puts "DETECTED_DEVICES: $devs"
    foreach dev $devs {
        current_hw_device $dev
        refresh_hw_device $dev
        puts "DEV_NAME: [get_property NAME $dev]"
        puts "DEV_PART: [get_property PART $dev]"
        puts "IS_PROGRAMMED: [get_property IS_PROGRAMMED $dev]"
    }
    close_hw_target
} else {
    puts "NO_JTAG_TARGETS_FOUND"
}
disconnect_hw_server
close_hw_manager
exit 0
