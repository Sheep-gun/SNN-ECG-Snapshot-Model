`timescale 1ns / 1ps

module tb_board_demo_core_timing;
    reg clk;
    reg rst;
    reg sample_valid;
    reg rhythm_tick;
    reg segment_start;
    reg segment_done;
    reg signed [11:0] adc_data;
    wire [1:0] pred_class;
    wire pred_valid;

    reg [11:0] sample_mem [0:59999];
    integer i;

    snn_ecg_model_a_plus_core dut (
        .clk(clk),
        .rst(rst),
        .sample_valid(sample_valid),
        .rhythm_tick(rhythm_tick),
        .segment_start(segment_start),
        .segment_done(segment_done),
        .adc_data(adc_data),
        .pred_class(pred_class),
        .pred_valid(pred_valid)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    task reset_dut;
        begin
            @(negedge clk);
            rst = 1'b1;
            sample_valid = 1'b0;
            rhythm_tick = 1'b0;
            segment_start = 1'b0;
            segment_done = 1'b0;
            adc_data = 12'sd0;
            repeat (6) @(posedge clk);
            @(negedge clk);
            rst = 1'b0;
        end
    endtask

    task pulse_start_only;
        begin
            @(negedge clk);
            segment_start = 1'b1;
            @(posedge clk);
            #1;
            segment_start = 1'b0;
        end
    endtask

    task drive_sample;
        input [11:0] value;
        input start_with_sample;
        input integer gap_cycles;
        begin
            if (gap_cycles > 1)
                repeat (gap_cycles - 1) @(posedge clk);
            @(negedge clk);
            adc_data = value;
            sample_valid = 1'b1;
            rhythm_tick = 1'b1;
            segment_start = start_with_sample;
            @(posedge clk);
            #1;
            sample_valid = 1'b0;
            rhythm_tick = 1'b0;
            segment_start = 1'b0;
        end
    endtask

    task run_case;
        input [8*16-1:0] label;
        input [1:0] expected;
        input [8*512-1:0] path;
        input same_start;
        input integer gap_cycles;
        begin
            $readmemh(path, sample_mem);
            reset_dut();

            if (!same_start)
                pulse_start_only();

            for (i = 0; i < 60000; i = i + 1)
                drive_sample(sample_mem[i], same_start && (i == 0), gap_cycles);

            @(negedge clk);
            segment_done = 1'b1;
            @(posedge clk);
            #1;
            segment_done = 1'b0;
            repeat (10) @(posedge clk);

            $display("BOARD_TIMING_CASE label=%0s expected=%0d same_start=%0d gap=%0d pred_valid=%0d pred=%0d correct=%0d",
                     label, expected, same_start, gap_cycles, pred_valid, pred_class, pred_valid && (pred_class == expected));
        end
    endtask

    initial begin
        rst = 1'b0;
        sample_valid = 1'b0;
        rhythm_tick = 1'b0;
        segment_start = 1'b0;
        segment_done = 1'b0;
        adc_data = 12'sd0;

        run_case("CHF", 2'd1,
                 "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_chf.mem",
                 1'b0, 1);
        run_case("CHF", 2'd1,
                 "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_chf.mem",
                 1'b1, 1);
        run_case("CHF", 2'd1,
                 "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_chf.mem",
                 1'b1, 50);
        run_case("ARR", 2'd2,
                 "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_arr.mem",
                 1'b0, 1);
        run_case("ARR", 2'd2,
                 "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_arr.mem",
                 1'b1, 1);
        run_case("ARR", 2'd2,
                 "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_arr.mem",
                 1'b1, 50);

        $finish;
    end
endmodule
