`timescale 1ns / 1ps

module snn_ecg_30min_record_final_synth_top(
    input clk,
    input rst,
    input record_clear,
    input record_done,
    input start,
    input sample_valid,
    input signed [11:0] adc_data,
    output sample_ready,
    output busy,
    output record_final_valid,
    output [1:0] record_final_pred_class,
    output signed [31:0] record_final_mem_nsr,
    output signed [31:0] record_final_mem_chf,
    output signed [31:0] record_final_mem_arr,
    output signed [31:0] record_final_mem_aff
);
    wire chunk_final_valid;
    wire [1:0] chunk_final_pred_class;
    wire signed [31:0] chunk_final_mem_nsr;
    wire signed [31:0] chunk_final_mem_chf;
    wire signed [31:0] chunk_final_mem_arr;
    wire signed [31:0] chunk_final_mem_aff;
    wire [5:0] snapshot_index_dbg;

    snn_ecg_30min_final_top u_chunk_top(
        .clk(clk),
        .rst(rst),
        .start(start),
        .sample_valid(sample_valid),
        .adc_data(adc_data),
        .sample_ready(sample_ready),
        .busy(busy),
        .final_valid(chunk_final_valid),
        .final_pred_class(chunk_final_pred_class),
        .final_mem_nsr(chunk_final_mem_nsr),
        .final_mem_chf(chunk_final_mem_chf),
        .final_mem_arr(chunk_final_mem_arr),
        .final_mem_aff(chunk_final_mem_aff),
        .snapshot_index_dbg(snapshot_index_dbg)
    );

    record_level_final_membrane_layer u_record_mem(
        .clk(clk),
        .rst(rst),
        .clear(record_clear),
        .chunk_done(chunk_final_valid),
        .record_done(record_done),
        .chunk_count_nsr(chunk_final_mem_nsr[5:0]),
        .chunk_count_chf(chunk_final_mem_chf[5:0]),
        .chunk_count_arr(chunk_final_mem_arr[5:0]),
        .chunk_count_aff(chunk_final_mem_aff[5:0]),
        .final_valid(record_final_valid),
        .final_pred_class(record_final_pred_class),
        .final_mem_nsr(record_final_mem_nsr),
        .final_mem_chf(record_final_mem_chf),
        .final_mem_arr(record_final_mem_arr),
        .final_mem_aff(record_final_mem_aff)
    );
endmodule
