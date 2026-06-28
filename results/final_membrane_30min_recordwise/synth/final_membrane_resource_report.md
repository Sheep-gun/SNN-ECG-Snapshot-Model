# Final Membrane Resource Report

## Synthesis Setup

- Tool: Vivado 2020.2 synthesis
- Part: `xc7a100tcsg324-1`
- Mode: synthesis-only `report_utilization`
- Script: `synth_final_membrane_resources.tcl`
- Output directory: `results/final_membrane_30min_recordwise/synth`

No DSP or BRAM is used by the final membrane logic.

## Summary

| Design | LUTs | FFs | BRAM36 | BRAM18 | DSP | Note |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `record_level_final_membrane_layer` | 142 | 132 | 0 | 0 | 0 | Standalone record-level layer |
| `final_membrane_layer` | 52 | 27 | 0 | 0 | 0 | 30-minute chunk vote counter |
| `final_membrane_record_chain_synth_top` | 163 | 157 | 0 | 0 | 0 | Chunk vote + record-level final membrane |
| `snn_ecg_30min_final_top` | 20,147 | 2,129 | 0 | 0 | 0 | Snapshot C24 30-minute top, without record-level layer |
| `snn_ecg_30min_record_final_synth_top` | 20,256 | 2,259 | 0 | 0 | 0 | Full top including record-level final membrane |

## Incremental Cost

Adding the record-level final membrane to the synthesized 30-minute Snapshot C24 top changes the design from:

```text
20,147 LUT / 2,129 FF
```

to:

```text
20,256 LUT / 2,259 FF
```

Incremental cost:

```text
+109 LUT
+130 FF
+0 DSP
+0 BRAM
```

This means the final record-level membrane is small compared with the Snapshot C24 feature/readout core. The dominant LUT usage remains inside the Snapshot C24 path, especially `class_score_neurons`, `rdm_variability_neuron`, `qrs_maf_neuron`, and `rbbb_qrs_delay_bank`.

## Hierarchical Full-Top Notes

In the full synthesized hierarchy:

- `u_chunk_top/u_final` (`final_membrane_layer`): 42 LUT / 25 FF
- `u_record_mem` (`record_level_final_membrane_layer`): 53 LUT / 132 FF

The top-level delta is slightly larger than the sum of these hierarchy rows because Vivado can move or rebuild small comparator/add logic across hierarchy boundaries during `-flatten_hierarchy rebuilt` synthesis.
