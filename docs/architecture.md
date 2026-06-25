# Architecture

## Input Interface

The digital core expects:

- `clk`
- `rst`
- `sample_valid`
- `rhythm_tick`
- `segment_start`
- `segment_done`
- `signed [11:0] adc_data`

The ECG stream is 1 kSPS, signed 12-bit, centered at zero.

## Event Encoder

The event encoder computes sample-to-sample delta and emits slope events:

- `strong_event`: large delta event used by QRS LIF
- `up_event`: positive slope event
- `down_event`: negative slope event
- `slope_valid`: slope event passed the threshold

## QRS LIF Detector

Strong events charge a QRS membrane. The membrane leaks each sample. When the membrane reaches the QRS threshold, a one-clock `beat_spike` is emitted. A refractory period prevents repeated firing inside one QRS complex.

## Feature Spike Layer

The final active feature set is:

- pNN125
- RDM
- DSCR
- RAM
- ECP
- QRS MAF
- RBBB QRS Delay Bank
- EERG readout gate

The feature values are not passed as floating-point scalar features. They are represented as spike events and fixed-weight membrane updates.

## Local and Segment Membranes

Model S uses two membrane layers:

```text
feature spikes
-> 60 s local class membrane
-> segment-level accumulated class membrane
-> readout correction
-> WTA
```

The 60-second local window reduces segment-length bias. If the final window is partial, its score is scaled before being committed to the segment membrane.

## WTA Readout

At `segment_done`, the final class scores are compared:

```text
pred_class = argmax(NSR_mem, CHF_mem, ARR_mem, AFF_mem)
```

This readout is hardware WTA using signed comparators, not softmax.
