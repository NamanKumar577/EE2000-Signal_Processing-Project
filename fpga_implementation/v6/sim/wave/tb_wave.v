// Waveform view of the v6 system test: wraps the normal system testbench (tb_core, which
// streams a recording like the board host and checks every uplink byte against the C model)
// and exposes readable internal signals for the Vivado waveform window / VCD dump.
`timescale 1ns / 1ps
module tb_wave;
    tb_core u();                                            // the unchanged system testbench

    // ---- clock and sample counter
    wire               clk        = u.clk;
    wire [31:0]        sample_T   = u.dut.T;                // input sample being processed
    wire [4:0]         seq_state  = u.dut.st;               // core sequencer state
    wire [2:0]         unit_ph    = u.dut.ph;               // 0 core, 1 front end, 2 maternal, 3 canceller, 4 tracks

    // ---- input samples (raw int16 from the host), 4 abdominal leads
    wire signed [15:0] raw_lead1  = u.dut.xs[15:0];
    wire signed [15:0] raw_lead2  = u.dut.xs[31:16];
    wire signed [15:0] raw_lead3  = u.dut.xs[47:32];
    wire signed [15:0] raw_lead4  = u.dut.xs[63:48];

    // ---- front end output Xf (written into the X/Z rings) and canceller writes into Z
    wire               xf_we      = u.dut.fe_we;
    wire [11:0]        xf_addr    = u.dut.fe_wa;
    wire signed [15:0] xf_lead1   = u.dut.fe_wd[15:0];
    wire signed [15:0] xf_lead2   = u.dut.fe_wd[31:16];
    wire signed [15:0] xf_lead3   = u.dut.fe_wd[47:32];
    wire signed [15:0] xf_lead4   = u.dut.fe_wd[63:48];
    wire               z_we       = u.dut.ca_zwe;
    wire [11:0]        z_addr     = u.dut.ca_zwa;
    wire signed [15:0] z_lead1    = u.dut.ca_zwd[15:0];
    wire signed [15:0] z_lead2    = u.dut.ca_zwd[31:16];
    wire signed [15:0] z_lead3    = u.dut.ca_zwd[47:32];
    wire signed [15:0] z_lead4    = u.dut.ca_zwd[63:48];

    // ---- maternal R peaks (count and sample position of the newest peak)
    wire [31:0]        mat_npeaks = u.dut.nmpk;
    wire signed [31:0] mat_peak_t = u.dut.mat.qwd;

    // ---- tracks: calibration done, selected track, last output beat, FHR (x10 bpm)
    wire               calibrated = u.dut.trk.calibrated;
    wire signed [4:0]  sel_track  = u.dut.trk.sel_k;
    wire signed [31:0] beat_t     = u.dut.trk.out_last;
    wire [15:0]        fhr_x10    = u.dut.trk.fhr_x10;

    // ---- unit hand-shakes (one sample = fe -> mat -> canc -> trk)
    wire fe_go = u.dut.fe_go,  fe_done = u.dut.fe_done;
    wire mat_go = u.dut.mat_go, mat_done = u.dut.mat_done;
    wire ca_go = u.dut.ca_go,  ca_done = u.dut.ca_done;
    wire tk_go = u.dut.tk_go,  tk_done = u.dut.tk_done;

    // ---- PC link: bytes in (samples, PC answers) and out (features, requests, beats)
    wire       rx_valid  = u.rxv;
    wire [7:0] rx_byte   = u.rxd;
    wire       tx_valid  = u.txv;
    wire [7:0] tx_byte   = u.txd;
    wire       msg_start = u.dut.msg_start;
    wire [7:0] msg_cmd   = u.dut.msg_cmd;
    wire       pca_answer = u.dut.v_valid, gevd_answer = u.dut.cal_valid, sel_answer = u.dut.sel_valid,
               basis_answer = u.dut.basis_valid, train_answer = u.dut.mk_valid;
endmodule
