`timescale 1ns / 1ps

module rcd_feature #(
    parameter QRS_OBS_WIN = 180,
    parameter TERMINAL_START = 40,
    parameter TERMINAL_END = 140,
    parameter T_QRS_WIDTH_CNT = 120,
    parameter T_TERMINAL_CNT = 3,
    parameter T_RCD_COUNT = 1,
    parameter SUBWINDOW_TICKS = 60000,
    parameter REG_GATE_ENABLE = 1,
    parameter HIGH_RDM_LEVEL = 9,
    parameter ACTIVITY_MODE = 2
)(
    input clk,
    input rst,
    input clear,
    input sample_valid,
    input rhythm_tick,
    input segment_done,
    input beat_spike,
    input strong_event,
    input slope_valid,
    input pnn_mismatch_spike,
    input rdm_valid_spike,
    input [14:0] rdm_level_spike,
    input qrs_maf_valid_spike,
    input qrs_width_abn_spike,
    input [7:0] qrs_width_value,
    output rcd_valid_beat_spike,
    output rcd_width_gate_spike,
    output rcd_terminal_gate_spike,
    output rcd_beat_spike,
    output rcd_segment_spike,
    output [7:0] rcd_terminal_count,
    output [7:0] rcd_width_value,
    output [7:0] rcd_beat_count,
    output [7:0] rcd_valid_count
);
    assign rcd_valid_beat_spike = 1'b0;
    assign rcd_width_gate_spike = 1'b0;
    assign rcd_terminal_gate_spike = 1'b0;
    assign rcd_beat_spike = 1'b0;
    assign rcd_segment_spike = 1'b0;
    assign rcd_terminal_count = 8'd0;
    assign rcd_width_value = 8'd0;
    assign rcd_beat_count = 8'd0;
    assign rcd_valid_count = 8'd0;
endmodule

module rcd2_feature #(
    parameter ADC_WIDTH = 12,
    parameter ABS_DELTA_WIDTH = 13,
    parameter PRE_WIN = 80,
    parameter POST_WIN = 140,
    parameter TERMINAL_START = 40,
    parameter TERMINAL_END = 140,
    parameter LOW_SLOPE_TH = 4,
    parameter FOOTPRINT_TH = 110,
    parameter TERMINAL_COUNT_TH = 10,
    parameter RCD2_COUNT_TH = 2,
    parameter SUBWINDOW_TICKS = 60000,
    parameter HIGH_RDM_LEVEL = 9,
    parameter HIGH_IRR_SUPPRESS = 1
)(
    input clk,
    input rst,
    input clear,
    input sample_valid,
    input rhythm_tick,
    input segment_done,
    input beat_spike,
    input strong_event,
    input [ABS_DELTA_WIDTH-1:0] abs_delta,
    input pnn_mismatch_spike,
    input rdm_valid_spike,
    input [14:0] rdm_level_spike,
    output rcd2_valid_beat_spike,
    output rcd2_width_gate_spike,
    output rcd2_terminal_gate_spike,
    output rcd2_beat_spike,
    output rcd2_segment_spike,
    output [7:0] rcd2_footprint_value,
    output [7:0] rcd2_terminal_count,
    output [7:0] rcd2_beat_count,
    output [7:0] rcd2_valid_count
);
    assign rcd2_valid_beat_spike = 1'b0;
    assign rcd2_width_gate_spike = 1'b0;
    assign rcd2_terminal_gate_spike = 1'b0;
    assign rcd2_beat_spike = 1'b0;
    assign rcd2_segment_spike = 1'b0;
    assign rcd2_footprint_value = 8'd0;
    assign rcd2_terminal_count = 8'd0;
    assign rcd2_beat_count = 8'd0;
    assign rcd2_valid_count = 8'd0;
endmodule

module ipb_feature #(
    parameter BIN_TICKS = 10000,
    parameter SUBWINDOW_TICKS = 60000,
    parameter RDM_MID_LEVEL = 4,
    parameter RDM_HIGH_LEVEL = 9,
    parameter T_BIN_MID = 2,
    parameter T_BIN_HIGH = 5,
    parameter T_PERSIST_BINS = 4,
    parameter T_BURST_BINS = 1
)(
    input clk,
    input rst,
    input clear,
    input rhythm_tick,
    input segment_done,
    input pnn_mismatch_spike,
    input rdm_valid_spike,
    input [14:0] rdm_level_spike,
    output persistent_irreg_spike,
    output episodic_irreg_spike,
    output burst_irreg_spike,
    output [7:0] high_irreg_bin_count,
    output [7:0] mid_irreg_bin_count,
    output [7:0] low_irreg_bin_count,
    output [7:0] burst_count,
    output [7:0] current_bin_irreg_count
);
    assign persistent_irreg_spike = 1'b0;
    assign episodic_irreg_spike = 1'b0;
    assign burst_irreg_spike = 1'b0;
    assign high_irreg_bin_count = 8'd0;
    assign mid_irreg_bin_count = 8'd0;
    assign low_irreg_bin_count = 8'd0;
    assign burst_count = 8'd0;
    assign current_bin_irreg_count = 8'd0;
endmodule

module nsr_normality_gate #(
    parameter PRE_WIN = 80,
    parameter POST_WIN = 140,
    parameter TERMINAL_START = 40,
    parameter TERMINAL_END = 140,
    parameter FOOTPRINT_TH = 100,
    parameter FOOTPRINT_MAX_TH = 160,
    parameter TERMINAL_COUNT_TH = 40,
    parameter REPEAT_COUNT_TH = 2,
    parameter PNN_HIGH_MIS_PCT = 18
)(
    input clk,
    input rst,
    input clear,
    input sample_valid,
    input segment_done,
    input beat_spike,
    input slope_valid,
    input pnn_match_spike,
    input pnn_mismatch_spike,
    output nsr_gate_valid_beat_spike,
    output nsr_gate_width_gate_spike,
    output nsr_gate_terminal_gate_spike,
    output nsr_gate_abnormal_beat_spike,
    output nsr_suppress_spike,
    output rbbb_strict_gate,
    output low_irregularity,
    output [7:0] qrs_footprint_width,
    output [7:0] terminal_activity_count,
    output [7:0] repeated_abnormal_beat_count,
    output [7:0] valid_beat_count
);
    assign nsr_gate_valid_beat_spike = 1'b0;
    assign nsr_gate_width_gate_spike = 1'b0;
    assign nsr_gate_terminal_gate_spike = 1'b0;
    assign nsr_gate_abnormal_beat_spike = 1'b0;
    assign nsr_suppress_spike = 1'b0;
    assign rbbb_strict_gate = 1'b0;
    assign low_irregularity = 1'b0;
    assign qrs_footprint_width = 8'd0;
    assign terminal_activity_count = 8'd0;
    assign repeated_abnormal_beat_count = 8'd0;
    assign valid_beat_count = 8'd0;
endmodule

module rbbb_lateslope_gate #(
    parameter LATE_START = 60,
    parameter LATE_END = 160,
    parameter LATE_SUM_TH = 665,
    parameter LATE_GATE_MODE = 0,
    parameter LATE_GATE_TH = 665,
    parameter LATE_COUNT_TH = 6,
    parameter PNN_HIGH_MIS_PCT = 18
)(
    input clk,
    input rst,
    input clear,
    input sample_valid,
    input segment_done,
    input beat_spike,
    input slope_valid,
    input pnn_match_spike,
    input pnn_mismatch_spike,
    output late_beat_valid_spike,
    output [7:0] late_slope_count,
    output [15:0] late_slope_sum,
    output [7:0] late_slope_max,
    output [7:0] late_ge_count,
    output [15:0] late_top2_sum,
    output [15:0] late_top3_sum,
    output [15:0] late_top5_sum,
    output rbbb_lateslope_gate_spike,
    output rbbb_lateslope_gate_level,
    output low_irregularity
);
    assign late_beat_valid_spike = 1'b0;
    assign late_slope_count = 8'd0;
    assign late_slope_sum = 16'd0;
    assign late_slope_max = 8'd0;
    assign late_ge_count = 8'd0;
    assign late_top2_sum = 16'd0;
    assign late_top3_sum = 16'd0;
    assign late_top5_sum = 16'd0;
    assign rbbb_lateslope_gate_spike = 1'b0;
    assign rbbb_lateslope_gate_level = 1'b0;
    assign low_irregularity = 1'b0;
endmodule

module etmc_feature #(
    parameter AGE_WIDTH = 12,
    parameter RAM_CODE_WIDTH = 6,
    parameter T_EARLY = 120,
    parameter T_LATE = 150,
    parameter T_RAM_DELTA = 3,
    parameter MORPH_MODE = 2,
    parameter SPIKE_MODE = 3
)(
    input clk,
    input rst,
    input clear,
    input rr_interval_valid_spike,
    input [AGE_WIDTH-1:0] rr_interval_in,
    input pnn_mismatch_spike,
    input [14:0] rdm_level_spike,
    input ram_amp_spike,
    input [RAM_CODE_WIDTH-1:0] ram_amp_code,
    input qrs_maf_valid_spike,
    input qrs_width_abn_spike,
    input qrs_energy_abn_spike,
    output etmc_early_spike,
    output etmc_late_spike,
    output etmc_qrs_abn_spike,
    output etmc_candidate_spike,
    output etmc_compensation_spike,
    output etmc_spike,
    output [AGE_WIDTH-1:0] etmc_rr_ref
);
    assign etmc_early_spike = 1'b0;
    assign etmc_late_spike = 1'b0;
    assign etmc_qrs_abn_spike = 1'b0;
    assign etmc_candidate_spike = 1'b0;
    assign etmc_compensation_spike = 1'b0;
    assign etmc_spike = 1'b0;
    assign etmc_rr_ref = {AGE_WIDTH{1'b0}};
endmodule
