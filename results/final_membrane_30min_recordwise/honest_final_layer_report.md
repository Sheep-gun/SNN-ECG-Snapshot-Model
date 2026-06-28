# Honest Final Membrane Search

No oracle/test-guided candidate selection was used.

## Selection Rule

- Generate candidates from train split only.
- Select the final candidate by validation macro-F1, balanced accuracy, ARR recall, recall balance, accuracy, and simplicity.
- A candidate is admissible only if validation macro-F1 and validation ARR recall are at least the majority-vote baseline.
- Evaluate test once after the validation-selected candidate is fixed.

## Majority Baseline

- train: 51/68 = 75.00%, macro-F1 74.55%, ARR recall 70.59%
- val: 26/32 = 81.25%, macro-F1 79.19%, ARR recall 37.50%
- test: 26/36 = 72.22%, macro-F1 72.36%, ARR recall 66.67%

## Selected Candidate

- candidate_id: 7846
- kind: single_threshold_override
- admissible candidates: 5756/26250
- params: `{"base": "majority", "direction": "gt", "feature": "ectopic_pair_count_max", "source_class": "NSR", "target_class": "ARR", "threshold": 6.2}`

## Honest Result

- train: 48/68 = 70.59%, macro-F1 69.78%, ARR recall 88.24%
- val: 30/32 = 93.75%, macro-F1 93.89%, ARR recall 87.50%
- test: 26/36 = 72.22%, macro-F1 72.36%, ARR recall 77.78%

## Test Confusion Matrix

Rows=true, columns=pred, class order NSR/CHF/ARR/AFF.

```text
[[6, 2, 1, 0], [0, 7, 0, 2], [1, 0, 7, 1], [0, 0, 3, 6]]
```
