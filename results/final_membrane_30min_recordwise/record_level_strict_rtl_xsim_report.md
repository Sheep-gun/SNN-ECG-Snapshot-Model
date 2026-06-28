# Record-Level Strict Final Membrane RTL/XSim Report

## Scope

- Dataset: `fullrec_afe_30min_annotation_valid_balanced`
- Model: fixed Snapshot C24, followed by record-level final membrane
- Selection source: `no_oracle_record_level_strict_selected_params.json`
- Rule kind: `record_arr_rescue`
- Parameters: `arr_th = 5`, `abnormal_th = 0`, `boost = 16`
- Final test was not used for parameter selection.

## RTL Structure

- `rtl/final_membrane_layer.v`
  - Counts raw 60 s Snapshot C24 prediction spikes inside each 30 min chunk.
  - Exposes raw chunk vote membranes: NSR/CHF/ARR/AFF counts.
- `rtl/record_level_final_membrane_layer.v`
  - Accumulates chunk vote counts across all 30 min chunks belonging to one record.
  - Applies ARR rescue: if accumulated ARR count is at least 5, add 16 to ARR score.
  - Uses WTA tie order: NSR, CHF, ARR, AFF.
- `sim/tb_snn_ecg_30min_record_level_dataset.v`
  - Streams actual 1,800,000-sample `.mem` chunks into RTL.
  - Applies record_start/record_done boundaries from the generated manifest.
  - Emits one final record-level class prediction and maps it back to chunks in that record.

## XSim Results

| Split | Correct / Total | Accuracy | Macro-F1 | Balanced Acc. | Python-vs-XSim Pred Mismatch |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | 55 / 68 | 80.88% | 80.19% | 80.88% | 0 |
| val | 29 / 32 | 90.62% | 90.28% | 90.62% | 0 |
| test | 30 / 36 | 83.33% | 83.11% | 83.33% | 0 |

## Test Per-Class Metrics

| Class | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| NSR | 80.00% | 88.89% | 84.21% | 9 |
| CHF | 85.71% | 66.67% | 75.00% | 9 |
| ARR | 100.00% | 77.78% | 87.50% | 9 |
| AFF | 75.00% | 100.00% | 85.71% | 9 |

Test confusion matrix, row=true and column=pred, class order NSR/CHF/ARR/AFF:

```text
[[8, 1, 0, 0],
 [0, 6, 0, 3],
 [2, 0, 7, 0],
 [0, 0, 0, 9]]
```

## Output Files

- `results/final_membrane_30min_recordwise/xsim_record_level_strict_train_predictions.csv`
- `results/final_membrane_30min_recordwise/xsim_record_level_strict_val_predictions.csv`
- `results/final_membrane_30min_recordwise/xsim_record_level_strict_test_predictions.csv`
- `results/final_membrane_30min_recordwise/xsim_record_level_strict_train_metrics.json`
- `results/final_membrane_30min_recordwise/xsim_record_level_strict_val_metrics.json`
- `results/final_membrane_30min_recordwise/xsim_record_level_strict_test_metrics.json`
- `results/final_membrane_30min_recordwise/python_vs_xsim_record_level_strict_compare.csv`

## Conclusion

The selected strict record-level final membrane has been moved to RTL and verified with XSim on train/val/test. RTL predictions match the Python equivalent for all 136 evaluated chunks, with zero prediction mismatches. The XSim test accuracy is 30/36 = 83.33%, meeting the 80% target.
