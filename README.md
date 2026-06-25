# SNN ECG Model S RTL Classifier

SNN-inspired ECG 4-class RTL classifier for **NSR / CHF / ARR / AFF** classification.

This repository is a GitHub-ready project package distilled from the final Model S RTL restore, strict record-wise verification, Nexys A7 FPGA demo, and analog/mixed-signal integration reports.

## Final Model

**Model S = Model A+ + EERG**

Model A+ is Model A with the RBBB QRS Delay Bank enabled. EERG is an Episodic Ectopic Rescue Gate implemented in RTL readout logic.

Active feature path:

```text
1 kSPS signed 12-bit ECG adc_data
-> event encoder
-> QRS LIF detector
-> pNN125 / RDM / DSCR / RAM / ECP / QRS MAF / RBBB evidence
-> 60 s local class neuron membranes
-> segment-level class membrane accumulation
-> RBBB/EERG readout adjustment
-> 4-class WTA
-> pred_class
```

The classifier uses fixed signed synaptic weights and comparator/counter/shift logic. It does not use DSP multipliers, floating point, STDP, or backpropagation.

## Key Results

### Strict record-wise RTL verification

| split | segment accuracy | record accuracy | macro-F1 | balanced accuracy |
|---|---:|---:|---:|---:|
| train | 313/400 = 78.25% | 41/50 = 82.00% | 78.22% | 78.25% |
| validation | 136/160 = 85.00% | 18/20 = 90.00% | 84.91% | 85.00% |
| test | 131/160 = 81.88% | 18/19 = 94.74% | 81.93% | 81.88% |

Test class correct:

| class | correct / total |
|---|---:|
| NSR | 31/40 |
| CHF | 37/40 |
| ARR | 28/40 |
| AFF | 35/40 |

### Core synthesis, wrapper excluded

Vivado 2020.2, part `xc7a100tcsg324-1`, top `snn_ecg_model_a_plus_core`.

| resource | used | available | utilization |
|---|---:|---:|---:|
| Slice LUTs | 5309 | 63400 | 8.37% |
| Slice Registers | 1250 | 126800 | 0.99% |
| BRAM Tile | 0 | 135 | 0.00% |
| DSP | 0 | 240 | 0.00% |

### Nexys A7 interactive demo

The board demo uses four stored 60-second ECG examples and buttons to select the class example.

- `BTNU`: NSR
- `BTNL`: ARR
- `BTND`: CHF
- `BTNR`: AFF
- `BTNC`: pseudo-random class example

The 7-segment display shows predicted class on the left and `CORR`/`ERR` on the right.

Board wrapper resource includes ECG ROMs, so BRAM usage is not the classifier core cost.

| wrapper resource | utilization |
|---|---:|
| Slice LUTs | 8.52% |
| Slice Registers | 1.09% |
| BRAM | 62.22% |
| DSP | 0.00% |

Timing was met with WNS 4.242 ns.

## Repository Layout

```text
SNN_ECG.srcs/             Vivado xpr가 직접 참조하는 원래 소스 트리
rtl/core/                 Model S synthesizable RTL core
rtl/board/                Nexys A7 board demo wrapper and demo mem files
sim/                      strict train/validation/test XSim testbenches
constraints/              Nexys A7 constraints
scripts/                  Vivado/XSim/report generation scripts
reports/                  final Model S metrics and synthesis reports
datasets/                 split manifests and compact demo samples
analog/                   AFE XModel, mixed-signal testbenches, and analysis scripts
docs/                     report-style documentation
bitstreams/               generated Nexys A7 demo bitstream
vivado_project/           portable unified Vivado xpr using relative source paths
```

`SNN_ECG.srcs/`는 Vivado 프로젝트를 바로 열기 위한 원본 레이아웃이고, `rtl/`과 `sim/`은 GitHub에서 소스만 빠르게 읽기 위한 정리 사본입니다. 두 경로의 RTL 내용은 같은 Model S 기준입니다.

## Open in Vivado

Open:

```text
vivado_project/SNN_ECG_ModelS_Unified/SNN_ECG_ModelS_Unified.xpr
```

Preferred top for board demo:

```text
nexys_a7_model_s_smoke_top
```

Core-only synthesis top:

```text
snn_ecg_model_a_plus_core
```

## Important Data Note

The full strict `.mem` dataset is not duplicated in this GitHub package to avoid storing large generated ECG segment files. The split manifests and final result CSVs are included under `datasets/record_wise_strict/`. The compact 4-class AFE/demo `.mem` examples are included under `datasets/afe_demo_samples/` and `rtl/board/`.

## Analog/Mixed-Signal Status

The analog teammate's AFE XModel and mixed-signal reports are included under `analog/` and `docs/analog_mixed_signal/`.

The AFE path is functionally compatible with the digital core, but the ADC output format must be converted:

```verilog
adc_signed = {~adc_unsigned[11], adc_unsigned[10:0]};
```

This is equivalent to offset-binary unsigned to signed two's-complement conversion centered at zero.

Mixed-signal verification found that standard AFE bandpass filtering can shift some ARR evidence toward AFF. This is a classifier robustness issue, not an AFE circuit failure. Final tapeout/SoC evaluation should include AFE-filtered ECG data in the train/validation process.

## Main Documentation

- [Model S Report](docs/model_s_report.md)
- [Architecture](docs/architecture.md)
- [Feature Neurons](docs/feature_neurons.md)
- [Dataset and Evaluation](docs/dataset_and_evaluation.md)
- [FPGA Verification](docs/fpga_verification.md)
- [Analog/Mixed-Signal Integration](docs/analog_mixed_signal.md)
- [Reproduction Notes](docs/reproduction.md)
- [Final Decisions](docs/final_decisions.md)
