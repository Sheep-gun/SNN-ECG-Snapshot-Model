`timescale 1ns / 1ps

module snn_ecg_model_a_plus_core #(
    parameter ADC_WIDTH = 12
)(
    input clk,
    input rst,
    input sample_valid,
    input rhythm_tick,
    input segment_start,
    input segment_done,
    input signed [ADC_WIDTH-1:0] adc_data,
    output [1:0] pred_class,
    output pred_valid
);

    snn_ecg_3feat_top #(
        .ADC_WIDTH(ADC_WIDTH),
        .RBBB_QRS_ACTIVITY_MODE(1),
        .RBBB_QRS_WIDE_TH(110),
        .RBBB_QRS_TERMINAL_TH(3),
        .RBBB_QRS_REPEAT_TH(5),
        .RBBB_QRS_HIGH_RDM_SUPPRESS(0),
        .ENABLE_RBBB_QRS_DELAY_GATE(1),
        .W_RBBB_DELAY_NSR_INH(150000),
        .W_RBBB_DELAY_ARR_BOOST(150000),
        .RBBB_DELAY_CHF_OVER_ARR_BLOCK(1)
    ) u_model_a_plus (
        .clk(clk),
        .rst(rst),
        .sample_valid(sample_valid),
        .rhythm_tick(rhythm_tick),
        .segment_start(segment_start),
        .segment_done(segment_done),
        .adc_data(adc_data),
        .pred_class(pred_class),
        .pred_valid(pred_valid)
    );

endmodule
