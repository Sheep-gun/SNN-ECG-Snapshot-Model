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
| SNN ECG V2 30분 chunk-level Python test accuracy | 32 / 36 = 88.89% |
| SNN ECG V2 30분 chunk-level XSim test accuracy | 32 / 36 = 88.89% |
| SNN ECG V2 30분 chunk-level test macro-F1 | 88.46% |
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

위 표는 30분 chunk 수 기준이다. 확보된 원본 record 수 자체가 class별로 동일하지 않기 때문에, 현재 30분 데이터셋은 “모든 chunk가 서로 다른 record에서 나온 strict record-wise holdout”이 아니라 **class별 chunk 수를 균형화한 30분 chunk-level balanced dataset**이다.

30분 dataset의 원천 record/chunk 구조:

| Class | 사용된 unique records | 30분 chunks | 해석 |
|---|---:|---:|---|
| NSR | 18 | 34 | 일부 긴 NSR record에서 여러 30분 chunk 생성 |
| CHF | 14 | 34 | 일부 CHF record에서 여러 30분 chunk 생성 |
| ARR | 34 | 34 | MIT-BIH ARR 30분 excerpt 특성상 대체로 record당 1 chunk |
| AFF | 4 | 34 | 적은 수의 긴 AFF record에서 여러 30분 chunk 생성 |

여기서 `사용된 unique records`는 원본 DB 전체 record 수가 아니라, 본 전처리 및 annotation-valid 조건을 통과해 실제 30분 chunk 생성에 사용된 원천 record 수를 의미한다.

따라서 본 보고서의 30분 성능은 chunk-level evaluation으로 해석해야 한다. 이는 원천 공개 데이터셋의 길이와 record 수 제한 때문에 선택한 현실적 검증 방식이며, 향후 더 많은 원천 record가 확보되면 strict record-wise holdout으로 다시 검증해야 한다.

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
4. 30분 데이터셋은 class별 chunk 수는 균형화되어 있지만, NSR/CHF/AFF에서는 같은 원천 record에서 나온 여러 chunk가 존재한다.
5. 따라서 현재 30분 검증은 strict record-wise holdout 성능으로 주장하지 않고, 30분 chunk-level balanced 성능으로 보고한다.

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

이 절은 대회 보고서에서 가장 중요하다. SNN ECG V2의 Snapshot Model은 ECG를 먼저 거대한 software feature vector로 만든 뒤 외부 classifier에 넣는 방식이 아니다. ECG stream에서 작은 event neuron들이 차례로 발화하고, 그 발화가 rhythm 또는 morphology evidence가 되어 class neuron membrane에 흥분성/억제성 자극을 넣는 구조이다.

아래 설명에서 사용하는 공통 언어는 다음과 같다.

```text
뉴런 membrane: 자극이 누적되는 정수 accumulator
흥분성 자극: membrane 값을 올리는 signed positive update
억제성 자극: membrane 값을 낮추는 signed negative update
임계값 threshold: membrane 또는 count가 넘으면 발화하는 기준
발화 spike: 다음 neuron이나 class membrane에 전달되는 event
leak: 시간이 지나면서 membrane이 조금씩 줄어드는 손실
refractory: 한 번 발화한 뒤 잠시 다시 발화하지 못하게 하는 억제 구간
```

### 6.1 Event Encoder와 Adaptive QRS LIF Detector

심전도에서 가장 먼저 잡아야 하는 것은 QRS파이다. QRS는 R peak 주변에서 짧은 시간 동안 기울기가 크게 변한다. 따라서 RTL은 “파형 전체를 해석”하기 전에, 먼저 강한 상승/하강 event를 만드는 뉴런을 둔다.

1단계는 event encoder이다.

```text
현재 sample과 이전 sample을 뺀다.
delta = adc_data[n] - adc_data[n-1]

abs(delta)가 threshold보다 크면 strong_event가 발화한다.
delta가 양수면 up_event 성격이고,
delta가 음수면 down_event 성격이다.
```

이 `strong_event`는 ECG에서 “갑자기 크게 움직인 순간”을 의미한다. QRS 구간에서는 이런 strong event가 짧은 시간 안에 연속해서 나타난다.

