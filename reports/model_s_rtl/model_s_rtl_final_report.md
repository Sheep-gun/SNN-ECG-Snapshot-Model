# Model S RTL Verification Report

## Scope

- This report is generated from XSim CSV output produced by the restored synthesizable RTL.
- EERG is inside RTL in this version. It is not applied by Python post-processing.
- Source root: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S`

## Split Metrics

| split | segment accuracy | record accuracy | macro-F1 | balanced acc | EERG applied segments | RBBB-delay applied segments |
|---|---:|---:|---:|---:|---:|---:|
| train | 313/400 = 78.25% | 41/50 = 82.00% | 78.22% | 78.25% | 33 | 14 |
| val | 136/160 = 85.00% | 18/20 = 90.00% | 84.91% | 85.00% | 11 | 5 |
| test | 131/160 = 81.88% | 18/19 = 94.74% | 81.93% | 81.88% | 6 | 10 |

## Target Comparison

| split | segment | record | class correct actual | class correct target | note |
|---|---:|---:|---|---|---|
| train | 313/400 vs 313/400 | 41/50 vs 41/50 | 84/76/71/82 | 85/76/70/82 | total target matched but class distribution differs |
| val | 136/160 vs 136/160 | 18/20 vs 18/20 | 36/31/38/31 | 36/31/38/31 | matches target |
| test | 131/160 vs 131/160 | 18/19 vs 18/19 | 31/37/28/35 | 31/37/28/35 | matches target |

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

## Notes

- XSim completed for train, validation, and test without fatal simulation errors.
- The remaining compile warnings are width/unconnected-port warnings in abandoned compatibility stubs; they do not affect the selected Model S path.
- The restored RTL test result matches the documented Model S test target exactly at segment and record level.
- Train total accuracy matches the target; NSR and ARR class correct counts are swapped by one segment compared with the historical post-readout record.

