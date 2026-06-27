# Model Snapshot Feature Neurons

이 문서는 최종 Model Snapshot에 남아 있는 feature만 설명한다. 최종 채택되지 않은 중간 feature 실험은 구조 설명에서 제외한다.

## 1. Adaptive QRS LIF

1. 입력 신호  
   AFE+ADC 이후의 1 kSPS signed 12-bit `adc_data` stream을 입력으로 사용한다. 내부적으로 `delta = adc_data[n] - adc_data[n-1]`, `abs_delta = |delta|`를 계산한다.

2. 핵심 목적  
   ECG stream에서 QRS event를 검출해 `beat_spike`를 생성한다. 이후 pNN125, RDM, RAM, ECP, QRS MAF, RBBB 계열 feature는 이 `beat_spike`를 기준으로 동작한다.

3. 내부 상태변수 또는 neuron/membrane 구조  
   초기 calibration 구간 동안 threshold bank별 event count를 세고, 선택된 `event_th`를 사용해 QRS LIF membrane을 갱신한다. QRS membrane은 strong slope event가 들어오면 증가하고, threshold를 넘으면 `beat_spike`를 발생시킨다.

4. spike 생성 조건  
   `up_event = delta >= +event_th`, `down_event = delta <= -event_th`, `strong_event = abs_delta >= event_th`로 정의한다. `strong_event`가 발생하면 `qrs_mem += QRS_W_EVENT`이고, `qrs_mem >= QRS_TH`이면 `beat_spike`가 발생한다.

5. class membrane에 주는 evidence 방향  
   Adaptive QRS LIF 자체가 특정 class를 직접 밀지는 않는다. 대신 모든 beat-based feature의 기준 timing을 제공한다.

6. 주요 파라미터  
   `ENABLE_ADAPTIVE=1`, `ADAPT_USE_BANK=1`, `ADAPT_CALIB_SAMPLES=2000`, `ADAPT_MIN_EVENT_TH=4`, `ADAPT_TARGET_EVENT_COUNT=100`, `ADAPT_PCT_TARGET=1900`, `QRS_W_EVENT=8`, `QRS_TH=16`, `QRS_LEAK=0`, `QRS_REF=280 ms`이다.

7. RTL 구현 관점의 특징  
   초기 2000 sample, 즉 2초 동안 `abs_delta`가 threshold bank를 얼마나 자주 넘는지 관찰한 뒤 target event count에 가까운 threshold를 선택한다. 선택 후에는 fixed threshold LIF처럼 동작하므로 회로는 counter, comparator, register 중심으로 구성된다.

Adaptive QRS LIF는 AFE+ADC stream의 amplitude/slope 분포 변화에 맞춰 event threshold를 선택하는 beat detector이다. 이 feature는 class 판단용 feature가 아니라 전체 Model Snapshot의 timing 기준을 제공하는 입력 event encoder이다.

## 2. pNN125

1. 입력 신호  
   `beat_spike`, 현재 RR interval, RR hypothesis bank 상태를 입력으로 사용한다.

2. 핵심 목적  
   RR interval regularity를 판단한다. 다음 QRS가 예측 window 안에 들어오는지 확인해 match/mismatch evidence를 만든다.

3. 내부 상태변수 또는 neuron/membrane 구조  
   250 ms부터 2500 ms까지 50 ms 간격의 RR hypothesis neuron bank를 둔다. 각 hypothesis는 다음 beat timing이 자기 window 안에 들어오는지 본다.

4. spike 생성 조건  
   `|RR_curr - expected_RR[k]| <= 125 ms`이면 match이고, 예측 window를 벗어나면 mismatch evidence로 본다.

5. class membrane에 주는 evidence 방향  
   mismatch가 높으면 ARR/AFF 쪽 rhythm irregularity evidence가 된다. mismatch가 낮으면 NSR/CHF 쪽 regular rhythm evidence로 해석한다.

6. 주요 파라미터  
   RR hypothesis range는 250~2500 ms, step은 50 ms, prediction window half는 125 ms이다.

7. RTL 구현 관점의 특징  
   곱셈 없이 counter와 comparator로 RR interval을 비교한다. pNN125는 class를 직접 결정하지 않고, match/mismatch spike를 class membrane readout에 제공한다.

pNN125는 RR rhythm이 규칙적인지 불규칙한지를 보는 핵심 timing feature이다. 특히 NSR/CHF group과 ARR/AFF group의 rhythm evidence를 나누는 데 사용된다.