2단계는 QRS LIF neuron이다.

```text
strong_event 발생
-> QRS LIF membrane에 W_EVENT만큼 흥분성 자극 입력

strong_event가 없는 clock
-> QRS LIF membrane에서 LEAK_QRS만큼 손실

QRS LIF membrane >= T_QRS
-> beat_spike 발화
-> QRS LIF membrane reset
-> refractory counter 시작
```

즉 QRS LIF neuron은 단발성 noise 하나에는 잘 반응하지 않는다. 그러나 QRS 구간처럼 strong event가 연속해서 들어오면 leak을 이기고 membrane이 임계값을 넘는다. 그 순간의 `beat_spike`가 “QRS 하나를 찾았다”는 발화이다.

refractory는 같은 QRS를 여러 번 세지 않기 위한 억제 장치이다. 한 번 `beat_spike`가 발생하면 일정 시간 동안 QRS membrane을 0으로 유지하고 재발화를 막는다.

초기 2000 sample 동안은 adaptive threshold calibration을 수행한다. ECG record마다 amplitude와 noise 수준이 다르므로, calibration 구간에서 delta 분포를 보고 strong event threshold를 맞춘다.

주요 RTL 파일:

```text
rtl/core/ecg_event_encoder_adaptive.v
rtl/core/qrs_lif_detector.v
```

주요 파라미터:

| 항목 | 의미 |
|---|---|
| `ADAPT_CALIB_SAMPLES` | segment 시작부 threshold calibration 길이 |
| `ADAPT_MIN_EVENT_TH` | adaptive event threshold 하한 |
| `ADAPT_TARGET_EVENT_COUNT` | calibration 중 목표 event 수 |
| `QRS_W_EVENT` | strong event가 QRS membrane에 주는 흥분성 자극 |
| `QRS_LEAK` | QRS membrane의 clock별 손실 |
| `QRS_TH` | QRS neuron 발화 임계값 |
| `QRS_REF` | beat 발화 후 재발화 억제 시간 |

이 QRS LIF의 출력 `beat_spike`는 뒤 feature들의 기준 clock이 된다. PNN, RDM, RAM, ECP, QRS MAF, RBBB feature는 모두 이 beat spike를 중심으로 “박동 간격”, “박동 주변 amplitude”, “QRS 폭”, “QRS terminal delay”를 관찰한다.

### 6.2 PNN Rhythm Predictor

PNN은 “다음 박동이 언제 올지 예측하고, 실제 박동이 그 예측을 지켰는지”를 보는 rhythm neuron이다. 여기서 중요한 점은 winner가 단순한 출력값이 아니라, 다음 beat 판단의 기준으로 저장된다는 것이다.

목표는 다음과 같다.

```text
RR interval이 일정하게 반복되는가?
직전 rhythm으로 예측한 다음 beat 위치에 실제 beat가 들어왔는가?
```

PNN 내부에는 여러 개의 RR hypothesis neuron이 있다.

```text
hypothesis 0: 250 ms
hypothesis 1: 300 ms
hypothesis 2: 350 ms
...
hypothesis 45: 2500 ms
```

각 hypothesis neuron은 “RR interval이 이 정도일 것이다”라는 후보이다. QRS LIF가 beat spike를 내면, PNN은 지난 beat부터 이번 beat까지 흐른 시간 `token_age`를 현재 RR interval로 본다.

동작 순서는 다음과 같다.

```text
1. beat_spike가 들어온다.
2. 지난 beat 이후 흐른 token_age를 현재 RR interval로 확정한다.
3. 46개 RR hypothesis neuron 중 현재 RR과 가장 가까운 neuron을 찾는다.
4. 그 neuron이 current winner가 된다.
5. current winner는 predictor_id로 저장되어 다음 beat의 기준이 된다.
6. 다음 beat가 오면, 이번 RR을 직전 predictor_id의 중심값과 비교한다.
7. 차이가 WINDOW_HALF 이내이면 pnn_match_spike 발화.
8. 차이가 WINDOW_HALF 밖이면 pnn_mismatch_spike 발화.
```

