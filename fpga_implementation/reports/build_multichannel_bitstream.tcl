# =============================================================================
# Vivado Complete Synthesis, Implementation, and Bitstream Generation Script
# Target: AMD Spartan-7 XC7S50-1CSGA324C on RealDigital Boolean Board
# Top Module: fecg_multichannel_top
# =============================================================================

set PART "xc7s50csga324-1"
set TOP  "fecg_multichannel_top"
set PROJ_DIR "D:/signal_project"

puts "================================================================="
puts "STARTING SYNTHESIS: $TOP on $PART"
puts "================================================================="

create_project -in_memory -part $PART

# Read all synthesizable RTL sources
read_verilog -verbose [list \
    "$PROJ_DIR/uart_bringup/rtl/uart_rx.v" \
    "$PROJ_DIR/uart_bringup/rtl/uart_tx.v" \
    "$PROJ_DIR/fpga_implementation/rtl/weight_slew_engine.v" \
    "$PROJ_DIR/fpga_implementation/rtl/spatial_beamformer.v" \
    "$PROJ_DIR/fpga_implementation/rtl/biquad_df2t.v" \
    "$PROJ_DIR/fpga_implementation/rtl/hp1_baseline.v" \
    "$PROJ_DIR/fpga_implementation/rtl/lp40_filter.v" \
    "$PROJ_DIR/fpga_implementation/rtl/bandpass_config_c.v" \
    "$PROJ_DIR/fpga_implementation/rtl/squarer_mwi.v" \
    "$PROJ_DIR/fpga_implementation/rtl/adaptive_detector.v" \
    "$PROJ_DIR/fpga_implementation/rtl/peak_localizer.v" \
    "$PROJ_DIR/fpga_implementation/rtl/interval_fusion.v" \
    "$PROJ_DIR/fpga_implementation/rtl/fhr_calculator.v" \
    "$PROJ_DIR/fpga_implementation/rtl/fecg_multichannel_top.v" \
]

# Read physical constraints
read_xdc "$PROJ_DIR/fpga_implementation/constraints/boolean_multichannel.xdc"

# Run Top-Level Synthesis
synth_design -top $TOP -part $PART

# Post-Synthesis Reports
file mkdir "$PROJ_DIR/fpga_implementation/reports/multichannel_out"
report_utilization -file "$PROJ_DIR/fpga_implementation/reports/multichannel_out/post_synth_utilization.rpt"
report_timing_summary -file "$PROJ_DIR/fpga_implementation/reports/multichannel_out/post_synth_timing.rpt"

puts "================================================================="
puts "STARTING LOGIC OPTIMIZATION & PLACEMENT"
puts "================================================================="
opt_design
place_design
report_utilization -file "$PROJ_DIR/fpga_implementation/reports/multichannel_out/post_place_utilization.rpt"
report_timing_summary -file "$PROJ_DIR/fpga_implementation/reports/multichannel_out/post_place_timing.rpt"

puts "================================================================="
puts "STARTING PHYSICAL ROUTING"
puts "================================================================="
route_design
report_utilization -file "$PROJ_DIR/fpga_implementation/reports/multichannel_out/post_route_utilization.rpt"
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -max_paths 10 -input_pins -routable_nets -file "$PROJ_DIR/fpga_implementation/reports/multichannel_out/post_route_timing.rpt"

puts "================================================================="
puts "GENERATING PHYSICAL FPGA BITSTREAM"
puts "================================================================="
file mkdir "$PROJ_DIR/fpga_implementation/bitstream"
write_bitstream -force "$PROJ_DIR/fpga_implementation/bitstream/fecg_multichannel_top.bit"

puts "================================================================="
puts "BUILD COMPLETE: fecg_multichannel_top.bit GENERATED SUCCESSFULLY!"
puts "================================================================="
exit 0
