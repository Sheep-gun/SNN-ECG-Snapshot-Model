`timescale 1ns / 1ps

module final_membrane_record_chain_synth_top(
    input clk,
    input rst,
    input chunk_clear,
    input record_clear,
    input snapshot_done,
    input chunk_done,
    input pred_valid,
    input [1:0] pred_class,
    input record_done,
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

    final_membrane_layer u_chunk_mem(
        .clk(clk),
        .rst(rst),
        .clear(chunk_clear),
        .snapshot_done(snapshot_done),
        .chunk_done(chunk_done),
        .pred_valid(pred_valid),
        .pred_class(pred_class),
        .class_mem_nsr(64'sd0),
        .class_mem_chf(64'sd0),
        .class_mem_arr(64'sd0),
        .class_mem_aff(64'sd0),
        .beat_count(32'd0),
        .pnn_mismatch_count(32'd0),
        .ectopic_pair_count(32'd0),
        .rdm_ge50_count(32'd0),
        .rdm_ge100_count(32'd0),
        .qrs_maf_count(32'd0),
        .qrs_width_abn_count(32'd0),
        .qrs_energy_abn_count(32'd0),
        .rbbb_delay_like_count(32'd0),
        .rbbb_delay_applied_count(32'd0),
        .pre_qrs_bump_count(32'd0),
        .dscr_flip_count(32'd0),
        .dscr_slope_count(32'd0),
        .abnormal_evidence_count(32'd0),
        .rhythm_irregular_evidence_count(32'd0),
        .morphology_evidence_count(32'd0),
        .pnn_decision_count(32'd0),
        .rdm_valid_count(32'd0),
        .rdm_code_sum(32'd0),
        .ram_code_sum(32'd0),
        .ram_code_count(32'd0),
        .final_valid(chunk_final_valid),
        .final_pred_class(chunk_final_pred_class),
        .final_mem_nsr(chunk_final_mem_nsr),
        .final_mem_chf(chunk_final_mem_chf),
        .final_mem_arr(chunk_final_mem_arr),
        .final_mem_aff(chunk_final_mem_aff)
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
