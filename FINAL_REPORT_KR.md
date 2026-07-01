# SNN ECG V2 최종 마무리 보고서

## 0. 요약

본 프로젝트는 AFE+ADC를 거친 ECG stream을 저전력 RTL 회로에서 처리하여 NSR / CHF / ARR / AFF 4개 class를 분류하는 **SNN-inspired ECG classifier**를 구현하고 검증하는 것을 목표로 한다.

최종 확정 모델명은 **SNN ECG V2**이다.

```text
SNN ECG V2
= Snapshot Model V2
+ Final Membrane Layer V2
```

최종 시스템은 하나의 짧은 ECG snapshot만 보고 환자 상태를 단정하지 않는다. Holter monitor처럼 긴 시간 동안 ECG를 관찰한다는 관점에서, 30분 ECG stream을 60초 snapshot event 30개로 나누고, 각 snapshot에서 발생한 class/evidence spike를 최종 class neuron membrane에 누적하여 30분 chunk class를 결정한다.

최종 구조는 다음과 같다.

```text
30분 AFE+ADC signed 12-bit ECG stream
-> timer neuron이 60000 sample마다 60초 boundary spike 생성
-> Snapshot Model V2가 60초 class/evidence spike 생성
-> Final Membrane Layer V2가 class neuron membrane에 흥분성/억제성 자극 누적
-> 30분 chunk_done 시점 WTA
-> NSR / CHF / ARR / AFF 최종 판정
```

최종 검증 결과:

| 항목 | 결과 |
|---|---:|
| Snapshot Model V2 60초 test accuracy | 205 / 256 = 80.08% |
| SNN ECG V2 30분 Python test accuracy | 32 / 36 = 88.89% |
| SNN ECG V2 30분 XSim test accuracy | 32 / 36 = 88.89% |
| SNN ECG V2 30분 test macro-F1 | 88.46% |
| Python-vs-XSim final prediction mismatch | 0 / 136 |
| Python-vs-XSim final membrane mismatch | 0 / 136 |
| Vivado LUT / FF / BRAM / DSP | 21002 / 2803 / 0 / 0 |
| Vivado estimated total on-chip power | 0.101 W |

## 1. 연구 목적과 Holter-style 설계 동기

일반적인 12-lead ECG는 짧은 시간의 심전도만 기록한다. 그러나 부정맥은 간헐적으로 나타나는 경우가 많고, 짧은 ECG만으로는 rhythm abnormality를 포착하지 못할 수 있다. Holter monitor와 ambulatory ECG monitoring은 이러한 문제를 해결하기 위해 일상 환경에서 장시간 ECG를 연속 기록하고, 그 안에서 transient 또는 infrequent arrhythmia pattern을 찾는 방식이다.

본 연구의 목적은 이러한 Holter-style monitoring 흐름을 FPGA/RTL 관점에서 저전력 SNN-inspired 구조로 옮기는 것이다. 즉 ECG를 큰 software feature vector로 만든 뒤 외부 ML classifier에 넣는 것이 아니라, ECG stream에서 event spike를 만들고, 이 event들이 class neuron membrane에 흥분성/억제성 자극으로 누적되도록 설계한다.

참고한 Holter/ambulatory ECG 근거:

