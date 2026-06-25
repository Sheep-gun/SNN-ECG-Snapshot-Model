`timescale 1ns / 1ps

module pnn_rhythm_predictor #(
    parameter NUM_HYP     = 46,
    parameter ID_WIDTH    = 6,
    parameter AGE_WIDTH   = 12,
    parameter BASE_DELAY  = 250,
    parameter DELAY_STEP  = 50,
    parameter WINDOW_HALF = 125
)(
    input clk,
    input rst,
    input clear,
    input rhythm_tick,
    input beat_spike,
    output reg token_active,
    output reg [AGE_WIDTH-1:0] token_age,
    output reg [AGE_WIDTH-1:0] rr_interval,
    output reg [ID_WIDTH-1:0] winner_id,
    output reg [ID_WIDTH-1:0] predictor_id,
    output reg winner_valid,
    output reg predictor_valid,
    output reg [AGE_WIDTH-1:0] winner_error,
    output reg [AGE_WIDTH-1:0] predictor_error,
    output reg pnn_match_spike,
    output reg pnn_mismatch_spike
);

    reg evaluating;
    reg [ID_WIDTH-1:0] eval_idx;
    reg [AGE_WIDTH-1:0] eval_age;
    reg [ID_WIDTH-1:0] eval_best_id;
    reg [AGE_WIDTH-1:0] eval_best_err;
    reg [ID_WIDTH-1:0] eval_predictor_id;
    reg eval_predictor_valid;

    wire [AGE_WIDTH-1:0] age_eval;
    wire [AGE_WIDTH-1:0] scan_center;
    wire [AGE_WIDTH-1:0] scan_err;
    wire scan_better;
    wire [ID_WIDTH-1:0] scan_best_id_next;
    wire [AGE_WIDTH-1:0] scan_best_err_next;
    wire [AGE_WIDTH-1:0] predictor_err_next;
    wire match_next;

    function [AGE_WIDTH-1:0] sat_age_inc;
        input [AGE_WIDTH-1:0] value;
        begin
            if (value == {AGE_WIDTH{1'b1}})
                sat_age_inc = value;
            else
                sat_age_inc = value + 1'b1;
        end
    endfunction

    function [AGE_WIDTH-1:0] hyp_center;
        input [ID_WIDTH-1:0] idx;
        integer center_int;
        begin
            center_int = BASE_DELAY + (idx * DELAY_STEP);
            if (center_int < 0)
                hyp_center = {AGE_WIDTH{1'b0}};
            else if (center_int > ((1 << AGE_WIDTH) - 1))
                hyp_center = {AGE_WIDTH{1'b1}};
            else
                hyp_center = center_int;
        end
    endfunction

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

    assign age_eval = (token_active && rhythm_tick) ? sat_age_inc(token_age) : token_age;
    assign scan_center = hyp_center(eval_idx);
    assign scan_err = abs_diff(eval_age, scan_center);
    assign scan_better = (scan_err < eval_best_err);
    assign scan_best_id_next = scan_better ? eval_idx : eval_best_id;
    assign scan_best_err_next = scan_better ? scan_err : eval_best_err;
    assign predictor_err_next = abs_diff(eval_age, hyp_center(eval_predictor_id));
    assign match_next = eval_predictor_valid && (predictor_err_next <= WINDOW_HALF);

    always @(posedge clk) begin
        if (rst) begin
            token_active <= 1'b0;
            token_age <= {AGE_WIDTH{1'b0}};
            rr_interval <= {AGE_WIDTH{1'b0}};
            winner_id <= {ID_WIDTH{1'b0}};
            predictor_id <= {ID_WIDTH{1'b0}};
            winner_valid <= 1'b0;
            predictor_valid <= 1'b0;
            winner_error <= {AGE_WIDTH{1'b1}};
            predictor_error <= {AGE_WIDTH{1'b1}};
            pnn_match_spike <= 1'b0;
            pnn_mismatch_spike <= 1'b0;
            evaluating <= 1'b0;
            eval_idx <= {ID_WIDTH{1'b0}};
            eval_age <= {AGE_WIDTH{1'b0}};
            eval_best_id <= {ID_WIDTH{1'b0}};
            eval_best_err <= {AGE_WIDTH{1'b1}};
            eval_predictor_id <= {ID_WIDTH{1'b0}};
            eval_predictor_valid <= 1'b0;
        end else begin
            pnn_match_spike <= 1'b0;
            pnn_mismatch_spike <= 1'b0;

            if (clear) begin
                token_active <= 1'b0;
                token_age <= {AGE_WIDTH{1'b0}};
                rr_interval <= {AGE_WIDTH{1'b0}};
                winner_id <= {ID_WIDTH{1'b0}};
                predictor_id <= {ID_WIDTH{1'b0}};
                winner_valid <= 1'b0;
                predictor_valid <= 1'b0;
                winner_error <= {AGE_WIDTH{1'b1}};
                predictor_error <= {AGE_WIDTH{1'b1}};
                pnn_match_spike <= 1'b0;
                pnn_mismatch_spike <= 1'b0;
                evaluating <= 1'b0;
                eval_idx <= {ID_WIDTH{1'b0}};
                eval_age <= {AGE_WIDTH{1'b0}};
                eval_best_id <= {ID_WIDTH{1'b0}};
                eval_best_err <= {AGE_WIDTH{1'b1}};
                eval_predictor_id <= {ID_WIDTH{1'b0}};
                eval_predictor_valid <= 1'b0;
            end else if (beat_spike) begin
                if (token_active) begin
                    rr_interval <= age_eval;
                    eval_age <= age_eval;
                    eval_idx <= {ID_WIDTH{1'b0}};
                    eval_best_id <= {ID_WIDTH{1'b0}};
                    eval_best_err <= {AGE_WIDTH{1'b1}};
                    eval_predictor_id <= predictor_id;
                    eval_predictor_valid <= predictor_valid;
                    evaluating <= 1'b1;
                end else begin
                    winner_valid <= 1'b0;
                    predictor_valid <= 1'b0;
                    predictor_error <= {AGE_WIDTH{1'b1}};
                    evaluating <= 1'b0;
                end

                token_active <= 1'b1;
                token_age <= {AGE_WIDTH{1'b0}};
            end else begin
                if (evaluating) begin
                    if (eval_idx == (NUM_HYP - 1)) begin
                        winner_id <= scan_best_id_next;
                        winner_error <= scan_best_err_next;
                        winner_valid <= 1'b1;
                        predictor_id <= scan_best_id_next;
                        predictor_valid <= 1'b1;
                        evaluating <= 1'b0;

                        if (eval_predictor_valid) begin
                            predictor_error <= predictor_err_next;
                            pnn_match_spike <= match_next;
                            pnn_mismatch_spike <= !match_next;
                        end else begin
                            predictor_error <= {AGE_WIDTH{1'b1}};
                        end
                    end else begin
                        eval_best_id <= scan_best_id_next;
                        eval_best_err <= scan_best_err_next;
                        eval_idx <= eval_idx + 1'b1;
                    end
                end

                if (rhythm_tick && token_active)
                    token_age <= sat_age_inc(token_age);
            end
        end
    end

endmodule
