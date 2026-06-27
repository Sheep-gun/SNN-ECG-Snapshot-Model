# Model Snapshot Feature and Neuron Blocks

이 문서는 Model Snapshot을 구성하는 최종 feature와 readout block을 RTL/SNN 관점에서 정리한 것이다. 각 block은 scalar feature를 직접 계산해 software classifier에 넣는 구조가 아니라, ECG stream에서 event spike 또는 gate evidence를 만들고 class neuron membrane에 fixed signed weight로 누적하는 구조이다.

## 1. Adaptive QRS LIF

1. 입력 신호  
   AFE+ADC 이후의 1 kSPS signed 12-bit `adc_data` stream을 입력으로 사용한다. 내부에서는 `delta[n] = adc_data[n] - adc_data[n-1]`, `abs_delta[n] = |delta[n]|`를 계산한다.

2. 핵심 목적  
   ECG stream에서 QRS complex에 해당하는 강한 slope event를 검출하고, 이를 `beat_spike`로 변환한다. `beat_spike`는 pNN125, RDM, RAM, ECP, QRS MAF, RBBB 계열 feature의 공통 timing 기준이다.

3. 내부 상태/neuron 구조  
   초기 2000 sample 동안 threshold bank별 event count를 측정한다. 선택된 `event_th` 이후에는 QRS LIF membrane `qrs_mem`이 strong event에 의해 충전되고, threshold를 넘으면 spike를 발생시키는 방식으로 동작한다.

4. spike 생성 조건  
   `up_event = (delta >= +event_th)`, `down_event = (delta <= -event_th)`, `strong_event = (abs_delta >= event_th)`로 정의한다. `strong_event`가 발생하면 `qrs_mem += QRS_W_EVENT`이고, `qrs_mem >= QRS_TH`이면 `beat_spike = 1`이 된다.

5. class membrane evidence 방향  
   QRS LIF는 class membrane에 직접 evidence를 넣지 않는다. 대신 모든 beat-based feature가 같은 QRS timing을 공유하도록 하며, QRS 검출 안정성이 전체 feature 품질을 결정한다.

6. 주요 파라미터  
   `ENABLE_ADAPTIVE=1`, `ADAPT_USE_BANK=1`, `ADAPT_CALIB_SAMPLES=2000`, `ADAPT_MIN_EVENT_TH=4`, `ADAPT_TARGET_EVENT_COUNT=100`, `ADAPT_PCT_TARGET=1900`, `QRS_W_EVENT=8`, `QRS_TH=16`, `QRS_LEAK=0`, `QRS_REF=280 ms`이다.

7. RTL 구현 특징  
   threshold 선택은 bank counter와 comparator로 수행한다. QRS LIF 자체는 signed delta, absolute value, comparator, refractory counter, membrane register만으로 구성되며 floating point나 multiplier를 사용하지 않는다.

Adaptive QRS LIF는 AFE+ADC stream의 slope 분포에 맞춰 event threshold를 먼저 선택한 뒤, 선택된 threshold로 QRS event를 검출한다. Model Snapshot에서 가장 앞단의 event encoder이며, 이후 모든 rhythm/morphology feature의 기준 clock 역할을 한다.

## 2. pNN125

1. 입력 신호  
   `beat_spike`, 현재 RR interval counter, RR hypothesis neuron bank를 사용한다.

2. 핵심 목적  
   다음 beat가 예측 가능한 RR window 안에 들어오는지 판단해 rhythm regularity evidence를 만든다. 이는 NSR/CHF와 ARR/AFF group을 나누는 핵심 rhythm feature이다.

3. 내부 상태/neuron 구조  
   250 ms부터 2500 ms까지 50 ms 간격의 RR hypothesis neuron bank를 둔다. 각 hypothesis neuron은 자기 RR 주기 주변에 prediction window를 만들고, 다음 `beat_spike`가 그 안에 들어오는지 확인한다.

