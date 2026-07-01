`timescale 1ns / 1ps

module tb_snapshot_c24_dataset #(
    parameter MAX_SAMPLES = 60000,
    parameter MANIFEST_FILE = "",
    parameter RESULT_CSV = ""
)();
    reg clk;
    reg rst;
    reg sample_valid;
    reg rhythm_tick;
    reg segment_start;
    reg segment_done;
    reg signed [11:0] adc_data;

    wire [1:0] pred_class;
    wire pred_valid;
    wire signed [63:0] c24_mem_nsr;
    wire signed [63:0] c24_mem_chf;
    wire signed [63:0] c24_mem_arr;
    wire signed [63:0] c24_mem_aff;

    reg [11:0] sample_mem [0:MAX_SAMPLES-1];

    integer manifest_fd;
    integer out_fd;
    integer scan_count;
    integer case_id_i;
    integer expected_i;
    integer sample_count_i;
    integer sample_index;
    integer cycles;
    integer total;
    integer correct;
    integer timeout_cycles;
    reg [8*512-1:0] path;

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
    ) dut (
        .clk(clk),
        .rst(rst),
        .sample_valid(sample_valid),
        .rhythm_tick(rhythm_tick),
        .segment_start(segment_start),
        .segment_done(segment_done),
        .adc_data(adc_data),
        .c24_mem_nsr(c24_mem_nsr),
        .c24_mem_chf(c24_mem_chf),
        .c24_mem_arr(c24_mem_arr),
        .c24_mem_aff(c24_mem_aff),
        .pred_class(pred_class),
        .pred_valid(pred_valid)
    );

    always #5 clk = ~clk;

    task reset_core;
        begin
            @(negedge clk);
            rst = 1'b1;
            sample_valid = 1'b0;
            rhythm_tick = 1'b0;
            segment_start = 1'b0;
            segment_done = 1'b0;
            adc_data = 12'sd0;
            repeat (8) @(posedge clk);
            rst = 1'b0;
        end
    endtask

    task run_case;
        input integer case_id;
        input integer expected_class;
        input integer sample_count;
        input [8*512-1:0] mem_path;
        begin
            $readmemh(mem_path, sample_mem);
            reset_core();

            @(negedge clk);
            segment_start = 1'b1;
            @(posedge clk);
            #1;
            @(negedge clk);
            segment_start = 1'b0;

            sample_index = 0;
            while (sample_index < sample_count) begin
                @(negedge clk);
                sample_valid = 1'b1;
                rhythm_tick = 1'b1;
                adc_data = sample_mem[sample_index];
                sample_index = sample_index + 1;
                @(posedge clk);
                #1;
            end

            @(negedge clk);
            sample_valid = 1'b0;
            rhythm_tick = 1'b0;
            adc_data = 12'sd0;
            segment_done = 1'b1;
            @(posedge clk);
            #1;
            @(negedge clk);
            segment_done = 1'b0;

            cycles = 0;
            timeout_cycles = 64;
            while ((pred_valid == 1'b0) && (cycles < timeout_cycles)) begin
                @(posedge clk);
                #1;
                cycles = cycles + 1;
            end

            total = total + 1;
            if (pred_valid && (pred_class == expected_class[1:0]))
                correct = correct + 1;

            $fdisplay(out_fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                      case_id,
                      expected_class,
                      pred_valid ? pred_class : 2'd0,
                      pred_valid && (pred_class == expected_class[1:0]),
                      pred_valid,
                      c24_mem_nsr,
                      c24_mem_chf,
                      c24_mem_arr,
                      c24_mem_aff);
            $display("SNAPSHOT_RESULT case=%0d expected=%0d pred=%0d correct=%0d valid=%0d",
                     case_id,
                     expected_class,
                     pred_valid ? pred_class : 2'd0,
                     pred_valid && (pred_class == expected_class[1:0]),
                     pred_valid);
        end
    endtask

    initial begin
        clk = 1'b0;
        rst = 1'b1;
        sample_valid = 1'b0;
        rhythm_tick = 1'b0;
        segment_start = 1'b0;
        segment_done = 1'b0;
        adc_data = 12'sd0;
        total = 0;
        correct = 0;

        manifest_fd = $fopen(MANIFEST_FILE, "r");
        if (manifest_fd == 0) begin
            $display("FAIL cannot open manifest: %s", MANIFEST_FILE);
            $finish;
        end
        out_fd = $fopen(RESULT_CSV, "w");
        if (out_fd == 0) begin
            $display("FAIL cannot open result csv: %s", RESULT_CSV);
            $finish;
        end
        $fdisplay(out_fd, "case_id,expected_class,pred_class,correct,pred_valid,class_mem_NSR,class_mem_CHF,class_mem_ARR,class_mem_AFF");

        while (!$feof(manifest_fd)) begin
            path = 0;
            scan_count = $fscanf(manifest_fd, "%d %d %d %s\n", case_id_i, expected_i, sample_count_i, path);
            if (scan_count == 4)
                run_case(case_id_i, expected_i, sample_count_i, path);
        end

        $display("SNAPSHOT_SUMMARY correct=%0d total=%0d", correct, total);
        $fclose(out_fd);
        $fclose(manifest_fd);
        $finish;
    end
endmodule
