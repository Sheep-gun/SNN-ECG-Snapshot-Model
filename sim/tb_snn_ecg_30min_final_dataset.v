`timescale 1ns / 1ps

module tb_snn_ecg_30min_final_dataset #(
    parameter MAX_SAMPLES = 1800000,
    parameter MANIFEST_FILE = "",
    parameter RESULT_CSV = ""
)();
    reg clk;
    reg rst;
    reg start;
    reg sample_valid;
    reg signed [11:0] adc_data;
    wire sample_ready;
    wire busy;
    wire final_valid;
    wire [1:0] final_pred_class;
    wire signed [31:0] final_mem_nsr;
    wire signed [31:0] final_mem_chf;
    wire signed [31:0] final_mem_arr;
    wire signed [31:0] final_mem_aff;
    wire [5:0] snapshot_index_dbg;

    reg [11:0] sample_mem [0:MAX_SAMPLES-1];

    integer fd;
    integer out_fd;
    integer scan_count;
    integer case_id_i;
    integer expected_i;
    integer sample_count_i;
    integer sample_index;
    integer cycles;
    integer total;
    integer correct;
    integer final_seen;
    integer timeout_cycles;
    reg [8*512-1:0] path;

    snn_ecg_30min_final_top dut(
        .clk(clk),
        .rst(rst),
        .start(start),
        .sample_valid(sample_valid),
        .adc_data(adc_data),
        .sample_ready(sample_ready),
        .busy(busy),
        .final_valid(final_valid),
        .final_pred_class(final_pred_class),
        .final_mem_nsr(final_mem_nsr),
        .final_mem_chf(final_mem_chf),
        .final_mem_arr(final_mem_arr),
        .final_mem_aff(final_mem_aff),
        .snapshot_index_dbg(snapshot_index_dbg)
    );

    always #5 clk = ~clk;

    task reset_dut;
        begin
            @(negedge clk);
            rst = 1'b1;
            start = 1'b0;
            sample_valid = 1'b0;
            adc_data = 12'sd0;
            repeat (6) @(posedge clk);
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
            reset_dut();

            @(negedge clk);
            start = 1'b1;
            @(posedge clk);
            #1;
            start = 1'b0;

            sample_index = 0;
            cycles = 0;
            final_seen = 0;
            timeout_cycles = sample_count + 5000;
            while ((final_seen == 0) && (cycles < timeout_cycles)) begin
                @(negedge clk);
                if (sample_ready && (sample_index < sample_count)) begin
                    sample_valid = 1'b1;
                    adc_data = sample_mem[sample_index];
                    sample_index = sample_index + 1;
                end else begin
                    sample_valid = 1'b0;
                end
                @(posedge clk);
                #1;
                if (final_valid)
                    final_seen = 1;
                cycles = cycles + 1;
            end

            @(negedge clk);
            sample_valid = 1'b0;

            total = total + 1;
            if (final_seen && (final_pred_class == expected_class[1:0]))
                correct = correct + 1;
            if (!final_seen)
                $display("WARN timeout case=%0d samples_driven=%0d cycles=%0d snapshot=%0d", case_id, sample_index, cycles, snapshot_index_dbg);
            if (sample_index != sample_count)
                $display("WARN sample_count mismatch case=%0d driven=%0d expected=%0d", case_id, sample_index, sample_count);

            $fdisplay(out_fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                      case_id,
                      expected_class,
                      final_seen ? final_pred_class : 2'd0,
                      final_seen && (final_pred_class == expected_class[1:0]),
                      final_seen,
                      sample_index,
                      final_mem_nsr,
                      final_mem_chf,
                      final_mem_arr,
                      final_mem_aff,
                      cycles);
            $display("CASE_RESULT case=%0d expected=%0d pred=%0d correct=%0d valid=%0d samples=%0d cycles=%0d",
                     case_id,
                     expected_class,
                     final_seen ? final_pred_class : 2'd0,
                     final_seen && (final_pred_class == expected_class[1:0]),
                     final_seen,
                     sample_index,
                     cycles);
        end
    endtask

    initial begin
        clk = 1'b0;
        rst = 1'b1;
        start = 1'b0;
        sample_valid = 1'b0;
        adc_data = 12'sd0;
        total = 0;
        correct = 0;

        fd = $fopen(MANIFEST_FILE, "r");
        if (fd == 0) begin
            $display("FAIL open manifest %0s", MANIFEST_FILE);
            $finish;
        end
        out_fd = $fopen(RESULT_CSV, "w");
        if (out_fd == 0) begin
            $display("FAIL open result %0s", RESULT_CSV);
            $finish;
        end
        $fdisplay(out_fd, "case_id,expected_class,final_pred_class,correct,final_valid,samples_driven,final_mem_NSR,final_mem_CHF,final_mem_ARR,final_mem_AFF,cycles");

        while (!$feof(fd)) begin
            scan_count = $fscanf(fd, "%d %d %d %s\n", case_id_i, expected_i, sample_count_i, path);
            if (scan_count == 4)
                run_case(case_id_i, expected_i, sample_count_i, path);
        end

        $display("STREAM_RESULT correct/total=%0d/%0d manifest=%0s", correct, total, MANIFEST_FILE);
        $fclose(fd);
        $fclose(out_fd);
        $finish;
    end
endmodule
