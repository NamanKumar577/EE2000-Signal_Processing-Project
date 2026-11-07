// =============================================================================
// Module: peak_localizer
// Description: Trailing R-Peak Localization & Timestamp Correction Engine.
//              Upon assertion of candidate_strobe by the adaptive detector,
//              searches backward through a trailing window of W = 26 samples
//              (104 ms at 250 Hz) of absolute bandpass energy |bp16| to find
//              the true R-peak apex index (best_idx) and magnitude (best_val).
//              Computes group-delay latency compensated timestamp:
//                comp_peak = max(0, best_idx - LATENCY_COMP)
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Mathematical Model:
//   lo = max(0, t - (LOC_WINDOW - 1))
//   best_idx = lo, best_val = |bp16[lo]|
//   for i in range(lo + 1, t + 1):
//       if |bp16[i]| > best_val:
//           best_val = |bp16[i]|
//           best_idx = i
//   comp_peak = max(0, best_idx - LATENCY_COMP)
//
// Latency: 1 clock cycle after candidate_strobe assertion
// =============================================================================

`timescale 1ns / 1ps

module peak_localizer #(
    parameter integer DATA_WIDTH   = 16,        // Signed 16-bit Q12 bandpass input
    parameter integer TIME_WIDTH   = 24,        // Timestamp counter width (24 bits)
    parameter integer LOC_WINDOW   = 26,        // Trailing search window length
    parameter integer LATENCY_COMP = 13         // Group delay compensation samples (Config C @ 20-30 Hz)
)(
    input  wire                          clk,               // Master system clock (100 MHz)
    input  wire                          rst_n,             // Synchronous active-low reset
    input  wire                          enable,            // Block enable / clock enable
    input  wire                          valid_in,          // 1-cycle sample strobe at sample t
    input  wire [TIME_WIDTH-1:0]         t_in,              // Global sample counter at sample t
    input  wire signed [DATA_WIDTH-1:0]  bp16_in,           // Bandpass output at sample t
    input  wire                          candidate_strobe,  // Pulse from adaptive detector

    output reg                           peak_strobe,       // 1-cycle pulse when localized peak is output
    output reg  [TIME_WIDTH-1:0]         raw_peak_out,      // Uncompensated R-peak timestamp (best_idx)
    output reg  [TIME_WIDTH-1:0]         comp_peak_out,     // Group-delay compensated timestamp
    output reg  [DATA_WIDTH-1:0]         peak_val_out       // Absolute peak magnitude |bp16|
);

    // -------------------------------------------------------------------------
    // Compute Absolute Value of Signed 16-bit Bandpass Input
    // |bp16| in [0, 32768]. Fits in 16-bit unsigned (16'h8000 for -32768).
    // -------------------------------------------------------------------------
    wire [DATA_WIDTH-1:0] abs_curr;
    assign abs_curr = (bp16_in < 16'sd0) ? 
                      ((bp16_in == -16'sd32768) ? 16'h8000 : $unsigned(-bp16_in)) :
                      $unsigned(bp16_in);

    // -------------------------------------------------------------------------
    // 26-Sample History Shift Register: abs_window[0] = t, abs_window[25] = t-25
    // -------------------------------------------------------------------------
    reg [DATA_WIDTH-1:0] abs_window [0:LOC_WINDOW-1];
    integer idx;

    // Latched timestamp corresponding to sample t
    reg [TIME_WIDTH-1:0] t_latched;

    // -------------------------------------------------------------------------
    // Balanced Binary Reduction Tree for Window Peak Search
    // Replaces 26-element serial loop with 5-level parallel comparator tree.
    // Achieves bit-identical results with < 3 ns propagation delay (meeting 100 MHz).
    // Node format: [21] = valid bit, [20:5] = 16b val, [4:0] = 5b k (offset)
    // -------------------------------------------------------------------------
    function [21:0] pick_winner;
        input [21:0] older_node; // larger k (earlier timestamp)
        input [21:0] newer_node; // smaller k (later timestamp)
        begin
            if (newer_node[21:5] > older_node[21:5])
                pick_winner = newer_node;
            else
                pick_winner = older_node;
        end
    endfunction

    reg [4:0] valid_len_reg;
    wire [4:0] valid_len = valid_len_reg;

    // Level 0: 26 leaf nodes (ordered oldest k=25 to newest k=0)
    wire [21:0] tree_L0 [0:25];
    genvar gi;
    generate
        for (gi = 0; gi < 26; gi = gi + 1) begin : gen_leaf
            wire [4:0] k_val = 5'd25 - gi[4:0];
            wire       is_vld = (k_val <= valid_len);
            assign tree_L0[gi] = {is_vld, abs_window[k_val], k_val};
        end
    endgenerate

    // Level 1: 13 winner nodes
    wire [21:0] tree_L1 [0:12];
    generate
        for (gi = 0; gi < 13; gi = gi + 1) begin : gen_l1
            assign tree_L1[gi] = pick_winner(tree_L0[2*gi], tree_L0[2*gi + 1]);
        end
    endgenerate

    // Level 2: 7 winner nodes (6 pairs + 1 passthrough)
    wire [21:0] tree_L2 [0:6];
    generate
        for (gi = 0; gi < 6; gi = gi + 1) begin : gen_l2
            assign tree_L2[gi] = pick_winner(tree_L1[2*gi], tree_L1[2*gi + 1]);
        end
    endgenerate
    assign tree_L2[6] = tree_L1[12];

    // Level 3: 4 winner nodes (3 pairs + 1 passthrough)
    wire [21:0] tree_L3 [0:3];
    generate
        for (gi = 0; gi < 3; gi = gi + 1) begin : gen_l3
            assign tree_L3[gi] = pick_winner(tree_L2[2*gi], tree_L2[2*gi + 1]);
        end
    endgenerate
    assign tree_L3[3] = tree_L2[6];

    // Level 4: 2 winner nodes
    wire [21:0] tree_L4 [0:1];
    assign tree_L4[0] = pick_winner(tree_L3[0], tree_L3[1]);
    assign tree_L4[1] = pick_winner(tree_L3[2], tree_L3[3]);

    // Level 5: 1 winner (root)
    wire [21:0] tree_winner;
    assign tree_winner = pick_winner(tree_L4[0], tree_L4[1]);

    wire [4:0]            comb_best_k;
    wire [DATA_WIDTH-1:0] comb_best_val;
    assign comb_best_k   = tree_winner[4:0];
    assign comb_best_val = tree_winner[20:5];

    // Calculated peak indices evaluated in parallel
    wire [5:0]            total_comp_offset;
    wire [TIME_WIDTH-1:0] calc_raw_peak;
    wire [TIME_WIDTH-1:0] calc_comp_peak;

    assign total_comp_offset = comb_best_k + LATENCY_COMP[5:0];   // was hard-coded 6'd18 (parameter ignored)
    assign calc_raw_peak     = (t_latched >= comb_best_k) ? (t_latched - comb_best_k) : {TIME_WIDTH{1'b0}};
    assign calc_comp_peak    = (t_latched >= total_comp_offset) ? (t_latched - total_comp_offset) : {TIME_WIDTH{1'b0}};

    // -------------------------------------------------------------------------
    // Sequential Shift Register & Strobe Processing
    // -------------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            peak_strobe   <= 1'b0;
            raw_peak_out  <= {TIME_WIDTH{1'b0}};
            comp_peak_out <= {TIME_WIDTH{1'b0}};
            peak_val_out  <= {DATA_WIDTH{1'b0}};
            t_latched     <= {TIME_WIDTH{1'b0}};
            valid_len_reg <= 5'd0;
            for (idx = 0; idx < LOC_WINDOW; idx = idx + 1) begin
                abs_window[idx] <= {DATA_WIDTH{1'b0}};
            end
        end else if (enable) begin
            // Default 1-cycle pulse deassertion
            peak_strobe <= 1'b0;

            // Shift history buffer when a new sample strobe arrives
            if (valid_in) begin
                t_latched     <= t_in;
                abs_window[0] <= abs_curr;
                for (idx = 1; idx < LOC_WINDOW; idx = idx + 1) begin
                    abs_window[idx] <= abs_window[idx-1];
                end
                if (valid_len_reg < 5'd25)
                    valid_len_reg <= valid_len_reg + 5'd1;
            end

            // When candidate detector declares a peak, register the localized maximum
            if (candidate_strobe) begin
                peak_strobe   <= 1'b1;
                raw_peak_out  <= calc_raw_peak;
                comp_peak_out <= calc_comp_peak;
                peak_val_out  <= comb_best_val;
            end
        end else begin
            peak_strobe <= 1'b0;
        end
    end

endmodule
