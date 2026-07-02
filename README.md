# SNN ECG V2

이 저장소는 AFE+ADC가 완료된 ECG stream을 저전력 RTL 구조로 처리하는 **SNN-inspired 4-class ECG classifier**이다.

현재 확정 모델명은 **SNN ECG V2**이다.

대회 제출/최종 설명 기준의 상세 문서는 반드시 [FINAL_REPORT_KR.md](FINAL_REPORT_KR.md)를 먼저 읽으면 된다. 해당 문서에는 연구 목적, Holter-style 설계 동기, AFE+ADC 조건, Snapshot feature block의 뉴로모픽 동작 설명, Final Membrane Layer V2, XSim 성능, Vivado 자원량이 모두 포함되어 있다.

```text
SNN ECG V2
= Snapshot Model V2
+ Final Membrane Layer V2
```

분류 class는 다음 네 가지이다.

| Class | 의미 |
|---|---|
| NSR | Normal Sinus Rhythm |
| CHF | Congestive Heart Failure |
| ARR | Arrhythmia |
| AFF | Atrial Fibrillation/Flutter 계열 |

## 전체 구조

SNN ECG V2는 30분 AFE+ADC ECG stream을 직접 입력받고, 내부 timer neuron이 60초마다 snapshot boundary spike를 만든다. 각 60초 구간은 Snapshot Model V2로 분류되고, 30개의 snapshot 결과는 Final Membrane Layer V2에 누적된다.

```text
30분 signed 12-bit AFE+ADC ECG stream
-> timer neuron: 60000 sample마다 60초 boundary spike 발생
-> Snapshot Model V2: 60초 구간별 class/evidence spike 생성
-> Final Membrane Layer V2: class neuron membrane에 흥분성/억제성 자극 누적
-> 30분 chunk_done
-> WTA
-> NSR / CHF / ARR / AFF
```

이 구조는 단순 software classifier가 아니라, RTL에서 counter, comparator, signed accumulator, threshold, WTA로 구현되는 **event-driven membrane readout**이다.

## Snapshot Model V2

Snapshot Model V2는 60초 ECG window 하나를 분류하는 고정 snapshot classifier이다.

입력:

- 60초
- 1 kSPS
- signed 12-bit AFE+ADC `.mem`
- 60000 samples/window

출력:

- `pred_class`
- `pred_valid`
- `c24_mem_nsr`
- `c24_mem_chf`
- `c24_mem_arr`
- `c24_mem_aff`

핵심 흐름:

```text
AFE+ADC sample
-> QRS/event/rhythm/morphology feature spike
-> fixed signed synaptic weight
-> class membrane accumulation
-> 60초 segment_done
-> 4-class WTA
```

Snapshot V2는 기존 C24 folded spike readout을 유지하되, EERG direct class-membrane 기여를 제거한 구조이다. EERG 제거는 validation에서 불필요한 경로를 줄이면서 test 성능을 유지했기 때문에 V2에 반영했다.

Snapshot Model V2의 주요 feature neuron은 다음과 같다. 상세 알고리즘은 [FINAL_REPORT_KR.md](FINAL_REPORT_KR.md)의 “Snapshot Feature Block 상세 설명” 절에 정리되어 있다.

| Feature block | 역할 |
|---|---|
| Adaptive QRS LIF | ADC slope event를 적분해 QRS/beat spike를 만든다. |
| PNN Rhythm Predictor | RR interval 예측 window 기반 match/mismatch rhythm evidence를 만든다. |
| RDM Variability Neuron | 연속 RR interval 변화량을 level/count로 누적한다. |
| DSCR Spike Counter | slope sign flip과 morphology complexity evidence를 만든다. |
| RAM Peak Accumulator | R-peak amplitude response를 threshold-bank code로 누적한다. |
| ECP Ectopic Pair Neuron | early beat + compensatory pause pattern을 감지한다. |
| QRS MAF Neuron | QRS width/complexity/energy abnormal evidence를 만든다. |
| RBBB QRS Delay Bank | RBBB-like conduction delay proxy evidence를 만든다. |
| EERG Gate | 검토된 ARR-like rescue gate이며, V2에서는 direct class-membrane 자극 경로를 제거했다. |

## Final Membrane Layer V2

