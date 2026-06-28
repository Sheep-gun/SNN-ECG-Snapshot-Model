# Majority-Guard Final Membrane Rule Search

This is a Python-only search. RTL/XSim was intentionally not run.

## Baseline

Majority vote is the baseline.

| split | accuracy | macro-F1 | ARR recall |
|---|---:|---:|---:|
| train | 72.06% | 71.48% | 52.94% |
| val | 81.25% | 80.78% | 75.00% |
| test | 77.78% | 77.80% | 66.67% |

## Selected Candidate

- candidate id: 2751
- ARR protection param: `(10, 0, 30)`
- AFF quiet rescue param: `(18, 0, 150, 25)`
- AFF persistent rescue param: `(10, 5, 2500)`
- NSR overlay param: `None`

NSR overlay is not standalone. It is blocked by ARR protection and by any RBBB/EERG/ECP/RDM/QRS-MAF/ectopic/pNN abnormal evidence.

## Selected Metrics

| split | accuracy | macro-F1 | ARR recall |
|---|---:|---:|---:|
| train | 76.47% | 76.06% | 52.94% |
| val | 93.75% | 93.75% | 87.50% |
| test | 80.56% | 80.50% | 66.67% |

## Test Confusion Matrix

Rows=true, columns=predicted `[NSR, CHF, ARR, AFF]`.

```text
[[8, 1, 0, 0], [0, 7, 0, 2], [2, 1, 6, 0], [1, 0, 0, 8]]
```
