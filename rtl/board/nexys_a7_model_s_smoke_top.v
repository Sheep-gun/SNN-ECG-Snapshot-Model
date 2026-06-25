`timescale 1ns / 1ps

module nexys_a7_model_s_smoke_top (
    input CLK100MHZ,
    input CPU_RESETN,
    input BTNC,
    input BTNU,
    input BTNL,
    input BTNR,
    input BTND,
    output [15:0] LED,
    output CA,
    output CB,
    output CC,
    output CD,
    output CE,
    output CF,
    output CG,
    output DP,
    output [7:0] AN
);

    localparam [1:0] CLASS_NSR = 2'd0;
    localparam [1:0] CLASS_CHF = 2'd1;
    localparam [1:0] CLASS_ARR = 2'd2;
    localparam [1:0] CLASS_AFF = 2'd3;

    localparam [2:0] ST_IDLE  = 3'd0;
    localparam [2:0] ST_RESET = 3'd1;
    localparam [2:0] ST_RUN   = 3'd2;
    localparam [2:0] ST_FLUSH = 3'd3;
    localparam [2:0] ST_DONE  = 3'd4;

    localparam integer CORE_DIV_HALF = 50;
    localparam integer TICK_DIV = 1;
    localparam integer SEGMENT_TICKS = 60000;

    localparam [4:0] CH_BLANK = 5'd0;
    localparam [4:0] CH_N     = 5'd1;
    localparam [4:0] CH_S     = 5'd2;
    localparam [4:0] CH_R     = 5'd3;
    localparam [4:0] CH_C     = 5'd4;
    localparam [4:0] CH_H     = 5'd5;
    localparam [4:0] CH_F     = 5'd6;
    localparam [4:0] CH_A     = 5'd7;
    localparam [4:0] CH_O     = 5'd8;
    localparam [4:0] CH_E     = 5'd9;

    reg [1:0] rst_sync_100;
    reg [1:0] rst_sync_core;
    reg [5:0] core_div;
    reg core_clk_raw;
    wire core_clk;
    wire rst_100;
    wire rst_core_sync;
    wire core_rst;

    always @(posedge CLK100MHZ) begin
        if (!CPU_RESETN) begin
            rst_sync_100 <= 2'b11;
        end else begin
            rst_sync_100 <= {rst_sync_100[0], 1'b0};
        end
    end

    assign rst_100 = rst_sync_100[1];

    always @(posedge CLK100MHZ) begin
        if (rst_100) begin
            core_div <= 6'd0;
            core_clk_raw <= 1'b0;
        end else if (core_div == CORE_DIV_HALF - 1) begin
            core_div <= 6'd0;
            core_clk_raw <= ~core_clk_raw;
        end else begin
            core_div <= core_div + 6'd1;
        end
    end

    BUFG u_core_clk_buf (
        .I(core_clk_raw),
        .O(core_clk)
    );

    always @(posedge core_clk) begin
        if (!CPU_RESETN) begin
            rst_sync_core <= 2'b11;
        end else begin
            rst_sync_core <= {rst_sync_core[0], 1'b0};
        end
    end

    assign rst_core_sync = rst_sync_core[1];

    reg [4:0] btn_sync_0;
    reg [4:0] btn_sync_1;
    reg [4:0] btn_prev;
    wire [4:0] btn_level;
    wire [4:0] btn_pulse;

    always @(posedge core_clk) begin
        if (rst_core_sync) begin
            btn_sync_0 <= 5'd0;
            btn_sync_1 <= 5'd0;
            btn_prev <= 5'd0;
        end else begin
            btn_sync_0 <= {BTNC, BTNU, BTNL, BTNR, BTND};
            btn_sync_1 <= btn_sync_0;
            btn_prev <= btn_sync_1;
        end
    end

    assign btn_level = btn_sync_1;
    assign btn_pulse = btn_sync_1 & ~btn_prev;

    reg [15:0] lfsr;
    always @(posedge core_clk) begin
        if (rst_core_sync) begin
            lfsr <= 16'hACE1;
        end else begin
            lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
        end
    end

    reg [2:0] state;
    reg [2:0] reset_count;
    reg [9:0] clk_div;
    reg [15:0] segment_cnt;
    reg [9:0] rr_cnt;
    reg [9:0] rr_period;
    reg [7:0] beat_count;
    reg sample_tick;
    reg segment_start;
    reg segment_done;
    reg signed [11:0] adc_data;
    reg [1:0] expected_class;
    reg [1:0] pred_class_latched;
    reg pred_seen;
    reg correct_latched;
    reg [7:0] pred_valid_count;
    reg [3:0] trial_count;

    wire [1:0] pred_class;
    wire pred_valid;

    (* rom_style = "block" *) reg [11:0] demo_nsr_rom [0:SEGMENT_TICKS-1];
    (* rom_style = "block" *) reg [11:0] demo_chf_rom [0:SEGMENT_TICKS-1];
    (* rom_style = "block" *) reg [11:0] demo_arr_rom [0:SEGMENT_TICKS-1];
    (* rom_style = "block" *) reg [11:0] demo_aff_rom [0:SEGMENT_TICKS-1];

    initial begin
        $readmemh("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_nsr.mem", demo_nsr_rom);
        $readmemh("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_chf.mem", demo_chf_rom);
        $readmemh("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_arr.mem", demo_arr_rom);
        $readmemh("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_aff.mem", demo_aff_rom);
    end

    assign core_rst = rst_core_sync || (state == ST_RESET);

    function [11:0] demo_sample;
        input [1:0] mode;
        input [15:0] sample_idx;
        begin
            case (mode)
                CLASS_NSR: demo_sample = demo_nsr_rom[sample_idx];
                CLASS_CHF: demo_sample = demo_chf_rom[sample_idx];
                CLASS_ARR: demo_sample = demo_arr_rom[sample_idx];
                default:    demo_sample = demo_aff_rom[sample_idx];
            endcase
        end
    endfunction

    always @(posedge core_clk) begin
        if (rst_core_sync) begin
            state <= ST_IDLE;
            reset_count <= 3'd0;
            clk_div <= 10'd0;
            sample_tick <= 1'b0;
            segment_cnt <= 16'd0;
            rr_cnt <= 10'd0;
            rr_period <= 10'd800;
            beat_count <= 8'd0;
            segment_start <= 1'b0;
            segment_done <= 1'b0;
            adc_data <= 12'sd0;
            expected_class <= CLASS_NSR;
            pred_class_latched <= CLASS_NSR;
            pred_seen <= 1'b0;
            correct_latched <= 1'b0;
            pred_valid_count <= 8'd0;
            trial_count <= 4'd0;
        end else begin
            sample_tick <= 1'b0;
            segment_start <= 1'b0;
            segment_done <= 1'b0;

            if (btn_pulse[3]) begin
                expected_class <= CLASS_NSR;
                state <= ST_RESET;
                reset_count <= 3'd0;
                pred_seen <= 1'b0;
                correct_latched <= 1'b0;
                trial_count <= trial_count + 4'd1;
            end else if (btn_pulse[2]) begin
                expected_class <= CLASS_ARR;
                state <= ST_RESET;
                reset_count <= 3'd0;
                pred_seen <= 1'b0;
                correct_latched <= 1'b0;
                trial_count <= trial_count + 4'd1;
            end else if (btn_pulse[0]) begin
                expected_class <= CLASS_CHF;
                state <= ST_RESET;
                reset_count <= 3'd0;
                pred_seen <= 1'b0;
                correct_latched <= 1'b0;
                trial_count <= trial_count + 4'd1;
            end else if (btn_pulse[1]) begin
                expected_class <= CLASS_AFF;
                state <= ST_RESET;
                reset_count <= 3'd0;
                pred_seen <= 1'b0;
                correct_latched <= 1'b0;
                trial_count <= trial_count + 4'd1;
            end else if (btn_pulse[4]) begin
                expected_class <= lfsr[1:0];
                state <= ST_RESET;
                reset_count <= 3'd0;
                pred_seen <= 1'b0;
                correct_latched <= 1'b0;
                trial_count <= trial_count + 4'd1;
            end else begin
                case (state)
                    ST_IDLE: begin
                        adc_data <= 12'sd0;
                    end
                    ST_RESET: begin
                        segment_cnt <= 16'd0;
                        rr_cnt <= 10'd0;
                        rr_period <= 10'd0;
                        beat_count <= 8'd0;
                        adc_data <= 12'sd0;
                        clk_div <= 10'd0;
                        if (reset_count == 3'd5) begin
                            reset_count <= 3'd0;
                            state <= ST_RUN;
                        end else begin
                            reset_count <= reset_count + 3'd1;
                        end
                    end
                    ST_RUN: begin
                        adc_data <= demo_sample(expected_class, segment_cnt);
                        sample_tick <= 1'b1;

                        if (segment_cnt == 16'd0) begin
                            segment_start <= 1'b1;
                        end
                        if (segment_cnt == SEGMENT_TICKS - 1) begin
                            state <= ST_FLUSH;
                        end
                        segment_cnt <= segment_cnt + 16'd1;

                        rr_cnt <= 10'd0;
                        beat_count <= 8'd0;
                        rr_period <= 10'd0;
                    end
                    ST_FLUSH: begin
                        segment_done <= 1'b1;
                        state <= ST_DONE;
                    end
                    default: begin
                        adc_data <= 12'sd0;
                    end
                endcase
            end

            if (!(|btn_pulse) && ((state == ST_DONE) || (state == ST_FLUSH)) && pred_valid) begin
                pred_class_latched <= pred_class;
                pred_seen <= 1'b1;
                correct_latched <= (pred_class == expected_class);
                pred_valid_count <= pred_valid_count + 8'd1;
            end
        end
    end

    snn_ecg_model_a_plus_core u_model_s_core (
        .clk(core_clk),
        .rst(core_rst),
        .sample_valid(sample_tick),
        .rhythm_tick(sample_tick),
        .segment_start(segment_start),
        .segment_done(segment_done),
        .adc_data(adc_data),
        .pred_class(pred_class),
        .pred_valid(pred_valid)
    );

    reg [25:0] blink_cnt;
    reg [16:0] refresh_cnt;
    reg [1:0] pred_seen_sync_100;
    reg [1:0] pred_class_sync_100;
    reg correct_sync_100;

    always @(posedge CLK100MHZ) begin
        if (rst_100) begin
            blink_cnt <= 26'd0;
            refresh_cnt <= 17'd0;
            pred_seen_sync_100 <= 2'b00;
            pred_class_sync_100 <= CLASS_NSR;
            correct_sync_100 <= 1'b0;
        end else begin
            blink_cnt <= blink_cnt + 26'd1;
            refresh_cnt <= refresh_cnt + 17'd1;
            pred_seen_sync_100 <= {pred_seen_sync_100[0], pred_seen};
            if (pred_seen) begin
                pred_class_sync_100 <= pred_class_latched;
                correct_sync_100 <= correct_latched;
            end
        end
    end

    wire [2:0] scan_digit = refresh_cnt[15:13];
    wire display_result_valid = pred_seen_sync_100[1];
    reg [7:0] an_reg;
    reg [6:0] seg_reg;
    reg [4:0] current_char;

    function [4:0] class_char;
        input [1:0] cls;
        input [1:0] pos;
        begin
            case (cls)
                CLASS_NSR: begin
                    case (pos)
                        2'd0: class_char = CH_N;
                        2'd1: class_char = CH_S;
                        2'd2: class_char = CH_R;
                        default: class_char = CH_BLANK;
                    endcase
                end
                CLASS_CHF: begin
                    case (pos)
                        2'd0: class_char = CH_C;
                        2'd1: class_char = CH_H;
                        2'd2: class_char = CH_F;
                        default: class_char = CH_BLANK;
                    endcase
                end
                CLASS_ARR: begin
                    case (pos)
                        2'd0: class_char = CH_A;
                        2'd1: class_char = CH_R;
                        2'd2: class_char = CH_R;
                        default: class_char = CH_BLANK;
                    endcase
                end
                default: begin
                    case (pos)
                        2'd0: class_char = CH_A;
                        2'd1: class_char = CH_F;
                        2'd2: class_char = CH_F;
                        default: class_char = CH_BLANK;
                    endcase
                end
            endcase
        end
    endfunction

    function [4:0] result_char;
        input valid;
        input corr;
        input [1:0] pos;
        begin
            if (!valid) begin
                result_char = CH_BLANK;
            end else if (corr) begin
                case (pos)
                    2'd0: result_char = CH_C;
                    2'd1: result_char = CH_O;
                    2'd2: result_char = CH_R;
                    default: result_char = CH_R;
                endcase
            end else begin
                case (pos)
                    2'd0: result_char = CH_E;
                    2'd1: result_char = CH_R;
                    2'd2: result_char = CH_R;
                    default: result_char = CH_BLANK;
                endcase
            end
        end
    endfunction

    function [6:0] sevenseg;
        input [4:0] ch;
        begin
            case (ch)
                CH_N:     sevenseg = 7'b1101010;
                CH_S:     sevenseg = 7'b0100100;
                CH_R:     sevenseg = 7'b1111010;
                CH_C:     sevenseg = 7'b0110001;
                CH_H:     sevenseg = 7'b1001000;
                CH_F:     sevenseg = 7'b0111000;
                CH_A:     sevenseg = 7'b0001000;
                CH_O:     sevenseg = 7'b0000001;
                CH_E:     sevenseg = 7'b0110000;
                default:  sevenseg = 7'b1111111;
            endcase
        end
    endfunction

    always @(*) begin
        an_reg = 8'b11111111;
        if (!display_result_valid) begin
            current_char = CH_BLANK;
            an_reg = 8'b11111111;
        end else begin
            an_reg[scan_digit] = 1'b0;
            case (scan_digit)
                3'd7: current_char = class_char(pred_class_sync_100, 2'd0);
                3'd6: current_char = class_char(pred_class_sync_100, 2'd1);
                3'd5: current_char = class_char(pred_class_sync_100, 2'd2);
                3'd4: current_char = class_char(pred_class_sync_100, 2'd3);
                3'd3: current_char = result_char(display_result_valid, correct_sync_100, 2'd0);
                3'd2: current_char = result_char(display_result_valid, correct_sync_100, 2'd1);
                3'd1: current_char = result_char(display_result_valid, correct_sync_100, 2'd2);
                default: current_char = result_char(display_result_valid, correct_sync_100, 2'd3);
            endcase
        end
        seg_reg = sevenseg(current_char);
    end

    assign {CA, CB, CC, CD, CE, CF, CG} = seg_reg;
    assign DP = 1'b1;
    assign AN = an_reg;

    assign LED[0] = blink_cnt[25];
    assign LED[1] = (state == ST_RUN);
    assign LED[2] = pred_seen;
    assign LED[3] = correct_latched;
    assign LED[5:4] = expected_class;
    assign LED[7:6] = pred_class_latched;
    assign LED[11:8] = trial_count;
    assign LED[15:12] = {BTNC, BTNU, BTNL, BTNR};

endmodule
