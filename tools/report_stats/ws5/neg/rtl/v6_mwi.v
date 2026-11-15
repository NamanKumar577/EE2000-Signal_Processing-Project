// FECG v6 - time-multiplexed moving-window integrators (mwi_q in the C model):
// sum += sq - r[i]; r[i] = sq; i = (i + 1) mod w.   Ring of instance n at n*64 + i.
`timescale 1ns / 1ps

module v6_mwi #(parameter integer NINST = 8) (
    input  wire               clk,
    input  wire               clear,        // pulse: zero all rings / sums / indices
    input  wire               start,        // pulse: one step of instance inst
    input  wire [4:0]         inst,
    input  wire [5:0]         w,            // window length (<= 40)
    input  wire signed [63:0] sq,
    input  wire               copy,         // pulse: copy instance copy_from -> inst
    input  wire [4:0]         copy_from,
    output reg                done,
    output reg  signed [63:0] sum
);
    reg signed [63:0] ring [0:NINST*64-1];
    reg signed [63:0] sums [0:NINST-1];
    reg [5:0]  idx [0:NINST-1];
    reg [10:0] addr, wa;
    reg        we;
    reg signed [63:0] wd, rd;
    always @(posedge clk) begin
        if (we) ring[wa] <= wd;
        rd <= ring[addr];
    end
    reg [3:0]  s = 0;
    reg [10:0] cnt;
    reg [4:0]  ins, src;
    reg [5:0]  wl;
    reg signed [63:0] sqv;
    always @(posedge clk) begin
        we <= 1'b0; done <= 1'b0;
        case (s)
        0: if (clear) begin cnt <= 0; s <= 1; end
           else if (start) begin ins <= inst; wl <= w; sqv <= sq; addr <= {inst, idx[inst]}; s <= 2; end
           else if (copy) begin ins <= inst; src <= copy_from; cnt <= 0; s <= 5; end
        1: begin
            we <= 1'b1; wa <= cnt; wd <= 0;
            if (cnt < NINST) begin sums[cnt] <= 0; idx[cnt] <= 0; end
            if (cnt == NINST * 64 - 1) s <= 9; else cnt <= cnt + 1'b1;
        end
        2: s <= 3;                                                   // BRAM latency
        3: begin
            sum <= sums[ins] + sqv - rd;
            sums[ins] <= sums[ins] + sqv - rd;
            we <= 1'b1; wa <= {ins, idx[ins]}; wd <= sqv;
            idx[ins] <= (idx[ins] + 1'b1 == wl) ? 6'd0 : idx[ins] + 1'b1;
            s <= 9;
        end
        // copy: 40 ring words + sum + index
        5: begin addr <= {src, cnt[5:0]}; s <= 6; end
        6: s <= 7;
        7: begin
            we <= 1'b1; wa <= {ins, cnt[5:0]}; wd <= rd;
            if (cnt == 39) begin sums[ins] <= sums[src]; idx[ins] <= idx[src]; s <= 9; end
            else begin cnt <= cnt + 1'b1; s <= 5; end
        end
        9: begin done <= 1'b1; s <= 0; end
        default: s <= 0;
        endcase
    end
endmodule
