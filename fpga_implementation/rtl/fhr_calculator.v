// =============================================================================
// Module: fhr_calculator
// Description: Fetal Heart Rate (FHR) Calculator with 251-Word Frozen Integer ROM.
//              Translates validated median RR intervals in the physiological range
//              [50, 300] samples (200 ms to 1200 ms at 250 Hz) into instantaneous
//              and held FHR values in 0.1 bpm units:
//                FHR = round(150000 / RR)
//              - Range: 50.0 bpm (RR=300) to 300.0 bpm (RR=50).
//              - Storage: 251 words x 16 bits distributed ROM / LUT RAM.
//              - Warmup output: 0 bpm during warmup (detector_active = 0).
//              - Post-warmup initial hold: 1400 (140.0 bpm) until first normal beat.
//
// Target: AMD / Xilinx Spartan-7 FPGA (XC7S50-1CSGA324C)
// Toolchain: AMD Vivado 2022.2+
//
// Latency: 1 clock cycle (registered FHR update)
// =============================================================================

`timescale 1ns / 1ps

module fhr_calculator #(
    parameter integer RR_WIDTH   = 16,        // RR interval width
    parameter integer FHR_WIDTH  = 16,        // FHR output width (0.1 bpm units)
    parameter integer RR_MIN     = 50,        // Minimum RR (300 bpm @ 250 Hz)
    parameter integer RR_MAX     = 300,       // Maximum RR (50 bpm @ 250 Hz)
    parameter integer LUT_SIZE   = 251        // RR_MAX - RR_MIN + 1
)(
    input  wire                          clk,               // Master system clock (100 MHz)
    input  wire                          rst_n,             // Synchronous active-low reset
    input  wire                          enable,            // Block enable / clock enable
    input  wire                          detector_active,   // Active high after 512-sample warmup
    input  wire                          rr_update_strobe,  // 1-cycle strobe from interval fusion
    input  wire [RR_WIDTH-1:0]           med_rr_in,         // Pure integer median RR

    output reg  [FHR_WIDTH-1:0]          fhr_instant_out,   // Instantaneous FHR for latest beat
    output wire [FHR_WIDTH-1:0]          fhr_stream_out,    // Continuous held FHR stream
    output reg                           fhr_valid_strobe,  // 1-cycle strobe when FHR is updated
    output reg                           fhr_lut_overflow   // Sticky flag: med_rr < 50 or > 300
);

    // -------------------------------------------------------------------------
    // Address Clamping & Range Check
    // -------------------------------------------------------------------------
    wire [7:0] lut_addr;
    wire       is_underflow;
    wire       is_overflow;

    assign is_underflow = (med_rr_in < RR_MIN);
    assign is_overflow  = (med_rr_in > RR_MAX);

    assign lut_addr = is_underflow ? 8'd0 :
                      is_overflow  ? 8'd250 :
                      (med_rr_in[7:0] - 8'd50);

    // -------------------------------------------------------------------------
    // 251-Word Combinational ROM Lookup Table: round(150000 / RR)
    // Synthesizes cleanly into Distributed ROM (LUT ROM) in Spartan-7.
    // -------------------------------------------------------------------------
    reg [FHR_WIDTH-1:0] fhr_rom_val;

    always @(*) begin
        case (lut_addr)
            8'd0: fhr_rom_val = 16'd3000; // RR = 50
            8'd1: fhr_rom_val = 16'd2941; // RR = 51
            8'd2: fhr_rom_val = 16'd2885; // RR = 52
            8'd3: fhr_rom_val = 16'd2830; // RR = 53
            8'd4: fhr_rom_val = 16'd2778; // RR = 54
            8'd5: fhr_rom_val = 16'd2727; // RR = 55
            8'd6: fhr_rom_val = 16'd2679; // RR = 56
            8'd7: fhr_rom_val = 16'd2632; // RR = 57
            8'd8: fhr_rom_val = 16'd2586; // RR = 58
            8'd9: fhr_rom_val = 16'd2542; // RR = 59
            8'd10: fhr_rom_val = 16'd2500; // RR = 60
            8'd11: fhr_rom_val = 16'd2459; // RR = 61
            8'd12: fhr_rom_val = 16'd2419; // RR = 62
            8'd13: fhr_rom_val = 16'd2381; // RR = 63
            8'd14: fhr_rom_val = 16'd2344; // RR = 64
            8'd15: fhr_rom_val = 16'd2308; // RR = 65
            8'd16: fhr_rom_val = 16'd2273; // RR = 66
            8'd17: fhr_rom_val = 16'd2239; // RR = 67
            8'd18: fhr_rom_val = 16'd2206; // RR = 68
            8'd19: fhr_rom_val = 16'd2174; // RR = 69
            8'd20: fhr_rom_val = 16'd2143; // RR = 70
            8'd21: fhr_rom_val = 16'd2113; // RR = 71
            8'd22: fhr_rom_val = 16'd2083; // RR = 72
            8'd23: fhr_rom_val = 16'd2055; // RR = 73
            8'd24: fhr_rom_val = 16'd2027; // RR = 74
            8'd25: fhr_rom_val = 16'd2000; // RR = 75
            8'd26: fhr_rom_val = 16'd1974; // RR = 76
            8'd27: fhr_rom_val = 16'd1948; // RR = 77
            8'd28: fhr_rom_val = 16'd1923; // RR = 78
            8'd29: fhr_rom_val = 16'd1899; // RR = 79
            8'd30: fhr_rom_val = 16'd1875; // RR = 80
            8'd31: fhr_rom_val = 16'd1852; // RR = 81
            8'd32: fhr_rom_val = 16'd1829; // RR = 82
            8'd33: fhr_rom_val = 16'd1807; // RR = 83
            8'd34: fhr_rom_val = 16'd1786; // RR = 84
            8'd35: fhr_rom_val = 16'd1765; // RR = 85
            8'd36: fhr_rom_val = 16'd1744; // RR = 86
            8'd37: fhr_rom_val = 16'd1724; // RR = 87
            8'd38: fhr_rom_val = 16'd1705; // RR = 88
            8'd39: fhr_rom_val = 16'd1685; // RR = 89
            8'd40: fhr_rom_val = 16'd1667; // RR = 90
            8'd41: fhr_rom_val = 16'd1648; // RR = 91
            8'd42: fhr_rom_val = 16'd1630; // RR = 92
            8'd43: fhr_rom_val = 16'd1613; // RR = 93
            8'd44: fhr_rom_val = 16'd1596; // RR = 94
            8'd45: fhr_rom_val = 16'd1579; // RR = 95
            8'd46: fhr_rom_val = 16'd1562; // RR = 96
            8'd47: fhr_rom_val = 16'd1546; // RR = 97
            8'd48: fhr_rom_val = 16'd1531; // RR = 98
            8'd49: fhr_rom_val = 16'd1515; // RR = 99
            8'd50: fhr_rom_val = 16'd1500; // RR = 100
            8'd51: fhr_rom_val = 16'd1485; // RR = 101
            8'd52: fhr_rom_val = 16'd1471; // RR = 102
            8'd53: fhr_rom_val = 16'd1456; // RR = 103
            8'd54: fhr_rom_val = 16'd1442; // RR = 104
            8'd55: fhr_rom_val = 16'd1429; // RR = 105
            8'd56: fhr_rom_val = 16'd1415; // RR = 106
            8'd57: fhr_rom_val = 16'd1402; // RR = 107
            8'd58: fhr_rom_val = 16'd1389; // RR = 108
            8'd59: fhr_rom_val = 16'd1376; // RR = 109
            8'd60: fhr_rom_val = 16'd1364; // RR = 110
            8'd61: fhr_rom_val = 16'd1351; // RR = 111
            8'd62: fhr_rom_val = 16'd1339; // RR = 112
            8'd63: fhr_rom_val = 16'd1327; // RR = 113
            8'd64: fhr_rom_val = 16'd1316; // RR = 114
            8'd65: fhr_rom_val = 16'd1304; // RR = 115
            8'd66: fhr_rom_val = 16'd1293; // RR = 116
            8'd67: fhr_rom_val = 16'd1282; // RR = 117
            8'd68: fhr_rom_val = 16'd1271; // RR = 118
            8'd69: fhr_rom_val = 16'd1261; // RR = 119
            8'd70: fhr_rom_val = 16'd1250; // RR = 120
            8'd71: fhr_rom_val = 16'd1240; // RR = 121
            8'd72: fhr_rom_val = 16'd1230; // RR = 122
            8'd73: fhr_rom_val = 16'd1220; // RR = 123
            8'd74: fhr_rom_val = 16'd1210; // RR = 124
            8'd75: fhr_rom_val = 16'd1200; // RR = 125
            8'd76: fhr_rom_val = 16'd1190; // RR = 126
            8'd77: fhr_rom_val = 16'd1181; // RR = 127
            8'd78: fhr_rom_val = 16'd1172; // RR = 128
            8'd79: fhr_rom_val = 16'd1163; // RR = 129
            8'd80: fhr_rom_val = 16'd1154; // RR = 130
            8'd81: fhr_rom_val = 16'd1145; // RR = 131
            8'd82: fhr_rom_val = 16'd1136; // RR = 132
            8'd83: fhr_rom_val = 16'd1128; // RR = 133
            8'd84: fhr_rom_val = 16'd1119; // RR = 134
            8'd85: fhr_rom_val = 16'd1111; // RR = 135
            8'd86: fhr_rom_val = 16'd1103; // RR = 136
            8'd87: fhr_rom_val = 16'd1095; // RR = 137
            8'd88: fhr_rom_val = 16'd1087; // RR = 138
            8'd89: fhr_rom_val = 16'd1079; // RR = 139
            8'd90: fhr_rom_val = 16'd1071; // RR = 140
            8'd91: fhr_rom_val = 16'd1064; // RR = 141
            8'd92: fhr_rom_val = 16'd1056; // RR = 142
            8'd93: fhr_rom_val = 16'd1049; // RR = 143
            8'd94: fhr_rom_val = 16'd1042; // RR = 144
            8'd95: fhr_rom_val = 16'd1034; // RR = 145
            8'd96: fhr_rom_val = 16'd1027; // RR = 146
            8'd97: fhr_rom_val = 16'd1020; // RR = 147
            8'd98: fhr_rom_val = 16'd1014; // RR = 148
            8'd99: fhr_rom_val = 16'd1007; // RR = 149
            8'd100: fhr_rom_val = 16'd1000; // RR = 150
            8'd101: fhr_rom_val = 16'd993; // RR = 151
            8'd102: fhr_rom_val = 16'd987; // RR = 152
            8'd103: fhr_rom_val = 16'd980; // RR = 153
            8'd104: fhr_rom_val = 16'd974; // RR = 154
            8'd105: fhr_rom_val = 16'd968; // RR = 155
            8'd106: fhr_rom_val = 16'd962; // RR = 156
            8'd107: fhr_rom_val = 16'd955; // RR = 157
            8'd108: fhr_rom_val = 16'd949; // RR = 158
            8'd109: fhr_rom_val = 16'd943; // RR = 159
            8'd110: fhr_rom_val = 16'd938; // RR = 160
            8'd111: fhr_rom_val = 16'd932; // RR = 161
            8'd112: fhr_rom_val = 16'd926; // RR = 162
            8'd113: fhr_rom_val = 16'd920; // RR = 163
            8'd114: fhr_rom_val = 16'd915; // RR = 164
            8'd115: fhr_rom_val = 16'd909; // RR = 165
            8'd116: fhr_rom_val = 16'd904; // RR = 166
            8'd117: fhr_rom_val = 16'd898; // RR = 167
            8'd118: fhr_rom_val = 16'd893; // RR = 168
            8'd119: fhr_rom_val = 16'd888; // RR = 169
            8'd120: fhr_rom_val = 16'd882; // RR = 170
            8'd121: fhr_rom_val = 16'd877; // RR = 171
            8'd122: fhr_rom_val = 16'd872; // RR = 172
            8'd123: fhr_rom_val = 16'd867; // RR = 173
            8'd124: fhr_rom_val = 16'd862; // RR = 174
            8'd125: fhr_rom_val = 16'd857; // RR = 175
            8'd126: fhr_rom_val = 16'd852; // RR = 176
            8'd127: fhr_rom_val = 16'd847; // RR = 177
            8'd128: fhr_rom_val = 16'd843; // RR = 178
            8'd129: fhr_rom_val = 16'd838; // RR = 179
            8'd130: fhr_rom_val = 16'd833; // RR = 180
            8'd131: fhr_rom_val = 16'd829; // RR = 181
            8'd132: fhr_rom_val = 16'd824; // RR = 182
            8'd133: fhr_rom_val = 16'd820; // RR = 183
            8'd134: fhr_rom_val = 16'd815; // RR = 184
            8'd135: fhr_rom_val = 16'd811; // RR = 185
            8'd136: fhr_rom_val = 16'd806; // RR = 186
            8'd137: fhr_rom_val = 16'd802; // RR = 187
            8'd138: fhr_rom_val = 16'd798; // RR = 188
            8'd139: fhr_rom_val = 16'd794; // RR = 189
            8'd140: fhr_rom_val = 16'd789; // RR = 190
            8'd141: fhr_rom_val = 16'd785; // RR = 191
            8'd142: fhr_rom_val = 16'd781; // RR = 192
            8'd143: fhr_rom_val = 16'd777; // RR = 193
            8'd144: fhr_rom_val = 16'd773; // RR = 194
            8'd145: fhr_rom_val = 16'd769; // RR = 195
            8'd146: fhr_rom_val = 16'd765; // RR = 196
            8'd147: fhr_rom_val = 16'd761; // RR = 197
            8'd148: fhr_rom_val = 16'd758; // RR = 198
            8'd149: fhr_rom_val = 16'd754; // RR = 199
            8'd150: fhr_rom_val = 16'd750; // RR = 200
            8'd151: fhr_rom_val = 16'd746; // RR = 201
            8'd152: fhr_rom_val = 16'd743; // RR = 202
            8'd153: fhr_rom_val = 16'd739; // RR = 203
            8'd154: fhr_rom_val = 16'd735; // RR = 204
            8'd155: fhr_rom_val = 16'd732; // RR = 205
            8'd156: fhr_rom_val = 16'd728; // RR = 206
            8'd157: fhr_rom_val = 16'd725; // RR = 207
            8'd158: fhr_rom_val = 16'd721; // RR = 208
            8'd159: fhr_rom_val = 16'd718; // RR = 209
            8'd160: fhr_rom_val = 16'd714; // RR = 210
            8'd161: fhr_rom_val = 16'd711; // RR = 211
            8'd162: fhr_rom_val = 16'd708; // RR = 212
            8'd163: fhr_rom_val = 16'd704; // RR = 213
            8'd164: fhr_rom_val = 16'd701; // RR = 214
            8'd165: fhr_rom_val = 16'd698; // RR = 215
            8'd166: fhr_rom_val = 16'd694; // RR = 216
            8'd167: fhr_rom_val = 16'd691; // RR = 217
            8'd168: fhr_rom_val = 16'd688; // RR = 218
            8'd169: fhr_rom_val = 16'd685; // RR = 219
            8'd170: fhr_rom_val = 16'd682; // RR = 220
            8'd171: fhr_rom_val = 16'd679; // RR = 221
            8'd172: fhr_rom_val = 16'd676; // RR = 222
            8'd173: fhr_rom_val = 16'd673; // RR = 223
            8'd174: fhr_rom_val = 16'd670; // RR = 224
            8'd175: fhr_rom_val = 16'd667; // RR = 225
            8'd176: fhr_rom_val = 16'd664; // RR = 226
            8'd177: fhr_rom_val = 16'd661; // RR = 227
            8'd178: fhr_rom_val = 16'd658; // RR = 228
            8'd179: fhr_rom_val = 16'd655; // RR = 229
            8'd180: fhr_rom_val = 16'd652; // RR = 230
            8'd181: fhr_rom_val = 16'd649; // RR = 231
            8'd182: fhr_rom_val = 16'd647; // RR = 232
            8'd183: fhr_rom_val = 16'd644; // RR = 233
            8'd184: fhr_rom_val = 16'd641; // RR = 234
            8'd185: fhr_rom_val = 16'd638; // RR = 235
            8'd186: fhr_rom_val = 16'd636; // RR = 236
            8'd187: fhr_rom_val = 16'd633; // RR = 237
            8'd188: fhr_rom_val = 16'd630; // RR = 238
            8'd189: fhr_rom_val = 16'd628; // RR = 239
            8'd190: fhr_rom_val = 16'd625; // RR = 240
            8'd191: fhr_rom_val = 16'd622; // RR = 241
            8'd192: fhr_rom_val = 16'd620; // RR = 242
            8'd193: fhr_rom_val = 16'd617; // RR = 243
            8'd194: fhr_rom_val = 16'd615; // RR = 244
            8'd195: fhr_rom_val = 16'd612; // RR = 245
            8'd196: fhr_rom_val = 16'd610; // RR = 246
            8'd197: fhr_rom_val = 16'd607; // RR = 247
            8'd198: fhr_rom_val = 16'd605; // RR = 248
            8'd199: fhr_rom_val = 16'd602; // RR = 249
            8'd200: fhr_rom_val = 16'd600; // RR = 250
            8'd201: fhr_rom_val = 16'd598; // RR = 251
            8'd202: fhr_rom_val = 16'd595; // RR = 252
            8'd203: fhr_rom_val = 16'd593; // RR = 253
            8'd204: fhr_rom_val = 16'd591; // RR = 254
            8'd205: fhr_rom_val = 16'd588; // RR = 255
            8'd206: fhr_rom_val = 16'd586; // RR = 256
            8'd207: fhr_rom_val = 16'd584; // RR = 257
            8'd208: fhr_rom_val = 16'd581; // RR = 258
            8'd209: fhr_rom_val = 16'd579; // RR = 259
            8'd210: fhr_rom_val = 16'd577; // RR = 260
            8'd211: fhr_rom_val = 16'd575; // RR = 261
            8'd212: fhr_rom_val = 16'd573; // RR = 262
            8'd213: fhr_rom_val = 16'd570; // RR = 263
            8'd214: fhr_rom_val = 16'd568; // RR = 264
            8'd215: fhr_rom_val = 16'd566; // RR = 265
            8'd216: fhr_rom_val = 16'd564; // RR = 266
            8'd217: fhr_rom_val = 16'd562; // RR = 267
            8'd218: fhr_rom_val = 16'd560; // RR = 268
            8'd219: fhr_rom_val = 16'd558; // RR = 269
            8'd220: fhr_rom_val = 16'd556; // RR = 270
            8'd221: fhr_rom_val = 16'd554; // RR = 271
            8'd222: fhr_rom_val = 16'd551; // RR = 272
            8'd223: fhr_rom_val = 16'd549; // RR = 273
            8'd224: fhr_rom_val = 16'd547; // RR = 274
            8'd225: fhr_rom_val = 16'd545; // RR = 275
            8'd226: fhr_rom_val = 16'd543; // RR = 276
            8'd227: fhr_rom_val = 16'd542; // RR = 277
            8'd228: fhr_rom_val = 16'd540; // RR = 278
            8'd229: fhr_rom_val = 16'd538; // RR = 279
            8'd230: fhr_rom_val = 16'd536; // RR = 280
            8'd231: fhr_rom_val = 16'd534; // RR = 281
            8'd232: fhr_rom_val = 16'd532; // RR = 282
            8'd233: fhr_rom_val = 16'd530; // RR = 283
            8'd234: fhr_rom_val = 16'd528; // RR = 284
            8'd235: fhr_rom_val = 16'd526; // RR = 285
            8'd236: fhr_rom_val = 16'd524; // RR = 286
            8'd237: fhr_rom_val = 16'd523; // RR = 287
            8'd238: fhr_rom_val = 16'd521; // RR = 288
            8'd239: fhr_rom_val = 16'd519; // RR = 289
            8'd240: fhr_rom_val = 16'd517; // RR = 290
            8'd241: fhr_rom_val = 16'd515; // RR = 291
            8'd242: fhr_rom_val = 16'd514; // RR = 292
            8'd243: fhr_rom_val = 16'd512; // RR = 293
            8'd244: fhr_rom_val = 16'd510; // RR = 294
            8'd245: fhr_rom_val = 16'd508; // RR = 295
            8'd246: fhr_rom_val = 16'd507; // RR = 296
            8'd247: fhr_rom_val = 16'd505; // RR = 297
            8'd248: fhr_rom_val = 16'd503; // RR = 298
            8'd249: fhr_rom_val = 16'd502; // RR = 299
            8'd250: fhr_rom_val = 16'd500; // RR = 300
            default: fhr_rom_val = 16'd1400;
        endcase
    end

    // -------------------------------------------------------------------------
    // Sequential State & Hold Stream Logic
    // -------------------------------------------------------------------------
    reg [FHR_WIDTH-1:0] fhr_hold_reg;

    // During warmup (detector_active = 0), fhr_stream is 0.
    // Once warmup finishes, fhr_stream outputs fhr_hold_reg (initialized to 1400 = 140.0 bpm).
    assign fhr_stream_out = detector_active ? fhr_hold_reg : 16'd0;

    always @(posedge clk) begin
        if (!rst_n) begin
            fhr_instant_out  <= 16'd0;
            fhr_hold_reg     <= 16'd1400; // Default 140.0 bpm
            fhr_valid_strobe <= 1'b0;
            fhr_lut_overflow <= 1'b0;
        end else if (enable) begin
            fhr_valid_strobe <= 1'b0;

            if (rr_update_strobe && detector_active) begin
                fhr_instant_out  <= fhr_rom_val;
                fhr_hold_reg     <= fhr_rom_val;
                fhr_valid_strobe <= 1'b1;

                if (is_underflow || is_overflow) begin
                    fhr_lut_overflow <= 1'b1;
                end
            end
        end else begin
            fhr_valid_strobe <= 1'b0;
        end
    end

endmodule
