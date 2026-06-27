# SNN ECG Model Snapshot RTL Classifier

이 저장소는 ECG 신호를 1 kSPS, signed 12-bit `adc_data` stream으로 입력받아 60초 snapshot 단위로 NSR / CHF / ARR / AFF를 분류하는 SNN-inspired RTL classifier를 정리한 프로젝트이다.

최종 모델명은 **Model Snapshot**이다. 이 GitHub 문서는 최종 C24 선택 결과와 Model Snapshot 구조만 설명한다.

## Model Snapshot 정의

Model Snapshot은 전체 환자 record를 한 번에 진단하는 clinical patient-level classifier가 아니다. 입력 ECG stream을 60초 snapshot으로 고정해 해당 snapshot이 어느 class evidence를 가장 강하게 보이는지 판정하는 RTL 모델이다.

- 입력: AFE+ADC 이후 1 kSPS signed 12-bit `adc_data`
- 입력 길이: 60초 snapshot
- 출력 class: `NSR`, `CHF`, `ARR`, `AFF`
- 최종 출력: `pred_class`, class membrane, feature evidence/debug signal
- 구현 방식: spike event, counter, threshold, comparator, signed membrane accumulation
- 사용하지 않는 방식: floating point, DSP multiplier, STDP, backpropagation

## RTL 구조

```text
ECG adc_data stream
-> adaptive QRS LIF event detector
-> beat_spike
-> pNN125 / RDM / RAM / ECP / QRS MAF / RBBB / EERG feature spike generation

simultaneously:
ECG adc_data stream
-> DSCR slope/sign feature generation

then:
feature evidence spike
-> local class neuron membrane
-> 60s snapshot-level class membrane
-> 4-class WTA
-> pred_class
```

각 feature는 scalar 값을 직접 class score에 넣지 않는다. feature별 조건이 만족되면 spike 또는 gate evidence가 발생하고, 이 evidence가 NSR / CHF / ARR / AFF class neuron membrane에 fixed signed synaptic weight로 누적된다. 60초 snapshot 끝에서 4개 class membrane을 비교해 가장 큰 membrane을 가진 class가 WTA winner가 된다.

## 최종 Feature Block

Model Snapshot의 최종 feature block은 다음과 같다.

| feature | 역할 |
|---|---|
| Adaptive QRS LIF | AFE+ADC stream에 맞춘 beat_spike 검출 |
| pNN125 | RR interval regularity 기반 rhythm evidence |
| RDM | 연속 RR interval 차이 기반 rhythm variability evidence |
| DSCR | slope sign-change 기반 morphology complexity evidence |
| RAM | R-peak amplitude response evidence |
| ECP | ectopic compensatory pair timing evidence |
| QRS MAF | QRS morphology abnormal evidence |
| RBBB QRS Delay Bank | RBBB-like conduction delay proxy evidence |
| EERG | episodic ectopic rescue gate |
| 4-class WTA | class membrane 경쟁 readout |

## C24 최종 선택

C01-C32 후보는 전체 Model Snapshot feature set을 유지한 상태에서 feature threshold, window, bank, gate, boost, readout parameter를 바꾼 후보군이다. 후보 선택은 record-wise train/validation split만 사용했으며, test set은 C24 확정 후 최종 1회 평가에만 사용했다.

최종 선택 후보는 **C24**이다.

| item | value |
|---|---|
| QRS tag | `e5w8t16l0r280a1b1c2000tc100_c24` |
| profile | `compact` |
| count scale | `10.0` |
| base scale | `25000.0` |
| L2 | `1000.0` |
| class boost | NSR `1.1`, CHF `1.8`, ARR `1.8`, AFF `1.0` |
| RBBB low slope threshold | `5` |
| RBBB wide threshold | `120` |
| RBBB terminal threshold | `4` |
| RBBB repeat threshold | `5` |
| RBBB NSR inhibition | `100000` |
| RBBB ARR boost | `100000` |

## 최종 검증 결과

