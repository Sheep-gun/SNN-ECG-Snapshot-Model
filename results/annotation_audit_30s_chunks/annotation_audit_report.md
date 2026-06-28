# 30-second chunk annotation audit

Inputs:
- Chunk manifest: `C:\Users\YangGeon\SNN_ECG_RESTORE_MODEL_S\fullrec_afe_30s_balanced_chunks\balanced_chunk_manifest.csv`
- Source annotations: `C:\Users\YangGeon\Desktop\작업물\학업\한양대학교 문서\스펙\대회 관련\2026 전국 반도체 설계대전\ECG Data Real`

Validation rules:
- NSR: low abnormal-beat contamination.
- ARR: at least 2 abnormal beats or abnormal-beat ratio >= 5%, excluding AFIB/AFL-dominant chunks.
- AFF: AFIB/AFL rhythm overlap >= 80%.
- CHF: record-level CHF label retained; audit checks beat count and AFIB/AFL contamination only.

Total chunks: 13268
Valid chunks: 7704
Excluded/ambiguous chunks: 5564

| Class | Valid | Excluded |
|---|---:|---:|
| AFF | 539 | 2778 |
| ARR | 1535 | 1782 |
| CHF | 2839 | 478 |
| NSR | 2791 | 526 |

Important caveat:
CHF is not directly provable from beat/rhythm annotation. CHF-valid means clean-enough chunk from a CHF-labeled record, not a direct CHF morphology proof.

Outputs:
- `chunk_annotation_audit.csv`
- `chunk_annotation_valid_manifest.csv`
- `chunk_annotation_excluded_manifest.csv`
- `annotation_audit_summary.csv`