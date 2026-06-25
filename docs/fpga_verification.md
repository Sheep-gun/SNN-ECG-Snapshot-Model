# FPGA Verification

## Verification Scope

Two hardware views are separated:

1. Model S classifier core resource usage
2. Nexys A7 board smoke wrapper resource usage

The core resource is the correct number for estimating the classifier IP size. The board wrapper resource includes buttons, 7-segment control, and four 60-second ECG ROMs.

## Core Synthesis

Vivado 2020.2, `xc7a100tcsg324-1`, top `snn_ecg_model_a_plus_core`.

| resource | used | available | utilization |
|---|---:|---:|---:|
| Slice LUTs | 5309 | 63400 | 8.37% |
| Slice Registers | 1250 | 126800 | 0.99% |
| BRAM Tile | 0 | 135 | 0.00% |
| DSP | 0 | 240 | 0.00% |

## Board Smoke Demo

Top module:

```text
nexys_a7_model_s_smoke_top
```

Interactive controls:

- `BTNU`: NSR example
- `BTNL`: ARR example
- `BTND`: CHF example
- `BTNR`: AFF example
- `BTNC`: pseudo-random example

The left 7-segment field displays the predicted class. The right field displays `CORR` or `ERR`.

## Board Implementation

- Device: Nexys A7-100T / `xc7a100tcsg324-1`
- Timing: met
- WNS: 4.242 ns
- TNS: 0 ns
- Estimated on-chip power: 0.104 W
- Junction temperature estimate: 25.5 C
- Power confidence: Low, so it should be treated as an estimate only

## Wrapper Resource

| resource | utilization |
|---|---:|
| LUT | 8.52% |
| FF | 1.09% |
| BRAM | 62.22% |
| DSP | 0.00% |

The BRAM is dominated by demo ECG ROM storage. It is not the core classifier BRAM cost.
