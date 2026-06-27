# Model Snapshot Dataset and Validation

## 1. Raw ECG to AFE+ADC Dataset Flow

1. 원본 데이터 입력  
   원본 ECG record에서 annotation 기준으로 60초 snapshot을 추출한다. 각 snapshot은 `record_id`, `segment_id`, `class_label`, `start_time`, `duration`으로 관리한다.

2. Snapshot label 검증  
   60초 snapshot이 해당 class의 rhythm/morphology 특성을 포함하는지 annotation 기반으로 검토한다. record label만 기계적으로 모든 segment label에 복사하지 않고, class 특징이 약하거나 ambiguous한 구간은 curation 과정에서 제외한다.

3. Raw ECG code 정리  
   원본 ECG sample은 digital preprocessing 단계에서 `.raw` 또는 `.mem` 형태의 sample stream으로 정리된다. 이후 AFE 입력으로 사용할 수 있도록 시간 순서가 보존된 waveform sequence로 변환한다.

4. AFE 입력 변환  
   raw ECG code는 analog simulation 또는 XModel-compatible pipeline에서 사용할 수 있는 PWL/stream 형태로 변환된다. 이때 ECG amplitude scale, baseline offset, sampling rate, interpolation 조건을 AFE 쪽 변환 규칙에 맞춘다.

5. AFE processing  
   AFE chain은 ECG front-end filtering과 gain stage를 거쳐 ADC 입력에 해당하는 신호를 만든다. 최종 GitHub 문서에서는 filter 세부 회로보다 Model Snapshot에 실제로 들어가는 ADC code stream을 기준 데이터로 본다.

6. ADC quantization  
   AFE output은 12-bit ADC code로 양자화된다. 팀 통합 데이터에서는 XModel-match output을 기준으로 하며, digital core 입력에서는 signed 12-bit `adc_data` stream으로 변환해 사용한다.

7. RTL 입력 dataset 생성  
   최종 dataset은 train/validation/test split별 `.mem` 또는 equivalent stream으로 저장된다. Model Snapshot은 이 signed 12-bit `adc_data`를 1 kSPS로 읽고, 앞단 Adaptive QRS LIF가 2초 calibration을 수행한 뒤 60초 snapshot classification을 진행한다.

이 pipeline의 목적은 raw ECG 자체가 아니라 실제 AFE+ADC를 거친 digital code stream에서 Model Snapshot이 동작하도록 검증하는 것이다. 따라서 최종 성능은 raw waveform classifier 성능이 아니라 AFE+ADC 이후 60초 snapshot classifier 성능으로 해석한다.

## 2. Record-Wise Split

| split | segments | records |
|---|---:|---:|
| train | 480 | 43 |
| validation | 240 | 21 |
| test | 240 | 21 |

Validation과 test split의 class별 segment 수는 NSR 64, CHF 64, ARR 54, AFF 58이다. Train split은 curation 이후 NSR 127, CHF 128, ARR 109, AFF 116으로 구성됐다.

Record-wise split은 데이터 누수를 막기 위한 원칙이다. 같은 record에서 나온 snapshot이 train/validation/test에 동시에 들어가면, 모델이 record 고유 패턴을 학습해 일반화 성능이 과대평가될 수 있다.

## 3. Validation Metric

1. 핵심 metric은 60초 snapshot 단위 segment accuracy이다.
2. Macro-F1은 class imbalance와 class별 난이도를 함께 보기 위해 사용한다.
3. Balanced accuracy는 class별 recall 평균으로, 특정 class에 편향된 모델을 걸러내기 위해 사용한다.
4. Segment confusion matrix는 어떤 class pair에서 혼동이 생기는지 확인하기 위해 출력한다.
5. Record-wise split은 데이터 구성 원칙이며, 장시간 record 최종 판정은 별도 aggregation layer에서 다룬다.

Model Snapshot은 60초 snapshot classifier이므로 현재 문서의 최종 성능 표는 segment metric 중심으로 정리한다. Patient-level 판단은 snapshot 결과를 장시간 누적하는 다음 단계의 system-level 문제로 분리한다.

## 4. Final C24 Result

| split | segment accuracy | macro-F1 | balanced accuracy |
|---|---:|---:|---:|
| train | 434/480 = 90.42% | 90.28% | 90.22% |
| validation | 219/240 = 91.25% | 91.18% | 91.34% |
| test | 193/240 = 80.42% | 80.28% | 79.99% |

## 5. Test Segment Confusion Matrix

| Actual \ Pred | NSR | CHF | ARR | AFF |
|---|---:|---:|---:|---:|
| NSR | 50 | 12 | 2 | 0 |
| CHF | 7 | 56 | 0 | 1 |
| ARR | 14 | 2 | 34 | 4 |
| AFF | 0 | 3 | 2 | 53 |

## 6. 해석

1. Model Snapshot C24는 60초 snapshot 기준 test accuracy 80.42%, macro-F1 80.28%를 달성했다.
2. 이 결과는 장시간 ECG 전체를 한 번에 넣어 환자 진단을 수행한 결과가 아니다.
3. 최종 patient-level 시스템에서는 24-48시간 ECG stream을 60초 snapshot으로 반복 분할한다.
4. 각 snapshot의 `pred_class`, class membrane, abnormal feature evidence를 장시간 aggregation layer에서 누적한다.
5. 이 구조는 Holter-style continuous ECG monitoring처럼 긴 기록 안에서 intermittent abnormality를 관찰하는 방향과 맞는다.
6. Wearable system에서는 이 snapshot classifier를 저전력 digital front-end로 사용하고, 장시간 누적 logic은 별도 readout layer로 구성한다.
7. 따라서 본 성능은 “AFE+ADC 기반 60초 ECG snapshot classifier”의 검증 결과로 해석한다.

Model Snapshot은 장시간 ECG record를 처리하기 위한 최종 front-end classifier이다. 다음 단계에서는 snapshot별 class membrane pattern과 abnormal evidence 지속성을 이용해 24-48시간 patient-level aggregation rule을 설계한다.
