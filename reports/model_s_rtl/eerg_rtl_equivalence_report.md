# EERG RTL Equivalence Report

## Purpose

This report compares the historical Python EERG post-readout result with the restored RTL-integrated EERG output.

## Summary

| split | total | pred mismatch | gate mismatch |
|---|---:|---:|---:|
| train | 400 | 2 | 19 |
| val | 160 | 0 | 6 |
| test | 160 | 0 | 0 |

## Interpretation

- Final prediction mismatches remain: 2.
- EERG gate booleans are not byte-equivalent because the historical Python path used offline annotation/pre-QRS statistics, while the restored RTL uses a streaming, synthesizable pre-QRS bump proxy and live counters. The final test predictions still match the documented Model S target exactly.
