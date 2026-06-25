`timescale 1ns / 1ps



module rbbb_qrs_delay_bank #(

    parameter ABS_DELTA_WIDTH = 13,

    parameter ACTIVITY_MODE = 2,

    parameter LOW_SLOPE_TH = 4,

    parameter ONSET_REF = 200,

    parameter MAX_QRS_OBS_WIN = 200,

    parameter ACTIVITY_GAP_END = 15,

    parameter TERMINAL_START = 90,

    parameter TERMINAL_END = 170,

    parameter WIDE_WIDTH_TH = 120,

    parameter TERMINAL_COUNT_TH = 5,

    parameter RBBB_REPEAT_TH = 3,

    parameter PNN_HIGH_MIS_PCT = 18,

    parameter HIGH_RDM_SUPPRESS = 0,

    parameter HIGH_RDM_MODE = 0,

    parameter HIGH_RDM_LEVEL = 11,

    parameter HIGH_RDM_PCT = 5,

    parameter HIGH_RDM_AVG_CODE = 9

)(

    input clk,

    input rst,

    input clear,

    input sample_valid,

    input segment_done,

    input strong_event,

    input slope_valid,

    input [ABS_DELTA_WIDTH-1:0] abs_delta,

    input pnn_match_spike,

    input pnn_mismatch_spike,

    input rdm_valid_spike,

    input [14:0] rdm_level_spike,

    input [3:0] rdm_level_code,

    output reg qrs_onset_spike,

    output reg qrs_valid_spike,

    output reg wide_qrs_spike,

    output reg terminal_delay_spike,

    output reg rbbb_like_beat_spike,

    output rbbb_segment_spike,

    output low_irregularity,

    output high_rdm_irregularity,

    output reg [7:0] last_matched_width,

    output reg [7:0] terminal_activity_count,

    output reg [7:0] max_last_matched_width,

    output reg [7:0] valid_qrs_count,

    output reg [7:0] wide_qrs_count,

    output reg [7:0] terminal_delay_count,

    output reg [7:0] rbbb_like_beat_count,

    output [119:0] combo_counts_flat

);



    localparam [7:0] ONSET_REF_U = ONSET_REF;

    localparam [7:0] MAX_QRS_OBS_WIN_U = MAX_QRS_OBS_WIN;

    localparam [7:0] ACTIVITY_GAP_END_U = ACTIVITY_GAP_END;

    localparam [7:0] TERMINAL_START_U = TERMINAL_START;

    localparam [7:0] TERMINAL_END_U = TERMINAL_END;

    localparam [7:0] WIDE_WIDTH_TH_U = WIDE_WIDTH_TH;

    localparam [7:0] TERMINAL_COUNT_TH_U = TERMINAL_COUNT_TH;

    localparam [7:0] RBBB_REPEAT_TH_U = RBBB_REPEAT_TH;

    localparam [ABS_DELTA_WIDTH-1:0] LOW_SLOPE_TH_U = LOW_SLOPE_TH;



    reg qrs_active;

    reg prev_activity;

    reg [7:0] onset_ref_cnt;

    reg [7:0] qrs_age;

    reg [7:0] activity_gap_cnt;

    reg [8:0] hyp_match;

    reg [7:0] terminal_count_work;

    reg [15:0] pnn_match_count;

    reg [15:0] pnn_mismatch_count;

    reg [15:0] rdm_valid_count;

    reg [15:0] rdm_high_count;

    reg [19:0] rdm_code_sum;



    reg [7:0] combo_w110_t3;

    reg [7:0] combo_w110_t5;

    reg [7:0] combo_w110_t8;

    reg [7:0] combo_w110_t10;

    reg [7:0] combo_w110_t15;

    reg [7:0] combo_w120_t3;

    reg [7:0] combo_w120_t5;

    reg [7:0] combo_w120_t8;

    reg [7:0] combo_w120_t10;

    reg [7:0] combo_w120_t15;

    reg [7:0] combo_w130_t3;

    reg [7:0] combo_w130_t5;

    reg [7:0] combo_w130_t8;

    reg [7:0] combo_w130_t10;

    reg [7:0] combo_w130_t15;



    reg low_slope_event;

    reg activity_event;

    reg onset_fire;

    reg [7:0] qrs_age_next;

    reg [7:0] gap_next;

    reg [8:0] hyp_match_next;

    reg [7:0] terminal_count_next;

    reg terminal_zone;

    reg qrs_end_fire;

    reg [7:0] last_width_calc;

    reg wide_cond;

    reg terminal_cond;

    reg rbbb_cond;

    reg [16:0] pnn_total_count;

    reg [31:0] pnn_mismatch_x100;

    reg [31:0] pnn_total_x_high;

    reg [31:0] rdm_high_x100;

    reg [31:0] rdm_valid_x_high;

    reg [31:0] rdm_valid_x_avg_code;

    reg high_rdm_rate;

    reg high_rdm_avg;

    reg high_rdm_event;

    integer j;



    always @* begin

        low_slope_event = (abs_delta >= LOW_SLOPE_TH_U);

        activity_event = slope_valid;

        if (ACTIVITY_MODE == 1)

            activity_event = low_slope_event;

        else if (ACTIVITY_MODE == 2)

            activity_event = strong_event | slope_valid;

        else if (ACTIVITY_MODE == 3)

            activity_event = strong_event | low_slope_event;



        onset_fire = sample_valid && activity_event && !prev_activity &&

                     !qrs_active && (onset_ref_cnt == 8'd0);



        qrs_age_next = qrs_age + 8'd1;

        gap_next = activity_event ? 8'd0 :

                   ((activity_gap_cnt != 8'hff) ? (activity_gap_cnt + 8'd1) : activity_gap_cnt);

        terminal_zone = (qrs_age_next >= TERMINAL_START_U) && (qrs_age_next < TERMINAL_END_U);



        hyp_match_next = hyp_match;

        if (activity_event) begin

            if (qrs_age_next == 8'd80)  hyp_match_next[0] = 1'b1;

            if (qrs_age_next == 8'd90)  hyp_match_next[1] = 1'b1;

            if (qrs_age_next == 8'd100) hyp_match_next[2] = 1'b1;

            if (qrs_age_next == 8'd110) hyp_match_next[3] = 1'b1;

            if (qrs_age_next == 8'd120) hyp_match_next[4] = 1'b1;

            if (qrs_age_next == 8'd130) hyp_match_next[5] = 1'b1;

            if (qrs_age_next == 8'd140) hyp_match_next[6] = 1'b1;

            if (qrs_age_next == 8'd150) hyp_match_next[7] = 1'b1;

            if (qrs_age_next == 8'd160) hyp_match_next[8] = 1'b1;

        end



        terminal_count_next = terminal_count_work;

        if (activity_event && terminal_zone && (terminal_count_work != 8'hff))

            terminal_count_next = terminal_count_work + 8'd1;



        qrs_end_fire = sample_valid && qrs_active &&

                       ((qrs_age_next >= MAX_QRS_OBS_WIN_U) ||

                        (gap_next >= ACTIVITY_GAP_END_U));



        if (hyp_match_next[8])      last_width_calc = 8'd160;

        else if (hyp_match_next[7]) last_width_calc = 8'd150;

        else if (hyp_match_next[6]) last_width_calc = 8'd140;

        else if (hyp_match_next[5]) last_width_calc = 8'd130;

        else if (hyp_match_next[4]) last_width_calc = 8'd120;

        else if (hyp_match_next[3]) last_width_calc = 8'd110;

        else if (hyp_match_next[2]) last_width_calc = 8'd100;

        else if (hyp_match_next[1]) last_width_calc = 8'd90;

        else if (hyp_match_next[0]) last_width_calc = 8'd80;

        else                       last_width_calc = 8'd0;



        wide_cond = (last_width_calc >= WIDE_WIDTH_TH_U);

        terminal_cond = (terminal_count_next >= TERMINAL_COUNT_TH_U);

        rbbb_cond = wide_cond && terminal_cond;



        pnn_total_count = {1'b0, pnn_match_count} + {1'b0, pnn_mismatch_count};

        pnn_mismatch_x100 = ({16'd0, pnn_mismatch_count} << 6) +

                            ({16'd0, pnn_mismatch_count} << 5) +

                            ({16'd0, pnn_mismatch_count} << 2);

        pnn_total_x_high = ({15'd0, pnn_total_count} << 4) +

                           ({15'd0, pnn_total_count} << 1);



        high_rdm_event = 1'b0;

        for (j = HIGH_RDM_LEVEL; j < 15; j = j + 1) begin

            if (rdm_level_spike[j])

                high_rdm_event = 1'b1;

        end



        rdm_high_x100 = ({16'd0, rdm_high_count} << 6) +

                        ({16'd0, rdm_high_count} << 5) +

                        ({16'd0, rdm_high_count} << 2);

        if (HIGH_RDM_PCT == 10)

            rdm_valid_x_high = ({16'd0, rdm_valid_count} << 3) + ({16'd0, rdm_valid_count} << 1);

        else

            rdm_valid_x_high = ({16'd0, rdm_valid_count} << 2) + {16'd0, rdm_valid_count};



        if (HIGH_RDM_AVG_CODE == 9)

            rdm_valid_x_avg_code = ({16'd0, rdm_valid_count} << 3) + {16'd0, rdm_valid_count};

        else if (HIGH_RDM_AVG_CODE == 8)

            rdm_valid_x_avg_code = ({16'd0, rdm_valid_count} << 3);

        else if (HIGH_RDM_AVG_CODE == 10)

            rdm_valid_x_avg_code = ({16'd0, rdm_valid_count} << 3) + ({16'd0, rdm_valid_count} << 1);

        else

            rdm_valid_x_avg_code = ({16'd0, rdm_valid_count} << 3) + {16'd0, rdm_valid_count};



        high_rdm_rate = (rdm_valid_count != 16'd0) && (rdm_high_x100 >= rdm_valid_x_high);

        high_rdm_avg = (rdm_valid_count != 16'd0) && ({12'd0, rdm_code_sum} >= rdm_valid_x_avg_code);

    end



    assign low_irregularity = (pnn_total_count == 17'd0) ||

                              (pnn_mismatch_x100 <= pnn_total_x_high);

    assign high_rdm_irregularity = (HIGH_RDM_MODE == 1) ? high_rdm_avg : high_rdm_rate;

    assign rbbb_segment_spike = segment_done && low_irregularity &&

                                ((HIGH_RDM_SUPPRESS == 0) || !high_rdm_irregularity) &&

                                (rbbb_like_beat_count >= RBBB_REPEAT_TH_U);



    assign combo_counts_flat = {

        combo_w130_t15, combo_w130_t10, combo_w130_t8, combo_w130_t5, combo_w130_t3,

        combo_w120_t15, combo_w120_t10, combo_w120_t8, combo_w120_t5, combo_w120_t3,

        combo_w110_t15, combo_w110_t10, combo_w110_t8, combo_w110_t5, combo_w110_t3

    };



    always @(posedge clk) begin

        if (rst) begin

            qrs_active <= 1'b0;

            prev_activity <= 1'b0;

            onset_ref_cnt <= 8'd0;

            qrs_age <= 8'd0;

            activity_gap_cnt <= 8'd0;

            hyp_match <= 9'd0;

            terminal_count_work <= 8'd0;

            pnn_match_count <= 16'd0;

            pnn_mismatch_count <= 16'd0;

            rdm_valid_count <= 16'd0;

            rdm_high_count <= 16'd0;

            rdm_code_sum <= 20'd0;

            qrs_onset_spike <= 1'b0;

            qrs_valid_spike <= 1'b0;

            wide_qrs_spike <= 1'b0;

            terminal_delay_spike <= 1'b0;

            rbbb_like_beat_spike <= 1'b0;

            last_matched_width <= 8'd0;

            terminal_activity_count <= 8'd0;

            max_last_matched_width <= 8'd0;

            valid_qrs_count <= 8'd0;

            wide_qrs_count <= 8'd0;

            terminal_delay_count <= 8'd0;

            rbbb_like_beat_count <= 8'd0;

            combo_w110_t3 <= 8'd0;

            combo_w110_t5 <= 8'd0;

            combo_w110_t8 <= 8'd0;

            combo_w110_t10 <= 8'd0;

            combo_w110_t15 <= 8'd0;

            combo_w120_t3 <= 8'd0;

            combo_w120_t5 <= 8'd0;

            combo_w120_t8 <= 8'd0;

            combo_w120_t10 <= 8'd0;

            combo_w120_t15 <= 8'd0;

            combo_w130_t3 <= 8'd0;

            combo_w130_t5 <= 8'd0;

            combo_w130_t8 <= 8'd0;

            combo_w130_t10 <= 8'd0;

            combo_w130_t15 <= 8'd0;

        end else begin

            qrs_onset_spike <= 1'b0;

            qrs_valid_spike <= 1'b0;

            wide_qrs_spike <= 1'b0;

            terminal_delay_spike <= 1'b0;

            rbbb_like_beat_spike <= 1'b0;



            if (clear) begin

                qrs_active <= 1'b0;

                prev_activity <= 1'b0;

                onset_ref_cnt <= 8'd0;

                qrs_age <= 8'd0;

                activity_gap_cnt <= 8'd0;

                hyp_match <= 9'd0;

                terminal_count_work <= 8'd0;

                pnn_match_count <= 16'd0;

                pnn_mismatch_count <= 16'd0;

                rdm_valid_count <= 16'd0;

                rdm_high_count <= 16'd0;

                rdm_code_sum <= 20'd0;

                last_matched_width <= 8'd0;

                terminal_activity_count <= 8'd0;

                max_last_matched_width <= 8'd0;

                valid_qrs_count <= 8'd0;

                wide_qrs_count <= 8'd0;

                terminal_delay_count <= 8'd0;

                rbbb_like_beat_count <= 8'd0;

                combo_w110_t3 <= 8'd0;

                combo_w110_t5 <= 8'd0;

                combo_w110_t8 <= 8'd0;

                combo_w110_t10 <= 8'd0;

                combo_w110_t15 <= 8'd0;

                combo_w120_t3 <= 8'd0;

                combo_w120_t5 <= 8'd0;

                combo_w120_t8 <= 8'd0;

                combo_w120_t10 <= 8'd0;

                combo_w120_t15 <= 8'd0;

                combo_w130_t3 <= 8'd0;

                combo_w130_t5 <= 8'd0;

                combo_w130_t8 <= 8'd0;

                combo_w130_t10 <= 8'd0;

                combo_w130_t15 <= 8'd0;

            end else begin

                if (pnn_match_spike && (pnn_match_count != 16'hffff))

                    pnn_match_count <= pnn_match_count + 16'd1;

                if (pnn_mismatch_spike && (pnn_mismatch_count != 16'hffff))

                    pnn_mismatch_count <= pnn_mismatch_count + 16'd1;

                if (rdm_valid_spike && (rdm_valid_count != 16'hffff))

                    rdm_valid_count <= rdm_valid_count + 16'd1;

                if (rdm_valid_spike)

                    rdm_code_sum <= rdm_code_sum + {16'd0, rdm_level_code};

                if (rdm_valid_spike && high_rdm_event && (rdm_high_count != 16'hffff))

                    rdm_high_count <= rdm_high_count + 16'd1;



                if (sample_valid) begin

                    prev_activity <= activity_event;

                    if (onset_ref_cnt != 8'd0)

                        onset_ref_cnt <= onset_ref_cnt - 8'd1;



                    if (onset_fire) begin

                        qrs_active <= 1'b1;

                        qrs_onset_spike <= 1'b1;

                        onset_ref_cnt <= ONSET_REF_U;

                        qrs_age <= 8'd0;

                        activity_gap_cnt <= 8'd0;

                        hyp_match <= 9'd0;

                        terminal_count_work <= 8'd0;

                    end else if (qrs_active) begin

                        qrs_age <= qrs_age_next;

                        activity_gap_cnt <= gap_next;

                        hyp_match <= hyp_match_next;

                        terminal_count_work <= terminal_count_next;



                        if (qrs_end_fire) begin

                            qrs_active <= 1'b0;

                            qrs_valid_spike <= 1'b1;

                            wide_qrs_spike <= wide_cond;

                            terminal_delay_spike <= terminal_cond;

                            rbbb_like_beat_spike <= rbbb_cond;

                            last_matched_width <= last_width_calc;

                            terminal_activity_count <= terminal_count_next;

                            if (last_width_calc > max_last_matched_width)

                                max_last_matched_width <= last_width_calc;

                            if (valid_qrs_count != 8'hff)

                                valid_qrs_count <= valid_qrs_count + 8'd1;

                            if (wide_cond && (wide_qrs_count != 8'hff))

                                wide_qrs_count <= wide_qrs_count + 8'd1;

                            if (terminal_cond && (terminal_delay_count != 8'hff))

                                terminal_delay_count <= terminal_delay_count + 8'd1;

                            if (rbbb_cond && (rbbb_like_beat_count != 8'hff))

                                rbbb_like_beat_count <= rbbb_like_beat_count + 8'd1;



                            if ((last_width_calc >= 8'd110) && (terminal_count_next >= 8'd3) && (combo_w110_t3 != 8'hff)) combo_w110_t3 <= combo_w110_t3 + 8'd1;

                            if ((last_width_calc >= 8'd110) && (terminal_count_next >= 8'd5) && (combo_w110_t5 != 8'hff)) combo_w110_t5 <= combo_w110_t5 + 8'd1;

                            if ((last_width_calc >= 8'd110) && (terminal_count_next >= 8'd8) && (combo_w110_t8 != 8'hff)) combo_w110_t8 <= combo_w110_t8 + 8'd1;

                            if ((last_width_calc >= 8'd110) && (terminal_count_next >= 8'd10) && (combo_w110_t10 != 8'hff)) combo_w110_t10 <= combo_w110_t10 + 8'd1;

                            if ((last_width_calc >= 8'd110) && (terminal_count_next >= 8'd15) && (combo_w110_t15 != 8'hff)) combo_w110_t15 <= combo_w110_t15 + 8'd1;

                            if ((last_width_calc >= 8'd120) && (terminal_count_next >= 8'd3) && (combo_w120_t3 != 8'hff)) combo_w120_t3 <= combo_w120_t3 + 8'd1;

                            if ((last_width_calc >= 8'd120) && (terminal_count_next >= 8'd5) && (combo_w120_t5 != 8'hff)) combo_w120_t5 <= combo_w120_t5 + 8'd1;

                            if ((last_width_calc >= 8'd120) && (terminal_count_next >= 8'd8) && (combo_w120_t8 != 8'hff)) combo_w120_t8 <= combo_w120_t8 + 8'd1;

                            if ((last_width_calc >= 8'd120) && (terminal_count_next >= 8'd10) && (combo_w120_t10 != 8'hff)) combo_w120_t10 <= combo_w120_t10 + 8'd1;

                            if ((last_width_calc >= 8'd120) && (terminal_count_next >= 8'd15) && (combo_w120_t15 != 8'hff)) combo_w120_t15 <= combo_w120_t15 + 8'd1;

                            if ((last_width_calc >= 8'd130) && (terminal_count_next >= 8'd3) && (combo_w130_t3 != 8'hff)) combo_w130_t3 <= combo_w130_t3 + 8'd1;

                            if ((last_width_calc >= 8'd130) && (terminal_count_next >= 8'd5) && (combo_w130_t5 != 8'hff)) combo_w130_t5 <= combo_w130_t5 + 8'd1;

                            if ((last_width_calc >= 8'd130) && (terminal_count_next >= 8'd8) && (combo_w130_t8 != 8'hff)) combo_w130_t8 <= combo_w130_t8 + 8'd1;

                            if ((last_width_calc >= 8'd130) && (terminal_count_next >= 8'd10) && (combo_w130_t10 != 8'hff)) combo_w130_t10 <= combo_w130_t10 + 8'd1;

                            if ((last_width_calc >= 8'd130) && (terminal_count_next >= 8'd15) && (combo_w130_t15 != 8'hff)) combo_w130_t15 <= combo_w130_t15 + 8'd1;

                        end

                    end

                end



                if (segment_done) begin

                    qrs_active <= 1'b0;

                    qrs_age <= 8'd0;

                    activity_gap_cnt <= 8'd0;

                    hyp_match <= 9'd0;

                    terminal_count_work <= 8'd0;

                    pnn_match_count <= 16'd0;

                    pnn_mismatch_count <= 16'd0;

                    rdm_valid_count <= 16'd0;

                    rdm_high_count <= 16'd0;

                    rdm_code_sum <= 20'd0;

                    valid_qrs_count <= 8'd0;

                    wide_qrs_count <= 8'd0;

                    terminal_delay_count <= 8'd0;

                    rbbb_like_beat_count <= 8'd0;

                    max_last_matched_width <= 8'd0;

                    combo_w110_t3 <= 8'd0;

                    combo_w110_t5 <= 8'd0;

                    combo_w110_t8 <= 8'd0;

                    combo_w110_t10 <= 8'd0;

                    combo_w110_t15 <= 8'd0;

                    combo_w120_t3 <= 8'd0;

                    combo_w120_t5 <= 8'd0;

                    combo_w120_t8 <= 8'd0;

                    combo_w120_t10 <= 8'd0;

                    combo_w120_t15 <= 8'd0;

                    combo_w130_t3 <= 8'd0;

                    combo_w130_t5 <= 8'd0;

                    combo_w130_t8 <= 8'd0;

                    combo_w130_t10 <= 8'd0;

                    combo_w130_t15 <= 8'd0;

                end

            end

        end

    end



endmodule
