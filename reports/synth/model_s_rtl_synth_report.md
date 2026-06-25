# Model S RTL Synthesis Report

## Vivado

- Tool: Vivado 2020.2
- Part: xc7a100tcsg324-1
- Top: snn_ecg_model_a_plus_core
- Script: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/scripts/create_and_synth_model_s_restore.tcl`
- Result: synth_design completed successfully.

## Utilization

| resource | used | available | util |
|---|---:|---:|---:|
| Slice LUTs* | 5309 | 63400 | 8.37% |
| Slice Registers | 1250 | 126800 | 0.99% |
| Block RAM Tile | 0 | 135 | 0.00% |
| DSPs | 0 | 240 | 0.00% |
| Bonded IOB | 21 | 210 | 10.00% |
| BUFGCTRL | 1 | 32 | 3.13% |

## Notes

- DSP usage is 0, so the restored Model S path remains multiplier/DSP-free after synthesis.
- BRAM usage is 0. QRS pre-window history is mapped to distributed shift-register LUT resources.
- This is synthesis-only timing without an XDC constraint file. Timing warnings below are expected until board-level clock/input/output constraints are added.
- no_clock pins reported: 1286
- unconstrained internal endpoints reported: 3215
- no_input_delay ports reported: 17
- no_output_delay ports reported: 3