Final Membrane Layer V2는 30분 동안 들어오는 30개의 snapshot 발화 결과를 모아 최종 class를 판정한다.

가장 단순한 기준은 snapshot `pred_class`의 class별 발화 횟수이다.

```text
pred_count_NSR
pred_count_CHF
pred_count_ARR
pred_count_AFF
```

이것은 majority vote membrane에 해당한다.

하지만 snapshot WTA는 60초마다 하나의 class만 출력하므로, WTA에서 패배한 subthreshold evidence가 사라질 수 있다. 그래서 Final Membrane V2는 보조 evidence neuron membrane도 함께 누적한다.

예:

- pNN mismatch evidence neuron
- RDM irregularity evidence neuron
- ectopic-pair evidence neuron
- QRS MAF morphology evidence neuron
- RBBB-like conduction evidence neuron
- abnormal evidence neuron

30분 동안 특정 병적 evidence neuron이 충분히 활성화되면, 최종 class neuron에 자극을 넣는다.

- ARR neuron에 양의 자극: ARR membrane 상승
- AFF/NSR/CHF neuron에 음의 자극: 해당 membrane 억제

RTL에서는 이것이 signed add/subtract로 구현된다.

```verilog
final_mem_arr = final_mem_arr + 4;   // ARR neuron 흥분성 자극
final_mem_aff = final_mem_aff - 16;  // AFF neuron 억제성 자극
```

최종 확정 후보는 `margin_evidence_0038974`이다.

```text
if 현재 우세 class가 AFF이고
   AFF 우세 margin이 작고
   ARR snapshot 발화가 최소 3회 이상이며
   RDM / pNN mismatch / ectopic / abnormal evidence가 충분하면:
       ARR final neuron에 흥분성 자극 +4
       AFF final neuron에 억제성 자극 -16
```

이 구조는 SVC, XGBoost, dense classifier가 아니다. RTL에서 comparator, counter, signed accumulator, WTA만 사용한다.

## 주요 RTL 파일

```text
rtl/core/class_score_neurons.v
rtl/core/snn_ecg_3feat_top.v
rtl/final_membrane_layer.v
rtl/snn_ecg_30min_final_top.v
rtl/board/snn_ecg_v2_nexys_a7_top.v
```

## 검증 스크립트

```text
scripts/snapshot_c24_rtl_exact.py
scripts/snapshot_c24_v2_search.py
scripts/search_final_membrane_v2_snn.py
scripts/search_final_membrane_v2_arr_focus.py
scripts/run_snapshot_v2_xsim.py
scripts/run_final_membrane_v2_xsim.py
scripts/build_snn_ecg_v2_bitstream.py
```

`snapshot_c24_v2_search.py`, `search_final_membrane_v2_snn.py`, `search_final_membrane_v2_arr_focus.py`는 이름에 `search`가 남아 있지만, 현재 repo에서는 최종 V2 Python 등가모델과 XSim expected 결과 생성에 필요한 고정 모듈로 보존한다.

실행 예:

```powershell
python scripts\run_snapshot_v2_xsim.py --split all
python scripts\run_final_membrane_v2_xsim.py --split all
python scripts\build_snn_ecg_v2_bitstream.py
```

## Snapshot Model V2 XSim 성능

60초 window-level 성능이다.

| Split | Correct / Total | Accuracy | Macro-F1 | Balanced Acc. |
|---|---:|---:|---:|---:|
| train | 466 / 512 | 91.02% | 90.96% | 91.02% |
| validation | 231 / 256 | 90.23% | 90.29% | 90.23% |
| test | 205 / 256 | 80.08% | 80.06% | 80.08% |

Snapshot V2 test confusion matrix:

| True \ Pred | NSR | CHF | ARR | AFF |
|---|---:|---:|---:|---:|
| NSR | 50 | 12 | 2 | 0 |
| CHF | 7 | 56 | 0 | 1 |
| ARR | 15 | 3 | 42 | 4 |
| AFF | 0 | 4 | 3 | 57 |

Snapshot V2 test class별 성능:

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| NSR | 69.44% | 78.12% | 73.53% |
| CHF | 74.67% | 87.50% | 80.58% |
| ARR | 89.36% | 65.62% | 75.68% |
| AFF | 91.94% | 89.06% | 90.48% |

## SNN ECG V2 30분 XSim 성능

