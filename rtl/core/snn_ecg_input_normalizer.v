`timescale 1ns / 1ps

module snn_ecg_input_normalizer #(
    parameter ADC_WIDTH = 12,
    parameter BASE_SHIFT = 8,
    parameter ENV_DECAY_SHIFT = 6,
    parameter GAIN_LOW_TH = 96,
    parameter GAIN_MID_TH = 192,
    parameter GAIN_HIGH_TH = 768,
    parameter ENABLE_ADAPTIVE_GAIN = 1
)(
    input clk,
    input rst,
    input clear,
    input sample_valid,
    input signed [ADC_WIDTH-1:0] adc_in,
    output reg signed [ADC_WIDTH-1:0] adc_out,
    output reg signed [ADC_WIDTH+3:0] baseline_mem,
    output reg [ADC_WIDTH+3:0] envelope_mem
);

    localparam signed [ADC_WIDTH-1:0] ADC_MAX = {1'b0, {(ADC_WIDTH-1){1'b1}}};
    localparam signed [ADC_WIDTH-1:0] ADC_MIN = {1'b1, {(ADC_WIDTH-1){1'b0}}};

    reg sample_seen;
    reg signed [ADC_WIDTH+3:0] adc_ext;
    reg signed [ADC_WIDTH+4:0] centered_ext;
    reg [ADC_WIDTH+4:0] centered_abs;
    reg signed [ADC_WIDTH+7:0] scaled_ext;
    reg signed [ADC_WIDTH+3:0] base_delta;
    reg [ADC_WIDTH+3:0] env_decay;
    reg [ADC_WIDTH+3:0] env_next;

    always @* begin
        adc_ext = {{4{adc_in[ADC_WIDTH-1]}}, adc_in};
        centered_ext = {adc_ext[ADC_WIDTH+3], adc_ext} - {baseline_mem[ADC_WIDTH+3], baseline_mem};
        centered_abs = centered_ext[ADC_WIDTH+4] ? ((~centered_ext) + 1'b1) : centered_ext;
        base_delta = centered_ext[ADC_WIDTH+4:1] >>> (BASE_SHIFT - 1);
        env_decay = envelope_mem >> ENV_DECAY_SHIFT;
        if (envelope_mem > env_decay)
            env_next = envelope_mem - env_decay + centered_abs[ADC_WIDTH+4:1];
        else
            env_next = centered_abs[ADC_WIDTH+4:1];

        scaled_ext = {{3{centered_ext[ADC_WIDTH+4]}}, centered_ext};
        if (ENABLE_ADAPTIVE_GAIN != 0) begin
            if (envelope_mem < GAIN_LOW_TH)
                scaled_ext = {{1{centered_ext[ADC_WIDTH+4]}}, centered_ext, 2'b00};
            else if (envelope_mem < GAIN_MID_TH)
                scaled_ext = {{2{centered_ext[ADC_WIDTH+4]}}, centered_ext, 1'b0};
            else if (envelope_mem > GAIN_HIGH_TH)
                scaled_ext = {{4{centered_ext[ADC_WIDTH+4]}}, centered_ext[ADC_WIDTH+4:1]};
        end
    end

    always @(posedge clk) begin
        if (rst || clear) begin
            adc_out <= {ADC_WIDTH{1'b0}};
            baseline_mem <= {(ADC_WIDTH+4){1'b0}};
            envelope_mem <= {(ADC_WIDTH+4){1'b0}};
            sample_seen <= 1'b0;
        end else if (sample_valid) begin
            if (!sample_seen) begin
                baseline_mem <= adc_ext;
                envelope_mem <= {(ADC_WIDTH+4){1'b0}};
                adc_out <= {ADC_WIDTH{1'b0}};
                sample_seen <= 1'b1;
            end else begin
                baseline_mem <= baseline_mem + base_delta;
                envelope_mem <= env_next;

                if (scaled_ext > ADC_MAX)
                    adc_out <= ADC_MAX;
                else if (scaled_ext < ADC_MIN)
                    adc_out <= ADC_MIN;
                else
                    adc_out <= scaled_ext[ADC_WIDTH-1:0];
            end
        end
    end

endmodule
