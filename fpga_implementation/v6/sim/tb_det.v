`timescale 1ns / 1ps
module tb_det;
    reg clk = 0; always #10 clk = ~clk;
    reg mclear = 0, mstart = 0; reg [4:0] minst = 0; reg [5:0] mw = 0; reg signed [63:0] msq = 0;
    wire mdone; wire signed [63:0] msum;
    v6_mwi #(.NINST(2)) mwi(.clk(clk), .clear(mclear), .start(mstart), .inst(minst), .w(mw), .sq(msq), .copy(1'b0), .copy_from(5'd0), .done(mdone), .sum(msum));
    reg dinit = 0, dstart = 0; reg [2:0] dinst = 0; reg signed [31:0] ist = 0, t = 0; reg [7:0] irf = 0, ilc = 0, irr = 0;
    reg signed [63:0] de = 0, dab = 0; wire ddone; wire signed [31:0] dout;
    v6_det #(.NINST(2)) det(.clk(clk), .init(dinit), .i_start(ist), .i_refr(irf), .i_loc(ilc), .i_rrmin(irr), .start(dstart), .inst(dinst), .t(t), .e(de), .ab(dab), .done(ddone), .out(dout));
    integer fd, r, n, err = 0, y, eh, p0, p1, k; reg signed [63:0] yq, e [0:1];
    initial begin
        @(negedge clk); mclear = 1; @(negedge clk); mclear = 0; while (!mdone) @(negedge clk);
        @(negedge clk); dinit = 1; dinst = 0; ist = 0; irf = 75; ilc = 30; irr = 75; @(negedge clk); dinit = 0; while (!ddone) @(negedge clk);
        @(negedge clk); dinit = 1; dinst = 1; ist = 1000; irf = 50; ilc = 26; irr = 50; @(negedge clk); dinit = 0; while (!ddone) @(negedge clk);
        fd = $fopen("det_vec.txt", "r");
        for (n = 0; n < 20000; n = n + 1) begin
            r = $fscanf(fd, "%d %d %d %d\n", y, eh, p0, p1);
            yq = y; yq = yq <<< 8;
            for (k = 0; k < 2; k = k + 1) begin
                @(negedge clk); minst = k; mw = k ? 30 : 38; msq = yq * yq; mstart = 1; @(negedge clk); mstart = 0;
                while (!mdone) @(negedge clk); e[k] = msum;
                @(negedge clk); dinst = k; t = n; de = msum; dab = yq < 0 ? -yq : yq; dstart = 1; @(negedge clk); dstart = 0;
                while (!ddone) @(negedge clk);
                if (dout !== (k ? p1 : p0)) begin err = err + 1; if (err < 8) $display("t=%0d inst %0d got %0d exp %0d", n, k, dout, k ? p1 : p0); end
            end
            if ((e[0] >>> 32) != eh) begin err = err + 1; if (err < 8) $display("t=%0d mwi got %0d exp %0d", n, e[0] >>> 32, eh); end
        end
        $display("DET TEST: %0d errors", err); $finish;
    end
endmodule
