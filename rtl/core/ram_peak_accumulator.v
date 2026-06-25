`timescale 1ns / 1ps

module ram_peak_accumulator #(
    parameter ADC_WIDTH     = 12,
    parameter AMP_WIDTH     = 13,
    parameter CODE_WIDTH    = 6,
    parameter BANK_SIZE     = 32,
    parameter BANK_BASE     = 64,
    parameter BANK_STEP     = 32,
    parameter POST_WIDTH    = 8,
    parameter RAM_POST_HOLD = 80
)(
    input clk,
    input rst,
    input clear,
    input sample_valid,
    input ram_window_open,
    input beat_spike,
    input signed [ADC_WIDTH-1:0] adc_data,
    input signed [ADC_WIDTH-1:0] baseline,
    output reg amp_window_active,
    output reg [CODE_WIDTH-1:0] amp_window_cnt,
    output reg [AMP_WIDTH-1:0] r_peak_abs,
    output reg ram_amp_spike,
    output reg [CODE_WIDTH-1:0] ram_amp_code
);

    wire signed [ADC_WIDTH:0] sample_ext;
    wire signed [ADC_WIDTH:0] baseline_ext;
    wire signed [ADC_WIDTH:0] amp_delta;
    wire [AMP_WIDTH-1:0] pos_amp;

    reg ram_window_open_d;
    reg beat_seen;
    reg post_hold_active;
    reg [POST_WIDTH-1:0] post_hold_cnt;
    reg [CODE_WIDTH-1:0] sample_code;
    reg [CODE_WIDTH-1:0] peak_code_next;

    wire capture_active;

    assign sample_ext = {adc_data[ADC_WIDTH-1], adc_data};
    assign baseline_ext = {baseline[ADC_WIDTH-1], baseline};
    assign amp_delta = sample_ext - baseline_ext;
    assign pos_amp = amp_delta[ADC_WIDTH] ? {AMP_WIDTH{1'b0}} : amp_delta;
    assign capture_active = ram_window_open || post_hold_active;

    function [CODE_WIDTH-1:0] encode_amp_code;
        input [AMP_WIDTH-1:0] amplitude;
        reg [CODE_WIDTH-1:0] code_work;
        integer threshold;
        integer bank_i;
        begin
            code_work = {CODE_WIDTH{1'b0}};
            for (bank_i = 0; bank_i < BANK_SIZE; bank_i = bank_i + 1) begin
                threshold = BANK_BASE + (bank_i * BANK_STEP);
                if (amplitude >= threshold)
                    code_work = bank_i + 1;
            end
            encode_amp_code = code_work;
        end
    endfunction

    always @(posedge clk) begin
        if (rst) begin
            amp_window_active <= 1'b0;
            amp_window_cnt <= {CODE_WIDTH{1'b0}};
            r_peak_abs <= {AMP_WIDTH{1'b0}};
            ram_amp_spike <= 1'b0;
            ram_amp_code <= {CODE_WIDTH{1'b0}};
            ram_window_open_d <= 1'b0;
            beat_seen <= 1'b0;
            post_hold_active <= 1'b0;
            post_hold_cnt <= {POST_WIDTH{1'b0}};
        end else begin
            ram_amp_spike <= 1'b0;
            ram_window_open_d <= ram_window_open;

            if (clear) begin
                amp_window_active <= 1'b0;
                amp_window_cnt <= {CODE_WIDTH{1'b0}};
                r_peak_abs <= {AMP_WIDTH{1'b0}};
                ram_amp_spike <= 1'b0;
                ram_amp_code <= {CODE_WIDTH{1'b0}};
                ram_window_open_d <= 1'b0;
                beat_seen <= 1'b0;
                post_hold_active <= 1'b0;
                post_hold_cnt <= {POST_WIDTH{1'b0}};
            end else begin
                if (ram_window_open && !ram_window_open_d) begin
                    amp_window_active <= 1'b1;
                    amp_window_cnt <= {CODE_WIDTH{1'b0}};
                    r_peak_abs <= {AMP_WIDTH{1'b0}};
                    beat_seen <= 1'b0;
                    post_hold_active <= 1'b0;
                    post_hold_cnt <= {POST_WIDTH{1'b0}};
                end

                if (capture_active) begin
                    peak_code_next = r_peak_abs[CODE_WIDTH-1:0];
                    if (sample_valid) begin
                        sample_code = encode_amp_code(pos_amp);
                        if (sample_code > peak_code_next)
                            peak_code_next = sample_code;
                        r_peak_abs <= {{(AMP_WIDTH-CODE_WIDTH){1'b0}}, peak_code_next};
                    end

                    if (beat_spike && ram_window_open) begin
                        beat_seen <= 1'b1;
                        post_hold_active <= 1'b1;
                        post_hold_cnt <= RAM_POST_HOLD;
                    end else if (post_hold_active && sample_valid) begin
                        if (post_hold_cnt <= 1) begin
                            post_hold_active <= 1'b0;
                            post_hold_cnt <= {POST_WIDTH{1'b0}};
                        end else begin
                            post_hold_cnt <= post_hold_cnt - 1'b1;
                        end
                    end
                end

                if (!ram_window_open && ram_window_open_d && !beat_seen && !post_hold_active) begin
                    amp_window_active <= 1'b0;
                    amp_window_cnt <= r_peak_abs[CODE_WIDTH-1:0];
                    beat_seen <= 1'b0;
                end

                if (post_hold_active && sample_valid && (post_hold_cnt <= 1)) begin
                    amp_window_active <= 1'b0;
                    amp_window_cnt <= r_peak_abs[CODE_WIDTH-1:0];
                    if (beat_seen) begin
                        ram_amp_code <= r_peak_abs[CODE_WIDTH-1:0];
                        ram_amp_spike <= 1'b1;
                    end
                    beat_seen <= 1'b0;
                end
            end
        end
    end

endmodule
