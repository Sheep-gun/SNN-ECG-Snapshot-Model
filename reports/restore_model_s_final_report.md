# Model S Restore Final Report

## Working Folder

- Restore root: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S`
- Original project folder was not written by this restore flow.
- Vivado project: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/vivado_project/SNN_ECG_ModelS_Restore/SNN_ECG_ModelS_Restore.xpr`

## Restored Model Definition

Model S was restored as a synthesizable RTL path:

- Model A base feature path
- RBBB QRS Delay Bank
- EERG inside RTL

EERG is not a Python post-processing step in this version. The EERG gate is implemented in `class_score_neurons.v` and connected through `snn_ecg_3feat_top.v`.

## Main RTL Changes

- `qrs_maf_neuron.v`
  - Added `pre_qrs_bump_spike`.
  - Fixed it to behave as a one-clock pulse instead of a latch-like debug signal.

- `class_score_neurons.v`
  - Added EERG segment counters.
  - Added EERG gate condition:
    - no RBBB-like repeated beat evidence
    - pre-QRS bump evidence present
    - early or ectopic-pair evidence present
    - low pNN mismatch rate
    - low RDM average code
  - Added `W_EERG_ARR_BOOST = 25000` to ARR membrane when the EERG gate fires.

- `snn_ecg_3feat_top.v`
  - Connected pre-QRS bump and EERG debug signals.

- `tb_snn_ecg_3feat_dataset.v`
  - Added EERG debug dump columns.
  - Fixed CSV field alignment.

## XSim Results

All train/validation/test simulations completed and the CSV outputs are column-consistent.

| split | segment accuracy | record accuracy | macro-F1 | balanced acc | EERG applied segments | RBBB-delay applied segments |
|---|---:|---:|---:|---:|---:|---:|
| train | 313/400 = 78.25% | 41/50 = 82.00% | 78.22% | 78.25% | 33 | 14 |
| val | 136/160 = 85.00% | 18/20 = 90.00% | 84.91% | 85.00% | 11 | 5 |
| test | 131/160 = 81.88% | 18/19 = 94.74% | 81.93% | 81.88% | 6 | 10 |

## Target Comparison

| split | actual segment | target segment | actual record | target record | class correct actual | class correct target |
|---|---:|---:|---:|---:|---|---|
| train | 313/400 | 313/400 | 41/50 | 41/50 | 84/76/71/82 | 85/76/70/82 |
| val | 136/160 | 136/160 | 18/20 | 18/20 | 36/31/38/31 | 36/31/38/31 |
| test | 131/160 | 131/160 | 18/19 | 18/19 | 31/37/28/35 | 31/37/28/35 |

Train total accuracy and record accuracy match the target. The train NSR and ARR class correct counts differ by one segment from the historical post-readout note. Validation and test match the documented Model S target exactly.

## EERG Equivalence Check

The restored RTL EERG path was compared against the historical Python post-readout EERG reference.

| split | total | final pred mismatch | EERG gate mismatch |
|---|---:|---:|---:|
| train | 400 | 2 | 19 |
| val | 160 | 0 | 6 |
| test | 160 | 0 | 0 |

The strict test set is fully equivalent to the historical Model S post-readout result. Train/validation gate booleans are not byte-equivalent because the previous Python path used offline annotation/pre-QRS statistics, while the restored RTL uses streaming, synthesizable counters and a pre-QRS bump proxy. Final validation predictions still match, and final test predictions/gates match exactly.

## Test Segment Confusion

| actual | pred NSR | pred CHF | pred ARR | pred AFF |
|---|---:|---:|---:|---:|
| NSR | 31 | 0 | 9 | 0 |
| CHF | 0 | 37 | 3 | 0 |
| ARR | 6 | 0 | 28 | 6 |
| AFF | 0 | 3 | 2 | 35 |

## Test Record Confusion

| actual | pred NSR | pred CHF | pred ARR | pred AFF |
|---|---:|---:|---:|---:|
| NSR | 3 | 0 | 0 | 0 |
| CHF | 0 | 3 | 0 | 0 |
| ARR | 0 | 0 | 8 | 1 |
| AFF | 0 | 0 | 0 | 4 |

## Synthesis

Vivado `synth_design` completed successfully for `xc7a100tcsg324-1`.

| resource | used | available | util |
|---|---:|---:|---:|
| Slice LUTs | 5309 | 63400 | 8.37% |
| Slice Registers | 1250 | 126800 | 0.99% |
| Block RAM Tile | 0 | 135 | 0.00% |
| DSPs | 0 | 240 | 0.00% |
| Bonded IOB | 21 | 210 | 10.00% |
| BUFGCTRL | 1 | 32 | 3.13% |

The restored path remains DSP-free and BRAM-free.

## Generated Reports

- `reports/model_s_rtl/model_s_rtl_final_report.md`
- `reports/model_s_rtl/model_s_rtl_split_metrics.csv`
- `reports/model_s_rtl/model_s_rtl_test_confusion.csv`
- `reports/model_s_rtl/model_s_rtl_test_record_confusion.csv`
- `reports/model_s_rtl/eerg_rtl_equivalence_report.md`
- `reports/model_s_rtl/eerg_rtl_equivalence_train.csv`
- `reports/model_s_rtl/eerg_rtl_equivalence_val.csv`
- `reports/model_s_rtl/eerg_rtl_equivalence_test.csv`
- `reports/synth/model_s_rtl_synth_report.md`
- `reports/synth/model_s_rtl_synth_utilization.csv`
- `restored_sources_file_list.txt`

## Remaining Notes

- The wrapper module name is still `snn_ecg_model_a_plus_core` for compatibility with the restored scripts, but EERG is enabled inside the RTL path. Functionally this is Model S.
- Timing is synthesis-only and currently unconstrained because no XDC file is attached. Board-level clock/input/output constraints are still needed before implementation/bitstream timing closure.
- Compile warnings are mainly unconnected debug outputs and abandoned compatibility stubs. The selected Model S datapath compiles and synthesizes.
