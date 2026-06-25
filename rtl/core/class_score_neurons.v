`timescale 1ns / 1ps



module class_score_neurons #(

    parameter SCORE_WIDTH = 32,

    parameter TH_PNN_REG  = 7,

    parameter TH_DSCR_HIGH = 35,

    parameter TH_RAM_HIGH = 13,

    parameter SUBWINDOW_TICKS = 60000,

    parameter BIAS_NSR = -5213,

    parameter BIAS_CHF = -22414,

    parameter BIAS_ARR = -7298,

    parameter BIAS_AFF = 32767,

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

    parameter ENABLE_NSR_NORMALITY_GATE = 0,

    parameter T_NSR_SUPPRESS_MARGIN = 200000,

    parameter W_NSR_SUPPRESS = 200000,

    parameter T_NSR_GATE_CHF_BLOCK_MARGIN = 0,

    parameter T_NSR_GATE_CHF_OVER_ARR_MARGIN = 0,

    parameter ENABLE_RBBB_LATESLOPE_GATE = 0,

    parameter W_RBBB_LATE_NSR_SUPPRESS = 150000,

    parameter W_RBBB_LATE_ARR_BOOST = 150000,

    parameter T_RBBB_LATE_CHF_BLOCK_MARGIN = 0,

    parameter ENABLE_RBBB_QRS_DELAY_GATE = 1,

    parameter W_RBBB_DELAY_NSR_INH = 150000,

    parameter W_RBBB_DELAY_ARR_BOOST = 150000,

    parameter T_RBBB_DELAY_CHF_BLOCK_MARGIN = 0,

    parameter RBBB_DELAY_CHF_OVER_ARR_BLOCK = 1,

    parameter ENABLE_EERG_GATE = 1,

    parameter W_EERG_ARR_BOOST = 25000,

    parameter EERG_PRE_QRS_BUMP_TH = 1,

    parameter EERG_EARLY_TH = 10,

    parameter EERG_ECP_TH = 3,

    parameter EERG_PNN_MIS_PCT_TH = 15,

    parameter EERG_RDM_AVG_TH = 5

)(

    input clk,

    input rst,

    input clear,

    input rhythm_tick,

    input segment_done,

    input pnn_match_spike,

    input pnn_mismatch_spike,

    input dscr_valid_slope_spike,

    input dscr_sign_flip_spike,

    input ram_amp_spike,

    input [5:0] ram_amp_code,

    input rdm_valid_spike,

    input [14:0] rdm_level_spike,

    input ectopic_pair_spike,

    input ectopic_early_spike,

    input pre_qrs_bump_spike,

    input qrs_width_abn_spike,

    input qrs_complex_abn_spike,

    input qrs_energy_abn_spike,

    input etmc_spike,

    input rcd_segment_spike,

    input rcd2_segment_spike,

    input ipb_persistent_irreg_spike,

    input ipb_episodic_irreg_spike,

    input ipb_burst_irreg_spike,

    input nsr_suppress_spike,

    input rbbb_lateslope_gate_spike,

    input rbbb_qrs_delay_segment_spike,

    input [7:0] rbbb_qrs_like_count,

    output reg pnn_regular_high,

    output reg dscr_high,

    output reg ram_high,

    output reg signed [SCORE_WIDTH-1:0] score_nsr,

    output reg signed [SCORE_WIDTH-1:0] score_chf,

    output reg signed [SCORE_WIDTH-1:0] score_arr,

    output reg signed [SCORE_WIDTH-1:0] score_aff,

    output reg signed [SCORE_WIDTH-1:0] score_nsr_before_suppress,

    output reg signed [SCORE_WIDTH-1:0] score_nsr_before_rbbb_late,

    output reg signed [SCORE_WIDTH-1:0] score_chf_before_rbbb_late,

    output reg signed [SCORE_WIDTH-1:0] score_arr_before_rbbb_late,

    output reg signed [SCORE_WIDTH-1:0] score_aff_before_rbbb_late,

    output reg signed [SCORE_WIDTH-1:0] score_nsr_before_rbbb_delay,

    output reg signed [SCORE_WIDTH-1:0] score_chf_before_rbbb_delay,

    output reg signed [SCORE_WIDTH-1:0] score_arr_before_rbbb_delay,

    output reg signed [SCORE_WIDTH-1:0] score_aff_before_rbbb_delay,

    output reg signed [SCORE_WIDTH-1:0] score_arr_before_eerg,

    output reg nsr_suppress_applied,

    output reg rbbb_lateslope_applied,

    output reg rbbb_qrs_delay_applied,

    output reg eerg_gate,

    output reg eerg_applied,

    output reg [15:0] eerg_pre_qrs_bump_count,

    output reg [15:0] eerg_early_count,

    output reg [15:0] eerg_ecp_count,

    output reg [15:0] eerg_pnn_decision_count,

    output reg [15:0] eerg_pnn_mismatch_count,

    output reg [15:0] eerg_rdm_valid_count,

    output reg [19:0] eerg_rdm_code_sum,

    output reg [1:0] pred_class,

    output reg pred_valid

);



    localparam [1:0] CLASS_NSR = 2'd0;

    localparam [1:0] CLASS_CHF = 2'd1;

    localparam [1:0] CLASS_ARR = 2'd2;

    localparam [1:0] CLASS_AFF = 2'd3;



    localparam signed [SCORE_WIDTH-1:0] W_PNN_MATCH_NSR = -32'sd100;

    localparam signed [SCORE_WIDTH-1:0] W_PNN_MATCH_CHF =  32'sd418;

    localparam signed [SCORE_WIDTH-1:0] W_PNN_MATCH_ARR = -32'sd746;

    localparam signed [SCORE_WIDTH-1:0] W_PNN_MATCH_AFF =  32'sd427;

    localparam signed [SCORE_WIDTH-1:0] W_PNN_MIS_NSR   = -32'sd955;

    localparam signed [SCORE_WIDTH-1:0] W_PNN_MIS_CHF   =  32'sd650;

    localparam signed [SCORE_WIDTH-1:0] W_PNN_MIS_ARR   = -32'sd643;

    localparam signed [SCORE_WIDTH-1:0] W_PNN_MIS_AFF   =  32'sd948;



    localparam signed [SCORE_WIDTH-1:0] W_DSCR_FLIP_NSR  =  32'sd650;

    localparam signed [SCORE_WIDTH-1:0] W_DSCR_FLIP_CHF  = -32'sd531;

    localparam signed [SCORE_WIDTH-1:0] W_DSCR_SLOPE_NSR = -32'sd21;

    localparam signed [SCORE_WIDTH-1:0] W_DSCR_SLOPE_CHF =  32'sd9;



    localparam signed [SCORE_WIDTH-1:0] W_RAM_SUM_ARR   = -32'sd23;

    localparam signed [SCORE_WIDTH-1:0] W_RAM_SUM_AFF   = -32'sd92;

    localparam signed [SCORE_WIDTH-1:0] W_RAM_COUNT_ARR = -32'sd987;

    localparam signed [SCORE_WIDTH-1:0] W_RAM_COUNT_AFF =  32'sd577;



    localparam signed [SCORE_WIDTH-1:0] W_RDM_VALID_NSR = -32'sd514;

    localparam signed [SCORE_WIDTH-1:0] W_RDM_VALID_CHF =  32'sd703;

    localparam signed [SCORE_WIDTH-1:0] W_RDM_VALID_ARR = -32'sd1059;

    localparam signed [SCORE_WIDTH-1:0] W_RDM_VALID_AFF =  32'sd871;

    localparam signed [SCORE_WIDTH-1:0] W_RDM_CODE_NSR  = -32'sd16;

    localparam signed [SCORE_WIDTH-1:0] W_RDM_CODE_CHF  = -32'sd12;

    localparam signed [SCORE_WIDTH-1:0] W_RDM_CODE_ARR  =  32'sd18;

    localparam signed [SCORE_WIDTH-1:0] W_RDM_CODE_AFF  =  32'sd10;



    localparam signed [SCORE_WIDTH-1:0] W_SEC_NSR =  32'sd1903;

    localparam signed [SCORE_WIDTH-1:0] W_SEC_CHF =  32'sd802;

    localparam signed [SCORE_WIDTH-1:0] W_SEC_ARR = -32'sd424;

    localparam signed [SCORE_WIDTH-1:0] W_SEC_AFF = -32'sd2281;



    localparam signed [SCORE_WIDTH-1:0] W_ECT_PAIR_NSR =  32'sd976;

    localparam signed [SCORE_WIDTH-1:0] W_ECT_PAIR_CHF =  32'sd1663;

    localparam signed [SCORE_WIDTH-1:0] W_ECT_PAIR_ARR =  32'sd328;

    localparam signed [SCORE_WIDTH-1:0] W_ECT_PAIR_AFF = -32'sd2967;



    localparam signed [SCORE_WIDTH-1:0] W_QRS_WIDTH_COUNT_NSR   = -32'sd2700;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_WIDTH_COUNT_CHF   = -32'sd2500;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_WIDTH_COUNT_ARR   =  32'sd2600;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_WIDTH_COUNT_AFF   =  32'sd700;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_COMPLEX_COUNT_NSR = -32'sd400;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_COMPLEX_COUNT_CHF = -32'sd2100;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_COMPLEX_COUNT_ARR = -32'sd200;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_COMPLEX_COUNT_AFF =  32'sd2500;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_ENERGY_COUNT_NSR  = -32'sd500;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_ENERGY_COUNT_CHF  =  32'sd2900;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_ENERGY_COUNT_ARR  = -32'sd1300;

    localparam signed [SCORE_WIDTH-1:0] W_QRS_ENERGY_COUNT_AFF  = -32'sd2700;



    localparam signed [SCORE_WIDTH-1:0] W_ARR_HIGH_IRR_TO_ARR = 32'sd40000;

    localparam signed [SCORE_WIDTH-1:0] T_NSR_SUPPRESS_MARGIN_S = T_NSR_SUPPRESS_MARGIN;

    localparam signed [SCORE_WIDTH-1:0] W_NSR_SUPPRESS_S = W_NSR_SUPPRESS;

    localparam signed [SCORE_WIDTH-1:0] T_NSR_GATE_CHF_BLOCK_MARGIN_S = T_NSR_GATE_CHF_BLOCK_MARGIN;

    localparam signed [SCORE_WIDTH-1:0] T_NSR_GATE_CHF_OVER_ARR_MARGIN_S = T_NSR_GATE_CHF_OVER_ARR_MARGIN;

    localparam signed [SCORE_WIDTH-1:0] W_RBBB_LATE_NSR_SUPPRESS_S = W_RBBB_LATE_NSR_SUPPRESS;

    localparam signed [SCORE_WIDTH-1:0] W_RBBB_LATE_ARR_BOOST_S = W_RBBB_LATE_ARR_BOOST;

    localparam signed [SCORE_WIDTH-1:0] T_RBBB_LATE_CHF_BLOCK_MARGIN_S = T_RBBB_LATE_CHF_BLOCK_MARGIN;

    localparam signed [SCORE_WIDTH-1:0] W_RBBB_DELAY_NSR_INH_S = W_RBBB_DELAY_NSR_INH;

    localparam signed [SCORE_WIDTH-1:0] W_RBBB_DELAY_ARR_BOOST_S = W_RBBB_DELAY_ARR_BOOST;

    localparam signed [SCORE_WIDTH-1:0] T_RBBB_DELAY_CHF_BLOCK_MARGIN_S = T_RBBB_DELAY_CHF_BLOCK_MARGIN;

    localparam signed [SCORE_WIDTH-1:0] W_EERG_ARR_BOOST_S = W_EERG_ARR_BOOST;

    localparam [15:0] EERG_PRE_QRS_BUMP_TH_U = EERG_PRE_QRS_BUMP_TH;

    localparam [15:0] EERG_EARLY_TH_U = EERG_EARLY_TH;

    localparam [15:0] EERG_ECP_TH_U = EERG_ECP_TH;



    reg signed [SCORE_WIDTH-1:0] local_nsr;

    reg signed [SCORE_WIDTH-1:0] local_chf;

    reg signed [SCORE_WIDTH-1:0] local_arr;

    reg signed [SCORE_WIDTH-1:0] local_aff;

    reg signed [SCORE_WIDTH-1:0] local_nsr_next;

    reg signed [SCORE_WIDTH-1:0] local_chf_next;

    reg signed [SCORE_WIDTH-1:0] local_arr_next;

    reg signed [SCORE_WIDTH-1:0] local_aff_next;

    reg signed [SCORE_WIDTH-1:0] score_nsr_next;

    reg signed [SCORE_WIDTH-1:0] score_chf_next;

    reg signed [SCORE_WIDTH-1:0] score_arr_next;

    reg signed [SCORE_WIDTH-1:0] score_aff_next;

    reg signed [SCORE_WIDTH-1:0] commit_nsr;

    reg signed [SCORE_WIDTH-1:0] commit_chf;

    reg signed [SCORE_WIDTH-1:0] commit_arr;

    reg signed [SCORE_WIDTH-1:0] commit_aff;

    reg signed [SCORE_WIDTH-1:0] best_score;

    reg [1:0] best_class;

    reg [9:0] ms_count;

    reg [16:0] subwindow_tick_count;

    reg [4:0] window_scale_q4;

    reg [4:0] rdm_code_calc;

    reg [7:0] ectopic_pair_win_count;

    reg [7:0] ectopic_pair_win_count_next;

    reg [15:0] ectopic_pair_seg_count;

    reg [15:0] ectopic_pair_seg_count_next;

    reg [15:0] ectopic_early_seg_count;

    reg [15:0] ectopic_early_seg_count_next;

    reg [15:0] pre_qrs_bump_seg_count;

    reg [15:0] pre_qrs_bump_seg_count_next;

    reg [15:0] pnn_match_win_count;

    reg [15:0] pnn_match_win_count_next;

    reg [15:0] pnn_mis_win_count;

    reg [15:0] pnn_mis_win_count_next;

    reg [15:0] pnn_match_seg_count;

    reg [15:0] pnn_match_seg_count_next;

    reg [15:0] pnn_mis_seg_count;

    reg [15:0] pnn_mis_seg_count_next;

    reg [16:0] pnn_decision_win_count;

    reg [16:0] pnn_decision_seg_count;

    reg [15:0] rdm_valid_win_count;

    reg [15:0] rdm_valid_win_count_next;

    reg [19:0] rdm_code_win_sum;

    reg [19:0] rdm_code_win_sum_next;

    reg [15:0] rdm_valid_seg_count;

    reg [15:0] rdm_valid_seg_count_next;

    reg [19:0] rdm_code_seg_sum;

    reg [19:0] rdm_code_seg_sum_next;

    reg [15:0] ram_count_win;

    reg [15:0] ram_count_win_next;

    reg [21:0] ram_code_win_sum;

    reg [21:0] ram_code_win_sum_next;

    reg [31:0] pnn_mis_x100;

    reg [31:0] pnn_mis_seg_x100;

    reg [31:0] pnn_decision_seg_x15;

    reg [31:0] pnn_decision_x12;

    reg [31:0] pnn_decision_x65;

    reg [31:0] rdm_valid_x5;

    reg [31:0] rdm_valid_seg_x5;

    reg [31:0] rdm_valid_x12;

    reg [31:0] ram_count_x12;

    reg [31:0] ectopic_pair_x100;

    reg [31:0] rdm_valid_x4;

    reg [31:0] rdm_valid_x35;

    reg subwindow_period_done;

    reg finalize_window;

    reg arr_high_irregular_spike;

    reg nsr_top_before_suppress;

    reg nsr_near_arr_before_suppress;

    reg nsr_chf_block_before_suppress;

    reg rbbb_late_top_nsr_before;

    reg rbbb_late_chf_block_before;

    reg rbbb_delay_top_nsr_before;

    reg rbbb_delay_chf_block_before;

    reg eerg_gate_next;

    integer i;



    function signed [SCORE_WIDTH-1:0] w_rdm_ge_nsr;

        input integer idx;

        begin

            case (idx)

                0: w_rdm_ge_nsr = -32'sd2616;

                1: w_rdm_ge_nsr =  32'sd458;

                2: w_rdm_ge_nsr =  32'sd2094;

                3: w_rdm_ge_nsr = -32'sd467;

                4: w_rdm_ge_nsr = -32'sd53;

                5: w_rdm_ge_nsr =  32'sd1765;

                6: w_rdm_ge_nsr =  32'sd1287;

                7: w_rdm_ge_nsr = -32'sd733;

                8: w_rdm_ge_nsr = -32'sd637;

                9: w_rdm_ge_nsr = -32'sd665;

                10: w_rdm_ge_nsr = -32'sd1000;

                11: w_rdm_ge_nsr = -32'sd992;

                12: w_rdm_ge_nsr = -32'sd1484;

                13: w_rdm_ge_nsr = -32'sd1536;

                14: w_rdm_ge_nsr = -32'sd2372;

                default: w_rdm_ge_nsr = 32'sd0;

            endcase

        end

    endfunction



    function signed [SCORE_WIDTH-1:0] w_rdm_ge_chf;

        input integer idx;

        begin

            case (idx)

                0: w_rdm_ge_chf = -32'sd2595;

                1: w_rdm_ge_chf = -32'sd730;

                2: w_rdm_ge_chf =  32'sd683;

                3: w_rdm_ge_chf =  32'sd773;

                4: w_rdm_ge_chf = -32'sd116;

                5: w_rdm_ge_chf = -32'sd533;

                6: w_rdm_ge_chf = -32'sd390;

                7: w_rdm_ge_chf =  32'sd135;

                8: w_rdm_ge_chf =  32'sd343;

                9: w_rdm_ge_chf =  32'sd354;

                10: w_rdm_ge_chf =  32'sd192;

                11: w_rdm_ge_chf =  32'sd564;

                12: w_rdm_ge_chf =  32'sd904;

                13: w_rdm_ge_chf =  32'sd267;

                14: w_rdm_ge_chf = -32'sd1037;

                default: w_rdm_ge_chf = 32'sd0;

            endcase

        end

    endfunction



    function signed [SCORE_WIDTH-1:0] w_rdm_ge_arr;

        input integer idx;

        begin

            case (idx)

                0: w_rdm_ge_arr =  32'sd5000;

                1: w_rdm_ge_arr =  32'sd876;

                2: w_rdm_ge_arr = -32'sd2054;

                3: w_rdm_ge_arr = -32'sd356;

                4: w_rdm_ge_arr = -32'sd183;

                5: w_rdm_ge_arr = -32'sd1500;

                6: w_rdm_ge_arr = -32'sd909;

                7: w_rdm_ge_arr =  32'sd453;

                8: w_rdm_ge_arr = -32'sd205;

                9: w_rdm_ge_arr = -32'sd709;

                10: w_rdm_ge_arr =  32'sd243;

                11: w_rdm_ge_arr = -32'sd358;

                12: w_rdm_ge_arr =  32'sd189;

                13: w_rdm_ge_arr =  32'sd940;

                14: w_rdm_ge_arr =  32'sd3099;

                default: w_rdm_ge_arr = 32'sd0;

            endcase

        end

    endfunction



    function signed [SCORE_WIDTH-1:0] w_rdm_ge_aff;

        input integer idx;

        begin

            case (idx)

                0: w_rdm_ge_aff =  32'sd211;

                1: w_rdm_ge_aff = -32'sd603;

                2: w_rdm_ge_aff = -32'sd723;

                3: w_rdm_ge_aff =  32'sd51;

                4: w_rdm_ge_aff =  32'sd351;

                5: w_rdm_ge_aff =  32'sd268;

                6: w_rdm_ge_aff =  32'sd12;

                7: w_rdm_ge_aff =  32'sd144;

                8: w_rdm_ge_aff =  32'sd499;

                9: w_rdm_ge_aff =  32'sd1021;

                10: w_rdm_ge_aff =  32'sd566;

                11: w_rdm_ge_aff =  32'sd787;

                12: w_rdm_ge_aff =  32'sd391;

                13: w_rdm_ge_aff =  32'sd329;

                14: w_rdm_ge_aff =  32'sd310;

                default: w_rdm_ge_aff = 32'sd0;

            endcase

        end

    endfunction



    function [4:0] scale_q4_from_ticks;

        input [16:0] ticks;

        begin

            if (ticks <= 17'd3750) scale_q4_from_ticks = 5'd1;

            else if (ticks <= 17'd7500) scale_q4_from_ticks = 5'd2;

            else if (ticks <= 17'd11250) scale_q4_from_ticks = 5'd3;

            else if (ticks <= 17'd15000) scale_q4_from_ticks = 5'd4;

            else if (ticks <= 17'd18750) scale_q4_from_ticks = 5'd5;

            else if (ticks <= 17'd22500) scale_q4_from_ticks = 5'd6;

            else if (ticks <= 17'd26250) scale_q4_from_ticks = 5'd7;

            else if (ticks <= 17'd30000) scale_q4_from_ticks = 5'd8;

            else if (ticks <= 17'd33750) scale_q4_from_ticks = 5'd9;

            else if (ticks <= 17'd37500) scale_q4_from_ticks = 5'd10;

            else if (ticks <= 17'd41250) scale_q4_from_ticks = 5'd11;

            else if (ticks <= 17'd45000) scale_q4_from_ticks = 5'd12;

            else if (ticks <= 17'd48750) scale_q4_from_ticks = 5'd13;

            else if (ticks <= 17'd52500) scale_q4_from_ticks = 5'd14;

            else if (ticks <= 17'd56250) scale_q4_from_ticks = 5'd15;

            else scale_q4_from_ticks = 5'd16;

        end

    endfunction



    function signed [SCORE_WIDTH-1:0] scale_score_q4;

        input signed [SCORE_WIDTH-1:0] score;

        input [4:0] scale_q4;

        reg signed [SCORE_WIDTH+5:0] s;

        reg signed [SCORE_WIDTH+5:0] product;

        begin

            s = {{6{score[SCORE_WIDTH-1]}}, score};

            case (scale_q4)

                5'd0:  product = {SCORE_WIDTH+6{1'b0}};

                5'd1:  product = s;

                5'd2:  product = s <<< 1;

                5'd3:  product = (s <<< 1) + s;

                5'd4:  product = s <<< 2;

                5'd5:  product = (s <<< 2) + s;

                5'd6:  product = (s <<< 2) + (s <<< 1);

                5'd7:  product = (s <<< 2) + (s <<< 1) + s;

                5'd8:  product = s <<< 3;

                5'd9:  product = (s <<< 3) + s;

                5'd10: product = (s <<< 3) + (s <<< 1);

                5'd11: product = (s <<< 3) + (s <<< 1) + s;

                5'd12: product = (s <<< 3) + (s <<< 2);

                5'd13: product = (s <<< 3) + (s <<< 2) + s;

                5'd14: product = (s <<< 3) + (s <<< 2) + (s <<< 1);

                5'd15: product = (s <<< 3) + (s <<< 2) + (s <<< 1) + s;

                default: product = s <<< 4;

            endcase

            scale_score_q4 = product >>> 4;

        end

    endfunction



    always @* begin

        local_nsr_next = local_nsr;

        local_chf_next = local_chf;

        local_arr_next = local_arr;

        local_aff_next = local_aff;

        score_nsr_next = score_nsr;

        score_chf_next = score_chf;

        score_arr_next = score_arr;

        score_aff_next = score_aff;

        commit_nsr = 32'sd0;

        commit_chf = 32'sd0;

        commit_arr = 32'sd0;

        commit_aff = 32'sd0;

        rdm_code_calc = 5'd0;

        score_nsr_before_rbbb_late = score_nsr_next;

        score_chf_before_rbbb_late = score_chf_next;

        score_arr_before_rbbb_late = score_arr_next;

        score_aff_before_rbbb_late = score_aff_next;

        score_nsr_before_rbbb_delay = score_nsr_next;

        score_chf_before_rbbb_delay = score_chf_next;

        score_arr_before_rbbb_delay = score_arr_next;

        score_aff_before_rbbb_delay = score_aff_next;

        score_arr_before_eerg = score_arr_next;

        nsr_suppress_applied = 1'b0;

        rbbb_lateslope_applied = 1'b0;

        rbbb_qrs_delay_applied = 1'b0;

        eerg_applied = 1'b0;

        eerg_gate_next = 1'b0;

        nsr_top_before_suppress = 1'b0;

        nsr_near_arr_before_suppress = 1'b0;

        nsr_chf_block_before_suppress = 1'b0;

        rbbb_late_top_nsr_before = 1'b0;

        rbbb_late_chf_block_before = 1'b0;

        rbbb_delay_top_nsr_before = 1'b0;

        rbbb_delay_chf_block_before = 1'b0;



        ectopic_pair_win_count_next = ectopic_pair_win_count + (ectopic_pair_spike ? 8'd1 : 8'd0);

        ectopic_pair_seg_count_next = ectopic_pair_seg_count + (ectopic_pair_spike ? 16'd1 : 16'd0);

        ectopic_early_seg_count_next = ectopic_early_seg_count + (ectopic_early_spike ? 16'd1 : 16'd0);

        pre_qrs_bump_seg_count_next = pre_qrs_bump_seg_count + (pre_qrs_bump_spike ? 16'd1 : 16'd0);

        pnn_match_win_count_next = pnn_match_win_count + (pnn_match_spike ? 16'd1 : 16'd0);

        pnn_mis_win_count_next = pnn_mis_win_count + (pnn_mismatch_spike ? 16'd1 : 16'd0);

        pnn_match_seg_count_next = pnn_match_seg_count + (pnn_match_spike ? 16'd1 : 16'd0);

        pnn_mis_seg_count_next = pnn_mis_seg_count + (pnn_mismatch_spike ? 16'd1 : 16'd0);

        rdm_valid_win_count_next = rdm_valid_win_count;

        rdm_code_win_sum_next = rdm_code_win_sum;

        rdm_valid_seg_count_next = rdm_valid_seg_count;

        rdm_code_seg_sum_next = rdm_code_seg_sum;

        ram_count_win_next = ram_count_win;

        ram_code_win_sum_next = ram_code_win_sum;



        if (pnn_match_spike) begin

            local_nsr_next = local_nsr_next + W_PNN_MATCH_NSR;

            local_chf_next = local_chf_next + W_PNN_MATCH_CHF;

            local_arr_next = local_arr_next + W_PNN_MATCH_ARR;

            local_aff_next = local_aff_next + W_PNN_MATCH_AFF;

        end

        if (pnn_mismatch_spike) begin

            local_nsr_next = local_nsr_next + W_PNN_MIS_NSR;

            local_chf_next = local_chf_next + W_PNN_MIS_CHF;

            local_arr_next = local_arr_next + W_PNN_MIS_ARR;

            local_aff_next = local_aff_next + W_PNN_MIS_AFF;

        end

        if (dscr_valid_slope_spike) begin

            local_nsr_next = local_nsr_next + W_DSCR_SLOPE_NSR;

            local_chf_next = local_chf_next + W_DSCR_SLOPE_CHF;

        end

        if (dscr_sign_flip_spike) begin

            local_nsr_next = local_nsr_next + W_DSCR_FLIP_NSR;

            local_chf_next = local_chf_next + W_DSCR_FLIP_CHF;

        end

        if (ram_amp_spike) begin

            local_arr_next = local_arr_next + W_RAM_COUNT_ARR + (W_RAM_SUM_ARR * $signed({26'd0, ram_amp_code}));

            local_aff_next = local_aff_next + W_RAM_COUNT_AFF + (W_RAM_SUM_AFF * $signed({26'd0, ram_amp_code}));

            ram_count_win_next = ram_count_win_next + 16'd1;

            ram_code_win_sum_next = ram_code_win_sum_next + {16'd0, ram_amp_code};

        end

        if (rdm_valid_spike) begin

            for (i = 0; i < 15; i = i + 1) begin

                if (rdm_level_spike[i]) begin

                    rdm_code_calc = rdm_code_calc + 5'd1;

                    local_nsr_next = local_nsr_next + w_rdm_ge_nsr(i);

                    local_chf_next = local_chf_next + w_rdm_ge_chf(i);

                    local_arr_next = local_arr_next + w_rdm_ge_arr(i);

                    local_aff_next = local_aff_next + w_rdm_ge_aff(i);

                end

            end

            local_nsr_next = local_nsr_next + W_RDM_VALID_NSR + (W_RDM_CODE_NSR * $signed({27'd0, rdm_code_calc}));

            local_chf_next = local_chf_next + W_RDM_VALID_CHF + (W_RDM_CODE_CHF * $signed({27'd0, rdm_code_calc}));

            local_arr_next = local_arr_next + W_RDM_VALID_ARR + (W_RDM_CODE_ARR * $signed({27'd0, rdm_code_calc}));

            local_aff_next = local_aff_next + W_RDM_VALID_AFF + (W_RDM_CODE_AFF * $signed({27'd0, rdm_code_calc}));

            rdm_valid_win_count_next = rdm_valid_win_count_next + 16'd1;

            rdm_code_win_sum_next = rdm_code_win_sum_next + {15'd0, rdm_code_calc};

            rdm_valid_seg_count_next = rdm_valid_seg_count_next + 16'd1;

            rdm_code_seg_sum_next = rdm_code_seg_sum_next + {15'd0, rdm_code_calc};

        end

        if (ectopic_pair_spike) begin

            local_nsr_next = local_nsr_next + W_ECT_PAIR_NSR;

            local_chf_next = local_chf_next + W_ECT_PAIR_CHF;

            local_arr_next = local_arr_next + W_ECT_PAIR_ARR;

            local_aff_next = local_aff_next + W_ECT_PAIR_AFF;

        end

        if (qrs_width_abn_spike) begin

            local_nsr_next = local_nsr_next + W_QRS_WIDTH_COUNT_NSR;

            local_chf_next = local_chf_next + W_QRS_WIDTH_COUNT_CHF;

            local_arr_next = local_arr_next + W_QRS_WIDTH_COUNT_ARR;

            local_aff_next = local_aff_next + W_QRS_WIDTH_COUNT_AFF;

        end

        if (qrs_complex_abn_spike) begin

            local_nsr_next = local_nsr_next + W_QRS_COMPLEX_COUNT_NSR;

            local_chf_next = local_chf_next + W_QRS_COMPLEX_COUNT_CHF;

            local_arr_next = local_arr_next + W_QRS_COMPLEX_COUNT_ARR;

            local_aff_next = local_aff_next + W_QRS_COMPLEX_COUNT_AFF;

        end

        if (qrs_energy_abn_spike) begin

            local_nsr_next = local_nsr_next + W_QRS_ENERGY_COUNT_NSR;

            local_chf_next = local_chf_next + W_QRS_ENERGY_COUNT_CHF;

            local_arr_next = local_arr_next + W_QRS_ENERGY_COUNT_ARR;

            local_aff_next = local_aff_next + W_QRS_ENERGY_COUNT_AFF;

        end

        if (etmc_spike) begin

            local_nsr_next = local_nsr_next + W_ETMC_NSR;

            local_chf_next = local_chf_next + W_ETMC_CHF;

            local_arr_next = local_arr_next + W_ETMC_ARR;

            local_aff_next = local_aff_next + W_ETMC_AFF;

        end

        if (rcd_segment_spike) begin

            local_nsr_next = local_nsr_next + W_RCD_NSR;

            local_chf_next = local_chf_next + W_RCD_CHF;

            local_arr_next = local_arr_next + W_RCD_ARR;

            local_aff_next = local_aff_next + W_RCD_AFF;

        end

        if (rcd2_segment_spike) begin

            local_nsr_next = local_nsr_next + W_RCD2_NSR;

            local_chf_next = local_chf_next + W_RCD2_CHF;

            local_arr_next = local_arr_next + W_RCD2_ARR;

            local_aff_next = local_aff_next + W_RCD2_AFF;

        end

        if (ipb_persistent_irreg_spike) begin

            local_nsr_next = local_nsr_next + W_IPB_PERSIST_NSR;

            local_chf_next = local_chf_next + W_IPB_PERSIST_CHF;

            local_arr_next = local_arr_next + W_IPB_PERSIST_ARR;

            local_aff_next = local_aff_next + W_IPB_PERSIST_AFF;

        end

        if (ipb_episodic_irreg_spike) begin

            local_nsr_next = local_nsr_next + W_IPB_EPISODIC_NSR;

            local_chf_next = local_chf_next + W_IPB_EPISODIC_CHF;

            local_arr_next = local_arr_next + W_IPB_EPISODIC_ARR;

            local_aff_next = local_aff_next + W_IPB_EPISODIC_AFF;

        end

        if (ipb_burst_irreg_spike) begin

            local_nsr_next = local_nsr_next + W_IPB_BURST_NSR;

            local_chf_next = local_chf_next + W_IPB_BURST_CHF;

            local_arr_next = local_arr_next + W_IPB_BURST_ARR;

            local_aff_next = local_aff_next + W_IPB_BURST_AFF;

        end

        if (rhythm_tick && (ms_count == 10'd999)) begin

            local_nsr_next = local_nsr_next + W_SEC_NSR;

            local_chf_next = local_chf_next + W_SEC_CHF;

            local_arr_next = local_arr_next + W_SEC_ARR;

            local_aff_next = local_aff_next + W_SEC_AFF;

        end



        subwindow_period_done = rhythm_tick && (subwindow_tick_count == (SUBWINDOW_TICKS - 1));

        finalize_window = subwindow_period_done || (segment_done && (subwindow_tick_count != 17'd0));

        if (subwindow_period_done)

            window_scale_q4 = 5'd16;

        else

            window_scale_q4 = scale_q4_from_ticks(subwindow_tick_count);



        pnn_decision_win_count = {1'b0, pnn_match_win_count_next} + {1'b0, pnn_mis_win_count_next};

        pnn_mis_x100 = ({16'd0, pnn_mis_win_count_next} << 6) +

                       ({16'd0, pnn_mis_win_count_next} << 5) +

                       ({16'd0, pnn_mis_win_count_next} << 2);

        pnn_decision_x12 = ({15'd0, pnn_decision_win_count} << 3) +

                           ({15'd0, pnn_decision_win_count} << 2);

        pnn_decision_x65 = ({15'd0, pnn_decision_win_count} << 6) +

                           {15'd0, pnn_decision_win_count};

        rdm_valid_x5 = ({16'd0, rdm_valid_win_count_next} << 2) +

                       {16'd0, rdm_valid_win_count_next};

        rdm_valid_x12 = ({16'd0, rdm_valid_win_count_next} << 3) +

                        ({16'd0, rdm_valid_win_count_next} << 2);

        ram_count_x12 = ({16'd0, ram_count_win_next} << 3) +

                        ({16'd0, ram_count_win_next} << 2);

        ectopic_pair_x100 = ({24'd0, ectopic_pair_win_count_next} << 6) +

                            ({24'd0, ectopic_pair_win_count_next} << 5) +

                            ({24'd0, ectopic_pair_win_count_next} << 2);

        rdm_valid_x4 = {16'd0, rdm_valid_win_count_next} << 2;

        rdm_valid_x35 = ({16'd0, rdm_valid_win_count_next} << 5) +

                        ({16'd0, rdm_valid_win_count_next} << 1) +

                        {16'd0, rdm_valid_win_count_next};

        pnn_decision_seg_count = {1'b0, pnn_match_seg_count_next} + {1'b0, pnn_mis_seg_count_next};

        pnn_mis_seg_x100 = ({16'd0, pnn_mis_seg_count_next} << 6) +

                           ({16'd0, pnn_mis_seg_count_next} << 5) +

                           ({16'd0, pnn_mis_seg_count_next} << 2);

        pnn_decision_seg_x15 = ({15'd0, pnn_decision_seg_count} << 3) +

                               ({15'd0, pnn_decision_seg_count} << 2) +

                               ({15'd0, pnn_decision_seg_count} << 1) +

                               {15'd0, pnn_decision_seg_count};

        rdm_valid_seg_x5 = ({16'd0, rdm_valid_seg_count_next} << 2) +

                           {16'd0, rdm_valid_seg_count_next};

        eerg_gate_next = (ENABLE_EERG_GATE != 0) &&

                         (rbbb_qrs_like_count == 8'd0) &&

                         (pre_qrs_bump_seg_count_next >= EERG_PRE_QRS_BUMP_TH_U) &&

                         ((ectopic_early_seg_count_next >= EERG_EARLY_TH_U) ||

                          (ectopic_pair_seg_count_next >= EERG_ECP_TH_U)) &&

                         (pnn_decision_seg_count != 17'd0) &&

                         (pnn_mis_seg_x100 <= pnn_decision_seg_x15) &&

                         (rdm_valid_seg_count_next != 16'd0) &&

                         ({12'd0, rdm_code_seg_sum_next} <= rdm_valid_seg_x5);

        arr_high_irregular_spike = finalize_window &&

                                   (pnn_decision_win_count != 17'd0) &&

                                   (pnn_mis_x100 >= pnn_decision_x12) &&

                                   (pnn_mis_x100 <= pnn_decision_x65) &&

                                   (rdm_valid_win_count_next != 16'd0) &&

                                   ({12'd0, rdm_code_win_sum_next} >= rdm_valid_x5) &&

                                   ({12'd0, rdm_code_win_sum_next} <= rdm_valid_x12) &&

                                   (ram_count_win_next != 16'd0) &&

                                   ({10'd0, ram_code_win_sum_next} >= ram_count_x12) &&

                                   (ectopic_pair_x100 >= rdm_valid_x4) &&

                                   (ectopic_pair_x100 <= rdm_valid_x35);



        if (finalize_window) begin

            commit_nsr = scale_score_q4(local_nsr_next - BIAS_NSR, window_scale_q4);

            commit_chf = scale_score_q4(local_chf_next - BIAS_CHF, window_scale_q4);

            commit_arr = scale_score_q4(local_arr_next - BIAS_ARR, window_scale_q4);

            commit_aff = scale_score_q4(local_aff_next - BIAS_AFF, window_scale_q4);

            score_nsr_next = score_nsr + commit_nsr;

            score_chf_next = score_chf + commit_chf;

            score_arr_next = score_arr + commit_arr;

            score_aff_next = score_aff + commit_aff;

            if (arr_high_irregular_spike)

                score_arr_next = score_arr_next + scale_score_q4(W_ARR_HIGH_IRR_TO_ARR, window_scale_q4);

            score_nsr_before_rbbb_late = score_nsr_next;

            score_chf_before_rbbb_late = score_chf_next;

            score_arr_before_rbbb_late = score_arr_next;

            score_aff_before_rbbb_late = score_aff_next;

            if (ENABLE_RBBB_LATESLOPE_GATE && rbbb_lateslope_gate_spike) begin

                rbbb_late_top_nsr_before = (score_nsr_next >= score_chf_next) &&

                                           (score_nsr_next >= score_arr_next) &&

                                           (score_nsr_next >= score_aff_next);

                rbbb_late_chf_block_before = (score_chf_next >

                                             (score_arr_next + T_RBBB_LATE_CHF_BLOCK_MARGIN_S));

                if (rbbb_late_top_nsr_before && !rbbb_late_chf_block_before) begin

                    score_nsr_next = score_nsr_next - W_RBBB_LATE_NSR_SUPPRESS_S;

                    score_arr_next = score_arr_next + W_RBBB_LATE_ARR_BOOST_S;

                    rbbb_lateslope_applied = 1'b1;

                end

            end

            score_nsr_before_rbbb_delay = score_nsr_next;

            score_chf_before_rbbb_delay = score_chf_next;

            score_arr_before_rbbb_delay = score_arr_next;

            score_aff_before_rbbb_delay = score_aff_next;

            if (ENABLE_RBBB_QRS_DELAY_GATE && rbbb_qrs_delay_segment_spike) begin

                rbbb_delay_top_nsr_before = (score_nsr_next >= score_chf_next) &&

                                            (score_nsr_next >= score_arr_next) &&

                                            (score_nsr_next >= score_aff_next);

                rbbb_delay_chf_block_before = (RBBB_DELAY_CHF_OVER_ARR_BLOCK != 0) &&

                                             (score_chf_next >

                                             (score_arr_next + T_RBBB_DELAY_CHF_BLOCK_MARGIN_S));

                if (!rbbb_delay_chf_block_before) begin

                    score_nsr_next = score_nsr_next - W_RBBB_DELAY_NSR_INH_S;

                    score_arr_next = score_arr_next + W_RBBB_DELAY_ARR_BOOST_S;

                    rbbb_qrs_delay_applied = 1'b1;

                end

            end

        end

        if (segment_done && !finalize_window) begin

            score_nsr_before_rbbb_late = score_nsr_next;

            score_chf_before_rbbb_late = score_chf_next;

            score_arr_before_rbbb_late = score_arr_next;

            score_aff_before_rbbb_late = score_aff_next;

            if (ENABLE_RBBB_LATESLOPE_GATE && rbbb_lateslope_gate_spike) begin

                rbbb_late_top_nsr_before = (score_nsr_next >= score_chf_next) &&

                                           (score_nsr_next >= score_arr_next) &&

                                           (score_nsr_next >= score_aff_next);

                rbbb_late_chf_block_before = (score_chf_next >

                                             (score_arr_next + T_RBBB_LATE_CHF_BLOCK_MARGIN_S));

                if (rbbb_late_top_nsr_before && !rbbb_late_chf_block_before) begin

                    score_nsr_next = score_nsr_next - W_RBBB_LATE_NSR_SUPPRESS_S;

                    score_arr_next = score_arr_next + W_RBBB_LATE_ARR_BOOST_S;

                    rbbb_lateslope_applied = 1'b1;

                end

            end

            score_nsr_before_rbbb_delay = score_nsr_next;

            score_chf_before_rbbb_delay = score_chf_next;

            score_arr_before_rbbb_delay = score_arr_next;

            score_aff_before_rbbb_delay = score_aff_next;

            if (ENABLE_RBBB_QRS_DELAY_GATE && rbbb_qrs_delay_segment_spike) begin

                rbbb_delay_top_nsr_before = (score_nsr_next >= score_chf_next) &&

                                            (score_nsr_next >= score_arr_next) &&

                                            (score_nsr_next >= score_aff_next);

                rbbb_delay_chf_block_before = (RBBB_DELAY_CHF_OVER_ARR_BLOCK != 0) &&

                                             (score_chf_next >

                                             (score_arr_next + T_RBBB_DELAY_CHF_BLOCK_MARGIN_S));

                if (!rbbb_delay_chf_block_before) begin

                    score_nsr_next = score_nsr_next - W_RBBB_DELAY_NSR_INH_S;

                    score_arr_next = score_arr_next + W_RBBB_DELAY_ARR_BOOST_S;

                    rbbb_qrs_delay_applied = 1'b1;

                end

            end

        end

        score_arr_before_eerg = score_arr_next;

        if (segment_done && eerg_gate_next) begin

            score_arr_next = score_arr_next + W_EERG_ARR_BOOST_S;

            eerg_applied = 1'b1;

        end



        best_score = score_nsr_next;

        best_class = CLASS_NSR;

        if (score_chf_next > best_score) begin best_score = score_chf_next; best_class = CLASS_CHF; end

        if (score_arr_next > best_score) begin best_score = score_arr_next; best_class = CLASS_ARR; end

        if (score_aff_next > best_score) begin best_score = score_aff_next; best_class = CLASS_AFF; end

    end



    always @(posedge clk) begin

        if (rst) begin

            local_nsr <= BIAS_NSR;

            local_chf <= BIAS_CHF;

            local_arr <= BIAS_ARR;

            local_aff <= BIAS_AFF;

            score_nsr <= BIAS_NSR;

            score_chf <= BIAS_CHF;

            score_arr <= BIAS_ARR;

            score_aff <= BIAS_AFF;

            pred_class <= CLASS_NSR;

            pred_valid <= 1'b0;

            pnn_regular_high <= 1'b0;

            dscr_high <= 1'b0;

            ram_high <= 1'b0;

            ms_count <= 10'd0;

            subwindow_tick_count <= 17'd0;

            ectopic_pair_win_count <= 8'd0;

            ectopic_pair_seg_count <= 16'd0;

            ectopic_early_seg_count <= 16'd0;

            pre_qrs_bump_seg_count <= 16'd0;

            pnn_match_win_count <= 16'd0;

            pnn_mis_win_count <= 16'd0;

            pnn_match_seg_count <= 16'd0;

            pnn_mis_seg_count <= 16'd0;

            rdm_valid_win_count <= 16'd0;

            rdm_code_win_sum <= 20'd0;

            rdm_valid_seg_count <= 16'd0;

            rdm_code_seg_sum <= 20'd0;

            ram_count_win <= 16'd0;

            ram_code_win_sum <= 22'd0;

            eerg_gate <= 1'b0;

            eerg_pre_qrs_bump_count <= 16'd0;

            eerg_early_count <= 16'd0;

            eerg_ecp_count <= 16'd0;

            eerg_pnn_decision_count <= 16'd0;

            eerg_pnn_mismatch_count <= 16'd0;

            eerg_rdm_valid_count <= 16'd0;

            eerg_rdm_code_sum <= 20'd0;

        end else if (clear) begin

            local_nsr <= BIAS_NSR;

            local_chf <= BIAS_CHF;

            local_arr <= BIAS_ARR;

            local_aff <= BIAS_AFF;

            score_nsr <= BIAS_NSR;

            score_chf <= BIAS_CHF;

            score_arr <= BIAS_ARR;

            score_aff <= BIAS_AFF;

            pred_class <= CLASS_NSR;

            pred_valid <= 1'b0;

            pnn_regular_high <= 1'b0;

            dscr_high <= 1'b0;

            ram_high <= 1'b0;

            ms_count <= 10'd0;

            subwindow_tick_count <= 17'd0;

            ectopic_pair_win_count <= 8'd0;

            ectopic_pair_seg_count <= 16'd0;

            ectopic_early_seg_count <= 16'd0;

            pre_qrs_bump_seg_count <= 16'd0;

            pnn_match_win_count <= 16'd0;

            pnn_mis_win_count <= 16'd0;

            pnn_match_seg_count <= 16'd0;

            pnn_mis_seg_count <= 16'd0;

            rdm_valid_win_count <= 16'd0;

            rdm_code_win_sum <= 20'd0;

            rdm_valid_seg_count <= 16'd0;

            rdm_code_seg_sum <= 20'd0;

            ram_count_win <= 16'd0;

            ram_code_win_sum <= 22'd0;

            eerg_gate <= 1'b0;

            eerg_pre_qrs_bump_count <= 16'd0;

            eerg_early_count <= 16'd0;

            eerg_ecp_count <= 16'd0;

            eerg_pnn_decision_count <= 16'd0;

            eerg_pnn_mismatch_count <= 16'd0;

            eerg_rdm_valid_count <= 16'd0;

            eerg_rdm_code_sum <= 20'd0;

        end else begin

            score_nsr <= score_nsr_next;

            score_chf <= score_chf_next;

            score_arr <= score_arr_next;

            score_aff <= score_aff_next;



            if (finalize_window) begin

                local_nsr <= BIAS_NSR;

                local_chf <= BIAS_CHF;

                local_arr <= BIAS_ARR;

                local_aff <= BIAS_AFF;

                ectopic_pair_win_count <= 8'd0;

                pnn_match_win_count <= 16'd0;

                pnn_mis_win_count <= 16'd0;

                rdm_valid_win_count <= 16'd0;

                rdm_code_win_sum <= 20'd0;

                ram_count_win <= 16'd0;

                ram_code_win_sum <= 22'd0;

                pnn_regular_high <= local_nsr_next >= local_arr_next;

                dscr_high <= local_nsr_next >= local_chf_next;

                ram_high <= local_arr_next >= local_aff_next;

            end else begin

                local_nsr <= local_nsr_next;

                local_chf <= local_chf_next;

                local_arr <= local_arr_next;

                local_aff <= local_aff_next;

                ectopic_pair_win_count <= ectopic_pair_win_count_next;

                pnn_match_win_count <= pnn_match_win_count_next;

                pnn_mis_win_count <= pnn_mis_win_count_next;

                rdm_valid_win_count <= rdm_valid_win_count_next;

                rdm_code_win_sum <= rdm_code_win_sum_next;

                ram_count_win <= ram_count_win_next;

                ram_code_win_sum <= ram_code_win_sum_next;

            end



            if (rhythm_tick) begin

                if (ms_count == 10'd999)

                    ms_count <= 10'd0;

                else

                    ms_count <= ms_count + 10'd1;



                if (subwindow_period_done)

                    subwindow_tick_count <= 17'd0;

                else

                    subwindow_tick_count <= subwindow_tick_count + 17'd1;

            end

            if (segment_done) begin

                eerg_gate <= eerg_gate_next;

                eerg_pre_qrs_bump_count <= pre_qrs_bump_seg_count_next;

                eerg_early_count <= ectopic_early_seg_count_next;

                eerg_ecp_count <= ectopic_pair_seg_count_next;

                eerg_pnn_decision_count <= pnn_decision_seg_count[15:0];

                eerg_pnn_mismatch_count <= pnn_mis_seg_count_next;

                eerg_rdm_valid_count <= rdm_valid_seg_count_next;

                eerg_rdm_code_sum <= rdm_code_seg_sum_next;

                ectopic_pair_seg_count <= 16'd0;

                ectopic_early_seg_count <= 16'd0;

                pre_qrs_bump_seg_count <= 16'd0;

                pnn_match_seg_count <= 16'd0;

                pnn_mis_seg_count <= 16'd0;

                rdm_valid_seg_count <= 16'd0;

                rdm_code_seg_sum <= 20'd0;

            end else begin

                eerg_gate <= 1'b0;

                ectopic_pair_seg_count <= ectopic_pair_seg_count_next;

                ectopic_early_seg_count <= ectopic_early_seg_count_next;

                pre_qrs_bump_seg_count <= pre_qrs_bump_seg_count_next;

                pnn_match_seg_count <= pnn_match_seg_count_next;

                pnn_mis_seg_count <= pnn_mis_seg_count_next;

                rdm_valid_seg_count <= rdm_valid_seg_count_next;

                rdm_code_seg_sum <= rdm_code_seg_sum_next;

            end



            if (segment_done) begin

                pred_class <= best_class;

                pred_valid <= 1'b1;

                ms_count <= 10'd0;

                subwindow_tick_count <= 17'd0;

            end

        end

    end

endmodule
