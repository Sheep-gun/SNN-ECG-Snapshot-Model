# No-Oracle Record-Level Final Membrane Search

Search and selection used only train/validation metrics. Test was evaluated once after the validation-selected candidate was fixed.

## Selected Candidate

- candidate_id: 15014
- kind: record_arr_rescue
- params: `{"abnormal_th": 0, "arr_th": 5, "boost": 32}`
- tie_order: `(0, 1, 2, 3)`

## Metrics

- train: 48/68 = 70.59%, macro-F1 70.50%
- val: 31/32 = 96.88%, macro-F1 96.86%
- test: 30/36 = 83.33%, macro-F1 83.11%

## Test Confusion Matrix

Rows=true, columns=pred, class order NSR/CHF/ARR/AFF.

```text
[[8, 1, 0, 0], [0, 6, 0, 3], [2, 0, 7, 0], [0, 0, 0, 9]]
```