- American Heart Association, [Holter Monitor](https://www.heart.org/en/health-topics/arrhythmia/symptoms-diagnosis--monitoring-of-arrhythmia/holter-monitor)
- Cleveland Clinic, [Holter Monitor: 24 to 48 hours](https://my.clevelandclinic.org/health/diagnostics/21491-holter-monitor)
- NIH/NCBI StatPearls, [Ambulatory ECG Monitoring](https://www.ncbi.nlm.nih.gov/books/NBK597374/)
- NIH/NCBI StatPearls, [Holter Monitor](https://www.ncbi.nlm.nih.gov/books/NBK538203/)

초기 지향점은 24시간 이상 monitoring이었지만, 공개 데이터셋의 ARR record가 MIT-BIH Arrhythmia Database의 30분 excerpt 중심이라는 한계가 있었다. NSR/CHF/AFF는 더 긴 record를 제공하지만 ARR은 30분 수준이므로, 현재 정량 검증은 모든 class를 공정하게 맞추기 위해 **30분 annotation-valid balanced chunk** 기준으로 제한했다.

이 선택의 의미:

1. 본래 지향점은 Holter-style 장시간 monitoring이다.
2. 공개 ARR 데이터셋 길이 한계 때문에 최종 정량 검증은 30분 chunk 기준으로 수행했다.
3. 구조 자체는 30분에 고정되지 않는다. Timer neuron threshold와 final membrane 누적 기간을 확장하면 더 긴 stream에도 적용할 수 있다.
4. 30분 chunk 검증은 “긴 ECG stream을 60초 snapshot으로 반복 평가하고, 반복되는 evidence를 최종 membrane에 누적한다”는 계층형 구조의 축소 실험이다.

## 2. 데이터셋과 AFE+ADC 입력

최종 모델 입력은 raw ECG가 아니라 AFE+ADC가 완료된 signed 12-bit digital stream이다.

AFE+ADC 변환 흐름:

```text
WFDB ECG channel
-> 1 kSPS linear resampling
-> AFE-equivalent filtering/gain
-> ADC quantization
-> signed 12-bit readmemh-compatible .mem
-> RTL adc_data input
```

주요 변환 조건:

| 항목 | 값 |
|---|---|
| sample rate | 1 kSPS |
| input scaling | `V = code / 200000` |
| HPF cutoff | 0.482 Hz |
| instrumentation amplifier gain | x201 |
| notch | 60 Hz Twin-T notch, Q 약 5 |
| LPF cutoff | 150 Hz |
| ADC reference | +/- 1.65 V |
| ADC full span | 3.3 V |
| ADC resolution | 12-bit |
| intermediate format | offset-binary unsigned |
| RTL input format | signed = unsigned - 2048 |

Snapshot V2 60초 검증 데이터셋:

```text
60s_afe_datasets/afe_output_xmodelmatch_curated_v2_128_64_64_balanced
```

30분 SNN ECG V2 검증 데이터셋:

```text
fullrec_afe_30min_annotation_valid_balanced
```

30분 dataset split/class 분포:

| Split | NSR | CHF | ARR | AFF | Total |
|---|---:|---:|---:|---:|---:|
| train | 17 | 17 | 17 | 17 | 68 |
| validation | 8 | 8 | 8 | 8 | 32 |
| test | 9 | 9 | 9 | 9 | 36 |
| all | 34 | 34 | 34 | 34 | 136 |

데이터 출처:

| Class | Source DB | 목적 |
|---|---|---|
| NSR | MIT-BIH Normal Sinus Rhythm Database (`nsrdb`) | 정상 동리듬 record |
| CHF | BIDMC Congestive Heart Failure Database (`chfdb`) | severe CHF subject ECG |
| ARR | MIT-BIH Arrhythmia Database (`mitdb`) | arrhythmia excerpt |
| AFF | MIT-BIH Atrial Fibrillation Database (`afdb`) | AF/AFL rhythm 포함 record |

주의할 점:

1. ARR은 MIT-BIH Arrhythmia Database의 30분 excerpt 성격 때문에 chunk 수와 record 길이가 구조적으로 제한된다.
2. AFF는 record 수가 적어 record diversity가 제한적이다.
3. CHF label은 record-level disease label이며, beat annotation만으로 CHF-specific rhythm을 직접 증명하는 것은 아니다.
4. 최종 split은 record-wise leakage가 없도록 구성했다.

## 3. 전체 RTL 모델 구조

SNN ECG V2는 두 계층으로 구성된다.

```text
Layer 1: Snapshot Model V2
  - 60초 ECG 구간 하나를 4-class로 분류
  - ECG event spike와 feature evidence를 class neuron membrane에 누적
  - 60초 끝에서 WTA로 snapshot pred_class 출력

Layer 2: Final Membrane Layer V2
  - 30분 chunk 안의 60초 snapshot event 30개를 누적
  - snapshot class spike와 보조 evidence neuron membrane을 함께 사용
  - 30분 끝에서 final class neuron WTA 수행
```

핵심 RTL 파일:

```text
rtl/core/snn_ecg_3feat_top.v
rtl/core/class_score_neurons.v
rtl/final_membrane_layer.v
rtl/snn_ecg_30min_final_top.v
rtl/board/snn_ecg_v2_nexys_a7_top.v
```

검증 testbench:

```text
sim/tb_snapshot_c24_dataset.v
sim/tb_snn_ecg_30min_chunk_dataset.v
```

## 4. Timer Neuron 기반 60초 Snapshot Boundary

초기 구현에서는 단순 sample counter로 60초를 끊었다. 그러나 최종 구조는 이를 SNN-style 설명에 맞게 **timer neuron**으로 해석하고 RTL top에 포함했다.

동작:

```text
sample_valid spike
-> timer_mem += 1
-> timer_mem == SNAPSHOT_SAMPLES - 1
-> snapshot_boundary_spike 발생
-> Snapshot V2 segment_done
-> timer_mem reset
-> 다음 60초 snapshot 시작
```

`SNAPSHOT_SAMPLES = 60000`, `SNAPSHOTS_PER_CHUNK = 30`이다. 즉 1 kSPS 기준 60초마다 boundary spike가 발생하고, 30개 boundary event 후 30분 chunk_done이 발생한다.

이 timer neuron은 생물학적 임의 발화 neuron은 아니지만, 입력 sample tick spike를 membrane에 적분하고 threshold 도달 시 boundary spike를 내는 deterministic event neuron으로 해석한다.

## 5. Snapshot Model V2 개요

Snapshot Model V2는 60초 AFE+ADC ECG stream을 받아 NSR / CHF / ARR / AFF 중 하나를 출력하는 SNN-inspired RTL classifier이다.

입력과 출력:

| 항목 | 정의 |
|---|---|
| input | 1 kSPS signed 12-bit `adc_data` |
| snapshot length | 60초 |
| output class | NSR / CHF / ARR / AFF |
| output signal | `pred_class`, `pred_valid`, `c24_mem_*` |
| readout | class neuron membrane WTA |

Snapshot Model V2는 feature vector classifier가 아니다. 각 feature spike/count가 class neuron membrane에 fixed signed weight로 흥분성 또는 억제성 자극을 준다.

```text
if feature_evidence_spike:
    class_mem[NSR] += W_FEATURE_TO_NSR
    class_mem[CHF] += W_FEATURE_TO_CHF
    class_mem[ARR] += W_FEATURE_TO_ARR
    class_mem[AFF] += W_FEATURE_TO_AFF

segment_done:
    pred_class = argmax(class_mem)
```

V2 변경점은 기존 C24 folded spike readout을 유지하면서 **EERG direct class-membrane contribution을 제거**한 것이다. EERG direct path 제거는 validation에서 불필요한 자극 경로를 줄이고 test 성능을 유지했기 때문에 V2에 반영했다.

## 6. Snapshot Feature Block 상세 설명

이 절은 대회 보고서에서 반드시 필요한 핵심 설명이다. SNN ECG V2의 성능은 단순 final layer가 아니라, 아래 feature neuron들이 60초 snapshot 안에서 어떤 rhythm/morphology evidence spike를 만드는지에 의해 결정된다.

### 6.1 Adaptive QRS LIF Detector

Adaptive QRS LIF는 ECG stream에서 QRS complex에 해당하는 강한 slope event를 검출한다. 입력 ADC의 변화량을 보고 QRS-like event를 만들고, 일정 refractory 기간을 둬 같은 QRS를 여러 번 세지 않게 한다.

개념:

```text
delta = adc_data[n] - adc_data[n-1]
abs_delta가 threshold를 넘으면 event 자극
event 자극이 QRS membrane에 누적
QRS membrane이 threshold를 넘으면 beat_spike 발화
refractory 동안 재발화 억제
```

초기 2000 sample 동안 calibration을 수행해 adaptive threshold bank를 선택한다.

주요 파라미터:

| 항목 | 값 |
|---|---:|
| calibration samples | 2000 |
| adaptive min event threshold | 4 |
| adaptive target event count | 100 |
| QRS event weight | 8 |
| QRS threshold | 16 |
| refractory | 280 ms |

출력 `beat_spike`는 PNN, RDM, RAM, ECP, QRS MAF, RBBB feature의 기준 clock 역할을 한다. 즉 QRS LIF는 snapshot feature extractor의 중심 timing neuron이다.

### 6.2 PNN Rhythm Predictor

PNN은 RR interval이 예측 가능한 rhythm window 안에 들어오는지 판단하는 rhythm predictor이다. 이전 beat interval을 기반으로 다음 beat가 예상 window 안에 들어오면 match spike, 벗어나면 mismatch spike를 만든다.

구조:

```text
RR hypothesis neuron bank
-> 250 ms부터 2500 ms까지 50 ms 간격
-> 다음 beat가 예상 window 안이면 pNN match
-> 예상 window 밖이면 pNN mismatch
```

주요 파라미터:

| 항목 | 값 |
|---|---:|
| RR base delay | 250 ms |
| RR step | 50 ms |
| hypothesis count | 46 |
| prediction half window | 125 ms |

해석:

- pNN match가 많으면 rhythm이 비교적 규칙적이라는 자극이다.
- pNN mismatch가 많으면 ARR/AFF 계열 irregular rhythm evidence이다.
- Final Membrane V2에서는 pNN mismatch가 반복될 경우 ARR/AFF 판단에 보조 evidence neuron으로 쓰인다.

### 6.3 RDM Variability Neuron

RDM은 연속 RR interval의 변화량을 직접 측정한다. PNN이 “예상된 beat window와 맞는가”를 보는 feature라면, RDM은 실제 RR 변화량 자체를 보는 feature이다.

계산 개념:

```text
rr_diff = abs(RR_curr - RR_prev)
```

RDM은 10 ms, 20 ms, ..., 150 ms threshold bank를 두고, 변화량이 어느 level까지 넘는지 code/count로 누적한다.

해석:

- RDM code가 작으면 rhythm variability가 낮다.
- RDM code가 크면 beat-to-beat interval 변화가 크다.
- 반복적인 RDM irregularity는 AFF 또는 ARR 계열의 보조 evidence가 된다.

### 6.4 DSCR Spike Counter

DSCR은 ECG waveform의 local slope sign-change와 morphology complexity를 보는 feature이다. Rhythm interval만 보는 PNN/RDM과 달리, DSCR은 waveform 자체의 형태 변화에 더 가깝다.

구조:

```text
delta = adc_data[n] - adc_data[n-1]
valid_slope_spike = abs(delta) >= slope_threshold
sign_flip_spike = current_slope_sign != previous_slope_sign
```

해석:

- valid slope count는 waveform 변화량이 충분히 큰 구간의 수를 의미한다.
- sign flip count는 slope 방향이 얼마나 자주 바뀌는지 나타낸다.
- morphology complexity나 CHF/NSR 분리 보조 evidence로 사용된다.

뉴로모픽 표현:

```text
slope event가 DSCR neuron에 자극을 주고,
sign flip이 반복되면 morphology evidence membrane이 상승한다.
```

### 6.5 RAM Peak Accumulator

RAM은 여기서 Random Access Memory가 아니라 R-peak amplitude response 계열 feature이다. R peak 주변 amplitude가 어느 threshold bank를 통과하는지 code로 변환하고, 이를 60초 동안 누적한다.

구조:

```text
beat_spike 근처 R peak amplitude 관찰
amplitude threshold bank 통과 정도를 code로 변환
ram_code_sum += code
ram_code_count += 1
```

RTL에서는 division으로 평균을 직접 만들지 않는다. 대신 `code_sum`, `code_count`, comparator threshold를 이용한다.

해석:

- R peak amplitude pattern은 class별 morphology 차이를 보조한다.
- RAM은 signed accumulator와 comparator로 구현되며 DSP multiplier를 사용하지 않는다.

### 6.6 ECP Ectopic Pair Neuron

ECP는 ectopic beat에서 나타날 수 있는 early beat와 compensatory pause pattern을 감지한다.

구조:

```text
early RR detected
-> pending state 유지
-> 다음 RR에서 pause pattern 감지
-> ectopic_pair_spike 발화
```

해석:

- ECP spike는 ARR-like ectopic rhythm evidence이다.
- Final Membrane V2에서는 ectopic pair count가 ARR/AFF 혼동 구간에서 중요한 보조 evidence로 쓰인다.

### 6.7 QRS MAF Neuron

QRS MAF는 QRS morphology abnormality를 잡기 위한 feature group이다. QRS width, slope complexity, energy/area deviation 등을 counter와 comparator로 계산한다.

주요 evidence:

```text
qrs_maf_count
qrs_width_abn_count
qrs_complex_abn_count
qrs_energy_abn_count
```

해석:

- QRS width abnormality는 conduction/morphology 이상 가능성을 나타낸다.
- QRS energy abnormality는 waveform amplitude/shape 이상을 나타낸다.
- QRS MAF evidence는 ARR/CHF 분리와 abnormal-priority 판단에 보조로 쓰인다.

### 6.8 RBBB QRS Delay Bank

RBBB QRS Delay Bank는 QRS conduction delay 성격이 반복되는 snapshot을 잡기 위한 proxy feature이다. 이는 임상적 RBBB 진단기라고 주장하는 것이 아니라, RBBB-like conduction delay evidence를 class membrane에 전달하는 보조 neuron이다.

구조:

```text
QRS slope/width/terminal delay pattern 감지
반복되는 delay-like event count
threshold 이상이면 RBBB-like evidence spike
```

주요 파라미터:

| 항목 | 값 |
|---|---:|
| low slope threshold | 5 |
| wide threshold | 120 |
| terminal threshold | 4 |
| repeat threshold | 5 |
| NSR inhibition | 100000 |
| ARR boost | 100000 |

해석:

- RBBB-like evidence는 NSR membrane을 억제하는 자극으로 쓰일 수 있다.
- 동시에 ARR 쪽 abnormal morphology evidence를 강화하는 흥분성 자극으로 쓰인다.

### 6.9 EERG Gate

EERG는 RBBB delay evidence는 없지만 episodic ectopic 또는 boundary abnormal 성격을 보이는 ARR-like snapshot을 rescue하기 위한 gate였다.

기존 조건 개념:

```text
rbbb_like_beat_count == 0
pre_qrs_bump_count >= 1
early_count 또는 ECP_count 충분
pNN mismatch rate 낮음
RDM average 낮음
```

기존 C24에서는 EERG가 ARR class membrane에 직접 boost를 주는 경로가 있었다. 하지만 Snapshot Model V2에서는 이 **EERG direct class-membrane contribution을 제거**했다. 이유는 validation에서 불필요한 자극 경로를 줄이고, test 성능을 유지하면서 모델 설명력을 높였기 때문이다.

따라서 보고서 표현은 다음이 정확하다.

```text
EERG feature/gate 개념은 분석 과정에서 검토되었으나,
Snapshot Model V2의 최종 class membrane 직접 자극 경로에서는 제거되었다.
```

### 6.10 Class Score Neurons / C24 Folded Readout

`class_score_neurons.v`는 feature evidence를 NSR/CHF/ARR/AFF class neuron membrane으로 누적하는 readout block이다.

중요한 점은 Python global readout을 RTL에 그대로 matrix multiplication block으로 넣지 않았다는 것이다. Python C24 coefficient를 feature spike/count별 signed integer weight로 fold하여, feature event가 class membrane에 흥분성 또는 억제성 자극을 주는 형태로 변환했다.

개념:

```text
Python:
    score[class] += feature_count * coef[class]

RTL:
    feature spike/count event 발생
    -> class neuron membrane에 fixed signed weight 누적
```

normalization, count scale, base scale, bias correction은 integer folded weight와 integer bias에 흡수했다. 최종 RTL은 `c24_mem_nsr/chf/arr/aff`를 signed class membrane으로 유지하고, `segment_done`에서 WTA를 수행한다.

## 7. Snapshot 후보군 C01-C32와 V2 선택 과정

Snapshot C24를 선택하기 위해 C01-C32 후보군을 구성했다. 이는 feature 자체를 새로 만드는 탐색이 아니라, 같은 feature set 안에서 timing window, threshold, bank, gate, boost, readout parameter를 바꾸는 후보군이다.

탐색 원칙:

1. train/validation 기준으로 후보를 선택한다.
2. test set은 최종 후보 확정 후 1회 평가한다.
3. record-wise split을 유지한다.
4. accuracy뿐 아니라 macro-F1, balanced accuracy, class별 recall을 함께 본다.
5. RTL에서 counter/comparator/signed accumulator로 구현 가능한 구조만 유지한다.

후보군 요약:

| 후보 | 설명 |
|---|---|
| C01 | pNN window 100 ms + ECP 100 ms |
| C02 | pNN 90 ms + ECP 80 ms |
| C03 | pNN 110 ms + ECP 100 ms |
| C04 | pNN 140 ms + ECP 140 ms |
| C05 | pNN 150 ms + ECP 100 ms |
| C06 | pNN/ECP 100 ms + DSCR 민감화 + RAM low/mid 조정 |
| C07 | DSCR 엄격화 + RAM step 조밀화 |
| C08 | pNN 150 ms + DSCR 민감화 + RAM 조정 |
| C09 | pNN 90 ms + ECP 80 ms + RAM 조밀화 |
| C10 | RAM low-amplitude bank 강화 |
| C11 | RAM mid-low 영역 조밀화 |
| C12 | RAM 전체 조밀화 |
| C13 | RAM bank high-amplitude 이동 |
| C14 | DSCR slope threshold 5 |
| C15 | DSCR slope threshold 6 |
| C16 | DSCR slope threshold 10 |
| C17 | QRS MAF 민감 후보 |
| C18 | QRS MAF 중간 후보 |
| C19 | QRS MAF 엄격 후보 |
| C20 | rhythm 후보 + QRS MAF 중간 조합 |
| C21 | RBBB QRS delay 매우 민감 |
| C22 | RBBB QRS delay 민감 |
| C23 | RBBB baseline 근처 + 강한 ARR boost/NSR inhibition |
| C24 | RBBB 조건 엄격 + 약한 boost |
| C25 | pNN/ECP + 민감한 RBBB delay |
| C26 | EERG permissive |
| C27 | EERG strict |
| C28 | EERG permissive + 강한 ARR boost |
| C29 | pNN/ECP + RBBB delay + EERG 조합 |
| C30 | adaptive QRS front-end 민감 |
| C31 | adaptive QRS front-end 엄격 |
| C32 | adaptive QRS target count 낮춤 + pNN/ECP 조합 |

이후 V2에서는 C24 계열 folded readout을 기반으로 유지하되, EERG direct class-membrane 자극을 제거한 후보를 선택했다.

## 8. Snapshot Model V2 XSim 성능

60초 window-level 성능:

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

해석:

1. Snapshot 단독 test accuracy는 80.08%이다.
2. AFF와 CHF는 비교적 안정적이다.
3. ARR 일부가 NSR/CHF로 이동하는 것이 가장 큰 병목이다.
4. 따라서 30분 Final Membrane Layer V2에서 반복되는 ARR evidence를 누적해 보완한다.

## 9. Final Membrane Layer V2

Final Membrane Layer V2는 Snapshot Model V2 뒤에 붙는 30분 chunk-level readout이다. Snapshot Model V2의 feature threshold, class weight, gate/boost는 고정하고, Final Membrane Layer V2만 별도 탐색/검증했다.

### 9.1 직관적 구조

Snapshot Model V2는 60초마다 class spike를 낸다.

```text
이번 60초는 NSR
이번 60초는 ARR
이번 60초는 AFF
...
```

Final Membrane Layer V2는 30분 동안 30개의 snapshot class spike를 class별 final neuron membrane에 누적한다.

```text
NSR final neuron membrane
CHF final neuron membrane
ARR final neuron membrane
AFF final neuron membrane
```

기본 구조는 majority vote membrane이다.

```text
pred_count_NSR
pred_count_CHF
pred_count_ARR
pred_count_AFF
```

그러나 단순 majority vote는 snapshot WTA에서 패배한 subthreshold evidence를 버린다. 예를 들어 어떤 60초 snapshot의 최종 class가 NSR이더라도, 내부적으로 pNN mismatch, RDM irregularity, ectopic pair, QRS morphology abnormality가 조금씩 반복될 수 있다.

따라서 Final Membrane Layer V2는 보조 evidence neuron membrane도 누적한다.

```text
pNN mismatch evidence neuron
RDM irregularity evidence neuron
ectopic-pair evidence neuron
QRS morphology evidence neuron
RBBB-like conduction evidence neuron
abnormal evidence neuron
```

이 evidence neuron들이 threshold를 넘으면 최종 class neuron에 흥분성 또는 억제성 자극을 넣는다.

예:

```text
ARR evidence가 반복됨
-> ARR final neuron에 흥분성 자극
-> AFF 또는 NSR final neuron에 억제성 자극
```

RTL 구현:

```verilog
final_mem_arr = final_mem_arr + 4;   // ARR 흥분성 자극
final_mem_aff = final_mem_aff - 16;  // AFF 억제성 자극
```

### 9.2 확정 후보

확정 후보:

```text
candidate_id = margin_evidence_0038974
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

이 조건은 comparator network와 signed accumulator로 구현된다. DSP multiplier, floating point, divider, SVC, XGBoost, dense ML classifier는 사용하지 않는다.

### 9.3 뉴로모픽 표현

Final Membrane Layer V2는 완전한 생물학적 SNN이라고 주장하지 않는다. 정확한 표현은 다음이다.

```text
timer-event-driven SNN-inspired final membrane readout
```

구조적 해석:

- timer neuron: 60초마다 snapshot boundary spike 발생
- snapshot class spike: 60초 구간의 local class 발화
- evidence neuron: 병적 rhythm/morphology evidence를 30분 동안 누적
- class neuron membrane: NSR/CHF/ARR/AFF 최종 neuron의 membrane potential
- 흥분성 자극: 해당 class membrane을 상승시키는 signed positive update
- 억제성 자극: competing class membrane을 낮추는 signed negative update
- WTA: 30분 종료 시 가장 큰 membrane potential을 가진 class 출력

## 10. SNN ECG V2 XSim 검증

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

ARR recall은 6/9로 남은 병목이다. 이는 전체 accuracy와 별도로 보고해야 한다.

## 11. Vivado 구현 결과

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

1. DSP 0개: multiplier 기반 dense classifier가 아님을 보여준다.
2. BRAM 0개: final readout과 feature/counter path가 register/LUT 중심임을 보여준다.
3. Dynamic power 0.004 W: datapath switching 추정 전력은 낮다.
4. Total power 0.101 W는 Vivado 추정값이며 실제 보드 전력 측정값은 아니다.

## 12. V1에서 V2로의 변경 요약

기존 V1 계열에서는 60초 Snapshot C24와 여러 30분 final layer 후보가 섞여 있었고, 일부 record-level aggregation 후보나 SVC/선형 classifier 계열 후보가 검토되었다.

V2에서는 다음 기준으로 정리했다.

1. Snapshot은 `Snapshot Model V2`로 고정
2. EERG direct class-membrane contribution 제거
3. 30분 final layer는 `Final Membrane Layer V2`로 고정
4. record-level aggregation 후보 폐기
5. SVC/XGBoost/dense classifier 후보 폐기
6. 30분 stream top 내부에 timer neuron 포함
7. 60초 snapshot boundary를 내부 event로 생성
8. final readout은 class neuron membrane에 흥분성/억제성 자극을 누적하는 구조로 표현
9. Python 등가모델과 XSim RTL의 final pred/mem 일치 확인
10. Vivado bitstream/resource/power report 생성

## 13. 주요 파일

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
scripts/build_snapshot_v2_expected.py
scripts/build_final_membrane_v2_fresh_dump.py
```

Results:

```text
results/snapshot_c24_v2_search/xsim_snapshot_v2_summary.json
results/snapshot_c24_v2_search/snapshot_v2_rtl_xsim_report.md
results/final_membrane_v2_snn/xsim_snn_ecg_v2_summary.json
results/final_membrane_v2_snn/snn_ecg_v2_final_report.md
results/final_membrane_v2_snn/vivado_snn_ecg_v2/snn_ecg_v2_vivado_summary.json
```

## 14. 한계와 향후 개선

현재 한계:

1. ARR 원천 데이터가 30분 excerpt 중심이라 24시간 Holter-style full-record 검증이 어렵다.
2. AFF는 record 수가 적어 record diversity가 낮다.
3. CHF는 record-level disease label이며, beat annotation만으로 CHF-specific rhythm을 직접 증명하기 어렵다.
4. Snapshot V2의 ARR 일부가 NSR/CHF로 흡수되는 문제가 남아 있다.
5. Final Membrane V2 test ARR recall은 6/9로 남은 병목이다.
6. Vivado power는 추정값이며 실제 board-level power 측정은 아직 수행하지 않았다.

향후 개선:

1. 24시간 이상 annotation-rich ARR/AFF/NSR/CHF dataset 확보
2. 더 균형 잡힌 record-level split 구성
3. Final Membrane에 class별 persistence/burst rule을 더 정교하게 추가
4. Snapshot stage별 Python-vs-RTL bit-exact 검증 강화
5. board-level timing/resource/power/throughput 통합 측정
6. clinical disease label과 rhythm annotation 차이를 분리한 evaluation protocol 작성

## 15. 최종 결론

SNN ECG V2는 30분 ECG stream을 60초 snapshot event들의 시간축 발화 패턴으로 해석하고, class neuron membrane에 흥분성/억제성 자극을 누적하여 최종 class를 판정하는 SNN-inspired hierarchical ECG classifier이다.

최종 성능:

```text
Snapshot Model V2 60초 test accuracy: 205/256 = 80.08%
SNN ECG V2 30분 test accuracy: 32/36 = 88.89%
SNN ECG V2 30분 test macro-F1: 88.46%
SNN ECG V2 30분 XSim mismatch: pred 0, mem 0
Vivado DSP usage: 0
Vivado BRAM usage: 0
```

보고서 핵심 문장:

```text
본 시스템은 60초 ECG snapshot을 독립적으로 진단하는 단일 판정기가 아니라,
30분 ECG stream에서 반복적으로 생성되는 snapshot-level class/evidence spike를
final class neuron membrane에 누적하고,
흥분성/억제성 자극을 통해 최종 WTA 판정을 수행하는
SNN-inspired hierarchical ECG classifier이다.
```

## 16. 참고문헌 및 데이터 출처

1. American Heart Association, Holter Monitor.
   https://www.heart.org/en/health-topics/arrhythmia/symptoms-diagnosis--monitoring-of-arrhythmia/holter-monitor

2. Cleveland Clinic, Holter Monitor: Purpose, Results & How It Works.
   https://my.clevelandclinic.org/health/diagnostics/21491-holter-monitor

3. Ambulatory ECG Monitoring, StatPearls, NCBI Bookshelf.
   https://www.ncbi.nlm.nih.gov/books/NBK597374/

4. Holter Monitor, StatPearls, NCBI Bookshelf.
   https://www.ncbi.nlm.nih.gov/books/NBK538203/

5. MIT-BIH Arrhythmia Database, PhysioNet.
   https://physionet.org/content/mitdb/1.0.0/

6. MIT-BIH Normal Sinus Rhythm Database, PhysioNet.
   https://physionet.org/content/nsrdb/1.0.0/

7. BIDMC Congestive Heart Failure Database, PhysioNet.
   https://physionet.org/content/chfdb/1.0.0/

8. MIT-BIH Atrial Fibrillation Database, PhysioNet.
   https://physionet.org/content/afdb/1.0.0/