30분 chunk-level 성능이다. Python 등가모델과 RTL/XSim 결과가 `pred_class`와 `final_mem[4]` 기준으로 일치한다.

| Split | Python | XSim | Pred mismatch | Mem mismatch |
|---|---:|---:|---:|---:|
| train | 62 / 68 = 91.18% | 62 / 68 = 91.18% | 0 | 0 |
| validation | 31 / 32 = 96.88% | 31 / 32 = 96.88% | 0 | 0 |
| test | 32 / 36 = 88.89% | 32 / 36 = 88.89% | 0 | 0 |

SNN ECG V2 test confusion matrix:

| True \ Pred | NSR | CHF | ARR | AFF |
|---|---:|---:|---:|---:|
| NSR | 9 | 0 | 0 | 0 |
| CHF | 0 | 9 | 0 | 0 |
| ARR | 2 | 1 | 6 | 0 |
| AFF | 0 | 0 | 1 | 8 |

SNN ECG V2 test class별 성능:

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| NSR | 81.82% | 100.00% | 90.00% |
| CHF | 90.00% | 100.00% | 94.74% |
| ARR | 85.71% | 66.67% | 75.00% |
| AFF | 100.00% | 88.89% | 94.12% |

Test macro-F1은 88.46%, balanced accuracy는 88.89%이다.

## Vivado 구현 결과

대상 FPGA:

```text
Nexys A7 / Artix-7 xc7a100tcsg324-1
```

Bitstream:

```text
results/final_membrane_v2_snn/vivado_snn_ecg_v2/bitstream/snn_ecg_v2_nexys_a7_top.bit
```

자원 사용량:

| Resource | Used | Available | Utilization |
|---|---:|---:|---:|
| LUT | 21002 | 63400 | 33.13% |
| FF | 2803 | 126800 | 2.21% |
| BRAM | 0 | 135 | 0.00% |
| DSP | 0 | 240 | 0.00% |
| Bonded IOB | 35 | 210 | 16.67% |
| BUFGCTRL | 2 | 32 | 6.25% |

Vivado power estimate:

| Power | W |
|---|---:|
| Total on-chip | 0.101 |
| Dynamic | 0.004 |
| Static | 0.097 |

Timing:

| Item | Value |
|---|---:|
| sys_clk_pin | 100 MHz |
| core_clk_1mhz | 1 MHz |
| WNS | 7.873 ns |
| TNS | 0.000 ns |
| WHS | 0.032 ns |
| THS | 0.000 ns |
| WPWS | 4.500 ns |
| TPWS | 0.000 ns |

FPGA board programming:

| Item | Value |
|---|---|
| Board target | Digilent / Nexys A7 |
| Detected device | `xc7a100t_0` |
| Program status | OK |
| Startup status | HIGH |
| Programmed at | 2026-07-02 20:19:25 |
| Bitstream size | 3,825,908 bytes |
| Board report | `results/final_membrane_v2_snn/vivado_snn_ecg_v2/board_program_report.txt` |

DSP 0개이므로 multiplier 기반 ML classifier가 아니라, comparator/counter/accumulator 기반 SNN-inspired RTL 구조임을 확인할 수 있다.
보드에는 bitstream이 정상적으로 올라갔고, 현재 board wrapper에는 UART/ILA 기반 live ECG stream 계측 경로가 없기 때문에 보드 위 실제 분류 정확도는 XSim dataset replay 결과로 검증한다.

## 주의사항

- 본 모델은 `SNN-inspired` 구조이다. 완전한 생물학적 SNN이나 STDP 학습 구조라고 주장하지 않는다.
- Final Membrane Layer V2는 1 kSPS sample마다 직접 class spike를 내는 층이 아니라, 60초 snapshot event를 시간축으로 누적하는 final readout이다.
- 30분 데이터셋은 class별 30분 chunk 수를 균형화한 `chunk-level balanced` 데이터셋이다. 원천 record 수가 class별로 같지 않기 때문에 모든 chunk가 서로 다른 record에서 나온 strict record-wise holdout은 아니다.
- XSim 정확도는 30분 `.mem` dataset testbench 기준이다.
- Vivado power는 실제 보드 전류 측정값이 아니라 post-implementation 추정값이다.
- ARR test recall은 6/9로 남은 병목이다. 전체 accuracy와 별도로 보고해야 한다.
