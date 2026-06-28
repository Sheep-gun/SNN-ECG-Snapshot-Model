`timescale 1ns / 1ps

module tb_final_membrane_layer_dataset;
    reg clk;
    reg rst;
    reg clear;
    reg snapshot_done;
    reg chunk_done;
    reg pred_valid;
    reg [1:0] pred_class;
    reg signed [63:0] class_mem_nsr;
    reg signed [63:0] class_mem_chf;
    reg signed [63:0] class_mem_arr;
    reg signed [63:0] class_mem_aff;
    reg [31:0] beat_count;
    reg [31:0] pnn_mismatch_count;
    reg [31:0] ectopic_pair_count;
    reg [31:0] rdm_ge50_count;
    reg [31:0] rdm_ge100_count;
    reg [31:0] qrs_maf_count;
    reg [31:0] qrs_width_abn_count;
    reg [31:0] qrs_energy_abn_count;
    reg [31:0] rbbb_delay_like_count;
    reg [31:0] rbbb_delay_applied_count;
    reg [31:0] pre_qrs_bump_count;
    reg [31:0] dscr_flip_count;
    reg [31:0] dscr_slope_count;
    reg [31:0] abnormal_evidence_count;
    reg [31:0] rhythm_irregular_evidence_count;
    reg [31:0] morphology_evidence_count;
    reg [31:0] pnn_decision_count;
    reg [31:0] rdm_valid_count;
    reg [31:0] rdm_code_sum;
    reg [31:0] ram_code_sum;
    reg [31:0] ram_code_count;

    wire final_valid;
    wire [1:0] final_pred_class;
    wire signed [31:0] final_mem_nsr;
    wire signed [31:0] final_mem_chf;
    wire signed [31:0] final_mem_arr;
    wire signed [31:0] final_mem_aff;

    integer case_id_i;
    integer expected_i;
    integer snapshot_id_i;
    integer pred_valid_i;
    integer pred_class_i;
    integer cm_nsr_i;
    integer cm_chf_i;
    integer cm_arr_i;
    integer cm_aff_i;
    integer beat_count_i;
    integer pnn_mismatch_count_i;
    integer ectopic_pair_count_i;
    integer rdm_ge50_count_i;
    integer rdm_ge100_count_i;
    integer qrs_maf_count_i;
    integer qrs_width_abn_count_i;
    integer qrs_energy_abn_count_i;
    integer rbbb_delay_like_count_i;
    integer rbbb_delay_applied_count_i;
    integer pre_qrs_bump_count_i;
    integer dscr_flip_count_i;
    integer dscr_slope_count_i;
    integer abnormal_evidence_count_i;
    integer rhythm_irregular_evidence_count_i;
    integer morphology_evidence_count_i;
    integer pnn_decision_count_i;
    integer rdm_valid_count_i;
    integer rdm_code_sum_i;
    integer ram_code_sum_i;
    integer ram_code_count_i;
    integer fd;
    integer out_fd;
    integer scan_count;
    integer total;
    integer correct;

    final_membrane_layer dut(
        .clk(clk),
        .rst(rst),
        .clear(clear),
        .snapshot_done(snapshot_done),
        .chunk_done(chunk_done),
        .pred_valid(pred_valid),
        .pred_class(pred_class),
        .class_mem_nsr(class_mem_nsr),
        .class_mem_chf(class_mem_chf),
        .class_mem_arr(class_mem_arr),
        .class_mem_aff(class_mem_aff),
        .beat_count(beat_count),
        .pnn_mismatch_count(pnn_mismatch_count),
        .ectopic_pair_count(ectopic_pair_count),
        .rdm_ge50_count(rdm_ge50_count),
        .rdm_ge100_count(rdm_ge100_count),
        .qrs_maf_count(qrs_maf_count),
        .qrs_width_abn_count(qrs_width_abn_count),
        .qrs_energy_abn_count(qrs_energy_abn_count),
        .rbbb_delay_like_count(rbbb_delay_like_count),
        .rbbb_delay_applied_count(rbbb_delay_applied_count),
        .pre_qrs_bump_count(pre_qrs_bump_count),
        .dscr_flip_count(dscr_flip_count),
        .dscr_slope_count(dscr_slope_count),
        .abnormal_evidence_count(abnormal_evidence_count),
        .rhythm_irregular_evidence_count(rhythm_irregular_evidence_count),
        .morphology_evidence_count(morphology_evidence_count),
        .pnn_decision_count(pnn_decision_count),
        .rdm_valid_count(rdm_valid_count),
        .rdm_code_sum(rdm_code_sum),
        .ram_code_sum(ram_code_sum),
        .ram_code_count(ram_code_count),
        .final_valid(final_valid),
        .final_pred_class(final_pred_class),
        .final_mem_nsr(final_mem_nsr),
        .final_mem_chf(final_mem_chf),
        .final_mem_arr(final_mem_arr),
        .final_mem_aff(final_mem_aff)
    );

    always #5 clk = ~clk;

    task clear_chunk;
        begin
            @(negedge clk);
            clear = 1'b1;
            snapshot_done = 1'b0;
            chunk_done = 1'b0;
            @(posedge clk);
            #1;
            clear = 1'b0;
        end
    endtask

    task run_split;
        input [8*512-1:0] input_path;
        input [8*512-1:0] output_path;
        begin
            fd = $fopen(input_path, "r");
            if (fd == 0) begin $display("FAIL open input %0s", input_path); $finish; end
            out_fd = $fopen(output_path, "w");
            if (out_fd == 0) begin $display("FAIL open output %0s", output_path); $finish; end
            $fdisplay(out_fd, "case_id,expected_class,final_pred_class,correct,final_mem_NSR,final_mem_CHF,final_mem_ARR,final_mem_AFF");
            total = 0;
            correct = 0;
            while (!$feof(fd)) begin
                scan_count = $fscanf(
                    fd,
                    "%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d\n",
                    case_id_i,
                    expected_i,
                    snapshot_id_i,
                    pred_valid_i,
                    pred_class_i,
                    cm_nsr_i,
                    cm_chf_i,
                    cm_arr_i,
                    cm_aff_i,
                    beat_count_i,
                    pnn_mismatch_count_i,
                    ectopic_pair_count_i,
                    rdm_ge50_count_i,
                    rdm_ge100_count_i,
                    qrs_maf_count_i,
                    qrs_width_abn_count_i,
                    qrs_energy_abn_count_i,
                    rbbb_delay_like_count_i,
                    rbbb_delay_applied_count_i,
                    pre_qrs_bump_count_i,
                    dscr_flip_count_i,
                    dscr_slope_count_i,
                    abnormal_evidence_count_i,
                    rhythm_irregular_evidence_count_i,
                    morphology_evidence_count_i,
                    pnn_decision_count_i,
                    rdm_valid_count_i,
                    rdm_code_sum_i,
                    ram_code_sum_i,
                    ram_code_count_i
                );
                if (scan_count == 30) begin
                    if (snapshot_id_i == 0) begin
                        clear_chunk();
                    end

                    pred_valid = pred_valid_i != 0;
                    pred_class = pred_class_i[1:0];
                    class_mem_nsr = cm_nsr_i;
                    class_mem_chf = cm_chf_i;
                    class_mem_arr = cm_arr_i;
                    class_mem_aff = cm_aff_i;
                    beat_count = beat_count_i[31:0];
                    pnn_mismatch_count = pnn_mismatch_count_i[31:0];
                    ectopic_pair_count = ectopic_pair_count_i[31:0];
                    rdm_ge50_count = rdm_ge50_count_i[31:0];
                    rdm_ge100_count = rdm_ge100_count_i[31:0];
                    qrs_maf_count = qrs_maf_count_i[31:0];
                    qrs_width_abn_count = qrs_width_abn_count_i[31:0];
                    qrs_energy_abn_count = qrs_energy_abn_count_i[31:0];
                    rbbb_delay_like_count = rbbb_delay_like_count_i[31:0];
                    rbbb_delay_applied_count = rbbb_delay_applied_count_i[31:0];
                    pre_qrs_bump_count = pre_qrs_bump_count_i[31:0];
                    dscr_flip_count = dscr_flip_count_i[31:0];
                    dscr_slope_count = dscr_slope_count_i[31:0];
                    abnormal_evidence_count = abnormal_evidence_count_i[31:0];
                    rhythm_irregular_evidence_count = rhythm_irregular_evidence_count_i[31:0];
                    morphology_evidence_count = morphology_evidence_count_i[31:0];
                    pnn_decision_count = pnn_decision_count_i[31:0];
                    rdm_valid_count = rdm_valid_count_i[31:0];
                    rdm_code_sum = rdm_code_sum_i[31:0];
                    ram_code_sum = ram_code_sum_i[31:0];
                    ram_code_count = ram_code_count_i[31:0];

                    @(negedge clk);
                    snapshot_done = 1'b1;
                    chunk_done = (snapshot_id_i == 29);
                    @(posedge clk);
                    #1;
                    snapshot_done = 1'b0;
                    chunk_done = 1'b0;

                    if (snapshot_id_i == 29) begin
                        total = total + 1;
                        if (final_valid && (final_pred_class == expected_i[1:0])) correct = correct + 1;
                        $fdisplay(out_fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                                  case_id_i,
                                  expected_i,
                                  final_pred_class,
                                  final_valid && (final_pred_class == expected_i[1:0]),
                                  final_mem_nsr,
                                  final_mem_chf,
                                  final_mem_arr,
                                  final_mem_aff);
                    end
                end
            end
            $display("SPLIT_RESULT %0s correct/total=%0d/%0d", input_path, correct, total);
            $fclose(fd);
            $fclose(out_fd);
        end
    endtask

    initial begin
        clk = 1'b0;
        rst = 1'b1;
        clear = 1'b0;
        snapshot_done = 1'b0;
        chunk_done = 1'b0;
        pred_valid = 1'b0;
        pred_class = 2'd0;
        class_mem_nsr = 64'sd0;
        class_mem_chf = 64'sd0;
        class_mem_arr = 64'sd0;
        class_mem_aff = 64'sd0;
        beat_count = 32'd0;
        pnn_mismatch_count = 32'd0;
        ectopic_pair_count = 32'd0;
        rdm_ge50_count = 32'd0;
        rdm_ge100_count = 32'd0;
        qrs_maf_count = 32'd0;
        qrs_width_abn_count = 32'd0;
        qrs_energy_abn_count = 32'd0;
        rbbb_delay_like_count = 32'd0;
        rbbb_delay_applied_count = 32'd0;
        pre_qrs_bump_count = 32'd0;
        dscr_flip_count = 32'd0;
        dscr_slope_count = 32'd0;
        abnormal_evidence_count = 32'd0;
        rhythm_irregular_evidence_count = 32'd0;
        morphology_evidence_count = 32'd0;
        pnn_decision_count = 32'd0;
        rdm_valid_count = 32'd0;
        rdm_code_sum = 32'd0;
        ram_code_sum = 32'd0;
        ram_code_count = 32'd0;
        repeat (4) @(posedge clk);
        rst = 1'b0;

        run_split("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/final_membrane_30min/rtl_replay_input_train.txt", "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/final_membrane_30min/rtl_replay_train_predictions.csv");
        run_split("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/final_membrane_30min/rtl_replay_input_val.txt", "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/final_membrane_30min/rtl_replay_val_predictions.csv");
        run_split("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/final_membrane_30min/rtl_replay_input_test.txt", "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/final_membrane_30min/rtl_replay_test_predictions.csv");
        $display("PASS tb_final_membrane_layer_dataset completed");
        $finish;
    end
endmodule
