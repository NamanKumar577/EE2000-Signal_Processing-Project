// FECG v6 system testbench: drives v6_core like the board host (lock-step SAMPLES chunks,
// PC responses replayed when their trigger frame has arrived) and checks every uplink
// byte against the C model's golden stream.   +define+... none; files: G_up.hex, G_script.txt
`timescale 1ns / 1ps
module tb_core;
    parameter MAXB = 4000000;
    reg clk = 0; always #10 clk = ~clk;
    reg rst = 1;
    reg [7:0] rxd = 0; reg rxv = 0;
    wire [7:0] txd; wire txv; wire [7:0] status;
    v6_core dut(.clk(clk), .rst(rst), .rx_data(rxd), .rx_valid(rxv), .tx_data(txd), .tx_valid(txv), .tx_ready(1'b1), .status(status));

    reg [7:0] expb [0:MAXB-1];
    integer up_i = 0, frames = 0, errs = 0, dones = 0, ends = 0, fs = 0, flen = 0, fpos = 0, idle = 0;
    reg flushed = 0;
    reg [7:0] fcmd;
    initial $readmemh("G_up.hex", expb);
    always @(posedge clk) begin
        idle <= idle + 1;
        if (txv) begin
            idle <= 0;
            if (txd !== expb[up_i]) begin
                errs = errs + 1;
                if (errs <= 20) $display("MISMATCH byte %0d (frame %0d, cmd %02h, pos %0d): got %02h exp %02h  t=%0t",
                                         up_i, frames, fcmd, fpos, txd, expb[up_i], $time);
                if (errs == 20) begin $display("too many errors"); $finish; end
            end
            up_i = up_i + 1;
            case (fs)
            0: fs = 1;
            1: fs = 2;
            2: begin fcmd = txd; fs = 3; end
            3: begin flen = txd; fs = 4; end
            4: begin flen = flen + 256 * txd; fpos = 0; fs = (flen == 0) ? 6 : 5; end
            5: begin fpos = fpos + 1; if (fpos == flen) fs = 6; end
            6: begin
                fs = 0; frames = frames + 1;
                if (fcmd == 8'h8C) dones = dones + 1;
                if (fcmd == 8'h8E) ends = ends + 1;
                if (frames % 2000 == 0) $display("  %0d frames, %0d bytes, t=%0t", frames, up_i, $time);
            end
            endcase
        end
    end

    task send_byte(input [7:0] b);
        begin @(negedge clk); rxd = b; rxv = 1; @(negedge clk); rxv = 0; end
    endtask

    integer fd, r, n, idx, i, chunks = 0;
    reg [7:0] ch, b;
    reg [7:0] buf_ [0:8191];
    initial begin
        repeat (10) @(negedge clk); rst = 0;
        repeat (5000) @(negedge clk);
        fd = $fopen("G_script.txt", "r");
        forever begin
            r = $fscanf(fd, " %c", ch);
            if (ch == "S") begin
                while (dones != chunks) begin @(negedge clk); if (idle > 20000000) begin $display("TIMEOUT waiting DONE %0d", chunks); $finish; end end
                r = $fscanf(fd, "%d", n);
                for (i = 0; i < n; i = i + 1) begin r = $fscanf(fd, "%h", b); send_byte(b); end
                chunks = chunks + 1;
            end else if (ch == "R") begin
                r = $fscanf(fd, "%d %d", idx, n);
                for (i = 0; i < n; i = i + 1) begin r = $fscanf(fd, "%h", b); buf_[i] = b; end
                while (frames <= idx) begin @(negedge clk); if (idle > 20000000) begin $display("TIMEOUT waiting frame %0d (have %0d)", idx, frames); $finish; end end
                for (i = 0; i < n; i = i + 1) send_byte(buf_[i]);
            end else if (ch == "F") begin                      // v7: FLUSH after the last DONE
                while (dones != chunks) begin @(negedge clk); if (idle > 20000000) begin $display("TIMEOUT before FLUSH"); $finish; end end
                send_byte(8'hA5); send_byte(8'h5A); send_byte(8'h03); send_byte(8'h00); send_byte(8'h00); send_byte(8'h03);
                flushed = 1;
            end else begin
                while (flushed && ends == 0) begin @(negedge clk); if (idle > 20000000) begin $display("TIMEOUT waiting END7"); $finish; end end
                while (dones != chunks) begin @(negedge clk); if (idle > 20000000) begin $display("TIMEOUT at end"); $finish; end end
                repeat (100) @(negedge clk);
                $display("RESULT: %0d uplink bytes, %0d frames, %0d byte errors, expected next byte %02h (x = end)", up_i, frames, errs, expb[up_i]);
                $finish;
            end
        end
    end
endmodule
