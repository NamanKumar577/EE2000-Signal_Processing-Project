// =============================================================================
// Module: fecg_multichannel_top
// Description: Complete Integrated 4-Channel Fetal ECG (FECG) Processing System
//              with PCA Spatial Beamformer, 64-Sample Linear Weight Slew Engine,
//              Single-Channel Datapath, and Real-Time Bidirectional UART Telemetry.
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C) on RealDigital Boolean Board
// Toolchain: AMD Vivado 2022.2+
//
// Clocks:
//   - Master Oscillator Input: 100.0 MHz on Pin F14
//   - Internal Processing Clock: 25.0 MHz via PLLE2_BASE (Period = 40.0 ns)
//     Guarantees positive setup timing slack (WNS > +15 ns) across entire datapath.
//
// UART Protocol (115,200 Baud, 8-N-1):
//   - Downlink 4-CH Sample (0xA5, 11B): [0xA5][Seq][CH0:2B][CH1:2B][CH2:2B][CH3:2B][CRC8]
//   - Downlink Calibration (0xC3, 10B): [0xC3][W0:2B][W1:2B][W2:2B][W3:2B][CRC8]
//   - Downlink Calibration + Detector Restart (0xC4, 10B): same layout as 0xC3;
//     additionally re-runs the detector warm-up 128 samples after the weights
//     (host sends it for the initial / any re-anchoring calibration)
//   - Uplink Clean FECG Stream (0x5A, 6B): [0x5A][Seq][FECG:3B Q20][CRC8]
//   - Uplink QRS/FHR Telemetry (0xAA, 8B): [0xAA][Timestamp:3B][FHR:2B in 0.1 bpm][Status:1B][CRC8]
//
// Diagnostic LEDs (Boolean Board Pins G1, G2, F1, F2, E1, E2, E3, E5):
//   - LED[0]: Blinks on each valid Downlink Sample Packet (0xA5)
//   - LED[1]: Blinks on each transmitted UART byte
//   - LED[2]: Slew Engine Active indicator (crossfade_step < 64)
//   - LED[3]: Fetal QRS Beat Detection pulse (stretched to ~50 ms for human visibility)
//   - LED[4]: Sticky Saturation / Overflow flag
//   - LED[5]: Adaptive Detector Active flag (512-sample warmup complete)
//   - LED[6]: Real Beat Classification bit (status_flag_2bit[0])
//   - LED[7]: PLL Locked indicator (System clock stable)
// =============================================================================

