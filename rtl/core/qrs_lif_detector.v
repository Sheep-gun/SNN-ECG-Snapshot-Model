`timescale 1ns / 1ps

module qrs_lif_detector #(
    parameter MEM_WIDTH = 12,
    parameter REF_WIDTH = 10,
    parameter W_EVENT   = 8,
    parameter LEAK_QRS  = 1,
    parameter T_QRS     = 24,
    parameter T_REF     = 50
)(
    input clk,
    input rst,
    input sample_valid,
    input strong_event,
    output reg [MEM_WIDTH-1:0] qrs_mem,
    output reg [REF_WIDTH-1:0] refractory_cnt,
    output reg beat_spike
);

    reg [MEM_WIDTH-1:0] qrs_mem_next;
    reg [REF_WIDTH-1:0] refractory_cnt_next;
    reg beat_spike_next;
    reg [MEM_WIDTH:0] mem_after_leak;
    reg [MEM_WIDTH:0] mem_after_event;

    always @* begin
        qrs_mem_next = qrs_mem;
        refractory_cnt_next = refractory_cnt;
        beat_spike_next = 1'b0;
        mem_after_leak = {1'b0, qrs_mem};
        mem_after_event = {1'b0, qrs_mem};

        if (sample_valid) begin
            if (refractory_cnt != {REF_WIDTH{1'b0}}) begin
                qrs_mem_next = {MEM_WIDTH{1'b0}};
                refractory_cnt_next = refractory_cnt - 1'b1;
            end else begin
                if (qrs_mem > LEAK_QRS)
                    mem_after_leak = qrs_mem - LEAK_QRS;
                else
                    mem_after_leak = {(MEM_WIDTH+1){1'b0}};

                if (strong_event)
                    mem_after_event = mem_after_leak + W_EVENT;
                else
                    mem_after_event = mem_after_leak;

                if (mem_after_event >= T_QRS) begin
                    beat_spike_next = 1'b1;
                    qrs_mem_next = {MEM_WIDTH{1'b0}};
                    refractory_cnt_next = T_REF[REF_WIDTH-1:0];
                end else begin
                    qrs_mem_next = mem_after_event[MEM_WIDTH-1:0];
                end
            end
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            qrs_mem <= {MEM_WIDTH{1'b0}};
            refractory_cnt <= {REF_WIDTH{1'b0}};
            beat_spike <= 1'b0;
        end else begin
            qrs_mem <= qrs_mem_next;
            refractory_cnt <= refractory_cnt_next;
            beat_spike <= beat_spike_next;
        end
    end

endmodule
