`timescale 1ns / 1ps

module tb_snn_ecg_3feat_record_strict_train;
    tb_snn_ecg_3feat_dataset #(
        .MAX_SAMPLES(180000),
        .MANIFEST_FILE("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/person_data_record_split_strict_varlen/train/dataset_manifest_train_varlen.txt"),
        .WRITE_CASE_CSV(1),
        .RESULT_CSV("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/train/rtl_train_varlen_case_results.csv"),
        .WRITE_SUBWINDOW_CSV(0),
        .SUBWINDOW_CSV("C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/results/train/rtl_train_varlen_subwindow_features.csv"),
        .MANIFEST_HAS_SAMPLE_COUNT(1)
    ) u_tb();
endmodule