정확히는 이번 beat에서 match/mismatch를 판단할 때 사용하는 기준은 직전 beat에서 저장된 `predictor_id`이다. 이번 RR로 새로 선택한 `current_winner`는 다음 beat를 평가할 `predictor_id`로 저장된다. 첫 valid RR은 predictor를 초기화하는 용도이므로, match/mismatch 판정은 이전 predictor가 존재한 뒤부터 유효하다.

따라서 PNN의 핵심은 다음 문장이다.

```text
현재 RR의 winner neuron이 다음 RR을 평가할 predictor neuron으로 넘어간다.
```

예를 들어 현재 RR이 800 ms 근처라면 800 ms hypothesis가 winner가 된다. 그러면 PNN은 다음 beat도 약 800 ms 근처에 올 것이라고 기대한다. 다음 beat가 790 ms에 오면 match이고, 500 ms나 1200 ms에 오면 mismatch이다.

해석:

- `pnn_match_spike`: rhythm이 직전 winner가 만든 예측을 지켰다는 발화
- `pnn_mismatch_spike`: rhythm이 직전 winner 예측에서 벗어났다는 발화
- match가 많으면 비교적 규칙적인 rhythm evidence
- mismatch가 반복되면 ARR/AFF 계열 irregular rhythm evidence

주요 RTL 파일:

```text
rtl/core/pnn_rhythm_predictor.v
```

주요 파라미터:

| 항목 | 값/의미 |
|---|---|
| `BASE_DELAY` | 첫 RR hypothesis 중심값 |
| `DELAY_STEP` | hypothesis 간격 |
| `NUM_HYP` | hypothesis neuron 개수 |
| `WINDOW_HALF` | predictor와 실제 RR을 match로 볼 허용 반경 |

### 6.3 RDM Variability Neuron

RDM은 PNN보다 더 직접적인 rhythm variability detector이다. PNN은 “예측을 지켰는가”를 보지만, RDM은 “이번 RR과 직전 RR이 얼마나 달라졌는가”를 본다.

목표는 다음과 같다.

```text
연속된 beat 간격이 안정적인가?
아니면 beat마다 RR interval이 크게 흔들리는가?
```

동작은 단순하지만 SNN-style threshold bank로 구현된다.

```text
beat_spike로 RR interval이 확정된다.
현재 RR과 직전 RR을 비교한다.

rr_diff = abs(RR_curr - RR_prev)

rr_diff가 10 ms 이상이면 level 1 neuron 발화
rr_diff가 20 ms 이상이면 level 2 neuron 발화
...
rr_diff가 150 ms 이상이면 level 15 neuron 발화
```

즉 RDM은 하나의 숫자를 floating point로 계산하는 블록이 아니라, 여러 threshold neuron이 계단처럼 배치된 구조이다. 변화량이 작으면 낮은 level까지만 발화하고, 변화량이 크면 높은 level neuron까지 발화한다.

해석:

- `rdm_valid_spike`: 이번 beat에서 RR 변화량 측정이 유효하다는 발화
- `rdm_level_code`: RR 변화량이 어느 정도 level까지 올라갔는지 나타내는 코드
- 낮은 RDM code 반복: 안정적인 rhythm
- 높은 RDM code 반복: beat-to-beat variability가 큰 rhythm

RDM은 특히 AFF처럼 RR interval이 불규칙하게 흔들리는 경우를 잡는 데 중요한 보조 evidence가 된다. ARR에서도 일부 irregular burst를 잡는 데 쓰인다.

주요 RTL 파일:

```text
rtl/core/rdm_variability_neuron.v
```

### 6.4 DSCR Spike Counter

DSCR은 rhythm interval이 아니라 ECG waveform의 모양을 보는 neuron이다. PNN/RDM이 beat 사이의 시간 간격을 본다면, DSCR은 한 beat 안팎에서 파형의 기울기가 어떻게 바뀌는지를 본다.

목표는 다음과 같다.

```text
파형이 단순하고 매끈한가?
아니면 상승/하강 기울기가 자주 바뀌는 복잡한 morphology인가?
```

DSCR은 먼저 ECG를 leaky filter로 부드럽게 만든다. 그 다음 현재 filter 값의 변화량을 slope input으로 본다.

