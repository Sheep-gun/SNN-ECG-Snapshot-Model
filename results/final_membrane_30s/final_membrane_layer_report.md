# Final Membrane Layer 30s Report

## Scope

- Dataset: `fullrec_afe_30s_annotation_valid_balanced`.
- Snapshot C24 was fixed. Its Python model is the bit-exact model in `scripts/snapshot_c24_rtl_exact.py`.
- Only the final membrane readout was trained using train data and selected by validation metrics.
- Test was evaluated once after selecting the validation winner.
- XSim verifies `rtl/final_membrane_layer.v` using the frozen Snapshot C24 dump columns as inputs to the final readout.

## Snapshot C24 Baseline

- train: 704/1080 = 65.19%, macro-F1 0.637
- val: 364/536 = 67.91%, macro-F1 0.665
- test: 366/540 = 67.78%, macro-F1 0.666

## Selected Final Layer

- selected candidate: 15666
- params: `{"cap": 0, "epochs": 6, "kind": "perceptron", "leak": 0, "lr": 4, "mem_init": 1, "pred_init": 0, "seed": 0, "tie_break": "lowest_class_index", "top_init": 0}`
- feature spikes/conditions: 270
- RTL structure: fixed condition spikes add signed integer weights into NSR/CHF/ARR/AFF final membranes, followed by WTA.
- DSP/floating point: none in the final-layer RTL source; thresholds use comparisons and constant shift/add expressions.

## Python Metrics

- train: 935/1080 = 86.57%, macro-F1 0.865, balanced 0.866, min recall 0.774
- val: 443/536 = 82.65%, macro-F1 0.827, balanced 0.826, min recall 0.784
- test: 435/540 = 80.56%, macro-F1 0.805, balanced 0.806, min recall 0.726

## XSim Metrics

- train: 935/1080 = 86.57%, macro-F1 0.865, balanced 0.866, min recall 0.774
  - confusion matrix rows=true NSR/CHF/ARR/AFF, cols=pred NSR/CHF/ARR/AFF: `[[230, 24, 12, 4], [3, 241, 18, 8], [24, 23, 209, 14], [1, 4, 10, 255]]`
  - NSR: precision 0.891, recall 0.852, F1 0.871, support 270
  - CHF: precision 0.825, recall 0.893, F1 0.858, support 270
  - ARR: precision 0.839, recall 0.774, F1 0.805, support 270
  - AFF: precision 0.907, recall 0.944, F1 0.926, support 270
- val: 443/536 = 82.65%, macro-F1 0.827, balanced 0.826, min recall 0.784
  - confusion matrix rows=true NSR/CHF/ARR/AFF, cols=pred NSR/CHF/ARR/AFF: `[[108, 14, 12, 0], [6, 112, 7, 9], [13, 11, 105, 5], [3, 5, 8, 118]]`
  - NSR: precision 0.831, recall 0.806, F1 0.818, support 134
  - CHF: precision 0.789, recall 0.836, F1 0.812, support 134
  - ARR: precision 0.795, recall 0.784, F1 0.789, support 134
  - AFF: precision 0.894, recall 0.881, F1 0.887, support 134
- test: 435/540 = 80.56%, macro-F1 0.805, balanced 0.806, min recall 0.726
  - confusion matrix rows=true NSR/CHF/ARR/AFF, cols=pred NSR/CHF/ARR/AFF: `[[112, 12, 8, 3], [9, 112, 9, 5], [9, 18, 98, 10], [6, 6, 10, 113]]`
  - NSR: precision 0.824, recall 0.830, F1 0.827, support 135
  - CHF: precision 0.757, recall 0.830, F1 0.792, support 135
  - ARR: precision 0.784, recall 0.726, F1 0.754, support 135
  - AFF: precision 0.863, recall 0.837, F1 0.850, support 135

## Python vs XSim

- compared cases: 2156
- pred_class mismatches: 0
- final_mem mismatches: 0

## Conclusion

Success: XSim test accuracy is 80.56%, meeting the 80% target.
