# FECG v5 platform: MicroBlaze (FPU) + LMB BRAM + UART Lite + Timer + GPIO LEDs
# Usage: vivado -mode batch -source build_v5.tcl
set PART xc7s50csga324-1
set V5   [file normalize [file dirname [info script]]]
set PROJ $V5/build/proj
set SYS_MHZ 73.728
set BAUD 921600
set LMB_KB 256

file delete -force $PROJ
create_project v5 $PROJ -part $PART
create_bd_design sys

# ports
create_bd_port -dir I -type clk -freq_hz 100000000 clk
create_bd_port -dir I -type rst rst_pin
set_property CONFIG.POLARITY ACTIVE_HIGH [get_bd_ports rst_pin]
create_bd_port -dir I uart_rxd
create_bd_port -dir O uart_txd
create_bd_port -dir O -from 7 -to 0 led

# clock
set cw [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz clk_wiz_0]
set_property -dict [list CONFIG.PRIM_IN_FREQ 100.000 CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $SYS_MHZ \
  CONFIG.USE_RESET true CONFIG.RESET_TYPE ACTIVE_HIGH CONFIG.USE_LOCKED true] $cw
connect_bd_net [get_bd_ports clk] [get_bd_pins clk_wiz_0/clk_in1]
connect_bd_net [get_bd_ports rst_pin] [get_bd_pins clk_wiz_0/reset]

# MicroBlaze
set mb [create_bd_cell -type ip -vlnv xilinx.com:ip:microblaze microblaze_0]
apply_bd_automation -rule xilinx.com:bd_rule:microblaze -config [list \
  axi_intc 0 axi_periph Enabled cache None clk "/clk_wiz_0/clk_out1 ($SYS_MHZ MHz)" \
  cores 1 debug_module {Debug Only} ecc None local_mem 128KB preset None] $mb
set_property -dict [list CONFIG.C_USE_FPU 2 CONFIG.C_USE_BARREL 1 CONFIG.C_USE_HW_MUL 1 \
  CONFIG.C_USE_DIV 1 CONFIG.C_USE_PCMP_INSTR 1 CONFIG.C_AREA_OPTIMIZED 0] $mb

# peripherals
# UART16550: programmable divisor; 73.728 MHz / (16*5) = 921600 baud (set in firmware)
set ul [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_uart16550 axi_uart_0]
set tm [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_timer axi_timer_0]
set gp [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio axi_gpio_0]
set_property -dict [list CONFIG.C_GPIO_WIDTH 8 CONFIG.C_ALL_OUTPUTS 1] $gp
foreach s {axi_uart_0/S_AXI axi_timer_0/S_AXI axi_gpio_0/S_AXI} {
  apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list Clk_master {Auto} Clk_slave {Auto} \
    Clk_xbar {Auto} Master {/microblaze_0 (Periph)} Slave "/[lindex [split $s /] 0]/S_AXI" \
    ddr_seg {Auto} intc_ip {New AXI Interconnect} master_apm {0}] [get_bd_intf_pins $s]
}
connect_bd_net [get_bd_ports uart_rxd] [get_bd_pins axi_uart_0/sin]
connect_bd_net [get_bd_ports uart_txd] [get_bd_pins axi_uart_0/sout]
set c1 [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant one]
foreach p {ctsn dcdn dsrn rin} { connect_bd_net [get_bd_pins one/dout] [get_bd_pins axi_uart_0/$p] }
connect_bd_net [get_bd_ports led] [get_bd_pins axi_gpio_0/gpio_io_o]

# reset: proc_sys_reset ext reset from button (automation created rst_clk_wiz_0_*)
set rst [get_bd_cells -filter {VLNV =~ *proc_sys_reset*}]
catch {disconnect_bd_net [get_bd_nets -of [get_bd_pins $rst/ext_reset_in]] [get_bd_pins $rst/ext_reset_in]}
connect_bd_net [get_bd_ports rst_pin] [get_bd_pins $rst/ext_reset_in]
# (ext reset polarity follows rst_pin's ACTIVE_HIGH property)

# extra data RAM on AXI: 75 BRAM36 total, LMB 256 KB uses 64 -> 32 KB is the largest power of 2 left
set ab [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_bram_ctrl axi_bram_ctrl_0]
set_property -dict [list CONFIG.SINGLE_PORT_BRAM 1 CONFIG.PROTOCOL AXI4LITE] $ab
# (bd automation for axi_bram_ctrl fails in 2025.2 batch mode -> wire it by hand)
set ic [get_bd_cells microblaze_0_axi_periph]
set nmi [get_property CONFIG.NUM_MI $ic]
set_property CONFIG.NUM_MI [expr {$nmi + 1}] $ic
connect_bd_intf_net [get_bd_intf_pins $ic/[format M%02d_AXI $nmi]] [get_bd_intf_pins axi_bram_ctrl_0/S_AXI]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins $ic/[format M%02d_ACLK $nmi]] [get_bd_pins axi_bram_ctrl_0/s_axi_aclk]
connect_bd_net [get_bd_pins $rst/peripheral_aresetn] [get_bd_pins $ic/[format M%02d_ARESETN $nmi]] [get_bd_pins axi_bram_ctrl_0/s_axi_aresetn]
create_bd_cell -type ip -vlnv xilinx.com:ip:blk_mem_gen axi_bram_0
connect_bd_intf_net [get_bd_intf_pins axi_bram_ctrl_0/BRAM_PORTA] [get_bd_intf_pins axi_bram_0/BRAM_PORTA]

assign_bd_address
set bseg [get_bd_addr_segs microblaze_0/Data/SEG_axi_bram_ctrl_0_Mem0]
set_property offset 0xC0000000 $bseg
set_property range 32K $bseg
# enlarge LMB to LMB_KB
foreach seg [get_bd_addr_segs -of [get_bd_addr_spaces microblaze_0/*] -filter {NAME =~ *ilmb* || NAME =~ *dlmb*}] {
  set_property range ${LMB_KB}K $seg
}
foreach seg [get_bd_addr_segs microblaze_0/*/SEG_*] { puts "SEG [get_property NAME $seg] [get_property OFFSET $seg] [get_property RANGE $seg]" }
validate_bd_design
save_bd_design

make_wrapper -files [get_files sys.bd] -top
add_files -norecurse [glob $PROJ/v5.gen/sources_1/bd/sys/hdl/sys_wrapper.v]
set_property top sys_wrapper [current_fileset]
add_files -fileset constrs_1 -norecurse $V5/v5.xdc

launch_runs synth_1 -jobs 8
wait_on_run synth_1
launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1
open_run impl_1
report_utilization -file $V5/reports/utilization.rpt
report_timing_summary -file $V5/reports/timing.rpt
report_clocks -file $V5/reports/clocks.rpt
file copy -force [glob $PROJ/v5.runs/impl_1/sys_wrapper.bit] $V5/build/sys_hw.bit
write_hw_platform -fixed -force -file $V5/build/sys.xsa
write_mem_info -force $V5/build/sys.mmi
puts "WNS=[get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]"
