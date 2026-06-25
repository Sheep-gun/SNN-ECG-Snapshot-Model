# Model S Final Report

## Purpose

Model S is the final SNN-inspired RTL classifier selected for the 4-class ECG task. The target classes are:

- NSR: normal sinus rhythm
- CHF: congestive heart failure
- ARR: arrhythmia class containing ectopic and conduction-delay cases
- AFF: atrial fibrillation/flutter-like irregular rhythm

The project objective is not a software classifier, but a low-resource FPGA/SoC-friendly RTL classifier that processes a 1 kSPS signed 12-bit ECG stream.

## Final Definition

Model S is defined as:

```text
Model S = Model A+ + EERG
Model A+ = Model A + RBBB QRS Delay Bank(repeat_th=5)
```

Model A contains:

- QRS LIF detector
- pNN125 rhythm predictor
- RDM variability feature
- DSCR slope sign-change feature
- RAM R-peak amplitude feature
- ECP ectopic compensatory pair feature
- QRS MAF morphology abnormal feature
- direct spike-to-class local membrane WTA structure

Model A+ adds RBBB QRS Delay Bank. Model S adds EERG readout logic.

## Classifier Structure

```text
adc_data
-> ecg_event_encoder
-> qrs_lif_detector
-> beat_spike
-> feature spike generation
-> 60 s local class membrane
-> segment membrane accumulation
-> RBBB/EERG readout correction
-> WTA comparator
-> pred_class
```

The class decision is made by four signed class membranes: `NSR`, `CHF`, `ARR`, and `AFF`. Feature events directly add or subtract fixed signed weights. At `segment_done`, the largest membrane is selected by WTA.

## Verification Result

| split | segment accuracy | record accuracy | macro-F1 | balanced accuracy |
|---|---:|---:|---:|---:|
| train | 313/400 = 78.25% | 41/50 = 82.00% | 78.22% | 78.25% |
| validation | 136/160 = 85.00% | 18/20 = 90.00% | 84.91% | 85.00% |
| test | 131/160 = 81.88% | 18/19 = 94.74% | 81.93% | 81.88% |

Test confusion matrix:

| actual | pred NSR | pred CHF | pred ARR | pred AFF |
|---|---:|---:|---:|---:|
| NSR | 31 | 0 | 9 | 0 |
| CHF | 0 | 37 | 3 | 0 |
| ARR | 6 | 0 | 28 | 6 |
| AFF | 0 | 3 | 2 | 35 |

Record-level test confusion:

| actual | pred NSR | pred CHF | pred ARR | pred AFF |
|---|---:|---:|---:|---:|
| NSR | 3 | 0 | 0 | 0 |
| CHF | 0 | 3 | 0 | 0 |
| ARR | 0 | 0 | 8 | 1 |
| AFF | 0 | 0 | 0 | 4 |

## Interpretation

The segment-level result is the per-window classifier result. The record-level result is the patient/record-level decision formed by accumulating multiple segment scores from the same record. Model S should be described as a multi-window record-level ECG classifier rather than a single-short-window clinical diagnosis engine.

## Resource Result

Core-only synthesis remains low-resource:

- LUT: 5309 / 63400 = 8.37%
- FF: 1250 / 126800 = 0.99%
- BRAM: 0
- DSP: 0

This supports the claim that Model S is multiplier-free and BRAM-free at classifier-core level.
