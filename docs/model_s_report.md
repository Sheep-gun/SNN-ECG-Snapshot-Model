# Model S ?? ???

## ??

Model S? NSR / CHF / ARR / AFF ? ?? ECG class? ???? ?? ??? ?? SNN-inspired RTL classifier???. ??? software classifier? ???, 1 kSPS signed 12-bit ECG stream? ?? ???? low-resource FPGA/SoC-friendly RTL classifier???.

## ?? ??

```text
Model S = Model A+ + EERG
Model A+ = Model A + RBBB QRS Delay Bank(repeat_th=5)
```

Model A?? ?? feature? ?????.

- QRS LIF detector
- pNN125 rhythm predictor
- RDM variability feature
- DSCR slope sign-change feature
- RAM R-peak amplitude feature
- ECP ectopic compensatory pair feature
- QRS MAF morphology abnormal feature
- direct spike-to-class local membrane WTA ??

Model A+? RBBB QRS Delay Bank? ????, Model S? EERG readout logic? ??? ?? ?????.

## Classifier ??

```text
adc_data
-> ecg_event_encoder
-> qrs_lif_detector
-> beat_spike
-> feature spike generation
-> 60? local class membrane
-> segment membrane accumulation
-> RBBB/EERG readout correction
-> WTA comparator
-> pred_class
```

Class decision? NSR, CHF, ARR, AFF ? ? signed class membrane?? ??????. Feature event? ??? ??? fixed signed weight? ????? ???, `segment_done`?? ?? ? membrane? WTA? ?????.

## ?? ??

| split | segment accuracy | record accuracy | macro-F1 | balanced accuracy |
|---|---:|---:|---:|---:|
| train | 313/400 = 78.25% | 41/50 = 82.00% | 78.22% | 78.25% |
| validation | 136/160 = 85.00% | 18/20 = 90.00% | 84.91% | 85.00% |
| test | 131/160 = 81.88% | 18/19 = 94.74% | 81.93% | 81.88% |

Test segment confusion matrix:

| actual | pred NSR | pred CHF | pred ARR | pred AFF |
|---|---:|---:|---:|---:|
| NSR | 31 | 0 | 9 | 0 |
| CHF | 0 | 37 | 3 | 0 |
| ARR | 6 | 0 | 28 | 6 |
| AFF | 0 | 3 | 2 | 35 |

Test record confusion matrix:

| actual | pred NSR | pred CHF | pred ARR | pred AFF |
|---|---:|---:|---:|---:|
| NSR | 3 | 0 | 0 | 0 |
| CHF | 0 | 3 | 0 | 0 |
| ARR | 0 | 0 | 8 | 1 |
| AFF | 0 | 0 | 0 | 4 |

## ??

Segment-level ??? ?? ECG window ?? ?????. Record-level ??? ?? record?? ?? ?? segment score? ??? ??/record ?? ?????. ??? Model S? single short segment diagnosis??? multi-window record-level ECG classifier? ???? ?? ????.

## ?? ???

Core-only ?? ??? ??? ????.

- LUT: 5309 / 63400 = 8.37%
- FF: 1250 / 126800 = 0.99%
- BRAM: 0%
- DSP: 0%

? ??? Model S? multiplier-free, BRAM-free classifier core?? ??? ??????.
