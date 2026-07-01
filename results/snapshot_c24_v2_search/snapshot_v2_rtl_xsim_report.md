# Snapshot V2 RTL/XSim Verification Report

## Model Definition

**Snapshot V2** is the active 60-second SNN ECG snapshot classifier.

- Base model: Snapshot C24 folded spike readout
- Input: 60-second AFE+ADC signed 12-bit `.mem`
- Output: `pred_class`, `c24_mem_NSR/CHF/ARR/AFF`
- Structural change from C24: EERG direct C24 class-membrane contribution removed
- Inactive: 30-minute downstream accumulation/readout candidates

## RTL Mapping

Active RTL files:

- `rtl/core/snn_ecg_3feat_top.v`
- `rtl/core/class_score_neurons.v`
- `sim/tb_snapshot_c24_dataset.v`

The classifier remains SNN-inspired:

```text
feature spike/count
-> fixed signed synaptic weight accumulation into class membranes
-> 60s segment_done
-> 4-class WTA
-> pred_class
```

No floating point, divider, or DSP multiplier is introduced by the readout.

## Enabled Feature Groups

| Feature group | Status |
|---|---:|
| PNN | enabled |
| RDM | enabled |
| DSCR | enabled |
| RAM | enabled |
| ECP | enabled |
| QRS MAF | enabled |
| RBBB | enabled |
| EERG direct class-membrane contribution | removed |

## XSim Testbench

Runner:

```powershell
python scripts\run_snapshot_v2_xsim.py --split train
python scripts\run_snapshot_v2_xsim.py --split val
python scripts\run_snapshot_v2_xsim.py --split test
```

The testbench drives each 60-second `.mem` window into `snn_ecg_3feat_top` and dumps:

- `expected_class`
- `pred_class`
- `pred_valid`
- `class_mem_NSR`
- `class_mem_CHF`
- `class_mem_ARR`
- `class_mem_AFF`

## Stored XSim Results

| Split | Correct / Total | Accuracy | Macro-F1 | Balanced Acc. |
|---|---:|---:|---:|---:|
| train | 466 / 512 | 91.02% | 90.96% | 91.02% |
| val | 231 / 256 | 90.23% | 90.29% | 90.23% |
| test | 205 / 256 | 80.08% | 80.06% | 80.08% |

## Interpretation

Snapshot V2 is the current clean active model. The discarded downstream 30-minute readout candidates are no longer part of the RTL path.

The remaining known limitation is ARR recall on the 60-second test windows. The active test result is:

```text
test: 205 / 256 = 80.08%
```