`timescale 1ns / 1ps

module fecg_multichannel_top #(
    parameter integer CLK_IN_FREQ       = 100_000_000, // 100 MHz oscillator
    parameter integer SYS_CLK_FREQ      = 25_000_000,  // 25 MHz internal clock
    parameter integer BAUD_RATE         = 115_200,     // 115,200 bps
    parameter integer ADC_WIDTH         = 16,          // Signed 16-bit Q12 ADC input
    parameter integer WEIGHT_WIDTH      = 17,          // Signed 17-bit Q2.15 weights
    parameter integer DATA_WIDTH        = 24,          // Signed 24-bit Q20 datapath
    parameter integer DET_WIDTH         = 16,          // Signed 16-bit Q12 bandpass word
    parameter integer MWI_WIDTH         = 36,          // Unsigned 36-bit energy
    parameter integer TIME_WIDTH        = 24,          // 24-bit sample timestamp
    parameter integer RR_WIDTH          = 16,          // 16-bit RR interval
    parameter integer FHR_WIDTH         = 16,          // 16-bit FHR in 0.1 bpm
    parameter integer WARMUP_LEN        = 512,         // Warmup duration (512 samples)
    parameter integer LOC_WINDOW        = 26,          // Trailing search window
    parameter integer LATENCY_COMP      = 13           // Group delay compensation (20-30 Hz)
)(
    input  wire       clk,        // Master 100.0 MHz oscillator (Pin F14)
    input  wire       rst_pin,    // External pushbutton reset BTN0 (Pin J2, active-high)
    input  wire       uart_rxd,   // Serial RX from host (Pin V12)
    output wire       uart_txd,   // Serial TX to host (Pin U11)
    output wire [7:0] led         // 8 Diagnostic LEDs (Pins G1, G2, F1, F2, E1, E2, E3, E5)
);

    // =========================================================================
    // 1. Clock Generation via 7-Series PLLE2_BASE (100 MHz -> 25 MHz)
    // =========================================================================
    wire clk_25m_unbuf;
    wire clk_25m;
    wire clk_fb;
    wire pll_locked;

    PLLE2_BASE #(
        .BANDWIDTH("OPTIMIZED"),
        .CLKFBOUT_MULT(8),         // 100 MHz * 8 = 800 MHz VCO
        .CLKFBOUT_PHASE(0.0),
        .CLKIN1_PERIOD(10.000),    // 100.0 MHz master clock
        .CLKOUT0_DIVIDE(32),       // 800 MHz / 32 = 25.0 MHz
        .CLKOUT0_DUTY_CYCLE(0.5),
        .CLKOUT0_PHASE(0.0),
        .DIVCLK_DIVIDE(1),
        .REF_JITTER1(0.010),
        .STARTUP_WAIT("FALSE")
    ) u_pll (
        .CLKOUT0(clk_25m_unbuf),
        .CLKOUT1(),
        .CLKOUT2(),
        .CLKOUT3(),
        .CLKOUT4(),
        .CLKOUT5(),
        .CLKFBOUT(clk_fb),
        .LOCKED(pll_locked),
        .CLKIN1(clk),
        .PWRDWN(1'b0),
        .RST(rst_pin),
        .CLKFBIN(clk_fb)
    );

    BUFG u_bufg_clk25 (
        .I(clk_25m_unbuf),
        .O(clk_25m)
    );

    // Synchronous Reset Release
    reg [1:0] rst_sync;
    wire sys_rst_n = rst_sync[1];
    wire sys_rst   = ~sys_rst_n;

    always @(posedge clk_25m or negedge pll_locked) begin
        if (!pll_locked) begin
            rst_sync <= 2'b00;
        end else begin
            if (rst_pin)
                rst_sync <= 2'b00;
            else
                rst_sync <= {rst_sync[0], 1'b1};
        end
    end

    // =========================================================================
    // 2. CRC8-CCITT Hardware Function (Polynomial 0x07, Init 0x00)
    // =========================================================================
    function [7:0] crc8_byte(input [7:0] data_in, input [7:0] crc_in);
        reg [7:0] c;
        integer i;
        begin
            c = crc_in ^ data_in;
            for (i = 0; i < 8; i = i + 1) begin
                if (c[7])
                    c = (c << 1) ^ 8'h07;
                else
                    c = c << 1;
            end
            crc8_byte = c;
        end
    endfunction

    // =========================================================================
    // 3. UART Physical Receiver & Transmitter (25 MHz, 115,200 Baud)
    // =========================================================================
    wire [7:0] rx_data;
    wire       rx_valid;
    wire       rx_busy;
    wire       rx_frame_err;

    uart_rx #(
        .CLK_FREQ(SYS_CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) u_uart_rx (
        .clk(clk_25m),
        .rst(sys_rst),
        .rx_serial(uart_rxd),
        .rx_data(rx_data),
        .rx_valid(rx_valid),
        .rx_busy(rx_busy),
        .rx_frame_err(rx_frame_err)
    );

    reg        tx_start;
    reg  [7:0] tx_data;
    wire       tx_busy;
    wire       tx_done;

    uart_tx #(
        .CLK_FREQ(SYS_CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) u_uart_tx (
        .clk(clk_25m),
        .rst(sys_rst),
        .tx_start(tx_start),
        .tx_data(tx_data),
        .tx_serial(uart_txd),
        .tx_busy(tx_busy),
        .tx_done(tx_done)
    );

    // =========================================================================
    // 4. Downlink Packet Parser (0xA5 Samples & 0xC3 Calibration Weights)
    // =========================================================================
    localparam [2:0]
        PARSE_IDLE    = 3'b000,
        PARSE_SAMPLE  = 3'b001,
        PARSE_CALIB   = 3'b010;

    reg [2:0] parse_state;
    reg [3:0] byte_idx;
    reg [7:0] rx_crc_accum;

    // Latched sample registers
    reg [7:0]  latched_seq;
    reg signed [ADC_WIDTH-1:0] ch0_reg, ch1_reg, ch2_reg, ch3_reg;
    reg signed [ADC_WIDTH-1:0] sample_ch0, sample_ch1, sample_ch2, sample_ch3;
    reg [7:0]  sample_seq;
    reg        sample_valid_strobe;

    // Latched calibration weight registers (Sign-extended to signed 17-bit Q2.15)
    reg signed [15:0] w0_reg, w1_reg, w2_reg, w3_reg;
    reg signed [WEIGHT_WIDTH-1:0] target_w0, target_w1, target_w2, target_w3;
    reg        weights_valid_strobe;
    reg        calib_restart_flag;     // current calibration packet is 0xC4
    reg        det_restart_strobe;     // 1-cycle: 0xC4 accepted (CRC ok)

    // Diagnostic activity toggles
    reg rx_sample_toggle;
    reg tx_activity_toggle;
    reg [15:0] crc_error_counter;

    always @(posedge clk_25m) begin
        if (!sys_rst_n) begin
            parse_state          <= PARSE_IDLE;
            byte_idx             <= 4'd0;
            rx_crc_accum         <= 8'd0;
            latched_seq          <= 8'd0;
            ch0_reg              <= 16'sd0;
            ch1_reg              <= 16'sd0;
            ch2_reg              <= 16'sd0;
            ch3_reg              <= 16'sd0;
            sample_ch0           <= 16'sd0;
            sample_ch1           <= 16'sd0;
            sample_ch2           <= 16'sd0;
            sample_ch3           <= 16'sd0;
            sample_seq           <= 8'd0;
            sample_valid_strobe  <= 1'b0;
            w0_reg               <= 16'sd0;
            w1_reg               <= 16'sd0;
            w2_reg               <= 16'sd0;
            w3_reg               <= 16'sd0;
            target_w0            <= 17'sd32768; // Default unity
            target_w1            <= 17'sd0;
            target_w2            <= 17'sd0;
            target_w3            <= 17'sd0;
            weights_valid_strobe <= 1'b0;
            calib_restart_flag   <= 1'b0;
            det_restart_strobe   <= 1'b0;
            rx_sample_toggle     <= 1'b0;
            crc_error_counter    <= 16'd0;
        end else begin
            sample_valid_strobe  <= 1'b0;
            weights_valid_strobe <= 1'b0;
            det_restart_strobe   <= 1'b0;

            if (rx_valid) begin
                case (parse_state)
                    PARSE_IDLE: begin
                        byte_idx <= 4'd1;
                        if (rx_data == 8'hA5) begin
                            rx_crc_accum <= crc8_byte(8'hA5, 8'h00);
                            parse_state  <= PARSE_SAMPLE;
                        end else if (rx_data == 8'hC3 || rx_data == 8'hC4) begin
                            rx_crc_accum       <= crc8_byte(rx_data, 8'h00);
                            calib_restart_flag <= (rx_data == 8'hC4);
                            parse_state        <= PARSE_CALIB;
                        end
                    end

                    PARSE_SAMPLE: begin
                        case (byte_idx)
                            4'd1: begin
                                latched_seq  <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd2: begin
                                ch0_reg[15:8] <= rx_data;
                                rx_crc_accum  <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx      <= byte_idx + 1'b1;
                            end
                            4'd3: begin
                                ch0_reg[7:0] <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd4: begin
                                ch1_reg[15:8] <= rx_data;
                                rx_crc_accum  <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx      <= byte_idx + 1'b1;
                            end
                            4'd5: begin
                                ch1_reg[7:0] <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd6: begin
                                ch2_reg[15:8] <= rx_data;
                                rx_crc_accum  <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx      <= byte_idx + 1'b1;
                            end
                            4'd7: begin
                                ch2_reg[7:0] <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd8: begin
                                ch3_reg[15:8] <= rx_data;
                                rx_crc_accum  <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx      <= byte_idx + 1'b1;
                            end
                            4'd9: begin
                                ch3_reg[7:0] <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd10: begin
                                // Final byte: Check CRC
                                if (rx_data == rx_crc_accum) begin
                                    sample_ch0          <= ch0_reg;
                                    sample_ch1          <= ch1_reg;
                                    sample_ch2          <= ch2_reg;
                                    sample_ch3          <= ch3_reg;
                                    sample_seq          <= latched_seq;
                                    sample_valid_strobe <= 1'b1;
                                    rx_sample_toggle    <= ~rx_sample_toggle;
                                end else begin
                                    crc_error_counter   <= crc_error_counter + 1'b1;
                                end
                                parse_state <= PARSE_IDLE;
                                byte_idx    <= 4'd0;
                            end
                            default: parse_state <= PARSE_IDLE;
                        endcase
                    end

                    PARSE_CALIB: begin
                        case (byte_idx)
                            4'd1: begin
                                w0_reg[15:8] <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd2: begin
                                w0_reg[7:0]  <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd3: begin
                                w1_reg[15:8] <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd4: begin
                                w1_reg[7:0]  <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd5: begin
                                w2_reg[15:8] <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd6: begin
                                w2_reg[7:0]  <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd7: begin
                                w3_reg[15:8] <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd8: begin
                                w3_reg[7:0]  <= rx_data;
                                rx_crc_accum <= crc8_byte(rx_data, rx_crc_accum);
                                byte_idx     <= byte_idx + 1'b1;
                            end
                            4'd9: begin
                                // Final byte: Check CRC
                                if (rx_data == rx_crc_accum) begin
                                    target_w0 <= {w0_reg[15], w0_reg};
                                    target_w1 <= {w1_reg[15], w1_reg};
                                    target_w2 <= {w2_reg[15], w2_reg};
                                    target_w3 <= {w3_reg[15], w3_reg};
                                    weights_valid_strobe <= 1'b1;
                                    det_restart_strobe   <= calib_restart_flag;
                                end else begin
                                    crc_error_counter <= crc_error_counter + 1'b1;
                                end
                                parse_state <= PARSE_IDLE;
                                byte_idx    <= 4'd0;
                            end
                            default: parse_state <= PARSE_IDLE;
                        endcase
                    end

                    default: parse_state <= PARSE_IDLE;
                endcase
            end
        end
    end

    // =========================================================================
    // 5. Weight Slew Engine (64-Sample Linear Crossfade)
    // =========================================================================
    wire signed [WEIGHT_WIDTH-1:0] w_curr0, w_curr1, w_curr2, w_curr3;
    wire crossfade_active;
    wire [6:0] slew_step_count;

    weight_slew_engine #(
        .WEIGHT_WIDTH(WEIGHT_WIDTH),
        .CROSSFADE_STEPS(64)
    ) u_slew_engine (
        .clk(clk_25m),
        .rst_n(sys_rst_n),
        .enable(1'b1),
        .sample_strobe(sample_valid_strobe),
        .weight_update_strobe(weights_valid_strobe),
        .target_w0(target_w0),
        .target_w1(target_w1),
        .target_w2(target_w2),
        .target_w3(target_w3),
        .w_curr0(w_curr0),
        .w_curr1(w_curr1),
        .w_curr2(w_curr2),
        .w_curr3(w_curr3),
        .crossfade_active(crossfade_active),
        .step_counter(slew_step_count)
    );

    // =========================================================================
    // 6. 4-Channel Spatial Beamformer
    // =========================================================================
    wire signed [DATA_WIDTH-1:0] beam_proj_out;
    wire                         beam_valid_out;
    wire                         beam_acc_ovf;
    wire                         beam_out_sat;

    spatial_beamformer #(
        .SAMPLE_WIDTH(ADC_WIDTH),
        .WEIGHT_WIDTH(WEIGHT_WIDTH),
        .PROD_WIDTH(33),
        .ACC_WIDTH(35),
        .PROJ_ACC_WIDTH(32),
        .PROJ_WIDTH(DATA_WIDTH),
        .PROJ_SHIFT(7)
    ) u_beamformer (
        .clk(clk_25m),
        .rst_n(sys_rst_n),
        .enable(1'b1),
        .valid_in(sample_valid_strobe),
        .x0_in(sample_ch0),
        .x1_in(sample_ch1),
        .x2_in(sample_ch2),
        .x3_in(sample_ch3),
        .w0_in(w_curr0),
        .w1_in(w_curr1),
        .w2_in(w_curr2),
        .w3_in(w_curr3),
        .proj_out(beam_proj_out),
        .valid_out(beam_valid_out),
        .acc_overflow(beam_acc_ovf),
        .out_saturated(beam_out_sat)
    );

    // Pipeline sample sequence tag across beamformer latency (1 cycle)
    reg [7:0] active_sample_seq;
    always @(posedge clk_25m) begin
        if (sample_valid_strobe)
            active_sample_seq <= sample_seq;
    end

    // =========================================================================
    // 7. Single-Channel Processing Datapath
    // =========================================================================

    // Stage 1: HP1 Baseline Wander Remover (fc ~ 0.62 Hz)
    wire signed [DATA_WIDTH-1:0] hp_out;
    wire                         hp_valid;
    wire                         hp_acc_ovf;
    wire                         hp_out_sat;
    wire                         hp_ovf = hp_acc_ovf | hp_out_sat;

    hp1_baseline #(
        .DATA_WIDTH(DATA_WIDTH),
        .ACC_WIDTH(32),
        .K_SHIFT(6)
    ) u_hp1 (
        .clk(clk_25m),
        .rst_n(sys_rst_n),
        .enable(1'b1),
        .valid_in(beam_valid_out),
        .x_in(beam_proj_out),
        .y_out(hp_out),
        .valid_out(hp_valid),
        .acc_out(),
        .base_out(),
        .acc_overflow(hp_acc_ovf),
        .out_saturated(hp_out_sat)
    );

    // Stage 2: LP40 Filter (4th-Order Butterworth Lowpass, fc = 40 Hz)
    wire signed [DATA_WIDTH-1:0] fecg_clean_out;
    wire                         lp_valid;
    wire                         lp_ovf;

    lp40_filter #(
        .DATA_WIDTH(DATA_WIDTH),
        .COEF_WIDTH(18),
        .COEF_FRAC(15),
        .STATE_WIDTH(48)
    ) u_lp40 (
        .clk(clk_25m),
        .rst_n(sys_rst_n),
        .enable(1'b1),
        .valid_in(hp_valid),
        .x_in(hp_out),
        .y_out(fecg_clean_out),
        .valid_out(lp_valid),
        .overflow_flag(lp_ovf)
    );

    // Stage 3: Config C Bandpass Filter (12.0 - 35.0 Hz, 8th-Order)
    wire signed [DET_WIDTH-1:0]  bp16_out;
    wire signed [DATA_WIDTH-1:0] bp24_raw;
    wire                         bp_valid;
    wire                         bp_ovf;

    bandpass_config_c #(
        .DATA_WIDTH(DATA_WIDTH),
        .OUT_WIDTH(DET_WIDTH),
        .COEF_WIDTH(18),
        .COEF_FRAC(15),
        .STATE_WIDTH(48),
        .DET_SHIFT(8)
    ) u_bandpass (
        .clk(clk_25m),
        .rst_n(sys_rst_n),
        .enable(1'b1),
        .valid_in(lp_valid),
        .x_in(fecg_clean_out),
        .bp16_out(bp16_out),
        .bp24_raw_out(bp24_raw),
        .valid_out(bp_valid),
        .overflow_flag(bp_ovf)
    );

    // Stage 4: Squarer & Moving Window Integrator (MWI, W = 30 samples)
    wire [MWI_WIDTH-1:0] mwi_out;
    wire [31:0]          sq_out;
    wire                 mwi_valid;
    wire                 mwi_ovf;

    squarer_mwi #(
        .IN_WIDTH(DET_WIDTH),
        .SQ_WIDTH(32),
        .MWI_WIDTH(MWI_WIDTH),
        .MWI_LEN(30)
    ) u_mwi (
        .clk(clk_25m),
        .rst_n(sys_rst_n),
        .enable(1'b1),
        .valid_in(bp_valid),
        .bp16_in(bp16_out),
        .mwi_out(mwi_out),
        .sq_out(sq_out),
        .valid_out(mwi_valid),
        .mwi_overflow(mwi_ovf)
    );

    // Stage 5: Adaptive Dual-Threshold QRS Detector
    wire                  candidate_strobe;
    wire [TIME_WIDTH-1:0] cand_timestamp;
    wire [MWI_WIDTH-1:0]  cand_energy;
    wire [MWI_WIDTH-1:0]  peak_level;
    wire [MWI_WIDTH-1:0]  noise_level;
    wire [MWI_WIDTH-1:0]  thresh;
    wire                  detector_active;
    wire [TIME_WIDTH-1:0] t_counter;

    adaptive_detector #(
        .MWI_WIDTH(MWI_WIDTH),
        .TIME_WIDTH(TIME_WIDTH),
        .WARMUP_LEN(WARMUP_LEN),
        .REFRACTORY_LEN(50)
    ) u_detector (
        .clk(clk_25m),
        .rst_n(sys_rst_n),
        .enable(1'b1),
        .valid_in(mwi_valid),
        .mwi_in(mwi_out),
        .restart_req(det_restart_strobe),
        .candidate_strobe(candidate_strobe),
        .cand_timestamp(cand_timestamp),
        .cand_energy(cand_energy),
        .peak_level_out(peak_level),
        .noise_level_out(noise_level),
        .threshold_out(thresh),
        .detector_active(detector_active),
        .t_counter(t_counter)
    );

    // Stage 6: Peak Localizer (26-Sample Trailing Search)
    wire                  peak_strobe;
    wire [TIME_WIDTH-1:0] raw_peak_loc;
    wire [TIME_WIDTH-1:0] comp_peak_loc;
    wire [DET_WIDTH-1:0]  peak_val_loc;

    peak_localizer #(
        .DATA_WIDTH(DET_WIDTH),
        .TIME_WIDTH(TIME_WIDTH),
        .LOC_WINDOW(LOC_WINDOW),
        .LATENCY_COMP(LATENCY_COMP)
    ) u_localizer (
        .clk(clk_25m),
        .rst_n(sys_rst_n),
        .enable(1'b1),
        .valid_in(bp_valid),
        .t_in(t_counter),
        .bp16_in(bp16_out),
        .candidate_strobe(candidate_strobe),
        .peak_strobe(peak_strobe),
        .raw_peak_out(raw_peak_loc),
        .comp_peak_out(comp_peak_loc),
        .peak_val_out(peak_val_loc)
    );

    // Stage 7: Interval Fusion & Pure Integer Median-5 Filter
    wire                  beat_valid_strobe;
    wire                  fused_strobe;
    wire                  rr_update_strobe;
    wire [TIME_WIDTH-1:0] last_raw_peak;
    wire [TIME_WIDTH-1:0] last_comp_peak;
    wire [RR_WIDTH-1:0]   raw_rr;
    wire [RR_WIDTH-1:0]   med_rr;
    wire [1:0]            status_flag_2bit;
    wire [15:0]           n_fused_events;

    interval_fusion #(
        .DATA_WIDTH(DET_WIDTH),
        .TIME_WIDTH(TIME_WIDTH),
        .RR_WIDTH(RR_WIDTH),
        .RR_MIN(50),
        .RR_MAX(300)
    ) u_fusion (
        .clk(clk_25m),
        .rst_n(sys_rst_n),
        .enable(1'b1),
        .detector_active(detector_active),
        .peak_strobe(peak_strobe),
        .raw_peak_in(raw_peak_loc),
        .comp_peak_in(comp_peak_loc),
        .peak_val_in(peak_val_loc),
        .beat_valid_strobe(beat_valid_strobe),
        .fused_strobe(fused_strobe),
        .rr_update_strobe(rr_update_strobe),
        .last_raw_peak_out(last_raw_peak),
        .last_comp_peak_out(last_comp_peak),
        .raw_rr_out(raw_rr),
        .med_rr_out(med_rr),
        .status_flag_2bit(status_flag_2bit),
        .n_fused_events(n_fused_events)
    );

    // Stage 8: FHR Calculator (251-Word Distributed ROM LUT)
    wire [FHR_WIDTH-1:0] fhr_instant_out;
    wire [FHR_WIDTH-1:0] fhr_stream_out;
    wire                 fhr_valid;
    wire                 fhr_ovf;

    fhr_calculator #(
        .RR_WIDTH(RR_WIDTH),
        .FHR_WIDTH(FHR_WIDTH),
        .RR_MIN(50),
        .RR_MAX(300),
        .LUT_SIZE(251)
    ) u_fhr (
        .clk(clk_25m),
        .rst_n(sys_rst_n),
        .enable(1'b1),
        .detector_active(detector_active),
        .rr_update_strobe(rr_update_strobe),
        .med_rr_in(med_rr),
        .fhr_instant_out(fhr_instant_out),
        .fhr_stream_out(fhr_stream_out),
        .fhr_valid_strobe(fhr_valid),
        .fhr_lut_overflow(fhr_ovf)
    );

    // Sticky Saturation Accounting
    reg sticky_sat;
    always @(posedge clk_25m) begin
        if (!sys_rst_n) begin
            sticky_sat <= 1'b0;
        end else begin
            if (beam_acc_ovf || beam_out_sat || hp_ovf || lp_ovf || bp_ovf || mwi_ovf || fhr_ovf)
                sticky_sat <= 1'b1;
        end
    end

    // Telemetry Status Byte (Byte 6 in 0xAA packet)
    wire [7:0] telemetry_status_byte;
    assign telemetry_status_byte = {4'b0000, sticky_sat, detector_active, status_flag_2bit};

    // =========================================================================
    // 8. Uplink Packet Generator & 64-Byte Elastic Distributed TX FIFO
    // =========================================================================
    (* ram_style = "distributed" *) reg [7:0] tx_fifo [0:63];
    reg [5:0]  tx_wr_ptr;
    reg [5:0]  tx_rd_ptr;
    reg [6:0]  tx_fifo_count;
    reg        fifo_wr_en;
    reg [7:0]  fifo_wr_byte;
    wire       fifo_rd_en;

    // Staged packet buffers
    reg [2:0]  fecg_tx_step;
    reg        fecg_tx_active;
    reg [7:0]  staged_fecg_seq;
    reg signed [23:0] staged_fecg_val;
    reg [7:0]  staged_fecg_crc;

    reg [3:0]  telemetry_tx_step;
    reg        telemetry_tx_active;
    reg [23:0] staged_comp_peak;
    reg [15:0] staged_fhr;
    reg [7:0]  staged_status;
    reg [7:0]  staged_telemetry_crc;

    // Precalculate CRC8 for 0x5A Clean FECG Stream Packet
    wire [7:0] fecg_crc_c0 = crc8_byte(8'h5A, 8'h00);
    wire [7:0] fecg_crc_c1 = crc8_byte(active_sample_seq, fecg_crc_c0);
    wire [7:0] fecg_crc_c2 = crc8_byte(fecg_clean_out[23:16], fecg_crc_c1);
    wire [7:0] fecg_crc_c3 = crc8_byte(fecg_clean_out[15:8], fecg_crc_c2);
    wire [7:0] fecg_crc_c4 = crc8_byte(fecg_clean_out[7:0], fecg_crc_c3);

    // Precalculate CRC8 for 0xAA Telemetry Packet
    wire [7:0] telem_crc_c0 = crc8_byte(8'hAA, 8'h00);
    wire [7:0] telem_crc_c1 = crc8_byte(last_comp_peak[23:16], telem_crc_c0);
    wire [7:0] telem_crc_c2 = crc8_byte(last_comp_peak[15:8], telem_crc_c1);
    wire [7:0] telem_crc_c3 = crc8_byte(last_comp_peak[7:0], telem_crc_c2);
    wire [7:0] telem_crc_c4 = crc8_byte(fhr_instant_out[15:8], telem_crc_c3);
    wire [7:0] telem_crc_c5 = crc8_byte(fhr_instant_out[7:0], telem_crc_c4);
    wire [7:0] telem_crc_c6 = crc8_byte(telemetry_status_byte, telem_crc_c5);

    // Staging and Enqueuing Sequencer
    always @(posedge clk_25m) begin
        if (!sys_rst_n) begin
            fecg_tx_step        <= 3'd0;
            fecg_tx_active      <= 1'b0;
            telemetry_tx_step   <= 4'd0;
            telemetry_tx_active <= 1'b0;
            fifo_wr_en          <= 1'b0;
            fifo_wr_byte        <= 8'd0;
            staged_fecg_seq     <= 8'd0;
            staged_fecg_val     <= 24'sd0;
            staged_fecg_crc     <= 8'd0;
            staged_comp_peak    <= 24'd0;
            staged_fhr          <= 16'd0;
            staged_status       <= 8'd0;
            staged_telemetry_crc<= 8'd0;
        end else begin
            fifo_wr_en <= 1'b0;

            // Trigger FECG Packet Enqueue
            if (lp_valid) begin
                staged_fecg_seq  <= active_sample_seq;
                staged_fecg_val  <= fecg_clean_out;
                staged_fecg_crc  <= fecg_crc_c4;
                fecg_tx_active   <= 1'b1;
                fecg_tx_step     <= 3'd0;
            end

            // Trigger Telemetry Packet Enqueue
            if (beat_valid_strobe) begin
                staged_comp_peak     <= last_comp_peak;
                staged_fhr           <= fhr_instant_out;
                staged_status        <= telemetry_status_byte;
                staged_telemetry_crc <= telem_crc_c6;
                telemetry_tx_active  <= 1'b1;
                telemetry_tx_step    <= 4'd0;
            end

            // Sequentially write packet bytes into FIFO
            if (fecg_tx_active) begin
                fifo_wr_en <= 1'b1;
                case (fecg_tx_step)
                    3'd0: fifo_wr_byte <= 8'h5A;
                    3'd1: fifo_wr_byte <= staged_fecg_seq;
                    3'd2: fifo_wr_byte <= staged_fecg_val[23:16];
                    3'd3: fifo_wr_byte <= staged_fecg_val[15:8];
                    3'd4: fifo_wr_byte <= staged_fecg_val[7:0];
                    3'd5: fifo_wr_byte <= staged_fecg_crc;
                endcase

                if (fecg_tx_step == 3'd5)
                    fecg_tx_active <= 1'b0;
                else
                    fecg_tx_step <= fecg_tx_step + 1'b1;
            end else if (telemetry_tx_active) begin
                fifo_wr_en <= 1'b1;
                case (telemetry_tx_step)
                    4'd0: fifo_wr_byte <= 8'hAA;
                    4'd1: fifo_wr_byte <= staged_comp_peak[23:16];
                    4'd2: fifo_wr_byte <= staged_comp_peak[15:8];
                    4'd3: fifo_wr_byte <= staged_comp_peak[7:0];
                    4'd4: fifo_wr_byte <= staged_fhr[15:8];
                    4'd5: fifo_wr_byte <= staged_fhr[7:0];
                    4'd6: fifo_wr_byte <= staged_status;
                    4'd7: fifo_wr_byte <= staged_telemetry_crc;
                endcase

                if (telemetry_tx_step == 4'd7)
                    telemetry_tx_active <= 1'b0;
                else
                    telemetry_tx_step <= telemetry_tx_step + 1'b1;
            end
        end
    end

    // FIFO Read & UART TX Dispatcher
    assign fifo_rd_en = (tx_fifo_count > 0) && (!tx_busy) && (!tx_start);

    always @(posedge clk_25m) begin
        if (!sys_rst_n) begin
            tx_wr_ptr          <= 6'd0;
            tx_rd_ptr          <= 6'd0;
            tx_fifo_count      <= 7'd0;
            tx_start           <= 1'b0;
            tx_data            <= 8'd0;
            tx_activity_toggle <= 1'b0;
        end else begin
            tx_start <= 1'b0;

            if (fifo_wr_en) begin
                tx_fifo[tx_wr_ptr] <= fifo_wr_byte;
                tx_wr_ptr          <= tx_wr_ptr + 1'b1;
            end

            if (fifo_rd_en) begin
                tx_data            <= tx_fifo[tx_rd_ptr];
                tx_start           <= 1'b1;
                tx_rd_ptr          <= tx_rd_ptr + 1'b1;
                tx_activity_toggle <= ~tx_activity_toggle;
            end

            // Safe simultaneous read and write count accounting
            case ({fifo_wr_en, fifo_rd_en})
                2'b10:   tx_fifo_count <= tx_fifo_count + 1'b1;
                2'b01:   tx_fifo_count <= tx_fifo_count - 1'b1;
                default: tx_fifo_count <= tx_fifo_count;
            endcase
        end
    end

    // =========================================================================
    // 9. Diagnostic LEDs & Pulse Stretcher
    // =========================================================================
    // Stretch beat detection strobe to ~50 ms (1,250,000 cycles at 25 MHz)
    reg [20:0] beat_stretcher_cnt;
    reg        beat_led_pulse;

    always @(posedge clk_25m) begin
        if (!sys_rst_n) begin
            beat_stretcher_cnt <= 21'd0;
            beat_led_pulse     <= 1'b0;
        end else begin
            if (beat_valid_strobe) begin
                beat_stretcher_cnt <= 21'd1_250_000;
                beat_led_pulse     <= 1'b1;
            end else if (beat_stretcher_cnt > 0) begin
                beat_stretcher_cnt <= beat_stretcher_cnt - 1'b1;
                beat_led_pulse     <= 1'b1;
            end else begin
                beat_led_pulse     <= 1'b0;
            end
        end
    end

    assign led[0] = rx_sample_toggle;     // Toggles on every valid 0xA5 sample
    assign led[1] = tx_activity_toggle;   // Toggles on every transmitted byte
    assign led[2] = crossfade_active;     // High during 64-sample weight crossfade
    assign led[3] = beat_led_pulse;       // Flashes on confirmed QRS peak
    assign led[4] = sticky_sat;           // High if any arithmetic saturated
    assign led[5] = detector_active;      // High when warmup is complete
    assign led[6] = status_flag_2bit[0];  // Classification flag bit 0
    assign led[7] = pll_locked;           // High when PLL clock is locked

endmodule
