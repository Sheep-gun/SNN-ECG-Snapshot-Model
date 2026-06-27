# Model Snapshot Validation

## Dataset

검증 대상은 AFE+ADC output 기반 60초 ECG snapshot dataset이다. Split은 record-wise로 고정했으며, 같은 record에서 나온 snapshot이 train/validation/test에 동시에 들어가지 않도록 구성했다.

| split | segments | records |
|---|---:|---:|
| train | 480 | 43 |
| validation | 240 | 21 |
| test | 240 | 21 |

Validation과 test split의 class별 segment 수는 NSR 64, CHF 64, ARR 54, AFF 58이다. Train split은 curation 이후 NSR 127, CHF 128, ARR 109, AFF 116으로 구성됐다.

## Metric

주요 metric은 60초 snapshot 단위 segment accuracy이다. Record accuracy는 같은 record에 속한 snapshot 결과를 묶어 확인한 보조 지표이다.

함께 보고한 지표는 다음과 같다.

- segment accuracy
- record accuracy
- class별 recall
- macro-F1
- balanced accuracy
- segment confusion matrix
- record confusion matrix

## Final C24 Result

| split | segment accuracy | record accuracy | macro-F1 | balanced accuracy |
|---|---:|---:|---:|---:|
| train | 434/480 = 90.42% | 41/43 = 95.35% | 90.28% | 90.22% |
| validation | 219/240 = 91.25% | 21/21 = 100.00% | 91.18% | 91.34% |
| test | 193/240 = 80.42% | 16/21 = 76.19% | 80.28% | 79.99% |

## Class별 Recall

### Train

| class | correct / total | recall |
|---|---:|---:|
| NSR | 116/127 | 91.34% |
| CHF | 117/128 | 91.41% |
| ARR | 88/109 | 80.73% |
| AFF | 113/116 | 97.41% |

### Validation

| class | correct / total | recall |
|---|---:|---:|
| NSR | 60/64 | 93.75% |
| CHF | 56/64 | 87.50% |
| ARR | 51/54 | 94.44% |
| AFF | 52/58 | 89.66% |

### Test

| class | correct / total | recall |
|---|---:|---:|
| NSR | 50/64 | 78.13% |
| CHF | 56/64 | 87.50% |
| ARR | 34/54 | 62.96% |
| AFF | 53/58 | 91.38% |

## Test Segment Confusion Matrix

| Actual \ Pred | NSR | CHF | ARR | AFF |
|---|---:|---:|---:|---:|
| NSR | 50 | 12 | 2 | 0 |
| CHF | 7 | 56 | 0 | 1 |
| ARR | 14 | 2 | 34 | 4 |
| AFF | 0 | 3 | 2 | 53 |

## Test Record Confusion Matrix

| Actual \ Pred | NSR | CHF | ARR | AFF |
|---|---:|---:|---:|---:|
| NSR | 3 | 1 | 0 | 0 |
| CHF | 0 | 3 | 0 | 0 |
| ARR | 3 | 0 | 5 | 1 |
| AFF | 0 | 0 | 0 | 5 |

## 해석

Model Snapshot C24는 60초 snapshot 기준 test accuracy 80.42%, macro-F1 80.28%를 달성했다. CHF와 AFF recall은 각각 87.50%, 91.38%로 안정적이며, ARR recall은 62.96%로 여전히 가장 어려운 class이다.

따라서 최종 해석은 “60초 AFE+ADC snapshot classifier”이다. 장시간 record 전체에 대한 patient-level 판정은 60초 snapshot 결과를 어떻게 aggregation할지 별도 정책을 둔 뒤 해석해야 한다.