## 3. RDM

1. 입력 신호  
   `beat_spike`, 현재 RR interval, 이전 RR interval을 입력으로 사용한다. RR 정보는 pNN 계열과 공유한다.

2. 핵심 목적  
   연속 RR interval 차이를 이용해 rhythm variability를 직접 판단한다.

3. 내부 상태변수 또는 neuron/membrane 구조  
   `RR_prev`, `RR_curr`, `rr_diff` register와 RR difference threshold bank를 사용한다.

4. spike 생성 조건  
   `rr_diff = |RR_curr - RR_prev|`를 계산하고, `10, 20, ..., 150 ms` threshold를 넘는 level마다 `rdm_level_spike`를 발생시킨다. RR 비교가 가능한 beat에서는 `rdm_valid_spike`가 발생한다.

5. class membrane에 주는 evidence 방향  
   높은 RDM은 ARR/AFF 쪽 rhythm variability evidence이다. 낮은 RDM은 NSR/CHF 쪽 regular rhythm evidence로 쓰인다.

6. 주요 파라미터  
   RR difference threshold bank는 10 ms부터 150 ms까지 10 ms 간격이다.

7. RTL 구현 관점의 특징  
   subtraction, absolute difference, comparator bank로 구현된다. division 없이 threshold crossing spike만 만든다.

RDM은 pNN125와 유사하게 rhythm irregularity를 보지만, 예측 window match가 아니라 실제 연속 RR 차이를 직접 본다. 따라서 pNN125와 함께 rhythm evidence를 보강한다.

## 4. DSCR

1. 입력 신호  
   raw `adc_data` stream의 slope sign, valid slope event, sign flip event를 입력으로 사용한다.

2. 핵심 목적  
   waveform slope sign-change 기반 morphology complexity를 측정한다. 주로 CHF와 NSR 분리에 기여한다.

3. 내부 상태변수 또는 neuron/membrane 구조  
   이전 slope sign, 현재 slope sign, valid slope count, sign flip count를 관리한다.

4. spike 생성 조건  
   유효 slope가 존재하고 slope sign이 바뀌면 `sign_flip_spike`를 발생시킨다. valid slope가 들어오는 경우에는 `valid_slope_spike`가 발생한다.

5. class membrane에 주는 evidence 방향  
   DSCR evidence는 주로 CHF/NSR 간 morphology complexity 차이를 반영한다. pNN/RDM처럼 ARR/AFF group을 강하게 나누는 feature로 쓰지 않는다.

6. 주요 파라미터  
   slope event threshold와 sign flip 판단 threshold를 사용한다. C24에서는 전체 feature-threshold 후보 탐색 안에서 DSCR threshold 축도 함께 검토했다.

7. RTL 구현 관점의 특징  
   raw stream에서 병렬로 동작하므로 QRS beat timing에 종속되지 않는다. signed delta와 sign comparison 중심으로 구현된다.

DSCR은 RR interval feature가 아니라 waveform morphology feature이다. Model Snapshot에서는 CHF와 NSR 분리에 쓰이는 보조적이지만 중요한 evidence block이다.

## 5. RAM

1. 입력 신호  
   `beat_spike`, R peak 주변 ADC amplitude, baseline 기준 amplitude response를 입력으로 사용한다.

2. 핵심 목적  
   R-peak amplitude response의 평균 수준을 class evidence로 사용한다. 여기서 RAM은 Random Access Memory가 아니라 R-peak Amplitude Mean 계열 feature이다.

3. 내부 상태변수 또는 neuron/membrane 구조  
   beat 주변 amplitude window, amplitude threshold bank, `ram_amp_code`, code accumulation/count를 사용한다.

4. spike 생성 조건  
   R peak 주변 amplitude가 threshold bank를 넘는 level에 따라 `ram_amp_code`가 생성된다. 이 code가 snapshot 동안 class evidence로 반영된다.

5. class membrane에 주는 evidence 방향  
   RAM은 ARR/AFF 분리와 CHF/NSR 보조 분리에 기여한다. 단일 feature로 class를 결정하지 않고 다른 rhythm/morphology evidence와 함께 쓰인다.

6. 주요 파라미터  
   amplitude threshold bank base/step과 code range가 핵심이다. C24 후보군에서는 RAM bank 조정도 함께 탐색했다.

