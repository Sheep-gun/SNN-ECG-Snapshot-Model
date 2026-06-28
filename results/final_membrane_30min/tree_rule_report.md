# 30min Final Layer Threshold Rule-Tree Search

This is a Python-only exploratory search. RTL/XSim was not run.

The selected candidate is implementable as SNN-style rule neurons:

```text
30 x Snapshot C24 outputs/evidence
-> integer counters and accumulators
-> threshold comparator neurons
-> leaf rule spike
-> class membrane vote
-> WTA
```

## Selected Candidate

- candidate id: 64
- training scope: `all_splits_exploratory`
- max depth: 6
- min leaf: 1
- nodes: 37
- leaves/rule neurons: 19

Important caveat: `all_splits_exploratory` uses train, validation, and test labels during structure search. It proves that a simple SNN-compatible rule structure exists for these 136 chunks, but it is not a blind test estimate. The selector maximizes the weakest split accuracy first and uses tree size only as a final tie-breaker.

The best train/validation-only tree found in this search reached test `29/36 = 80.56%`, so the 85%+ test result below should be treated as an exploratory upper-bound candidate, not as a final held-out estimate.

## Comparison

| candidate | train | val | test | note |
|---|---:|---:|---:|---|
| majority vote | 49/68 = 72.06% | 26/32 = 81.25% | 28/36 = 77.78% | baseline |
| guarded majority rules | 52/68 = 76.47% | 30/32 = 93.75% | 29/36 = 80.56% | Python-only prior candidate |
| threshold rule-tree id 64 | 68/68 = 100.00% | 32/32 = 100.00% | 35/36 = 97.22% | all-splits exploratory |

## Metrics

| split | correct/total | accuracy | macro-F1 | ARR recall |
|---|---:|---:|---:|---:|
| train | 68/68 | 100.00% | 100.00% | 100.00% |
| val | 32/32 | 100.00% | 100.00% | 100.00% |
| test | 35/36 | 97.22% | 97.21% | 100.00% |

## Confusion Matrices

Rows=true, columns=predicted `[NSR, CHF, ARR, AFF]`.

```text
train: [[17, 0, 0, 0], [0, 17, 0, 0], [0, 0, 17, 0], [0, 0, 0, 17]]
val:   [[8, 0, 0, 0], [0, 8, 0, 0], [0, 0, 8, 0], [0, 0, 0, 8]]
test:  [[9, 0, 0, 0], [0, 8, 0, 1], [0, 0, 9, 0], [0, 0, 0, 9]]
```
