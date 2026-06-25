# Final Decisions

## Adopted Final Model

The adopted model is Model S.

```text
Model S = Model A+ + EERG
Model A+ = Model A + RBBB QRS Delay Bank
```

## Adopted Features

- QRS LIF detector
- pNN125
- RDM
- DSCR
- RAM
- ECP
- QRS MAF
- RBBB QRS Delay Bank
- EERG readout gate

## Excluded From Final Claim

The following experimental branches are not part of the final performance claim:

- RCD/RCD2 attempts beyond the final RBBB QRS Delay Bank
- IPB
- ETMC
- PAC v2-style experimental gates
- pure decision tree classifier
- rate-threshold-bank classifier variant after it was replaced by direct spike membrane accumulation

They may remain in historical notes or compatibility stubs, but they are not active final Model S evidence.

## Final Performance Claim

The final classifier performance should be quoted as:

```text
strict record-wise XSim test:
segment accuracy = 131/160 = 81.88%
record accuracy = 18/19 = 94.74%
```

The FPGA implementation claim should be quoted separately:

```text
classifier core:
LUT = 8.37%
FF = 0.99%
BRAM = 0%
DSP = 0%
```

Board demo BRAM should not be described as classifier core memory usage because it stores ECG demo ROMs.

## Remaining Engineering Risk

The main remaining risk is AFE-filtered signal distribution shift. The final report should state that the AFE path is electrically compatible, but the classifier should be revalidated on AFE-equivalent filtered ECG before claiming full analog-front-end robustness.
