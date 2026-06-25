# Analog and Mixed-Signal Integration

## AFE Model

The analog teammate's XModel AFE consists of:

```text
ECG differential input
-> high-pass filter
-> instrumentation amplifier
-> active Twin-T 60 Hz notch
-> low-pass filter
-> 12-bit 1 kSPS SAR ADC model
```

Reported AFE fidelity against 4-class demo ECG samples:

| class | source record | correlation | clipping |
|---|---|---:|---:|
| NSR | 16539 | 0.972 | 0 |
| ARR | 105 | 0.905 | 0 |
| AFF | 04015 | 0.940 | 0 |
| CHF | chf05 | 0.915 | 0 |

## Digital Interface Adapter

AFE SAR ADC output is offset-binary unsigned centered at 2048. Model S core expects signed two's-complement centered at zero.

Required conversion:

```verilog
assign adc_signed = {~adc_unsigned[11], adc_unsigned[10:0]};
```

The sample clock must also be converted into one-clock `sample_valid` and `rhythm_tick` pulses in the digital core clock domain.

## Mixed-Signal Finding

The AFE itself preserves ECG morphology without clipping. However, mixed-signal verification showed that standard ECG filtering can shift classifier evidence in weak ARR cases.

Observed issue:

- NSR/CHF/AFF mostly reproduce the digital-only result
- one ARR case flips toward AFF after AFE-equivalent filtering

Isolation with digital AFE-equivalent filters showed that this is a linear filtering distribution-shift issue, not an analog circuit bug.

## Final Interpretation

The analog front-end is not the failure point. The classifier should eventually be validated and, if necessary, retuned on AFE-filtered ECG data as well as raw `.mem` data.