4. spike 생성 조건  
   `expected_rr[k] = 250 ms + 50 ms * k`이고, `|RR_curr - expected_rr[k]| <= 125 ms`이면 match로 본다. prediction window 밖에서 beat가 들어오거나 예측이 깨지면 mismatch evidence가 발생한다.

5. class membrane evidence 방향  
   mismatch evidence가 높으면 ARR/AFF 쪽 irregular rhythm evidence로 사용한다. match가 우세하거나 mismatch가 낮으면 NSR/CHF 쪽 regular rhythm evidence로 사용한다.

6. 주요 파라미터  
   RR hypothesis range는 `250-2500 ms`, step은 `50 ms`, window half는 `125 ms`이다. 최종 Model Snapshot에서는 pNN125를 기준 rhythm predictor로 유지한다.

7. RTL 구현 특징  
   RR counter와 comparator bank로 구현한다. 각 hypothesis는 독립 neuron처럼 동작하지만, 실제 회로는 counter/comparator 배열과 match/mismatch flag로 단순화된다.

pNN125는 beat-to-beat rhythm이 예측 가능한지를 판단하는 feature이다. Model Snapshot에서는 불규칙 rhythm evidence를 class membrane에 전달하되, 단독 class 결정기가 아니라 RDM, DSCR, RAM, ECP, morphology feature와 함께 사용된다.

## 3. RDM

1. 입력 신호  
   `beat_spike`, 현재 RR interval `RR_curr`, 이전 RR interval `RR_prev`를 입력으로 사용한다.

2. 핵심 목적  
   연속 RR interval의 변화량을 직접 측정한다. pNN125가 prediction window match를 본다면, RDM은 실제 `RR_curr`와 `RR_prev`의 차이를 threshold bank로 분해한다.

3. 내부 상태/neuron 구조  
   `RR_prev`, `RR_curr`, `rr_diff` register와 RR difference threshold bank를 사용한다. 각 threshold는 하나의 level neuron처럼 동작한다.

4. spike 생성 조건  
   `rr_diff = |RR_curr - RR_prev|`이다. `rr_diff`가 `10, 20, ..., 150 ms` threshold를 넘을 때 해당 `rdm_level_spike`가 발생한다. RR 비교가 가능한 beat에서는 `rdm_valid_spike`가 함께 발생한다.

5. class membrane evidence 방향  
   높은 RDM level은 ARR/AFF 쪽 rhythm variability evidence이다. 낮은 RDM 또는 valid 대비 low-level evidence는 NSR/CHF 쪽 regular rhythm evidence로 해석한다.

6. 주요 파라미터  
   `RDM_DIFF_TH0-14 = 10 ms, 20 ms, ..., 150 ms`이고 threshold 간격은 `10 ms`이다.

7. RTL 구현 특징  
   subtraction, absolute value, comparator bank만 사용한다. 평균값을 floating point로 계산하지 않고, threshold crossing spike count와 level evidence를 class membrane readout에 전달한다.

RDM은 pNN125와 역할이 비슷해 보일 수 있지만, prediction error가 아니라 연속 RR 변화량 자체를 본다. 두 rhythm feature를 함께 쓰면 irregularity를 window mismatch와 RR difference 두 방향에서 관찰할 수 있다.

## 4. DSCR

1. 입력 신호  
   raw `adc_data` stream의 sample-to-sample delta, slope sign, valid slope event를 입력으로 사용한다.

2. 핵심 목적  
   ECG waveform의 slope sign-change 비율을 이용해 morphology complexity를 측정한다. Model Snapshot에서는 주로 NSR과 CHF를 가르는 morphology evidence로 사용한다.

3. 내부 상태/neuron 구조  
   이전 slope sign, 현재 slope sign, `valid_slope_count`, `sign_flip_count`를 유지한다. sign이 바뀌는 순간을 DSCR event로 본다.

4. spike 생성 조건  
   slope magnitude가 threshold를 넘으면 `valid_slope_spike`가 발생한다. 이때 이전 slope sign과 현재 slope sign이 다르면 `sign_flip_spike`가 발생한다.

