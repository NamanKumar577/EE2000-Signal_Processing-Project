// FECG v6 - time-multiplexed adaptive-threshold peak detectors (det_step in the C
// model, integer): warm-up 512 samples, threshold 0.25 peak + 0.75 noise (1/8 EMAs),
// refractory, localisation on |y| over the last `loc` samples, merging of peaks
// closer than rr_min, finalisation once the pending peak can no longer be replaced.
`timescale 1ns / 1ps

module v6_det #(parameter integer NINST = 4) (
    input  wire               clk,
    input  wire               init,         // pulse: initialise instance inst
    input  wire signed [31:0] i_start,      // det_start
    input  wire [7:0]         i_refr, i_loc, i_rrmin,
    input  wire               start,        // pulse: one step
    input  wire [2:0]         inst,
    input  wire signed [31:0] t,
    input  wire signed [63:0] e,
    input  wire signed [63:0] ab,
    output reg                done,
    output reg  signed [31:0] out           // final peak or -1
);
    reg signed [31:0] dstart [0:NINST-1];
    reg signed [31:0] refr [0:NINST-1], loc [0:NINST-1], rrmin [0:NINST-1];
    reg signed [63:0] peak [0:NINST-1], noise [0:NINST-1], wmax [0:NINST-1], wsum [0:NINST-1];
    reg signed [63:0] e1 [0:NINST-1], e2 [0:NINST-1], pendv [0:NINST-1];
    reg        en [0:NINST-1];
    reg signed [31:0] last [0:NINST-1], pend [0:NINST-1];
    reg signed [63:0] ring [0:NINST*32-1];
    reg [7:0]  ra, wa; reg we; reg signed [63:0] wd, rd;
    always @(posedge clk) begin if (we) ring[wa] <= wd; rd <= ring[ra]; end

    reg [3:0] s = 0;
    reg [2:0] k;
    reg signed [31:0] tv, lo, i, best, o;
    reg signed [63:0] ev, v, vp, thr, bv;
    reg [5:0] cnt;
    always @(posedge clk) begin
        we <= 1'b0; done <= 1'b0;
        case (s)
        0: if (init) begin
               k <= inst; dstart[inst] <= i_start; refr[inst] <= $signed({24'd0, i_refr}); loc[inst] <= $signed({24'd0, i_loc}); rrmin[inst] <= $signed({24'd0, i_rrmin});
               peak[inst] <= 0; noise[inst] <= 0; wmax[inst] <= 0; wsum[inst] <= 0;
               e1[inst] <= 0; e2[inst] <= 0; pendv[inst] <= 0; en[inst] <= 0;
               last[inst] <= -32'sd1000000000; pend[inst] <= -32'sd1;
               cnt <= 0; s <= 1;
           end else if (start) begin
               k <= inst; tv <= t; ev <= e; o <= -32'sd1;
               we <= 1'b1; wa <= {inst, t[4:0]}; wd <= ab;
               s <= 2;
           end
        1: begin                                                     // clear the |y| ring
            we <= 1'b1; wa <= {k, cnt[4:0]}; wd <= 0;
            if (cnt == 31) s <= 15; else cnt <= cnt + 1'b1;
        end
        2: begin
            v = e1[k]; vp = e2[k];
            thr = (peak[k] + 3 * noise[k]) >>> 2;
            if (tv >= dstart[k]) begin
                if (tv < dstart[k] + 512) begin
                    if (ev > wmax[k]) wmax[k] <= ev;
                    wsum[k] <= wsum[k] + ev;
                    if (tv == dstart[k] + 511) begin
                        peak[k] <= (ev > wmax[k]) ? ev : wmax[k];
                        noise[k] <= (wsum[k] + ev) >>> 9;
                        en[k] <= ((ev > wmax[k]) ? ev : wmax[k]) > ((wsum[k] + ev) >>> 9);
                    end
                    s <= 8;
                end else if (en[k] && tv >= 2 && vp < v && v >= ev) begin
                    if (v > thr && (tv - 1) - last[k] >= refr[k]) begin
                        lo = tv - (loc[k] - 1); if (lo < 0) lo = 0;
                        i <= lo + 1; best <= lo; ra <= {k, lo[4:0]};
                        s <= 3;
                    end else begin
                        if (v <= thr) noise[k] <= noise[k] + ((v - noise[k]) >>> 3);
                        s <= 8;
                    end
                end else s <= 8;
            end else s <= 8;
        end
        3: begin ra <= {k, i[4:0]}; s <= 4; end                       // wait for ab[lo]
        4: begin bv <= rd; ra <= {k, i[4:0] + 5'd1}; s <= 5; end        // rd = ab[lo]
        5: begin                                                      // rd = ab[i]
            if (i <= tv) begin
                if (rd > bv) begin bv <= rd; best <= i; end
                i <= i + 1; ra <= {k, i[4:0] + 5'd2};
            end else s <= 6;
        end
        6: begin
            if (pend[k] >= 0 && best - pend[k] < rrmin[k]) begin
                if (bv > pendv[k]) begin pend[k] <= best; pendv[k] <= bv; end
            end else begin
                o <= pend[k]; pend[k] <= best; pendv[k] <= bv;
            end
            last[k] <= tv - 1;
            peak[k] <= peak[k] + ((e1[k] - peak[k]) >>> 3);
            s <= 8;
        end
        8: begin
            e2[k] <= e1[k]; e1[k] <= ev;
            s <= 9;
        end
        9: begin
            if (o < 0 && pend[k] >= 0 && tv - (loc[k] - 1) - pend[k] >= rrmin[k]) begin
                out <= pend[k]; pend[k] <= -32'sd1;
            end else out <= o;
            done <= 1'b1; s <= 0;
        end
        15: begin done <= 1'b1; s <= 0; end
        default: s <= 0;
        endcase
    end
endmodule
