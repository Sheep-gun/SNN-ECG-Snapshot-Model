# Nexys A7 Model S Interactive Demo Summary

## Purpose

This bitstream verifies that the restored Model S RTL can be synthesized, implemented, written as a bitstream, programmed onto the Nexys A7-100T FPGA, and exercised interactively through the board buttons and 7-segment display.

This is a board-level interactive demo, not a full dataset accuracy test. The wrapper stores four strict-test 60-second `.mem` examples in FPGA ROM and feeds the selected example into the Model S classifier core.

## Files

- Board top: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/nexys_a7_model_s_smoke_top.v`
- Constraint file: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/constraints/nexys_a7_model_s_smoke.xdc`
- Build/program script: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/scripts/build_program_nexys_a7_smoke.tcl`
- Bitstream: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/bitstreams/nexys_a7_model_s_smoke_top.bit`
- Timing report: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/reports/board_smoke/nexys_a7_model_s_smoke_timing_summary.rpt`
- Utilization report: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/reports/board_smoke/nexys_a7_model_s_smoke_utilization.rpt`
- Demo NSR ROM: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_nsr.mem`
- Demo CHF ROM: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_chf.mem`
- Demo ARR ROM: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_arr.mem`
- Demo AFF ROM: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/SNN_ECG.srcs/sources_1/board/demo_aff.mem`

## Button Mapping

- `BTNU`: NSR example
- `BTNL`: ARR example
- `BTND`: CHF example
- `BTNR`: AFF example
- `BTNC`: pseudo-random one of NSR / CHF / ARR / AFF
- `CPU_RESETN`: board demo reset

After a button is pressed, the selected 60-second test segment is streamed into the Model S core. The logical segment length is 60,000 samples. The board wrapper feeds one sample on every 1 MHz core-clock cycle, matching the strict XSim dataset testbench's valid-sample cadence. The result appears after about 60 ms instead of 60 seconds.

## 7-Segment Display

The 8-digit 7-segment display is split into two 4-digit fields.

- Left 4 digits, `AN[7:4]`: Model S predicted class
  - `NSR`
  - `CHF`
  - `ARR`
  - `AFF`
- Right 4 digits, `AN[3:0]`: correctness result
  - `CORR` if predicted class equals the selected example class
  - `ERR` if predicted class differs from the selected example class

Before the classifier produces a prediction, all 7-segment digits are blank. After `pred_valid`, the left field shows the Model S result and the right field shows `CORR` or `ERR`.

The board wrapper clears the displayed result on every new button press. While a new selected segment is running, `AN[7:0]` is held inactive so stale results are not shown. The ECG playback now uses a continuous valid-sample cadence. Debug simulation showed that inserting idle core-clock cycles between samples reproduced the observed board mismatch, where the CHF demo was classified as NSR and the ARR demo was classified as AFF. Removing that idle gap restores the same timing behavior as the strict XSim dataset testbench.

## LED Mapping

- `LED0`: heartbeat blink
- `LED1`: classifier is running
- `LED2`: prediction has been received
- `LED3`: prediction is correct
- `LED[5:4]`: selected expected class
- `LED[7:6]`: latched predicted class
- `LED[11:8]`: trial count
- `LED[15:12]`: button activity/debug bits

## Hardware Result

- Hardware target detected: `localhost:3121/xilinx_tcf/Digilent/210292B7D430A`
- FPGA device detected: `xc7a100t_0`
- Program result: `program_hw_devices` completed successfully
- Startup status: `HIGH`

## Timing Result

- Timing status: all user specified timing constraints are met
- WNS: 4.242 ns
- TNS: 0.000 ns
- WHS: 0.085 ns
- THS: 0.000 ns

The classifier core is clocked at 1 MHz in the board demo wrapper. The board clock remains 100 MHz and is used to generate the slower core clock. This avoids unnecessary timing pressure while preserving the Model S event-driven control behavior.

## Utilization

- Slice LUTs: 5400 / 63400 = 8.52%
- Slice Registers: 1384 / 126800 = 1.09%
- BRAM: 84 / 135 = 62.22%
- DSP: 0 / 240 = 0.00%

## Limitations

This wrapper does not connect an external ADC to the FPGA. It uses four stored strict-test examples selected by the board buttons. Therefore, this bitstream proves board programmability, display control, button interaction, ROM playback, and Model S runtime operation, but it is not a replacement for external ADC validation or full dataset playback on hardware.
