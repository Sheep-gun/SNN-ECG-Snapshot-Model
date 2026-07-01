# SNN ECG V2 Final Membrane XSim Report

Candidate: `margin_evidence_0038974`.

Structure: 30-minute ADC stream -> timer neuron 60s snapshot spikes -> Snapshot V2 -> final membrane evidence current -> WTA.

| Split | Python | XSim | Pred mismatch | Mem mismatch |
|---|---:|---:|---:|---:|
| train | 62/68 = 0.9118 | 62/68 = 0.9118 | 0 | 0 |
| val | 31/32 = 0.9688 | 31/32 = 0.9688 | 0 | 0 |
| test | 32/36 = 0.8889 | 32/36 = 0.8889 | 0 | 0 |

Final membrane rescue neuron:

```text
if arr_focus_pred == AFF and arr_focus_margin <= 12 and pred_count_ARR >= 3
   and rdm_code_sum >= 512 and pNN_mismatch >= 800
   and ectopic_pair >= 256 and abnormal_evidence >= 256:
    final_mem_ARR += 4
    final_mem_AFF -= 16
```
