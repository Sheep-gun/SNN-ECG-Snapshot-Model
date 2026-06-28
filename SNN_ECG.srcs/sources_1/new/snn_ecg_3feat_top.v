`timescale 1ns / 1ps



module snn_ecg_3feat_top #(

    parameter ADC_WIDTH   = 12,

    parameter EVENT_TH    = 5,

    parameter SLOPE_TH    = 4,

    parameter ENABLE_AMP_EVENT = 0,

    parameter AMP_EVENT_TH = 4,

    parameter ENABLE_ADAPTIVE_QRS_EVENT = 1,

    parameter ADAPT_QRS_USE_BANK = 1,

    parameter ADAPT_QRS_CALIB_SAMPLES = 2000,

    parameter ADAPT_QRS_MIN_EVENT_TH = 4,

    parameter ADAPT_QRS_PCT_TARGET = 1900,

    parameter ADAPT_QRS_TARGET_EVENT_COUNT = 100,

    parameter ENABLE_INPUT_NORMALIZER = 0,

    parameter NORM_BASE_SHIFT = 8,

    parameter NORM_ENV_DECAY_SHIFT = 6,

    parameter NORM_GAIN_LOW_TH = 96,

    parameter NORM_GAIN_MID_TH = 192,

    parameter NORM_GAIN_HIGH_TH = 768,

    parameter NORM_ENABLE_ADAPTIVE_GAIN = 0,

    parameter QRS_MEM_W   = 12,

    parameter QRS_REF_W   = 10,

    parameter QRS_W_EVENT = 8,

    parameter QRS_LEAK    = 0,

    parameter QRS_TH      = 16,

    parameter QRS_REF     = 280,

    parameter NUM_HYP     = 46,

    parameter ID_WIDTH    = 6,

    parameter AGE_WIDTH   = 12,

    parameter COUNT_WIDTH = 16,

    parameter BASE_DELAY  = 250,

    parameter DELAY_STEP  = 50,

    parameter WINDOW_HALF = 125,

    parameter AMP_WIDTH   = 13,

    parameter ACC_WIDTH   = 24,

    parameter RAM_WIN     = 30,

    parameter RAM_CODE_WIDTH = 6,

    parameter RAM_BANK_SIZE  = 32,

    parameter RAM_BANK_BASE  = 32,

    parameter RAM_BANK_STEP  = 32,

    parameter RAM_POST_HOLD  = 80,

    parameter TH_PNN_REG  = 7,

    parameter TH_DSCR_HIGH = 35,

    parameter TH_RAM_HIGH = 13,

    parameter CLASS_SUBWINDOW_TICKS = 60000,

    parameter DSCR_EVENT_WINDOW = 256,

    parameter DSCR_MEM_WIDTH = 16,

    parameter DSCR_FILTER_SHIFT = 4,

    parameter DSCR_FILTER_FRAC = 8,

    parameter DSCR_SLOPE_LEAK = 8,

    parameter DSCR_SLOPE_TH = 8,

    parameter DSCR_SIGN_LEAK = 0,

    parameter DSCR_SIGN_WEIGHT = 1,

    parameter DSCR_SIGN_TH = 1,

    parameter RDM_DIFF_TH0 = 10,

    parameter RDM_DIFF_TH1 = 20,

    parameter RDM_DIFF_TH2 = 30,

    parameter RDM_DIFF_TH3 = 40,

    parameter RDM_DIFF_TH4 = 50,

    parameter RDM_DIFF_TH5 = 60,

    parameter RDM_DIFF_TH6 = 70,

    parameter RDM_DIFF_TH7 = 80,

    parameter RDM_DIFF_TH8 = 90,

    parameter RDM_DIFF_TH9 = 100,

    parameter RDM_DIFF_TH10 = 110,

    parameter RDM_DIFF_TH11 = 120,

    parameter RDM_DIFF_TH12 = 130,

    parameter RDM_DIFF_TH13 = 140,

    parameter RDM_DIFF_TH14 = 150,

    parameter ECTOPIC_RR_TH = 120,

    parameter ECTOPIC_REF_SHIFT = 4,

    parameter QRS_MAF_PRE_WIN = 120,

    parameter QRS_MAF_WIN = 100,

    parameter QRS_MAF_WIDTH_TH = 120,

    parameter QRS_MAF_WIDTH_DEV_TH = 40,

    parameter QRS_MAF_COMPLEX_TH = 6,

    parameter QRS_MAF_ENERGY_DEV_TH = 8,

    parameter ETMC_T_EARLY = 120,

    parameter ETMC_T_LATE = 150,

    parameter ETMC_RAM_DELTA_TH = 3,

    parameter ETMC_MORPH_MODE = 2,

    parameter ETMC_SPIKE_MODE = 3,

    parameter RCD_QRS_OBS_WIN = 180,

    parameter RCD_TERMINAL_START = 40,

    parameter RCD_TERMINAL_END = 140,

    parameter RCD_QRS_WIDTH_TH = 120,

    parameter RCD_TERMINAL_CNT_TH = 3,

    parameter RCD_COUNT_TH = 1,

    parameter RCD_REG_GATE_ENABLE = 1,

    parameter RCD_HIGH_RDM_LEVEL = 9,

    parameter RCD_ACTIVITY_MODE = 2,

    parameter RCD2_PRE_WIN = 80,

    parameter RCD2_POST_WIN = 140,

    parameter RCD2_TERMINAL_START = 40,

    parameter RCD2_TERMINAL_END = 140,

    parameter RCD2_LOW_SLOPE_TH = 4,

    parameter RCD2_FOOTPRINT_TH = 110,

    parameter RCD2_TERMINAL_COUNT_TH = 10,

    parameter RCD2_COUNT_TH = 2,

    parameter RCD2_HIGH_RDM_LEVEL = 9,

    parameter RCD2_HIGH_IRR_SUPPRESS = 1,

    parameter IPB_BIN_TICKS = 10000,

    parameter IPB_RDM_MID_LEVEL = 4,

    parameter IPB_RDM_HIGH_LEVEL = 9,

    parameter IPB_T_BIN_MID = 2,

    parameter IPB_T_BIN_HIGH = 5,

    parameter IPB_T_PERSIST_BINS = 4,

    parameter IPB_T_BURST_BINS = 1,

    parameter NSR_GATE_PRE_WIN = 80,

    parameter NSR_GATE_POST_WIN = 140,

    parameter NSR_GATE_TERMINAL_START = 40,

    parameter NSR_GATE_TERMINAL_END = 140,

    parameter NSR_GATE_FOOTPRINT_TH = 100,

    parameter NSR_GATE_FOOTPRINT_MAX_TH = 160,

    parameter NSR_GATE_TERMINAL_COUNT_TH = 40,

    parameter NSR_GATE_REPEAT_COUNT_TH = 2,

    parameter NSR_GATE_PNN_HIGH_MIS_PCT = 18,

    parameter ENABLE_NSR_NORMALITY_GATE = 0,

    parameter T_NSR_SUPPRESS_MARGIN = 200000,

    parameter W_NSR_SUPPRESS = 200000,

    parameter T_NSR_GATE_CHF_BLOCK_MARGIN = 0,

    parameter T_NSR_GATE_CHF_OVER_ARR_MARGIN = 0,

    parameter RBBB_LATE_START = 60,

    parameter RBBB_LATE_END = 160,

    parameter RBBB_LATE_SUM_TH = 665,

    parameter RBBB_LATE_GATE_MODE = 0,

    parameter RBBB_LATE_GATE_TH = 665,

    parameter RBBB_LATE_COUNT_TH = 6,

    parameter RBBB_LATE_PNN_HIGH_MIS_PCT = 18,

    parameter ENABLE_RBBB_LATESLOPE_GATE = 0,

    parameter W_RBBB_LATE_NSR_SUPPRESS = 150000,

    parameter W_RBBB_LATE_ARR_BOOST = 150000,

    parameter T_RBBB_LATE_CHF_BLOCK_MARGIN = 0,

    parameter RBBB_QRS_ACTIVITY_MODE = 1,

    parameter RBBB_QRS_LOW_SLOPE_TH = 5,

    parameter RBBB_QRS_ONSET_REF = 200,

    parameter RBBB_QRS_MAX_OBS_WIN = 200,

    parameter RBBB_QRS_GAP_END = 15,

    parameter RBBB_QRS_TERMINAL_START = 90,

    parameter RBBB_QRS_TERMINAL_END = 170,

    parameter RBBB_QRS_WIDE_TH = 120,

    parameter RBBB_QRS_TERMINAL_TH = 4,

    parameter RBBB_QRS_REPEAT_TH = 5,

    parameter RBBB_QRS_PNN_HIGH_MIS_PCT = 18,

    parameter RBBB_QRS_HIGH_RDM_SUPPRESS = 0,

    parameter RBBB_QRS_HIGH_RDM_MODE = 0,

    parameter RBBB_QRS_HIGH_RDM_LEVEL = 11,

    parameter RBBB_QRS_HIGH_RDM_PCT = 5,

    parameter RBBB_QRS_HIGH_RDM_AVG_CODE = 9,

    parameter ENABLE_RBBB_QRS_DELAY_GATE = 1,

    parameter W_RBBB_DELAY_NSR_INH = 100000,

    parameter W_RBBB_DELAY_ARR_BOOST = 100000,

    parameter T_RBBB_DELAY_CHF_BLOCK_MARGIN = 0,

    parameter RBBB_DELAY_CHF_OVER_ARR_BLOCK = 1,

    parameter ENABLE_EERG_GATE = 1,

    parameter W_EERG_ARR_BOOST = 25000,

    parameter EERG_PRE_QRS_BUMP_TH = 1,

    parameter EERG_EARLY_TH = 10,

    parameter EERG_ECP_TH = 3,

    parameter EERG_PNN_MIS_PCT_TH = 15,

    parameter EERG_RDM_AVG_TH = 5,

    parameter W_ETMC_NSR = 0,

    parameter W_ETMC_CHF = 0,

    parameter W_ETMC_ARR = 0,

    parameter W_ETMC_AFF = 0,

    parameter W_RCD_NSR = 0,

    parameter W_RCD_CHF = 0,

    parameter W_RCD_ARR = 0,

    parameter W_RCD_AFF = 0,

    parameter W_RCD2_NSR = 0,

    parameter W_RCD2_CHF = 0,

    parameter W_RCD2_ARR = 0,

    parameter W_RCD2_AFF = 0,

    parameter W_IPB_PERSIST_NSR = 0,

    parameter W_IPB_PERSIST_CHF = 0,

    parameter W_IPB_PERSIST_ARR = 0,

    parameter W_IPB_PERSIST_AFF = 0,

    parameter W_IPB_EPISODIC_NSR = 0,

    parameter W_IPB_EPISODIC_CHF = 0,

    parameter W_IPB_EPISODIC_ARR = 0,

    parameter W_IPB_EPISODIC_AFF = 0,

    parameter W_IPB_BURST_NSR = 0,

    parameter W_IPB_BURST_CHF = 0,

    parameter W_IPB_BURST_ARR = 0,

    parameter W_IPB_BURST_AFF = 0,

    parameter BIAS_NSR = -5213,

    parameter BIAS_CHF = -22414,

    parameter BIAS_ARR = -7298,

    parameter BIAS_AFF = 32767

)(

    input clk,

    input rst,

    input sample_valid,

    input rhythm_tick,

    input segment_start,

    input segment_done,

    input signed [ADC_WIDTH-1:0] adc_data,

    output strong_event,

    output up_event,

    output down_event,

    output slope_valid,

    output beat_spike,

    output [AGE_WIDTH-1:0] token_age,

    output [AGE_WIDTH-1:0] rr_interval,

    output [ID_WIDTH-1:0] winner_id,

    output [ID_WIDTH-1:0] predictor_id,

    output pnn_match_spike,

    output pnn_mismatch_spike,

    output dscr_valid_slope_spike,

    output dscr_sign_flip_spike,

    output ram_amp_spike,

    output [RAM_CODE_WIDTH-1:0] ram_amp_code,

    output rdm_valid_spike,

    output [14:0] rdm_level_spike,

    output [3:0] rdm_level_code,

    output [AGE_WIDTH-1:0] rdm_rr_diff,

    output ectopic_early_spike,

    output ectopic_late_spike,

    output ectopic_pair_spike,

    output [AGE_WIDTH-1:0] ectopic_rr_ref,

    output rr_alt_spike,

    output rr_diff_large_spike,

    output ram_amp_jump_spike,

    output qrs_width_jump_spike,

    output [7:0] qrs_width_span,

    output qrs_maf_valid_spike,

    output qrs_maf_spike,

    output qrs_width_abn_spike,

    output qrs_complex_abn_spike,

    output qrs_energy_abn_spike,

    output pre_qrs_bump_spike,

    output qrs_terminal_delay_spike,

    output qrs_late_energy_spike,

    output qrs_asymmetry_spike,

    output qrs_peak_to_tail_spike,

    output qrs_pvc_like_spike,

    output qrs_rbbb_like_spike,

    output [7:0] qrs_maf_width_value,

    output [5:0] qrs_maf_complex_count,

    output [5:0] qrs_maf_energy_code,

    output [5:0] qrs_maf_late_event_count,

    output [5:0] qrs_maf_late_energy_code,

    output [5:0] qrs_maf_asymmetry_code,

    output [5:0] qrs_maf_peak_tail_code,

    output [5:0] qrs_maf_code,

    output qrs_template_ready,

    output qrs_template_mismatch_spike,

    output qrs_template_strong_spike,

    output qrs_template_width_spike,

    output qrs_template_energy_spike,

    output qrs_template_tail_spike,

    output [5:0] qrs_template_score,

    output [7:0] qrs_template_count,

    output etmc_early_spike,

    output etmc_late_spike,

    output etmc_qrs_abn_spike,

    output etmc_candidate_spike,

    output etmc_compensation_spike,

    output etmc_spike,

    output [AGE_WIDTH-1:0] etmc_rr_ref,

    output rcd_valid_beat_spike,

    output rcd_width_gate_spike,

    output rcd_terminal_gate_spike,

    output rcd_beat_spike,

    output rcd_segment_spike,

    output [7:0] rcd_terminal_count,

    output [7:0] rcd_width_value,

    output [7:0] rcd_beat_count,

    output [7:0] rcd_valid_count,

    output rcd2_valid_beat_spike,

    output rcd2_width_gate_spike,

    output rcd2_terminal_gate_spike,

    output rcd2_beat_spike,

    output rcd2_segment_spike,

    output [7:0] rcd2_footprint_value,

    output [7:0] rcd2_terminal_count,

    output [7:0] rcd2_beat_count,

    output [7:0] rcd2_valid_count,

    output ipb_persistent_irreg_spike,

    output ipb_episodic_irreg_spike,

    output ipb_burst_irreg_spike,

    output [3:0] ipb_high_irreg_bin_count,

    output [3:0] ipb_mid_irreg_bin_count,

    output [3:0] ipb_low_irreg_bin_count,

    output [3:0] ipb_burst_count,

    output [7:0] ipb_current_bin_irreg_count,

    output nsr_gate_valid_beat_spike,

    output nsr_gate_width_gate_spike,

    output nsr_gate_terminal_gate_spike,

    output nsr_gate_abnormal_beat_spike,

    output nsr_suppress_spike,

    output nsr_suppress_applied,

    output rbbb_strict_gate,

    output nsr_gate_low_irregularity,

    output [7:0] nsr_gate_footprint_width,

    output [7:0] nsr_gate_terminal_activity_count,

    output [7:0] nsr_gate_repeated_abnormal_beat_count,

    output [7:0] nsr_gate_valid_beat_count,

    output rbbb_late_beat_valid_spike,

    output rbbb_lateslope_gate_spike,

    output rbbb_lateslope_gate_level,

    output rbbb_lateslope_applied,

    output rbbb_lateslope_low_irregularity,

    output [7:0] rbbb_late_slope_count,

    output [15:0] rbbb_late_slope_sum,

    output [7:0] rbbb_late_slope_max,

    output [7:0] rbbb_late_ge_count,

    output [15:0] rbbb_late_top2_sum,

    output [15:0] rbbb_late_top3_sum,

    output [15:0] rbbb_late_top5_sum,

    output rbbb_qrs_onset_spike,

    output rbbb_qrs_valid_spike,

    output rbbb_qrs_wide_spike,

    output rbbb_qrs_terminal_spike,

    output rbbb_qrs_like_beat_spike,

    output rbbb_qrs_segment_spike,

    output rbbb_qrs_delay_applied,

    output rbbb_qrs_low_irregularity,

    output rbbb_qrs_high_rdm_irregularity,

    output [7:0] rbbb_qrs_last_width,

    output [7:0] rbbb_qrs_terminal_count,

    output [7:0] rbbb_qrs_max_width,

    output [7:0] rbbb_qrs_valid_count,

    output [7:0] rbbb_qrs_wide_count,

    output [7:0] rbbb_qrs_terminal_delay_count,

    output [7:0] rbbb_qrs_like_count,

    output [119:0] rbbb_qrs_combo_counts_flat,

    output abnormal_beat_valid_spike,

    output abnormal_beat_spike,

    output abnormal_beat_mid_spike,

    output abnormal_beat_high_spike,

    output abnormal_beat_strong_spike,

    output [7:0] abnormal_beat_score,

    output abnormal_beat_observe_active,

    output pnn_regular_high,

    output dscr_high,

    output ram_high,

    output signed [31:0] score_nsr_before_suppress,

    output signed [31:0] score_nsr_before_rbbb_late,

    output signed [31:0] score_chf_before_rbbb_late,

    output signed [31:0] score_arr_before_rbbb_late,

    output signed [31:0] score_aff_before_rbbb_late,

    output signed [31:0] score_nsr_before_rbbb_delay,

    output signed [31:0] score_chf_before_rbbb_delay,

    output signed [31:0] score_arr_before_rbbb_delay,

    output signed [31:0] score_aff_before_rbbb_delay,

    output signed [31:0] score_arr_before_eerg,

    output eerg_gate,

    output eerg_applied,

    output [15:0] eerg_pre_qrs_bump_count,

    output [15:0] eerg_early_count,

    output [15:0] eerg_ecp_count,

    output [15:0] eerg_pnn_decision_count,

    output [15:0] eerg_pnn_mismatch_count,

    output [15:0] eerg_rdm_valid_count,

    output [19:0] eerg_rdm_code_sum,

    output signed [63:0] c24_mem_nsr,

    output signed [63:0] c24_mem_chf,

    output signed [63:0] c24_mem_arr,

    output signed [63:0] c24_mem_aff,

    output [1:0] pred_class,

    output pred_valid

);



    wire signed [ADC_WIDTH-1:0] prev_sample;

    wire signed [ADC_WIDTH:0] delta;

    wire [ADC_WIDTH:0] abs_delta;

    wire sample_seen;

    wire adaptive_event_ready;

    wire [7:0] adaptive_event_th;

    wire [QRS_MEM_W-1:0] qrs_mem;

    wire [QRS_REF_W-1:0] refractory_cnt;

    wire token_active;

    wire winner_valid;

    wire predictor_valid;

    wire [AGE_WIDTH-1:0] winner_error;
    wire [AGE_WIDTH-1:0] predictor_error;

    wire ram_window_open;

    wire [AGE_WIDTH-1:0] ram_predictor_center;

    wire [AGE_WIDTH-1:0] ram_predictor_error;

    wire signed [ADC_WIDTH-1:0] adc_norm_data;

    wire signed [ADC_WIDTH-1:0] adc_frontend;

    wire signed [ADC_WIDTH+3:0] norm_baseline_mem;

    wire [ADC_WIDTH+3:0] norm_envelope_mem;

    wire prev_slope_valid;

    wire prev_slope_sign;

    wire amp_window_active;

    wire [RAM_CODE_WIDTH-1:0] amp_window_cnt;

    wire [AMP_WIDTH-1:0] r_peak_abs;

    wire signed [ADC_WIDTH-1:0] baseline;

    wire [AGE_WIDTH-1:0] rdm_current_rr;

    wire [AGE_WIDTH-1:0] rdm_prev_rr;

    wire signed [31:0] score_nsr;

    wire signed [31:0] score_chf;

    wire signed [31:0] score_arr;

    wire signed [31:0] score_aff;

    wire qrs_maf_valid_i;

    wire qrs_width_abn_i;

    wire qrs_complex_abn_i;

    wire qrs_energy_abn_i;

    wire pre_qrs_bump_i;

    wire [7:0] qrs_maf_width_value_i;

    wire [5:0] qrs_maf_complex_count_i;

    wire [5:0] qrs_maf_energy_code_i;

    wire etmc_spike_i;

    wire rcd_segment_spike_i;

    wire rcd2_segment_spike_i;

    wire ipb_persistent_irreg_spike_i;

    wire ipb_episodic_irreg_spike_i;

    wire ipb_burst_irreg_spike_i;

    reg qrs_sample_valid;

    reg rdm_rr_valid_delay;



    assign baseline = {ADC_WIDTH{1'b0}};

    assign rr_alt_spike = 1'b0;

    assign rr_diff_large_spike = 1'b0;

    assign ram_amp_jump_spike = 1'b0;

    assign qrs_width_jump_spike = 1'b0;

    assign qrs_width_span = 8'd0;

    assign qrs_maf_valid_spike = qrs_maf_valid_i;

    assign qrs_width_abn_spike = qrs_width_abn_i;

    assign qrs_complex_abn_spike = qrs_complex_abn_i;

    assign qrs_energy_abn_spike = qrs_energy_abn_i;

    assign pre_qrs_bump_spike = pre_qrs_bump_i;

    assign qrs_maf_spike = qrs_width_abn_i | qrs_complex_abn_i | qrs_energy_abn_i;

    assign qrs_terminal_delay_spike = 1'b0;

    assign qrs_late_energy_spike = 1'b0;

    assign qrs_asymmetry_spike = 1'b0;

    assign qrs_peak_to_tail_spike = 1'b0;

    assign qrs_pvc_like_spike = 1'b0;

    assign qrs_rbbb_like_spike = 1'b0;

    assign qrs_maf_width_value = qrs_maf_width_value_i;

    assign qrs_maf_complex_count = qrs_maf_complex_count_i;

    assign qrs_maf_energy_code = qrs_maf_energy_code_i;

    assign qrs_maf_late_event_count = 6'd0;

    assign qrs_maf_late_energy_code = 6'd0;

    assign qrs_maf_asymmetry_code = 6'd0;

    assign qrs_maf_peak_tail_code = 6'd0;

    assign qrs_maf_code = qrs_maf_energy_code_i;

    assign qrs_template_ready = 1'b0;

    assign qrs_template_mismatch_spike = 1'b0;

    assign qrs_template_strong_spike = 1'b0;

    assign qrs_template_width_spike = 1'b0;

    assign qrs_template_energy_spike = 1'b0;

    assign qrs_template_tail_spike = 1'b0;

    assign qrs_template_score = 6'd0;

    assign qrs_template_count = 8'd0;

    assign abnormal_beat_valid_spike = 1'b0;

    assign abnormal_beat_spike = 1'b0;

    assign abnormal_beat_mid_spike = 1'b0;

    assign abnormal_beat_high_spike = 1'b0;

    assign abnormal_beat_strong_spike = 1'b0;

    assign abnormal_beat_score = 8'd0;

    assign abnormal_beat_observe_active = 1'b0;



    function [AGE_WIDTH-1:0] hyp_center;
        input [ID_WIDTH-1:0] idx;
        integer center_int;
        begin
            center_int = BASE_DELAY + (idx * DELAY_STEP);
            if (center_int > ((1 << AGE_WIDTH) - 1))
                hyp_center = {AGE_WIDTH{1'b1}};
            else
                hyp_center = center_int[AGE_WIDTH-1:0];
        end
    endfunction

    function [AGE_WIDTH-1:0] abs_age_diff;
        input [AGE_WIDTH-1:0] a;
        input [AGE_WIDTH-1:0] b;
        begin
            if (a >= b)
                abs_age_diff = a - b;
            else
                abs_age_diff = b - a;
        end
    endfunction

    assign ram_predictor_center = hyp_center(predictor_id);
    assign ram_predictor_error = abs_age_diff(token_age, ram_predictor_center);
    assign ram_window_open = token_active && predictor_valid && (ram_predictor_error <= WINDOW_HALF);
    assign adc_frontend = (ENABLE_INPUT_NORMALIZER != 0) ? adc_norm_data : adc_data;

    snn_ecg_input_normalizer #(
        .ADC_WIDTH(ADC_WIDTH),
        .BASE_SHIFT(NORM_BASE_SHIFT),
        .ENV_DECAY_SHIFT(NORM_ENV_DECAY_SHIFT),
        .GAIN_LOW_TH(NORM_GAIN_LOW_TH),
        .GAIN_MID_TH(NORM_GAIN_MID_TH),
        .GAIN_HIGH_TH(NORM_GAIN_HIGH_TH),
        .ENABLE_ADAPTIVE_GAIN(NORM_ENABLE_ADAPTIVE_GAIN)
    ) u_input_normalizer (
        .clk(clk),
        .rst(rst),
        .clear(segment_start),
        .sample_valid(sample_valid),
        .adc_in(adc_data),
        .adc_out(adc_norm_data),
        .baseline_mem(norm_baseline_mem),
        .envelope_mem(norm_envelope_mem)
    );

    always @(posedge clk) begin
        if (rst)
            qrs_sample_valid <= 1'b0;
        else
            qrs_sample_valid <= sample_valid;
    end

    always @(posedge clk) begin
        if (rst)
            rdm_rr_valid_delay <= 1'b0;
        else if (segment_start)
            rdm_rr_valid_delay <= 1'b0;
        else
            rdm_rr_valid_delay <= beat_spike && token_active;
    end

    ecg_event_encoder_adaptive #(
        .ADC_WIDTH(ADC_WIDTH),
        .T_EVENT(EVENT_TH),
        .T_SLOPE(SLOPE_TH),
        .ENABLE_AMP_EVENT(ENABLE_AMP_EVENT),
        .T_AMP_EVENT(AMP_EVENT_TH),
        .ENABLE_ADAPTIVE(ENABLE_ADAPTIVE_QRS_EVENT),
        .ADAPT_USE_BANK(ADAPT_QRS_USE_BANK),
        .ADAPT_CALIB_SAMPLES(ADAPT_QRS_CALIB_SAMPLES),
        .ADAPT_MIN_EVENT_TH(ADAPT_QRS_MIN_EVENT_TH),
        .ADAPT_PCT_TARGET(ADAPT_QRS_PCT_TARGET),
        .ADAPT_TARGET_EVENT_COUNT(ADAPT_QRS_TARGET_EVENT_COUNT)
    ) u_event_encoder (
        .clk(clk),
        .rst(rst),
        .sample_valid(sample_valid),
        .segment_start(segment_start),
        .adc_data(adc_frontend),
        .prev_sample(prev_sample),
        .delta(delta),
        .abs_delta(abs_delta),
        .sample_seen(sample_seen),
        .strong_event(strong_event),
        .up_event(up_event),
        .down_event(down_event),
        .slope_valid(slope_valid),
        .adaptive_ready(adaptive_event_ready),
        .adaptive_event_th(adaptive_event_th)
    );

    qrs_lif_detector #(
        .MEM_WIDTH(QRS_MEM_W),
        .REF_WIDTH(QRS_REF_W),
        .W_EVENT(QRS_W_EVENT),
        .LEAK_QRS(QRS_LEAK),
        .T_QRS(QRS_TH),
        .T_REF(QRS_REF)
    ) u_qrs_detector (
        .clk(clk),
        .rst(rst),
        .sample_valid(qrs_sample_valid),
        .strong_event(strong_event),
        .qrs_mem(qrs_mem),
        .refractory_cnt(refractory_cnt),
        .beat_spike(beat_spike)
    );

    pnn_rhythm_predictor #(
        .NUM_HYP(NUM_HYP),
        .ID_WIDTH(ID_WIDTH),
        .AGE_WIDTH(AGE_WIDTH),
        .BASE_DELAY(BASE_DELAY),
        .DELAY_STEP(DELAY_STEP),
        .WINDOW_HALF(WINDOW_HALF)
    ) u_pnn (
        .clk(clk),
        .rst(rst),
        .clear(segment_start),
        .rhythm_tick(rhythm_tick),
        .beat_spike(beat_spike),
        .token_active(token_active),
        .token_age(token_age),
        .rr_interval(rr_interval),
        .winner_id(winner_id),
        .predictor_id(predictor_id),
        .winner_valid(winner_valid),
        .predictor_valid(predictor_valid),
        .winner_error(winner_error),
        .predictor_error(predictor_error),
        .pnn_match_spike(pnn_match_spike),
        .pnn_mismatch_spike(pnn_mismatch_spike)
    );

    dscr_spike_counter #(
        .ADC_WIDTH(ADC_WIDTH),
        .MEM_WIDTH(DSCR_MEM_WIDTH),
        .FILTER_SHIFT(DSCR_FILTER_SHIFT),
        .FILTER_FRAC(DSCR_FILTER_FRAC),
        .SLOPE_INPUT_SHIFT(0),
        .SLOPE_LEAK(DSCR_SLOPE_LEAK),
        .SLOPE_THRESHOLD(DSCR_SLOPE_TH),
        .SIGN_LEAK(DSCR_SIGN_LEAK),
        .SIGN_WEIGHT(DSCR_SIGN_WEIGHT),
        .SIGN_THRESHOLD(DSCR_SIGN_TH)
    ) u_dscr (
        .clk(clk),
        .rst(rst),
        .clear(segment_start),
        .sample_valid(qrs_sample_valid),
        .adc_data(adc_frontend),
        .prev_slope_valid(prev_slope_valid),
        .prev_slope_sign(prev_slope_sign),
        .valid_slope_spike(dscr_valid_slope_spike),
        .sign_flip_spike(dscr_sign_flip_spike)
    );

    ram_peak_accumulator #(
        .ADC_WIDTH(ADC_WIDTH),
        .AMP_WIDTH(AMP_WIDTH),
        .CODE_WIDTH(RAM_CODE_WIDTH),
        .BANK_SIZE(RAM_BANK_SIZE),
        .BANK_BASE(RAM_BANK_BASE),
        .BANK_STEP(RAM_BANK_STEP),
        .POST_WIDTH(8),
        .RAM_POST_HOLD(RAM_POST_HOLD)
    ) u_ram (
        .clk(clk),
        .rst(rst),
        .clear(segment_start),
        .sample_valid(sample_valid),
        .ram_window_open(ram_window_open),
        .beat_spike(beat_spike),
        .adc_data(adc_frontend),
        .baseline(baseline),
        .amp_window_active(amp_window_active),
        .amp_window_cnt(amp_window_cnt),
        .r_peak_abs(r_peak_abs),
        .ram_amp_spike(ram_amp_spike),
        .ram_amp_code(ram_amp_code)
    );

    rdm_variability_neuron #(
        .AGE_WIDTH(AGE_WIDTH),
        .DIFF_TH0(RDM_DIFF_TH0),
        .DIFF_TH1(RDM_DIFF_TH1),
        .DIFF_TH2(RDM_DIFF_TH2),
        .DIFF_TH3(RDM_DIFF_TH3),
        .DIFF_TH4(RDM_DIFF_TH4),
        .DIFF_TH5(RDM_DIFF_TH5),
        .DIFF_TH6(RDM_DIFF_TH6),
        .DIFF_TH7(RDM_DIFF_TH7),
        .DIFF_TH8(RDM_DIFF_TH8),
        .DIFF_TH9(RDM_DIFF_TH9),
        .DIFF_TH10(RDM_DIFF_TH10),
        .DIFF_TH11(RDM_DIFF_TH11),
        .DIFF_TH12(RDM_DIFF_TH12),
        .DIFF_TH13(RDM_DIFF_TH13),
        .DIFF_TH14(RDM_DIFF_TH14)
    ) u_rdm (
        .clk(clk),
        .rst(rst),
        .clear(segment_start),
        .rr_interval_valid_spike(rdm_rr_valid_delay),
        .rr_interval_in(rr_interval),
        .rr_diff_valid_spike(rdm_valid_spike),
        .rdm_level_spike(rdm_level_spike),
        .rdm_level_code(rdm_level_code),
        .current_rr(rdm_current_rr),
        .prev_rr(rdm_prev_rr),
        .rr_diff(rdm_rr_diff)
    );

    ectopic_pair_neuron #(
        .AGE_WIDTH(AGE_WIDTH),
        .RR_DELTA_TH(ECTOPIC_RR_TH),
        .REF_SHIFT(ECTOPIC_REF_SHIFT)
    ) u_ectopic (
        .clk(clk),
        .rst(rst),
        .clear(segment_start),
        .rr_interval_valid_spike(rdm_rr_valid_delay),
        .rr_interval_in(rr_interval),
        .early_rr_spike(ectopic_early_spike),
        .late_rr_spike(ectopic_late_spike),
        .ectopic_pair_spike(ectopic_pair_spike),
        .rr_ref(ectopic_rr_ref)
    );

    qrs_maf_neuron #(
        .ADC_WIDTH(ADC_WIDTH),
        .CODE_WIDTH(6),
        .WIN_WIDTH(8),
        .PRE_WIN(QRS_MAF_PRE_WIN),
        .POST_WIN(QRS_MAF_WIN),
        .WIDTH_TH(QRS_MAF_WIDTH_TH),
        .WIDTH_DEV_TH(QRS_MAF_WIDTH_DEV_TH),
        .COMPLEX_TH(QRS_MAF_COMPLEX_TH),
        .ENERGY_DEV_TH(QRS_MAF_ENERGY_DEV_TH),
        .REF_SHIFT(3)
    ) u_qrs_maf (
        .clk(clk),
        .rst(rst),
        .clear(segment_start),
        .sample_valid(sample_valid),
        .adc_data(adc_frontend),
        .baseline(baseline),
        .strong_event(strong_event),
        .dscr_sign_flip_spike(dscr_sign_flip_spike),
        .beat_spike(beat_spike),
        .qrs_maf_valid_spike(qrs_maf_valid_i),
        .qrs_width_abn_spike(qrs_width_abn_i),
        .qrs_complex_abn_spike(qrs_complex_abn_i),
        .qrs_energy_abn_spike(qrs_energy_abn_i),
        .pre_qrs_bump_spike(pre_qrs_bump_i),
        .qrs_width_value(qrs_maf_width_value_i),
        .qrs_complex_count(qrs_maf_complex_count_i),
        .qrs_energy_code(qrs_maf_energy_code_i)
    );

    rcd_feature #(

        .QRS_OBS_WIN(RCD_QRS_OBS_WIN),

        .TERMINAL_START(RCD_TERMINAL_START),

        .TERMINAL_END(RCD_TERMINAL_END),

        .T_QRS_WIDTH_CNT(RCD_QRS_WIDTH_TH),

        .T_TERMINAL_CNT(RCD_TERMINAL_CNT_TH),

        .T_RCD_COUNT(RCD_COUNT_TH),

        .SUBWINDOW_TICKS(CLASS_SUBWINDOW_TICKS),

        .REG_GATE_ENABLE(RCD_REG_GATE_ENABLE),

        .HIGH_RDM_LEVEL(RCD_HIGH_RDM_LEVEL),

        .ACTIVITY_MODE(RCD_ACTIVITY_MODE)

    ) u_rcd (

        .clk(clk),

        .rst(rst),

        .clear(segment_start),

        .sample_valid(sample_valid),

        .rhythm_tick(rhythm_tick),

        .segment_done(segment_done),

        .beat_spike(beat_spike),

        .strong_event(strong_event),

        .slope_valid(slope_valid),

        .pnn_mismatch_spike(pnn_mismatch_spike),

        .rdm_valid_spike(rdm_valid_spike),

        .rdm_level_spike(rdm_level_spike),

        .qrs_maf_valid_spike(qrs_maf_valid_spike),

        .qrs_width_abn_spike(qrs_width_abn_spike),

        .qrs_width_value(qrs_maf_width_value),

        .rcd_valid_beat_spike(rcd_valid_beat_spike),

        .rcd_width_gate_spike(rcd_width_gate_spike),

        .rcd_terminal_gate_spike(rcd_terminal_gate_spike),

        .rcd_beat_spike(rcd_beat_spike),

        .rcd_segment_spike(rcd_segment_spike_i),

        .rcd_terminal_count(rcd_terminal_count),

        .rcd_width_value(rcd_width_value),

        .rcd_beat_count(rcd_beat_count),

        .rcd_valid_count(rcd_valid_count)

    );



    assign rcd_segment_spike = rcd_segment_spike_i;



    rcd2_feature #(

        .ADC_WIDTH(ADC_WIDTH),

        .ABS_DELTA_WIDTH(ADC_WIDTH + 1),

        .PRE_WIN(RCD2_PRE_WIN),

        .POST_WIN(RCD2_POST_WIN),

        .TERMINAL_START(RCD2_TERMINAL_START),

        .TERMINAL_END(RCD2_TERMINAL_END),

        .LOW_SLOPE_TH(RCD2_LOW_SLOPE_TH),

        .FOOTPRINT_TH(RCD2_FOOTPRINT_TH),

        .TERMINAL_COUNT_TH(RCD2_TERMINAL_COUNT_TH),

        .RCD2_COUNT_TH(RCD2_COUNT_TH),

        .SUBWINDOW_TICKS(CLASS_SUBWINDOW_TICKS),

        .HIGH_RDM_LEVEL(RCD2_HIGH_RDM_LEVEL),

        .HIGH_IRR_SUPPRESS(RCD2_HIGH_IRR_SUPPRESS)

    ) u_rcd2 (

        .clk(clk),

        .rst(rst),

        .clear(segment_start),

        .sample_valid(sample_valid),

        .rhythm_tick(rhythm_tick),

        .segment_done(segment_done),

        .beat_spike(beat_spike),

        .strong_event(strong_event),

        .abs_delta(abs_delta),

        .pnn_mismatch_spike(pnn_mismatch_spike),

        .rdm_valid_spike(rdm_valid_spike),

        .rdm_level_spike(rdm_level_spike),

        .rcd2_valid_beat_spike(rcd2_valid_beat_spike),

        .rcd2_width_gate_spike(rcd2_width_gate_spike),

        .rcd2_terminal_gate_spike(rcd2_terminal_gate_spike),

        .rcd2_beat_spike(rcd2_beat_spike),

        .rcd2_segment_spike(rcd2_segment_spike_i),

        .rcd2_footprint_value(rcd2_footprint_value),

        .rcd2_terminal_count(rcd2_terminal_count),

        .rcd2_beat_count(rcd2_beat_count),

        .rcd2_valid_count(rcd2_valid_count)

    );



    assign rcd2_segment_spike = rcd2_segment_spike_i;



    ipb_feature #(

        .BIN_TICKS(IPB_BIN_TICKS),

        .SUBWINDOW_TICKS(CLASS_SUBWINDOW_TICKS),

        .RDM_MID_LEVEL(IPB_RDM_MID_LEVEL),

        .RDM_HIGH_LEVEL(IPB_RDM_HIGH_LEVEL),

        .T_BIN_MID(IPB_T_BIN_MID),

        .T_BIN_HIGH(IPB_T_BIN_HIGH),

        .T_PERSIST_BINS(IPB_T_PERSIST_BINS),

        .T_BURST_BINS(IPB_T_BURST_BINS)

    ) u_ipb (

        .clk(clk),

        .rst(rst),

        .clear(segment_start),

        .rhythm_tick(rhythm_tick),

        .segment_done(segment_done),

        .pnn_mismatch_spike(pnn_mismatch_spike),

        .rdm_valid_spike(rdm_valid_spike),

        .rdm_level_spike(rdm_level_spike),

        .persistent_irreg_spike(ipb_persistent_irreg_spike_i),

        .episodic_irreg_spike(ipb_episodic_irreg_spike_i),

        .burst_irreg_spike(ipb_burst_irreg_spike_i),

        .high_irreg_bin_count(ipb_high_irreg_bin_count),

        .mid_irreg_bin_count(ipb_mid_irreg_bin_count),

        .low_irreg_bin_count(ipb_low_irreg_bin_count),

        .burst_count(ipb_burst_count),

        .current_bin_irreg_count(ipb_current_bin_irreg_count)

    );



    assign ipb_persistent_irreg_spike = ipb_persistent_irreg_spike_i;

    assign ipb_episodic_irreg_spike = ipb_episodic_irreg_spike_i;

    assign ipb_burst_irreg_spike = ipb_burst_irreg_spike_i;



    nsr_normality_gate #(

        .PRE_WIN(NSR_GATE_PRE_WIN),

        .POST_WIN(NSR_GATE_POST_WIN),

        .TERMINAL_START(NSR_GATE_TERMINAL_START),

        .TERMINAL_END(NSR_GATE_TERMINAL_END),

        .FOOTPRINT_TH(NSR_GATE_FOOTPRINT_TH),

        .FOOTPRINT_MAX_TH(NSR_GATE_FOOTPRINT_MAX_TH),

        .TERMINAL_COUNT_TH(NSR_GATE_TERMINAL_COUNT_TH),

        .REPEAT_COUNT_TH(NSR_GATE_REPEAT_COUNT_TH),

        .PNN_HIGH_MIS_PCT(NSR_GATE_PNN_HIGH_MIS_PCT)

    ) u_nsr_gate (

        .clk(clk),

        .rst(rst),

        .clear(segment_start),

        .sample_valid(sample_valid),

        .segment_done(segment_done),

        .beat_spike(beat_spike),

        .slope_valid(slope_valid),

        .pnn_match_spike(pnn_match_spike),

        .pnn_mismatch_spike(pnn_mismatch_spike),

        .nsr_gate_valid_beat_spike(nsr_gate_valid_beat_spike),

        .nsr_gate_width_gate_spike(nsr_gate_width_gate_spike),

        .nsr_gate_terminal_gate_spike(nsr_gate_terminal_gate_spike),

        .nsr_gate_abnormal_beat_spike(nsr_gate_abnormal_beat_spike),

        .nsr_suppress_spike(nsr_suppress_spike),

        .rbbb_strict_gate(rbbb_strict_gate),

        .low_irregularity(nsr_gate_low_irregularity),

        .qrs_footprint_width(nsr_gate_footprint_width),

        .terminal_activity_count(nsr_gate_terminal_activity_count),

        .repeated_abnormal_beat_count(nsr_gate_repeated_abnormal_beat_count),

        .valid_beat_count(nsr_gate_valid_beat_count)

    );



    rbbb_lateslope_gate #(

        .LATE_START(RBBB_LATE_START),

        .LATE_END(RBBB_LATE_END),

        .LATE_SUM_TH(RBBB_LATE_SUM_TH),

        .LATE_GATE_MODE(RBBB_LATE_GATE_MODE),

        .LATE_GATE_TH(RBBB_LATE_GATE_TH),

        .LATE_COUNT_TH(RBBB_LATE_COUNT_TH),

        .PNN_HIGH_MIS_PCT(RBBB_LATE_PNN_HIGH_MIS_PCT)

    ) u_rbbb_late_gate (

        .clk(clk),

        .rst(rst),

        .clear(segment_start),

        .sample_valid(sample_valid),

        .segment_done(segment_done),

        .beat_spike(beat_spike),

        .slope_valid(slope_valid),

        .pnn_match_spike(pnn_match_spike),

        .pnn_mismatch_spike(pnn_mismatch_spike),

        .late_beat_valid_spike(rbbb_late_beat_valid_spike),

        .late_slope_count(rbbb_late_slope_count),

        .late_slope_sum(rbbb_late_slope_sum),

        .late_slope_max(rbbb_late_slope_max),

        .late_ge_count(rbbb_late_ge_count),

        .late_top2_sum(rbbb_late_top2_sum),

        .late_top3_sum(rbbb_late_top3_sum),

        .late_top5_sum(rbbb_late_top5_sum),

        .rbbb_lateslope_gate_spike(rbbb_lateslope_gate_spike),

        .rbbb_lateslope_gate_level(rbbb_lateslope_gate_level),

        .low_irregularity(rbbb_lateslope_low_irregularity)

    );



    rbbb_qrs_delay_bank #(

        .ABS_DELTA_WIDTH(ADC_WIDTH+1),

        .ACTIVITY_MODE(RBBB_QRS_ACTIVITY_MODE),

        .LOW_SLOPE_TH(RBBB_QRS_LOW_SLOPE_TH),

        .ONSET_REF(RBBB_QRS_ONSET_REF),

        .MAX_QRS_OBS_WIN(RBBB_QRS_MAX_OBS_WIN),

        .ACTIVITY_GAP_END(RBBB_QRS_GAP_END),

        .TERMINAL_START(RBBB_QRS_TERMINAL_START),

        .TERMINAL_END(RBBB_QRS_TERMINAL_END),

        .WIDE_WIDTH_TH(RBBB_QRS_WIDE_TH),

        .TERMINAL_COUNT_TH(RBBB_QRS_TERMINAL_TH),

        .RBBB_REPEAT_TH(RBBB_QRS_REPEAT_TH),

        .PNN_HIGH_MIS_PCT(RBBB_QRS_PNN_HIGH_MIS_PCT),

        .HIGH_RDM_SUPPRESS(RBBB_QRS_HIGH_RDM_SUPPRESS),

        .HIGH_RDM_MODE(RBBB_QRS_HIGH_RDM_MODE),

        .HIGH_RDM_LEVEL(RBBB_QRS_HIGH_RDM_LEVEL),

        .HIGH_RDM_PCT(RBBB_QRS_HIGH_RDM_PCT),

        .HIGH_RDM_AVG_CODE(RBBB_QRS_HIGH_RDM_AVG_CODE)

    ) u_rbbb_qrs_delay (

        .clk(clk),

        .rst(rst),

        .clear(segment_start),

        .sample_valid(sample_valid),

        .segment_done(segment_done),

        .strong_event(strong_event),

        .slope_valid(slope_valid),

        .abs_delta(abs_delta),

        .pnn_match_spike(pnn_match_spike),

        .pnn_mismatch_spike(pnn_mismatch_spike),

        .rdm_valid_spike(rdm_valid_spike),

        .rdm_level_spike(rdm_level_spike),

        .rdm_level_code(rdm_level_code),

        .qrs_onset_spike(rbbb_qrs_onset_spike),

        .qrs_valid_spike(rbbb_qrs_valid_spike),

        .wide_qrs_spike(rbbb_qrs_wide_spike),

        .terminal_delay_spike(rbbb_qrs_terminal_spike),

        .rbbb_like_beat_spike(rbbb_qrs_like_beat_spike),

        .rbbb_segment_spike(rbbb_qrs_segment_spike),

        .low_irregularity(rbbb_qrs_low_irregularity),

        .high_rdm_irregularity(rbbb_qrs_high_rdm_irregularity),

        .last_matched_width(rbbb_qrs_last_width),

        .terminal_activity_count(rbbb_qrs_terminal_count),

        .max_last_matched_width(rbbb_qrs_max_width),

        .valid_qrs_count(rbbb_qrs_valid_count),

        .wide_qrs_count(rbbb_qrs_wide_count),

        .terminal_delay_count(rbbb_qrs_terminal_delay_count),

        .rbbb_like_beat_count(rbbb_qrs_like_count),

        .combo_counts_flat(rbbb_qrs_combo_counts_flat)

    );



    etmc_feature #(

        .AGE_WIDTH(AGE_WIDTH),

        .RAM_CODE_WIDTH(RAM_CODE_WIDTH),

        .T_EARLY(ETMC_T_EARLY),

        .T_LATE(ETMC_T_LATE),

        .T_RAM_DELTA(ETMC_RAM_DELTA_TH),

        .MORPH_MODE(ETMC_MORPH_MODE),

        .SPIKE_MODE(ETMC_SPIKE_MODE)

    ) u_etmc (

        .clk(clk),

        .rst(rst),

        .clear(segment_start),

        .rr_interval_valid_spike(rdm_rr_valid_delay),

        .rr_interval_in(rr_interval),

        .pnn_mismatch_spike(pnn_mismatch_spike),

        .rdm_level_spike(rdm_level_spike),

        .ram_amp_spike(ram_amp_spike),

        .ram_amp_code(ram_amp_code),

        .qrs_maf_valid_spike(qrs_maf_valid_spike),

        .qrs_width_abn_spike(qrs_width_abn_spike),

        .qrs_energy_abn_spike(qrs_energy_abn_spike),

        .etmc_early_spike(etmc_early_spike),

        .etmc_late_spike(etmc_late_spike),

        .etmc_qrs_abn_spike(etmc_qrs_abn_spike),

        .etmc_candidate_spike(etmc_candidate_spike),

        .etmc_compensation_spike(etmc_compensation_spike),

        .etmc_spike(etmc_spike_i),

        .etmc_rr_ref(etmc_rr_ref)

    );



    assign etmc_spike = etmc_spike_i;



    class_score_neurons #(

        .SCORE_WIDTH(32),

        .TH_PNN_REG(TH_PNN_REG),

        .TH_DSCR_HIGH(TH_DSCR_HIGH),

        .TH_RAM_HIGH(TH_RAM_HIGH),

        .SUBWINDOW_TICKS(CLASS_SUBWINDOW_TICKS),

        .BIAS_NSR(BIAS_NSR),

        .BIAS_CHF(BIAS_CHF),

        .BIAS_ARR(BIAS_ARR),

        .BIAS_AFF(BIAS_AFF),

        .W_ETMC_NSR(W_ETMC_NSR),

        .W_ETMC_CHF(W_ETMC_CHF),

        .W_ETMC_ARR(W_ETMC_ARR),

        .W_ETMC_AFF(W_ETMC_AFF),

        .W_RCD_NSR(W_RCD_NSR),

        .W_RCD_CHF(W_RCD_CHF),

        .W_RCD_ARR(W_RCD_ARR),

        .W_RCD_AFF(W_RCD_AFF),

        .W_RCD2_NSR(W_RCD2_NSR),

        .W_RCD2_CHF(W_RCD2_CHF),

        .W_RCD2_ARR(W_RCD2_ARR),

        .W_RCD2_AFF(W_RCD2_AFF),

        .W_IPB_PERSIST_NSR(W_IPB_PERSIST_NSR),

        .W_IPB_PERSIST_CHF(W_IPB_PERSIST_CHF),

        .W_IPB_PERSIST_ARR(W_IPB_PERSIST_ARR),

        .W_IPB_PERSIST_AFF(W_IPB_PERSIST_AFF),

        .W_IPB_EPISODIC_NSR(W_IPB_EPISODIC_NSR),

        .W_IPB_EPISODIC_CHF(W_IPB_EPISODIC_CHF),

        .W_IPB_EPISODIC_ARR(W_IPB_EPISODIC_ARR),

        .W_IPB_EPISODIC_AFF(W_IPB_EPISODIC_AFF),

        .W_IPB_BURST_NSR(W_IPB_BURST_NSR),

        .W_IPB_BURST_CHF(W_IPB_BURST_CHF),

        .W_IPB_BURST_ARR(W_IPB_BURST_ARR),

        .W_IPB_BURST_AFF(W_IPB_BURST_AFF),

        .ENABLE_NSR_NORMALITY_GATE(ENABLE_NSR_NORMALITY_GATE),

        .T_NSR_SUPPRESS_MARGIN(T_NSR_SUPPRESS_MARGIN),

        .W_NSR_SUPPRESS(W_NSR_SUPPRESS),

        .T_NSR_GATE_CHF_BLOCK_MARGIN(T_NSR_GATE_CHF_BLOCK_MARGIN),

        .T_NSR_GATE_CHF_OVER_ARR_MARGIN(T_NSR_GATE_CHF_OVER_ARR_MARGIN),

        .ENABLE_RBBB_LATESLOPE_GATE(ENABLE_RBBB_LATESLOPE_GATE),

        .W_RBBB_LATE_NSR_SUPPRESS(W_RBBB_LATE_NSR_SUPPRESS),

        .W_RBBB_LATE_ARR_BOOST(W_RBBB_LATE_ARR_BOOST),

        .T_RBBB_LATE_CHF_BLOCK_MARGIN(T_RBBB_LATE_CHF_BLOCK_MARGIN),

        .ENABLE_RBBB_QRS_DELAY_GATE(ENABLE_RBBB_QRS_DELAY_GATE),

        .W_RBBB_DELAY_NSR_INH(W_RBBB_DELAY_NSR_INH),

        .W_RBBB_DELAY_ARR_BOOST(W_RBBB_DELAY_ARR_BOOST),

        .T_RBBB_DELAY_CHF_BLOCK_MARGIN(T_RBBB_DELAY_CHF_BLOCK_MARGIN),

        .RBBB_DELAY_CHF_OVER_ARR_BLOCK(RBBB_DELAY_CHF_OVER_ARR_BLOCK),

        .ENABLE_EERG_GATE(ENABLE_EERG_GATE),

        .W_EERG_ARR_BOOST(W_EERG_ARR_BOOST),

        .EERG_PRE_QRS_BUMP_TH(EERG_PRE_QRS_BUMP_TH),

        .EERG_EARLY_TH(EERG_EARLY_TH),

        .EERG_ECP_TH(EERG_ECP_TH),

        .EERG_PNN_MIS_PCT_TH(EERG_PNN_MIS_PCT_TH),

        .EERG_RDM_AVG_TH(EERG_RDM_AVG_TH)

    ) u_class (

        .clk(clk),

        .rst(rst),

        .clear(segment_start),

        .rhythm_tick(rhythm_tick),

        .segment_done(segment_done),

        .beat_spike(beat_spike),

        .qrs_maf_valid_spike(qrs_maf_valid_spike),

        .rbbb_qrs_valid_spike(rbbb_qrs_valid_spike),

        .rbbb_qrs_wide_spike(rbbb_qrs_wide_spike),

        .rbbb_qrs_terminal_spike(rbbb_qrs_terminal_spike),

        .rbbb_qrs_like_beat_spike(rbbb_qrs_like_beat_spike),

        .pnn_match_spike(pnn_match_spike),

        .pnn_mismatch_spike(pnn_mismatch_spike),

        .dscr_valid_slope_spike(dscr_valid_slope_spike),

        .dscr_sign_flip_spike(dscr_sign_flip_spike),

        .ram_amp_spike(ram_amp_spike),

        .ram_amp_code(ram_amp_code),

        .rdm_valid_spike(rdm_valid_spike),

        .rdm_level_spike(rdm_level_spike),

        .ectopic_pair_spike(ectopic_pair_spike),

        .ectopic_early_spike(ectopic_early_spike),

        .pre_qrs_bump_spike(pre_qrs_bump_i),

        .qrs_width_abn_spike(qrs_width_abn_spike),

        .qrs_complex_abn_spike(qrs_complex_abn_spike),

        .qrs_energy_abn_spike(qrs_energy_abn_spike),

        .etmc_spike(etmc_spike_i),

        .rcd_segment_spike(rcd_segment_spike_i),

        .rcd2_segment_spike(rcd2_segment_spike_i),

        .ipb_persistent_irreg_spike(ipb_persistent_irreg_spike_i),

        .ipb_episodic_irreg_spike(ipb_episodic_irreg_spike_i),

        .ipb_burst_irreg_spike(ipb_burst_irreg_spike_i),

        .nsr_suppress_spike(nsr_suppress_spike),

        .rbbb_lateslope_gate_spike(rbbb_lateslope_gate_spike),

        .rbbb_qrs_delay_segment_spike(rbbb_qrs_segment_spike),

        .rbbb_qrs_like_count(rbbb_qrs_like_count),

        .pnn_regular_high(pnn_regular_high),

        .dscr_high(dscr_high),

        .ram_high(ram_high),

        .score_nsr(score_nsr),

        .score_chf(score_chf),

        .score_arr(score_arr),

        .score_aff(score_aff),

        .score_nsr_before_suppress(score_nsr_before_suppress),

        .score_nsr_before_rbbb_late(score_nsr_before_rbbb_late),

        .score_chf_before_rbbb_late(score_chf_before_rbbb_late),

        .score_arr_before_rbbb_late(score_arr_before_rbbb_late),

        .score_aff_before_rbbb_late(score_aff_before_rbbb_late),

        .score_nsr_before_rbbb_delay(score_nsr_before_rbbb_delay),

        .score_chf_before_rbbb_delay(score_chf_before_rbbb_delay),

        .score_arr_before_rbbb_delay(score_arr_before_rbbb_delay),

        .score_aff_before_rbbb_delay(score_aff_before_rbbb_delay),

        .score_arr_before_eerg(score_arr_before_eerg),

        .nsr_suppress_applied(nsr_suppress_applied),

        .rbbb_lateslope_applied(rbbb_lateslope_applied),

        .rbbb_qrs_delay_applied(rbbb_qrs_delay_applied),

        .eerg_gate(eerg_gate),

        .eerg_applied(eerg_applied),

        .eerg_pre_qrs_bump_count(eerg_pre_qrs_bump_count),

        .eerg_early_count(eerg_early_count),

        .eerg_ecp_count(eerg_ecp_count),

        .eerg_pnn_decision_count(eerg_pnn_decision_count),

        .eerg_pnn_mismatch_count(eerg_pnn_mismatch_count),

        .eerg_rdm_valid_count(eerg_rdm_valid_count),

        .eerg_rdm_code_sum(eerg_rdm_code_sum),

        .c24_mem_nsr(c24_mem_nsr),

        .c24_mem_chf(c24_mem_chf),

        .c24_mem_arr(c24_mem_arr),

        .c24_mem_aff(c24_mem_aff),

        .pred_class(pred_class),

        .pred_valid(pred_valid)

    );



endmodule
