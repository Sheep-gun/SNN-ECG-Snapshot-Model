# Model Snapshot RTL Architecture

## 목적

Model Snapshot은 AFE+ADC 이후의 ECG stream을 60초 단위로 입력받아 NSR / CHF / ARR / AFF 중 하나를 선택하는 SNN-inspired RTL classifier이다. 이 모델은 장시간 환자 record 전체를 직접 진단하는 구조가 아니라, 60초 snapshot 단위의 class evidence를 안정적으로 산출하는 것을 목표로 한다.

## 왜 60초 Snapshot 구조인가

기존 60-180초 variable-length 판단 모델은 segment 길이가 바뀔 때 feature evidence 누적량과 abnormal event 희석 정도가 함께 바뀌었다. Rate 기반 feature를 도입하더라도, class membrane readout 단계에서 긴 segment의 정상 구간이 abnormal evidence를 희석하거나 특정 class evidence를 과도하게 누적하는 문제가 남았다.

또한 record label이 모든 임의 segment label과 항상 같은 것은 아니다. ARR record 안에도 정상처럼 보이는 60초 구간이 있을 수 있고, AFF/ARR처럼 rhythm abnormality가 시간에 따라 달라지는 class는 짧은 구간 하나만으로 전체 환자 상태를 단정하기 어렵다. 따라서 최종 구조는 임의 길이 segment 하나를 최종 진단 단위로 보지 않고, 고정 길이 60초 snapshot을 반복 평가하는 방향으로 정리했다.

이 방향은 Holter-style ECG monitoring과 맞닿아 있다. Holter monitor는 보통 24-48시간 동안 ECG를 연속 기록해 짧은 ECG에서 포착되지 않는 rhythm abnormality를 확인하는 검사 흐름이다. Model Snapshot은 이 긴 ECG stream을 60초 단위로 읽어 class evidence를 만드는 저전력 digital front-end classifier 역할을 맡는다.

## Top-Level Signal Flow

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

QRS 기반 feature는 `beat_spike`를 기준으로 RR interval, R-peak amplitude, QRS morphology, ectopic timing evidence를 만든다. DSCR은 QRS 이후에만 동작하는 후처리 feature가 아니라, raw `adc_data` stream에서 병렬로 slope sign-change evidence를 생성한다.

## 입력과 출력

| 항목 | 정의 |
|---|---|
| sample rate | 1 kSPS |
| input data | signed 12-bit `adc_data` |
| snapshot length | 60 seconds |
| classes | NSR, CHF, ARR, AFF |
| primary output | `pred_class` |
| debug output | class membrane, feature evidence count, feature spike |

입력은 AFE+ADC를 통과한 digital ECG code stream으로 본다. Model Snapshot은 이 stream의 절대 count를 그대로 class score로 쓰지 않고, ECG event가 발생하는 순간마다 class neuron membrane에 fixed signed evidence를 누적한다.

## SNN-Inspired Membrane 구조

각 feature block은 다음 중 하나를 출력한다.

- beat-level spike
- window-level spike
- segment-level gate
- feature evidence count/debug signal

feature evidence는 class neuron membrane에 signed weight로 누적된다.

```text
if feature_evidence_spike:
    class_mem[NSR] += W_FEATURE_TO_NSR
    class_mem[CHF] += W_FEATURE_TO_CHF
    class_mem[ARR] += W_FEATURE_TO_ARR
    class_mem[AFF] += W_FEATURE_TO_AFF
```

이 구조는 scalar feature를 floating-point classifier에 넣는 방식이 아니다. RTL 내부에서는 정수 counter, comparator, add/subtract, shift, threshold bank만 사용한다.

## 60초 Snapshot WTA

60초 snapshot이 끝나면 4개 class membrane을 비교한다.

```text
pred_class = argmax(
    class_mem[NSR],
    class_mem[CHF],
    class_mem[ARR],
    class_mem[AFF]
)
```

이 WTA는 SNN class neuron들의 경쟁 결과를 읽어내는 readout이다. STDP, backpropagation, floating point 학습은 사용하지 않는다. weight와 threshold는 train/validation 기반 탐색으로 미리 고정된다.

## 장시간 Record 처리 방향

최종 patient-level 시스템은 24-48시간 ECG record를 한 번에 하나의 거대한 segment로 넣지 않는다. 대신 60초 snapshot을 순차적으로 입력하고, 각 snapshot의 `pred_class`, class membrane, abnormal feature evidence를 장시간 aggregation layer에 전달한다.

```text
24-48h ECG stream
-> repeated 60s Model Snapshot inference
-> snapshot-level class membrane pattern
-> long-term aggregation layer
-> patient-level class decision
```

이 방식은 긴 record 안에서 일시적으로 나타나는 abnormal event를 보존하면서도, 모든 ECG 구간을 같은 60초 기준으로 평가한다. 향후 aggregation layer는 class vote, membrane 평균, abnormal-priority rule, event persistence rule 등을 비교해 설계한다.

## Hardware Implementation Notes

Model Snapshot은 FPGA-friendly RTL 구조를 목표로 한다.

- multiplier/DSP 기반 연산을 피한다.
- floating point를 사용하지 않는다.
- divider 대신 threshold comparison, shift, add/subtract를 사용한다.
- feature 판단은 counter, comparator, latch, small register로 구성한다.
- class readout은 signed integer membrane comparison으로 수행한다.

이 구조의 핵심은 ECG feature를 “숫자 하나”로 계산하는 것이 아니라, feature evidence spike가 class membrane에 반복적으로 들어가면서 최종 class 경쟁을 형성한다는 점이다.

궁극적인 시스템 지향점은 wearable ECG device에 들어갈 수 있는 저전력 neuromorphic SNN-inspired classifier이다. 따라서 Model Snapshot은 Galaxy Watch와 같은 wearable platform을 염두에 두고, 지속 monitoring에 적합한 event-driven low-power RTL 구조를 유지한다.
