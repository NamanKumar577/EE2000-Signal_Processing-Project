// =============================================================================
// Module: interval_fusion
// Description: Split-Beat Interval Fusion & Pure Integer Median-5 Filter.
//              - True Interval Fusion: Detects split/double-triggered beats with
//                raw_rr < RR_MIN (50 samples = 200 ms @ 250 Hz). Merges candidate
//                into preceding beat, updating timestamp if amplitude is higher,
//                without corrupting the median FIFO.
//              - Normal Beats (50 <= raw_rr <= 300): Pushes RR into a 5-entry FIFO
//                and computes the pure integer median using a combinational
//                sorting network (zero floating-point operations).
//              - Dropouts (raw_rr > 300): Declares held FHR event (Flag 2'b10)
//                without pushing the anomalous RR into the median buffer.
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Latency: 1 clock cycle after peak_strobe assertion
// =============================================================================

`timescale 1ns / 1ps

module interval_fusion #(
    parameter integer DATA_WIDTH = 16,        // Peak magnitude width
    parameter integer TIME_WIDTH = 24,        // Timestamp counter width
    parameter integer RR_WIDTH   = 16,        // RR interval width
    parameter integer RR_MIN     = 50,        // 300 bpm @ 250 Hz (50 samples = 200 ms)
    parameter integer RR_MAX     = 300        // 50 bpm @ 250 Hz (300 samples = 1200 ms)
)(
    input  wire                          clk,               // Master system clock (100 MHz)
    input  wire                          rst_n,             // Synchronous active-low reset
    input  wire                          enable,            // Block enable / clock enable
    input  wire                          detector_active,   // Active high after warmup is done
    input  wire                          peak_strobe,       // 1-cycle pulse from peak localizer
    input  wire [TIME_WIDTH-1:0]         raw_peak_in,       // Localized raw peak timestamp
    input  wire [TIME_WIDTH-1:0]         comp_peak_in,      // Compensated peak timestamp
    input  wire [DATA_WIDTH-1:0]         peak_val_in,       // Localized peak magnitude

    output reg                           beat_valid_strobe, // 1-cycle pulse on confirmed beat (Real / Held / First)
    output reg                           fused_strobe,      // 1-cycle pulse on fused beat event
    output reg                           rr_update_strobe,  // 1-cycle pulse when median RR is updated
    output reg  [TIME_WIDTH-1:0]         last_raw_peak_out, // Confirmed raw peak timestamp
    output reg  [TIME_WIDTH-1:0]         last_comp_peak_out,// Confirmed compensated peak timestamp
    output reg  [RR_WIDTH-1:0]           raw_rr_out,        // Current raw RR interval
    output reg  [RR_WIDTH-1:0]           med_rr_out,        // Pure integer median-5 RR interval
    output reg  [1:0]                    status_flag_2bit,  // 2-bit classification flag
    output reg  [15:0]                   n_fused_events     // Total count of merged split beats
);

    // -------------------------------------------------------------------------
    // Telemetry Status Flag Constants (Byte 6 bits 1:0)
    // -------------------------------------------------------------------------
    localparam [1:0] FLAG_REAL_DETECTED  = 2'b00;
    localparam [1:0] FLAG_FUSED_BEAT     = 2'b01;
    localparam [1:0] FLAG_HELD_FHR       = 2'b10;
    localparam [1:0] FLAG_INVALID_WARMUP = 2'b11;

    // -------------------------------------------------------------------------
    // Internal Registers & FIFO Buffer
    // -------------------------------------------------------------------------
    reg                  has_detected_beat;
    reg [TIME_WIDTH-1:0] last_raw_peak;
    reg [TIME_WIDTH-1:0] last_comp_peak;
    reg [DATA_WIDTH-1:0] last_peak_val;

    reg [RR_WIDTH-1:0]   median_fifo [0:4];
    reg [2:0]            fifo_count; // 0 to 5

    // -------------------------------------------------------------------------
    // Combinational Sorting Network for 1 to 5 values
    // -------------------------------------------------------------------------
    // Next candidate buffer contents upon normal beat push
    reg [RR_WIDTH-1:0] next_fifo [0:4];
    reg [2:0]          next_count;

    wire [RR_WIDTH-1:0] calc_rr;
    assign calc_rr = raw_peak_in - last_raw_peak;

    always @(*) begin
        if (fifo_count < 3'd5) begin
            next_count   = fifo_count + 3'd1;
            next_fifo[0] = median_fifo[0];
            next_fifo[1] = median_fifo[1];
            next_fifo[2] = median_fifo[2];
            next_fifo[3] = median_fifo[3];
            next_fifo[4] = median_fifo[4];
            next_fifo[fifo_count] = calc_rr;
        end else begin
            next_count   = 3'd5;
            next_fifo[0] = median_fifo[1];
            next_fifo[1] = median_fifo[2];
            next_fifo[2] = median_fifo[3];
            next_fifo[3] = median_fifo[4];
            next_fifo[4] = calc_rr;
        end
    end

    // -------------------------------------------------------------------------
    // Knuth Optimal 5-Element Sorting Network (9 comparators, depth 5)
    // Replaces 10-step bubble sort with static wire network (< 3 ns latency).
    // -------------------------------------------------------------------------
    function [31:0] cs;
        input [15:0] x;
        input [15:0] y;
        begin
            if (x <= y)
                cs = {y, x}; // [31:16] is max, [15:0] is min
            else
                cs = {x, y};
        end
    endfunction

    // Layer 0: inputs padded with 16'hFFFF so valid items sort to front
    wire [15:0] l0_0 = (next_count >= 3'd1) ? next_fifo[0] : 16'hFFFF;
    wire [15:0] l0_1 = (next_count >= 3'd2) ? next_fifo[1] : 16'hFFFF;
    wire [15:0] l0_2 = (next_count >= 3'd3) ? next_fifo[2] : 16'hFFFF;
    wire [15:0] l0_3 = (next_count >= 3'd4) ? next_fifo[3] : 16'hFFFF;
    wire [15:0] l0_4 = (next_count >= 3'd5) ? next_fifo[4] : 16'hFFFF;

    // Layer 1: cs(0,1), cs(3,4)
    wire [31:0] cs1_01 = cs(l0_0, l0_1);
    wire [31:0] cs1_34 = cs(l0_3, l0_4);
    wire [15:0] l1_0   = cs1_01[15:0];
    wire [15:0] l1_1   = cs1_01[31:16];
    wire [15:0] l1_2   = l0_2;
    wire [15:0] l1_3   = cs1_34[15:0];
    wire [15:0] l1_4   = cs1_34[31:16];

    // Layer 2: cs(2,4)
    wire [31:0] cs2_24 = cs(l1_2, l1_4);
    wire [15:0] l2_0   = l1_0;
    wire [15:0] l2_1   = l1_1;
    wire [15:0] l2_2   = cs2_24[15:0];
    wire [15:0] l2_3   = l1_3;
    wire [15:0] l2_4   = cs2_24[31:16];

    // Layer 3: cs(2,3), cs(1,4)
    wire [31:0] cs3_23 = cs(l2_2, l2_3);
    wire [31:0] cs3_14 = cs(l2_1, l2_4);
    wire [15:0] l3_0   = l2_0;
    wire [15:0] l3_1   = cs3_14[15:0];
    wire [15:0] l3_2   = cs3_23[15:0];
    wire [15:0] l3_3   = cs3_23[31:16];
    wire [15:0] l3_4   = cs3_14[31:16];

    // Layer 4: cs(0,3)
    wire [31:0] cs4_03 = cs(l3_0, l3_3);
    wire [15:0] l4_0   = cs4_03[15:0];
    wire [15:0] l4_1   = l3_1;
    wire [15:0] l4_2   = l3_2;
    wire [15:0] l4_3   = cs4_03[31:16];
    wire [15:0] l4_4   = l3_4;

    // Layer 5: cs(0,2), cs(1,3)
    wire [31:0] cs5_02 = cs(l4_0, l4_2);
    wire [31:0] cs5_13 = cs(l4_1, l4_3);
    wire [15:0] l5_0   = cs5_02[15:0];
    wire [15:0] l5_1   = cs5_13[15:0];
    wire [15:0] l5_2   = cs5_02[31:16];
    wire [15:0] l5_3   = cs5_13[31:16];
    wire [15:0] l5_4   = l4_4;

    // Layer 6: cs(1,2)
    wire [31:0] cs6_12 = cs(l5_1, l5_2);
    wire [15:0] s0     = l5_0;
    wire [15:0] s1     = cs6_12[15:0];
    wire [15:0] s2     = cs6_12[31:16];
    wire [15:0] s3     = l5_3;
    wire [15:0] s4     = l5_4;

    // Select integer median based on active count (exact match to Python)
    reg [RR_WIDTH-1:0] comb_median;
    always @(*) begin
        case (next_count)
            3'd1: comb_median = s0;
            3'd2: comb_median = (s0 + s1 + 16'd1) >> 1;
            3'd3: comb_median = s1;
            3'd4: comb_median = (s1 + s2 + 16'd1) >> 1;
            default: comb_median = s2; // 3'd5
        endcase
    end

    // -------------------------------------------------------------------------
    // Sequential Fusion & State Logic
    // -------------------------------------------------------------------------
    integer i;

    always @(posedge clk) begin
        if (!rst_n) begin
            beat_valid_strobe  <= 1'b0;
            fused_strobe       <= 1'b0;
            rr_update_strobe   <= 1'b0;
            has_detected_beat  <= 1'b0;
            last_raw_peak      <= {TIME_WIDTH{1'b0}};
            last_comp_peak     <= {TIME_WIDTH{1'b0}};
            last_peak_val      <= {DATA_WIDTH{1'b0}};
            last_raw_peak_out  <= {TIME_WIDTH{1'b0}};
            last_comp_peak_out <= {TIME_WIDTH{1'b0}};
            raw_rr_out         <= {RR_WIDTH{1'b0}};
            med_rr_out         <= 16'd107; // 107 samples ~ 140.0 bpm default
            status_flag_2bit   <= FLAG_INVALID_WARMUP;
            n_fused_events     <= 16'd0;
            fifo_count         <= 3'd0;
            for (i = 0; i < 5; i = i + 1) begin
                median_fifo[i] <= {RR_WIDTH{1'b0}};
            end
        end else if (enable) begin
            // Default 1-cycle strobe deassertions
            beat_valid_strobe <= 1'b0;
            fused_strobe      <= 1'b0;
            rr_update_strobe  <= 1'b0;

            // Handle transition out of warmup
            if (!detector_active) begin
                status_flag_2bit <= FLAG_INVALID_WARMUP;
            end

            if (peak_strobe && detector_active) begin
                if (!has_detected_beat) begin
                    // ── First Detected Beat ──────────────────────────────────
                    has_detected_beat  <= 1'b1;
                    last_raw_peak      <= raw_peak_in;
                    last_comp_peak     <= comp_peak_in;
                    last_peak_val      <= peak_val_in;
                    last_raw_peak_out  <= raw_peak_in;
                    last_comp_peak_out <= comp_peak_in;
                    raw_rr_out         <= {RR_WIDTH{1'b0}};
                    status_flag_2bit   <= FLAG_REAL_DETECTED;
                    beat_valid_strobe  <= 1'b1;
                end else begin
                    // ── Subsequent Beats ─────────────────────────────────────
                    if (calc_rr < RR_MIN) begin
                        // 1. True Interval Fusion: Merge Split Peak
                        n_fused_events   <= n_fused_events + 16'd1;
                        status_flag_2bit <= FLAG_FUSED_BEAT;
                        fused_strobe     <= 1'b1;

                        if (peak_val_in > last_peak_val) begin
                            // Split beat has higher amplitude: update peak location
                            last_raw_peak      <= raw_peak_in;
                            last_comp_peak     <= comp_peak_in;
                            last_peak_val      <= peak_val_in;
                            last_raw_peak_out  <= raw_peak_in;
                            last_comp_peak_out <= comp_peak_in;
                        end
                        // Do NOT push to median buffer!
                    end else if (calc_rr <= RR_MAX) begin
                        // 2. Normal Physiological Beat (50 <= RR <= 300)
                        last_raw_peak      <= raw_peak_in;
                        last_comp_peak     <= comp_peak_in;
                        last_peak_val      <= peak_val_in;
                        last_raw_peak_out  <= raw_peak_in;
                        last_comp_peak_out <= comp_peak_in;
                        raw_rr_out         <= calc_rr;
                        status_flag_2bit   <= FLAG_REAL_DETECTED;
                        beat_valid_strobe  <= 1'b1;

                        // Push to median-5 FIFO and update median RR
                        for (i = 0; i < 5; i = i + 1) begin
                            median_fifo[i] <= next_fifo[i];
                        end
                        fifo_count       <= next_count;
                        med_rr_out       <= comb_median;
                        rr_update_strobe <= 1'b1;
                    end else begin
                        // 3. Isolated Dropout / Bradycardia (RR > 300)
                        last_raw_peak      <= raw_peak_in;
                        last_comp_peak     <= comp_peak_in;
                        last_peak_val      <= peak_val_in;
                        last_raw_peak_out  <= raw_peak_in;
                        last_comp_peak_out <= comp_peak_in;
                        raw_rr_out         <= calc_rr;
                        status_flag_2bit   <= FLAG_HELD_FHR;
                        beat_valid_strobe  <= 1'b1;
                        // Hold previous valid FHR; do NOT push to median buffer
                    end
                end
            end
        end else begin
            beat_valid_strobe <= 1'b0;
            fused_strobe      <= 1'b0;
            rr_update_strobe  <= 1'b0;
        end
    end

endmodule
