# 30min Final Membrane Layer Report

Status: complete for the requested Python search, RTL implementation, and full 30min ADC-stream XSim verification. The 90% test-accuracy target was not met; the validation-selected RTL result is reported without test-set retuning.

## Dataset

- Dataset: `C:\Users\YangGeon\SNN_ECG_RESTORE_MODEL_S\fullrec_afe_30min_annotation_valid_balanced`
- Manifest: `annotation_valid_balanced_30min_manifest.csv`
- Total chunks: 136
- Chunk length: 30 minutes, 1,800,000 signed 12-bit AFE+ADC samples at 1 kSPS
- Snapshot structure: each 30min chunk is split inside the model into 30 non-overlapping 60s snapshots of 60,000 samples

Split/class counts:

| split | NSR | CHF | ARR | AFF | total |
|---|---:|---:|---:|---:|---:|
| train | 17 | 17 | 17 | 17 | 68 |
| val | 8 | 8 | 8 | 8 | 32 |
| test | 9 | 9 | 9 | 9 | 36 |

## Fixed Snapshot C24

Snapshot C24 was frozen. Feature thresholds, class weights, gate/boost behavior, and C24 readout were not retuned.

The Python snapshot dump was generated with `scripts/snapshot_c24_rtl_exact.py`, one 30min chunk at a time, split into 30 snapshots. Generated files:

- `snapshot_dump_train.csv`: 2040 snapshots
- `snapshot_dump_val.csv`: 960 snapshots
- `snapshot_dump_test.csv`: 1080 snapshots

Each snapshot row includes C24 `pred_class`, `class_mem_NSR/CHF/ARR/AFF`, and QRS/pNN/RDM/DSCR/RAM/ECP/QRS-MAF/RBBB/EERG evidence counts.

## Final Membrane Search

The final membrane layer is an SNN-style integer accumulator over 30 snapshot events:

```text
30min AFE+ADC stream
-> 60s Snapshot C24 reset/evaluate, repeated 30 times
-> final_mem[NSR/CHF/ARR/AFF] integer accumulation
-> 30min WTA
```

Selected candidate:

- candidate id: 60687
- base candidate: 53280
- kind: `threshold_overlay`
- overlay feature: `pred_count_NSR_ge_13`
- overlay target: NSR
- overlay boost: 131072
- cap: 0
- leak: 0
- tie-break: lowest class index

Selection rule: validation accuracy, validation macro-F1, validation balanced accuracy, validation min recall, validation recall range, then train accuracy/macro-F1 as tie-break. Test was evaluated once after selection.

## Python Metrics

| split | correct/total | accuracy | macro-F1 | balanced acc. |
|---|---:|---:|---:|---:|
| train | 60/68 | 88.24% | 88.37% | 88.24% |
| val | 29/32 | 90.62% | 90.40% | 90.62% |
| test | 28/36 | 77.78% | 76.59% | 77.78% |

## RTL Implementation

Implemented/modified files:

- `rtl/final_membrane_layer.v`
- `rtl/snn_ecg_30min_final_top.v`
- `sim/tb_snn_ecg_30min_final_dataset.v`
- `sim/tb_final_membrane_layer_dataset.v`
- `rtl/core/class_score_neurons.v`
- `rtl/core/snn_ecg_3feat_top.v`
- `SNN_ECG.srcs/sources_1/new/class_score_neurons.v`
- `SNN_ECG.srcs/sources_1/new/snn_ecg_3feat_top.v`

`snn_ecg_30min_final_top.v` accepts one 30min ADC stream with `sample_ready` backpressure. A timer-neuron block integrates accepted `sample_tick_spike` events into `timer_mem`; when the 60s membrane threshold is reached, it emits `snapshot_boundary_spike`, resets Snapshot C24 for the next 60s window, accumulates the 30 snapshot outputs in `final_membrane_layer`, and emits the 30min WTA result.

The final layer/top wrapper use counters, comparators, signed accumulators, and add/subtract logic. Source scan found no multiplication operator in `rtl/final_membrane_layer.v` or `rtl/snn_ecg_30min_final_top.v` except `always @(*)`, so no explicit multiplier/DSP structure was introduced.

## XSim Verification

Full stream XSim used the actual 30min `.mem` files, not precomputed snapshot rows. All samples were driven through `snn_ecg_30min_final_top.v`; the timer-neuron wrapper generated the 60s Snapshot C24 boundary spikes internally.

XSim metrics:

| split | correct/total | accuracy | macro-F1 | balanced acc. |
|---|---:|---:|---:|---:|
| train | 60/68 | 88.24% | 88.37% | 88.24% |
| val | 29/32 | 90.62% | 90.40% | 90.62% |
| test | 28/36 | 77.78% | 76.59% | 77.78% |

Python vs full-stream XSim:

- compared chunks: 136
- final `pred_class` mismatches: 0
- final `final_mem[4]` mismatches: 0
- missing `final_valid`: 0
- compare file: `python_vs_xsim_compare.csv`

Timer-neuron refactor smoke check:

- case id: 15
- samples driven: 1,800,000
- final `pred_class`: 0
- `final_mem[NSR/CHF/ARR/AFF]`: `[237393, -86411, -63942, -152140]`
- matches previous full-stream XSim result for the same case: yes

Test confusion matrix, rows=true and columns=predicted `[NSR, CHF, ARR, AFF]`:

```text
NSR: [9, 0, 0, 0]
CHF: [0, 7, 0, 2]
ARR: [4, 1, 4, 0]
AFF: [1, 0, 0, 8]
```

Per-class test recall:

- NSR: 100.00%
- CHF: 77.78%
- ARR: 44.44%
- AFF: 88.89%

## Target Status

The requested RTL/XSim equivalence was achieved: Python final membrane and full-stream XSim produce identical `pred_class` and `final_mem[4]` on all 136 chunks.

The requested 90% test accuracy was not achieved. The final validation-selected RTL result is 77.78% on test.

The main bottleneck is ARR recall. On test, ARR is often pulled toward NSR: 4 of 9 ARR chunks are predicted as NSR, and 1 of 9 as CHF. Since test was not used for parameter selection, this is reported as a limitation rather than retuned away.

The failure appears to be a Snapshot-C24/final-layer separability issue on the held-out ARR 30min chunks: validation-selected final accumulation can rescue validation to 90.62%, but the same fixed rule does not generalize to ARR-heavy held-out chunks.
