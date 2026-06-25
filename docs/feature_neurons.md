# Feature Neurons

## pNN125

pNN125 is an RR rhythm regularity feature. It uses 46 RR hypothesis neurons covering 250 ms to 2500 ms in 50 ms steps. The selected winner opens a prediction window. If the next beat arrives within ?125 ms, a match spike is generated. Otherwise a mismatch spike is generated.

Role: separates regular NSR/CHF-like rhythm from irregular ARR/AFF-like rhythm.

## RDM

RDM compares consecutive RR intervals:

```text
abs(RR_curr - RR_prev)
```

The difference is encoded with a 10 ms to 150 ms threshold bank. It reuses the RR interval already computed by the pNN path.

Role: rhythm variability evidence, especially ARR/AFF tendency.

## DSCR

DSCR encodes ECG slope direction changes. Up/down slope LIF neurons fire valid slope spikes, and a sign flip spike is emitted when the valid slope direction changes.

Role: morphology complexity evidence, mainly useful for CHF/NSR separation.

## RAM

RAM means R-peak Amplitude Mean-style evidence, not memory RAM. It observes R-peak amplitude around the predicted/observed beat window and encodes the peak with an amplitude threshold neuron bank.

Role: amplitude-pattern evidence, mainly supporting ARR/AFF and class balance.

## ECP

ECP detects short-long RR patterns that resemble ectopic beat plus compensatory pause. It uses an adaptive RR reference and emits an ectopic-pair spike when early/late behavior appears in sequence.

Role: auxiliary ARR evidence.

## QRS MAF

QRS MAF observes QRS morphology around each beat using pre-window and post-window activity. The final Model S path keeps three active morphology spikes:

- width abnormal spike
- energy abnormal spike
- complexity abnormal spike

Role: general morphology abnormal evidence.

## RBBB QRS Delay Bank

The RBBB bank targets regular-rhythm ARR cases where pNN/RDM can look NSR-like. It detects repeated wide QRS footprint and terminal activity delay.

Final selected setting:

- activity mode: low-slope abs-delta activity
- width threshold: 110
- terminal threshold: 3
- repeat threshold: 5
- low-irregularity gate: enabled
- readout: hybrid ARR boost / NSR inhibition

Role: rescue RBBB-heavy ARR segments from NSR misclassification.

## EERG

EERG is the Episodic Ectopic Rescue Gate. It is a readout-stage gate, not a new beat-level morphology detector.

Condition summary:

- no repeated RBBB-like evidence
- pre-QRS bump evidence exists
- early evidence or ECP evidence exists
- pNN mismatch rate is low
- RDM average code is low

If the gate fires, ARR score receives a fixed boost of +25000.

Role: rescue episodic ectopic/boundary ARR without damaging NSR/CHF/AFF.
