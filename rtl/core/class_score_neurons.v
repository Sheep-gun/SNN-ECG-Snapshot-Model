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

    parameter EERG_RDM_AVG_TH = 5

)(

    input clk,

    input rst,

    input clear,

    input rhythm_tick,

    input segment_done,

    input beat_spike,

    input qrs_maf_valid_spike,

    input rbbb_qrs_valid_spike,

    input rbbb_qrs_wide_spike,

    input rbbb_qrs_terminal_spike,

    input rbbb_qrs_like_beat_spike,

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

    output reg signed [63:0] c24_mem_nsr,

    output reg signed [63:0] c24_mem_chf,

    output reg signed [63:0] c24_mem_arr,

    output reg signed [63:0] c24_mem_aff,

    output reg [1:0] pred_class,

    output reg pred_valid

);



    localparam [1:0] CLASS_NSR = 2'd0;

    localparam [1:0] CLASS_CHF = 2'd1;

    localparam [1:0] CLASS_ARR = 2'd2;

    localparam [1:0] CLASS_AFF = 2'd3;

    localparam ENABLE_C24_GLOBAL_READOUT = 1;

    localparam signed [63:0] C24_MEM_INIT_NSR = -64'sd31470242;
    localparam signed [63:0] C24_MEM_INIT_CHF = -64'sd53294831;
    localparam signed [63:0] C24_MEM_INIT_ARR = -64'sd30853479;
    localparam signed [63:0] C24_MEM_INIT_AFF = -64'sd88781713;

    localparam signed [63:0] C24_W_PNN_MATCH_NSR = -64'sd172275;
    localparam signed [63:0] C24_W_PNN_MATCH_CHF = 64'sd421505;
    localparam signed [63:0] C24_W_PNN_MATCH_ARR = -64'sd307519;
    localparam signed [63:0] C24_W_PNN_MATCH_AFF = 64'sd60643;

    localparam signed [63:0] C24_W_PNN_MIS_NSR = -64'sd255769;
    localparam signed [63:0] C24_W_PNN_MIS_CHF = 64'sd361470;
    localparam signed [63:0] C24_W_PNN_MIS_ARR = -64'sd461123;
    localparam signed [63:0] C24_W_PNN_MIS_AFF = 64'sd323992;

    localparam signed [63:0] C24_W_DSCR_FLIP_NSR = 64'sd99665;
    localparam signed [63:0] C24_W_DSCR_FLIP_CHF = -64'sd97569;
    localparam signed [63:0] C24_W_DSCR_FLIP_ARR = -64'sd79354;
    localparam signed [63:0] C24_W_DSCR_FLIP_AFF = 64'sd101622;

    localparam signed [63:0] C24_W_DSCR_SLOPE_NSR = -64'sd2495;
    localparam signed [63:0] C24_W_DSCR_SLOPE_CHF = 64'sd649;
    localparam signed [63:0] C24_W_DSCR_SLOPE_ARR = 64'sd61;
    localparam signed [63:0] C24_W_DSCR_SLOPE_AFF = 64'sd756;

    localparam signed [63:0] C24_W_RAM_COUNT_NSR = -64'sd170667;
    localparam signed [63:0] C24_W_RAM_COUNT_CHF = 64'sd417727;
    localparam signed [63:0] C24_W_RAM_COUNT_ARR = -64'sd474131;
    localparam signed [63:0] C24_W_RAM_COUNT_AFF = 64'sd188927;

    localparam signed [63:0] C24_W_RAM_CODE_NSR = 64'sd20621;
    localparam signed [63:0] C24_W_RAM_CODE_CHF = -64'sd11950;
    localparam signed [63:0] C24_W_RAM_CODE_ARR = 64'sd8622;
    localparam signed [63:0] C24_W_RAM_CODE_AFF = -64'sd20197;

    localparam signed [63:0] C24_W_RDM_VALID_NSR = -64'sd294110;
    localparam signed [63:0] C24_W_RDM_VALID_CHF = 64'sd610517;
    localparam signed [63:0] C24_W_RDM_VALID_ARR = -64'sd593336;
    localparam signed [63:0] C24_W_RDM_VALID_AFF = 64'sd290313;

    localparam signed [63:0] C24_W_RDM_CODE_NSR = -64'sd1857;
    localparam signed [63:0] C24_W_RDM_CODE_CHF = -64'sd6908;
    localparam signed [63:0] C24_W_RDM_CODE_ARR = -64'sd6006;
    localparam signed [63:0] C24_W_RDM_CODE_AFF = 64'sd14999;

    localparam signed [63:0] C24_W_ECT_PAIR_NSR = 64'sd603057;
    localparam signed [63:0] C24_W_ECT_PAIR_CHF = -64'sd120529;
    localparam signed [63:0] C24_W_ECT_PAIR_ARR = 64'sd1209186;
    localparam signed [63:0] C24_W_ECT_PAIR_AFF = -64'sd1471862;

    localparam signed [63:0] C24_W_PRE_QRS_NSR = -64'sd69606;
    localparam signed [63:0] C24_W_PRE_QRS_CHF = 64'sd92815;
    localparam signed [63:0] C24_W_PRE_QRS_ARR = -64'sd102850;
    localparam signed [63:0] C24_W_PRE_QRS_AFF = 64'sd130442;

    localparam signed [63:0] C24_W_QRS_MAF_NSR = 64'sd65915;
    localparam signed [63:0] C24_W_QRS_MAF_CHF = 64'sd218075;
    localparam signed [63:0] C24_W_QRS_MAF_ARR = -64'sd187860;
    localparam signed [63:0] C24_W_QRS_MAF_AFF = -64'sd43844;

    localparam signed [63:0] C24_W_QRS_WIDTH_NSR = -64'sd228392;
    localparam signed [63:0] C24_W_QRS_WIDTH_CHF = -64'sd1011419;
    localparam signed [63:0] C24_W_QRS_WIDTH_ARR = 64'sd336720;
    localparam signed [63:0] C24_W_QRS_WIDTH_AFF = 64'sd648989;

    localparam signed [63:0] C24_W_QRS_COMPLEX_NSR = -64'sd417100;
    localparam signed [63:0] C24_W_QRS_COMPLEX_CHF = -64'sd36700;
    localparam signed [63:0] C24_W_QRS_COMPLEX_ARR = -64'sd865800;
    localparam signed [63:0] C24_W_QRS_COMPLEX_AFF = 64'sd1134300;

    localparam signed [63:0] C24_W_QRS_ENERGY_NSR = -64'sd53225;
    localparam signed [63:0] C24_W_QRS_ENERGY_CHF = 64'sd1049071;
    localparam signed [63:0] C24_W_QRS_ENERGY_ARR = -64'sd84317;
    localparam signed [63:0] C24_W_QRS_ENERGY_AFF = -64'sd756818;

    localparam signed [63:0] C24_W_SECOND_NSR = 64'sd592274;
    localparam signed [63:0] C24_W_SECOND_CHF = 64'sd32327;
    localparam signed [63:0] C24_W_SECOND_ARR = 64'sd464933;
    localparam signed [63:0] C24_W_SECOND_AFF = -64'sd905174;

    localparam signed [63:0] C24_W_RBBB_LIKE_NSR = 64'sd27245;
    localparam signed [63:0] C24_W_RBBB_LIKE_CHF = -64'sd7071;
    localparam signed [63:0] C24_W_RBBB_LIKE_ARR = -64'sd72779;
    localparam signed [63:0] C24_W_RBBB_LIKE_AFF = 64'sd55922;

    localparam signed [63:0] C24_W_RBBB_SEGMENT_NSR = -64'sd8159206;
    localparam signed [63:0] C24_W_RBBB_SEGMENT_CHF = 64'sd10226055;
    localparam signed [63:0] C24_W_RBBB_SEGMENT_ARR = -64'sd7024184;
    localparam signed [63:0] C24_W_RBBB_SEGMENT_AFF = 64'sd5387377;

    localparam signed [63:0] C24_W_RBBB_APPLIED_NSR = -64'sd15531494;
    localparam signed [63:0] C24_W_RBBB_APPLIED_CHF = -64'sd31830900;
    localparam signed [63:0] C24_W_RBBB_APPLIED_ARR = 64'sd39520507;
    localparam signed [63:0] C24_W_RBBB_APPLIED_AFF = 64'sd5329691;

    localparam signed [63:0] C24_W_RBBB_LATE_APPLIED_NSR = -64'sd17700000;
    localparam signed [63:0] C24_W_RBBB_LATE_APPLIED_CHF = -64'sd45450000;
    localparam signed [63:0] C24_W_RBBB_LATE_APPLIED_ARR = 64'sd51150000;
    localparam signed [63:0] C24_W_RBBB_LATE_APPLIED_AFF = 64'sd6600000;

    localparam signed [63:0] C24_W_EERG_GATE_NSR = 64'sd5042413;
    localparam signed [63:0] C24_W_EERG_GATE_CHF = 64'sd1853587;
    localparam signed [63:0] C24_W_EERG_GATE_ARR = -64'sd6346411;
    localparam signed [63:0] C24_W_EERG_GATE_AFF = -64'sd825955;

    localparam signed [63:0] C24_W_EERG_APPLIED_NSR = 64'sd4717413;
    localparam signed [63:0] C24_W_EERG_APPLIED_CHF = -64'sd4196413;
    localparam signed [63:0] C24_W_EERG_APPLIED_ARR = 64'sd2653589;
    localparam signed [63:0] C24_W_EERG_APPLIED_AFF = -64'sd1775955;

    localparam signed [63:0] C24_W_ARR_HIGH_IRR_NSR = -64'sd520000;
    localparam signed [63:0] C24_W_ARR_HIGH_IRR_CHF = -64'sd9680000;
    localparam signed [63:0] C24_W_ARR_HIGH_IRR_ARR = 64'sd14400000;
    localparam signed [63:0] C24_W_ARR_HIGH_IRR_AFF = -64'sd1520000;

    localparam signed [63:0] C24_W_ETMC_NSR = 64'sd0;
    localparam signed [63:0] C24_W_ETMC_CHF = 64'sd0;
    localparam signed [63:0] C24_W_ETMC_ARR = 64'sd0;
    localparam signed [63:0] C24_W_ETMC_AFF = 64'sd0;

    localparam signed [63:0] C24_W_RCD_NSR = 64'sd0;
    localparam signed [63:0] C24_W_RCD_CHF = 64'sd0;
    localparam signed [63:0] C24_W_RCD_ARR = 64'sd0;
    localparam signed [63:0] C24_W_RCD_AFF = 64'sd0;

    localparam signed [63:0] C24_W_RCD2_NSR = 64'sd0;
    localparam signed [63:0] C24_W_RCD2_CHF = 64'sd0;
    localparam signed [63:0] C24_W_RCD2_ARR = 64'sd0;
    localparam signed [63:0] C24_W_RCD2_AFF = 64'sd0;

    localparam signed [63:0] C24_W_IPB_PERSIST_NSR = 64'sd0;
    localparam signed [63:0] C24_W_IPB_PERSIST_CHF = 64'sd0;
    localparam signed [63:0] C24_W_IPB_PERSIST_ARR = 64'sd0;
    localparam signed [63:0] C24_W_IPB_PERSIST_AFF = 64'sd0;

    localparam signed [63:0] C24_W_IPB_EPISODIC_NSR = 64'sd0;
    localparam signed [63:0] C24_W_IPB_EPISODIC_CHF = 64'sd0;
    localparam signed [63:0] C24_W_IPB_EPISODIC_ARR = 64'sd0;
    localparam signed [63:0] C24_W_IPB_EPISODIC_AFF = 64'sd0;

    localparam signed [63:0] C24_W_IPB_BURST_NSR = 64'sd0;
    localparam signed [63:0] C24_W_IPB_BURST_CHF = 64'sd0;
    localparam signed [63:0] C24_W_IPB_BURST_ARR = 64'sd0;
    localparam signed [63:0] C24_W_IPB_BURST_AFF = 64'sd0;

    localparam signed [63:0] C24_W_PNN_MIS_GE_3_NSR = -64'sd790811;
    localparam signed [63:0] C24_W_PNN_MIS_GE_3_CHF = 64'sd807261;
    localparam signed [63:0] C24_W_PNN_MIS_GE_3_ARR = 64'sd381108;
    localparam signed [63:0] C24_W_PNN_MIS_GE_3_AFF = -64'sd151676;

    localparam signed [63:0] C24_W_PNN_MIS_GE_8_NSR = -64'sd1909429;
    localparam signed [63:0] C24_W_PNN_MIS_GE_8_CHF = -64'sd3626195;
    localparam signed [63:0] C24_W_PNN_MIS_GE_8_ARR = 64'sd5102747;
    localparam signed [63:0] C24_W_PNN_MIS_GE_8_AFF = 64'sd875371;

    localparam signed [63:0] C24_W_PNN_MIS_GE_15_NSR = -64'sd3139875;
    localparam signed [63:0] C24_W_PNN_MIS_GE_15_CHF = -64'sd2783740;
    localparam signed [63:0] C24_W_PNN_MIS_GE_15_ARR = 64'sd4029184;
    localparam signed [63:0] C24_W_PNN_MIS_GE_15_AFF = 64'sd2182200;

    localparam signed [63:0] C24_W_PNN_MIS_GE_25_NSR = -64'sd2009514;
    localparam signed [63:0] C24_W_PNN_MIS_GE_25_CHF = -64'sd3409796;
    localparam signed [63:0] C24_W_PNN_MIS_GE_25_ARR = 64'sd2038706;
    localparam signed [63:0] C24_W_PNN_MIS_GE_25_AFF = 64'sd3905756;

    localparam signed [63:0] C24_W_PNN_MIS_GE_45_NSR = 64'sd3895045;
    localparam signed [63:0] C24_W_PNN_MIS_GE_45_CHF = -64'sd906783;
    localparam signed [63:0] C24_W_PNN_MIS_GE_45_ARR = -64'sd10346539;
    localparam signed [63:0] C24_W_PNN_MIS_GE_45_AFF = 64'sd8375393;

    localparam signed [63:0] C24_W_PNN_MIS_LE_3_NSR = 64'sd642779;
    localparam signed [63:0] C24_W_PNN_MIS_LE_3_CHF = -64'sd524082;
    localparam signed [63:0] C24_W_PNN_MIS_LE_3_ARR = -64'sd383892;
    localparam signed [63:0] C24_W_PNN_MIS_LE_3_AFF = 64'sd16133;

    localparam signed [63:0] C24_W_PNN_MIS_LE_8_NSR = 64'sd1909429;
    localparam signed [63:0] C24_W_PNN_MIS_LE_8_CHF = 64'sd3626195;
    localparam signed [63:0] C24_W_PNN_MIS_LE_8_ARR = -64'sd5102747;
    localparam signed [63:0] C24_W_PNN_MIS_LE_8_AFF = -64'sd875371;

    localparam signed [63:0] C24_W_PNN_MIS_LE_15_NSR = 64'sd3551864;
    localparam signed [63:0] C24_W_PNN_MIS_LE_15_CHF = 64'sd2239988;
    localparam signed [63:0] C24_W_PNN_MIS_LE_15_ARR = -64'sd3787723;
    localparam signed [63:0] C24_W_PNN_MIS_LE_15_AFF = -64'sd2312037;

    localparam signed [63:0] C24_W_RDM_AVG_GE_2_NSR = -64'sd1138068;
    localparam signed [63:0] C24_W_RDM_AVG_GE_2_CHF = -64'sd1999784;
    localparam signed [63:0] C24_W_RDM_AVG_GE_2_ARR = 64'sd2074350;
    localparam signed [63:0] C24_W_RDM_AVG_GE_2_AFF = 64'sd951359;

    localparam signed [63:0] C24_W_RDM_AVG_GE_4_NSR = -64'sd1773313;
    localparam signed [63:0] C24_W_RDM_AVG_GE_4_CHF = -64'sd1369505;
    localparam signed [63:0] C24_W_RDM_AVG_GE_4_ARR = 64'sd2446679;
    localparam signed [63:0] C24_W_RDM_AVG_GE_4_AFF = 64'sd753304;

    localparam signed [63:0] C24_W_RDM_AVG_GE_6_NSR = -64'sd739319;
    localparam signed [63:0] C24_W_RDM_AVG_GE_6_CHF = -64'sd3722618;
    localparam signed [63:0] C24_W_RDM_AVG_GE_6_ARR = 64'sd171391;
    localparam signed [63:0] C24_W_RDM_AVG_GE_6_AFF = 64'sd4818082;

    localparam signed [63:0] C24_W_RDM_AVG_GE_9_NSR = 64'sd3873191;
    localparam signed [63:0] C24_W_RDM_AVG_GE_9_CHF = -64'sd805932;
    localparam signed [63:0] C24_W_RDM_AVG_GE_9_ARR = -64'sd12685639;
    localparam signed [63:0] C24_W_RDM_AVG_GE_9_AFF = 64'sd10787411;

    localparam signed [63:0] C24_W_RDM_AVG_GE_12_NSR = 64'sd17821496;
    localparam signed [63:0] C24_W_RDM_AVG_GE_12_CHF = -64'sd6457274;
    localparam signed [63:0] C24_W_RDM_AVG_GE_12_ARR = 64'sd22964771;
    localparam signed [63:0] C24_W_RDM_AVG_GE_12_AFF = -64'sd33852587;

    localparam signed [63:0] C24_W_RDM_AVG_LE_2_NSR = 64'sd1474350;
    localparam signed [63:0] C24_W_RDM_AVG_LE_2_CHF = 64'sd1182275;
    localparam signed [63:0] C24_W_RDM_AVG_LE_2_ARR = -64'sd1861134;
    localparam signed [63:0] C24_W_RDM_AVG_LE_2_AFF = -64'sd682284;

    localparam signed [63:0] C24_W_RDM_AVG_LE_4_NSR = 64'sd1693509;
    localparam signed [63:0] C24_W_RDM_AVG_LE_4_CHF = 64'sd1801416;
    localparam signed [63:0] C24_W_RDM_AVG_LE_4_ARR = -64'sd2708494;
    localparam signed [63:0] C24_W_RDM_AVG_LE_4_AFF = -64'sd851542;

    localparam signed [63:0] C24_W_RDM_AVG_LE_6_NSR = 64'sd739319;
    localparam signed [63:0] C24_W_RDM_AVG_LE_6_CHF = 64'sd3722618;
    localparam signed [63:0] C24_W_RDM_AVG_LE_6_ARR = -64'sd171391;
    localparam signed [63:0] C24_W_RDM_AVG_LE_6_AFF = -64'sd4818082;

    localparam signed [63:0] C24_W_RDM_GE20_GE_3_NSR = 64'sd1583412;
    localparam signed [63:0] C24_W_RDM_GE20_GE_3_CHF = 64'sd4570836;
    localparam signed [63:0] C24_W_RDM_GE20_GE_3_ARR = -64'sd7399425;
    localparam signed [63:0] C24_W_RDM_GE20_GE_3_AFF = 64'sd1837717;

    localparam signed [63:0] C24_W_RDM_GE20_GE_8_NSR = 64'sd3636360;
    localparam signed [63:0] C24_W_RDM_GE20_GE_8_CHF = 64'sd5247742;
    localparam signed [63:0] C24_W_RDM_GE20_GE_8_ARR = -64'sd9841306;
    localparam signed [63:0] C24_W_RDM_GE20_GE_8_AFF = 64'sd1983527;

    localparam signed [63:0] C24_W_RDM_GE20_GE_20_NSR = 64'sd6134562;
    localparam signed [63:0] C24_W_RDM_GE20_GE_20_CHF = -64'sd7603416;
    localparam signed [63:0] C24_W_RDM_GE20_GE_20_ARR = 64'sd2494965;
    localparam signed [63:0] C24_W_RDM_GE20_GE_20_AFF = -64'sd564353;

    localparam signed [63:0] C24_W_RDM_GE20_GE_40_NSR = 64'sd2207463;
    localparam signed [63:0] C24_W_RDM_GE20_GE_40_CHF = -64'sd11369729;
    localparam signed [63:0] C24_W_RDM_GE20_GE_40_ARR = 64'sd7977348;
    localparam signed [63:0] C24_W_RDM_GE20_GE_40_AFF = 64'sd1280495;

    localparam signed [63:0] C24_W_RDM_GE50_GE_3_NSR = -64'sd233770;
    localparam signed [63:0] C24_W_RDM_GE50_GE_3_CHF = -64'sd6876278;
    localparam signed [63:0] C24_W_RDM_GE50_GE_3_ARR = 64'sd8135018;
    localparam signed [63:0] C24_W_RDM_GE50_GE_3_AFF = -64'sd1070786;

    localparam signed [63:0] C24_W_RDM_GE50_GE_8_NSR = -64'sd79060;
    localparam signed [63:0] C24_W_RDM_GE50_GE_8_CHF = 64'sd1293825;
    localparam signed [63:0] C24_W_RDM_GE50_GE_8_ARR = -64'sd425988;
    localparam signed [63:0] C24_W_RDM_GE50_GE_8_AFF = -64'sd951994;

    localparam signed [63:0] C24_W_RDM_GE50_GE_20_NSR = 64'sd1865356;
    localparam signed [63:0] C24_W_RDM_GE50_GE_20_CHF = -64'sd260729;
    localparam signed [63:0] C24_W_RDM_GE50_GE_20_ARR = -64'sd3683480;
    localparam signed [63:0] C24_W_RDM_GE50_GE_20_AFF = 64'sd1870477;

    localparam signed [63:0] C24_W_RDM_GE50_GE_40_NSR = -64'sd163850;
    localparam signed [63:0] C24_W_RDM_GE50_GE_40_CHF = -64'sd384026;
    localparam signed [63:0] C24_W_RDM_GE50_GE_40_ARR = -64'sd1768562;
    localparam signed [63:0] C24_W_RDM_GE50_GE_40_AFF = 64'sd2368639;

    localparam signed [63:0] C24_W_RDM_GE80_GE_3_NSR = -64'sd6109919;
    localparam signed [63:0] C24_W_RDM_GE80_GE_3_CHF = 64'sd6668979;
    localparam signed [63:0] C24_W_RDM_GE80_GE_3_ARR = 64'sd10851;
    localparam signed [63:0] C24_W_RDM_GE80_GE_3_AFF = -64'sd603767;

    localparam signed [63:0] C24_W_RDM_GE80_GE_8_NSR = -64'sd2860740;
    localparam signed [63:0] C24_W_RDM_GE80_GE_8_CHF = 64'sd772276;
    localparam signed [63:0] C24_W_RDM_GE80_GE_8_ARR = 64'sd2323768;
    localparam signed [63:0] C24_W_RDM_GE80_GE_8_AFF = -64'sd260977;

    localparam signed [63:0] C24_W_RDM_GE80_GE_20_NSR = -64'sd3408769;
    localparam signed [63:0] C24_W_RDM_GE80_GE_20_CHF = -64'sd1025998;
    localparam signed [63:0] C24_W_RDM_GE80_GE_20_ARR = 64'sd3294222;
    localparam signed [63:0] C24_W_RDM_GE80_GE_20_AFF = 64'sd1219820;

    localparam signed [63:0] C24_W_RDM_GE80_GE_40_NSR = 64'sd411274;
    localparam signed [63:0] C24_W_RDM_GE80_GE_40_CHF = -64'sd3968257;
    localparam signed [63:0] C24_W_RDM_GE80_GE_40_ARR = -64'sd2092653;
    localparam signed [63:0] C24_W_RDM_GE80_GE_40_AFF = 64'sd6334251;

    localparam signed [63:0] C24_W_RDM_GE100_GE_3_NSR = -64'sd3203544;
    localparam signed [63:0] C24_W_RDM_GE100_GE_3_CHF = 64'sd662011;
    localparam signed [63:0] C24_W_RDM_GE100_GE_3_ARR = 64'sd3166627;
    localparam signed [63:0] C24_W_RDM_GE100_GE_3_AFF = -64'sd527685;

    localparam signed [63:0] C24_W_RDM_GE100_GE_8_NSR = 64'sd187254;
    localparam signed [63:0] C24_W_RDM_GE100_GE_8_CHF = -64'sd3813158;
    localparam signed [63:0] C24_W_RDM_GE100_GE_8_ARR = 64'sd3634564;
    localparam signed [63:0] C24_W_RDM_GE100_GE_8_AFF = 64'sd267977;

    localparam signed [63:0] C24_W_RDM_GE100_GE_20_NSR = -64'sd2021388;
    localparam signed [63:0] C24_W_RDM_GE100_GE_20_CHF = -64'sd1193078;
    localparam signed [63:0] C24_W_RDM_GE100_GE_20_ARR = 64'sd1343843;
    localparam signed [63:0] C24_W_RDM_GE100_GE_20_AFF = 64'sd2129923;

    localparam signed [63:0] C24_W_RDM_GE100_GE_40_NSR = 64'sd995257;
    localparam signed [63:0] C24_W_RDM_GE100_GE_40_CHF = -64'sd3283556;
    localparam signed [63:0] C24_W_RDM_GE100_GE_40_ARR = -64'sd3484174;
    localparam signed [63:0] C24_W_RDM_GE100_GE_40_AFF = 64'sd6471489;

    localparam signed [63:0] C24_W_DSCR_GE_1_NSR = 64'sd7523915;
    localparam signed [63:0] C24_W_DSCR_GE_1_CHF = -64'sd5081937;
    localparam signed [63:0] C24_W_DSCR_GE_1_ARR = -64'sd1504896;
    localparam signed [63:0] C24_W_DSCR_GE_1_AFF = -64'sd294870;

    localparam signed [63:0] C24_W_DSCR_GE_3_NSR = 64'sd4309661;
    localparam signed [63:0] C24_W_DSCR_GE_3_CHF = -64'sd3117028;
    localparam signed [63:0] C24_W_DSCR_GE_3_ARR = -64'sd3503348;
    localparam signed [63:0] C24_W_DSCR_GE_3_AFF = 64'sd2270005;

    localparam signed [63:0] C24_W_DSCR_GE_5_NSR = 64'sd4671106;
    localparam signed [63:0] C24_W_DSCR_GE_5_CHF = -64'sd4435657;
    localparam signed [63:0] C24_W_DSCR_GE_5_ARR = -64'sd6071606;
    localparam signed [63:0] C24_W_DSCR_GE_5_AFF = 64'sd5925118;

    localparam signed [63:0] C24_W_DSCR_GE_8_NSR = 64'sd15618943;
    localparam signed [63:0] C24_W_DSCR_GE_8_CHF = -64'sd2547447;
    localparam signed [63:0] C24_W_DSCR_GE_8_ARR = -64'sd13985669;
    localparam signed [63:0] C24_W_DSCR_GE_8_AFF = 64'sd612188;

    localparam signed [63:0] C24_W_DSCR_GE_12_NSR = 64'sd20512118;
    localparam signed [63:0] C24_W_DSCR_GE_12_CHF = -64'sd7565392;
    localparam signed [63:0] C24_W_DSCR_GE_12_ARR = -64'sd7428226;
    localparam signed [63:0] C24_W_DSCR_GE_12_AFF = -64'sd6363294;

    localparam signed [63:0] C24_W_DSCR_LE_1_NSR = -64'sd7523915;
    localparam signed [63:0] C24_W_DSCR_LE_1_CHF = 64'sd5081937;
    localparam signed [63:0] C24_W_DSCR_LE_1_ARR = 64'sd1504896;
    localparam signed [63:0] C24_W_DSCR_LE_1_AFF = 64'sd294870;

    localparam signed [63:0] C24_W_DSCR_LE_3_NSR = -64'sd4309661;
    localparam signed [63:0] C24_W_DSCR_LE_3_CHF = 64'sd3117028;
    localparam signed [63:0] C24_W_DSCR_LE_3_ARR = 64'sd3503348;
    localparam signed [63:0] C24_W_DSCR_LE_3_AFF = -64'sd2270005;

    localparam signed [63:0] C24_W_DSCR_LE_5_NSR = -64'sd4671106;
    localparam signed [63:0] C24_W_DSCR_LE_5_CHF = 64'sd4435657;
    localparam signed [63:0] C24_W_DSCR_LE_5_ARR = 64'sd6071606;
    localparam signed [63:0] C24_W_DSCR_LE_5_AFF = -64'sd5925118;

    localparam signed [63:0] C24_W_RAM_GE_2_NSR = 64'sd1914317;
    localparam signed [63:0] C24_W_RAM_GE_2_CHF = 64'sd5407272;
    localparam signed [63:0] C24_W_RAM_GE_2_ARR = -64'sd2302702;
    localparam signed [63:0] C24_W_RAM_GE_2_AFF = -64'sd4753568;

    localparam signed [63:0] C24_W_RAM_GE_4_NSR = 64'sd4955518;
    localparam signed [63:0] C24_W_RAM_GE_4_CHF = -64'sd10057368;
    localparam signed [63:0] C24_W_RAM_GE_4_ARR = 64'sd6412196;
    localparam signed [63:0] C24_W_RAM_GE_4_AFF = -64'sd968218;

    localparam signed [63:0] C24_W_RAM_GE_6_NSR = 64'sd4703088;
    localparam signed [63:0] C24_W_RAM_GE_6_CHF = -64'sd8566451;
    localparam signed [63:0] C24_W_RAM_GE_6_ARR = 64'sd6228629;
    localparam signed [63:0] C24_W_RAM_GE_6_AFF = -64'sd2256748;

    localparam signed [63:0] C24_W_RAM_GE_10_NSR = -64'sd651136;
    localparam signed [63:0] C24_W_RAM_GE_10_CHF = -64'sd1779420;
    localparam signed [63:0] C24_W_RAM_GE_10_ARR = 64'sd2867117;
    localparam signed [63:0] C24_W_RAM_GE_10_AFF = -64'sd293013;

    localparam signed [63:0] C24_W_RAM_GE_14_NSR = 64'sd13787814;
    localparam signed [63:0] C24_W_RAM_GE_14_CHF = -64'sd5516574;
    localparam signed [63:0] C24_W_RAM_GE_14_ARR = -64'sd6557655;
    localparam signed [63:0] C24_W_RAM_GE_14_AFF = -64'sd1157027;

    localparam signed [63:0] C24_W_RAM_LE_2_NSR = -64'sd3288095;
    localparam signed [63:0] C24_W_RAM_LE_2_CHF = 64'sd1860918;
    localparam signed [63:0] C24_W_RAM_LE_2_ARR = -64'sd2440175;
    localparam signed [63:0] C24_W_RAM_LE_2_AFF = 64'sd3572228;

    localparam signed [63:0] C24_W_RAM_LE_4_NSR = -64'sd4955518;
    localparam signed [63:0] C24_W_RAM_LE_4_CHF = 64'sd10057368;
    localparam signed [63:0] C24_W_RAM_LE_4_ARR = -64'sd6412196;
    localparam signed [63:0] C24_W_RAM_LE_4_AFF = 64'sd968218;

    localparam signed [63:0] C24_W_RAM_LE_6_NSR = -64'sd5062482;
    localparam signed [63:0] C24_W_RAM_LE_6_CHF = 64'sd8232535;
    localparam signed [63:0] C24_W_RAM_LE_6_ARR = -64'sd5868479;
    localparam signed [63:0] C24_W_RAM_LE_6_AFF = 64'sd2601478;

    localparam signed [63:0] C24_W_ECP_GE_1_NSR = -64'sd2054340;
    localparam signed [63:0] C24_W_ECP_GE_1_CHF = 64'sd1669589;
    localparam signed [63:0] C24_W_ECP_GE_1_ARR = 64'sd1422932;
    localparam signed [63:0] C24_W_ECP_GE_1_AFF = -64'sd1010015;

    localparam signed [63:0] C24_W_ECP_GE_3_NSR = -64'sd1781484;
    localparam signed [63:0] C24_W_ECP_GE_3_CHF = -64'sd814326;
    localparam signed [63:0] C24_W_ECP_GE_3_ARR = 64'sd856840;
    localparam signed [63:0] C24_W_ECP_GE_3_AFF = 64'sd1902547;

    localparam signed [63:0] C24_W_ECP_GE_8_NSR = -64'sd3419957;
    localparam signed [63:0] C24_W_ECP_GE_8_CHF = -64'sd1585378;
    localparam signed [63:0] C24_W_ECP_GE_8_ARR = 64'sd4605697;
    localparam signed [63:0] C24_W_ECP_GE_8_AFF = 64'sd521574;

    localparam signed [63:0] C24_W_ECP_GE_15_NSR = -64'sd1183789;
    localparam signed [63:0] C24_W_ECP_GE_15_CHF = -64'sd2489580;
    localparam signed [63:0] C24_W_ECP_GE_15_ARR = 64'sd6587278;
    localparam signed [63:0] C24_W_ECP_GE_15_AFF = -64'sd2969758;

    localparam signed [63:0] C24_W_ECP_GE_25_NSR = 64'sd1403208;
    localparam signed [63:0] C24_W_ECP_GE_25_CHF = 64'sd471611;
    localparam signed [63:0] C24_W_ECP_GE_25_ARR = 64'sd7895206;
    localparam signed [63:0] C24_W_ECP_GE_25_AFF = -64'sd9946768;

    localparam signed [63:0] C24_W_PRE_GE_1_NSR = 64'sd0;
    localparam signed [63:0] C24_W_PRE_GE_1_CHF = 64'sd0;
    localparam signed [63:0] C24_W_PRE_GE_1_ARR = 64'sd0;
    localparam signed [63:0] C24_W_PRE_GE_1_AFF = 64'sd0;

    localparam signed [63:0] C24_W_PRE_GE_3_NSR = 64'sd0;
    localparam signed [63:0] C24_W_PRE_GE_3_CHF = 64'sd0;
    localparam signed [63:0] C24_W_PRE_GE_3_ARR = 64'sd0;
    localparam signed [63:0] C24_W_PRE_GE_3_AFF = 64'sd0;

    localparam signed [63:0] C24_W_PRE_GE_8_NSR = 64'sd0;
    localparam signed [63:0] C24_W_PRE_GE_8_CHF = 64'sd0;
    localparam signed [63:0] C24_W_PRE_GE_8_ARR = 64'sd0;
    localparam signed [63:0] C24_W_PRE_GE_8_AFF = 64'sd0;

    localparam signed [63:0] C24_W_QRS_GE_1_NSR = -64'sd106927;
    localparam signed [63:0] C24_W_QRS_GE_1_CHF = 64'sd3025589;
    localparam signed [63:0] C24_W_QRS_GE_1_ARR = 64'sd366225;
    localparam signed [63:0] C24_W_QRS_GE_1_AFF = -64'sd3254911;

    localparam signed [63:0] C24_W_QRS_GE_3_NSR = -64'sd334469;
    localparam signed [63:0] C24_W_QRS_GE_3_CHF = 64'sd3467691;
    localparam signed [63:0] C24_W_QRS_GE_3_ARR = -64'sd2274950;
    localparam signed [63:0] C24_W_QRS_GE_3_AFF = -64'sd644727;

    localparam signed [63:0] C24_W_QRS_GE_8_NSR = -64'sd1229563;
    localparam signed [63:0] C24_W_QRS_GE_8_CHF = 64'sd2868997;
    localparam signed [63:0] C24_W_QRS_GE_8_ARR = -64'sd1260173;
    localparam signed [63:0] C24_W_QRS_GE_8_AFF = -64'sd169438;

    localparam signed [63:0] C24_W_QRS_GE_20_NSR = 64'sd850144;
    localparam signed [63:0] C24_W_QRS_GE_20_CHF = -64'sd1365369;
    localparam signed [63:0] C24_W_QRS_GE_20_ARR = 64'sd10661505;
    localparam signed [63:0] C24_W_QRS_GE_20_AFF = -64'sd8892890;

    localparam signed [63:0] C24_W_QRS_GE_40_NSR = 64'sd4186070;
    localparam signed [63:0] C24_W_QRS_GE_40_CHF = -64'sd428065;
    localparam signed [63:0] C24_W_QRS_GE_40_ARR = -64'sd15437270;
    localparam signed [63:0] C24_W_QRS_GE_40_AFF = 64'sd13248892;

    localparam signed [63:0] C24_W_QRS_WIDTH_GE_1_NSR = -64'sd166307;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_1_CHF = 64'sd2769968;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_1_ARR = 64'sd361225;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_1_AFF = -64'sd2859774;

    localparam signed [63:0] C24_W_QRS_WIDTH_GE_3_NSR = -64'sd1072450;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_3_CHF = 64'sd4498715;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_3_ARR = -64'sd2017836;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_3_AFF = -64'sd1217475;

    localparam signed [63:0] C24_W_QRS_WIDTH_GE_8_NSR = -64'sd572815;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_8_CHF = 64'sd3756569;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_8_ARR = -64'sd2113731;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_8_AFF = -64'sd601415;

    localparam signed [63:0] C24_W_QRS_WIDTH_GE_15_NSR = 64'sd6052939;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_15_CHF = 64'sd46369;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_15_ARR = 64'sd2248041;
    localparam signed [63:0] C24_W_QRS_WIDTH_GE_15_AFF = -64'sd7532159;

    localparam signed [63:0] C24_W_QRS_ENERGY_GE_1_NSR = -64'sd3013100;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_1_CHF = 64'sd5772542;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_1_ARR = -64'sd1004102;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_1_AFF = -64'sd1656860;

    localparam signed [63:0] C24_W_QRS_ENERGY_GE_3_NSR = -64'sd921969;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_3_CHF = -64'sd1209476;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_3_ARR = 64'sd3340883;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_3_AFF = -64'sd1063043;

    localparam signed [63:0] C24_W_QRS_ENERGY_GE_8_NSR = -64'sd955613;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_8_CHF = 64'sd8658196;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_8_ARR = -64'sd15312729;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_8_AFF = 64'sd9059022;

    localparam signed [63:0] C24_W_QRS_ENERGY_GE_20_NSR = -64'sd6589261;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_20_CHF = 64'sd1122114;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_20_ARR = -64'sd7642060;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_20_AFF = 64'sd13384245;

    localparam signed [63:0] C24_W_QRS_ENERGY_GE_40_NSR = 64'sd0;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_40_CHF = 64'sd0;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_40_ARR = 64'sd0;
    localparam signed [63:0] C24_W_QRS_ENERGY_GE_40_AFF = 64'sd0;

    localparam signed [63:0] C24_W_RBBB_GE_1_NSR = -64'sd665456;
    localparam signed [63:0] C24_W_RBBB_GE_1_CHF = 64'sd5866010;
    localparam signed [63:0] C24_W_RBBB_GE_1_ARR = -64'sd2129742;
    localparam signed [63:0] C24_W_RBBB_GE_1_AFF = -64'sd2888328;

    localparam signed [63:0] C24_W_RBBB_GE_3_NSR = 64'sd1898500;
    localparam signed [63:0] C24_W_RBBB_GE_3_CHF = 64'sd2727209;
    localparam signed [63:0] C24_W_RBBB_GE_3_ARR = -64'sd86332;
    localparam signed [63:0] C24_W_RBBB_GE_3_AFF = -64'sd4174360;

    localparam signed [63:0] C24_W_RBBB_GE_8_NSR = 64'sd86222;
    localparam signed [63:0] C24_W_RBBB_GE_8_CHF = 64'sd757786;
    localparam signed [63:0] C24_W_RBBB_GE_8_ARR = 64'sd719562;
    localparam signed [63:0] C24_W_RBBB_GE_8_AFF = -64'sd836404;

    localparam signed [63:0] C24_W_RBBB_GE_15_NSR = 64'sd385280;
    localparam signed [63:0] C24_W_RBBB_GE_15_CHF = 64'sd3221580;
    localparam signed [63:0] C24_W_RBBB_GE_15_ARR = -64'sd3191188;
    localparam signed [63:0] C24_W_RBBB_GE_15_AFF = 64'sd550022;

    localparam signed [63:0] C24_W_RBBB_WIDE_GE_1_NSR = -64'sd1646203;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_1_CHF = 64'sd5614792;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_1_ARR = -64'sd995067;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_1_AFF = -64'sd2822779;

    localparam signed [63:0] C24_W_RBBB_WIDE_GE_3_NSR = 64'sd222698;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_3_CHF = 64'sd3046855;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_3_ARR = 64'sd359917;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_3_AFF = -64'sd3219894;

    localparam signed [63:0] C24_W_RBBB_WIDE_GE_8_NSR = 64'sd444657;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_8_CHF = 64'sd3003338;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_8_ARR = -64'sd2138662;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_8_AFF = -64'sd624133;

    localparam signed [63:0] C24_W_RBBB_WIDE_GE_15_NSR = 64'sd279176;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_15_CHF = -64'sd4374765;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_15_ARR = 64'sd1099766;
    localparam signed [63:0] C24_W_RBBB_WIDE_GE_15_AFF = 64'sd3709549;

    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_1_NSR = -64'sd11282875;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_1_CHF = 64'sd4984161;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_1_ARR = 64'sd9595521;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_1_AFF = -64'sd3482804;

    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_3_NSR = -64'sd10120487;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_3_CHF = -64'sd942925;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_3_ARR = 64'sd14836650;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_3_AFF = -64'sd3938466;

    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_8_NSR = -64'sd11739024;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_8_CHF = 64'sd3560599;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_8_ARR = 64'sd10024850;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_8_AFF = -64'sd1992124;

    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_15_NSR = -64'sd12229985;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_15_CHF = 64'sd2153592;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_15_ARR = 64'sd8212529;
    localparam signed [63:0] C24_W_RBBB_TERMINAL_GE_15_AFF = 64'sd1685319;

    localparam signed [63:0] C24_W_GATE_REGULAR_RBBB_RESCUE_NSR = -64'sd9323560;
    localparam signed [63:0] C24_W_GATE_REGULAR_RBBB_RESCUE_CHF = 64'sd10489159;
    localparam signed [63:0] C24_W_GATE_REGULAR_RBBB_RESCUE_ARR = -64'sd6812886;
    localparam signed [63:0] C24_W_GATE_REGULAR_RBBB_RESCUE_AFF = 64'sd5868140;

    localparam signed [63:0] C24_W_GATE_REGULAR_QRS_ARR_RESCUE_NSR = -64'sd3564439;
    localparam signed [63:0] C24_W_GATE_REGULAR_QRS_ARR_RESCUE_CHF = 64'sd5017357;
    localparam signed [63:0] C24_W_GATE_REGULAR_QRS_ARR_RESCUE_ARR = -64'sd2255461;
    localparam signed [63:0] C24_W_GATE_REGULAR_QRS_ARR_RESCUE_AFF = 64'sd981382;

    localparam signed [63:0] C24_W_GATE_EPISODIC_ECTOPIC_ARR_NSR = -64'sd3702587;
    localparam signed [63:0] C24_W_GATE_EPISODIC_ECTOPIC_ARR_CHF = 64'sd3029564;
    localparam signed [63:0] C24_W_GATE_EPISODIC_ECTOPIC_ARR_ARR = 64'sd1282935;
    localparam signed [63:0] C24_W_GATE_EPISODIC_ECTOPIC_ARR_AFF = -64'sd1075221;

    localparam signed [63:0] C24_W_GATE_EERG_LIKE_NSR = 64'sd5042413;
    localparam signed [63:0] C24_W_GATE_EERG_LIKE_CHF = 64'sd1853587;
    localparam signed [63:0] C24_W_GATE_EERG_LIKE_ARR = -64'sd6346411;
    localparam signed [63:0] C24_W_GATE_EERG_LIKE_AFF = -64'sd825955;

    localparam signed [63:0] C24_W_GATE_AFF_PERSISTENT_IRREG_NSR = -64'sd217384;
    localparam signed [63:0] C24_W_GATE_AFF_PERSISTENT_IRREG_CHF = -64'sd3743518;
    localparam signed [63:0] C24_W_GATE_AFF_PERSISTENT_IRREG_ARR = -64'sd2278623;
    localparam signed [63:0] C24_W_GATE_AFF_PERSISTENT_IRREG_AFF = 64'sd6831438;

    localparam signed [63:0] C24_W_GATE_ARR_MID_IRREG_NSR = 64'sd1144922;
    localparam signed [63:0] C24_W_GATE_ARR_MID_IRREG_CHF = -64'sd1458145;
    localparam signed [63:0] C24_W_GATE_ARR_MID_IRREG_ARR = 64'sd4422487;
    localparam signed [63:0] C24_W_GATE_ARR_MID_IRREG_AFF = -64'sd4287835;

    localparam signed [63:0] C24_W_GATE_CHF_LOW_DSCR_LOW_IRREG_NSR = -64'sd7007057;
    localparam signed [63:0] C24_W_GATE_CHF_LOW_DSCR_LOW_IRREG_CHF = 64'sd13252201;
    localparam signed [63:0] C24_W_GATE_CHF_LOW_DSCR_LOW_IRREG_ARR = -64'sd5649598;
    localparam signed [63:0] C24_W_GATE_CHF_LOW_DSCR_LOW_IRREG_AFF = -64'sd519888;

    localparam signed [63:0] C24_W_GATE_NSR_HIGH_DSCR_LOW_IRREG_NSR = 64'sd11033396;
    localparam signed [63:0] C24_W_GATE_NSR_HIGH_DSCR_LOW_IRREG_CHF = -64'sd12613555;
    localparam signed [63:0] C24_W_GATE_NSR_HIGH_DSCR_LOW_IRREG_ARR = 64'sd9003961;
    localparam signed [63:0] C24_W_GATE_NSR_HIGH_DSCR_LOW_IRREG_AFF = -64'sd7756620;

    localparam signed [63:0] C24_W_GATE_RAM_HIGH_REGULAR_NSR = 64'sd229914;
    localparam signed [63:0] C24_W_GATE_RAM_HIGH_REGULAR_CHF = -64'sd3915861;
    localparam signed [63:0] C24_W_GATE_RAM_HIGH_REGULAR_ARR = 64'sd3161124;
    localparam signed [63:0] C24_W_GATE_RAM_HIGH_REGULAR_AFF = 64'sd657840;

    localparam signed [63:0] C24_W_GATE_RAM_LOW_IRREGULAR_NSR = 64'sd7206883;
    localparam signed [63:0] C24_W_GATE_RAM_LOW_IRREGULAR_CHF = -64'sd5883813;
    localparam signed [63:0] C24_W_GATE_RAM_LOW_IRREGULAR_ARR = -64'sd12129080;
    localparam signed [63:0] C24_W_GATE_RAM_LOW_IRREGULAR_AFF = 64'sd11253358;



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

    reg signed [63:0] c24_mem_nsr_next;

    reg signed [63:0] c24_mem_chf_next;

    reg signed [63:0] c24_mem_arr_next;

    reg signed [63:0] c24_mem_aff_next;

    reg signed [63:0] c24_best_score;

    reg [1:0] c24_best_class;

    reg [9:0] ms_count;

    reg [16:0] subwindow_tick_count;

    reg [4:0] window_scale_q4;

    reg [4:0] rdm_code_calc;

    reg [15:0] beat_seg_count;

    reg [15:0] beat_seg_count_next;

    reg [15:0] dscr_flip_seg_count;

    reg [15:0] dscr_flip_seg_count_next;

    reg [15:0] dscr_slope_seg_count;

    reg [15:0] dscr_slope_seg_count_next;

    reg [15:0] ram_seg_count;

    reg [15:0] ram_seg_count_next;

    reg [21:0] ram_code_seg_sum;

    reg [21:0] ram_code_seg_sum_next;

    reg [15:0] rdm_ge20_seg_count;

    reg [15:0] rdm_ge20_seg_count_next;

    reg [15:0] rdm_ge50_seg_count;

    reg [15:0] rdm_ge50_seg_count_next;

    reg [15:0] rdm_ge80_seg_count;

    reg [15:0] rdm_ge80_seg_count_next;

    reg [15:0] rdm_ge100_seg_count;

    reg [15:0] rdm_ge100_seg_count_next;

    reg [15:0] qrs_maf_valid_seg_count;

    reg [15:0] qrs_maf_valid_seg_count_next;

    reg [15:0] qrs_maf_seg_count;

    reg [15:0] qrs_maf_seg_count_next;

    reg [15:0] qrs_width_abn_seg_count;

    reg [15:0] qrs_width_abn_seg_count_next;

    reg [15:0] qrs_energy_abn_seg_count;

    reg [15:0] qrs_energy_abn_seg_count_next;

    reg [15:0] rbbb_valid_seg_count;

    reg [15:0] rbbb_valid_seg_count_next;

    reg [15:0] rbbb_wide_seg_count;

    reg [15:0] rbbb_wide_seg_count_next;

    reg [15:0] rbbb_terminal_seg_count;

    reg [15:0] rbbb_terminal_seg_count_next;

    reg [15:0] rbbb_like_seg_count;

    reg [15:0] rbbb_like_seg_count_next;

    reg [15:0] rbbb_segment_seg_count;

    reg [15:0] rbbb_segment_seg_count_next;

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



    function [63:0] c24_u32_x100;
        input [31:0] value;
        begin
            c24_u32_x100 = ({32'd0, value} << 6) + ({32'd0, value} << 5) + ({32'd0, value} << 2);
        end
    endfunction

    function [63:0] c24_u32_mul_th;
        input [31:0] value;
        input [31:0] th;
        begin
            case (th)
                32'd1:  c24_u32_mul_th = {32'd0, value};
                32'd2:  c24_u32_mul_th = {32'd0, value} << 1;
                32'd3:  c24_u32_mul_th = ({32'd0, value} << 1) + {32'd0, value};
                32'd4:  c24_u32_mul_th = {32'd0, value} << 2;
                32'd5:  c24_u32_mul_th = ({32'd0, value} << 2) + {32'd0, value};
                32'd6:  c24_u32_mul_th = ({32'd0, value} << 2) + ({32'd0, value} << 1);
                32'd7:  c24_u32_mul_th = ({32'd0, value} << 2) + ({32'd0, value} << 1) + {32'd0, value};
                32'd8:  c24_u32_mul_th = {32'd0, value} << 3;
                32'd9:  c24_u32_mul_th = ({32'd0, value} << 3) + {32'd0, value};
                32'd10: c24_u32_mul_th = ({32'd0, value} << 3) + ({32'd0, value} << 1);
                32'd12: c24_u32_mul_th = ({32'd0, value} << 3) + ({32'd0, value} << 2);
                32'd14: c24_u32_mul_th = ({32'd0, value} << 3) + ({32'd0, value} << 2) + ({32'd0, value} << 1);
                32'd15: c24_u32_mul_th = ({32'd0, value} << 3) + ({32'd0, value} << 2) + ({32'd0, value} << 1) + {32'd0, value};
                32'd20: c24_u32_mul_th = ({32'd0, value} << 4) + ({32'd0, value} << 2);
                32'd25: c24_u32_mul_th = ({32'd0, value} << 4) + ({32'd0, value} << 3) + {32'd0, value};
                32'd30: c24_u32_mul_th = ({32'd0, value} << 4) + ({32'd0, value} << 3) + ({32'd0, value} << 2) + ({32'd0, value} << 1);
                32'd35: c24_u32_mul_th = ({32'd0, value} << 5) + ({32'd0, value} << 1) + {32'd0, value};
                32'd40: c24_u32_mul_th = ({32'd0, value} << 5) + ({32'd0, value} << 3);
                32'd45: c24_u32_mul_th = ({32'd0, value} << 5) + ({32'd0, value} << 3) + ({32'd0, value} << 2) + {32'd0, value};
                default: c24_u32_mul_th = 64'd0;
            endcase
        end
    endfunction

    function c24_ge_pct;
        input [31:0] num;
        input [31:0] den;
        input [31:0] th;
        begin
            c24_ge_pct = (den != 32'd0) && (c24_u32_x100(num) >= c24_u32_mul_th(den, th));
        end
    endfunction

    function c24_le_pct;
        input [31:0] num;
        input [31:0] den;
        input [31:0] th;
        begin
            c24_le_pct = (den == 32'd0) || (c24_u32_x100(num) <= c24_u32_mul_th(den, th));
        end
    endfunction

    function c24_ge_avg;
        input [31:0] sum;
        input [31:0] den;
        input [31:0] th;
        begin
            c24_ge_avg = (den != 32'd0) && ({32'd0, sum} >= c24_u32_mul_th(den, th));
        end
    endfunction

    function c24_le_avg;
        input [31:0] sum;
        input [31:0] den;
        input [31:0] th;
        begin
            c24_le_avg = (den == 32'd0) || ({32'd0, sum} <= c24_u32_mul_th(den, th));
        end
    endfunction

    function signed [SCORE_WIDTH-1:0] score_mul_u6;
        input signed [SCORE_WIDTH-1:0] weight;
        input [5:0] value;
        reg signed [SCORE_WIDTH-1:0] acc;
        begin
            acc = {SCORE_WIDTH{1'b0}};
            if (value[0]) acc = acc + weight;
            if (value[1]) acc = acc + (weight <<< 1);
            if (value[2]) acc = acc + (weight <<< 2);
            if (value[3]) acc = acc + (weight <<< 3);
            if (value[4]) acc = acc + (weight <<< 4);
            if (value[5]) acc = acc + (weight <<< 5);
            score_mul_u6 = acc;
        end
    endfunction

    function signed [63:0] c24_mul_u6;
        input signed [63:0] weight;
        input [5:0] value;
        reg signed [63:0] acc;
        begin
            acc = 64'sd0;
            if (value[0]) acc = acc + weight;
            if (value[1]) acc = acc + (weight <<< 1);
            if (value[2]) acc = acc + (weight <<< 2);
            if (value[3]) acc = acc + (weight <<< 3);
            if (value[4]) acc = acc + (weight <<< 4);
            if (value[5]) acc = acc + (weight <<< 5);
            c24_mul_u6 = acc;
        end
    endfunction

    function signed [63:0] c24_rdm_level_nsr;
        input integer idx;
        begin
            case (idx)
                0: c24_rdm_level_nsr = -64'sd279683;
                1: c24_rdm_level_nsr = 64'sd174791;
                2: c24_rdm_level_nsr = 64'sd352927;
                3: c24_rdm_level_nsr = -64'sd83114;
                4: c24_rdm_level_nsr = -64'sd63011;
                5: c24_rdm_level_nsr = 64'sd176035;
                6: c24_rdm_level_nsr = 64'sd159576;
                7: c24_rdm_level_nsr = -64'sd114336;
                8: c24_rdm_level_nsr = -64'sd168571;
                9: c24_rdm_level_nsr = -64'sd260903;
                10: c24_rdm_level_nsr = -64'sd219033;
                11: c24_rdm_level_nsr = -64'sd264959;
                12: c24_rdm_level_nsr = -64'sd264182;
                13: c24_rdm_level_nsr = -64'sd243853;
                14: c24_rdm_level_nsr = -64'sd306671;
                default: c24_rdm_level_nsr = 64'sd0;
            endcase
        end
    endfunction
    function signed [63:0] c24_rdm_level_chf;
        input integer idx;
        begin
            case (idx)
                0: c24_rdm_level_chf = -64'sd1899353;
                1: c24_rdm_level_chf = -64'sd437738;
                2: c24_rdm_level_chf = 64'sd658779;
                3: c24_rdm_level_chf = 64'sd233464;
                4: c24_rdm_level_chf = 64'sd71339;
                5: c24_rdm_level_chf = 64'sd397348;
                6: c24_rdm_level_chf = 64'sd215751;
                7: c24_rdm_level_chf = -64'sd102292;
                8: c24_rdm_level_chf = 64'sd164026;
                9: c24_rdm_level_chf = 64'sd369149;
                10: c24_rdm_level_chf = 64'sd11286;
                11: c24_rdm_level_chf = 64'sd272858;
                12: c24_rdm_level_chf = 64'sd121684;
                13: c24_rdm_level_chf = -64'sd211255;
                14: c24_rdm_level_chf = -64'sd1070699;
                default: c24_rdm_level_chf = 64'sd0;
            endcase
        end
    endfunction
    function signed [63:0] c24_rdm_level_arr;
        input integer idx;
        begin
            case (idx)
                0: c24_rdm_level_arr = 64'sd1388974;
                1: c24_rdm_level_arr = 64'sd362838;
                2: c24_rdm_level_arr = -64'sd463052;
                3: c24_rdm_level_arr = -64'sd53539;
                4: c24_rdm_level_arr = -64'sd155451;
                5: c24_rdm_level_arr = -64'sd628307;
                6: c24_rdm_level_arr = -64'sd352911;
                7: c24_rdm_level_arr = 64'sd135095;
                8: c24_rdm_level_arr = -64'sd149845;
                9: c24_rdm_level_arr = -64'sd441139;
                10: c24_rdm_level_arr = -64'sd28088;
                11: c24_rdm_level_arr = -64'sd245764;
                12: c24_rdm_level_arr = 64'sd67240;
                13: c24_rdm_level_arr = 64'sd272042;
                14: c24_rdm_level_arr = 64'sd878338;
                default: c24_rdm_level_arr = 64'sd0;
            endcase
        end
    endfunction
    function signed [63:0] c24_rdm_level_aff;
        input integer idx;
        begin
            case (idx)
                0: c24_rdm_level_aff = 64'sd622149;
                1: c24_rdm_level_aff = -64'sd76260;
                2: c24_rdm_level_aff = -64'sd425829;
                3: c24_rdm_level_aff = -64'sd96373;
                4: c24_rdm_level_aff = 64'sd127506;
                5: c24_rdm_level_aff = 64'sd93883;
                6: c24_rdm_level_aff = 64'sd13662;
                7: c24_rdm_level_aff = 64'sd52405;
                8: c24_rdm_level_aff = 64'sd119075;
                9: c24_rdm_level_aff = 64'sd274988;
                10: c24_rdm_level_aff = 64'sd180930;
                11: c24_rdm_level_aff = 64'sd183266;
                12: c24_rdm_level_aff = 64'sd28012;
                13: c24_rdm_level_aff = 64'sd120627;
                14: c24_rdm_level_aff = 64'sd374695;
                default: c24_rdm_level_aff = 64'sd0;
            endcase
        end
    endfunction
    task c24_add4;
        input signed [63:0] w_nsr;
        input signed [63:0] w_chf;
        input signed [63:0] w_arr;
        input signed [63:0] w_aff;
        begin
            c24_mem_nsr_next = c24_mem_nsr_next + w_nsr;
            c24_mem_chf_next = c24_mem_chf_next + w_chf;
            c24_mem_arr_next = c24_mem_arr_next + w_arr;
            c24_mem_aff_next = c24_mem_aff_next + w_aff;
        end
    endtask

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

        c24_mem_nsr_next = c24_mem_nsr;

        c24_mem_chf_next = c24_mem_chf;

        c24_mem_arr_next = c24_mem_arr;

        c24_mem_aff_next = c24_mem_aff;

        c24_best_score = 64'sd0;

        c24_best_class = CLASS_NSR;

        nsr_top_before_suppress = 1'b0;

        nsr_near_arr_before_suppress = 1'b0;

        nsr_chf_block_before_suppress = 1'b0;

        rbbb_late_top_nsr_before = 1'b0;

        rbbb_late_chf_block_before = 1'b0;

        rbbb_delay_top_nsr_before = 1'b0;

        rbbb_delay_chf_block_before = 1'b0;



        beat_seg_count_next = beat_seg_count + (beat_spike ? 16'd1 : 16'd0);

        dscr_flip_seg_count_next = dscr_flip_seg_count + (dscr_sign_flip_spike ? 16'd1 : 16'd0);

        dscr_slope_seg_count_next = dscr_slope_seg_count + (dscr_valid_slope_spike ? 16'd1 : 16'd0);

        qrs_maf_valid_seg_count_next = qrs_maf_valid_seg_count + (qrs_maf_valid_spike ? 16'd1 : 16'd0);

        qrs_maf_seg_count_next = qrs_maf_seg_count + ((qrs_width_abn_spike || qrs_complex_abn_spike || qrs_energy_abn_spike) ? 16'd1 : 16'd0);

        qrs_width_abn_seg_count_next = qrs_width_abn_seg_count + (qrs_width_abn_spike ? 16'd1 : 16'd0);

        qrs_energy_abn_seg_count_next = qrs_energy_abn_seg_count + (qrs_energy_abn_spike ? 16'd1 : 16'd0);

        rbbb_valid_seg_count_next = rbbb_valid_seg_count + (rbbb_qrs_valid_spike ? 16'd1 : 16'd0);

        rbbb_wide_seg_count_next = rbbb_wide_seg_count + (rbbb_qrs_wide_spike ? 16'd1 : 16'd0);

        rbbb_terminal_seg_count_next = rbbb_terminal_seg_count + (rbbb_qrs_terminal_spike ? 16'd1 : 16'd0);

        rbbb_like_seg_count_next = rbbb_like_seg_count + (rbbb_qrs_like_beat_spike ? 16'd1 : 16'd0);

        rbbb_segment_seg_count_next = rbbb_segment_seg_count + (rbbb_qrs_delay_segment_spike ? 16'd1 : 16'd0);

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

        ram_seg_count_next = ram_seg_count;

        ram_code_seg_sum_next = ram_code_seg_sum;

        rdm_ge20_seg_count_next = rdm_ge20_seg_count;

        rdm_ge50_seg_count_next = rdm_ge50_seg_count;

        rdm_ge80_seg_count_next = rdm_ge80_seg_count;

        rdm_ge100_seg_count_next = rdm_ge100_seg_count;



        if (pre_qrs_bump_spike) begin

            c24_add4(C24_W_PRE_QRS_NSR, C24_W_PRE_QRS_CHF, C24_W_PRE_QRS_ARR, C24_W_PRE_QRS_AFF);

        end

        if (rbbb_qrs_like_beat_spike) begin

            c24_add4(C24_W_RBBB_LIKE_NSR, C24_W_RBBB_LIKE_CHF, C24_W_RBBB_LIKE_ARR, C24_W_RBBB_LIKE_AFF);

        end

        if (rbbb_qrs_delay_segment_spike) begin

            c24_add4(C24_W_RBBB_SEGMENT_NSR, C24_W_RBBB_SEGMENT_CHF, C24_W_RBBB_SEGMENT_ARR, C24_W_RBBB_SEGMENT_AFF);

        end

        if (pnn_match_spike) begin

            c24_add4(C24_W_PNN_MATCH_NSR, C24_W_PNN_MATCH_CHF, C24_W_PNN_MATCH_ARR, C24_W_PNN_MATCH_AFF);

            local_nsr_next = local_nsr_next + W_PNN_MATCH_NSR;

            local_chf_next = local_chf_next + W_PNN_MATCH_CHF;

            local_arr_next = local_arr_next + W_PNN_MATCH_ARR;

            local_aff_next = local_aff_next + W_PNN_MATCH_AFF;

        end

        if (pnn_mismatch_spike) begin

            c24_add4(C24_W_PNN_MIS_NSR, C24_W_PNN_MIS_CHF, C24_W_PNN_MIS_ARR, C24_W_PNN_MIS_AFF);

            local_nsr_next = local_nsr_next + W_PNN_MIS_NSR;

            local_chf_next = local_chf_next + W_PNN_MIS_CHF;

            local_arr_next = local_arr_next + W_PNN_MIS_ARR;

            local_aff_next = local_aff_next + W_PNN_MIS_AFF;

        end

        if (dscr_valid_slope_spike) begin

            c24_add4(C24_W_DSCR_SLOPE_NSR, C24_W_DSCR_SLOPE_CHF, C24_W_DSCR_SLOPE_ARR, C24_W_DSCR_SLOPE_AFF);

            local_nsr_next = local_nsr_next + W_DSCR_SLOPE_NSR;

            local_chf_next = local_chf_next + W_DSCR_SLOPE_CHF;

        end

        if (dscr_sign_flip_spike) begin

            c24_add4(C24_W_DSCR_FLIP_NSR, C24_W_DSCR_FLIP_CHF, C24_W_DSCR_FLIP_ARR, C24_W_DSCR_FLIP_AFF);

            local_nsr_next = local_nsr_next + W_DSCR_FLIP_NSR;

            local_chf_next = local_chf_next + W_DSCR_FLIP_CHF;

        end

        if (ram_amp_spike) begin

            c24_add4(C24_W_RAM_COUNT_NSR + c24_mul_u6(C24_W_RAM_CODE_NSR, ram_amp_code), C24_W_RAM_COUNT_CHF + c24_mul_u6(C24_W_RAM_CODE_CHF, ram_amp_code), C24_W_RAM_COUNT_ARR + c24_mul_u6(C24_W_RAM_CODE_ARR, ram_amp_code), C24_W_RAM_COUNT_AFF + c24_mul_u6(C24_W_RAM_CODE_AFF, ram_amp_code));

            local_arr_next = local_arr_next + W_RAM_COUNT_ARR + score_mul_u6(W_RAM_SUM_ARR, ram_amp_code);

            local_aff_next = local_aff_next + W_RAM_COUNT_AFF + score_mul_u6(W_RAM_SUM_AFF, ram_amp_code);

            ram_count_win_next = ram_count_win_next + 16'd1;

            ram_code_win_sum_next = ram_code_win_sum_next + {16'd0, ram_amp_code};

            ram_seg_count_next = ram_seg_count_next + 16'd1;

            ram_code_seg_sum_next = ram_code_seg_sum_next + {16'd0, ram_amp_code};

        end

        if (rdm_valid_spike) begin

            for (i = 0; i < 15; i = i + 1) begin

                if (rdm_level_spike[i]) begin

                    rdm_code_calc = rdm_code_calc + 5'd1;

                    local_nsr_next = local_nsr_next + w_rdm_ge_nsr(i);

                    local_chf_next = local_chf_next + w_rdm_ge_chf(i);

                    local_arr_next = local_arr_next + w_rdm_ge_arr(i);

                    local_aff_next = local_aff_next + w_rdm_ge_aff(i);

                    c24_add4(c24_rdm_level_nsr(i), c24_rdm_level_chf(i), c24_rdm_level_arr(i), c24_rdm_level_aff(i));

                end

            end

            c24_add4(C24_W_RDM_VALID_NSR + c24_mul_u6(C24_W_RDM_CODE_NSR, {1'b0, rdm_code_calc}), C24_W_RDM_VALID_CHF + c24_mul_u6(C24_W_RDM_CODE_CHF, {1'b0, rdm_code_calc}), C24_W_RDM_VALID_ARR + c24_mul_u6(C24_W_RDM_CODE_ARR, {1'b0, rdm_code_calc}), C24_W_RDM_VALID_AFF + c24_mul_u6(C24_W_RDM_CODE_AFF, {1'b0, rdm_code_calc}));

            local_nsr_next = local_nsr_next + W_RDM_VALID_NSR + score_mul_u6(W_RDM_CODE_NSR, {1'b0, rdm_code_calc});

            local_chf_next = local_chf_next + W_RDM_VALID_CHF + score_mul_u6(W_RDM_CODE_CHF, {1'b0, rdm_code_calc});

            local_arr_next = local_arr_next + W_RDM_VALID_ARR + score_mul_u6(W_RDM_CODE_ARR, {1'b0, rdm_code_calc});

            local_aff_next = local_aff_next + W_RDM_VALID_AFF + score_mul_u6(W_RDM_CODE_AFF, {1'b0, rdm_code_calc});

            rdm_valid_win_count_next = rdm_valid_win_count_next + 16'd1;

            rdm_code_win_sum_next = rdm_code_win_sum_next + {15'd0, rdm_code_calc};

            rdm_valid_seg_count_next = rdm_valid_seg_count_next + 16'd1;

            rdm_code_seg_sum_next = rdm_code_seg_sum_next + {15'd0, rdm_code_calc};

            if (rdm_level_spike[1])
                rdm_ge20_seg_count_next = rdm_ge20_seg_count_next + 16'd1;
            if (rdm_level_spike[4])
                rdm_ge50_seg_count_next = rdm_ge50_seg_count_next + 16'd1;
            if (rdm_level_spike[7])
                rdm_ge80_seg_count_next = rdm_ge80_seg_count_next + 16'd1;
            if (rdm_level_spike[9])
                rdm_ge100_seg_count_next = rdm_ge100_seg_count_next + 16'd1;

        end

        if (ectopic_pair_spike) begin

            c24_add4(C24_W_ECT_PAIR_NSR, C24_W_ECT_PAIR_CHF, C24_W_ECT_PAIR_ARR, C24_W_ECT_PAIR_AFF);

            local_nsr_next = local_nsr_next + W_ECT_PAIR_NSR;

            local_chf_next = local_chf_next + W_ECT_PAIR_CHF;

            local_arr_next = local_arr_next + W_ECT_PAIR_ARR;

            local_aff_next = local_aff_next + W_ECT_PAIR_AFF;

        end

        if (qrs_width_abn_spike || qrs_complex_abn_spike || qrs_energy_abn_spike) begin

            c24_add4(C24_W_QRS_MAF_NSR, C24_W_QRS_MAF_CHF, C24_W_QRS_MAF_ARR, C24_W_QRS_MAF_AFF);

        end

        if (qrs_width_abn_spike) begin

            c24_add4(C24_W_QRS_WIDTH_NSR, C24_W_QRS_WIDTH_CHF, C24_W_QRS_WIDTH_ARR, C24_W_QRS_WIDTH_AFF);

            local_nsr_next = local_nsr_next + W_QRS_WIDTH_COUNT_NSR;

            local_chf_next = local_chf_next + W_QRS_WIDTH_COUNT_CHF;

            local_arr_next = local_arr_next + W_QRS_WIDTH_COUNT_ARR;

            local_aff_next = local_aff_next + W_QRS_WIDTH_COUNT_AFF;

        end

        if (qrs_complex_abn_spike) begin

            c24_add4(C24_W_QRS_COMPLEX_NSR, C24_W_QRS_COMPLEX_CHF, C24_W_QRS_COMPLEX_ARR, C24_W_QRS_COMPLEX_AFF);

            local_nsr_next = local_nsr_next + W_QRS_COMPLEX_COUNT_NSR;

            local_chf_next = local_chf_next + W_QRS_COMPLEX_COUNT_CHF;

            local_arr_next = local_arr_next + W_QRS_COMPLEX_COUNT_ARR;

            local_aff_next = local_aff_next + W_QRS_COMPLEX_COUNT_AFF;

        end

        if (qrs_energy_abn_spike) begin

            c24_add4(C24_W_QRS_ENERGY_NSR, C24_W_QRS_ENERGY_CHF, C24_W_QRS_ENERGY_ARR, C24_W_QRS_ENERGY_AFF);

            local_nsr_next = local_nsr_next + W_QRS_ENERGY_COUNT_NSR;

            local_chf_next = local_chf_next + W_QRS_ENERGY_COUNT_CHF;

            local_arr_next = local_arr_next + W_QRS_ENERGY_COUNT_ARR;

            local_aff_next = local_aff_next + W_QRS_ENERGY_COUNT_AFF;

        end

        if (etmc_spike) begin

            c24_add4(C24_W_ETMC_NSR, C24_W_ETMC_CHF, C24_W_ETMC_ARR, C24_W_ETMC_AFF);

            local_nsr_next = local_nsr_next + W_ETMC_NSR;

            local_chf_next = local_chf_next + W_ETMC_CHF;

            local_arr_next = local_arr_next + W_ETMC_ARR;

            local_aff_next = local_aff_next + W_ETMC_AFF;

        end

        if (rcd_segment_spike) begin

            c24_add4(C24_W_RCD_NSR, C24_W_RCD_CHF, C24_W_RCD_ARR, C24_W_RCD_AFF);

            local_nsr_next = local_nsr_next + W_RCD_NSR;

            local_chf_next = local_chf_next + W_RCD_CHF;

            local_arr_next = local_arr_next + W_RCD_ARR;

            local_aff_next = local_aff_next + W_RCD_AFF;

        end

        if (rcd2_segment_spike) begin

            c24_add4(C24_W_RCD2_NSR, C24_W_RCD2_CHF, C24_W_RCD2_ARR, C24_W_RCD2_AFF);

            local_nsr_next = local_nsr_next + W_RCD2_NSR;

            local_chf_next = local_chf_next + W_RCD2_CHF;

            local_arr_next = local_arr_next + W_RCD2_ARR;

            local_aff_next = local_aff_next + W_RCD2_AFF;

        end

        if (ipb_persistent_irreg_spike) begin

            c24_add4(C24_W_IPB_PERSIST_NSR, C24_W_IPB_PERSIST_CHF, C24_W_IPB_PERSIST_ARR, C24_W_IPB_PERSIST_AFF);

            local_nsr_next = local_nsr_next + W_IPB_PERSIST_NSR;

            local_chf_next = local_chf_next + W_IPB_PERSIST_CHF;

            local_arr_next = local_arr_next + W_IPB_PERSIST_ARR;

            local_aff_next = local_aff_next + W_IPB_PERSIST_AFF;

        end

        if (ipb_episodic_irreg_spike) begin

            c24_add4(C24_W_IPB_EPISODIC_NSR, C24_W_IPB_EPISODIC_CHF, C24_W_IPB_EPISODIC_ARR, C24_W_IPB_EPISODIC_AFF);

            local_nsr_next = local_nsr_next + W_IPB_EPISODIC_NSR;

            local_chf_next = local_chf_next + W_IPB_EPISODIC_CHF;

            local_arr_next = local_arr_next + W_IPB_EPISODIC_ARR;

            local_aff_next = local_aff_next + W_IPB_EPISODIC_AFF;

        end

        if (ipb_burst_irreg_spike) begin

            c24_add4(C24_W_IPB_BURST_NSR, C24_W_IPB_BURST_CHF, C24_W_IPB_BURST_ARR, C24_W_IPB_BURST_AFF);

            local_nsr_next = local_nsr_next + W_IPB_BURST_NSR;

            local_chf_next = local_chf_next + W_IPB_BURST_CHF;

            local_arr_next = local_arr_next + W_IPB_BURST_ARR;

            local_aff_next = local_aff_next + W_IPB_BURST_AFF;

        end

        if (rhythm_tick && (ms_count == 10'd999)) begin

            c24_add4(C24_W_SECOND_NSR, C24_W_SECOND_CHF, C24_W_SECOND_ARR, C24_W_SECOND_AFF);

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

            if (arr_high_irregular_spike) begin

                score_arr_next = score_arr_next + scale_score_q4(W_ARR_HIGH_IRR_TO_ARR, window_scale_q4);

                c24_add4(C24_W_ARR_HIGH_IRR_NSR, C24_W_ARR_HIGH_IRR_CHF, C24_W_ARR_HIGH_IRR_ARR, C24_W_ARR_HIGH_IRR_AFF);

            end

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

                    c24_add4(C24_W_RBBB_LATE_APPLIED_NSR, C24_W_RBBB_LATE_APPLIED_CHF, C24_W_RBBB_LATE_APPLIED_ARR, C24_W_RBBB_LATE_APPLIED_AFF);

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

                    c24_add4(C24_W_RBBB_APPLIED_NSR, C24_W_RBBB_APPLIED_CHF, C24_W_RBBB_APPLIED_ARR, C24_W_RBBB_APPLIED_AFF);

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

                    c24_add4(C24_W_RBBB_LATE_APPLIED_NSR, C24_W_RBBB_LATE_APPLIED_CHF, C24_W_RBBB_LATE_APPLIED_ARR, C24_W_RBBB_LATE_APPLIED_AFF);

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

                    c24_add4(C24_W_RBBB_APPLIED_NSR, C24_W_RBBB_APPLIED_CHF, C24_W_RBBB_APPLIED_ARR, C24_W_RBBB_APPLIED_AFF);

                end

            end

        end

        score_arr_before_eerg = score_arr_next;

        if (segment_done && eerg_gate_next) begin

            score_arr_next = score_arr_next + W_EERG_ARR_BOOST_S;

            eerg_applied = 1'b1;

            c24_add4(C24_W_EERG_GATE_NSR, C24_W_EERG_GATE_CHF, C24_W_EERG_GATE_ARR, C24_W_EERG_GATE_AFF);

            c24_add4(C24_W_EERG_APPLIED_NSR, C24_W_EERG_APPLIED_CHF, C24_W_EERG_APPLIED_ARR, C24_W_EERG_APPLIED_AFF);

        end



                if ((ENABLE_C24_GLOBAL_READOUT != 0) && segment_done) begin
            if (c24_ge_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd3))
                c24_add4(C24_W_PNN_MIS_GE_3_NSR, C24_W_PNN_MIS_GE_3_CHF, C24_W_PNN_MIS_GE_3_ARR, C24_W_PNN_MIS_GE_3_AFF); // pnn_mis_ge_3
            if (c24_ge_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd8))
                c24_add4(C24_W_PNN_MIS_GE_8_NSR, C24_W_PNN_MIS_GE_8_CHF, C24_W_PNN_MIS_GE_8_ARR, C24_W_PNN_MIS_GE_8_AFF); // pnn_mis_ge_8
            if (c24_ge_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd15))
                c24_add4(C24_W_PNN_MIS_GE_15_NSR, C24_W_PNN_MIS_GE_15_CHF, C24_W_PNN_MIS_GE_15_ARR, C24_W_PNN_MIS_GE_15_AFF); // pnn_mis_ge_15
            if (c24_ge_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd25))
                c24_add4(C24_W_PNN_MIS_GE_25_NSR, C24_W_PNN_MIS_GE_25_CHF, C24_W_PNN_MIS_GE_25_ARR, C24_W_PNN_MIS_GE_25_AFF); // pnn_mis_ge_25
            if (c24_ge_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd45))
                c24_add4(C24_W_PNN_MIS_GE_45_NSR, C24_W_PNN_MIS_GE_45_CHF, C24_W_PNN_MIS_GE_45_ARR, C24_W_PNN_MIS_GE_45_AFF); // pnn_mis_ge_45
            if (c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd3))
                c24_add4(C24_W_PNN_MIS_LE_3_NSR, C24_W_PNN_MIS_LE_3_CHF, C24_W_PNN_MIS_LE_3_ARR, C24_W_PNN_MIS_LE_3_AFF); // pnn_mis_le_3
            if (c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd8))
                c24_add4(C24_W_PNN_MIS_LE_8_NSR, C24_W_PNN_MIS_LE_8_CHF, C24_W_PNN_MIS_LE_8_ARR, C24_W_PNN_MIS_LE_8_AFF); // pnn_mis_le_8
            if (c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd15))
                c24_add4(C24_W_PNN_MIS_LE_15_NSR, C24_W_PNN_MIS_LE_15_CHF, C24_W_PNN_MIS_LE_15_ARR, C24_W_PNN_MIS_LE_15_AFF); // pnn_mis_le_15
            if (c24_ge_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd2))
                c24_add4(C24_W_RDM_AVG_GE_2_NSR, C24_W_RDM_AVG_GE_2_CHF, C24_W_RDM_AVG_GE_2_ARR, C24_W_RDM_AVG_GE_2_AFF); // rdm_avg_ge_2
            if (c24_ge_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd4))
                c24_add4(C24_W_RDM_AVG_GE_4_NSR, C24_W_RDM_AVG_GE_4_CHF, C24_W_RDM_AVG_GE_4_ARR, C24_W_RDM_AVG_GE_4_AFF); // rdm_avg_ge_4
            if (c24_ge_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd6))
                c24_add4(C24_W_RDM_AVG_GE_6_NSR, C24_W_RDM_AVG_GE_6_CHF, C24_W_RDM_AVG_GE_6_ARR, C24_W_RDM_AVG_GE_6_AFF); // rdm_avg_ge_6
            if (c24_ge_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd9))
                c24_add4(C24_W_RDM_AVG_GE_9_NSR, C24_W_RDM_AVG_GE_9_CHF, C24_W_RDM_AVG_GE_9_ARR, C24_W_RDM_AVG_GE_9_AFF); // rdm_avg_ge_9
            if (c24_ge_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd12))
                c24_add4(C24_W_RDM_AVG_GE_12_NSR, C24_W_RDM_AVG_GE_12_CHF, C24_W_RDM_AVG_GE_12_ARR, C24_W_RDM_AVG_GE_12_AFF); // rdm_avg_ge_12
            if (c24_le_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd2))
                c24_add4(C24_W_RDM_AVG_LE_2_NSR, C24_W_RDM_AVG_LE_2_CHF, C24_W_RDM_AVG_LE_2_ARR, C24_W_RDM_AVG_LE_2_AFF); // rdm_avg_le_2
            if (c24_le_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd4))
                c24_add4(C24_W_RDM_AVG_LE_4_NSR, C24_W_RDM_AVG_LE_4_CHF, C24_W_RDM_AVG_LE_4_ARR, C24_W_RDM_AVG_LE_4_AFF); // rdm_avg_le_4
            if (c24_le_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd6))
                c24_add4(C24_W_RDM_AVG_LE_6_NSR, C24_W_RDM_AVG_LE_6_CHF, C24_W_RDM_AVG_LE_6_ARR, C24_W_RDM_AVG_LE_6_AFF); // rdm_avg_le_6
            if (c24_ge_pct({16'd0, rdm_ge20_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd3))
                c24_add4(C24_W_RDM_GE20_GE_3_NSR, C24_W_RDM_GE20_GE_3_CHF, C24_W_RDM_GE20_GE_3_ARR, C24_W_RDM_GE20_GE_3_AFF); // rdm_ge20_ge_3
            if (c24_ge_pct({16'd0, rdm_ge20_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd8))
                c24_add4(C24_W_RDM_GE20_GE_8_NSR, C24_W_RDM_GE20_GE_8_CHF, C24_W_RDM_GE20_GE_8_ARR, C24_W_RDM_GE20_GE_8_AFF); // rdm_ge20_ge_8
            if (c24_ge_pct({16'd0, rdm_ge20_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd20))
                c24_add4(C24_W_RDM_GE20_GE_20_NSR, C24_W_RDM_GE20_GE_20_CHF, C24_W_RDM_GE20_GE_20_ARR, C24_W_RDM_GE20_GE_20_AFF); // rdm_ge20_ge_20
            if (c24_ge_pct({16'd0, rdm_ge20_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd40))
                c24_add4(C24_W_RDM_GE20_GE_40_NSR, C24_W_RDM_GE20_GE_40_CHF, C24_W_RDM_GE20_GE_40_ARR, C24_W_RDM_GE20_GE_40_AFF); // rdm_ge20_ge_40
            if (c24_ge_pct({16'd0, rdm_ge50_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd3))
                c24_add4(C24_W_RDM_GE50_GE_3_NSR, C24_W_RDM_GE50_GE_3_CHF, C24_W_RDM_GE50_GE_3_ARR, C24_W_RDM_GE50_GE_3_AFF); // rdm_ge50_ge_3
            if (c24_ge_pct({16'd0, rdm_ge50_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd8))
                c24_add4(C24_W_RDM_GE50_GE_8_NSR, C24_W_RDM_GE50_GE_8_CHF, C24_W_RDM_GE50_GE_8_ARR, C24_W_RDM_GE50_GE_8_AFF); // rdm_ge50_ge_8
            if (c24_ge_pct({16'd0, rdm_ge50_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd20))
                c24_add4(C24_W_RDM_GE50_GE_20_NSR, C24_W_RDM_GE50_GE_20_CHF, C24_W_RDM_GE50_GE_20_ARR, C24_W_RDM_GE50_GE_20_AFF); // rdm_ge50_ge_20
            if (c24_ge_pct({16'd0, rdm_ge50_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd40))
                c24_add4(C24_W_RDM_GE50_GE_40_NSR, C24_W_RDM_GE50_GE_40_CHF, C24_W_RDM_GE50_GE_40_ARR, C24_W_RDM_GE50_GE_40_AFF); // rdm_ge50_ge_40
            if (c24_ge_pct({16'd0, rdm_ge80_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd3))
                c24_add4(C24_W_RDM_GE80_GE_3_NSR, C24_W_RDM_GE80_GE_3_CHF, C24_W_RDM_GE80_GE_3_ARR, C24_W_RDM_GE80_GE_3_AFF); // rdm_ge80_ge_3
            if (c24_ge_pct({16'd0, rdm_ge80_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd8))
                c24_add4(C24_W_RDM_GE80_GE_8_NSR, C24_W_RDM_GE80_GE_8_CHF, C24_W_RDM_GE80_GE_8_ARR, C24_W_RDM_GE80_GE_8_AFF); // rdm_ge80_ge_8
            if (c24_ge_pct({16'd0, rdm_ge80_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd20))
                c24_add4(C24_W_RDM_GE80_GE_20_NSR, C24_W_RDM_GE80_GE_20_CHF, C24_W_RDM_GE80_GE_20_ARR, C24_W_RDM_GE80_GE_20_AFF); // rdm_ge80_ge_20
            if (c24_ge_pct({16'd0, rdm_ge80_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd40))
                c24_add4(C24_W_RDM_GE80_GE_40_NSR, C24_W_RDM_GE80_GE_40_CHF, C24_W_RDM_GE80_GE_40_ARR, C24_W_RDM_GE80_GE_40_AFF); // rdm_ge80_ge_40
            if (c24_ge_pct({16'd0, rdm_ge100_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd3))
                c24_add4(C24_W_RDM_GE100_GE_3_NSR, C24_W_RDM_GE100_GE_3_CHF, C24_W_RDM_GE100_GE_3_ARR, C24_W_RDM_GE100_GE_3_AFF); // rdm_ge100_ge_3
            if (c24_ge_pct({16'd0, rdm_ge100_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd8))
                c24_add4(C24_W_RDM_GE100_GE_8_NSR, C24_W_RDM_GE100_GE_8_CHF, C24_W_RDM_GE100_GE_8_ARR, C24_W_RDM_GE100_GE_8_AFF); // rdm_ge100_ge_8
            if (c24_ge_pct({16'd0, rdm_ge100_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd20))
                c24_add4(C24_W_RDM_GE100_GE_20_NSR, C24_W_RDM_GE100_GE_20_CHF, C24_W_RDM_GE100_GE_20_ARR, C24_W_RDM_GE100_GE_20_AFF); // rdm_ge100_ge_20
            if (c24_ge_pct({16'd0, rdm_ge100_seg_count_next}, {16'd0, rdm_valid_seg_count_next}, 32'd40))
                c24_add4(C24_W_RDM_GE100_GE_40_NSR, C24_W_RDM_GE100_GE_40_CHF, C24_W_RDM_GE100_GE_40_ARR, C24_W_RDM_GE100_GE_40_AFF); // rdm_ge100_ge_40
            if (c24_ge_pct({16'd0, dscr_flip_seg_count_next}, {16'd0, dscr_slope_seg_count_next}, 32'd1))
                c24_add4(C24_W_DSCR_GE_1_NSR, C24_W_DSCR_GE_1_CHF, C24_W_DSCR_GE_1_ARR, C24_W_DSCR_GE_1_AFF); // dscr_ge_1
            if (c24_ge_pct({16'd0, dscr_flip_seg_count_next}, {16'd0, dscr_slope_seg_count_next}, 32'd3))
                c24_add4(C24_W_DSCR_GE_3_NSR, C24_W_DSCR_GE_3_CHF, C24_W_DSCR_GE_3_ARR, C24_W_DSCR_GE_3_AFF); // dscr_ge_3
            if (c24_ge_pct({16'd0, dscr_flip_seg_count_next}, {16'd0, dscr_slope_seg_count_next}, 32'd5))
                c24_add4(C24_W_DSCR_GE_5_NSR, C24_W_DSCR_GE_5_CHF, C24_W_DSCR_GE_5_ARR, C24_W_DSCR_GE_5_AFF); // dscr_ge_5
            if (c24_ge_pct({16'd0, dscr_flip_seg_count_next}, {16'd0, dscr_slope_seg_count_next}, 32'd8))
                c24_add4(C24_W_DSCR_GE_8_NSR, C24_W_DSCR_GE_8_CHF, C24_W_DSCR_GE_8_ARR, C24_W_DSCR_GE_8_AFF); // dscr_ge_8
            if (c24_ge_pct({16'd0, dscr_flip_seg_count_next}, {16'd0, dscr_slope_seg_count_next}, 32'd12))
                c24_add4(C24_W_DSCR_GE_12_NSR, C24_W_DSCR_GE_12_CHF, C24_W_DSCR_GE_12_ARR, C24_W_DSCR_GE_12_AFF); // dscr_ge_12
            if (c24_le_pct({16'd0, dscr_flip_seg_count_next}, {16'd0, dscr_slope_seg_count_next}, 32'd1))
                c24_add4(C24_W_DSCR_LE_1_NSR, C24_W_DSCR_LE_1_CHF, C24_W_DSCR_LE_1_ARR, C24_W_DSCR_LE_1_AFF); // dscr_le_1
            if (c24_le_pct({16'd0, dscr_flip_seg_count_next}, {16'd0, dscr_slope_seg_count_next}, 32'd3))
                c24_add4(C24_W_DSCR_LE_3_NSR, C24_W_DSCR_LE_3_CHF, C24_W_DSCR_LE_3_ARR, C24_W_DSCR_LE_3_AFF); // dscr_le_3
            if (c24_le_pct({16'd0, dscr_flip_seg_count_next}, {16'd0, dscr_slope_seg_count_next}, 32'd5))
                c24_add4(C24_W_DSCR_LE_5_NSR, C24_W_DSCR_LE_5_CHF, C24_W_DSCR_LE_5_ARR, C24_W_DSCR_LE_5_AFF); // dscr_le_5
            if (c24_ge_avg({10'd0, ram_code_seg_sum_next}, {16'd0, ram_seg_count_next}, 32'd2))
                c24_add4(C24_W_RAM_GE_2_NSR, C24_W_RAM_GE_2_CHF, C24_W_RAM_GE_2_ARR, C24_W_RAM_GE_2_AFF); // ram_ge_2
            if (c24_ge_avg({10'd0, ram_code_seg_sum_next}, {16'd0, ram_seg_count_next}, 32'd4))
                c24_add4(C24_W_RAM_GE_4_NSR, C24_W_RAM_GE_4_CHF, C24_W_RAM_GE_4_ARR, C24_W_RAM_GE_4_AFF); // ram_ge_4
            if (c24_ge_avg({10'd0, ram_code_seg_sum_next}, {16'd0, ram_seg_count_next}, 32'd6))
                c24_add4(C24_W_RAM_GE_6_NSR, C24_W_RAM_GE_6_CHF, C24_W_RAM_GE_6_ARR, C24_W_RAM_GE_6_AFF); // ram_ge_6
            if (c24_ge_avg({10'd0, ram_code_seg_sum_next}, {16'd0, ram_seg_count_next}, 32'd10))
                c24_add4(C24_W_RAM_GE_10_NSR, C24_W_RAM_GE_10_CHF, C24_W_RAM_GE_10_ARR, C24_W_RAM_GE_10_AFF); // ram_ge_10
            if (c24_ge_avg({10'd0, ram_code_seg_sum_next}, {16'd0, ram_seg_count_next}, 32'd14))
                c24_add4(C24_W_RAM_GE_14_NSR, C24_W_RAM_GE_14_CHF, C24_W_RAM_GE_14_ARR, C24_W_RAM_GE_14_AFF); // ram_ge_14
            if (c24_le_avg({10'd0, ram_code_seg_sum_next}, {16'd0, ram_seg_count_next}, 32'd2))
                c24_add4(C24_W_RAM_LE_2_NSR, C24_W_RAM_LE_2_CHF, C24_W_RAM_LE_2_ARR, C24_W_RAM_LE_2_AFF); // ram_le_2
            if (c24_le_avg({10'd0, ram_code_seg_sum_next}, {16'd0, ram_seg_count_next}, 32'd4))
                c24_add4(C24_W_RAM_LE_4_NSR, C24_W_RAM_LE_4_CHF, C24_W_RAM_LE_4_ARR, C24_W_RAM_LE_4_AFF); // ram_le_4
            if (c24_le_avg({10'd0, ram_code_seg_sum_next}, {16'd0, ram_seg_count_next}, 32'd6))
                c24_add4(C24_W_RAM_LE_6_NSR, C24_W_RAM_LE_6_CHF, C24_W_RAM_LE_6_ARR, C24_W_RAM_LE_6_AFF); // ram_le_6
            if (c24_ge_pct({16'd0, ectopic_pair_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd1))
                c24_add4(C24_W_ECP_GE_1_NSR, C24_W_ECP_GE_1_CHF, C24_W_ECP_GE_1_ARR, C24_W_ECP_GE_1_AFF); // ecp_ge_1
            if (c24_ge_pct({16'd0, ectopic_pair_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd3))
                c24_add4(C24_W_ECP_GE_3_NSR, C24_W_ECP_GE_3_CHF, C24_W_ECP_GE_3_ARR, C24_W_ECP_GE_3_AFF); // ecp_ge_3
            if (c24_ge_pct({16'd0, ectopic_pair_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd8))
                c24_add4(C24_W_ECP_GE_8_NSR, C24_W_ECP_GE_8_CHF, C24_W_ECP_GE_8_ARR, C24_W_ECP_GE_8_AFF); // ecp_ge_8
            if (c24_ge_pct({16'd0, ectopic_pair_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd15))
                c24_add4(C24_W_ECP_GE_15_NSR, C24_W_ECP_GE_15_CHF, C24_W_ECP_GE_15_ARR, C24_W_ECP_GE_15_AFF); // ecp_ge_15
            if (c24_ge_pct({16'd0, ectopic_pair_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd25))
                c24_add4(C24_W_ECP_GE_25_NSR, C24_W_ECP_GE_25_CHF, C24_W_ECP_GE_25_ARR, C24_W_ECP_GE_25_AFF); // ecp_ge_25
            if (c24_ge_pct({16'd0, pre_qrs_bump_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd1))
                c24_add4(C24_W_PRE_GE_1_NSR, C24_W_PRE_GE_1_CHF, C24_W_PRE_GE_1_ARR, C24_W_PRE_GE_1_AFF); // pre_ge_1
            if (c24_ge_pct({16'd0, pre_qrs_bump_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd3))
                c24_add4(C24_W_PRE_GE_3_NSR, C24_W_PRE_GE_3_CHF, C24_W_PRE_GE_3_ARR, C24_W_PRE_GE_3_AFF); // pre_ge_3
            if (c24_ge_pct({16'd0, pre_qrs_bump_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd8))
                c24_add4(C24_W_PRE_GE_8_NSR, C24_W_PRE_GE_8_CHF, C24_W_PRE_GE_8_ARR, C24_W_PRE_GE_8_AFF); // pre_ge_8
            if (c24_ge_pct({16'd0, qrs_maf_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd1))
                c24_add4(C24_W_QRS_GE_1_NSR, C24_W_QRS_GE_1_CHF, C24_W_QRS_GE_1_ARR, C24_W_QRS_GE_1_AFF); // qrs_ge_1
            if (c24_ge_pct({16'd0, qrs_maf_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd3))
                c24_add4(C24_W_QRS_GE_3_NSR, C24_W_QRS_GE_3_CHF, C24_W_QRS_GE_3_ARR, C24_W_QRS_GE_3_AFF); // qrs_ge_3
            if (c24_ge_pct({16'd0, qrs_maf_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd8))
                c24_add4(C24_W_QRS_GE_8_NSR, C24_W_QRS_GE_8_CHF, C24_W_QRS_GE_8_ARR, C24_W_QRS_GE_8_AFF); // qrs_ge_8
            if (c24_ge_pct({16'd0, qrs_maf_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd20))
                c24_add4(C24_W_QRS_GE_20_NSR, C24_W_QRS_GE_20_CHF, C24_W_QRS_GE_20_ARR, C24_W_QRS_GE_20_AFF); // qrs_ge_20
            if (c24_ge_pct({16'd0, qrs_maf_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd40))
                c24_add4(C24_W_QRS_GE_40_NSR, C24_W_QRS_GE_40_CHF, C24_W_QRS_GE_40_ARR, C24_W_QRS_GE_40_AFF); // qrs_ge_40
            if (c24_ge_pct({16'd0, qrs_width_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd1))
                c24_add4(C24_W_QRS_WIDTH_GE_1_NSR, C24_W_QRS_WIDTH_GE_1_CHF, C24_W_QRS_WIDTH_GE_1_ARR, C24_W_QRS_WIDTH_GE_1_AFF); // qrs_width_ge_1
            if (c24_ge_pct({16'd0, qrs_width_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd3))
                c24_add4(C24_W_QRS_WIDTH_GE_3_NSR, C24_W_QRS_WIDTH_GE_3_CHF, C24_W_QRS_WIDTH_GE_3_ARR, C24_W_QRS_WIDTH_GE_3_AFF); // qrs_width_ge_3
            if (c24_ge_pct({16'd0, qrs_width_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd8))
                c24_add4(C24_W_QRS_WIDTH_GE_8_NSR, C24_W_QRS_WIDTH_GE_8_CHF, C24_W_QRS_WIDTH_GE_8_ARR, C24_W_QRS_WIDTH_GE_8_AFF); // qrs_width_ge_8
            if (c24_ge_pct({16'd0, qrs_width_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd15))
                c24_add4(C24_W_QRS_WIDTH_GE_15_NSR, C24_W_QRS_WIDTH_GE_15_CHF, C24_W_QRS_WIDTH_GE_15_ARR, C24_W_QRS_WIDTH_GE_15_AFF); // qrs_width_ge_15
            if (c24_ge_pct({16'd0, qrs_energy_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd1))
                c24_add4(C24_W_QRS_ENERGY_GE_1_NSR, C24_W_QRS_ENERGY_GE_1_CHF, C24_W_QRS_ENERGY_GE_1_ARR, C24_W_QRS_ENERGY_GE_1_AFF); // qrs_energy_ge_1
            if (c24_ge_pct({16'd0, qrs_energy_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd3))
                c24_add4(C24_W_QRS_ENERGY_GE_3_NSR, C24_W_QRS_ENERGY_GE_3_CHF, C24_W_QRS_ENERGY_GE_3_ARR, C24_W_QRS_ENERGY_GE_3_AFF); // qrs_energy_ge_3
            if (c24_ge_pct({16'd0, qrs_energy_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd8))
                c24_add4(C24_W_QRS_ENERGY_GE_8_NSR, C24_W_QRS_ENERGY_GE_8_CHF, C24_W_QRS_ENERGY_GE_8_ARR, C24_W_QRS_ENERGY_GE_8_AFF); // qrs_energy_ge_8
            if (c24_ge_pct({16'd0, qrs_energy_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd20))
                c24_add4(C24_W_QRS_ENERGY_GE_20_NSR, C24_W_QRS_ENERGY_GE_20_CHF, C24_W_QRS_ENERGY_GE_20_ARR, C24_W_QRS_ENERGY_GE_20_AFF); // qrs_energy_ge_20
            if (c24_ge_pct({16'd0, qrs_energy_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd40))
                c24_add4(C24_W_QRS_ENERGY_GE_40_NSR, C24_W_QRS_ENERGY_GE_40_CHF, C24_W_QRS_ENERGY_GE_40_ARR, C24_W_QRS_ENERGY_GE_40_AFF); // qrs_energy_ge_40
            if (c24_ge_pct({16'd0, rbbb_like_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd1))
                c24_add4(C24_W_RBBB_GE_1_NSR, C24_W_RBBB_GE_1_CHF, C24_W_RBBB_GE_1_ARR, C24_W_RBBB_GE_1_AFF); // rbbb_ge_1
            if (c24_ge_pct({16'd0, rbbb_like_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd3))
                c24_add4(C24_W_RBBB_GE_3_NSR, C24_W_RBBB_GE_3_CHF, C24_W_RBBB_GE_3_ARR, C24_W_RBBB_GE_3_AFF); // rbbb_ge_3
            if (c24_ge_pct({16'd0, rbbb_like_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd8))
                c24_add4(C24_W_RBBB_GE_8_NSR, C24_W_RBBB_GE_8_CHF, C24_W_RBBB_GE_8_ARR, C24_W_RBBB_GE_8_AFF); // rbbb_ge_8
            if (c24_ge_pct({16'd0, rbbb_like_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd15))
                c24_add4(C24_W_RBBB_GE_15_NSR, C24_W_RBBB_GE_15_CHF, C24_W_RBBB_GE_15_ARR, C24_W_RBBB_GE_15_AFF); // rbbb_ge_15
            if (c24_ge_pct({16'd0, rbbb_wide_seg_count_next}, {16'd0, rbbb_valid_seg_count_next}, 32'd1))
                c24_add4(C24_W_RBBB_WIDE_GE_1_NSR, C24_W_RBBB_WIDE_GE_1_CHF, C24_W_RBBB_WIDE_GE_1_ARR, C24_W_RBBB_WIDE_GE_1_AFF); // rbbb_wide_ge_1
            if (c24_ge_pct({16'd0, rbbb_wide_seg_count_next}, {16'd0, rbbb_valid_seg_count_next}, 32'd3))
                c24_add4(C24_W_RBBB_WIDE_GE_3_NSR, C24_W_RBBB_WIDE_GE_3_CHF, C24_W_RBBB_WIDE_GE_3_ARR, C24_W_RBBB_WIDE_GE_3_AFF); // rbbb_wide_ge_3
            if (c24_ge_pct({16'd0, rbbb_wide_seg_count_next}, {16'd0, rbbb_valid_seg_count_next}, 32'd8))
                c24_add4(C24_W_RBBB_WIDE_GE_8_NSR, C24_W_RBBB_WIDE_GE_8_CHF, C24_W_RBBB_WIDE_GE_8_ARR, C24_W_RBBB_WIDE_GE_8_AFF); // rbbb_wide_ge_8
            if (c24_ge_pct({16'd0, rbbb_wide_seg_count_next}, {16'd0, rbbb_valid_seg_count_next}, 32'd15))
                c24_add4(C24_W_RBBB_WIDE_GE_15_NSR, C24_W_RBBB_WIDE_GE_15_CHF, C24_W_RBBB_WIDE_GE_15_ARR, C24_W_RBBB_WIDE_GE_15_AFF); // rbbb_wide_ge_15
            if (c24_ge_pct({16'd0, rbbb_terminal_seg_count_next}, {16'd0, rbbb_valid_seg_count_next}, 32'd1))
                c24_add4(C24_W_RBBB_TERMINAL_GE_1_NSR, C24_W_RBBB_TERMINAL_GE_1_CHF, C24_W_RBBB_TERMINAL_GE_1_ARR, C24_W_RBBB_TERMINAL_GE_1_AFF); // rbbb_terminal_ge_1
            if (c24_ge_pct({16'd0, rbbb_terminal_seg_count_next}, {16'd0, rbbb_valid_seg_count_next}, 32'd3))
                c24_add4(C24_W_RBBB_TERMINAL_GE_3_NSR, C24_W_RBBB_TERMINAL_GE_3_CHF, C24_W_RBBB_TERMINAL_GE_3_ARR, C24_W_RBBB_TERMINAL_GE_3_AFF); // rbbb_terminal_ge_3
            if (c24_ge_pct({16'd0, rbbb_terminal_seg_count_next}, {16'd0, rbbb_valid_seg_count_next}, 32'd8))
                c24_add4(C24_W_RBBB_TERMINAL_GE_8_NSR, C24_W_RBBB_TERMINAL_GE_8_CHF, C24_W_RBBB_TERMINAL_GE_8_ARR, C24_W_RBBB_TERMINAL_GE_8_AFF); // rbbb_terminal_ge_8
            if (c24_ge_pct({16'd0, rbbb_terminal_seg_count_next}, {16'd0, rbbb_valid_seg_count_next}, 32'd15))
                c24_add4(C24_W_RBBB_TERMINAL_GE_15_NSR, C24_W_RBBB_TERMINAL_GE_15_CHF, C24_W_RBBB_TERMINAL_GE_15_ARR, C24_W_RBBB_TERMINAL_GE_15_AFF); // rbbb_terminal_ge_15
            if (c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd15) && c24_ge_pct({16'd0, rbbb_like_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd2))
                c24_add4(C24_W_GATE_REGULAR_RBBB_RESCUE_NSR, C24_W_GATE_REGULAR_RBBB_RESCUE_CHF, C24_W_GATE_REGULAR_RBBB_RESCUE_ARR, C24_W_GATE_REGULAR_RBBB_RESCUE_AFF); // gate_regular_rbbb_rescue
            if (c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd15) && (c24_ge_pct({16'd0, qrs_width_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd2) || c24_ge_pct({16'd0, qrs_energy_abn_seg_count_next}, {16'd0, qrs_maf_valid_seg_count_next}, 32'd35)))
                c24_add4(C24_W_GATE_REGULAR_QRS_ARR_RESCUE_NSR, C24_W_GATE_REGULAR_QRS_ARR_RESCUE_CHF, C24_W_GATE_REGULAR_QRS_ARR_RESCUE_ARR, C24_W_GATE_REGULAR_QRS_ARR_RESCUE_AFF); // gate_regular_qrs_arr_rescue
            if (c24_ge_pct({16'd0, ectopic_pair_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd3) && c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd35) && c24_le_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd8))
                c24_add4(C24_W_GATE_EPISODIC_ECTOPIC_ARR_NSR, C24_W_GATE_EPISODIC_ECTOPIC_ARR_CHF, C24_W_GATE_EPISODIC_ECTOPIC_ARR_ARR, C24_W_GATE_EPISODIC_ECTOPIC_ARR_AFF); // gate_episodic_ectopic_arr
            if ((rbbb_like_seg_count_next == 16'd0) && (pre_qrs_bump_seg_count_next >= 16'd1) && ((ectopic_early_seg_count_next >= 16'd10) || (ectopic_pair_seg_count_next >= 16'd3)) && c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd15) && c24_le_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd5))
                c24_add4(C24_W_GATE_EERG_LIKE_NSR, C24_W_GATE_EERG_LIKE_CHF, C24_W_GATE_EERG_LIKE_ARR, C24_W_GATE_EERG_LIKE_AFF); // gate_eerg_like
            if (c24_ge_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd25) && c24_ge_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd7) && c24_ge_pct({16'd0, ectopic_pair_seg_count_next}, {16'd0, beat_seg_count_next}, 32'd5))
                c24_add4(C24_W_GATE_AFF_PERSISTENT_IRREG_NSR, C24_W_GATE_AFF_PERSISTENT_IRREG_CHF, C24_W_GATE_AFF_PERSISTENT_IRREG_ARR, C24_W_GATE_AFF_PERSISTENT_IRREG_AFF); // gate_aff_persistent_irreg
            if (c24_ge_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd5) && c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd30) && c24_ge_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd2) && c24_le_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd9))
                c24_add4(C24_W_GATE_ARR_MID_IRREG_NSR, C24_W_GATE_ARR_MID_IRREG_CHF, C24_W_GATE_ARR_MID_IRREG_ARR, C24_W_GATE_ARR_MID_IRREG_AFF); // gate_arr_mid_irreg
            if (c24_le_pct({16'd0, dscr_flip_seg_count_next}, {16'd0, dscr_slope_seg_count_next}, 32'd3) && c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd20))
                c24_add4(C24_W_GATE_CHF_LOW_DSCR_LOW_IRREG_NSR, C24_W_GATE_CHF_LOW_DSCR_LOW_IRREG_CHF, C24_W_GATE_CHF_LOW_DSCR_LOW_IRREG_ARR, C24_W_GATE_CHF_LOW_DSCR_LOW_IRREG_AFF); // gate_chf_low_dscr_low_irreg
            if (c24_ge_pct({16'd0, dscr_flip_seg_count_next}, {16'd0, dscr_slope_seg_count_next}, 32'd5) && c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd15) && c24_le_avg({12'd0, rdm_code_seg_sum_next}, {16'd0, rdm_valid_seg_count_next}, 32'd5))
                c24_add4(C24_W_GATE_NSR_HIGH_DSCR_LOW_IRREG_NSR, C24_W_GATE_NSR_HIGH_DSCR_LOW_IRREG_CHF, C24_W_GATE_NSR_HIGH_DSCR_LOW_IRREG_ARR, C24_W_GATE_NSR_HIGH_DSCR_LOW_IRREG_AFF); // gate_nsr_high_dscr_low_irreg
            if (c24_ge_avg({10'd0, ram_code_seg_sum_next}, {16'd0, ram_seg_count_next}, 32'd10) && c24_le_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd20))
                c24_add4(C24_W_GATE_RAM_HIGH_REGULAR_NSR, C24_W_GATE_RAM_HIGH_REGULAR_CHF, C24_W_GATE_RAM_HIGH_REGULAR_ARR, C24_W_GATE_RAM_HIGH_REGULAR_AFF); // gate_ram_high_regular
            if (c24_le_avg({10'd0, ram_code_seg_sum_next}, {16'd0, ram_seg_count_next}, 32'd5) && c24_ge_pct({16'd0, pnn_mis_seg_count_next}, {15'd0, pnn_decision_seg_count}, 32'd15))
                c24_add4(C24_W_GATE_RAM_LOW_IRREGULAR_NSR, C24_W_GATE_RAM_LOW_IRREGULAR_CHF, C24_W_GATE_RAM_LOW_IRREGULAR_ARR, C24_W_GATE_RAM_LOW_IRREGULAR_AFF); // gate_ram_low_irregular
        end

        if ((ENABLE_C24_GLOBAL_READOUT != 0) && segment_done) begin
            c24_best_score = c24_mem_nsr_next;
            c24_best_class = CLASS_NSR;
            if (c24_mem_chf_next > c24_best_score) begin c24_best_score = c24_mem_chf_next; c24_best_class = CLASS_CHF; end
            if (c24_mem_arr_next > c24_best_score) begin c24_best_score = c24_mem_arr_next; c24_best_class = CLASS_ARR; end
            if (c24_mem_aff_next > c24_best_score) begin c24_best_score = c24_mem_aff_next; c24_best_class = CLASS_AFF; end
            best_score = c24_best_score[SCORE_WIDTH-1:0];
            best_class = c24_best_class;
        end else begin
            best_score = score_nsr_next;
            best_class = CLASS_NSR;
            if (score_chf_next > best_score) begin best_score = score_chf_next; best_class = CLASS_CHF; end
            if (score_arr_next > best_score) begin best_score = score_arr_next; best_class = CLASS_ARR; end
            if (score_aff_next > best_score) begin best_score = score_aff_next; best_class = CLASS_AFF; end
        end

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

            c24_mem_nsr <= C24_MEM_INIT_NSR;

            c24_mem_chf <= C24_MEM_INIT_CHF;

            c24_mem_arr <= C24_MEM_INIT_ARR;

            c24_mem_aff <= C24_MEM_INIT_AFF;

            pred_class <= CLASS_NSR;

            pred_valid <= 1'b0;

            pnn_regular_high <= 1'b0;

            dscr_high <= 1'b0;

            ram_high <= 1'b0;

            ms_count <= 10'd0;

            subwindow_tick_count <= 17'd0;

            beat_seg_count <= 16'd0;

            dscr_flip_seg_count <= 16'd0;

            dscr_slope_seg_count <= 16'd0;

            ram_seg_count <= 16'd0;

            ram_code_seg_sum <= 22'd0;

            rdm_ge20_seg_count <= 16'd0;

            rdm_ge50_seg_count <= 16'd0;

            rdm_ge80_seg_count <= 16'd0;

            rdm_ge100_seg_count <= 16'd0;

            qrs_maf_valid_seg_count <= 16'd0;

            qrs_maf_seg_count <= 16'd0;

            qrs_width_abn_seg_count <= 16'd0;

            qrs_energy_abn_seg_count <= 16'd0;

            rbbb_valid_seg_count <= 16'd0;

            rbbb_wide_seg_count <= 16'd0;

            rbbb_terminal_seg_count <= 16'd0;

            rbbb_like_seg_count <= 16'd0;

            rbbb_segment_seg_count <= 16'd0;

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

            c24_mem_nsr <= C24_MEM_INIT_NSR;

            c24_mem_chf <= C24_MEM_INIT_CHF;

            c24_mem_arr <= C24_MEM_INIT_ARR;

            c24_mem_aff <= C24_MEM_INIT_AFF;

            pred_class <= CLASS_NSR;

            pred_valid <= 1'b0;

            pnn_regular_high <= 1'b0;

            dscr_high <= 1'b0;

            ram_high <= 1'b0;

            ms_count <= 10'd0;

            subwindow_tick_count <= 17'd0;

            beat_seg_count <= 16'd0;

            dscr_flip_seg_count <= 16'd0;

            dscr_slope_seg_count <= 16'd0;

            ram_seg_count <= 16'd0;

            ram_code_seg_sum <= 22'd0;

            rdm_ge20_seg_count <= 16'd0;

            rdm_ge50_seg_count <= 16'd0;

            rdm_ge80_seg_count <= 16'd0;

            rdm_ge100_seg_count <= 16'd0;

            qrs_maf_valid_seg_count <= 16'd0;

            qrs_maf_seg_count <= 16'd0;

            qrs_width_abn_seg_count <= 16'd0;

            qrs_energy_abn_seg_count <= 16'd0;

            rbbb_valid_seg_count <= 16'd0;

            rbbb_wide_seg_count <= 16'd0;

            rbbb_terminal_seg_count <= 16'd0;

            rbbb_like_seg_count <= 16'd0;

            rbbb_segment_seg_count <= 16'd0;

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

            c24_mem_nsr <= c24_mem_nsr_next;

            c24_mem_chf <= c24_mem_chf_next;

            c24_mem_arr <= c24_mem_arr_next;

            c24_mem_aff <= c24_mem_aff_next;



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

                beat_seg_count <= 16'd0;

                dscr_flip_seg_count <= 16'd0;

                dscr_slope_seg_count <= 16'd0;

                ram_seg_count <= 16'd0;

                ram_code_seg_sum <= 22'd0;

                rdm_ge20_seg_count <= 16'd0;

                rdm_ge50_seg_count <= 16'd0;

                rdm_ge80_seg_count <= 16'd0;

                rdm_ge100_seg_count <= 16'd0;

                qrs_maf_valid_seg_count <= 16'd0;

                qrs_maf_seg_count <= 16'd0;

                qrs_width_abn_seg_count <= 16'd0;

                qrs_energy_abn_seg_count <= 16'd0;

                rbbb_valid_seg_count <= 16'd0;

                rbbb_wide_seg_count <= 16'd0;

                rbbb_terminal_seg_count <= 16'd0;

                rbbb_like_seg_count <= 16'd0;

                rbbb_segment_seg_count <= 16'd0;

                ectopic_pair_seg_count <= 16'd0;

                ectopic_early_seg_count <= 16'd0;

                pre_qrs_bump_seg_count <= 16'd0;

                pnn_match_seg_count <= 16'd0;

                pnn_mis_seg_count <= 16'd0;

                rdm_valid_seg_count <= 16'd0;

                rdm_code_seg_sum <= 20'd0;

            end else begin

                eerg_gate <= 1'b0;

                beat_seg_count <= beat_seg_count_next;

                dscr_flip_seg_count <= dscr_flip_seg_count_next;

                dscr_slope_seg_count <= dscr_slope_seg_count_next;

                ram_seg_count <= ram_seg_count_next;

                ram_code_seg_sum <= ram_code_seg_sum_next;

                rdm_ge20_seg_count <= rdm_ge20_seg_count_next;

                rdm_ge50_seg_count <= rdm_ge50_seg_count_next;

                rdm_ge80_seg_count <= rdm_ge80_seg_count_next;

                rdm_ge100_seg_count <= rdm_ge100_seg_count_next;

                qrs_maf_valid_seg_count <= qrs_maf_valid_seg_count_next;

                qrs_maf_seg_count <= qrs_maf_seg_count_next;

                qrs_width_abn_seg_count <= qrs_width_abn_seg_count_next;

                qrs_energy_abn_seg_count <= qrs_energy_abn_seg_count_next;

                rbbb_valid_seg_count <= rbbb_valid_seg_count_next;

                rbbb_wide_seg_count <= rbbb_wide_seg_count_next;

                rbbb_terminal_seg_count <= rbbb_terminal_seg_count_next;

                rbbb_like_seg_count <= rbbb_like_seg_count_next;

                rbbb_segment_seg_count <= rbbb_segment_seg_count_next;

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