```text
filtered ECG 계산
slope_input = filtered[n] - filtered[n-1]
```

그 다음 두 개의 slope LIF neuron을 둔다.

```text
positive slope neuron:
    상승 기울기 자극을 누적
    시간이 지나면 leak 발생
    충분히 큰 상승 기울기가 쌓이면 valid_slope_spike 발화

negative slope neuron:
    하강 기울기 자극을 누적
    시간이 지나면 leak 발생
    충분히 큰 하강 기울기가 쌓이면 valid_slope_spike 발화
```

이렇게 하면 아주 작은 흔들림은 leak에 의해 사라지고, 의미 있는 상승/하강만 slope spike가 된다.

그 다음 sign flip neuron이 있다.

```text
직전 valid slope가 상승이었고 이번 valid slope가 하강이면 sign flip 자극
직전 valid slope가 하강이었고 이번 valid slope가 상승이면 sign flip 자극
sign flip 자극이 threshold를 넘으면 dscr_sign_flip_spike 발화
```

해석:

- `dscr_valid_slope_spike`: 의미 있는 waveform slope가 감지되었다는 발화
- `dscr_sign_flip_spike`: 파형 기울기 방향이 의미 있게 바뀌었다는 발화
- slope/sign flip이 많으면 morphology가 복잡하거나 에너지가 많은 구간으로 해석된다.
- 이 evidence는 CHF/NSR 분리, AFF/ARR 보조 판단, QRS MAF와 연결된 morphology 판단에 쓰인다.

주요 RTL 파일:

```text
rtl/core/dscr_spike_counter.v
```

### 6.5 RAM Peak Accumulator

RAM은 여기서 memory RAM이 아니라 R-peak amplitude response를 보는 feature이다. QRS LIF가 beat를 찾으면, RAM은 그 beat 주변에서 baseline 대비 R peak가 얼마나 크게 올라갔는지 본다.

목표는 다음과 같다.

```text
R peak의 amplitude가 어느 정도인가?
beat마다 amplitude pattern이 class별로 다른가?
```

동작은 다음과 같다.

```text
1. QRS 주변 amplitude 관찰 window를 연다.
2. 각 sample에서 baseline을 뺀다.
3. baseline보다 위에 있는 양의 amplitude만 본다.
4. amplitude threshold bank를 통과한 정도를 code로 만든다.
5. window 안에서 가장 큰 code를 R peak amplitude code로 잡는다.
6. beat가 확인되면 ram_amp_spike와 ram_amp_code를 낸다.
```

여기서 threshold bank는 여러 amplitude neuron으로 볼 수 있다.

```text
amplitude >= BANK_BASE + 0 * BANK_STEP -> level 1
amplitude >= BANK_BASE + 1 * BANK_STEP -> level 2
...
amplitude가 더 크면 더 높은 amplitude neuron 발화
```

해석:

- `ram_amp_spike`: 이번 beat의 R peak amplitude가 하나의 code로 확정되었다는 발화
- `ram_amp_code`: R peak amplitude가 어느 amplitude bank까지 올라갔는지 나타내는 코드
- `ram_code_sum`: 60초 동안 R peak amplitude code가 누적된 값
- `ram_code_count`: amplitude가 측정된 beat 수

RTL은 평균 amplitude를 divider로 계산하지 않는다. `ram_code_sum`, `ram_code_count`, threshold comparator를 사용하여 class membrane 자극으로 fold한다. 따라서 DSP multiplier나 divider 없이 구현된다.

주요 RTL 파일:

```text
rtl/core/ram_peak_accumulator.v
```

### 6.6 ECP Ectopic Pair Neuron

ECP는 ectopic beat에서 자주 나타나는 “조기 박동 + 보상성 지연” 패턴을 잡는 neuron이다. 단순히 RR이 짧거나 길다는 사실 하나만 보지 않고, early와 late가 번갈아 나타나는 패턴을 본다.

목표는 다음과 같다.

```text
정상 rhythm 기준보다 너무 빠른 beat가 있었는가?
그 다음에 보상하듯 늦은 beat가 따라왔는가?
또는 반대로 late 이후 early가 나타났는가?
```

ECP는 먼저 천천히 움직이는 reference RR을 유지한다.

