`timescale 1ns / 1ps

module ectopic_pair_neuron #(
    parameter AGE_WIDTH = 12,
    parameter RR_DELTA_TH = 120,
    parameter REF_SHIFT = 4
)(
    input clk,
    input rst,
    input clear,
    input rr_interval_valid_spike,
    input [AGE_WIDTH-1:0] rr_interval_in,
    output reg early_rr_spike,
    output reg late_rr_spike,
    output reg ectopic_pair_spike,
    output reg [AGE_WIDTH-1:0] rr_ref
);

    localparam PAT_NONE  = 2'd0;
    localparam PAT_EARLY = 2'd1;
    localparam PAT_LATE  = 2'd2;
    localparam [AGE_WIDTH-1:0] RR_DELTA = RR_DELTA_TH;

    reg ref_valid;
    reg [1:0] prev_pattern;
    reg [1:0] curr_pattern;
    reg [AGE_WIDTH-1:0] diff_ref;
    reg [AGE_WIDTH-1:0] ref_step;

    always @* begin
        curr_pattern = PAT_NONE;

        if (ref_valid) begin
            if ((rr_interval_in + RR_DELTA) < rr_ref)
                curr_pattern = PAT_EARLY;
            else if (rr_interval_in > (rr_ref + RR_DELTA))
                curr_pattern = PAT_LATE;
        end

        if (rr_interval_in >= rr_ref)
            diff_ref = rr_interval_in - rr_ref;
        else
            diff_ref = rr_ref - rr_interval_in;

        ref_step = diff_ref >> REF_SHIFT;
    end

    always @(posedge clk) begin
        if (rst) begin
            ref_valid <= 1'b0;
            prev_pattern <= PAT_NONE;
            rr_ref <= {AGE_WIDTH{1'b0}};
            early_rr_spike <= 1'b0;
            late_rr_spike <= 1'b0;
            ectopic_pair_spike <= 1'b0;
        end else begin
            early_rr_spike <= 1'b0;
            late_rr_spike <= 1'b0;
            ectopic_pair_spike <= 1'b0;

            if (clear) begin
                ref_valid <= 1'b0;
                prev_pattern <= PAT_NONE;
                rr_ref <= {AGE_WIDTH{1'b0}};
            end else if (rr_interval_valid_spike) begin
                if (!ref_valid) begin
                    rr_ref <= rr_interval_in;
                    ref_valid <= 1'b1;
                    prev_pattern <= PAT_NONE;
                end else begin
                    early_rr_spike <= (curr_pattern == PAT_EARLY);
                    late_rr_spike <= (curr_pattern == PAT_LATE);

                    if ((curr_pattern != PAT_NONE) &&
                        (prev_pattern != PAT_NONE) &&
                        (curr_pattern != prev_pattern))
                        ectopic_pair_spike <= 1'b1;

                    if (curr_pattern != PAT_NONE)
                        prev_pattern <= curr_pattern;

                    if (rr_interval_in >= rr_ref)
                        rr_ref <= rr_ref + ref_step;
                    else
                        rr_ref <= rr_ref - ref_step;
                end
            end
        end
    end

endmodule
