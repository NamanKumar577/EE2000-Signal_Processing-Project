# ==============================================================================
# run_production_build.tcl
# Autonomous Vivado 2025.2 Batch Flow Script
# Target: Spartan-7 XC7S50 (RealDigital Boolean Board)
# Project: C:/Users/Naman/Desktop/vivado/spartan7_uart_bringup/spartan7_uart_bringup.xpr
# ==============================================================================

set start_time [clock seconds]
puts "=========================================================================="
puts "  STARTING VIVADO BATCH BUILD FLOW FOR SPARTAN-7 UART BRINGUP"
puts "  Time: [clock format $start_time -format {%Y-%m-%d %H:%M:%S}]"
puts "=========================================================================="

# 1. Open Project
set proj_path "C:/Users/Naman/Desktop/vivado/spartan7_uart_bringup/spartan7_uart_bringup.xpr"
puts "INFO: Opening project: $proj_path"
open_project $proj_path

# Verify Target Device and Top Module
set current_part [get_property PART [current_project]]
set current_top  [get_property TOP [current_fileset]]
puts "INFO: Part = $current_part (Expected: xc7s50csga324-1)"
puts "INFO: Top  = $current_top (Expected: uart_top)"

# 2. Disable and Clear Stale Incremental Checkpoints
puts "INFO: Disabling and clearing incremental checkpoints on synth_1 and impl_1..."
catch { set_property AUTO_INCREMENTAL_CHECKPOINT 0 [get_runs synth_1] }
catch { set_property INCREMENTAL_CHECKPOINT "" [get_runs synth_1] }
catch { set_property AUTO_INCREMENTAL_CHECKPOINT 0 [get_runs impl_1] }
catch { set_property INCREMENTAL_CHECKPOINT "" [get_runs impl_1] }

# Remove stale checkpoint from utils_1 if present
catch {
    set dcp_files [get_files -quiet -of [get_filesets utils_1] uart_top.dcp]
    if {[llength $dcp_files] > 0} {
        puts "INFO: Removing stale checkpoint from utils_1: $dcp_files"
        remove_files -fileset utils_1 $dcp_files
    }
}

# 3. Clean Reset of Previous Runs
puts "INFO: Resetting impl_1 and synth_1 runs..."
reset_run impl_1
reset_run synth_1

# 4. Launch Synthesis
puts "=========================================================================="
puts "  STEP 1: RUNNING SYNTHESIS (synth_1)"
puts "=========================================================================="
launch_runs synth_1 -jobs 8
wait_on_run synth_1

set synth_status   [get_property STATUS [get_runs synth_1]]
set synth_progress [get_property PROGRESS [get_runs synth_1]]
puts "INFO: synth_1 finished: Status='$synth_status', Progress='$synth_progress'"

if {$synth_progress ne "100%"} {
    puts "ERROR: Synthesis failed! Status='$synth_status'"
    exit 1
}

# 5. Launch Implementation through Bitstream Generation
puts "=========================================================================="
puts "  STEP 2: RUNNING IMPLEMENTATION & WRITE BITSTREAM (impl_1)"
puts "=========================================================================="
launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1

set impl_status   [get_property STATUS [get_runs impl_1]]
set impl_progress [get_property PROGRESS [get_runs impl_1]]
puts "INFO: impl_1 finished: Status='$impl_status', Progress='$impl_progress'"

if {$impl_progress ne "100%"} {
    puts "ERROR: Implementation / write_bitstream failed! Status='$impl_status'"
    exit 1
}

# 6. Verify Artifacts
set bit_path "C:/Users/Naman/Desktop/vivado/spartan7_uart_bringup/spartan7_uart_bringup.runs/impl_1/uart_top.bit"
if {[file exists $bit_path]} {
    set bit_size [file size $bit_path]
    puts "=========================================================================="
    puts "  SUCCESS: BITSTREAM GENERATED SUCCESSFULLY"
    puts "  Path: $bit_path"
    puts "  Size: $bit_size bytes"
    puts "=========================================================================="
} else {
    puts "ERROR: Bitstream file was not created at $bit_path"
    exit 1
}

set end_time [clock seconds]
set elapsed [expr {$end_time - $start_time}]
puts "INFO: Build finished in $elapsed seconds."

close_project
exit 0