```text
rr_ref = 최근 RR interval을 따라가는 기준 interval
```

새 RR interval이 들어오면 `rr_ref`와 비교한다.

```text
RR_curr + RR_DELTA_TH < rr_ref
-> early_rr_spike 발화

RR_curr > rr_ref + RR_DELTA_TH
-> late_rr_spike 발화
```

그 다음 pattern memory가 있다.

```text
직전 pattern이 early였고 이번 pattern이 late이면 ectopic_pair_spike
직전 pattern이 late였고 이번 pattern이 early이면 ectopic_pair_spike
```

즉 ECP는 early 하나만 보고 바로 질병 evidence라고 하지 않는다. early와 late가 교대로 나타나는 “쌍”을 볼 때 ectopic pair neuron이 발화한다.

해석:

- `early_rr_spike`: 기준 RR보다 유의미하게 짧은 RR
- `late_rr_spike`: 기준 RR보다 유의미하게 긴 RR
- `ectopic_pair_spike`: early/late가 번갈아 나타난 ectopic-like pair
- 이 발화는 ARR-like rhythm evidence로 쓰인다.

주요 RTL 파일:

```text
rtl/core/ectopic_pair_neuron.v
```

### 6.7 QRS MAF Neuron

QRS MAF(Morphology Abnormality Feature)는 QRS 주변의 morphology abnormality를 보는 feature group이다. 여기서 MAF는 단일 feature 하나가 아니라, QRS 주변 event 폭, 복잡도, energy 변화를 함께 보는 작은 morphology analyzer에 가깝다.

목표는 다음과 같다.

```text
QRS가 너무 넓은가?
QRS 주변 기울기 변화가 복잡한가?
QRS 주변 energy가 평소와 다르게 튀는가?
QRS 직전에 이상한 bump가 있는가?
```

동작은 beat spike를 기준으로 pre-window와 post-window를 잡는 방식이다.

```text
beat_spike 발생 전 PRE_WIN sample:
    strong_event, dscr_sign_flip, energy를 shift register로 저장

beat_spike 발생 후 POST_WIN sample:
    strong_event, dscr_sign_flip, energy를 계속 누적

window 종료:
    QRS width, complexity count, energy code, pre-QRS bump 여부 계산
```

QRS width neuron:

```text
QRS window 안에서 첫 strong_event 위치와 마지막 strong_event 위치를 찾는다.
width = last_pos - first_pos
width가 threshold를 넘거나 평소 width reference에서 크게 벗어나면 qrs_width_abn_spike 발화
```

QRS complexity neuron:

```text
QRS window 안의 dscr_sign_flip_spike 수를 센다.
sign flip이 많으면 qrs_complex_abn_spike 발화
```

QRS energy neuron:

```text
baseline 대비 abs(sample-baseline)을 energy code로 누적한다.
평소 energy reference와 많이 다르면 qrs_energy_abn_spike 발화
```

Pre-QRS bump neuron:

```text
beat 직전 PRE_WIN 안에 strong_event, sign flip, energy가 이미 많으면
pre_qrs_bump_spike 발화
```

해석:

- `qrs_maf_valid_spike`: QRS morphology 측정 window가 끝났다는 발화
- `qrs_width_abn_spike`: QRS 폭이 넓거나 평소보다 달라졌다는 발화
- `qrs_complex_abn_spike`: QRS 주변 slope sign flip이 많다는 발화
- `qrs_energy_abn_spike`: QRS energy가 평소 reference에서 벗어났다는 발화
- `pre_qrs_bump_spike`: QRS 직전에 이상 event가 있었다는 발화

이 feature는 ARR/CHF/AFF가 rhythm만으로는 헷갈리는 경우 morphology evidence를 제공한다.

주요 RTL 파일:

```text
rtl/core/qrs_maf_neuron.v
```

### 6.8 RBBB QRS Delay Bank

RBBB QRS Delay Bank는 임상적 RBBB 진단기라고 주장하는 블록이 아니다. 이름 그대로 RBBB-like conduction delay 성격, 즉 QRS가 넓고 terminal activity가 길게 남는 패턴을 잡는 proxy evidence neuron이다.

