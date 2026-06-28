`timescale 1ns / 1ps

// 30-minute chunk snapshot vote counter.
//
// SNN-style structure:
//   snapshot pred spike -> per-class chunk vote membrane
//   chunk_done -> WTA chunk majority
//
// The record-level selected final layer is implemented in
// record_level_final_membrane_layer.v. This module intentionally exposes raw
// 30-snapshot vote membranes so the record-level layer can accumulate them
// across all 30-minute chunks belonging to the same record.
module final_membrane_layer(
    input clk,
    input rst,
    input clear,
    input snapshot_done,
    input chunk_done,
    input pred_valid,
    input [1:0] pred_class,
    input signed [63:0] class_mem_nsr,
    input signed [63:0] class_mem_chf,
    input signed [63:0] class_mem_arr,
    input signed [63:0] class_mem_aff,
    input [31:0] beat_count,
    input [31:0] pnn_mismatch_count,
    input [31:0] ectopic_pair_count,
    input [31:0] rdm_ge50_count,
    input [31:0] rdm_ge100_count,
    input [31:0] qrs_maf_count,
    input [31:0] qrs_width_abn_count,
    input [31:0] qrs_energy_abn_count,
    input [31:0] rbbb_delay_like_count,
    input [31:0] rbbb_delay_applied_count,
    input [31:0] pre_qrs_bump_count,
    input [31:0] dscr_flip_count,
    input [31:0] dscr_slope_count,
    input [31:0] abnormal_evidence_count,
    input [31:0] rhythm_irregular_evidence_count,
    input [31:0] morphology_evidence_count,
    input [31:0] pnn_decision_count,
    input [31:0] rdm_valid_count,
    input [31:0] rdm_code_sum,
    input [31:0] ram_code_sum,
    input [31:0] ram_code_count,
    output reg final_valid,
    output reg [1:0] final_pred_class,
    output reg signed [31:0] final_mem_nsr,
    output reg signed [31:0] final_mem_chf,
    output reg signed [31:0] final_mem_arr,
    output reg signed [31:0] final_mem_aff
);

    reg [5:0] pred_count_nsr;
    reg [5:0] pred_count_chf;
    reg [5:0] pred_count_arr;
    reg [5:0] pred_count_aff;

    reg [5:0] nsr_next;
    reg [5:0] chf_next;
    reg [5:0] arr_next;
    reg [5:0] aff_next;

    reg signed [31:0] score_nsr;
    reg signed [31:0] score_chf;
    reg signed [31:0] score_arr;
    reg signed [31:0] score_aff;
    reg signed [31:0] best_score;
    reg [1:0] best_class;

    always @(*) begin
        nsr_next = pred_count_nsr + ((pred_valid && (pred_class == 2'd0)) ? 6'd1 : 6'd0);
        chf_next = pred_count_chf + ((pred_valid && (pred_class == 2'd1)) ? 6'd1 : 6'd0);
        arr_next = pred_count_arr + ((pred_valid && (pred_class == 2'd2)) ? 6'd1 : 6'd0);
        aff_next = pred_count_aff + ((pred_valid && (pred_class == 2'd3)) ? 6'd1 : 6'd0);

        score_nsr = {{26{1'b0}}, nsr_next};
        score_chf = {{26{1'b0}}, chf_next};
        score_arr = {{26{1'b0}}, arr_next};
        score_aff = {{26{1'b0}}, aff_next};

        best_class = 2'd0;
        best_score = score_nsr;
        if (score_chf > best_score) begin
            best_score = score_chf;
            best_class = 2'd1;
        end
        if (score_arr > best_score) begin
            best_score = score_arr;
            best_class = 2'd2;
        end
        if (score_aff > best_score) begin
            best_score = score_aff;
            best_class = 2'd3;
        end
    end

    always @(posedge clk) begin
        if (rst || clear) begin
            pred_count_nsr <= 6'd0;
            pred_count_chf <= 6'd0;
            pred_count_arr <= 6'd0;
            pred_count_aff <= 6'd0;
            final_valid <= 1'b0;
            final_pred_class <= 2'd0;
            final_mem_nsr <= 32'sd0;
            final_mem_chf <= 32'sd0;
            final_mem_arr <= 32'sd0;
            final_mem_aff <= 32'sd0;
        end else begin
            final_valid <= 1'b0;
            if (snapshot_done) begin
                pred_count_nsr <= nsr_next;
                pred_count_chf <= chf_next;
                pred_count_arr <= arr_next;
                pred_count_aff <= aff_next;
                final_mem_nsr <= score_nsr;
                final_mem_chf <= score_chf;
                final_mem_arr <= score_arr;
                final_mem_aff <= score_aff;
                if (chunk_done) begin
                    final_valid <= 1'b1;
                    final_pred_class <= best_class;
                end
            end
        end
    end

endmodule
