set root "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S"
set proj_dir "$root/vivado_project/SNN_ECG_ModelS_Restore"
set report_dir "$root/reports/synth"
file mkdir $report_dir

create_project -force SNN_ECG_ModelS_Restore $proj_dir -part xc7a100tcsg324-1

set src_dir "$root/SNN_ECG.srcs/sources_1/new"
set sim_dir "$root/SNN_ECG.srcs/sim_1/new"

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
]

add_files -fileset sources_1 $rtl_files
set_property top snn_ecg_model_a_plus_core [current_fileset]

set sim_files [list \
    "$sim_dir/tb_snn_ecg_3feat_dataset.v" \
    "$sim_dir/tb_snn_ecg_3feat_record_strict_train.v" \
    "$sim_dir/tb_snn_ecg_3feat_record_strict_val.v" \
    "$sim_dir/tb_snn_ecg_3feat_record_strict_test.v" \
]
add_files -fileset sim_1 $sim_files

update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

synth_design -top snn_ecg_model_a_plus_core -part xc7a100tcsg324-1
report_utilization -file "$report_dir/restore_model_s_utilization.rpt"
report_utilization -hierarchical -file "$report_dir/restore_model_s_utilization_hier.rpt"
report_timing_summary -file "$report_dir/restore_model_s_timing_summary.rpt"
write_checkpoint -force "$report_dir/restore_model_s_synth.dcp"

exit