7. RTL 구현 관점의 특징  
   amplitude를 직접 floating-point 평균으로 계산하지 않고, threshold bank code와 integer accumulation 형태로 처리한다.

RAM은 R peak amplitude의 절대/상대 response를 SNN-style code evidence로 변환한다. Model Snapshot에서는 rhythm feature가 놓치는 morphology/amplitude 차이를 보조한다.

## 6. ECP

1. 입력 신호  
   `beat_spike`, RR interval, previous/stable RR reference를 입력으로 사용한다.

2. 핵심 목적  
   ectopic-like timing pattern, 특히 early beat와 compensatory pause의 조합을 감지한다.

3. 내부 상태변수 또는 neuron/membrane 구조  
   early beat flag, late/compensatory pause flag, pending ectopic state, ECP count를 사용한다.

4. spike 생성 조건  
   beat가 예상보다 일찍 들어오면 early evidence가 생기고, 이후 긴 RR pause가 뒤따르면 compensatory evidence가 된다. 두 조건이 ectopic pair로 묶이면 ECP evidence가 발생한다.

5. class membrane에 주는 evidence 방향  
   ECP는 ARR 쪽 ectopic rhythm evidence로 쓰인다. NSR을 ARR로 과도하게 끌지 않도록 다른 rhythm/morphology gate와 함께 해석된다.

6. 주요 파라미터  
   early RR threshold, late RR threshold, ECP count threshold가 주요 조정 대상이다.

7. RTL 구현 관점의 특징  
   1-beat pending flag와 RR comparator로 구현 가능하다. 복잡한 template matching 없이 timing coincidence만 본다.

ECP는 ARR 중 ectopic timing 성격을 가진 snapshot을 보조하기 위한 feature이다. pNN/RDM이 segment 전체 irregularity를 보는 반면, ECP는 beat-pair timing pattern을 더 직접적으로 본다.

## 7. QRS MAF

1. 입력 신호  
   `adc_data`, `beat_spike`, QRS window activity, slope/energy/amplitude event를 입력으로 사용한다.

2. 핵심 목적  
   QRS Morphology Abnormal Feature로서 QRS 폭, slope complexity, energy/area, amplitude deviation 계열 abnormal evidence를 만든다.

3. 내부 상태변수 또는 neuron/membrane 구조  
   QRS observation window counter, width count, energy accumulation, slope transition count, abnormal flag를 사용한다.

4. spike 생성 조건  
   QRS width, energy, slope complexity, morphology deviation이 threshold를 넘으면 QRS MAF evidence spike가 발생한다.

5. class membrane에 주는 evidence 방향  
   QRS MAF는 ARR morphology abnormal evidence를 보조한다. 단독으로 ARR을 결정하기보다는 pNN/RDM/ECP/RBBB evidence와 함께 class membrane에 반영된다.

6. 주요 파라미터  
   QRS width threshold, complex threshold, energy deviation threshold, width deviation threshold가 주요 후보이다.

7. RTL 구현 관점의 특징  
   QRS window 안에서 counter와 comparator로 morphology abnormality를 평가한다. division이나 waveform template matching은 사용하지 않는다.

QRS MAF는 rhythm이 정상처럼 보이는 abnormal beat를 보조적으로 잡기 위한 morphology feature이다. 최종 구조에서는 ARR evidence를 보강하지만, 단독 feature로 과신하지 않는다.

## 8. RBBB QRS Delay Bank

1. 입력 신호  
   QRS activity event, low-slope event, terminal activity count, pNN high mismatch evidence를 입력으로 사용한다.

2. 핵심 목적  
   RR rhythm은 비교적 regular하지만 QRS conduction delay 성격이 반복되는 snapshot을 감지한다. 이는 RBBB-like conduction delay proxy feature이며 임상적 RBBB 진단 모듈이 아니다.

3. 내부 상태변수 또는 neuron/membrane 구조  
   wide QRS count, terminal activity count, repeated delay-like beat count, low-irregularity gate, segment-level RBBB delay evidence를 사용한다.

4. spike 생성 조건  
   low-slope 기반 activity가 충분하고, QRS width와 terminal activity가 threshold를 넘으며, 이 beat가 snapshot 안에서 반복되면 RBBB delay evidence가 발생한다.

5. class membrane에 주는 evidence 방향  
   RBBB delay evidence는 ARR membrane을 boost하고 NSR membrane을 inhibit한다. CHF/AFF 쪽 영향은 제한적으로 둔다.

