# Dataset and Evaluation

## Split Principle

The final dataset uses strict record-wise split. A record can appear in only one split:

- train
- validation
- test

Segments from the same patient/record are not allowed to appear in multiple splits. This prevents record leakage.

## Segment Format

Each ECG segment is converted to:

```text
1 kSPS signed 12-bit .mem
```

The RTL testbench reads the `.mem` stream as `adc_data`.

## Segment Lengths

The strict dataset includes variable-length segments:

- 60 s
- 90 s
- 120 s
- 130 s
- 150 s
- 180 s

Model S uses 60-second local windows and segment-level accumulation to reduce length bias.

## Evaluation Policy

- Train: threshold/weight candidate exploration
- Validation: final parameter selection
- Test: fixed final Model S evaluation only

The test split must not be used to tune thresholds, class weights, feature rules, or readout gates.

## Final Metrics

| split | segment accuracy | record accuracy |
|---|---:|---:|
| train | 313/400 = 78.25% | 41/50 = 82.00% |
| validation | 136/160 = 85.00% | 18/20 = 90.00% |
| test | 131/160 = 81.88% | 18/19 = 94.74% |

## Included Data Files

This repository includes manifests and result CSVs, but not the full strict `.mem` dataset. The full dataset can be regenerated from the source ECG records and manifest policy or copied from the local restore workspace.

Compact 4-class demo `.mem` files are included for AFE/demo reference.
