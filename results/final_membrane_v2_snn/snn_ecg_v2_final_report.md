# SNN ECG V2 Final Membrane Report

## 모델 정의

최종 모델은 **SNN ECG V2**이다.

```text
SNN ECG V2
= Snapshot Model V2
+ Final Membrane Layer V2
```

전체 흐름:

```text
30분 signed 12-bit AFE+ADC ECG stream
-> timer neuron이 60000 sample마다 60초 boundary spike 생성
-> Snapshot Model V2가 60초 class/evidence spike 생성
-> Final Membrane Layer V2가 class neuron membrane에 흥분성/억제성 자극 누적
-> 30분 chunk_done WTA
-> NSR / CHF / ARR / AFF
```

## Final Membrane Layer V2 알고리즘

Final Membrane Layer V2는 30개의 60초 snapshot 결과를 class별 final neuron membrane에 누적한다.

기본 자극:

```text
pred_class == NSR -> NSR final neuron에 흥분성 자극
pred_class == CHF -> CHF final neuron에 흥분성 자극
pred_class == ARR -> ARR final neuron에 흥분성 자극
pred_class == AFF -> AFF final neuron에 흥분성 자극
```

이 기본 구조는 majority vote membrane에 해당한다.

추가로 snapshot WTA에서 패배한 subthreshold evidence를 잃지 않기 위해 보조 evidence neuron membrane을 누적한다.

```text
pNN mismatch evidence neuron
RDM irregularity evidence neuron
ectopic pair evidence neuron
QRS morphology evidence neuron
RBBB-like conduction evidence neuron
abnormal evidence neuron
```

이 evidence neuron들이 threshold를 넘으면 최종 class neuron에 흥분성 또는 억제성 자극을 넣는다.

확정 후보:

```text
candidate_id = margin_evidence_0038974
```

핵심 ARR rescue 자극:

```text
if 현재 우세 class가 AFF이고
   AFF 우세 margin이 작고
   ARR snapshot 발화가 최소 3회 이상이고
   RDM / pNN mismatch / ectopic / abnormal evidence가 충분하면:
       ARR final neuron에 흥분성 자극 +4
       AFF final neuron에 억제성 자극 -16
```

RTL 구현:

```verilog
calc_arr = calc_arr + 32'sd4;
calc_aff = calc_aff - 32'sd16;
```

이 구조는 comparator, counter, signed accumulator, WTA만 사용한다. Floating point, divider, DSP multiplier, SVC, XGBoost, dense classifier는 사용하지 않는다.

## XSim 검증

Python 등가모델과 RTL/XSim 결과가 `pred_class` 및 `final_mem[4]` 기준으로 일치한다.

| Split | Python | XSim | Pred mismatch | Mem mismatch |
|---|---:|---:|---:|---:|
| train | 62/68 = 91.18% | 62/68 = 91.18% | 0 | 0 |
| validation | 31/32 = 96.88% | 31/32 = 96.88% | 0 | 0 |
| test | 32/36 = 88.89% | 32/36 = 88.89% | 0 | 0 |

Test confusion matrix:

| True \ Pred | NSR | CHF | ARR | AFF |
|---|---:|---:|---:|---:|
| NSR | 9 | 0 | 0 | 0 |
| CHF | 0 | 9 | 0 | 0 |
| ARR | 2 | 1 | 6 | 0 |
| AFF | 0 | 0 | 1 | 8 |

Test class별 성능:

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| NSR | 81.82% | 100.00% | 90.00% |
| CHF | 90.00% | 100.00% | 94.74% |
| ARR | 85.71% | 66.67% | 75.00% |
| AFF | 100.00% | 88.89% | 94.12% |

Test macro-F1은 88.46%, balanced accuracy는 88.89%이다.

## Vivado 구현 결과

Target:

```text
Nexys A7 / Artix-7 xc7a100tcsg324-1
```

Bitstream:

```text
results/final_membrane_v2_snn/vivado_snn_ecg_v2/bitstream/snn_ecg_v2_nexys_a7_top.bit
```

자원 사용량:

| Resource | Used |
|---|---:|
| LUT | 21002 |
| FF | 2803 |
| BRAM | 0 |
| DSP | 0 |

Vivado power estimate:

| Power | W |
|---|---:|
| Total on-chip | 0.101 |
| Dynamic | 0.004 |
| Static | 0.097 |

Timing은 routed implementation 기준으로 met 되었다.

## 해석상 주의사항

- 본 모델은 SNN-inspired membrane readout이다. 완전한 생물학적 SNN이나 STDP 학습 구조로 표현하지 않는다.
- 30분 dataset 정확도는 XSim dataset testbench 기준이다.
- Bitstream wrapper는 FPGA implementation/resource/timing 확인용이다.
- Power는 Vivado 추정값이며 실제 보드 측정값은 아니다.
- ARR recall은 test 기준 6/9로 남은 병목이다.
