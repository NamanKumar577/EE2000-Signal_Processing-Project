# =============================================================================
# Vivado Batch Synthesis and Implementation Script
# Target: AMD / Xilinx Spartan-7 XC7S50-1CSGA324C
# =============================================================================

set PART "xc7s50csga324-1"
set TOP  "fecg_single_channel_top"
set PROJ_DIR "D:/signal_project/fpga_implementation"

puts "================================================================="
puts "STARTING SYNTHESIS: $TOP on $PART"
puts "================================================================="

# Create in-memory project
create_project -in_memory -part $PART

# Read synthesizable RTL sources
read_verilog -verbose [list \
    "$PROJ_DIR/rtl/biquad_df2t.v" \
    "$PROJ_DIR/rtl/hp1_baseline.v" \
    "$PROJ_DIR/rtl/lp40_filter.v" \
    "$PROJ_DIR/rtl/bandpass_config_c.v" \
    "$PROJ_DIR/rtl/squarer_mwi.v" \
    "$PROJ_DIR/rtl/adaptive_detector.v" \
    "$PROJ_DIR/rtl/peak_localizer.v" \
    "$PROJ_DIR/rtl/interval_fusion.v" \
    "$PROJ_DIR/rtl/fhr_calculator.v" \
    "$PROJ_DIR/rtl/fecg_single_channel_top.v" \
]

# Read timing constraints
read_xdc "$PROJ_DIR/constraints/spartan7_timing.xdc"

# Run Synthesis (Out of Context to preserve pure datapath metrics)
synth_design -top $TOP -part $PART -mode out_of_context

# Reports post-synthesis
file mkdir "$PROJ_DIR/reports/reports_out"
report_utilization -file "$PROJ_DIR/reports/reports_out/post_synth_utilization.rpt" -pb "$PROJ_DIR/reports/reports_out/post_synth_utilization.pb"
report_timing_summary -file "$PROJ_DIR/reports/reports_out/post_synth_timing.rpt"

puts "================================================================="
puts "STARTING OPTIMIZATION & PLACEMENT"
puts "================================================================="
opt_design
place_design
report_utilization -file "$PROJ_DIR/reports/reports_out/post_place_utilization.rpt"
report_timing_summary -file "$PROJ_DIR/reports/reports_out/post_place_timing.rpt"

puts "================================================================="
puts "STARTING ROUTING"
puts "================================================================="
route_design
report_utilization -file "$PROJ_DIR/reports/reports_out/post_route_utilization.rpt" -pb "$PROJ_DIR/reports/reports_out/post_route_utilization.pb"
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -max_paths 10 -input_pins -routable_nets -file "$PROJ_DIR/reports/reports_out/post_route_timing.rpt"

puts "================================================================="
puts "VIVADO SYNTHESIS AND IMPLEMENTATION COMPLETE!"
puts "================================================================="
exit
