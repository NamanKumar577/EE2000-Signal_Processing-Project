// =============================================================================
// Module: weight_slew_engine
// Description: 64-Sample Linear Crossfade Slew Engine for PCA Beamforming Weights.
//              Smoothly interpolates active spatial weights from w_old to w_target
//              over exactly 64 input samples, preventing sudden step transients
//              and filter ringing when calibration updates are received.
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Mathematical Recurrence:
//   For each channel c in [0..3]:
//     delta = w_target[c] - w_old[c]
//     step  = round_nearest_even((crossfade_step * delta) / 64)
//     w_curr[c] = sat(w_old[c] + step)
//   At step == 64:
//     w_curr[c] = w_target[c]
//
// Latency: Registered, updates w_curr on each sample_strobe
// =============================================================================

`timescale 1ns / 1ps

module weight_slew_engine #(
    parameter integer WEIGHT_WIDTH     = 17, // Signed 17-bit Q2.15 ([-32768, +32768])
    parameter integer CROSSFADE_STEPS  = 64  // Linear transition length
)(
    input  wire                               clk,                  // Master system clock
    input  wire                               rst_n,                // Synchronous active-low reset
    input  wire                               enable,               // Block enable
    input  wire                               sample_strobe,        // 1-cycle strobe at 250 Hz (sample arrival)
    input  wire                               weight_update_strobe, // 1-cycle strobe when new target weights arrive

    input  wire signed [WEIGHT_WIDTH-1:0]      target_w0,            // New target weight for CH0 (Q2.15)
    input  wire signed [WEIGHT_WIDTH-1:0]      target_w1,            // New target weight for CH1 (Q2.15)
    input  wire signed [WEIGHT_WIDTH-1:0]      target_w2,            // New target weight for CH2 (Q2.15)
    input  wire signed [WEIGHT_WIDTH-1:0]      target_w3,            // New target weight for CH3 (Q2.15)

    output reg  signed [WEIGHT_WIDTH-1:0]      w_curr0,              // Active slewed weight for CH0 (Q2.15)
    output reg  signed [WEIGHT_WIDTH-1:0]      w_curr1,              // Active slewed weight for CH1 (Q2.15)
    output reg  signed [WEIGHT_WIDTH-1:0]      w_curr2,              // Active slewed weight for CH2 (Q2.15)
    output reg  signed [WEIGHT_WIDTH-1:0]      w_curr3,              // Active slewed weight for CH3 (Q2.15)

    output wire                               crossfade_active,     // High while slewing (step < 64)
    output reg  [6:0]                         step_counter          // Current crossfade step (1 to 64)
);

    // Default unity initialization: w0 = +1.0 (exact +32768 in Q1.15), w1..3 = 0.0
    localparam signed [WEIGHT_WIDTH-1:0] UNITY_W0 = 17'sd32768;

    // Internal state registers
    reg signed [WEIGHT_WIDTH-1:0] w_old0, w_old1, w_old2, w_old3;
    reg signed [WEIGHT_WIDTH-1:0] w_tgt0, w_tgt1, w_tgt2, w_tgt3;

    assign crossfade_active = (step_counter < CROSSFADE_STEPS);

    // -------------------------------------------------------------------------
    // Combinational Crossfade Arithmetic for all 4 channels
    // -------------------------------------------------------------------------
    function signed [WEIGHT_WIDTH-1:0] calc_slew_step;
        input signed [WEIGHT_WIDTH-1:0] w_old;
        input signed [WEIGHT_WIDTH-1:0] w_tgt;
        input [6:0]                     step_idx;
        
        reg signed [18:0] delta;
        reg signed [7:0]  step_s;
        reg signed [26:0] prod;
        reg signed [20:0] q;
        reg [5:0]         rem;
        reg signed [20:0] step_round;
        reg signed [20:0] w_raw;
        begin
            delta      = $signed({{2{w_tgt[WEIGHT_WIDTH-1]}}, w_tgt}) - $signed({{2{w_old[WEIGHT_WIDTH-1]}}, w_old});
            step_s     = $signed({1'b0, step_idx});
            prod       = step_s * delta;
            q          = prod >>> 6;
            rem        = prod[5:0];
            
            // Convergent rounding to nearest even
            if (rem > 6'd32)
                step_round = q + 21'sd1;
            else if (rem < 6'd32)
                step_round = q;
            else
                step_round = q + (q[0] ? 21'sd1 : 21'sd0);

            w_raw = $signed({{4{w_old[WEIGHT_WIDTH-1]}}, w_old}) + step_round;

            // Clamping to Signed range [-32768, 32768]
            if (w_raw > 21'sd32768)
                calc_slew_step = 17'sd32768;
            else if (w_raw < -21'sd32768)
                calc_slew_step = -17'sd32768;
            else
                calc_slew_step = w_raw[WEIGHT_WIDTH-1:0];
        end
    endfunction

    // -------------------------------------------------------------------------
    // Sequential State Logic
    // -------------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            w_curr0      <= UNITY_W0;
            w_curr1      <= 17'sd0;
            w_curr2      <= 17'sd0;
            w_curr3      <= 17'sd0;
            w_old0       <= UNITY_W0;
            w_old1       <= 17'sd0;
            w_old2       <= 17'sd0;
            w_old3       <= 17'sd0;
            w_tgt0       <= UNITY_W0;
            w_tgt1       <= 17'sd0;
            w_tgt2       <= 17'sd0;
            w_tgt3       <= 17'sd0;
            step_counter <= 7'd64; // Settled
        end else if (enable) begin
            if (weight_update_strobe) begin
                // Latch current active weights as old baseline, set new targets
                w_old0       <= w_curr0;
                w_old1       <= w_curr1;
                w_old2       <= w_curr2;
                w_old3       <= w_curr3;
                w_tgt0       <= target_w0;
                w_tgt1       <= target_w1;
                w_tgt2       <= target_w2;
                w_tgt3       <= target_w3;
                step_counter <= 7'd1; // Begin 64-sample transition
            end else if (sample_strobe) begin
                if (step_counter < CROSSFADE_STEPS) begin
                    step_counter <= step_counter + 7'd1;
                    w_curr0      <= calc_slew_step(w_old0, w_tgt0, step_counter + 7'd1);
                    w_curr1      <= calc_slew_step(w_old1, w_tgt1, step_counter + 7'd1);
                    w_curr2      <= calc_slew_step(w_old2, w_tgt2, step_counter + 7'd1);
                    w_curr3      <= calc_slew_step(w_old3, w_tgt3, step_counter + 7'd1);
                end else if (step_counter == CROSSFADE_STEPS) begin
                    w_curr0      <= w_tgt0;
                    w_curr1      <= w_tgt1;
                    w_curr2      <= w_tgt2;
                    w_curr3      <= w_tgt3;
                end
            end
        end
    end

endmodule