목표는 다음과 같다.

```text
QRS가 넓게 지속되는가?
QRS 후반부 terminal 구간에도 activity가 남는가?
이런 beat가 60초 안에서 반복되는가?
```

먼저 QRS activity onset neuron이 있다.

```text
strong_event 또는 slope_valid가 발생하고
직전 clock에는 activity가 없었고
현재 QRS 관찰 window가 닫혀 있으면
qrs_onset_spike 발화
```

onset 이후 QRS observation window가 열린다.

```text
qrs_age가 0부터 증가
activity가 계속 있는지 관찰
activity gap이 길어지거나 MAX_QRS_OBS_WIN에 도달하면 QRS window 종료
```

그 안에서 delay bank가 작동한다.

```text
80 ms, 90 ms, 100 ms, ..., 160 ms 지점에 activity가 있었는지 기록
가장 늦게 activity가 남은 지점을 last_matched_width로 본다.
last_matched_width >= WIDE_WIDTH_TH이면 wide_qrs_spike
```

terminal delay neuron은 QRS 후반부를 본다.

```text
TERMINAL_START부터 TERMINAL_END 사이 activity 개수를 센다.
terminal activity count >= TERMINAL_COUNT_TH이면 terminal_delay_spike
```

RBBB-like beat neuron:

```text
wide_qrs_spike와 terminal_delay_spike가 동시에 만족되면
rbbb_like_beat_spike 발화
```

마지막으로 segment-level neuron이 있다.

```text
60초 동안 rbbb_like_beat_count가 repeat threshold 이상이고
rhythm irregularity 조건이 너무 높지 않으면
rbbb_segment_spike 발화
```

해석:

- `wide_qrs_spike`: QRS width가 넓다는 morphology 발화
- `terminal_delay_spike`: QRS 후반부 activity가 남는다는 발화
- `rbbb_like_beat_spike`: wide + terminal delay가 같이 나타난 beat
- `rbbb_segment_spike`: 이런 beat가 60초 안에서 반복되었다는 segment evidence

이 evidence는 Snapshot class membrane에서 NSR을 억제하거나 ARR/CHF/AFF 쪽 morphology evidence를 강화하는 자극으로 쓰일 수 있다.

주요 RTL 파일:

```text
rtl/core/rbbb_qrs_delay_bank.v
```

### 6.9 EERG Gate: 후보 탐색용 gate, V2 direct readout에서는 제거

EERG는 C24 탐색 과정에서 검토한 ARR-like rescue gate였다. 의도는 RBBB-like delay는 강하지 않지만, QRS 직전 bump, ectopic pair, 낮은 수준의 rhythm abnormality가 조합되어 ARR처럼 보이는 구간을 살리는 것이었다.

개념은 다음과 같았다.

```text
RBBB-like delay는 강하지 않다.
그런데 pre-QRS bump가 있다.
early/late 또는 ectopic pair evidence가 있다.
pNN/RDM irregularity가 특정 범위에 있다.
그러면 ARR rescue 자극을 줄 수 있다.
```

하지만 Snapshot Model V2에서는 이 EERG direct class-membrane contribution을 제거했다. 이유는 다음과 같다.

1. EERG가 일부 validation case에서는 도움이 되었지만, 최종 V2에서는 direct 자극 경로를 제거해도 test 성능이 유지되었다.
2. 직접 ARR boost 경로가 남아 있으면 feature 설명이 불필요하게 복잡해지고, 특정 edge case에 과도하게 의존하는 구조가 된다.
3. V2는 더 단순한 “feature spike -> class membrane” 경로를 유지하기 위해 EERG direct boost를 끈 모델로 확정했다.

따라서 보고서에서 EERG는 다음처럼 표현하는 것이 정확하다.

```text
EERG는 후보 탐색 중 검토한 episodic ARR rescue gate였지만,
Snapshot Model V2의 최종 class membrane 직접 자극 경로에서는 제거했다.
```

### 6.10 Class Score Neurons / C24 Folded Readout

위 feature neuron들이 만든 spike와 count는 마지막에 `class_score_neurons.v`로 들어간다. 이 블록은 NSR/CHF/ARR/AFF class neuron membrane 네 개를 유지한다.

