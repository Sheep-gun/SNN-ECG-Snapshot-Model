`timescale 1ns / 1ps

module tb_snn_ecg_30min_record_level_dataset #(
    parameter MAX_SAMPLES = 1800000,
    parameter MAX_RECORD_CHUNKS = 128,
    parameter MANIFEST_FILE = "",
    parameter RESULT_CSV = ""
)();
    reg clk;
    reg top_rst;
    reg record_rst;
    reg start;
    reg sample_valid;
    reg signed [11:0] adc_data;
    wire sample_ready;
    wire busy;
    wire chunk_valid;
    wire [1:0] chunk_pred_class;
    wire signed [31:0] chunk_mem_nsr;
    wire signed [31:0] chunk_mem_chf;
    wire signed [31:0] chunk_mem_arr;
    wire signed [31:0] chunk_mem_aff;
    wire [5:0] snapshot_index_dbg;

    reg record_clear;
    reg record_chunk_done;
    reg record_done_pulse;
    wire record_final_valid;
    wire [1:0] record_pred_class;
    wire signed [31:0] record_mem_nsr;
    wire signed [31:0] record_mem_chf;
    wire signed [31:0] record_mem_arr;
    wire signed [31:0] record_mem_aff;

    reg [5:0] record_chunk_count_nsr;
    reg [5:0] record_chunk_count_chf;
    reg [5:0] record_chunk_count_arr;
    reg [5:0] record_chunk_count_aff;

    reg [11:0] sample_mem [0:MAX_SAMPLES-1];
    reg [31:0] rec_case_id [0:MAX_RECORD_CHUNKS-1];
    reg [31:0] rec_expected [0:MAX_RECORD_CHUNKS-1];
    reg [31:0] rec_samples [0:MAX_RECORD_CHUNKS-1];
    reg [31:0] rec_cycles [0:MAX_RECORD_CHUNKS-1];

    integer fd;
    integer out_fd;
    integer scan_count;
    integer case_id_i;
    integer expected_i;
    integer sample_count_i;
    integer record_start_i;
    integer record_done_i;
    integer sample_index;
    integer cycles;
    integer total;
    integer correct;
    integer chunk_seen;
    integer record_seen;
    integer timeout_cycles;
    integer rec_count;
    integer i;
    reg [8*512-1:0] path;

    snn_ecg_30min_final_top u_chunk(
        .clk(clk),
        .rst(top_rst),
        .start(start),
        .sample_valid(sample_valid),
        .adc_data(adc_data),
        .sample_ready(sample_ready),
        .busy(busy),
        .final_valid(chunk_valid),
        .final_pred_class(chunk_pred_class),
        .final_mem_nsr(chunk_mem_nsr),
        .final_mem_chf(chunk_mem_chf),
        .final_mem_arr(chunk_mem_arr),
        .final_mem_aff(chunk_mem_aff),
        .snapshot_index_dbg(snapshot_index_dbg)
    );

    record_level_final_membrane_layer u_record(
        .clk(clk),
        .rst(record_rst),
        .clear(record_clear),
        .chunk_done(record_chunk_done),
        .record_done(record_done_pulse),
        .chunk_count_nsr(record_chunk_count_nsr),
        .chunk_count_chf(record_chunk_count_chf),
        .chunk_count_arr(record_chunk_count_arr),
        .chunk_count_aff(record_chunk_count_aff),
        .final_valid(record_final_valid),
        .final_pred_class(record_pred_class),
        .final_mem_nsr(record_mem_nsr),
        .final_mem_chf(record_mem_chf),
        .final_mem_arr(record_mem_arr),
        .final_mem_aff(record_mem_aff)
    );

    always #5 clk = ~clk;

    task reset_chunk_top;
        begin
            @(negedge clk);
            top_rst = 1'b1;
            start = 1'b0;
            sample_valid = 1'b0;
            adc_data = 12'sd0;
            repeat (6) @(posedge clk);
            top_rst = 1'b0;
        end
    endtask

    task clear_record_layer;
        begin
            @(negedge clk);
            record_clear = 1'b1;
            record_chunk_done = 1'b0;
            record_done_pulse = 1'b0;
            @(posedge clk);
            #1;
            @(negedge clk);
            record_clear = 1'b0;
        end
    endtask

    task run_chunk;
        input integer case_id;
        input integer expected_class;
        input integer sample_count;
        input integer is_record_start;
        input integer is_record_done;
        input [8*512-1:0] mem_path;
        begin
            if (is_record_start != 0) begin
                clear_record_layer();
                rec_count = 0;
            end

            $readmemh(mem_path, sample_mem);
            reset_chunk_top();

            @(negedge clk);
            start = 1'b1;
            @(posedge clk);
            #1;
            start = 1'b0;

            sample_index = 0;
            cycles = 0;
            chunk_seen = 0;
            timeout_cycles = sample_count + 5000;
            while ((chunk_seen == 0) && (cycles < timeout_cycles)) begin
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
                if (chunk_valid)
                    chunk_seen = 1;
                cycles = cycles + 1;
            end

            @(negedge clk);
            sample_valid = 1'b0;

            if (!chunk_seen)
                $display("WARN chunk timeout case=%0d samples_driven=%0d cycles=%0d snapshot=%0d", case_id, sample_index, cycles, snapshot_index_dbg);
            if (sample_index != sample_count)
                $display("WARN sample_count mismatch case=%0d driven=%0d expected=%0d", case_id, sample_index, sample_count);
            if (rec_count >= MAX_RECORD_CHUNKS) begin
                $display("FAIL record chunk buffer overflow case=%0d", case_id);
                $finish;
            end

            rec_case_id[rec_count] = case_id;
            rec_expected[rec_count] = expected_class;
            rec_samples[rec_count] = sample_index;
            rec_cycles[rec_count] = cycles;
            rec_count = rec_count + 1;

            @(negedge clk);
            record_chunk_count_nsr = chunk_mem_nsr[5:0];
            record_chunk_count_chf = chunk_mem_chf[5:0];
            record_chunk_count_arr = chunk_mem_arr[5:0];
            record_chunk_count_aff = chunk_mem_aff[5:0];
            record_chunk_done = 1'b1;
            record_done_pulse = (is_record_done != 0);
            @(posedge clk);
            #1;
            record_seen = record_final_valid;
            @(negedge clk);
            record_chunk_done = 1'b0;
            record_done_pulse = 1'b0;

            if (is_record_done != 0) begin
                for (i = 0; i < rec_count; i = i + 1) begin
                    total = total + 1;
                    if (record_seen && (record_pred_class == rec_expected[i][1:0]))
                        correct = correct + 1;
                    $fdisplay(out_fd, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                              rec_case_id[i],
                              rec_expected[i],
                              record_seen ? record_pred_class : 2'd0,
                              record_seen && (record_pred_class == rec_expected[i][1:0]),
                              record_seen,
                              rec_samples[i],
                              record_mem_nsr,
                              record_mem_chf,
                              record_mem_arr,
                              record_mem_aff,
                              rec_cycles[i]);
                    $display("RECORD_RESULT case=%0d expected=%0d pred=%0d correct=%0d valid=%0d samples=%0d cycles=%0d",
                             rec_case_id[i],
                             rec_expected[i],
                             record_seen ? record_pred_class : 2'd0,
                             record_seen && (record_pred_class == rec_expected[i][1:0]),
                             record_seen,
                             rec_samples[i],
                             rec_cycles[i]);
                end
                if (!record_seen)
                    $display("WARN record final missing last_case=%0d", case_id);
                rec_count = 0;
            end
        end
    endtask

    initial begin
        clk = 1'b0;
        top_rst = 1'b1;
        record_rst = 1'b1;
        start = 1'b0;
        sample_valid = 1'b0;
        adc_data = 12'sd0;
        record_clear = 1'b0;
        record_chunk_done = 1'b0;
        record_done_pulse = 1'b0;
        record_chunk_count_nsr = 6'd0;
        record_chunk_count_chf = 6'd0;
        record_chunk_count_arr = 6'd0;
        record_chunk_count_aff = 6'd0;
        rec_count = 0;
        total = 0;
        correct = 0;

        repeat (6) @(posedge clk);
        top_rst = 1'b0;
        record_rst = 1'b0;

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
            scan_count = $fscanf(fd, "%d %d %d %d %d %s\n", case_id_i, expected_i, sample_count_i, record_start_i, record_done_i, path);
            if (scan_count == 6)
                run_chunk(case_id_i, expected_i, sample_count_i, record_start_i, record_done_i, path);
        end

        $display("RECORD_STREAM_RESULT correct/total=%0d/%0d manifest=%0s", correct, total, MANIFEST_FILE);
        $fclose(fd);
        $fclose(out_fd);
        $finish;
    end
endmodule
