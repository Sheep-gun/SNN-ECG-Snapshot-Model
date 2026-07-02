set script_dir [file dirname [file normalize [info script]]]
set repo_dir [file normalize [file join $script_dir ".."]]
set proj_dir [file normalize [file join $repo_dir "vivado_project" "SNN_ECG_V2"]]

file mkdir $proj_dir

create_project -force SNN_ECG_V2 $proj_dir -part xc7a100tcsg324-1
set_property target_language Verilog [current_project]
cd $repo_dir

set rtl_files [list \
    "rtl/core/ecg_event_encoder.v" \
    "rtl/core/ecg_event_encoder_adaptive.v" \
    "rtl/core/snn_ecg_input_normalizer.v" \
    "rtl/core/qrs_lif_detector.v" \
    "rtl/core/pnn_rhythm_predictor.v" \
    "rtl/core/dscr_spike_counter.v" \
    "rtl/core/ram_peak_accumulator.v" \
    "rtl/core/rdm_variability_neuron.v" \
    "rtl/core/ectopic_pair_neuron.v" \
    "rtl/core/qrs_maf_neuron.v" \
    "rtl/core/rbbb_qrs_delay_bank.v" \
    "rtl/core/abandoned_feature_stubs.v" \
    "rtl/core/class_score_neurons.v" \
    "rtl/core/snn_ecg_3feat_top.v" \
    "rtl/final_membrane_layer.v" \
    "rtl/snn_ecg_30min_final_top.v" \
    "rtl/board/snn_ecg_v2_nexys_a7_top.v" \
]

add_files -fileset sources_1 $rtl_files
add_files -fileset constrs_1 "constraints/nexys_a7_snn_ecg_v2.xdc"

set_property top snn_ecg_v2_nexys_a7_top [current_fileset]
update_compile_order -fileset sources_1

puts "XPR=[file join $proj_dir SNN_ECG_V2.xpr]"
exit
