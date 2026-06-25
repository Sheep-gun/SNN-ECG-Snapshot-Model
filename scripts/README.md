# Scripts

This folder contains selected scripts from the final restore project.

Some scripts contain local Windows or Vivado installation assumptions. Check paths before running on a different machine.

Most useful scripts:

- `create_unified_models_project.tcl`: recreate/open the unified Vivado project
- `run_record_split_strict_varlen_tb_xsim.ps1`: run strict train/validation/test XSim testbenches
- `build_program_nexys_a7_smoke.tcl`: build/program Nexys A7 board demo
- `program_existing_nexys_a7_smoke_bit.tcl`: program the included bitstream
- `generate_model_s_rtl_reports.py`: regenerate metrics from XSim CSV outputs
