`timescale 1ns / 1ps

module tb_snn_ecg_3feat_dataset;
    parameter MAX_SAMPLES = 60000;
    parameter MANIFEST_FILE = "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/person_data_record_split_strict_varlen/test/dataset_manifest_test_varlen.txt";
    parameter WRITE_CASE_CSV = 1;
    parameter RESULT_CSV = "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/generic/rtl_dataset_case_results.csv";
    parameter WRITE_SUBWINDOW_CSV = 0;
    parameter SUBWINDOW_CSV = "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/generic/rtl_dataset_subwindow_features.csv";
    parameter MANIFEST_HAS_SAMPLE_COUNT = 0;

    reg clk;
    reg rst;
    reg sample_valid;
    reg rhythm_tick;
    reg segment_start;
    reg segment_done;
    reg signed [11:0] adc_data;
    reg [11:0] sample_mem [0:MAX_SAMPLES-1];

    integer i;
    integer manifest_fd;
    integer result_fd;
    integer subwindow_fd;
    integer scan_count;
    integer case_sample_count;
    integer expected_class;
    integer total_cases;
    integer correct_cases;
    integer pred_valid_cases;
    integer errors;
    integer beat_count;
    integer pnn_match_count;
    integer pnn_mismatch_count;
    integer dscr_flip_count;
    integer dscr_slope_count;
    integer ram_code_sum;
    integer ram_code_count;
    integer rdm_valid_count;
    integer rdm_code_sum;
    integer ectopic_pair_count;
    integer rr_alt_count;
    integer amp_jump_count;
    integer width_jump_count;
    integer qrs_maf_valid_count;
    integer qrs_maf_count;
    integer qrs_maf_code_sum;
    integer qrs_width_abn_count;
    integer qrs_complex_abn_count;
    integer qrs_energy_abn_count;
    integer pre_qrs_bump_count;
    integer qrs_terminal_delay_count;
    integer qrs_late_energy_count;
    integer qrs_asymmetry_count;
    integer qrs_peak_to_tail_count;
    integer qrs_pvc_like_count;
    integer qrs_rbbb_like_count;
    integer qrs_maf_width_sum;
    integer qrs_maf_complex_sum;
    integer qrs_maf_energy_sum;
    integer qrs_maf_late_event_sum;
    integer qrs_maf_late_energy_sum;
    integer qrs_maf_asymmetry_sum;
    integer qrs_maf_peak_tail_sum;
    integer qrs_template_mismatch_count;
    integer qrs_template_strong_count;
    integer qrs_template_width_count;
    integer qrs_template_energy_count;
    integer qrs_template_tail_count;
    integer qrs_template_score_sum;
    integer qrs_template_ready_count;
    integer abnormal_beat_valid_count;
    integer abnormal_beat_count;
    integer abnormal_beat_mid_count;
    integer abnormal_beat_high_count;
    integer abnormal_beat_strong_count;
    integer abnormal_beat_score_sum;
    integer rbbb_delay_valid_count;
    integer rbbb_delay_wide_count;
    integer rbbb_delay_terminal_count;
    integer rbbb_delay_like_count;
    integer rbbb_delay_segment_count;
    integer rbbb_delay_applied_count;
    integer eerg_gate_count;
    integer eerg_applied_count;
    integer rdm_ge_count [0:14];
    integer rdm_i;
    integer feature_i;
    integer subwindow_id;
    integer class_total [0:3];
    integer class_correct [0:3];
    integer acc_bp;
    reg [8*16-1:0] label_name;
    reg [8*512-1:0] mem_file;

    wire strong_event;
    wire up_event;
    wire down_event;
    wire slope_valid;
    wire beat_spike;
    wire [11:0] token_age;
    wire [11:0] rr_interval;
    wire [5:0] winner_id;
    wire [5:0] predictor_id;
    wire pnn_match_spike;
    wire pnn_mismatch_spike;
    wire dscr_valid_slope_spike;
    wire dscr_sign_flip_spike;
    wire ram_amp_spike;
    wire [5:0] ram_amp_code;
    wire rdm_valid_spike;
    wire [14:0] rdm_level_spike;
    wire [3:0] rdm_level_code;
    wire [11:0] rdm_rr_diff;
    wire ectopic_early_spike;
    wire ectopic_late_spike;
    wire ectopic_pair_spike;
    wire [11:0] ectopic_rr_ref;
    wire rr_alt_spike;
    wire rr_diff_large_spike;
    wire ram_amp_jump_spike;
    wire qrs_width_jump_spike;
    wire [7:0] qrs_width_span;
    wire qrs_maf_valid_spike;
    wire qrs_maf_spike;
    wire qrs_width_abn_spike;
    wire qrs_complex_abn_spike;
    wire qrs_energy_abn_spike;
    wire pre_qrs_bump_spike;
    wire qrs_terminal_delay_spike;
    wire qrs_late_energy_spike;
    wire qrs_asymmetry_spike;
    wire qrs_peak_to_tail_spike;
    wire qrs_pvc_like_spike;
    wire qrs_rbbb_like_spike;
    wire [7:0] qrs_maf_width_value;
    wire [5:0] qrs_maf_complex_count;
    wire [5:0] qrs_maf_energy_code;
    wire [5:0] qrs_maf_late_event_count;
    wire [5:0] qrs_maf_late_energy_code;
    wire [5:0] qrs_maf_asymmetry_code;
    wire [5:0] qrs_maf_peak_tail_code;
    wire [5:0] qrs_maf_code;
    wire qrs_template_ready;
    wire qrs_template_mismatch_spike;
    wire qrs_template_strong_spike;
    wire qrs_template_width_spike;
    wire qrs_template_energy_spike;
    wire qrs_template_tail_spike;
    wire [5:0] qrs_template_score;
    wire [7:0] qrs_template_count;
    wire abnormal_beat_valid_spike;
    wire abnormal_beat_spike;
    wire abnormal_beat_mid_spike;
    wire abnormal_beat_high_spike;
    wire abnormal_beat_strong_spike;
    wire [7:0] abnormal_beat_score;
    wire abnormal_beat_observe_active;
    wire rbbb_qrs_valid_spike;
    wire rbbb_qrs_wide_spike;
    wire rbbb_qrs_terminal_spike;
    wire rbbb_qrs_like_beat_spike;
    wire rbbb_qrs_segment_spike;
    wire rbbb_qrs_delay_applied;
    wire signed [31:0] score_arr_before_eerg;
    wire eerg_gate;
    wire eerg_applied;
    wire [15:0] eerg_pre_qrs_bump_count;
    wire [15:0] eerg_early_count;
    wire [15:0] eerg_ecp_count;
    wire [15:0] eerg_pnn_decision_count;
    wire [15:0] eerg_pnn_mismatch_count;
    wire [15:0] eerg_rdm_valid_count;
    wire [19:0] eerg_rdm_code_sum;
    wire pnn_regular_high;
    wire dscr_high;
    wire ram_high;
    wire [1:0] pred_class;
    wire pred_valid;

    snn_ecg_3feat_top #(
        .ADC_WIDTH(12),
        .EVENT_TH(8),
        .SLOPE_TH(4),
        .ENABLE_AMP_EVENT(0),
        .AMP_EVENT_TH(4),
        .QRS_MEM_W(12),
        .QRS_REF_W(10),
        .QRS_W_EVENT(8),
        .QRS_LEAK(0),
        .QRS_TH(16),
        .QRS_REF(220),
        .NUM_HYP(46),
        .ID_WIDTH(6),
        .AGE_WIDTH(12),
        .BASE_DELAY(250),
        .DELAY_STEP(50),
        .WINDOW_HALF(125),
        .AMP_WIDTH(13),
        .RAM_WIN(30),
        .TH_PNN_REG(7),
        .TH_DSCR_HIGH(35),
        .TH_RAM_HIGH(13),
        .DSCR_EVENT_WINDOW(256),
        .DSCR_FILTER_SHIFT(4),
        .DSCR_SLOPE_LEAK(8),
        .DSCR_SLOPE_TH(8),
        .RDM_DIFF_TH0(10),
        .RDM_DIFF_TH1(20),
        .RDM_DIFF_TH2(30),
        .RDM_DIFF_TH3(40),
        .RDM_DIFF_TH4(50),
        .RDM_DIFF_TH5(60),
        .RDM_DIFF_TH6(70),
        .RDM_DIFF_TH7(80),
        .RDM_DIFF_TH8(90),
        .RDM_DIFF_TH9(100),
        .RDM_DIFF_TH10(110),
        .RDM_DIFF_TH11(120),
        .RDM_DIFF_TH12(130),
        .RDM_DIFF_TH13(140),
        .RDM_DIFF_TH14(150),
        .ECTOPIC_RR_TH(120),
        .ECTOPIC_REF_SHIFT(4),
        .QRS_MAF_PRE_WIN(120),
        .QRS_MAF_WIN(100),
        .QRS_MAF_WIDTH_TH(120),
        .QRS_MAF_WIDTH_DEV_TH(40),
        .QRS_MAF_COMPLEX_TH(6),
        .QRS_MAF_ENERGY_DEV_TH(8),
        .BIAS_NSR(-5213),
        .BIAS_CHF(-22414),
        .BIAS_ARR(-7298),
        .BIAS_AFF(32767)
    ) dut (
        .clk(clk),
        .rst(rst),
        .sample_valid(sample_valid),
        .rhythm_tick(rhythm_tick),
        .segment_start(segment_start),
        .segment_done(segment_done),
        .adc_data(adc_data),
        .strong_event(strong_event),
        .up_event(up_event),
        .down_event(down_event),
        .slope_valid(slope_valid),
        .beat_spike(beat_spike),
        .token_age(token_age),
        .rr_interval(rr_interval),
        .winner_id(winner_id),
        .predictor_id(predictor_id),
        .pnn_match_spike(pnn_match_spike),
        .pnn_mismatch_spike(pnn_mismatch_spike),
        .dscr_valid_slope_spike(dscr_valid_slope_spike),
        .dscr_sign_flip_spike(dscr_sign_flip_spike),
        .ram_amp_spike(ram_amp_spike),
        .ram_amp_code(ram_amp_code),
        .rdm_valid_spike(rdm_valid_spike),
        .rdm_level_spike(rdm_level_spike),
        .rdm_level_code(rdm_level_code),
        .rdm_rr_diff(rdm_rr_diff),
        .ectopic_early_spike(ectopic_early_spike),
        .ectopic_late_spike(ectopic_late_spike),
        .ectopic_pair_spike(ectopic_pair_spike),
        .ectopic_rr_ref(ectopic_rr_ref),
        .rr_alt_spike(rr_alt_spike),
        .rr_diff_large_spike(rr_diff_large_spike),
        .ram_amp_jump_spike(ram_amp_jump_spike),
        .qrs_width_jump_spike(qrs_width_jump_spike),
        .qrs_width_span(qrs_width_span),
        .qrs_maf_valid_spike(qrs_maf_valid_spike),
        .qrs_maf_spike(qrs_maf_spike),
        .qrs_width_abn_spike(qrs_width_abn_spike),
        .qrs_complex_abn_spike(qrs_complex_abn_spike),
        .qrs_energy_abn_spike(qrs_energy_abn_spike),
        .pre_qrs_bump_spike(pre_qrs_bump_spike),
        .qrs_terminal_delay_spike(qrs_terminal_delay_spike),
        .qrs_late_energy_spike(qrs_late_energy_spike),
        .qrs_asymmetry_spike(qrs_asymmetry_spike),
        .qrs_peak_to_tail_spike(qrs_peak_to_tail_spike),
        .qrs_pvc_like_spike(qrs_pvc_like_spike),
        .qrs_rbbb_like_spike(qrs_rbbb_like_spike),
        .qrs_maf_width_value(qrs_maf_width_value),
        .qrs_maf_complex_count(qrs_maf_complex_count),
        .qrs_maf_energy_code(qrs_maf_energy_code),
        .qrs_maf_late_event_count(qrs_maf_late_event_count),
        .qrs_maf_late_energy_code(qrs_maf_late_energy_code),
        .qrs_maf_asymmetry_code(qrs_maf_asymmetry_code),
        .qrs_maf_peak_tail_code(qrs_maf_peak_tail_code),
        .qrs_maf_code(qrs_maf_code),
        .qrs_template_ready(qrs_template_ready),
        .qrs_template_mismatch_spike(qrs_template_mismatch_spike),
        .qrs_template_strong_spike(qrs_template_strong_spike),
        .qrs_template_width_spike(qrs_template_width_spike),
        .qrs_template_energy_spike(qrs_template_energy_spike),
        .qrs_template_tail_spike(qrs_template_tail_spike),
        .qrs_template_score(qrs_template_score),
        .qrs_template_count(qrs_template_count),
        .rbbb_qrs_valid_spike(rbbb_qrs_valid_spike),
        .rbbb_qrs_wide_spike(rbbb_qrs_wide_spike),
        .rbbb_qrs_terminal_spike(rbbb_qrs_terminal_spike),
        .rbbb_qrs_like_beat_spike(rbbb_qrs_like_beat_spike),
        .rbbb_qrs_segment_spike(rbbb_qrs_segment_spike),
        .rbbb_qrs_delay_applied(rbbb_qrs_delay_applied),
        .score_arr_before_eerg(score_arr_before_eerg),
        .eerg_gate(eerg_gate),
        .eerg_applied(eerg_applied),
        .eerg_pre_qrs_bump_count(eerg_pre_qrs_bump_count),
        .eerg_early_count(eerg_early_count),
        .eerg_ecp_count(eerg_ecp_count),
        .eerg_pnn_decision_count(eerg_pnn_decision_count),
        .eerg_pnn_mismatch_count(eerg_pnn_mismatch_count),
        .eerg_rdm_valid_count(eerg_rdm_valid_count),
        .eerg_rdm_code_sum(eerg_rdm_code_sum),
        .abnormal_beat_valid_spike(abnormal_beat_valid_spike),
        .abnormal_beat_spike(abnormal_beat_spike),
        .abnormal_beat_mid_spike(abnormal_beat_mid_spike),
        .abnormal_beat_high_spike(abnormal_beat_high_spike),
        .abnormal_beat_strong_spike(abnormal_beat_strong_spike),
        .abnormal_beat_score(abnormal_beat_score),
        .abnormal_beat_observe_active(abnormal_beat_observe_active),
        .pnn_regular_high(pnn_regular_high),
        .dscr_high(dscr_high),
        .ram_high(ram_high),
        .pred_class(pred_class),
        .pred_valid(pred_valid)
    );

    always #5 clk = ~clk;

    always @(posedge clk) begin
        if (rst) begin
            beat_count <= 0;
            pnn_match_count <= 0;
            pnn_mismatch_count <= 0;
            dscr_flip_count <= 0;
            dscr_slope_count <= 0;
            ram_code_sum <= 0;
            ram_code_count <= 0;
            rdm_valid_count <= 0;
            rdm_code_sum <= 0;
            ectopic_pair_count <= 0;
            rr_alt_count <= 0;
            amp_jump_count <= 0;
            width_jump_count <= 0;
            qrs_maf_valid_count <= 0;
            qrs_maf_count <= 0;
            qrs_maf_code_sum <= 0;
            qrs_width_abn_count <= 0;
            qrs_complex_abn_count <= 0;
            qrs_energy_abn_count <= 0;
            pre_qrs_bump_count <= 0;
            qrs_terminal_delay_count <= 0;
            qrs_late_energy_count <= 0;
            qrs_asymmetry_count <= 0;
            qrs_peak_to_tail_count <= 0;
            qrs_pvc_like_count <= 0;
            qrs_rbbb_like_count <= 0;
            qrs_maf_width_sum <= 0;
            qrs_maf_complex_sum <= 0;
            qrs_maf_energy_sum <= 0;
            qrs_maf_late_event_sum <= 0;
            qrs_maf_late_energy_sum <= 0;
            qrs_maf_asymmetry_sum <= 0;
            qrs_maf_peak_tail_sum <= 0;
            qrs_template_mismatch_count <= 0;
            qrs_template_strong_count <= 0;
            qrs_template_width_count <= 0;
            qrs_template_energy_count <= 0;
            qrs_template_tail_count <= 0;
            qrs_template_score_sum <= 0;
            qrs_template_ready_count <= 0;
            abnormal_beat_valid_count <= 0;
            abnormal_beat_count <= 0;
            abnormal_beat_mid_count <= 0;
            abnormal_beat_high_count <= 0;
            abnormal_beat_strong_count <= 0;
            abnormal_beat_score_sum <= 0;
            rbbb_delay_valid_count <= 0;
            rbbb_delay_wide_count <= 0;
            rbbb_delay_terminal_count <= 0;
            rbbb_delay_like_count <= 0;
            rbbb_delay_segment_count <= 0;
            rbbb_delay_applied_count <= 0;
            eerg_gate_count <= 0;
            eerg_applied_count <= 0;
            subwindow_id <= 0;
            for (rdm_i = 0; rdm_i < 15; rdm_i = rdm_i + 1)
                rdm_ge_count[rdm_i] <= 0;
        end else begin
            if (beat_spike)
                beat_count <= beat_count + 1;
            if (pnn_match_spike)
                pnn_match_count <= pnn_match_count + 1;
            if (pnn_mismatch_spike)
                pnn_mismatch_count <= pnn_mismatch_count + 1;
            if (dscr_valid_slope_spike)
                dscr_slope_count <= dscr_slope_count + 1;
            if (dscr_sign_flip_spike)
                dscr_flip_count <= dscr_flip_count + 1;
            if (ram_amp_spike) begin
                ram_code_sum <= ram_code_sum + ram_amp_code;
                ram_code_count <= ram_code_count + 1;
            end
            if (rdm_valid_spike) begin
                rdm_valid_count <= rdm_valid_count + 1;
                rdm_code_sum <= rdm_code_sum + rdm_level_code;
                for (rdm_i = 0; rdm_i < 15; rdm_i = rdm_i + 1) begin
                    if (rdm_level_spike[rdm_i])
                        rdm_ge_count[rdm_i] <= rdm_ge_count[rdm_i] + 1;
                end
            end
            if (ectopic_pair_spike)
                ectopic_pair_count <= ectopic_pair_count + 1;
            if (rr_alt_spike)
                rr_alt_count <= rr_alt_count + 1;
            if (ram_amp_jump_spike)
                amp_jump_count <= amp_jump_count + 1;
            if (qrs_width_jump_spike)
                width_jump_count <= width_jump_count + 1;
            if (qrs_maf_valid_spike)
                qrs_maf_valid_count <= qrs_maf_valid_count + 1;
            if (qrs_maf_valid_spike) begin
                qrs_maf_width_sum <= qrs_maf_width_sum + qrs_maf_width_value;
                qrs_maf_complex_sum <= qrs_maf_complex_sum + qrs_maf_complex_count;
                qrs_maf_energy_sum <= qrs_maf_energy_sum + qrs_maf_energy_code;
                qrs_maf_late_event_sum <= qrs_maf_late_event_sum + qrs_maf_late_event_count;
                qrs_maf_late_energy_sum <= qrs_maf_late_energy_sum + qrs_maf_late_energy_code;
                qrs_maf_asymmetry_sum <= qrs_maf_asymmetry_sum + qrs_maf_asymmetry_code;
                qrs_maf_peak_tail_sum <= qrs_maf_peak_tail_sum + qrs_maf_peak_tail_code;
            end
            if (qrs_maf_spike) begin
                qrs_maf_count <= qrs_maf_count + 1;
                qrs_maf_code_sum <= qrs_maf_code_sum + qrs_maf_code;
            end
            if (qrs_width_abn_spike)
                qrs_width_abn_count <= qrs_width_abn_count + 1;
            if (qrs_complex_abn_spike)
                qrs_complex_abn_count <= qrs_complex_abn_count + 1;
            if (qrs_energy_abn_spike)
                qrs_energy_abn_count <= qrs_energy_abn_count + 1;
            if (pre_qrs_bump_spike)
                pre_qrs_bump_count <= pre_qrs_bump_count + 1;
            if (qrs_terminal_delay_spike)
                qrs_terminal_delay_count <= qrs_terminal_delay_count + 1;
            if (qrs_late_energy_spike)
                qrs_late_energy_count <= qrs_late_energy_count + 1;
            if (qrs_asymmetry_spike)
                qrs_asymmetry_count <= qrs_asymmetry_count + 1;
            if (qrs_peak_to_tail_spike)
                qrs_peak_to_tail_count <= qrs_peak_to_tail_count + 1;
            if (qrs_pvc_like_spike)
                qrs_pvc_like_count <= qrs_pvc_like_count + 1;
            if (qrs_rbbb_like_spike)
                qrs_rbbb_like_count <= qrs_rbbb_like_count + 1;
            if (qrs_maf_valid_spike && qrs_template_ready)
                qrs_template_ready_count <= qrs_template_ready_count + 1;
            if (qrs_template_mismatch_spike) begin
                qrs_template_mismatch_count <= qrs_template_mismatch_count + 1;
                qrs_template_score_sum <= qrs_template_score_sum + qrs_template_score;
            end
            if (qrs_template_strong_spike)
                qrs_template_strong_count <= qrs_template_strong_count + 1;
            if (qrs_template_width_spike)
                qrs_template_width_count <= qrs_template_width_count + 1;
            if (qrs_template_energy_spike)
                qrs_template_energy_count <= qrs_template_energy_count + 1;
            if (qrs_template_tail_spike)
                qrs_template_tail_count <= qrs_template_tail_count + 1;
            if (abnormal_beat_valid_spike)
                abnormal_beat_valid_count <= abnormal_beat_valid_count + 1;
            if (abnormal_beat_mid_spike)
                abnormal_beat_mid_count <= abnormal_beat_mid_count + 1;
            if (abnormal_beat_spike)
                abnormal_beat_count <= abnormal_beat_count + 1;
            if (abnormal_beat_high_spike)
                abnormal_beat_high_count <= abnormal_beat_high_count + 1;
            if (abnormal_beat_strong_spike)
                abnormal_beat_strong_count <= abnormal_beat_strong_count + 1;
            if (abnormal_beat_valid_spike)
                abnormal_beat_score_sum <= abnormal_beat_score_sum + abnormal_beat_score;
            if (rbbb_qrs_valid_spike)
                rbbb_delay_valid_count <= rbbb_delay_valid_count + 1;
            if (rbbb_qrs_wide_spike)
                rbbb_delay_wide_count <= rbbb_delay_wide_count + 1;
            if (rbbb_qrs_terminal_spike)
                rbbb_delay_terminal_count <= rbbb_delay_terminal_count + 1;
            if (rbbb_qrs_like_beat_spike)
                rbbb_delay_like_count <= rbbb_delay_like_count + 1;
            if (rbbb_qrs_segment_spike)
                rbbb_delay_segment_count <= rbbb_delay_segment_count + 1;
            if (rbbb_qrs_delay_applied)
                rbbb_delay_applied_count <= rbbb_delay_applied_count + 1;
            if (eerg_gate)
                eerg_gate_count <= eerg_gate_count + 1;
            if (eerg_applied)
                eerg_applied_count <= eerg_applied_count + 1;
            if (WRITE_SUBWINDOW_CSV && (subwindow_fd != 0) && dut.u_class.finalize_window) begin
                $fwrite(subwindow_fd, "%0d,%0s,%0d,%0d,%0d", total_cases, label_name, expected_class, subwindow_id, dut.u_class.window_scale_q4);
                for (feature_i = 0; feature_i < 184; feature_i = feature_i + 1)
                    $fwrite(subwindow_fd, ",%0d", 0);
                $fwrite(subwindow_fd, ",%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                        dut.u_class.local_nsr_next, dut.u_class.local_chf_next,
                        dut.u_class.local_arr_next, dut.u_class.local_aff_next,
                        dut.u_class.score_nsr_next, dut.u_class.score_chf_next,
                        dut.u_class.score_arr_next, dut.u_class.score_aff_next,
                        0);
                $fwrite(subwindow_fd, "\n");
                subwindow_id <= subwindow_id + 1;
            end
        end
    end

    task drive_sample;
        input [11:0] value;
        begin
            @(negedge clk);
            adc_data = value;
            sample_valid = 1'b1;
            rhythm_tick = 1'b1;
            @(posedge clk);
            #1;
            sample_valid = 1'b0;
            rhythm_tick = 1'b0;
        end
    endtask

    task reset_dut;
        begin
            @(negedge clk);
            rst = 1'b1;
            sample_valid = 1'b0;
            rhythm_tick = 1'b0;
            segment_start = 1'b0;
            segment_done = 1'b0;
            adc_data = 12'sd0;
            repeat (4) @(posedge clk);
            rst = 1'b0;
        end
    endtask

    task run_case;
        input integer case_id;
        input integer exp_class;
        input integer sample_count;
        input [8*16-1:0] exp_label;
        input [8*512-1:0] path;
        begin
            $readmemh(path, sample_mem);

            reset_dut();

            @(negedge clk);
            segment_start = 1'b1;
            @(posedge clk);
            #1;
            segment_start = 1'b0;

            for (i = 0; i < sample_count; i = i + 1)
                drive_sample(sample_mem[i]);

            @(negedge clk);
            segment_done = 1'b1;
            @(posedge clk);
            #1;
            segment_done = 1'b0;

            repeat (10) @(posedge clk);

            total_cases = total_cases + 1;
            class_total[exp_class] = class_total[exp_class] + 1;

            if (pred_valid) begin
                pred_valid_cases = pred_valid_cases + 1;
                if (pred_class === exp_class[1:0]) begin
                    correct_cases = correct_cases + 1;
                    class_correct[exp_class] = class_correct[exp_class] + 1;
                end
            end else begin
                errors = errors + 1;
                $display("WARN no pred_valid case=%0d label=%0s file=%0s", case_id, exp_label, path);
            end

            if (WRITE_CASE_CSV && (result_fd != 0)) begin
                $fdisplay(result_fd, "%0d,%0s,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0s",
                          case_id, exp_label, exp_class, pred_class, pred_valid,
                          pred_valid && (pred_class === exp_class[1:0]),
                          beat_count, pnn_match_count, pnn_mismatch_count,
                          dscr_flip_count, dscr_slope_count,
                          ram_code_sum, ram_code_count,
                          rdm_valid_count, rdm_code_sum,
                          rdm_ge_count[0], rdm_ge_count[1], rdm_ge_count[2],
                          rdm_ge_count[3], rdm_ge_count[4], rdm_ge_count[5],
                          rdm_ge_count[6], rdm_ge_count[7], rdm_ge_count[8],
                          rdm_ge_count[9], rdm_ge_count[10], rdm_ge_count[11],
                          rdm_ge_count[12], rdm_ge_count[13], rdm_ge_count[14],
                          dut.score_nsr, dut.score_chf, dut.score_arr, dut.score_aff,
                          ectopic_pair_count, rr_alt_count, amp_jump_count, width_jump_count,
                          qrs_maf_valid_count, qrs_maf_count, qrs_maf_code_sum,
                          qrs_width_abn_count, qrs_complex_abn_count, qrs_energy_abn_count,
                          qrs_terminal_delay_count, qrs_late_energy_count, qrs_asymmetry_count,
                          qrs_peak_to_tail_count, qrs_pvc_like_count, qrs_rbbb_like_count,
                          qrs_maf_width_sum, qrs_maf_complex_sum, qrs_maf_energy_sum,
                          qrs_maf_late_event_sum, qrs_maf_late_energy_sum,
                          qrs_maf_asymmetry_sum, qrs_maf_peak_tail_sum,
                          qrs_template_mismatch_count, qrs_template_strong_count,
                          qrs_template_width_count, qrs_template_energy_count,
                          qrs_template_tail_count, qrs_template_score_sum,
                          qrs_template_ready_count,
                          abnormal_beat_valid_count, abnormal_beat_count,
                          abnormal_beat_mid_count, abnormal_beat_high_count,
                          abnormal_beat_strong_count, abnormal_beat_score_sum,
                          rbbb_delay_valid_count, rbbb_delay_wide_count,
                          rbbb_delay_terminal_count, rbbb_delay_like_count,
                          rbbb_delay_segment_count, rbbb_delay_applied_count,
                          pre_qrs_bump_count, eerg_gate_count, eerg_applied_count,
                          eerg_pre_qrs_bump_count, eerg_early_count, eerg_ecp_count,
                          eerg_pnn_decision_count, eerg_pnn_mismatch_count,
                          eerg_rdm_valid_count, eerg_rdm_code_sum,
                          score_arr_before_eerg,
                          path);
            end

            if ((case_id % 25) == 0) begin
                $display("PROGRESS case=%0d label=%0s expected=%0d pred=%0d correct=%0d/%0d beats=%0d pnn_match/mismatch=%0d/%0d dscr_flip/slope=%0d/%0d ram_code_sum/n=%0d/%0d rdm_code_sum/n=%0d/%0d ectopic_pair=%0d rr_alt=%0d amp_jump=%0d width_jump=%0d qrs_maf=%0d/%0d w/c/e=%0d/%0d/%0d term/late/asym/pt/pvc/rbbb=%0d/%0d/%0d/%0d/%0d/%0d tmpl=m/s/w/e/t=%0d/%0d/%0d/%0d/%0d score=%0d abn=v/mid/high/strong=%0d/%0d/%0d/%0d score=%0d",
                         case_id, exp_label, exp_class, pred_class, correct_cases, total_cases,
                         beat_count, pnn_match_count, pnn_mismatch_count, dscr_flip_count,
                         dscr_slope_count, ram_code_sum, ram_code_count,
                         rdm_code_sum, rdm_valid_count, ectopic_pair_count, rr_alt_count, amp_jump_count, width_jump_count,
                         qrs_maf_count, qrs_maf_valid_count, qrs_width_abn_count, qrs_complex_abn_count, qrs_energy_abn_count,
                         qrs_terminal_delay_count, qrs_late_energy_count, qrs_asymmetry_count,
                         qrs_peak_to_tail_count, qrs_pvc_like_count, qrs_rbbb_like_count,
                         qrs_template_mismatch_count, qrs_template_strong_count,
                         qrs_template_width_count, qrs_template_energy_count,
                         qrs_template_tail_count, qrs_template_score_sum,
                         abnormal_beat_valid_count, abnormal_beat_mid_count,
                         abnormal_beat_high_count, abnormal_beat_strong_count,
                         abnormal_beat_score_sum);
            end
        end
    endtask

    initial begin
        clk = 1'b0;
        rst = 1'b1;
        sample_valid = 1'b0;
        rhythm_tick = 1'b0;
        segment_start = 1'b0;
        segment_done = 1'b0;
        adc_data = 12'sd0;
        total_cases = 0;
        correct_cases = 0;
        pred_valid_cases = 0;
        errors = 0;
        result_fd = 0;
        subwindow_fd = 0;
        beat_count = 0;
        pnn_match_count = 0;
        pnn_mismatch_count = 0;
        dscr_flip_count = 0;
        dscr_slope_count = 0;
        ram_code_sum = 0;
        ram_code_count = 0;
        rdm_valid_count = 0;
        rdm_code_sum = 0;
        ectopic_pair_count = 0;
        rr_alt_count = 0;
        amp_jump_count = 0;
        width_jump_count = 0;
        qrs_maf_valid_count = 0;
        qrs_maf_count = 0;
        qrs_maf_code_sum = 0;
        qrs_width_abn_count = 0;
        qrs_complex_abn_count = 0;
        qrs_energy_abn_count = 0;
        pre_qrs_bump_count = 0;
        qrs_terminal_delay_count = 0;
        qrs_late_energy_count = 0;
        qrs_asymmetry_count = 0;
        qrs_peak_to_tail_count = 0;
        qrs_pvc_like_count = 0;
        qrs_rbbb_like_count = 0;
        qrs_maf_width_sum = 0;
        qrs_maf_complex_sum = 0;
        qrs_maf_energy_sum = 0;
        qrs_maf_late_event_sum = 0;
        qrs_maf_late_energy_sum = 0;
        qrs_maf_asymmetry_sum = 0;
        qrs_maf_peak_tail_sum = 0;
        qrs_template_mismatch_count = 0;
        qrs_template_strong_count = 0;
        qrs_template_width_count = 0;
        qrs_template_energy_count = 0;
        qrs_template_tail_count = 0;
        qrs_template_score_sum = 0;
        qrs_template_ready_count = 0;
        abnormal_beat_valid_count = 0;
        abnormal_beat_count = 0;
        abnormal_beat_mid_count = 0;
        abnormal_beat_high_count = 0;
        abnormal_beat_strong_count = 0;
        abnormal_beat_score_sum = 0;
        rbbb_delay_valid_count = 0;
        rbbb_delay_wide_count = 0;
        rbbb_delay_terminal_count = 0;
        rbbb_delay_like_count = 0;
        rbbb_delay_segment_count = 0;
        rbbb_delay_applied_count = 0;
        eerg_gate_count = 0;
        eerg_applied_count = 0;
        subwindow_id = 0;
        for (rdm_i = 0; rdm_i < 15; rdm_i = rdm_i + 1)
            rdm_ge_count[rdm_i] = 0;

        for (i = 0; i < 4; i = i + 1) begin
            class_total[i] = 0;
            class_correct[i] = 0;
        end

        manifest_fd = $fopen(MANIFEST_FILE, "r");
        if (manifest_fd == 0) begin
            $display("FAIL cannot open manifest: %0s", MANIFEST_FILE);
            $finish;
        end

        if (WRITE_CASE_CSV) begin
            result_fd = $fopen(RESULT_CSV, "w");
            if (result_fd == 0) begin
                $display("FAIL cannot open result csv: %0s", RESULT_CSV);
                $finish;
            end
            $fdisplay(result_fd, "case_id,label,expected_class,pred_class,pred_valid,correct,beat_count,pnn_match_count,pnn_mismatch_count,dscr_flip_count,dscr_slope_count,ram_code_sum,ram_code_count,rdm_valid_count,rdm_code_sum,rdm_ge10_count,rdm_ge20_count,rdm_ge30_count,rdm_ge40_count,rdm_ge50_count,rdm_ge60_count,rdm_ge70_count,rdm_ge80_count,rdm_ge90_count,rdm_ge100_count,rdm_ge110_count,rdm_ge120_count,rdm_ge130_count,rdm_ge140_count,rdm_ge150_count,score_nsr,score_chf,score_arr,score_aff,ectopic_pair_count,rr_alt_count,amp_jump_count,width_jump_count,qrs_maf_valid_count,qrs_maf_count,qrs_maf_code_sum,qrs_width_abn_count,qrs_complex_abn_count,qrs_energy_abn_count,qrs_terminal_delay_count,qrs_late_energy_count,qrs_asymmetry_count,qrs_peak_to_tail_count,qrs_pvc_like_count,qrs_rbbb_like_count,qrs_maf_width_sum,qrs_maf_complex_sum,qrs_maf_energy_sum,qrs_maf_late_event_sum,qrs_maf_late_energy_sum,qrs_maf_asymmetry_sum,qrs_maf_peak_tail_sum,qrs_template_mismatch_count,qrs_template_strong_count,qrs_template_width_count,qrs_template_energy_count,qrs_template_tail_count,qrs_template_score_sum,qrs_template_ready_count,abnormal_beat_valid_count,abnormal_beat_count,abnormal_beat_mid_count,abnormal_beat_high_count,abnormal_beat_strong_count,abnormal_beat_score_sum,rbbb_delay_valid_count,rbbb_delay_wide_count,rbbb_delay_terminal_count,rbbb_delay_like_count,rbbb_delay_segment_count,rbbb_delay_applied_count,pre_qrs_bump_count,eerg_gate_count,eerg_applied_count,eerg_pre_qrs_bump_count,eerg_early_count,eerg_ecp_count,eerg_pnn_decision_count,eerg_pnn_mismatch_count,eerg_rdm_valid_count,eerg_rdm_code_sum,score_arr_before_eerg,mem_file");
        end

        if (WRITE_SUBWINDOW_CSV) begin
            subwindow_fd = $fopen(SUBWINDOW_CSV, "w");
            if (subwindow_fd == 0) begin
                $display("FAIL cannot open subwindow csv: %0s", SUBWINDOW_CSV);
                $finish;
            end
            $fwrite(subwindow_fd, "case_id,label,expected_class,subwindow_id,scale_q4");
            for (feature_i = 0; feature_i < 184; feature_i = feature_i + 1)
                $fwrite(subwindow_fd, ",f%0d", feature_i);
            $fwrite(subwindow_fd, ",local_nsr,local_chf,local_arr,local_aff,seg_nsr,seg_chf,seg_arr,seg_aff,arr_burst_spike");
            $fwrite(subwindow_fd, "\n");
        end

        $display("DATASET_TB_START manifest=%0s", MANIFEST_FILE);

        while (!$feof(manifest_fd)) begin
            if (MANIFEST_HAS_SAMPLE_COUNT)
                scan_count = $fscanf(manifest_fd, "%d %s %d %s\n", expected_class, label_name, case_sample_count, mem_file);
            else begin
                scan_count = $fscanf(manifest_fd, "%d %s %s\n", expected_class, label_name, mem_file);
                case_sample_count = MAX_SAMPLES;
            end
            if (((MANIFEST_HAS_SAMPLE_COUNT == 0) && (scan_count == 3)) || ((MANIFEST_HAS_SAMPLE_COUNT != 0) && (scan_count == 4))) begin
                if ((expected_class >= 0) && (expected_class <= 3))
                    run_case(total_cases, expected_class, case_sample_count, label_name, mem_file);
                else begin
                    errors = errors + 1;
                    $display("WARN invalid class_id=%0d label=%0s file=%0s", expected_class, label_name, mem_file);
                end
            end else if (scan_count != -1) begin
                errors = errors + 1;
                $display("WARN malformed manifest row scan_count=%0d", scan_count);
            end
        end

        $fclose(manifest_fd);
        if (WRITE_CASE_CSV && (result_fd != 0))
            $fclose(result_fd);
        if (WRITE_SUBWINDOW_CSV && (subwindow_fd != 0))
            $fclose(subwindow_fd);

        if (total_cases > 0)
            acc_bp = (correct_cases * 10000) / total_cases;
        else
            acc_bp = 0;

        $display("DATASET_RESULT correct/total = %0d/%0d", correct_cases, total_cases);
        $display("DATASET_ACCURACY = %0d.%02d%%", acc_bp / 100, acc_bp % 100);
        $display("PRED_VALID_RESULT valid/total = %0d/%0d", pred_valid_cases, total_cases);
        $display("CLASS_NSR correct/total = %0d/%0d", class_correct[0], class_total[0]);
        $display("CLASS_CHF correct/total = %0d/%0d", class_correct[1], class_total[1]);
        $display("CLASS_ARR correct/total = %0d/%0d", class_correct[2], class_total[2]);
        $display("CLASS_AFF correct/total = %0d/%0d", class_correct[3], class_total[3]);

        if ((errors == 0) && (total_cases > 0))
            $display("PASS: tb_snn_ecg_3feat_dataset completed");
        else
            $display("FAIL: tb_snn_ecg_3feat_dataset errors=%0d total_cases=%0d", errors, total_cases);

        $finish;
    end
endmodule
