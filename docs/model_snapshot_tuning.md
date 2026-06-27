# Model Snapshot C24 Tuning

## 목적

튜닝 목표는 AFE+ADC 기반 60초 snapshot dataset에서 Model Snapshot의 feature threshold, class weight, gate/boost 조합을 record-wise train/validation 기준으로 선택하는 것이다. Test set은 최종 후보가 선택된 뒤 1회 평가에만 사용했다.

## Split 원칙

- split 기준은 segment ID가 아니라 record ID이다.
- 같은 record에서 나온 snapshot이 train/validation/test에 동시에 들어가면 안 된다.
- train/validation은 후보 생성 및 선택에 사용한다.
- test는 최종 후보 C24 확정 뒤 최종 평가에만 사용한다.

## 후보 탐색 범위

C01~C32 후보는 feature 제거 실험이 아니라, 최종 Model Snapshot feature set을 유지한 상태에서 threshold/window/bank/gate/boost를 바꾼 후보이다.

| 후보 축 | 탐색 내용 |
|---|---|
| Adaptive QRS LIF | AFE+ADC stream에 맞춘 event threshold calibration |
| pNN/ECP timing | pNN window half, ectopic RR timing |
| RAM bank | amplitude bank base/step |
| DSCR | slope threshold |
| QRS MAF | width/complexity/energy threshold |
| RBBB QRS Delay Bank | low-slope, width, terminal, repeat, boost |
| EERG | gate threshold, ARR rescue boost |
| readout | class weight, class boost, base scale, count scale, regularization |

## 후보 선택 기준

후보 선택 우선순위는 다음과 같다.

1. validation macro-F1 최대화
2. validation balanced accuracy 최대화
3. validation ARR recall 유지 또는 개선
4. validation record accuracy 유지 또는 개선
5. NSR/CHF/AFF recall이 과도하게 무너지지 않을 것

이 기준 때문에 test 성능이 아닌 validation 성능으로 C24를 선택했다.

## Validation Ranking

| rank | candidate | val acc | val macro-F1 | val balanced | val record | NSR | CHF | ARR | AFF |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | C24 | 91.25% | 91.18% | 91.34% | 100.00% | 93.75% | 87.50% | 94.44% | 89.66% |
| 2 | C09 | 90.42% | 90.29% | 90.35% | 100.00% | 92.19% | 89.06% | 87.04% | 93.10% |
| 3 | C07 | 90.00% | 89.93% | 89.99% | 100.00% | 90.62% | 89.06% | 88.89% | 91.38% |
| 4 | C20 | 89.58% | 89.54% | 89.71% | 95.24% | 92.19% | 82.81% | 90.74% | 93.10% |
| 5 | C16 | 88.75% | 88.62% | 88.89% | 100.00% | 93.75% | 79.69% | 90.74% | 91.38% |

## C24 최종 Parameter

| item | value |
|---|---|
| candidate | `c24` |
| QRS tag | `e5w8t16l0r280a1b1c2000tc100_c24` |
| note | strict RBBB with weaker boost |
| profile | compact |
| count scale | `10.0` |
| base scale | `25000.0` |
| L2 regularization | `1000.0` |
| class boost | NSR `1.1`, CHF `1.8`, ARR `1.8`, AFF `1.0` |
| RBBB low slope threshold | `5` |
| RBBB wide threshold | `120` |
| RBBB terminal threshold | `4` |
| RBBB repeat threshold | `5` |
| RBBB NSR inhibition | `100000` |
| RBBB ARR boost | `100000` |

## C24 선택 이유

C24는 validation 기준으로 segment accuracy, macro-F1, balanced accuracy가 모두 1위였고, validation record accuracy도 100%였다. 특히 validation ARR recall이 51/54 = 94.44%로 높으면서 NSR, CHF, AFF recall이 동시에 유지됐다.

RBBB QRS Delay Bank는 ARR이 NSR로 넘어가는 문제를 줄이기 위한 feature지만, boost를 과도하게 키우면 NSR을 ARR로 끌고 올 수 있다. C24는 RBBB 조건을 더 엄격하게 두고 boost를 100000으로 제한해 ARR rescue와 NSR 오염 사이의 trade-off를 맞춘 후보이다.

## Test 사용 원칙

C24는 train/validation 기준으로 선택한 뒤 test set에서 최종 1회 평가했다. Test 결과를 보고 C24 threshold, weight, boost, gate를 다시 수정하지 않았다.
