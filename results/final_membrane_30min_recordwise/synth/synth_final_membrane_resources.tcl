set root "C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S"
set out_dir "$root/results/final_membrane_30min_recordwise/synth"
set part "xc7a100tcsg324-1"
file mkdir $out_dir

set core_files [list \
    "$root/rtl/core/ecg_event_encoder.v" \
    "$root/rtl/core/ecg_event_encoder_adaptive.v" \
    "$root/rtl/core/snn_ecg_input_normalizer.v" \
    "$root/rtl/core/qrs_lif_detector.v" \
    "$root/rtl/core/pnn_rhythm_predictor.v" \
    "$root/rtl/core/dscr_spike_counter.v" \
    "$root/rtl/core/ram_peak_accumulator.v" \
    "$root/rtl/core/rdm_variability_neuron.v" \
    "$root/rtl/core/ectopic_pair_neuron.v" \
    "$root/rtl/core/qrs_maf_neuron.v" \
    "$root/rtl/core/rbbb_qrs_delay_bank.v" \
    "$root/rtl/core/abandoned_feature_stubs.v" \
    "$root/rtl/core/class_score_neurons.v" \
    "$root/rtl/core/snn_ecg_3feat_top.v" \
]

proc synth_one {top files} {
    global out_dir part
    set proj_dir "$out_dir/vivado_$top"
    create_project -force "synth_$top" $proj_dir -part $part
    add_files -fileset sources_1 $files
    set_property top $top [current_fileset]
    update_compile_order -fileset sources_1
    synth_design -top $top -part $part -flatten_hierarchy rebuilt
    report_utilization -file "$out_dir/${top}_utilization.rpt"
    report_utilization -hierarchical -file "$out_dir/${top}_utilization_hier.rpt"
    report_timing_summary -file "$out_dir/${top}_timing_summary.rpt"
    close_project
}

synth_one record_level_final_membrane_layer [list \
    "$root/rtl/record_level_final_membrane_layer.v" \
]

synth_one final_membrane_layer [list \
    "$root/rtl/final_membrane_layer.v" \
]

synth_one final_membrane_record_chain_synth_top [list \
    "$root/rtl/final_membrane_layer.v" \
    "$root/rtl/record_level_final_membrane_layer.v" \
    "$out_dir/final_membrane_record_chain_synth_top.v" \
]

synth_one snn_ecg_30min_final_top [concat $core_files [list \
    "$root/rtl/final_membrane_layer.v" \
    "$root/rtl/snn_ecg_30min_final_top.v" \
]]

synth_one snn_ecg_30min_record_final_synth_top [concat $core_files [list \
    "$root/rtl/final_membrane_layer.v" \
    "$root/rtl/record_level_final_membrane_layer.v" \
    "$root/rtl/snn_ecg_30min_final_top.v" \
    "$out_dir/snn_ecg_30min_record_final_synth_top.v" \
]]

exit