5. class membrane evidence 방향  
   DSCR evidence는 rhythm irregularity보다는 waveform complexity에 해당한다. 따라서 pNN/RDM처럼 ARR/AFF group을 직접 밀기보다 NSR/CHF 분리에 중심적으로 사용한다.

6. 주요 파라미터  
   slope threshold와 sign flip threshold가 핵심이다. C24 후보군에서는 DSCR slope threshold를 민감하게 또는 엄격하게 바꾸는 후보를 비교했다.

7. RTL 구현 특징  
   QRS 이후 window에만 종속되지 않고 `adc_data` stream에서 병렬로 동작한다. signed delta, sign bit, comparator, counter로 구현된다.

DSCR은 RR interval이 아니라 ECG 파형의 복잡도를 보는 feature이다. Model Snapshot에서는 CHF/NSR 분리용 morphology evidence로 유지되며, rhythm feature와 독립적인 정보를 제공한다.

## 5. RAM

1. 입력 신호  
   `beat_spike`, R peak 주변 ADC amplitude, baseline 기준 R-wave amplitude response를 입력으로 사용한다.

2. 핵심 목적  
   R-peak amplitude mean 계열 evidence를 만든다. 여기서 RAM은 Random Access Memory가 아니라 R-peak Amplitude Mean feature를 의미한다.

3. 내부 상태/neuron 구조  
   beat 주변 amplitude observation window, amplitude threshold bank, `ram_amp_code`, code sum/count register를 사용한다.

4. spike 생성 조건  
   R peak 주변 amplitude가 threshold bank의 각 level을 넘으면 amplitude code가 생성된다. `ram_amp_code`는 beat 단위로 발생하며 snapshot 동안 누적된다.

5. class membrane evidence 방향  
   RAM은 ARR/AFF 분리와 CHF/NSR 보조 분리에 사용한다. 특정 class를 단독으로 결정하기보다 rhythm feature가 만든 group evidence를 amplitude evidence로 보정한다.

6. 주요 파라미터  
   RAM bank base, step, code range가 핵심이다. C24 탐색에서는 low/mid amplitude 영역을 더 조밀하게 보는 후보와 high amplitude 쪽으로 bank를 이동하는 후보를 비교했다.

7. RTL 구현 특징  
   실제 평균을 division으로 계산하지 않는다. amplitude threshold bank로 code를 만들고, integer sum/count 및 gate feature로 readout에 반영한다.

RAM은 R peak amplitude response를 SNN-style code로 변환하는 feature이다. ECG record 간 gain 차이와 morphology 차이에 민감하므로 단독 판단보다 다른 feature와 함께 쓰는 것이 중요하다.

## 6. ECP

1. 입력 신호  
   `beat_spike`, 현재 RR interval, 이전 또는 기준 RR interval, pNN/RDM rhythm evidence를 사용한다.

2. 핵심 목적  
   ectopic beat에서 나타날 수 있는 early beat와 compensatory pause의 timing pattern을 감지한다.

3. 내부 상태/neuron 구조  
   `early_spike`, `late_spike`, `ectopic_pending`, `compensation_spike`, `ecp_count`를 사용한다. early beat가 감지되면 pending state를 두고 다음 RR에서 pause 여부를 확인한다.

4. spike 생성 조건  
   `RR_curr < RR_ref - T_EARLY`이면 early evidence로 본다. 이후 `RR_next > RR_ref + T_LATE`이면 compensatory evidence로 보고 ECP event를 만든다.

5. class membrane evidence 방향  
   ECP는 ARR 쪽 ectopic rhythm evidence로 사용한다. 다만 NSR 오염을 막기 위해 pNN/RDM, QRS morphology, EERG gate와 함께 readout에서 해석한다.

6. 주요 파라미터  
   `T_EARLY`, `T_LATE`, ECP count threshold가 핵심이다. C24 후보군에서는 pNN window와 ECP timing threshold를 함께 조정했다.

7. RTL 구현 특징  
   beat-to-beat RR comparator와 1-beat pending flag로 구현한다. 복잡한 template matching 없이 timing coincidence만 사용한다.

