`timescale 1ns / 1ps

// Strict no-oracle record-level final membrane layer.
// Selected by:
//   results/final_membrane_30min_recordwise/
//     no_oracle_record_level_strict_selected_params.json
//
// Python-selected rule:
//   base score = record-level accumulated snapshot pred counts
//   if record_arr_count >= 5: ARR score += 16
//   WTA tie order = NSR, CHF, ARR, AFF
//
// This module receives one spike event per completed 30-minute chunk. The
// chunk inputs are raw counts of the 30 snapshot predictions inside that chunk.
module record_level_final_membrane_layer(
    input clk,
    input rst,
    input clear,
    input chunk_done,
    input record_done,
    input [5:0] chunk_count_nsr,
    input [5:0] chunk_count_chf,
    input [5:0] chunk_count_arr,
    input [5:0] chunk_count_aff,
    output reg final_valid,
    output reg [1:0] final_pred_class,
    output reg signed [31:0] final_mem_nsr,
    output reg signed [31:0] final_mem_chf,
    output reg signed [31:0] final_mem_arr,
    output reg signed [31:0] final_mem_aff
);

    localparam [15:0] ARR_TH = 16'd5;
    localparam signed [31:0] ARR_BOOST = 32'sd16;

    reg [15:0] count_nsr;
    reg [15:0] count_chf;
    reg [15:0] count_arr;
    reg [15:0] count_aff;

    reg [15:0] nsr_next;
    reg [15:0] chf_next;
    reg [15:0] arr_next;
    reg [15:0] aff_next;

    reg signed [31:0] score_nsr;
    reg signed [31:0] score_chf;
    reg signed [31:0] score_arr;
    reg signed [31:0] score_aff;
    reg signed [31:0] best_score;
    reg [1:0] best_class;

    always @(*) begin
        nsr_next = count_nsr + {10'd0, chunk_count_nsr};
        chf_next = count_chf + {10'd0, chunk_count_chf};
        arr_next = count_arr + {10'd0, chunk_count_arr};
        aff_next = count_aff + {10'd0, chunk_count_aff};

        score_nsr = {{16{1'b0}}, nsr_next};
        score_chf = {{16{1'b0}}, chf_next};
        score_arr = {{16{1'b0}}, arr_next};
        score_aff = {{16{1'b0}}, aff_next};

        if (arr_next >= ARR_TH)
            score_arr = score_arr + ARR_BOOST;

        best_class = 2'd0;
        best_score = score_nsr;
        if (score_chf > best_score) begin
            best_score = score_chf;
            best_class = 2'd1;
        end
        if (score_arr > best_score) begin
            best_score = score_arr;
            best_class = 2'd2;
        end
        if (score_aff > best_score) begin
            best_score = score_aff;
            best_class = 2'd3;
        end
    end

    always @(posedge clk) begin
        if (rst || clear) begin
            count_nsr <= 16'd0;
            count_chf <= 16'd0;
            count_arr <= 16'd0;
            count_aff <= 16'd0;
            final_valid <= 1'b0;
            final_pred_class <= 2'd0;
            final_mem_nsr <= 32'sd0;
            final_mem_chf <= 32'sd0;
            final_mem_arr <= 32'sd0;
            final_mem_aff <= 32'sd0;
        end else begin
            final_valid <= 1'b0;
            if (chunk_done) begin
                count_nsr <= nsr_next;
                count_chf <= chf_next;
                count_arr <= arr_next;
                count_aff <= aff_next;
                final_mem_nsr <= score_nsr;
                final_mem_chf <= score_chf;
                final_mem_arr <= score_arr;
                final_mem_aff <= score_aff;
                if (record_done) begin
                    final_valid <= 1'b1;
                    final_pred_class <= best_class;
                end
            end
        end
    end

endmodule
