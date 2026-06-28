from __future__ import annotations

import argparse
import csv
from pathlib import Path

from fullrec_patient_membrane_layer import CLASS_TO_ID, write_csv
from verify_python_rtl_equivalence import (
    REPO,
    compare_outputs,
    python_dump,
    run_xsim,
    write_xsim_inputs,
)


DATASET = REPO / "datasets" / "afe_output_xmodelmatch_curated_v2_50_25_25"
RESULTS = REPO / "results" / "snapshot_c24_curated_equivalence"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_curated_selection() -> list[dict[str, str]]:
    selection: list[dict[str, str]] = []
    case_id = 0
    for split in ["train", "val", "test"]:
        manifest = DATASET / f"afe_manifest_{split}.csv"
        for row in read_csv(manifest):
            label = row["class_label"]
            mem_path = DATASET / "signed" / split / Path(row["afe_adc_signed_file"]).name
            if not mem_path.exists():
                raise FileNotFoundError(mem_path)
            selection.append(
                {
                    "case_id": str(case_id),
                    "split": split,
                    "record_id": row["record_id"],
                    "window_id": row["segment_id"],
                    "true_record_class": label,
                    "true_class_id": row.get("class_id", str(CLASS_TO_ID[label])),
                    "selection_tags": "curated_afe_adc_60s_all",
                    "window_mem_file": str(mem_path),
                    "source_split": row.get("source_split", ""),
                    "source_segment_id": row.get("source_segment_id", ""),
                    "start_time_s": row.get("start_time_s", ""),
                }
            )
            case_id += 1
    return selection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-xsim", action="store_true")
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    selection_path = RESULTS / "selected_windows.csv"
    if args.skip_xsim and selection_path.exists():
        selection = read_csv(selection_path)
    else:
        selection = load_curated_selection()
        write_csv(selection_path, selection)

    work, tb, wrapper = write_xsim_inputs(selection, RESULTS)
    if not args.skip_xsim:
        run_xsim(work, tb, wrapper, RESULTS)

    py_rows = python_dump(selection, RESULTS)
    if (RESULTS / "rtl_xsim_window_dump.csv").exists():
        compare_outputs(selection, py_rows, RESULTS)

    print(f"[done] curated Snapshot C24 equivalence windows={len(selection)} -> {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
