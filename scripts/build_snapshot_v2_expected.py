from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
from pathlib import Path
from typing import Any

from snapshot_c24_v2_search import DATASET, OUT, eval_jobs, job_rows


EXPECTED_FIELDS = [
    "case_id",
    "split",
    "row_index",
    "segment_id",
    "record_id",
    "class_label",
    "class_id",
    "expected_pred_class",
    "expected_pred_label",
    "expected_correct",
    "expected_class_mem_NSR",
    "expected_class_mem_CHF",
    "expected_class_mem_ARR",
    "expected_class_mem_AFF",
    "eerg_applied_count",
    "eerg_gate_count",
    "eerg_pre_qrs_bump_count",
    "eerg_early_count",
    "eerg_ecp_count",
    "eerg_pnn_decision_count",
    "eerg_pnn_mismatch_count",
    "eerg_rdm_valid_count",
    "eerg_rdm_code_sum",
]


def expected_row(case_id: int, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "split": row["split"],
        "row_index": row["row_index"],
        "segment_id": row["segment_id"],
        "record_id": row["record_id"],
        "class_label": row["class_label"],
        "class_id": row["class_id"],
        "expected_pred_class": row["pred_class"],
        "expected_pred_label": row["pred_label"],
        "expected_correct": row["correct"],
        "expected_class_mem_NSR": row["class_mem_NSR"],
        "expected_class_mem_CHF": row["class_mem_CHF"],
        "expected_class_mem_ARR": row["class_mem_ARR"],
        "expected_class_mem_AFF": row["class_mem_AFF"],
        "eerg_applied_count": row.get("eerg_applied_count", 0),
        "eerg_gate_count": row.get("eerg_gate_count", 0),
        "eerg_pre_qrs_bump_count": row.get("eerg_pre_qrs_bump_count", 0),
        "eerg_early_count": row.get("eerg_early_count", 0),
        "eerg_ecp_count": row.get("eerg_ecp_count", 0),
        "eerg_pnn_decision_count": row.get("eerg_pnn_decision_count", 0),
        "eerg_pnn_mismatch_count": row.get("eerg_pnn_mismatch_count", 0),
        "eerg_rdm_valid_count": row.get("eerg_rdm_valid_count", 0),
        "eerg_rdm_code_sum": row.get("eerg_rdm_code_sum", 0),
    }


def write_expected(split: str, dataset: Path, out_dir: Path, workers: int, chunksize: int) -> Path:
    jobs = [dict(job, feature_off=("EERG",)) for job in job_rows([split], dataset)]
    rows = sorted(eval_jobs(jobs, workers=workers, chunksize=chunksize), key=lambda r: int(r["row_index"]))
    out_rows = [expected_row(case_id, row) for case_id, row in enumerate(rows)]
    path = out_dir / f"snapshot_v2_python_expected_{split}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPECTED_FIELDS)
        writer.writeheader()
        writer.writerows(out_rows)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Snapshot V2 Python expected CSVs.")
    parser.add_argument("--dataset-root", default=str(DATASET))
    parser.add_argument("--out-dir", default=str(OUT))
    parser.add_argument("--splits", nargs="+", default=["train", "val", "test"], choices=["train", "val", "test"])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--chunksize", type=int, default=4)
    args = parser.parse_args()

    dataset = Path(args.dataset_root)
    out_dir = Path(args.out_dir)
    for split in args.splits:
        path = write_expected(split, dataset, out_dir, args.workers, args.chunksize)
        print(f"{split}: wrote {path}", flush=True)


if __name__ == "__main__":
    mp.freeze_support()
    main()
