`timescale 1ns / 1ps

module ecg_event_encoder #(
    parameter ADC_WIDTH = 12,
    parameter T_EVENT   = 20,
    parameter T_SLOPE   = 4,
    parameter ENABLE_AMP_EVENT = 0,
    parameter T_AMP_EVENT = 4
)(
    input clk,
    input rst,
    input sample_valid,
    input signed [ADC_WIDTH-1:0] adc_data,
    output reg signed [ADC_WIDTH-1:0] prev_sample,
    output reg signed [ADC_WIDTH:0] delta,
    output reg [ADC_WIDTH:0] abs_delta,
    output reg sample_seen,
    output reg strong_event,
    output reg up_event,
    output reg down_event,
    output reg slope_valid
);

    wire signed [ADC_WIDTH:0] adc_ext;
    wire signed [ADC_WIDTH:0] prev_ext;
    wire signed [ADC_WIDTH:0] delta_calc;
    wire [ADC_WIDTH:0] abs_delta_calc;
    wire signed [ADC_WIDTH:0] slope_pos_th;
    wire signed [ADC_WIDTH:0] slope_neg_th;
    wire [ADC_WIDTH:0] abs_adc_calc;
    wire [ADC_WIDTH:0] abs_prev_calc;
    wire amp_cross_event;

    assign adc_ext = {adc_data[ADC_WIDTH-1], adc_data};
    assign prev_ext = {prev_sample[ADC_WIDTH-1], prev_sample};
    assign delta_calc = adc_ext - prev_ext;
    assign abs_delta_calc = delta_calc[ADC_WIDTH] ? ((~delta_calc) + 1'b1) : delta_calc;
    assign slope_pos_th = T_SLOPE;
    assign slope_neg_th = -T_SLOPE;
    assign abs_adc_calc = adc_ext[ADC_WIDTH] ? ((~adc_ext) + 1'b1) : adc_ext;
    assign abs_prev_calc = prev_ext[ADC_WIDTH] ? ((~prev_ext) + 1'b1) : prev_ext;
    assign amp_cross_event = ENABLE_AMP_EVENT && (abs_adc_calc > T_AMP_EVENT) && (abs_prev_calc <= T_AMP_EVENT);

    always @(posedge clk) begin
        if (rst) begin
            prev_sample <= {ADC_WIDTH{1'b0}};
            delta <= {(ADC_WIDTH+1){1'b0}};
            abs_delta <= {(ADC_WIDTH+1){1'b0}};
            sample_seen <= 1'b0;
            strong_event <= 1'b0;
            up_event <= 1'b0;
            down_event <= 1'b0;
            slope_valid <= 1'b0;
        end else begin
            strong_event <= 1'b0;
            up_event <= 1'b0;
            down_event <= 1'b0;
            slope_valid <= 1'b0;

            if (sample_valid) begin
                if (!sample_seen) begin
                    prev_sample <= adc_data;
                    delta <= {(ADC_WIDTH+1){1'b0}};
                    abs_delta <= {(ADC_WIDTH+1){1'b0}};
                    sample_seen <= 1'b1;
                end else begin
                    prev_sample <= adc_data;
                    delta <= delta_calc;
                    abs_delta <= abs_delta_calc;
                    strong_event <= (abs_delta_calc > T_EVENT) || amp_cross_event;

                    if (delta_calc > slope_pos_th) begin
                        up_event <= 1'b1;
                        slope_valid <= 1'b1;
                    end else if (delta_calc < slope_neg_th) begin
                        down_event <= 1'b1;
                        slope_valid <= 1'b1;
                    end
                end
            end
        end
    end

endmodule