| split | segment accuracy | macro-F1 | balanced accuracy |
|---|---:|---:|---:|
| train | 434/480 = 90.42% | 90.28% | 90.22% |
| validation | 219/240 = 91.25% | 91.18% | 91.34% |
| test | 193/240 = 80.42% | 80.28% | 79.99% |

이 결과는 60초 snapshot 단위의 분류 성능이다. 장시간 환자 record에 대한 최종 판단은 아래의 Holter-style aggregation 단계에서 별도로 정의한다.

## 최종 지향점

기존 60-180초 variable-length segment를 직접 WTA로 분류하는 방식은 길이가 바뀔 때 class membrane 누적량과 abnormal evidence의 희석 정도가 함께 바뀌는 문제가 있었다. 특히 ARR처럼 정상처럼 보이는 구간과 abnormal beat가 섞여 있는 class는 어느 60-180초 구간을 잘랐는지에 따라 NSR처럼 보이거나 AFF처럼 보일 수 있다. 따라서 임의 길이 segment 하나를 최종 진단 단위로 보는 방식은 안정적인 patient-level 판단에 적합하지 않다.

최종 방향은 Holter monitor처럼 24-48시간 연속 ECG를 기록하는 방식에 맞춘다. Holter monitoring은 심전도를 하루 또는 이틀 동안 연속 기록해 짧은 ECG에서 놓칠 수 있는 rhythm abnormality를 확인하는 임상적 검사 흐름이다. 관련 설명은 [American Heart Association](https://www.heart.org/en/health-topics/arrhythmia/symptoms-diagnosis--monitoring-of-arrhythmia/holter-monitor), [Cleveland Clinic](https://my.clevelandclinic.org/health/diagnostics/21491-holter-monitor), [Mayo Clinic](https://www.mayoclinic.org/tests-procedures/holter-monitor/about/pac-20385039) 자료를 기준으로 했다.

따라서 Model Snapshot은 24-48시간 record를 하나의 거대한 segment로 넣는 모델이 아니라, 긴 ECG stream을 60초 snapshot으로 계속 분할해 각 snapshot의 class membrane과 feature evidence를 생성하는 front-end classifier로 사용한다. 이후 snapshot별 `pred_class`, class membrane pattern, abnormal evidence의 빈도와 지속성을 누적해 patient-level class를 결정하는 aggregation layer를 붙이는 것이 최종 시스템 방향이다.

궁극적인 목표는 ECG AFE/ADC와 저전력 RTL classifier를 결합해, 스마트워치나 wearable healthcare device에 들어갈 수 있는 neuromorphic SNN-inspired ECG 4-class classifier를 만드는 것이다. 이 목표를 위해 Model Snapshot은 floating point나 DSP multiplier 없이 counter, comparator, threshold, signed membrane accumulation 중심으로 구성한다.

## 문서

- [Model Snapshot 구조](docs/model_snapshot_architecture.md)
- [Feature neuron 설명](docs/model_snapshot_features.md)
- [C24 튜닝 및 선택 과정](docs/model_snapshot_tuning.md)
- [검증 데이터셋 및 최종 성능](docs/model_snapshot_validation.md)

## 저장소 구성

| path | 내용 |
|---|---|
| `rtl/` | 주요 RTL source |
| `SNN_ECG.srcs/` | Vivado source tree 형식 RTL/testbench |
| `sim/` | XSim testbench |
| `constraints/` | Nexys A7 constraint |
| `scripts/` | Vivado/XSim 실행 script |
| `datasets/` | strict split 증빙 및 demo data |
| `reports/` | 합성, FPGA smoke, Model Snapshot 관련 결과 |
| `docs/` | 최종 Model Snapshot 문서 |
| `bitstreams/` | FPGA demo bitstream |

## 해석 범위

Model Snapshot의 핵심 검증 단위는 60초 ECG snapshot이다. 전체 장시간 ECG에 대한 최종 class 판단은 snapshot 결과를 장시간 누적하는 별도 aggregation layer에서 다룬다.
