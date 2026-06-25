`timescale 1ns / 1ps

module rdm_variability_neuron #(
    parameter AGE_WIDTH = 12,
    parameter DIFF_TH0 = 10,
    parameter DIFF_TH1 = 20,
    parameter DIFF_TH2 = 30,
    parameter DIFF_TH3 = 40,
    parameter DIFF_TH4 = 50,
    parameter DIFF_TH5 = 60,
    parameter DIFF_TH6 = 70,
    parameter DIFF_TH7 = 80,
    parameter DIFF_TH8 = 90,
    parameter DIFF_TH9 = 100,
    parameter DIFF_TH10 = 110,
    parameter DIFF_TH11 = 120,
    parameter DIFF_TH12 = 130,
    parameter DIFF_TH13 = 140,
    parameter DIFF_TH14 = 150
)(
    input clk,
    input rst,
    input clear,
    input rr_interval_valid_spike,
    input [AGE_WIDTH-1:0] rr_interval_in,
    output reg rr_diff_valid_spike,
    output reg [14:0] rdm_level_spike,
    output reg [3:0] rdm_level_code,
    output reg [AGE_WIDTH-1:0] current_rr,
    output reg [AGE_WIDTH-1:0] prev_rr,
    output reg [AGE_WIDTH-1:0] rr_diff
);

    reg prev_rr_valid;

    reg [AGE_WIDTH-1:0] diff_next;
    reg [14:0] level_next;
    reg [3:0] code_next;

    function [AGE_WIDTH-1:0] abs_diff;
        input [AGE_WIDTH-1:0] a;
        input [AGE_WIDTH-1:0] b;
        begin
            if (a >= b)
                abs_diff = a - b;
            else
                abs_diff = b - a;
        end
    endfunction

    always @* begin
        diff_next = abs_diff(rr_interval_in, prev_rr);
        level_next = 15'b000000000000000;

        if (diff_next >= DIFF_TH0)
            level_next[0] = 1'b1;
        if (diff_next >= DIFF_TH1)
            level_next[1] = 1'b1;
        if (diff_next >= DIFF_TH2)
            level_next[2] = 1'b1;
        if (diff_next >= DIFF_TH3)
            level_next[3] = 1'b1;
        if (diff_next >= DIFF_TH4)
            level_next[4] = 1'b1;
        if (diff_next >= DIFF_TH5)
            level_next[5] = 1'b1;
        if (diff_next >= DIFF_TH6)
            level_next[6] = 1'b1;
        if (diff_next >= DIFF_TH7)
            level_next[7] = 1'b1;
        if (diff_next >= DIFF_TH8)
            level_next[8] = 1'b1;
        if (diff_next >= DIFF_TH9)
            level_next[9] = 1'b1;
        if (diff_next >= DIFF_TH10)
            level_next[10] = 1'b1;
        if (diff_next >= DIFF_TH11)
            level_next[11] = 1'b1;
        if (diff_next >= DIFF_TH12)
            level_next[12] = 1'b1;
        if (diff_next >= DIFF_TH13)
            level_next[13] = 1'b1;
        if (diff_next >= DIFF_TH14)
            level_next[14] = 1'b1;

        if (level_next[14])
            code_next = 4'd15;
        else if (level_next[13])
            code_next = 4'd14;
        else if (level_next[12])
            code_next = 4'd13;
        else if (level_next[11])
            code_next = 4'd12;
        else if (level_next[10])
            code_next = 4'd11;
        else if (level_next[9])
            code_next = 4'd10;
        else if (level_next[8])
            code_next = 4'd9;
        else if (level_next[7])
            code_next = 4'd8;
        else if (level_next[6])
            code_next = 4'd7;
        else if (level_next[5])
            code_next = 4'd6;
        else if (level_next[4])
            code_next = 4'd5;
        else if (level_next[3])
            code_next = 4'd4;
        else if (level_next[2])
            code_next = 4'd3;
        else if (level_next[1])
            code_next = 4'd2;
        else if (level_next[0])
            code_next = 4'd1;
        else
            code_next = 4'd0;
    end

    always @(posedge clk) begin
        if (rst) begin
            prev_rr_valid <= 1'b0;
            current_rr <= {AGE_WIDTH{1'b0}};
            prev_rr <= {AGE_WIDTH{1'b0}};
            rr_diff <= {AGE_WIDTH{1'b0}};
            rr_diff_valid_spike <= 1'b0;
            rdm_level_spike <= 15'b000000000000000;
            rdm_level_code <= 4'd0;
        end else begin
            rr_diff_valid_spike <= 1'b0;
            rdm_level_spike <= 15'b000000000000000;
            rdm_level_code <= 4'd0;

            if (clear) begin
                prev_rr_valid <= 1'b0;
                current_rr <= {AGE_WIDTH{1'b0}};
                prev_rr <= {AGE_WIDTH{1'b0}};
                rr_diff <= {AGE_WIDTH{1'b0}};
            end else if (rr_interval_valid_spike) begin
                current_rr <= rr_interval_in;

                if (prev_rr_valid) begin
                    rr_diff <= diff_next;
                    rr_diff_valid_spike <= 1'b1;
                    rdm_level_spike <= level_next;
                    rdm_level_code <= code_next;
                end

                prev_rr <= rr_interval_in;
                prev_rr_valid <= 1'b1;
            end
        end
    end

endmodule