6. 주요 파라미터  
   C24 최종값은 `RBBB_QRS_LOW_SLOPE_TH=5`, `RBBB_QRS_WIDE_TH=120`, `RBBB_QRS_TERMINAL_TH=4`, `RBBB_QRS_REPEAT_TH=5`, `W_RBBB_DELAY_NSR_INH=100000`, `W_RBBB_DELAY_ARR_BOOST=100000`이다.

7. RTL 구현 관점의 특징  
   `activity_mode = abs_delta_ge_low_slope` 방식으로 terminal activity를 잡고, `low_irregularity = not_high_pnn` gate를 사용한다. readout은 hybrid 방식으로 class membrane에 직접 보정 evidence를 넣는다.

RBBB QRS Delay Bank는 ARR이 NSR로 넘어가는 문제를 줄이기 위한 conduction-delay proxy feature이다. C24에서는 이전보다 엄격한 width/terminal 조건과 약화된 boost를 사용해 NSR 오염을 줄이는 방향으로 선택됐다.

## 9. EERG

1. 입력 신호  
   RBBB-like beat count, pre-QRS bump count, early count, ECP count, pNN mismatch rate, RDM average를 입력으로 사용한다.

2. 핵심 목적  
   RBBB delay evidence는 없지만 episodic ectopic 또는 boundary abnormal 성격을 보이는 ARR-like snapshot을 rescue한다.

3. 내부 상태변수 또는 neuron/membrane 구조  
   EERG condition flag와 applied count를 사용한다. 조건이 만족되면 segment-level gate로 ARR membrane에 boost를 넣는다.

4. spike 생성 조건  
   최종 rule은 `rbbb_like_beat_count == 0`, `pre_qrs_bump_count >= 1`, `early_count >= 10 OR ECP_count >= 3`, `pNN_mismatch_rate <= 0.15`, `RDM_avg <= 5`이다.

5. class membrane에 주는 evidence 방향  
   EERG가 활성화되면 `ARR_mem += 25000`을 적용한다. AFF inhibition은 사용하지 않는다.

6. 주요 파라미터  
   pre-QRS bump threshold, early count threshold, ECP count threshold, pNN mismatch rate upper bound, RDM average upper bound, ARR boost가 주요 파라미터이다.

7. RTL 구현 관점의 특징  
   EERG는 PAC-only detector가 아니라 episodic/boundary ectopic ARR rescue gate이다. 여러 counter 조건을 AND/OR gate로 묶고, 조건 만족 시 segment-level ARR boost를 넣는 구조이다.

EERG는 RBBB delay로 설명되지 않는 ARR-like snapshot을 보조적으로 구제하기 위한 readout gate이다. AFF처럼 지속적인 irregularity가 큰 경우가 아니라 low pNN/RDM irregularity 조건에서만 동작하도록 제한한다.

## 10. 4-Class Local Membrane / WTA Readout

1. 입력 신호  
   pNN125, RDM, DSCR, RAM, ECP, QRS MAF, RBBB, EERG에서 나온 feature evidence spike와 gate를 입력으로 받는다.

2. 핵심 목적  
   각 feature evidence를 NSR / CHF / ARR / AFF class neuron membrane에 누적하고, 60초 snapshot 끝에서 winner class를 선택한다.

3. 내부 상태변수 또는 neuron/membrane 구조  
   `class_mem[NSR]`, `class_mem[CHF]`, `class_mem[ARR]`, `class_mem[AFF]` signed integer membrane을 사용한다.

4. spike 생성 조건  
   WTA 자체가 spike generator라기보다 readout이다. snapshot 끝에서 가장 큰 class membrane을 가진 class가 `pred_class`로 선택된다.

5. class membrane에 주는 evidence 방향  
   각 feature가 class별 signed weight를 통해 membrane을 증가 또는 감소시킨다. WTA는 그 결과를 비교한다.

6. 주요 파라미터  
   class weight, class boost, base scale, count scale, RBBB/EERG boost, regularization이 주요 readout parameter이다.

7. RTL 구현 관점의 특징  
   signed add/subtract와 comparator로 구현된다. WTA는 STDP나 학습 회로가 아니라 고정 parameter classifier의 최종 readout이다.

4-class WTA는 Model Snapshot의 최종 class 경쟁 단계이다. 모든 feature evidence가 class membrane에 반영된 뒤, 60초 snapshot의 가장 강한 class evidence를 가진 class가 출력된다.