ECP는 ectopic-like RR timing을 spike event로 바꾸는 feature이다. ARR을 rhythm irregularity 하나로만 보지 않고, beat pair 단위의 abnormal timing pattern을 class evidence로 추가한다.

## 7. QRS MAF

1. 입력 신호  
   `adc_data`, `beat_spike`, QRS window activity, slope event, energy/area accumulator, amplitude deviation signal을 사용한다.

2. 핵심 목적  
   QRS morphology abnormality를 감지한다. rhythm은 정상처럼 보여도 QRS width, energy, slope complexity가 비정상적인 snapshot을 보조적으로 잡기 위한 feature이다.

3. 내부 상태/neuron 구조  
   QRS observation window counter, width counter, slope complexity counter, energy accumulator, abnormal flag를 사용한다.

4. spike 생성 조건  
   QRS width가 threshold 이상이거나, slope transition이 많거나, QRS energy/area가 기준 이상이면 QRS MAF evidence가 발생한다.

5. class membrane evidence 방향  
   QRS MAF는 morphology abnormal evidence로 ARR 쪽 보조 신호를 제공한다. 동시에 CHF/NSR 분리에서 RAM/DSCR과 함께 보조 evidence로 쓰일 수 있다.

6. 주요 파라미터  
   `QrsMafWidthTh`, `QrsMafComplexTh`, `QrsMafEnergyDevTh`, `QrsMafWidthDevTh`가 핵심이다. C17-C20 후보에서 민감도와 rhythm 조합을 비교했다.

7. RTL 구현 특징  
   beat-centered window 안에서 counter와 comparator로 동작한다. waveform template이나 convolution 없이 width, event count, energy level을 threshold로 판단한다.

QRS MAF는 QRS morphology abnormality를 직접 class evidence로 바꾸는 feature이다. Model Snapshot에서는 rhythm feature만으로 설명되지 않는 abnormal beat를 보조적으로 잡기 위해 유지한다.

## 8. RBBB QRS Delay Bank

1. 입력 신호  
   QRS activity event, `abs_delta`, low-slope event, terminal activity count, pNN high mismatch evidence를 사용한다.

2. 핵심 목적  
   RR rhythm은 비교적 regular하지만 QRS conduction delay 성격이 반복되는 snapshot을 감지한다. 이는 RBBB-like conduction delay proxy이며 임상적 RBBB 진단 모듈은 아니다.

3. 내부 상태/neuron 구조  
   low-slope activity detector, wide QRS counter, terminal activity counter, repeated delay-like beat counter, low-irregularity gate를 사용한다.

4. spike 생성 조건  
   `abs_delta >= RBBB_QRS_LOW_SLOPE_TH`인 activity가 QRS window 안에서 지속되고, `width_count >= RBBB_QRS_WIDE_TH`, `terminal_count >= RBBB_QRS_TERMINAL_TH` 조건을 만족하는 beat가 `RBBB_QRS_REPEAT_TH` 이상 반복되면 RBBB delay evidence가 발생한다.

5. class membrane evidence 방향  
   RBBB delay evidence는 ARR membrane을 boost하고 NSR membrane을 inhibit한다. 목적은 regular rhythm처럼 보이는 conduction-delay snapshot이 NSR로 흡수되는 것을 줄이는 것이다.

6. 주요 파라미터  
   C24 최종값은 `RBBB_QRS_LOW_SLOPE_TH=5`, `RBBB_QRS_WIDE_TH=120`, `RBBB_QRS_TERMINAL_TH=4`, `RBBB_QRS_REPEAT_TH=5`, `W_RBBB_DELAY_NSR_INH=100000`, `W_RBBB_DELAY_ARR_BOOST=100000`이다.

7. RTL 구현 특징  
   activity mode는 `abs_delta_ge_low_slope`이고, low-irregularity gate는 `not_high_pnn` 기준으로 둔다. readout은 hybrid 방식으로 class membrane에 boost/inhibition을 직접 반영한다.

