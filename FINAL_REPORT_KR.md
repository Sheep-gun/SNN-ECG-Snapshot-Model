# SNN ECG V2 최종 정리 보고서

## 1. 연구 목적

본 프로젝트의 목적은 ECG 신호를 저전력 디지털 회로에서 처리할 수 있는 **SNN-inspired 4-class ECG classifier**로 구현하는 것이다.

분류 대상은 다음 네 가지이다.

| Class | 의미 |
|---|---|
| NSR | Normal Sinus Rhythm |
| CHF | Congestive Heart Failure |
| ARR | Arrhythmia |
| AFF | Atrial Fibrillation/Flutter 계열 |

초기 목표는 Holter monitor처럼 장시간 ECG를 관찰하면서 특정 순간의 짧은 ECG만 보고 환자를 단정하지 않고, 시간축으로 반복되는 rhythm/morphology evidence를 누적해 최종 class를 판단하는 것이었다. Holter monitor는 일반적으로 24-48시간 동안 심장 리듬을 기록하여 진료실 밖에서 발생하는 비정상 리듬을 포착하는 장치로 설명된다. 참고 문헌으로는 American Heart Association의 [Holter Monitor 설명](https://www.heart.org/en/health-topics/arrhythmia/symptoms-diagnosis--monitoring-of-arrhythmia/holter-monitor), Cleveland Clinic의 [24-48시간 Holter monitor 설명](https://my.clevelandclinic.org/health/diagnostics/21491-holter-monitor), NIH/NCBI StatPearls의 [Ambulatory ECG Monitoring](https://www.ncbi.nlm.nih.gov/books/NBK597374/)를 참조했다.

다만 현재 사용 가능한 ARR full-record 데이터 길이가 NSR처럼 24시간 이상으로 길지 않고, 일부 ARR record는 약 30분 수준으로 제한된다. 따라서 본 프로젝트의 최종 RTL 모델은 **30분 ECG chunk를 처리하는 SNN ECG V2**로 정의했다.

## 2. 최종 모델 정의

최종 모델명은 **SNN ECG V2**이다.

```text
SNN ECG V2
= Snapshot Model V2
+ Final Membrane Layer V2
```

전체 처리 흐름:

```text
30분 AFE+ADC signed 12-bit ECG stream
-> timer neuron이 60000 sample마다 60초 boundary spike 생성
-> Snapshot Model V2가 60초 구간별 class/evidence spike 생성
-> Final Membrane Layer V2가 30개 snapshot evidence를 시간축으로 누적
-> 30분 chunk_done 시점에 WTA
-> NSR / CHF / ARR / AFF 최종 판정
```

핵심은 외부에서 60초 파일을 따로 넣는 구조가 아니라, 30분 ADC stream을 RTL top에 직접 넣고 내부 timer neuron이 60초 snapshot boundary를 만든다는 점이다.

## 3. 입력 데이터와 AFE+ADC 조건

모델 입력은 raw ECG가 아니라 AFE+ADC가 완료된 signed 12-bit digital stream이다.

AFE+ADC 변환 흐름:

```text
ECG waveform
-> 1 kSPS resampling
-> AFE-equivalent filtering/gain
-> ADC quantization
-> signed 12-bit .mem
-> RTL digital core
```

주요 조건:

- sample rate: 1 kSPS
- ADC format: signed 12-bit
- Verilog `$readmemh` 호환 `.mem`
- 60초 snapshot: 60000 samples
- 30분 chunk: 1800000 samples

Snapshot V2 검증 데이터셋:

```text
60s_afe_datasets/afe_output_xmodelmatch_curated_v2_128_64_64_balanced
```

30분 SNN ECG V2 검증 데이터셋:

```text
fullrec_afe_30min_annotation_valid_balanced
```

30분 데이터셋은 annotation-valid chunk를 기준으로 구성했고, record-wise split 기준으로 train/validation/test leakage가 없도록 관리했다.

## 4. Snapshot Model V2

Snapshot Model V2는 60초 ECG window 하나를 NSR / CHF / ARR / AFF 중 하나로 분류하는 고정 snapshot classifier이다.

구조:

```text
AFE+ADC samples
-> event/QRS/rhythm/morphology feature spike
-> feature별 fixed signed synaptic weight
-> class membrane accumulation
-> 60초 segment_done
-> 4-class WTA
-> pred_class
```

이 구조는 Python classifier를 RTL에 matrix multiplication 형태로 복사한 것이 아니다. C24 readout coefficient를 feature spike별 signed synaptic weight로 fold하여, feature spike가 class neuron membrane에 흥분성 또는 억제성 자극을 주는 구조로 구현했다.

### 4.1 주요 feature neuron

| Feature group | 역할 |
|---|---|
| PNN | RR/rhythm pattern match/mismatch evidence |
| RDM | rhythm variability level/count evidence |
| DSCR | morphology slope/sign-flip evidence |
| RAM | peak/amplitude code/count evidence |
| ECP | ectopic pair evidence |
| QRS MAF | QRS morphology/width/energy evidence |
| RBBB | conduction delay / RBBB-like evidence |

Snapshot V2에서는 기존 C24에서 존재하던 EERG direct class-membrane contribution을 제거했다. EERG direct path를 꺼도 test 성능은 유지되고 validation window 하나가 개선되었기 때문에, 불필요한 자극 경로를 줄인 구조를 V2로 확정했다.

### 4.2 Snapshot V2 XSim 성능

| Split | Correct / Total | Accuracy | Macro-F1 | Balanced Accuracy |
|---|---:|---:|---:|---:|
| train | 466 / 512 | 91.02% | 90.96% | 91.02% |
| validation | 231 / 256 | 90.23% | 90.29% | 90.23% |
| test | 205 / 256 | 80.08% | 80.06% | 80.08% |

Test confusion matrix:

| True \ Pred | NSR | CHF | ARR | AFF |
|---|---:|---:|---:|---:|
| NSR | 50 | 12 | 2 | 0 |
| CHF | 7 | 56 | 0 | 1 |
| ARR | 15 | 3 | 42 | 4 |
| AFF | 0 | 4 | 3 | 57 |

Test class별 precision / recall / F1:

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| NSR | 69.44% | 78.12% | 73.53% |
| CHF | 74.67% | 87.50% | 80.58% |
| ARR | 89.36% | 65.62% | 75.68% |
| AFF | 91.94% | 89.06% | 90.48% |

Snapshot 단독으로는 test 80.08%이며, ARR 일부가 NSR/CHF 쪽으로 이동하는 것이 가장 큰 병목이다.

## 5. Final Membrane Layer V2

Final Membrane Layer V2는 30분 동안 30개의 60초 snapshot 결과를 받아 최종 30분 class를 고르는 SNN-inspired readout이다.

### 5.1 직관적 설명

Snapshot Model V2는 60초마다 다음과 같은 class spike를 낸다.

```text
이번 60초는 NSR
이번 60초는 ARR
이번 60초는 AFF
...
```

Final Membrane Layer V2는 이를 30분 동안 모아 class별 membrane에 누적한다.

```text
NSR final neuron membrane
CHF final neuron membrane
ARR final neuron membrane
AFF final neuron membrane
```

가장 기본적인 자극은 snapshot `pred_class` spike이다.

```text
pred_class == NSR -> NSR final neuron에 자극
pred_class == CHF -> CHF final neuron에 자극
pred_class == ARR -> ARR final neuron에 자극
pred_class == AFF -> AFF final neuron에 자극
```

여기까지는 majority vote와 비슷하다. 하지만 단순 majority vote는 snapshot WTA에서 패배한 subthreshold evidence를 버린다. 예를 들어 60초 snapshot의 최종 class는 NSR이더라도, 내부적으로 ARR-like pNN mismatch, ectopic pair, RDM irregularity, QRS morphology evidence가 조금씩 반복될 수 있다.

그래서 Final Membrane Layer V2는 보조 evidence neuron membrane을 같이 누적한다.

```text
pNN mismatch evidence neuron
RDM irregularity evidence neuron
ectopic-pair evidence neuron
QRS morphology evidence neuron
RBBB-like conduction evidence neuron
abnormal evidence neuron
```

이 evidence neuron들이 30분 동안 일정 threshold 이상 활성화되면, 최종 class neuron에 흥분성 또는 억제성 자극을 넣는다.

예:

```text
ARR evidence가 반복됨
-> ARR final neuron에 흥분성 자극
-> AFF 또는 NSR final neuron에 억제성 자극
```

RTL에서는 이 표현이 signed add/subtract로 구현된다.

```verilog
final_mem_arr = final_mem_arr + 4;   // ARR 흥분성 자극
final_mem_aff = final_mem_aff - 16;  // AFF 억제성 자극
```

### 5.2 확정 후보

Final Membrane Layer V2의 확정 후보는 다음이다.

```text
candidate_id: margin_evidence_0038974
```

핵심 ARR rescue neuron:

```text
if 현재 우세 class가 AFF이고
   AFF 우세 margin이 작고
   ARR snapshot 발화가 최소 3회 이상이고
   RDM irregularity evidence가 충분하고
   pNN mismatch evidence가 충분하고
   ectopic pair evidence가 충분하고
   abnormal evidence가 충분하면:
       ARR final neuron에 흥분성 자극 +4
       AFF final neuron에 억제성 자극 -16
```

이 조건은 comparator network와 signed accumulator로 구현된다. DSP multiplier, floating point, divider, dense ML classifier는 사용하지 않는다.

### 5.3 Final Membrane V2의 뉴로모픽 해석

Final Membrane Layer V2는 완전한 생물학적 SNN이라고 주장하지 않는다. 더 정확한 표현은 다음이다.

```text
timer-event-driven SNN-inspired final membrane readout
```

구조적으로는 다음 특성을 가진다.

- timer neuron: 60초마다 snapshot boundary spike 발생
- snapshot class spike: 60초 구간의 local class 발화
- evidence neuron: 병적 rhythm/morphology evidence를 30분 동안 누적
- class neuron membrane: NSR/CHF/ARR/AFF 최종 neuron의 membrane potential
- 흥분성 자극: 해당 class membrane을 상승시키는 signed positive update
- 억제성 자극: competing class membrane을 낮추는 signed negative update
- WTA: 30분 종료 시 가장 큰 membrane potential을 가진 class를 최종 출력

## 6. SNN ECG V2 XSim 검증

30분 chunk-level XSim에서 Python 등가모델과 RTL 결과를 비교했다.

비교 기준:

- final `pred_class`
- `final_mem_nsr`
- `final_mem_chf`
- `final_mem_arr`
- `final_mem_aff`

결과:

| Split | Python | XSim | Pred mismatch | Mem mismatch |
|---|---:|---:|---:|---:|
| train | 62 / 68 = 91.18% | 62 / 68 = 91.18% | 0 | 0 |
| validation | 31 / 32 = 96.88% | 31 / 32 = 96.88% | 0 | 0 |
| test | 32 / 36 = 88.89% | 32 / 36 = 88.89% | 0 | 0 |

Test confusion matrix:

| True \ Pred | NSR | CHF | ARR | AFF |
|---|---:|---:|---:|---:|
| NSR | 9 | 0 | 0 | 0 |
| CHF | 0 | 9 | 0 | 0 |
| ARR | 2 | 1 | 6 | 0 |
| AFF | 0 | 0 | 1 | 8 |

Test class별 precision / recall / F1:

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| NSR | 81.82% | 100.00% | 90.00% |
| CHF | 90.00% | 100.00% | 94.74% |
| ARR | 85.71% | 66.67% | 75.00% |
| AFF | 100.00% | 88.89% | 94.12% |

요약:

- test accuracy: 32 / 36 = 88.89%
- test macro-F1: 88.46%
- test balanced accuracy: 88.89%
- Python vs XSim pred mismatch: 0
- Python vs XSim final_mem mismatch: 0

ARR recall은 6/9로 남은 병목이다. 그러나 NSR, CHF는 test 기준 9/9, AFF는 8/9로 안정적이다.

## 7. Vivado 합성/구현 결과

대상:

```text
Nexys A7 / Artix-7 xc7a100tcsg324-1
```

Top:

```text
rtl/board/snn_ecg_v2_nexys_a7_top.v
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

해석:

- DSP 0개: multiplier 기반 dense classifier가 아님을 보여준다.
- BRAM 0개: final readout과 feature/counter path가 register/LUT 중심임을 보여준다.
- Dynamic power 0.004 W: datapath switching 추정 전력은 낮지만, FPGA 특성상 static power가 대부분이다.
- Power 값은 Vivado 추정값이며 실제 보드 전력 측정값은 아니다.

## 8. 주요 파일

RTL:

```text
rtl/core/class_score_neurons.v
rtl/core/snn_ecg_3feat_top.v
rtl/final_membrane_layer.v
rtl/snn_ecg_30min_final_top.v
rtl/board/snn_ecg_v2_nexys_a7_top.v
```

Simulation:

```text
sim/tb_snapshot_c24_dataset.v
sim/tb_snn_ecg_30min_chunk_dataset.v
```

Scripts:

```text
scripts/run_snapshot_v2_xsim.py
scripts/run_final_membrane_v2_xsim.py
scripts/build_snn_ecg_v2_bitstream.py
```

Results:

```text
results/snapshot_c24_v2_search/xsim_snapshot_v2_summary.json
results/snapshot_c24_v2_search/snapshot_v2_rtl_xsim_report.md
results/final_membrane_v2_snn/xsim_snn_ecg_v2_summary.json
results/final_membrane_v2_snn/snn_ecg_v2_final_report.md
results/final_membrane_v2_snn/vivado_snn_ecg_v2/snn_ecg_v2_vivado_summary.json
```

## 9. V1에서 V2로의 변경 요약

기존 V1 계열에서는 60초 Snapshot C24 성능과 30분 final layer 후보가 분리되어 있었고, 일부 record-level aggregation 성격의 후보나 SVC/선형 classifier 계열 후보가 섞여 있었다.

V2에서는 다음 기준으로 정리했다.

1. Snapshot은 `Snapshot Model V2`로 고정
2. EERG direct class-membrane contribution 제거
3. 30분 final layer는 `Final Membrane Layer V2`만 사용
4. record-level aggregation 후보 폐기
5. SVC/XGBoost/dense classifier 후보 폐기
6. 30분 stream top 내부에 timer neuron 포함
7. 60초 snapshot boundary를 내부 event로 생성
8. final readout은 흥분성/억제성 자극을 class membrane에 누적하는 구조로 표현
9. Python 등가모델과 XSim RTL의 final pred/mem 일치 확인
10. Vivado bitstream/resource/power report 생성

## 10. 결론

SNN ECG V2는 30분 ECG stream을 60초 snapshot event들의 시간축 발화 패턴으로 해석하고, class neuron membrane에 흥분성/억제성 자극을 누적하여 최종 class를 판정하는 SNN-inspired hierarchical ECG classifier이다.

최종 성능은 다음과 같다.

```text
Snapshot Model V2 60초 test accuracy: 205/256 = 80.08%
SNN ECG V2 30분 test accuracy: 32/36 = 88.89%
SNN ECG V2 30분 test macro-F1: 88.46%
SNN ECG V2 30분 XSim mismatch: pred 0, mem 0
Vivado DSP usage: 0
Vivado BRAM usage: 0
```

보고서에서 사용할 핵심 문장:

```text
본 시스템은 60초 ECG snapshot을 독립적으로 진단하는 단일 판정기가 아니라,
30분 ECG stream에서 반복적으로 생성되는 snapshot-level class/evidence spike를
patient/chunk-level final class neuron membrane에 누적하고,
흥분성/억제성 자극을 통해 최종 WTA 판정을 수행하는
SNN-inspired hierarchical ECG classifier이다.
```
