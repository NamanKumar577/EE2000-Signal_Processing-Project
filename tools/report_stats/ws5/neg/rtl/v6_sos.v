// FECG v6 - time-multiplexed second-order-section cascade (DF2T), bit-exact with
// sos_q() in the C model:  y = rnd(b0 x + z1, 28); z1 = b1 x - a1 y + z2; z2 = b2 x - a2 y
// Filter sets (Q28): 0 = LP (2 sections), 1 = MAT (2), 2 = BP (4).
// State of instance i, section s: z1 at i*8+s*2, z2 at i*8+s*2+1 (64-bit words).
`timescale 1ns / 1ps

module v6_sos #(parameter integer NINST = 8) (
    input  wire               clk,
    input  wire               clear,        // pulse: zero all state (takes NINST*8 cycles)
    input  wire               start,        // pulse: filter one sample
    input  wire [4:0]         inst,
    input  wire [1:0]         fset,
    input  wire signed [31:0] x,
    input  wire               copy,         // pulse: copy state of inst copy_from -> inst
    input  wire [4:0]         copy_from,
    output reg                busy,
    output reg                done,         // 1-cycle pulse when finished
    output reg  signed [31:0] y
);
    localparam integer NW = NINST * 8;
    reg signed [63:0] st [0:NW-1];
    reg [8:0] addr;
    reg signed [63:0] rd;
    reg        we;
    reg [8:0]  wa;
    reg signed [63:0] wd;
    always @(posedge clk) begin
        if (we) st[wa] <= wd;
        rd <= st[addr];
    end

    // coefficient ROM: index fset*20 + sec*5 + k (b0 b1 b2 a1 a2)
    function signed [31:0] coef(input [1:0] f, input [1:0] s, input [2:0] k);
        reg [5:0] i;
        begin
            i = f * 20 + s * 5 + k;
            case (i)
            // LP
            0: coef = 22192263;  1: coef = 44384525;  2: coef = 22192263;  3: coef = -17538717; 4: coef = 10885636;
            5: coef = 268435456; 6: coef = 536870912; 7: coef = 268435456; 8: coef = -24393743; 9: coef = 120058588;
            // MAT
            20: coef = 12383411;  21: coef = 24766823;   22: coef = 12383411;  23: coef = -356959220; 24: coef = 152844523;
            25: coef = 268435456; 26: coef = -536870912; 27: coef = 268435456; 28: coef = -495263578; 29: coef = 231861802;
            // BP
            40: coef = 1295025;   41: coef = 2590050;    42: coef = 1295025;   43: coef = -281841220; 44: coef = 129027493;
            45: coef = 268435456; 46: coef = 536870912;  47: coef = 268435456; 48: coef = -381159569; 49: coef = 165384610;
            50: coef = 268435456; 51: coef = -536870912; 52: coef = 268435456; 53: coef = -258219510; 54: coef = 195860243;
            55: coef = 268435456; 56: coef = -536870912; 57: coef = 268435456; 58: coef = -464003324; 59: coef = 232786574;
            default: coef = 0;
            endcase
        end
    endfunction

    reg [3:0]  ph;
    reg [1:0]  sec, nsec, f;
    reg [4:0]  ins, src;
    reg [8:0]  cnt;
    reg signed [31:0] xv, yv;
    reg signed [63:0] z2v, acc;
    reg signed [31:0] ma, mb;
    reg signed [63:0] prod;
    always @(posedge clk) prod <= ma * mb;
    wire [8:0] base = {ins, sec, 1'b0};

    localparam S_IDLE = 0, S_CLR = 1, S_RD = 2, S_M0 = 3, S_Y = 4, S_M1 = 5, S_M2 = 6, S_Z1 = 7,
               S_M3 = 8, S_M4 = 9, S_Z2 = 10, S_CP0 = 11, S_CP1 = 12, S_W = 13;
    reg [3:0] s = S_IDLE;
    always @(posedge clk) begin
        we <= 1'b0;
        done <= 1'b0;
        case (s)
        S_IDLE: begin
            busy <= 1'b0;
            if (clear) begin cnt <= 0; busy <= 1'b1; s <= S_CLR; end
            else if (start) begin
                busy <= 1'b1; ins <= inst; f <= fset; nsec <= (fset == 2) ? 2'd3 : 2'd1;
                sec <= 0; xv <= x; s <= S_RD;
            end else if (copy) begin
                busy <= 1'b1; ins <= inst; src <= copy_from; cnt <= 0; s <= S_CP0;
            end
        end
        S_CLR: begin
            we <= 1'b1; wa <= cnt; wd <= 0;
            if (cnt == NW - 1) s <= S_W; else cnt <= cnt + 1'b1;
        end
        S_RD: begin addr <= base; ma <= coef(f, sec, 0); mb <= xv; s <= S_M0; end      // read z1, b0*x
        S_M0: begin addr <= base + 1'b1; s <= S_Y; end                               // wait product, read z2
        S_Y: begin                                                                    // prod = b0 x, rd = z1
            yv <= (prod + rd + 64'sd134217728) >>> 28;
            ma <= coef(f, sec, 1); mb <= xv;                                          // b1*x
            s <= S_M1;
        end
        S_M1: begin z2v <= rd; ma <= coef(f, sec, 3); mb <= yv; s <= S_M2; end        // a1*y
        S_M2: begin acc <= prod; ma <= coef(f, sec, 2); mb <= xv; s <= S_Z1; end      // prod = b1 x ; b2*x
        S_Z1: begin                                                                   // prod = a1 y
            we <= 1'b1; wa <= base; wd <= acc - prod + z2v;
            ma <= coef(f, sec, 4); mb <= yv;                                          // a2*y
            s <= S_M3;
        end
        S_M3: begin acc <= prod; s <= S_M4; end                                       // prod = b2 x
        S_M4: begin                                                                   // prod = a2 y
            we <= 1'b1; wa <= base + 1'b1; wd <= acc - prod;
            if (sec == nsec) begin y <= yv; s <= S_W; end
            else begin sec <= sec + 1'b1; xv <= yv; s <= S_RD; end
        end
        S_CP0: begin addr <= {src, cnt[2:0]}; s <= S_CP1; end
        S_CP1: s <= S_Z2;
        S_Z2: begin                                                                   // copy word
            we <= 1'b1; wa <= {ins, cnt[2:0]}; wd <= rd;
            if (cnt == 7) s <= S_W; else begin cnt <= cnt + 1'b1; s <= S_CP0; end
        end
        S_W: begin done <= 1'b1; s <= S_IDLE; end                                                           // busy drops next cycle
        default: s <= S_IDLE;
        endcase
    end
endmodule
