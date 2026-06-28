# Patient-Level Membrane Layer Python Equivalent

## Dataset

| split | NSR | CHF | ARR | AFF | total | windows |
|---|---:|---:|---:|---:|---:|---:|
| train | 9 | 8 | 9 | 9 | 35 | 28492 |
| val | 3 | 3 | 3 | 3 | 12 | 9826 |
| test | 3 | 3 | 3 | 3 | 12 | 9891 |

## Selected Final Layer

- candidate_id: 15504
- margin_threshold: 100000000
- use_rates: True
- l2: 0.3
- boosts: {'NSR': 1.2, 'CHF': 1.2, 'ARR': 0.9, 'AFF': 0.9}
- structure: each 60 s Snapshot C24 window emits pred/confidence/evidence spikes; patient_mem[4] accumulates learned signed integer weights; record_done uses WTA.

## Metrics

| split | accuracy | correct/total | macro-F1 | balanced accuracy | fixed mismatch |
|---|---:|---:|---:|---:|---:|
| train | 0.9429 | 33/35 | 0.9428 | 0.9444 | 0 |
| val | 0.9167 | 11/12 | 0.9143 | 0.9167 | 0 |
| test | 0.5833 | 7/12 | 0.5417 | 0.5833 | 0 |

## Baselines

| split | baseline | accuracy | correct/total | macro-F1 | balanced accuracy |
|---|---|---:|---:|---:|---:|
| train | majority_vote | 0.4000 | 14/35 | 0.3220 | 0.3889 |
| train | mean_c24_mem | 0.4000 | 14/35 | 0.3358 | 0.3889 |
| val | majority_vote | 0.4167 | 5/12 | 0.3464 | 0.4167 |
| val | mean_c24_mem | 0.3333 | 4/12 | 0.2333 | 0.3333 |
| test | majority_vote | 0.5833 | 7/12 | 0.5929 | 0.5833 |
| test | mean_c24_mem | 0.5833 | 7/12 | 0.5929 | 0.5833 |

## Notes

- Snapshot C24 weights are fixed from `results/c24_rtl_equivalence/c24_folded_weights_for_rtl.json`.
- This is a Python equivalent exploration of the patient-level final layer, not an RTL/XSim equivalence result.
- Test-set records are evaluated only after selecting the final-layer candidate from train/validation.
