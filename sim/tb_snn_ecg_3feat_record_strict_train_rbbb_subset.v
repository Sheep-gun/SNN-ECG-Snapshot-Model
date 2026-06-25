`timescale 1ns / 1ps

module tb_snn_ecg_3feat_record_strict_train_rbbb_subset;
    tb_snn_ecg_3feat_dataset #(
        .MAX_SAMPLES(180000),
        .MANIFEST_FILE("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/debug_train_rbbb_subset_manifest.txt"),
        .WRITE_CASE_CSV(1),
        .RESULT_CSV("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/debug_train_rbbb_subset_case_results.csv"),
        .WRITE_SUBWINDOW_CSV(0),
        .SUBWINDOW_CSV("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/debug_train_rbbb_subset_subwindow_features.csv"),
        .MANIFEST_HAS_SAMPLE_COUNT(1)
    ) u_tb();
endmodule
