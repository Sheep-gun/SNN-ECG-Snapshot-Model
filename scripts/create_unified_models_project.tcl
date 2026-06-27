set root "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S"
set proj_dir "$root/vivado_project/SNN_ECG_ModelS_Unified"

create_project -force SNN_ECG_ModelS_Unified $proj_dir -part xc7a100tcsg324-1
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]

set src_dir "$root/SNN_ECG.srcs/sources_1/new"
set board_dir "$root/SNN_ECG.srcs/sources_1/board"
set sim_dir "$root/SNN_ECG.srcs/sim_1/new"
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

set sim_files [list \
    "$sim_dir/tb_snn_ecg_3feat_dataset.v" \
    "$sim_dir/tb_snn_ecg_3feat_record_strict_train.v" \
    "$sim_dir/tb_snn_ecg_3feat_record_strict_val.v" \
    "$sim_dir/tb_snn_ecg_3feat_record_strict_test.v" \
    "$sim_dir/tb_snn_ecg_3feat_record_strict_train_rbbb_subset.v" \
    "$sim_dir/tb_board_demo_core_timing.v" \
]

add_files -fileset sources_1 $rtl_files
add_files -fileset sim_1 $sim_files
add_files -fileset constrs_1 "$xdc_dir/nexys_a7_model_s_smoke.xdc"

set_property top nexys_a7_model_s_smoke_top [get_filesets sources_1]
set_property top tb_snn_ecg_3feat_record_strict_test [get_filesets sim_1]
set_property source_set sources_1 [get_filesets sim_1]

update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

puts "UNIFIED_PROJECT=$proj_dir/SNN_ECG_ModelS_Unified.xpr"
close_project
exit
