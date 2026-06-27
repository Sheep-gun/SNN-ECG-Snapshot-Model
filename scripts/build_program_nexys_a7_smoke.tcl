set root "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S"
set proj_dir "$root/vivado_project/SNN_ECG_ModelS_BoardSmoke"
set report_dir "$root/reports/board_smoke"
set bit_dir "$root/bitstreams"
file mkdir $report_dir
file mkdir $bit_dir

create_project -force SNN_ECG_ModelS_BoardSmoke $proj_dir -part xc7a100tcsg324-1

set src_dir "$root/SNN_ECG.srcs/sources_1/new"
set board_dir "$root/SNN_ECG.srcs/sources_1/board"
set xdc_dir "$root/constraints"

set rtl_files [list \
    "$src_dir/ecg_event_encoder.v" \
    "$src_dir/snn_ecg_input_normalizer.v" \
    "$src_dir/qrs_lif_detector.v" \
    "$src_dir/pnn_rhythm_predictor.v" \
    "$src_dir/dscr_spike_counter.v" \
    "$src_dir/ram_peak_accumulator.v" \
    "$src_dir/rdm_variability_neuron.v" \
    "$src_dir/ectopic_pair_neuron.v" \
    "$src_dir/qrs_maf_neuron.v" \
    "$src_dir/rbbb_qrs_delay_bank.v" \
    "$src_dir/abandoned_feature_stubs.v" \
    "$src_dir/class_score_neurons.v" \
    "$src_dir/snn_ecg_3feat_top.v" \
    "$src_dir/snn_ecg_model_a_plus_core.v" \
    "$board_dir/nexys_a7_model_s_smoke_top.v" \
]

add_files -fileset sources_1 $rtl_files
add_files -fileset constrs_1 "$xdc_dir/nexys_a7_model_s_smoke.xdc"
set_property top nexys_a7_model_s_smoke_top [current_fileset]
update_compile_order -fileset sources_1

launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
    error "synth_1 did not complete"
}
if {[get_property STATUS [get_runs synth_1]] != "synth_design Complete!"} {
    error "synth_1 status: [get_property STATUS [get_runs synth_1]]"
}

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
    error "impl_1 did not complete"
}

open_run impl_1
report_utilization -file "$report_dir/nexys_a7_model_s_smoke_utilization.rpt"
report_timing_summary -file "$report_dir/nexys_a7_model_s_smoke_timing_summary.rpt"
write_checkpoint -force "$report_dir/nexys_a7_model_s_smoke_impl.dcp"

set bit_file "$proj_dir/SNN_ECG_ModelS_BoardSmoke.runs/impl_1/nexys_a7_model_s_smoke_top.bit"
if {![file exists $bit_file]} {
    error "Bitstream not found: $bit_file"
}
file copy -force $bit_file "$bit_dir/nexys_a7_model_s_smoke_top.bit"
puts "BITSTREAM=$bit_dir/nexys_a7_model_s_smoke_top.bit"

open_hw_manager
connect_hw_server -allow_non_jtag
set targets [get_hw_targets *]
puts "HW_TARGET_COUNT=[llength $targets]"
if {[llength $targets] < 1} {
    error "No hardware target found"
}
current_hw_target [lindex $targets 0]
open_hw_target
set devs [get_hw_devices xc7a100t*]
puts "HW_DEVICE_COUNT=[llength $devs]"
if {[llength $devs] < 1} {
    error "No xc7a100t hardware device found"
}
set dev [lindex $devs 0]
current_hw_device $dev
refresh_hw_device $dev
set_property PROGRAM.FILE "$bit_dir/nexys_a7_model_s_smoke_top.bit" $dev
program_hw_devices $dev
refresh_hw_device $dev
puts "PROGRAMMED_DEVICE=$dev"
catch {puts "DONE_PROPERTY=[get_property REGISTER.CONFIG_STATUS.BITSTREAM_DONE $dev]"}
catch {puts "PROGRAM_HW_CFGMEM_STATUS=[get_property PROGRAM.HW_CFGMEM_STATUS $dev]"}
exit
