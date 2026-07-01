`timescale 1ns / 1ps

// SNN-style 30-minute final membrane layer for Snapshot V2.
//
// Structure:
//   60s snapshot pred spike -> pred_count_* membranes
//   60s feature evidence -> auxiliary evidence-neuron membranes
//   comparator gates -> excitatory/inhibitory signed stimuli into class membranes
//   final WTA -> 30-minute chunk class
//
// Candidate frozen as internal engineering baseline:
//   arr_focus_0042452 + margin_evidence_0038974
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

    localparam [1:0] CLS_NSR = 2'd0;
    localparam [1:0] CLS_CHF = 2'd1;
    localparam [1:0] CLS_ARR = 2'd2;
    localparam [1:0] CLS_AFF = 2'd3;

    reg [5:0] pred_count_nsr;
    reg [5:0] pred_count_chf;
    reg [5:0] pred_count_arr;
    reg [5:0] pred_count_aff;

    reg [31:0] sum_pnn_mismatch;
    reg [31:0] sum_ectopic_pair;
    reg [31:0] sum_qrs_maf;
    reg [31:0] sum_rbbb_like;
    reg [31:0] sum_pre_qrs;
    reg [31:0] sum_abnormal;
    reg [31:0] sum_rhythm;
    reg [31:0] sum_morphology;
    reg [31:0] sum_rdm_valid;
    reg [31:0] sum_rdm_code;

    wire [5:0] count_nsr_next = pred_count_nsr + ((pred_valid && (pred_class == CLS_NSR)) ? 6'd1 : 6'd0);
    wire [5:0] count_chf_next = pred_count_chf + ((pred_valid && (pred_class == CLS_CHF)) ? 6'd1 : 6'd0);
    wire [5:0] count_arr_next = pred_count_arr + ((pred_valid && (pred_class == CLS_ARR)) ? 6'd1 : 6'd0);
    wire [5:0] count_aff_next = pred_count_aff + ((pred_valid && (pred_class == CLS_AFF)) ? 6'd1 : 6'd0);

    wire [31:0] pnn_mismatch_next = sum_pnn_mismatch + pnn_mismatch_count;
    wire [31:0] ectopic_pair_next = sum_ectopic_pair + ectopic_pair_count;
    wire [31:0] qrs_maf_next = sum_qrs_maf + qrs_maf_count;
    wire [31:0] rbbb_like_next = sum_rbbb_like + rbbb_delay_like_count;
    wire [31:0] pre_qrs_next = sum_pre_qrs + pre_qrs_bump_count;
    wire [31:0] abnormal_next = sum_abnormal + abnormal_evidence_count;
    wire [31:0] rhythm_next = sum_rhythm + rhythm_irregular_evidence_count;
    wire [31:0] morphology_next = sum_morphology + morphology_evidence_count;
    wire [31:0] rdm_valid_next = sum_rdm_valid + rdm_valid_count;
    wire [31:0] rdm_code_next = sum_rdm_code + rdm_code_sum;
    wire [35:0] rdm_valid_next_ext = {4'd0, rdm_valid_next};
    wire [35:0] rdm_code_next_ext = {4'd0, rdm_code_next};
    wire [35:0] rdm_valid_times10 = (rdm_valid_next_ext << 3) + (rdm_valid_next_ext << 1);

    function [1:0] argmax_count4;
        input [5:0] a;
        input [5:0] b;
        input [5:0] c;
        input [5:0] d;
        reg [5:0] best;
        begin
            argmax_count4 = CLS_NSR;
            best = a;
            if (b > best) begin best = b; argmax_count4 = CLS_CHF; end
            if (c > best) begin best = c; argmax_count4 = CLS_ARR; end
            if (d > best) begin best = d; argmax_count4 = CLS_AFF; end
        end
    endfunction

    function [1:0] argmax_score4;
        input signed [31:0] a;
        input signed [31:0] b;
        input signed [31:0] c;
        input signed [31:0] d;
        reg signed [31:0] best;
        begin
            argmax_score4 = CLS_NSR;
            best = a;
            if (b > best) begin best = b; argmax_score4 = CLS_CHF; end
            if (c > best) begin best = c; argmax_score4 = CLS_ARR; end
            if (d > best) begin best = d; argmax_score4 = CLS_AFF; end
        end
    endfunction

    function signed [31:0] margin_score4;
        input signed [31:0] a;
        input signed [31:0] b;
        input signed [31:0] c;
        input signed [31:0] d;
        reg signed [31:0] best;
        reg signed [31:0] second;
        begin
            best = a;
            second = -32'sd2147483647;
            if (b > best) begin second = best; best = b; end else if (b > second) begin second = b; end
            if (c > best) begin second = best; best = c; end else if (c > second) begin second = c; end
            if (d > best) begin second = best; best = d; end else if (d > second) begin second = d; end
            margin_score4 = best - second;
        end
    endfunction

    reg [1:0] base_pred;
    reg [1:0] local_pred;
    reg [1:0] arr_focus_pred;
    reg [1:0] final_pred_calc;

    reg signed [31:0] local_nsr;
    reg signed [31:0] local_chf;
    reg signed [31:0] local_arr;
    reg signed [31:0] local_aff;
    reg signed [31:0] post_nsr;
    reg signed [31:0] post_chf;
    reg signed [31:0] post_arr;
    reg signed [31:0] post_aff;
    reg signed [31:0] calc_nsr;
    reg signed [31:0] calc_chf;
    reg signed [31:0] calc_arr;
    reg signed [31:0] calc_aff;

    reg signed [31:0] nsr_arr_margin;
    reg signed [31:0] chf_aff_margin;
    reg signed [31:0] arr_aff_margin;
    reg signed [31:0] arr_focus_margin;

    reg aff_low_rescue;
    reg nsr_from_chf_rescue;
    reg chf_from_aff_rescue;
    reg strong_chf;
    reg arr_rescue;
    reg arr_over_aff;
    reg aff_rescue;
    reg arr_low_rescue;
    reg arr_silent_rescue;
    reg arr_from_nsr;
    reg arr_from_chf;
    reg arr_from_aff;
    reg margin_evidence_rescue;

    always @(*) begin
        base_pred = argmax_count4(count_nsr_next, count_chf_next, count_arr_next, count_aff_next);
        nsr_arr_margin = $signed({26'd0, count_nsr_next}) - $signed({26'd0, count_arr_next});
        chf_aff_margin = $signed({26'd0, count_chf_next}) - $signed({26'd0, count_aff_next});
        arr_aff_margin = $signed({26'd0, count_arr_next}) - $signed({26'd0, count_aff_next});

        local_nsr = $signed({26'd0, count_nsr_next}) + 32'sd2;
        local_chf = $signed({26'd0, count_chf_next});
        local_arr = $signed({26'd0, count_arr_next});
        local_aff = $signed({26'd0, count_aff_next});

        aff_low_rescue = (base_pred == CLS_CHF) &&
                         (abnormal_next <= 32'd50) &&
                         (morphology_next <= 32'd20) &&
                         (rbbb_like_next <= 32'd0) &&
                         (((rdm_valid_next > 32'd0) && (rdm_code_next_ext >= rdm_valid_times10)) ||
                          ((rdm_valid_next == 32'd0) && (rdm_code_next == 32'd0) &&
                           (rhythm_next <= 32'd256) && (qrs_maf_next <= 32'd8) && (pre_qrs_next <= 32'd8))) &&
                         (count_chf_next >= 6'd18);
        if (aff_low_rescue) begin
            local_aff = local_aff + 32'sd60;
            local_chf = local_chf - 32'sd20;
        end

        nsr_from_chf_rescue = (base_pred == CLS_CHF) &&
                              (count_nsr_next >= 6'd3) &&
                              (abnormal_next <= 32'd150) &&
                              (qrs_maf_next <= 32'd64) &&
                              (rbbb_like_next <= 32'd1) &&
                              (morphology_next <= 32'd1500);
        if (nsr_from_chf_rescue) begin
            local_nsr = local_nsr + 32'sd10;
            local_chf = local_chf - 32'sd30;
        end

        chf_from_aff_rescue = (base_pred == CLS_AFF) &&
                              (count_chf_next >= 6'd5) &&
                              (morphology_next <= 32'd100) &&
                              (qrs_maf_next <= 32'd32) &&
                              (rbbb_like_next <= 32'd2);
        if (chf_from_aff_rescue) begin
            local_chf = local_chf + 32'sd20;
            local_aff = local_aff - 32'sd10;
        end

        strong_chf = (base_pred == CLS_CHF) &&
                     ((count_chf_next >= 6'd30) || (chf_aff_margin >= 32'sd24));

        arr_rescue = ((base_pred == CLS_NSR) || (base_pred == CLS_CHF) || (base_pred == CLS_AFF)) &&
                     (count_arr_next >= 6'd12) &&
                     (count_aff_next <= 6'd10) &&
                     (nsr_arr_margin <= 32'sd24) &&
                     (morphology_next >= 32'd180) &&
                     (qrs_maf_next >= 32'd40) &&
                     (rbbb_like_next >= 32'd8) &&
                     (pre_qrs_next >= 32'd1800);
        if (arr_rescue) begin
            local_arr = local_arr + 32'sd50;
            local_nsr = local_nsr - 32'sd30;
            local_chf = local_chf - 32'sd10;
            local_aff = local_aff - 32'sd5;
        end

        arr_over_aff = (base_pred == CLS_AFF) &&
                       (count_arr_next >= 6'd8) &&
                       (qrs_maf_next >= 32'd1000) &&
                       (morphology_next >= 32'd1500);
        if (arr_over_aff) begin
            local_arr = local_arr + 32'sd20;
            local_aff = local_aff - 32'sd10;
        end

        aff_rescue = ((base_pred == CLS_CHF) || (base_pred == CLS_ARR)) &&
                     !strong_chf &&
                     (count_arr_next < 6'd15) &&
                     (count_aff_next >= 6'd6) &&
                     (chf_aff_margin <= 32'sd14) &&
                     (rhythm_next >= 32'd1800) &&
                     (ectopic_pair_next <= 32'd100);
        if (aff_rescue) begin
            local_aff = local_aff + 32'sd25;
            local_chf = local_chf - 32'sd15;
        end

        if (strong_chf) begin
            local_aff = local_aff - 32'sd4;
        end

        arr_low_rescue = ((base_pred == CLS_NSR) || (base_pred == CLS_CHF) || (base_pred == CLS_AFF)) &&
                         (count_arr_next >= 6'd4) &&
                         (count_aff_next <= 6'd3) &&
                         (pre_qrs_next >= 32'd3000) &&
                         (qrs_maf_next >= 32'd40) &&
                         (rbbb_like_next >= 32'd8) &&
                         (morphology_next >= 32'd350);
        if (arr_low_rescue) begin
            local_arr = local_arr + 32'sd30;
            local_chf = local_chf - 32'sd10;
            local_aff = local_aff - 32'sd10;
        end

        arr_silent_rescue = (base_pred == CLS_NSR) &&
                            (count_nsr_next >= 6'd18) &&
                            (count_arr_next <= 6'd5) &&
                            (abnormal_next >= 32'd100) &&
                            (abnormal_next <= 32'd350) &&
                            (morphology_next >= 32'd1500) &&
                            (morphology_next <= 32'd6500) &&
                            (qrs_maf_next <= 32'd20) &&
                            (rbbb_like_next <= 32'd2) &&
                            (pnn_mismatch_next >= 32'd32) &&
                            (ectopic_pair_next >= 32'd8) &&
                            (rdm_code_next >= 32'd1500) &&
                            (rdm_code_next <= 32'd7000);
        if (arr_silent_rescue) begin
            local_arr = local_arr + 32'sd30;
            local_nsr = local_nsr - 32'sd50;
        end

        local_pred = argmax_score4(local_nsr, local_chf, local_arr, local_aff);
        post_nsr = local_nsr;
        post_chf = local_chf;
        post_arr = local_arr;
        post_aff = local_aff;

        arr_from_nsr = (local_pred == CLS_NSR) &&
                       (count_nsr_next >= 6'd18) &&
                       (count_arr_next >= 6'd4) &&
                       (count_aff_next <= 6'd10) &&
                       ((count_nsr_next - count_arr_next) <= 6'd30) &&
                       (morphology_next >= 32'd5500) &&
                       (rdm_code_next >= 32'd6500) &&
                       (pnn_mismatch_next >= 32'd64) &&
                       (ectopic_pair_next >= 32'd50) &&
                       (qrs_maf_next <= 32'd256) &&
                       (rbbb_like_next <= 32'd32);
        if (arr_from_nsr) begin
            post_arr = post_arr + 32'sd16;
            post_nsr = post_nsr - 32'sd12;
            post_aff = post_aff - 32'sd4;
        end

        arr_from_chf = (local_pred == CLS_CHF) &&
                       (count_arr_next >= 6'd9) &&
                       (($signed({26'd0, count_chf_next}) - $signed({26'd0, count_arr_next})) <= 32'sd15) &&
                       (morphology_next >= 32'd650) &&
                       (qrs_maf_next >= 32'd64) &&
                       (rbbb_like_next >= 32'd12) &&
                       (rdm_code_next >= 32'd9500) &&
                       (ectopic_pair_next >= 32'd64);
        if (arr_from_chf) begin
            post_arr = post_arr + 32'sd32;
            post_chf = post_chf - 32'sd20;
        end

        arr_from_aff = (local_pred == CLS_AFF) &&
                       (count_arr_next >= 6'd5) &&
                       (($signed({26'd0, count_aff_next}) - $signed({26'd0, count_arr_next})) <= 32'sd20) &&
                       (morphology_next >= 32'd1000) &&
                       (rdm_code_next >= 32'd20000) &&
                       (pnn_mismatch_next >= 32'd256) &&
                       (ectopic_pair_next >= 32'd64) &&
                       (qrs_maf_next <= 32'd512) &&
                       (rbbb_like_next <= 32'd10);
        if (arr_from_aff) begin
            post_arr = post_arr + 32'sd24;
            post_aff = post_aff - 32'sd8;
        end

        arr_focus_pred = argmax_score4(post_nsr, post_chf, post_arr, post_aff);
        arr_focus_margin = margin_score4(post_nsr, post_chf, post_arr, post_aff);
        calc_nsr = post_nsr;
        calc_chf = post_chf;
        calc_arr = post_arr;
        calc_aff = post_aff;

        margin_evidence_rescue = (arr_focus_pred == CLS_AFF) &&
                                 (arr_focus_margin <= 32'sd12) &&
                                 (count_arr_next >= 6'd3) &&
                                 (rdm_code_next >= 32'd512) &&
                                 (pnn_mismatch_next >= 32'd800) &&
                                 (ectopic_pair_next >= 32'd256) &&
                                 (abnormal_next >= 32'd256);
        if (margin_evidence_rescue) begin
            calc_arr = calc_arr + 32'sd4;
            calc_aff = calc_aff - 32'sd16;
        end

        final_pred_calc = argmax_score4(calc_nsr, calc_chf, calc_arr, calc_aff);
    end

    always @(posedge clk) begin
        if (rst || clear) begin
            pred_count_nsr <= 6'd0;
            pred_count_chf <= 6'd0;
            pred_count_arr <= 6'd0;
            pred_count_aff <= 6'd0;
            sum_pnn_mismatch <= 32'd0;
            sum_ectopic_pair <= 32'd0;
            sum_qrs_maf <= 32'd0;
            sum_rbbb_like <= 32'd0;
            sum_pre_qrs <= 32'd0;
            sum_abnormal <= 32'd0;
            sum_rhythm <= 32'd0;
            sum_morphology <= 32'd0;
            sum_rdm_valid <= 32'd0;
            sum_rdm_code <= 32'd0;
            final_valid <= 1'b0;
            final_pred_class <= CLS_NSR;
            final_mem_nsr <= 32'sd0;
            final_mem_chf <= 32'sd0;
            final_mem_arr <= 32'sd0;
            final_mem_aff <= 32'sd0;
        end else begin
            final_valid <= 1'b0;
            if (snapshot_done) begin
                pred_count_nsr <= count_nsr_next;
                pred_count_chf <= count_chf_next;
                pred_count_arr <= count_arr_next;
                pred_count_aff <= count_aff_next;
                sum_pnn_mismatch <= pnn_mismatch_next;
                sum_ectopic_pair <= ectopic_pair_next;
                sum_qrs_maf <= qrs_maf_next;
                sum_rbbb_like <= rbbb_like_next;
                sum_pre_qrs <= pre_qrs_next;
                sum_abnormal <= abnormal_next;
                sum_rhythm <= rhythm_next;
                sum_morphology <= morphology_next;
                sum_rdm_valid <= rdm_valid_next;
                sum_rdm_code <= rdm_code_next;
                final_mem_nsr <= calc_nsr;
                final_mem_chf <= calc_chf;
                final_mem_arr <= calc_arr;
                final_mem_aff <= calc_aff;
                final_pred_class <= final_pred_calc;
                if (chunk_done)
                    final_valid <= 1'b1;
            end
        end
    end

endmodule
