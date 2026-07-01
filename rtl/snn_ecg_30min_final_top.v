`timescale 1ns / 1ps

// Full 30-minute stream top.
//
// The timer neuron integrates accepted ADC sample ticks. When its membrane
// reaches SNAPSHOT_SAMPLES, it emits a snapshot boundary spike, drives
// Snapshot V2 segment_done, resets itself, and starts the next 60s snapshot.
// Each snapshot spike then stimulates the final membrane layer with class
// spikes and feature-evidence neuron activity.
module snn_ecg_30min_final_top #(
    parameter ADC_WIDTH = 12,
    parameter SNAPSHOT_SAMPLES = 60000,
    parameter SNAPSHOTS_PER_CHUNK = 30,
    parameter POST_DONE_TICKS = 9
)(
    input clk,
    input rst,
    input start,
    input sample_valid,
    input signed [ADC_WIDTH-1:0] adc_data,
    output sample_ready,
    output busy,
    output final_valid,
    output [1:0] final_pred_class,
    output signed [31:0] final_mem_nsr,
    output signed [31:0] final_mem_chf,
    output signed [31:0] final_mem_arr,
    output signed [31:0] final_mem_aff,
    output [5:0] snapshot_index_dbg
);

    localparam ST_IDLE       = 4'd0;
    localparam ST_CORE_RESET = 4'd1;
    localparam ST_SEG_START  = 4'd2;
    localparam ST_RUN        = 4'd3;
    localparam ST_SEG_DONE   = 4'd4;
    localparam ST_FLUSH      = 4'd5;
    localparam ST_COMMIT     = 4'd6;
    localparam ST_DONE       = 4'd7;

    reg [3:0] state;
    reg [3:0] reset_count;
    reg [3:0] flush_count;
    reg [31:0] timer_mem;
    reg [5:0] snapshot_index;

    wire core_rst = rst || (state == ST_CORE_RESET);
    wire core_segment_start = (state == ST_SEG_START);
    wire core_segment_done = (state == ST_SEG_DONE);
    wire core_sample_valid = (state == ST_RUN) && sample_valid && sample_ready;
    wire core_rhythm_tick = core_sample_valid;
    wire sample_tick_spike = core_sample_valid;
    wire snapshot_boundary_spike = sample_tick_spike && (timer_mem == (SNAPSHOT_SAMPLES - 1));
    wire final_clear = (state == ST_SEG_START) && (snapshot_index == 6'd0);
    wire final_snapshot_done = (state == ST_COMMIT);
    wire final_chunk_done = (state == ST_COMMIT) && (snapshot_index == (SNAPSHOTS_PER_CHUNK - 1));

    assign sample_ready = (state == ST_RUN);
    assign busy = (state != ST_IDLE) && (state != ST_DONE);
    assign snapshot_index_dbg = snapshot_index;

    wire beat_spike;
    wire pnn_match_spike;
    wire pnn_mismatch_spike;
    wire dscr_valid_slope_spike;
    wire dscr_sign_flip_spike;
    wire ram_amp_spike;
    wire [5:0] ram_amp_code;
    wire rdm_valid_spike;
    wire [14:0] rdm_level_spike;
    wire [3:0] rdm_level_code;
    wire ectopic_pair_spike;
    wire qrs_maf_spike;
    wire qrs_width_abn_spike;
    wire qrs_complex_abn_spike;
    wire qrs_energy_abn_spike;
    wire pre_qrs_bump_spike;
    wire rbbb_qrs_like_beat_spike;
    wire rbbb_qrs_delay_applied;
    wire [1:0] snapshot_pred_class;
    wire snapshot_pred_valid;
    wire signed [63:0] c24_mem_nsr;
    wire signed [63:0] c24_mem_chf;
    wire signed [63:0] c24_mem_arr;
    wire signed [63:0] c24_mem_aff;

    reg [31:0] beat_count;
    reg [31:0] pnn_match_count;
    reg [31:0] pnn_mismatch_count;
    reg [31:0] dscr_flip_count;
    reg [31:0] dscr_slope_count;
    reg [31:0] ram_code_sum;
    reg [31:0] ram_code_count;
    reg [31:0] rdm_valid_count;
    reg [31:0] rdm_code_sum;
    reg [31:0] rdm_ge50_count;
    reg [31:0] rdm_ge100_count;
    reg [31:0] ectopic_pair_count;
    reg [31:0] qrs_maf_count;
    reg [31:0] qrs_width_abn_count;
    reg [31:0] qrs_complex_abn_count;
    reg [31:0] qrs_energy_abn_count;
    reg [31:0] rbbb_delay_like_count;
    reg [31:0] rbbb_delay_applied_count;
    reg [31:0] pre_qrs_bump_count;

    wire [31:0] pnn_decision_count = pnn_match_count + pnn_mismatch_count;
    wire [31:0] rhythm_irregular_evidence_count = pnn_mismatch_count + rdm_code_sum + ectopic_pair_count;
    wire [31:0] morphology_evidence_count = dscr_flip_count + qrs_maf_count + qrs_width_abn_count +
                                             qrs_complex_abn_count + qrs_energy_abn_count +
                                             rbbb_delay_like_count;
    wire [31:0] abnormal_evidence_count = pnn_mismatch_count + ectopic_pair_count + qrs_maf_count +
                                           qrs_width_abn_count + qrs_complex_abn_count +
                                           qrs_energy_abn_count + rbbb_delay_like_count;

    snn_ecg_3feat_top #(
        .ADC_WIDTH(12),
        .EVENT_TH(5),
        .SLOPE_TH(4),
        .ENABLE_AMP_EVENT(0),
        .AMP_EVENT_TH(4),
        .ENABLE_ADAPTIVE_QRS_EVENT(1),
        .ADAPT_QRS_USE_BANK(1),
        .ADAPT_QRS_CALIB_SAMPLES(2000),
        .ADAPT_QRS_MIN_EVENT_TH(4),
        .ADAPT_QRS_PCT_TARGET(1900),
        .ADAPT_QRS_TARGET_EVENT_COUNT(100),
        .ENABLE_INPUT_NORMALIZER(0),
        .NORM_BASE_SHIFT(8),
        .NORM_ENV_DECAY_SHIFT(6),
        .NORM_GAIN_LOW_TH(96),
        .NORM_GAIN_MID_TH(192),
        .NORM_GAIN_HIGH_TH(768),
        .NORM_ENABLE_ADAPTIVE_GAIN(0),
        .QRS_MEM_W(12),
        .QRS_REF_W(10),
        .QRS_W_EVENT(8),
        .QRS_LEAK(0),
        .QRS_TH(16),
        .QRS_REF(280),
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
    ) u_snapshot (
        .clk(clk),
        .rst(core_rst),
        .sample_valid(core_sample_valid),
        .rhythm_tick(core_rhythm_tick),
        .segment_start(core_segment_start),
        .segment_done(core_segment_done),
        .adc_data(adc_data),
        .beat_spike(beat_spike),
        .pnn_match_spike(pnn_match_spike),
        .pnn_mismatch_spike(pnn_mismatch_spike),
        .dscr_valid_slope_spike(dscr_valid_slope_spike),
        .dscr_sign_flip_spike(dscr_sign_flip_spike),
        .ram_amp_spike(ram_amp_spike),
        .ram_amp_code(ram_amp_code),
        .rdm_valid_spike(rdm_valid_spike),
        .rdm_level_spike(rdm_level_spike),
        .rdm_level_code(rdm_level_code),
        .ectopic_pair_spike(ectopic_pair_spike),
        .qrs_maf_spike(qrs_maf_spike),
        .qrs_width_abn_spike(qrs_width_abn_spike),
        .qrs_complex_abn_spike(qrs_complex_abn_spike),
        .qrs_energy_abn_spike(qrs_energy_abn_spike),
        .pre_qrs_bump_spike(pre_qrs_bump_spike),
        .rbbb_qrs_like_beat_spike(rbbb_qrs_like_beat_spike),
        .rbbb_qrs_delay_applied(rbbb_qrs_delay_applied),
        .c24_mem_nsr(c24_mem_nsr),
        .c24_mem_chf(c24_mem_chf),
        .c24_mem_arr(c24_mem_arr),
        .c24_mem_aff(c24_mem_aff),
        .pred_class(snapshot_pred_class),
        .pred_valid(snapshot_pred_valid)
    );

    final_membrane_layer u_final (
        .clk(clk),
        .rst(rst),
        .clear(final_clear),
        .snapshot_done(final_snapshot_done),
        .chunk_done(final_chunk_done),
        .pred_valid(snapshot_pred_valid),
        .pred_class(snapshot_pred_class),
        .class_mem_nsr(c24_mem_nsr),
        .class_mem_chf(c24_mem_chf),
        .class_mem_arr(c24_mem_arr),
        .class_mem_aff(c24_mem_aff),
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

    always @(posedge clk) begin
        if (rst) begin
            state <= ST_IDLE;
            reset_count <= 4'd0;
            flush_count <= 4'd0;
            timer_mem <= 32'd0;
            snapshot_index <= 6'd0;
        end else begin
            case (state)
                ST_IDLE: begin
                    if (start) begin
                        state <= ST_CORE_RESET;
                        reset_count <= 4'd0;
                        snapshot_index <= 6'd0;
                    end
                end
                ST_CORE_RESET: begin
                    if (reset_count == 4'd3) begin
                        state <= ST_SEG_START;
                        reset_count <= 4'd0;
                    end else begin
                        reset_count <= reset_count + 4'd1;
                    end
                end
                ST_SEG_START: begin
                    timer_mem <= 32'd0;
                    state <= ST_RUN;
                end
                ST_RUN: begin
                    if (sample_tick_spike) begin
                        if (snapshot_boundary_spike) begin
                            timer_mem <= 32'd0;
                            state <= ST_SEG_DONE;
                        end else begin
                            timer_mem <= timer_mem + 32'd1;
                        end
                    end
                end
                ST_SEG_DONE: begin
                    flush_count <= 4'd0;
                    state <= ST_FLUSH;
                end
                ST_FLUSH: begin
                    if (flush_count == (POST_DONE_TICKS - 1)) begin
                        flush_count <= 4'd0;
                        state <= ST_COMMIT;
                    end else begin
                        flush_count <= flush_count + 4'd1;
                    end
                end
                ST_COMMIT: begin
                    if (snapshot_index == (SNAPSHOTS_PER_CHUNK - 1)) begin
                        state <= ST_DONE;
                    end else begin
                        snapshot_index <= snapshot_index + 6'd1;
                        state <= ST_CORE_RESET;
                    end
                end
                ST_DONE: begin
                    if (!start)
                        state <= ST_IDLE;
                end
                default: state <= ST_IDLE;
            endcase
        end
    end

    always @(posedge clk) begin
        if (rst || core_segment_start) begin
            beat_count <= 32'd0;
            pnn_match_count <= 32'd0;
            pnn_mismatch_count <= 32'd0;
            dscr_flip_count <= 32'd0;
            dscr_slope_count <= 32'd0;
            ram_code_sum <= 32'd0;
            ram_code_count <= 32'd0;
            rdm_valid_count <= 32'd0;
            rdm_code_sum <= 32'd0;
            rdm_ge50_count <= 32'd0;
            rdm_ge100_count <= 32'd0;
            ectopic_pair_count <= 32'd0;
            qrs_maf_count <= 32'd0;
            qrs_width_abn_count <= 32'd0;
            qrs_complex_abn_count <= 32'd0;
            qrs_energy_abn_count <= 32'd0;
            rbbb_delay_like_count <= 32'd0;
            rbbb_delay_applied_count <= 32'd0;
            pre_qrs_bump_count <= 32'd0;
        end else if ((state == ST_RUN) || (state == ST_SEG_DONE) || (state == ST_FLUSH)) begin
            if (beat_spike)
                beat_count <= beat_count + 32'd1;
            if (pnn_match_spike)
                pnn_match_count <= pnn_match_count + 32'd1;
            if (pnn_mismatch_spike)
                pnn_mismatch_count <= pnn_mismatch_count + 32'd1;
            if (dscr_valid_slope_spike)
                dscr_slope_count <= dscr_slope_count + 32'd1;
            if (dscr_sign_flip_spike)
                dscr_flip_count <= dscr_flip_count + 32'd1;
            if (ram_amp_spike) begin
                ram_code_sum <= ram_code_sum + {26'd0, ram_amp_code};
                ram_code_count <= ram_code_count + 32'd1;
            end
            if (rdm_valid_spike) begin
                rdm_valid_count <= rdm_valid_count + 32'd1;
                rdm_code_sum <= rdm_code_sum + {28'd0, rdm_level_code};
                if (rdm_level_spike[4])
                    rdm_ge50_count <= rdm_ge50_count + 32'd1;
                if (rdm_level_spike[9])
                    rdm_ge100_count <= rdm_ge100_count + 32'd1;
            end
            if (ectopic_pair_spike)
                ectopic_pair_count <= ectopic_pair_count + 32'd1;
            if (qrs_maf_spike)
                qrs_maf_count <= qrs_maf_count + 32'd1;
            if (qrs_width_abn_spike)
                qrs_width_abn_count <= qrs_width_abn_count + 32'd1;
            if (qrs_complex_abn_spike)
                qrs_complex_abn_count <= qrs_complex_abn_count + 32'd1;
            if (qrs_energy_abn_spike)
                qrs_energy_abn_count <= qrs_energy_abn_count + 32'd1;
            if (rbbb_qrs_like_beat_spike)
                rbbb_delay_like_count <= rbbb_delay_like_count + 32'd1;
            if (rbbb_qrs_delay_applied)
                rbbb_delay_applied_count <= rbbb_delay_applied_count + 32'd1;
            if (pre_qrs_bump_spike)
                pre_qrs_bump_count <= pre_qrs_bump_count + 32'd1;
        end
    end

endmodule
