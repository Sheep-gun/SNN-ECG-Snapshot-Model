# Dataset Notes

This folder contains compact metadata and small demo samples only.

The full strict record-wise `.mem` dataset is intentionally not duplicated in this GitHub package. It is large generated data and should be stored separately or regenerated from the source ECG records.

Included:

- `record_wise_strict/record_split.json`
- train/validation/test manifest files
- final RTL result CSVs
- compact four-class AFE demo `.mem` samples

Evaluation policy:

- train: candidate exploration
- validation: final parameter selection
- test: final fixed Model S evaluation only