RBBB QRS Delay Bank는 Model Snapshot에서 regular-looking ARR 계열을 보조하기 위한 핵심 morphology-timing feature이다. C24에서는 조건을 엄격하게 두고 boost를 제한해 ARR 보정과 NSR 오염 사이의 균형을 맞췄다.

## 9. EERG

1. 입력 신호  
   `rbbb_like_beat_count`, `pre_qrs_bump_count`, `early_count`, `ECP_count`, pNN mismatch rate, RDM average를 사용한다.

2. 핵심 목적  
   RBBB delay evidence는 없지만 episodic ectopic 또는 boundary abnormal 성격을 보이는 ARR-like snapshot을 rescue한다.

3. 내부 상태/neuron 구조  
   EERG condition flag와 applied count를 사용한다. 조건이 만족되면 segment-level gate가 열리고 ARR membrane에 boost를 넣는다.

4. spike 생성 조건  
   최종 rule은 `rbbb_like_beat_count == 0`, `pre_qrs_bump_count >= 1`, `early_count >= 10 OR ECP_count >= 3`, `pNN_mismatch_rate <= 0.15`, `RDM_avg <= 5`이다.

5. class membrane evidence 방향  
   EERG가 활성화되면 `ARR_mem += 25000`을 적용한다. AFF inhibition은 사용하지 않는다.

6. 주요 파라미터  
   pre-QRS bump threshold, early count threshold, ECP count threshold, pNN mismatch upper bound, RDM average upper bound, ARR boost가 주요 파라미터이다.

7. RTL 구현 특징  
   여러 counter 조건을 AND/OR gate로 묶는 readout gate이다. PAC-only detector가 아니라 episodic/boundary ectopic ARR rescue gate로 해석한다.

EERG는 RBBB feature로 설명되지 않는 ARR-like snapshot을 보조적으로 구제하는 gate이다. 지속적인 AFF-like irregularity가 아니라 low pNN/RDM irregularity 조건에서만 ARR boost를 허용한다.

## 10. 4-Class Local Membrane / WTA Readout

1. 입력 신호  
   pNN125, RDM, DSCR, RAM, ECP, QRS MAF, RBBB, EERG에서 나온 feature evidence spike, count, gate를 입력으로 받는다.

2. 핵심 목적  
   모든 feature evidence를 NSR / CHF / ARR / AFF class neuron membrane에 통합하고, 60초 snapshot 끝에서 최종 class를 선택한다.

3. 내부 상태/neuron 구조  
   `class_mem[NSR]`, `class_mem[CHF]`, `class_mem[ARR]`, `class_mem[AFF]` signed integer membrane을 사용한다. 각 membrane은 feature evidence가 들어올 때마다 fixed signed weight로 갱신된다.

4. spike 생성 조건  
   WTA 자체는 feature spike generator가 아니라 readout이다. snapshot 종료 시점에 가장 큰 membrane을 가진 class가 `pred_class`가 된다.

5. class membrane evidence 방향  
   각 feature는 class별로 양 또는 음의 evidence를 줄 수 있다. 예를 들어 rhythm irregularity는 ARR/AFF 쪽으로, DSCR/RAM morphology evidence는 NSR/CHF 또는 ARR/AFF 세부 분리에 사용된다.

6. 주요 파라미터  
   class weight, class boost, count scale, base scale, RBBB boost/inhibition, EERG boost, regularization이 주요 readout parameter이다. C24에서는 `count_scale=10.0`, `base_scale=25000.0`, class boost `NSR=1.1`, `CHF=1.8`, `ARR=1.8`, `AFF=1.0`을 사용한다.

7. RTL 구현 특징  
   signed add/subtract와 comparator로 구성된다. WTA는 STDP나 backpropagation 학습 회로가 아니라, train/validation 기반으로 고정된 parameter를 읽어내는 class competition 회로이다.

4-class WTA는 Model Snapshot의 최종 class 경쟁 단계이다. 모든 feature evidence가 60초 동안 class membrane에 누적된 뒤, 가장 강한 class evidence를 가진 membrane이 최종 prediction으로 선택된다.
