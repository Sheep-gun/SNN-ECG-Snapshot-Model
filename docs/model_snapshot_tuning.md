# Model Snapshot Candidate Search and C24 Selection

## 1. 튜닝 목적

Model Snapshot의 튜닝 목적은 AFE+ADC 기반 60초 snapshot dataset에 대해 feature threshold, class weight, gate/boost parameter를 함께 조정해 가장 안정적인 4-class readout을 선택하는 것이다. 튜닝은 record-wise train/validation split에서 수행하고, test split은 최종 후보 확정 이후 1회 평가에만 사용한다.

## 2. 탐색 원칙

1. 동일 record에서 나온 snapshot이 train/validation/test에 동시에 들어가지 않도록 record-wise split을 고정한다.
2. candidate C01-C32는 feature 제거 실험이 아니라, 최종 Model Snapshot feature set을 유지한 상태에서 threshold/window/bank/gate/boost를 바꾼 후보이다.
3. 각 후보는 RTL/XSim 또는 동일 dump 기반 readout search로 train/validation 성능을 계산한다.
4. class weight, class boost, feature boost, RBBB/EERG boost, count scale, base scale, regularization을 함께 탐색한다.
5. 최종 후보는 validation macro-F1, balanced accuracy, segment accuracy, class 균형을 기준으로 선택한다.
6. test 결과를 보고 threshold나 weight를 다시 수정하지 않는다.
7. 최종 선택된 C24만 test split에서 최종 평가한다.

이 절차의 핵심은 test set을 candidate selection에 쓰지 않는 것이다. 따라서 C24는 test에 맞춘 후보가 아니라 validation에서 가장 좋은 trade-off를 보인 후보이다.

## 3. Candidate Set

| candidate | 설명 |
|---|---|
| baseline | 기존 모델 파라미터 기준 후보 |
| C01 | pNN window 100 ms + ECP 100 ms. 이전 combo1 계열 기준 후보 |
| C02 | pNN 90 ms + ECP 80 ms. rhythm timing을 더 엄격하게 잡는 후보 |
| C03 | pNN 110 ms + ECP 100 ms. baseline보다 약간 좁은 pNN 후보 |
| C04 | pNN 140 ms + ECP 140 ms. rhythm timing을 느슨하게 잡는 후보 |
| C05 | pNN 150 ms + ECP 100 ms. pNN은 넓게, ECP는 엄격하게 둔 후보 |
| C06 | pNN/ECP 100 ms + DSCR 민감화 + RAM low/mid bank 조정 |
| C07 | pNN/ECP 100 ms + DSCR 엄격화 + RAM step 조밀화 |
| C08 | pNN 150 ms + DSCR 민감화 + RAM 조정 |
| C09 | pNN 90 ms + ECP 80 ms + RAM 조밀화 |
| C10 | RAM base/step을 낮춰 low-amplitude 쪽을 더 세밀하게 보는 후보 |
| C11 | RAM mid-low 영역을 더 조밀하게 보는 후보 |
| C12 | RAM 전체를 baseline보다 조밀하게 보는 후보 |
| C13 | RAM bank를 높은 amplitude 쪽으로 이동한 후보 |
| C14 | DSCR slope threshold 5. morphology sign-change를 더 민감하게 잡는 후보 |
| C15 | DSCR slope threshold 6. DSCR을 약간 민감하게 잡는 후보 |
| C16 | DSCR slope threshold 10. DSCR을 더 엄격하게 잡는 후보 |
| C17 | QRS MAF를 민감하게 설정한 후보 |
| C18 | QRS MAF를 중간 정도로 민감하게 설정한 후보 |
| C19 | QRS MAF를 엄격하게 설정한 후보 |
| C20 | pNN/ECP rhythm 후보 + QRS MAF 중간 민감도 조합 |
| C21 | RBBB QRS delay를 매우 민감하게 잡는 후보 |
| C22 | RBBB QRS delay를 민감하게 잡되 C21보다 약간 보수적인 후보 |
| C23 | RBBB 조건은 baseline 근처, ARR boost/NSR inhibition을 더 강하게 준 후보 |
| C24 | RBBB 조건은 엄격하게, boost는 약하게 둔 후보 |
| C25 | pNN/ECP rhythm 후보 + 민감한 RBBB delay 조합 |
| C26 | EERG를 더 잘 뜨게 만든 permissive 후보 |
| C27 | EERG를 더 엄격하게 만든 후보 |
| C28 | EERG는 permissive하게 두고 ARR boost를 더 강하게 준 후보 |
| C29 | pNN/ECP + RBBB delay + EERG를 함께 조합한 후보 |
| C30 | QRS event front-end를 더 민감하게 만든 adaptive QRS 후보 |
| C31 | QRS event front-end를 더 엄격하게 만든 adaptive QRS 후보 |
| C32 | adaptive QRS target event count를 낮추고 pNN/ECP rhythm 후보를 같이 적용한 후보 |

이 후보군은 rhythm timing, morphology sensitivity, amplitude bank, conduction delay evidence, episodic ectopic rescue gate, QRS front-end 민감도를 각각 독립적으로 흔든 뒤 일부 조합을 비교하도록 구성했다. 목적은 단일 feature만 최적화하는 것이 아니라, 최종 class membrane readout에서 서로 충돌하지 않는 조합을 찾는 것이다.

## 4. Validation Ranking

| rank | candidate | val acc | val macro-F1 | val balanced |
|---:|---|---:|---:|---:|
| 1 | C24 | 91.25% | 91.18% | 91.34% |
| 2 | C09 | 90.42% | 90.29% | 90.35% |
| 3 | C07 | 90.00% | 89.93% | 89.99% |
| 4 | C20 | 89.58% | 89.54% | 89.71% |
| 5 | C16 | 88.75% | 88.62% | 88.89% |

상위 후보를 보면 rhythm timing 조정, RAM bank 조밀화, DSCR 엄격화, QRS MAF 조합, RBBB delay 조정이 모두 유효한 축으로 확인됐다. 그중 C24는 validation 기준에서 전체 metric 균형이 가장 좋았기 때문에 최종 후보로 선택했다.

## 5. C24 최종 Parameter

| item | value |
|---|---|
| candidate | `c24` |
| QRS tag | `e5w8t16l0r280a1b1c2000tc100_c24` |
| note | strict RBBB with weaker boost |
| profile | `compact` |
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

## 6. C24 선택 해석

1. C24는 RBBB QRS delay 조건을 민감하게 풀지 않고, width/terminal/repeat 조건을 비교적 엄격하게 둔다.
2. ARR boost와 NSR inhibition을 `100000`으로 제한해 RBBB evidence가 과도하게 class membrane을 지배하지 않게 한다.
3. class boost는 CHF와 ARR을 보강하되 AFF는 1.0으로 유지해 AFF 쪽 과검출을 줄인다.
4. validation 기준 segment accuracy, macro-F1, balanced accuracy가 모두 1위였다.
5. 특정 feature 하나의 성능보다 최종 class membrane readout의 균형이 가장 좋았다.
6. test split은 C24 확정 이후 최종 평가에만 사용했다.
7. 따라서 C24는 최종 Model Snapshot parameter set으로 확정한다.

C24는 RBBB-like conduction delay evidence를 살리되 boost를 과도하게 키우지 않는 보수적인 후보이다. 이 선택은 60초 snapshot classifier에서 abnormal evidence를 반영하면서도 특정 class로 readout이 쏠리는 것을 줄이기 위한 결정이다.
