# Record-Wise 30min Final Membrane Layer Report

This run replaces the previous chunk-wise split with a record-wise holdout split. The earlier `97.22%` tree-rule result is discarded as an exploratory/oracle-like upper bound because it used test labels during structure search.

## Dataset And Split

- Dataset: `C:\Users\YangGeon\SNN_ECG_RESTORE_MODEL_S\fullrec_afe_30min_annotation_valid_balanced`
- Chunks: 136 annotation-valid 30min AFE+ADC `.mem` chunks
- `chf12`: not present
- Remainder chunks shorter than 30min: not used
- Original leakage: 33 records appeared in more than one old split
- New record-wise leakage: 0 records

New record-wise split:

| split | NSR records/chunks | CHF records/chunks | ARR records/chunks | AFF records/chunks |
|---|---:|---:|---:|---:|
| train | 9 / 17 | 6 / 17 | 17 / 17 | 2 / 17 |
| val | 4 / 8 | 4 / 8 | 8 / 8 | 1 / 8 |
| test | 5 / 9 | 4 / 9 | 9 / 9 | 1 / 9 |

Audit files:

- `recordwise_original_leakage_audit.csv`
- `recordwise_split_audit_summary.csv`
- `recordwise_split_audit_records.csv`
- `recordwise_split_leakage_check.csv`
- `recordwise_manifest.csv`

## Snapshot C24

Snapshot C24 was fixed. Feature thresholds, class weights, gate/boost, and C24 readout were not changed.

The prior fixed Python Snapshot C24 dumps were reused and relabeled into the new record-wise split. Each 30min chunk still contains 30 internal 60s snapshots.

## Baselines

Record-wise majority vote:

| split | correct/total | accuracy | macro-F1 |
|---|---:|---:|---:|
| train | 51/68 | 75.00% | 74.55% |
| val | 26/32 | 81.25% | 79.19% |
| test | 26/36 | 72.22% | 72.36% |

Average/raw-sum class-mem did not improve over majority on this split.

## Selected Final Layer

Selection used train/validation only. Test was evaluated after the validation-selected candidate was fixed.

Selected candidate:

- kind: `guarded_rule`
- candidate id: 177
- ARR rescue: `pred_count_ARR >= 8`
- AFF persistent rescue: majority CHF, `pred_count_CHF >= 8`, `pred_count_AFF >= 3`, `abnormal_evidence_sum >= 500`
- NSR overlay: disabled
- structure: snapshot pred spike counters + abnormal evidence accumulator + threshold rescue spike + class membrane WTA

## Python Metrics

| split | correct/total | accuracy | macro-F1 | balanced acc. |
|---|---:|---:|---:|---:|
| train | 46/68 | 67.65% | 67.15% | 67.65% |
| val | 28/32 | 87.50% | 86.67% | 87.50% |
| test | 24/36 | 66.67% | 66.50% | 66.67% |

Test confusion matrix, rows=true and columns=predicted `[NSR, CHF, ARR, AFF]`:

```text
[[7, 2, 0, 0],
 [0, 5, 1, 3],
 [2, 0, 6, 1],
 [1, 0, 2, 6]]
```

## RTL And XSim

Implemented final RTL:

- `rtl/final_membrane_layer.v`

Existing 30min top remains stream-based:

- `rtl/snn_ecg_30min_final_top.v`
- accepts one 30min ADC stream
- internally generates 60s snapshot boundaries with the timer-neuron structure
- does not accept pre-split 60s snapshots from outside

Full-stream XSim used actual 30min `.mem` files.

XSim metrics:

| split | correct/total | accuracy | macro-F1 | balanced acc. |
|---|---:|---:|---:|---:|
| train | 46/68 | 67.65% | 67.15% | 67.65% |
| val | 28/32 | 87.50% | 86.67% | 87.50% |
| test | 24/36 | 66.67% | 66.50% | 66.67% |

Python vs XSim equivalence:

- compared chunks: 136
- pred_class mismatches: 0
- final_mem[4] mismatches: 0

## Conclusion

Record-wise holdout exposes strong leakage in the previous chunk-wise split. Under the corrected record-wise split, the validation-selected final membrane layer does not improve blind test performance:

- majority test: 26/36 = 72.22%
- selected final layer test: 24/36 = 66.67%
- previous chunk-wise validation-selected result: 29/36 = 80.56%, not comparable because split leakage existed

The RTL implementation is functionally equivalent to the Python selected model, but the model itself does not meet the improvement target on record-wise holdout. The bottleneck is not RTL mismatch; it is generalization across held-out records after leakage removal.
