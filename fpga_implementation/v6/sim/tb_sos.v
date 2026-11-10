`timescale 1ns / 1ps
module tb_sos;
    reg clk = 0; always #10 clk = ~clk;
    reg clear = 0, start = 0, copy = 0; reg [4:0] inst = 0, cf = 0; reg [1:0] fset = 0; reg signed [31:0] x = 0;
    wire busy, done; wire signed [31:0] y;
    v6_sos #(.NINST(4)) dut(.clk(clk), .clear(clear), .start(start), .inst(inst), .fset(fset), .x(x), .copy(copy), .copy_from(cf), .busy(busy), .done(done), .y(y));
    integer fd, n, err = 0, r; reg [31:0] vx, v0, v1, v2, got;
    task run(input [4:0] i, input [1:0] f, input [31:0] xx, output [31:0] yy);
        begin @(negedge clk); inst = i; fset = f; x = xx; start = 1; @(negedge clk); start = 0;
              while (!done) @(negedge clk); yy = y; end
    endtask
    initial begin
        @(negedge clk); clear = 1; @(negedge clk); clear = 0; while (!done) @(negedge clk);
        fd = $fopen("sos_vec.txt", "r");
        for (n = 0; n < 3000; n = n + 1) begin
            r = $fscanf(fd, "%h %h %h %h\n", vx, v0, v1, v2);
            run(0, 0, vx, got); if (got !== v0) begin err = err + 1; if (err < 5) $display("LP  n=%0d got %h exp %h", n, got, v0); end
            run(1, 1, vx, got); if (got !== v1) begin err = err + 1; if (err < 5) $display("MAT n=%0d got %h exp %h", n, got, v1); end
            run(2, 2, vx, got); if (got !== v2) begin err = err + 1; if (err < 5) $display("BP  n=%0d got %h exp %h", n, got, v2); end
        end
        $display("SOS TEST: %0d errors", err); $finish;
    end
endmodule
