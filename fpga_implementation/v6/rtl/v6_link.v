// FECG v6 - link layer: downlink frame parser (samples FIFO + PC response buffers)
// and uplink message writer (header / payload words / xor) with a TX byte FIFO.
// Frame: A5 5A cmd len_lo len_hi payload xor(cmd, len_lo, len_hi, payload)
`timescale 1ns / 1ps

module v6_link (
    input  wire        clk,
    input  wire        rst,
    // UART byte interfaces
    input  wire [7:0]  rx_data,
    input  wire        rx_valid,
    output wire [7:0]  tx_data,
    output wire        tx_valid,
    input  wire        tx_ready,
    // samples FIFO (read side)
    output wire        smp_empty,
    input  wire        smp_pop,
    output wire [63:0] smp_x,          // 4 x s16, lead 0 in [15:0]
    output wire        smp_last,       // last sample of its SAMPLES frame
    output reg         soft_reset,     // RESET frame received (1-cycle pulse)
    output reg         err,            // sticky: checksum error / FIFO overflow
    // PC responses
    output reg         v_valid,  input wire v_clr,
    output reg  [255:0] v_q,           // 16 x s16 Q14, index k*4+l at [16*(k*4+l) +: 16]
    output reg         mk_valid, input wire mk_clr,
    output reg  [1:0]  mk,
    output reg         basis_valid, input wire basis_clr,
    output reg  [7:0]  basis_nb,       // 4 x 2-bit: nb of lead l at [2l +: 2]
    input  wire [10:0] basis_raddr,    // l*450 + c*150 + i
    output reg  signed [23:0] basis_rdata,
    output reg         cal_valid, input wire cal_clr,
    output reg  [4:0]  cal_ntr,
    output reg  [15:0] cal_kind, cal_src, cal_blank,
    output reg  [1023:0] cal_w,        // 16 tracks x 4 x s16 Q14 at [64k+16l +: 16]
    output reg         sel_valid, input wire sel_clr,
    output reg  [3:0]  sel,
    // uplink message writer
    input  wire        msg_start,      // accepted when msg_idle
    input  wire [7:0]  msg_cmd,
    input  wire [15:0] msg_len,
    output wire        msg_idle,
    input  wire        w_valid,        // payload word, LSB first, w_nb bytes (1..8)
    input  wire [63:0] w_data,
    input  wire [3:0]  w_nb,
    output wire        w_ready
);
    // ------------------------------------------------------------------ RX parser
    localparam P_H1 = 0, P_H2 = 1, P_CMD = 2, P_LLO = 3, P_LHI = 4, P_PAY = 5, P_CHK = 6;
    reg [2:0]  ps = P_H1;
    reg [7:0]  pcmd, pxor;
    reg [15:0] plen, pi;
    // samples
    reg [63:0] sbuf;
    reg [2:0]  sbyte;
    reg [15:0] sidx, snum;
    // sample FIFO: 512 x 65
    reg [64:0] sfifo [0:511];
    reg [9:0]  swp = 0, srp = 0;
    wire [9:0] scount = swp - srp;
    assign smp_empty = (scount == 0);
    reg [64:0] sout;
    assign smp_x = sout[63:0];
    assign smp_last = sout[64];
    // FIFO head kept in a register (first-word-fall-through)
    always @(posedge clk) sout <= sfifo[srp[8:0]];
    // basis RAM: 1800 x 24
    reg signed [23:0] bram [0:2047];
    reg [10:0] bwa;
    reg [23:0] bw;
    reg        bwe;
    reg [1:0]  bl, bc;
    reg [7:0]  bi;
    reg [1:0]  bbyte;
    always @(posedge clk) begin
        if (bwe) bram[bwa] <= bw;
        basis_rdata <= bram[basis_raddr];
    end
    // cal parser counters
    reg [4:0] ck;
    reg [3:0] co;
    reg [7:0] clo;

    function [1:0] nbl(input [7:0] nb, input [1:0] l); nbl = nb[2*l +: 2]; endfunction

    reg spush;
    reg [64:0] sdin;
    always @(posedge clk) begin
        soft_reset <= 1'b0;
        bwe <= 1'b0;
        spush <= 1'b0;
        if (spush) begin sfifo[swp[8:0]] <= sdin; swp <= swp + 1'b1; if (scount == 10'd512) err <= 1'b1; end
        if (smp_pop && !smp_empty) srp <= srp + 1'b1;
        if (v_clr) v_valid <= 1'b0;
        if (mk_clr) mk_valid <= 1'b0;
        if (basis_clr) basis_valid <= 1'b0;
        if (cal_clr) cal_valid <= 1'b0;
        if (sel_clr) sel_valid <= 1'b0;
        if (rst) begin
            ps <= P_H1; err <= 1'b0;
            swp <= 0; srp <= 0;
            v_valid <= 0; mk_valid <= 0; basis_valid <= 0; cal_valid <= 0; sel_valid <= 0;
        end else if (rx_valid) begin
            case (ps)
            P_H1: if (rx_data == 8'hA5) ps <= P_H2;
            P_H2: ps <= (rx_data == 8'h5A) ? P_CMD : (rx_data == 8'hA5 ? P_H2 : P_H1);
            P_CMD: begin pcmd <= rx_data; pxor <= rx_data; ps <= P_LLO; end
            P_LLO: begin plen[7:0] <= rx_data; pxor <= pxor ^ rx_data; ps <= P_LHI; end
            P_LHI: begin
                plen[15:8] <= rx_data; pxor <= pxor ^ rx_data; pi <= 0;
                sbyte <= 0; sidx <= 0; snum <= {rx_data, plen[7:0]} >> 3;
                bbyte <= 0; bi <= 0; bc <= 0; bl <= 0;
                ck <= 0; co <= 0;
                ps <= ({rx_data, plen[7:0]} == 16'd0) ? P_CHK : P_PAY;
            end
            P_PAY: begin
                pxor <= pxor ^ rx_data;
                pi <= pi + 1'b1;
                if (pi + 1'b1 == plen) ps <= P_CHK;
                case (pcmd)
                8'h02: begin                                          // SAMPLES
                    sbuf <= {rx_data, sbuf[63:8]};
                    sbyte <= sbyte + 1'b1;
                    if (sbyte == 3'd7) begin
                        sdin <= {(sidx + 1'b1 == snum), rx_data, sbuf[63:8]};
                        spush <= 1'b1;
                        sidx <= sidx + 1'b1;
                    end
                end
                8'h10: v_q[8 * pi +: 8] <= rx_data;                    // RSP_V
                8'h11: mk <= rx_data[1:0];                             // RSP_MK
                8'h12: begin                                          // RSP_BASIS
                    if (pi < 4) begin
                        basis_nb[2 * pi[1:0] +: 2] <= rx_data[1:0];
                        if (pi == 3) begin                             // first lead with nb > 0
                            if (basis_nb[1:0] != 0) bl <= 0;
                            else if (basis_nb[3:2] != 0) bl <= 1;
                            else if (basis_nb[5:4] != 0) bl <= 2;
                            else bl <= 3;
                        end
                    end else begin
                        bw <= {rx_data, bw[23:8]};
                        bbyte <= (bbyte == 2) ? 2'd0 : bbyte + 1'b1;
                        if (bbyte == 2) begin
                            bwe <= 1'b1;
                            bwa <= bl * 11'd450 + bc * 11'd150 + bi;
                            bw <= {rx_data, bw[23:8]};
                            if (bi == 149) begin
                                bi <= 0;
                                if (bc + 1'b1 == nbl(basis_nb, bl)) begin
                                    bc <= 0;
                                    // next lead with nb > 0
                                    if (bl < 1 && basis_nb[3:2] != 0) bl <= 1;
                                    else if (bl < 2 && basis_nb[5:4] != 0) bl <= 2;
                                    else bl <= 3;
                                end else bc <= bc + 1'b1;
                            end else bi <= bi + 1'b1;
                        end
                    end
                end
                8'h13: begin                                          // RSP_CAL
                    if (pi == 0) cal_ntr <= rx_data[4:0];
                    else begin
                        case (co)
                        0: cal_kind[ck] <= rx_data[0];
                        1: cal_src[ck] <= rx_data[0];
                        2: cal_blank[ck] <= rx_data[0];
                        3, 5, 7, 9: clo <= rx_data;
                        default: cal_w[64 * ck + 16 * ((co - 4) >> 1) +: 16] <= {rx_data, clo};
                        endcase
                        if (co == 10) begin co <= 0; ck <= ck + 1'b1; end else co <= co + 1'b1;
                    end
                end
                8'h14: sel <= rx_data[3:0];                            // RSP_SEL
                default: ;
                endcase
            end
            P_CHK: begin
                ps <= P_H1;
                if (rx_data != pxor) err <= 1'b1;
                else case (pcmd)
                    8'h01: soft_reset <= 1'b1;
                    8'h10: v_valid <= 1'b1;
                    8'h11: mk_valid <= 1'b1;
                    8'h12: basis_valid <= 1'b1;
                    8'h13: cal_valid <= 1'b1;
                    8'h14: sel_valid <= 1'b1;
                    default: ;
                endcase
            end
            default: ps <= P_H1;
            endcase
        end
    end

    // ------------------------------------------------------------------ TX: writer + FIFO
    reg [7:0]  tfifo [0:4095];
    reg [12:0] twp = 0, trp = 0;
    wire [12:0] tcount = twp - trp;
    wire tfull = (tcount >= 13'd4090);
    reg [7:0]  tout;
    reg        tout_v = 1'b0;
    assign tx_data = tout;
    assign tx_valid = tout_v;
    always @(posedge clk) begin
        if (rst) begin trp <= 0; tout_v <= 1'b0; end
        else if (!tout_v || tx_ready) begin
            if (tout_v && tx_ready) tout_v <= 1'b0;
            if (tcount != 0 && !(tout_v && !tx_ready)) begin
                tout <= tfifo[trp[11:0]]; tout_v <= 1'b1; trp <= trp + 1'b1;
            end
        end
    end

    localparam W_IDLE = 0, W_HDR = 1, W_PAY = 2, W_XOR = 3;
    reg [1:0]  ws = W_IDLE;
    reg [2:0]  hi;
    reg [39:0] hdr;
    reg [15:0] wleft;
    reg [63:0] wsh;
    reg [3:0]  wn;
    reg [7:0]  wx;
    assign msg_idle = (ws == W_IDLE);
    assign w_ready = (ws == W_PAY) && (wn == 0);
    reg tpush; reg [7:0] tdin;
    always @(posedge clk) begin
        tpush <= 1'b0;
        if (tpush) begin tfifo[twp[11:0]] <= tdin; twp <= twp + 1'b1; end
        if (rst) begin ws <= W_IDLE; twp <= 0; tpush <= 1'b0; end
        else case (ws)
        W_IDLE: if (msg_start) begin
            hdr <= {msg_len, msg_cmd, 8'h5A, 8'hA5};
            wx <= msg_cmd ^ msg_len[7:0] ^ msg_len[15:8];
            wleft <= msg_len; hi <= 0; wn <= 0;
            ws <= W_HDR;
        end
        W_HDR: if (!tfull && !tpush) begin
            tdin <= hdr[7:0]; tpush <= 1'b1; hdr <= hdr >> 8;
            if (hi == 4) ws <= (wleft == 0) ? W_XOR : W_PAY;
            hi <= hi + 1'b1;
        end
        W_PAY: begin
            if (wn == 0) begin
                if (w_valid) begin wsh <= w_data; wn <= w_nb; end
            end else if (!tfull && !tpush) begin
                tdin <= wsh[7:0]; tpush <= 1'b1; wx <= wx ^ wsh[7:0];
                wsh <= wsh >> 8; wn <= wn - 1'b1;
                wleft <= wleft - 1'b1;
                if (wleft == 1) begin wn <= 0; ws <= W_XOR; end
            end
        end
        W_XOR: if (!tfull && !tpush) begin tdin <= wx; tpush <= 1'b1; ws <= W_IDLE; end
        endcase
    end
endmodule