중요한 점은 Python classifier를 RTL에 그대로 복사하지 않았다는 것이다. Python C24 global readout의 coefficient를 feature별 synaptic weight로 fold해서, RTL에서는 feature spike가 직접 class membrane에 자극을 주는 형태로 바꾸었다.

Python 관점에서는 다음처럼 보인다.

```text
score[class] += feature_count * coefficient[class]
score[class] += bias[class]
```

RTL/SNN-inspired 관점에서는 다음처럼 구현된다.

```text
segment 시작:
    class_mem[NSR] = folded_bias_NSR
    class_mem[CHF] = folded_bias_CHF
    class_mem[ARR] = folded_bias_ARR
    class_mem[AFF] = folded_bias_AFF

feature spike/count 발생:
    class_mem[NSR] += W_feature_to_NSR
    class_mem[CHF] += W_feature_to_CHF
    class_mem[ARR] += W_feature_to_ARR
    class_mem[AFF] += W_feature_to_AFF

60초 segment_done:
    pred_class = WTA(class_mem)
```

여기서 weight가 양수이면 해당 class neuron에 흥분성 자극을 주는 것이고, weight가 음수이면 억제성 자극을 주는 것이다.

예를 들면 다음과 같이 해석한다.

```text
pNN mismatch가 반복됨
-> rhythm irregularity evidence 발화
-> AFF 또는 ARR membrane에 흥분성 자극
-> NSR membrane에는 억제성 자극 가능

RBBB-like delay가 반복됨
-> conduction/morphology abnormal evidence 발화
-> ARR 계열 membrane 강화 또는 NSR membrane 억제
```

mean/std normalization, count scale, base scale, bias correction은 모두 integer folded weight와 integer bias에 흡수했다. RTL에는 floating point, divider, DSP multiplier 기반 matrix multiplication을 넣지 않았다. 최종 구조는 정수 counter, comparator, signed accumulator, WTA로 구현된다.

주요 RTL 파일:

```text
rtl/core/class_score_neurons.v
```

## 7. Snapshot 후보군 C01-C32와 V2 선택 과정

Snapshot C24를 선택하기 위해 C01-C32 후보군을 구성했다. 이는 feature 자체를 새로 만드는 탐색이 아니라, 같은 feature set 안에서 timing window, threshold, bank, gate, boost, readout parameter를 바꾸는 후보군이다.

탐색 원칙:

1. train/validation 기준으로 후보를 선택한다.
2. test set은 최종 후보 확정 후 1회 평가한다.
3. 정해진 train/validation/test split을 후보별로 동일하게 유지한다.
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
4. 30분 dataset은 class별 chunk 수를 균형화한 구조이며, 원천 record 수 제한 때문에 strict record-wise holdout으로 주장할 수 없다.
5. Snapshot V2의 ARR 일부가 NSR/CHF로 흡수되는 문제가 남아 있다.
6. Final Membrane V2 test ARR recall은 6/9로 남은 병목이다.
7. Vivado power는 추정값이며 실제 board-level power 측정은 아직 수행하지 않았다.

향후 개선:

1. 24시간 이상 annotation-rich ARR/AFF/NSR/CHF dataset 확보
2. class별 원천 record 수를 충분히 확보한 뒤 strict record-wise split 구성
3. Final Membrane에 class별 persistence/burst rule을 더 정교하게 추가
4. Snapshot stage별 Python-vs-RTL bit-exact 검증 강화
5. board-level timing/resource/power/throughput 통합 측정
6. clinical disease label과 rhythm annotation 차이를 분리한 evaluation protocol 작성

## 15. 최종 결론

SNN ECG V2는 30분 ECG stream을 60초 snapshot event들의 시간축 발화 패턴으로 해석하고, class neuron membrane에 흥분성/억제성 자극을 누적하여 최종 class를 판정하는 SNN-inspired hierarchical ECG classifier이다.

최종 성능:

```text
Snapshot Model V2 60초 test accuracy: 205/256 = 80.08%
SNN ECG V2 30분 chunk-level test accuracy: 32/36 = 88.89%
SNN ECG V2 30분 chunk-level test macro-F1: 88.46%
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
