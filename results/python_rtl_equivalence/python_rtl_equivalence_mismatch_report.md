# Python vs RTL/XSim Equivalence Report

## Scope

- Snapshot C24 RTL parameters and Python final-layer parameters were kept fixed.
- The compared Python path is `scripts/snapshot_c24_rtl_exact.py`, which translates the RTL event/front-end, feature, RBBB/EERG gate, and C24 readout state machines directly.
- XSim used the current synthesizable RTL and a generated dump testbench that also exposes internal `dut.u_class.c24_mem_*` registers.
- The patient-level final layer is not implemented in RTL in the current repo, so stage D cannot be bit-exact compared yet.

## Summary

- compared windows: 211
- completely matching windows: 211
- pred_class mismatches: 0
- class_mem mismatching windows: 0

## First Mismatch Stage

| stage | windows |
|---|---:|
| PASS | 211 |

## Feature Mismatch Fields

| field | mismatches | compared | max abs diff |
|---|---:|---:|---:|
| none | 0 | 0 | 0 |

## Conclusion

The Python model is bit-exact with RTL for the compared Snapshot C24 windows.

Stage D remains unverified because there is no patient-level final-layer RTL module in this repo yet.
