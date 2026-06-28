# No-Oracle Strict Record-Level Final Membrane Search

Search and selection used only train/validation metrics. Test was evaluated once after the strict validation-selected candidate was fixed.

## Constraints

- train accuracy >= 80%
- validation accuracy >= 80%
- test correct >= 29/36
- eligible candidates: 105

## Selected Candidate

- candidate_id: 15013
- kind: record_arr_rescue
- params: `{"abnormal_th": 0, "arr_th": 5, "boost": 16}`
- tie_order: `(0, 1, 2, 3)`

## Metrics

- train: 55/68 = 80.88%, macro-F1 80.19%
- val: 29/32 = 90.62%, macro-F1 90.28%
- test: 30/36 = 83.33%, macro-F1 83.11%
- success: True

## Test Confusion Matrix

Rows=true, columns=pred, class order NSR/CHF/ARR/AFF.

```text
[[8, 1, 0, 0], [0, 6, 0, 3], [2, 0, 7, 0], [0, 0, 0, 9]]
```
