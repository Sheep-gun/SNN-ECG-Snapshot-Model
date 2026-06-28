from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import final_membrane_30min_recordwise_pipeline as rw  # noqa: E402
import search_final_membrane_30min_recordwise_recordlevel as recordlevel  # noqa: E402


RESULTS = rw.RESULTS
CLASSES = rw.CLASSES

SEARCH_CSV = RESULTS / "no_oracle_record_level_strict_search.csv"
SELECTED_JSON = RESULTS / "no_oracle_record_level_strict_selected_params.json"
REPORT_MD = RESULTS / "no_oracle_record_level_strict_report.md"

TRAIN_ACC_FLOOR = 0.80
VAL_ACC_FLOOR = 0.80
TEST_CORRECT_TARGET = 29


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def selection_key(train_metrics: dict, val_metrics: dict, candidate: dict) -> tuple:
    # All candidates reaching this function already pass train/val accuracy floors.
    # Prefer balanced validation behavior, then a stable train/val floor, then simplicity.
    return (
        val_metrics["macro_f1"],
        val_metrics["balanced_accuracy"],
        -val_metrics["recall_range"],
        min(train_metrics["macro_f1"], val_metrics["macro_f1"]),
        train_metrics["accuracy"],
        val_metrics["accuracy"],
        -candidate["complexity"],
    )


def prediction_rows(rows: list[dict], pred: np.ndarray) -> list[dict]:
    out = []
    for row, p in zip(rows, pred.tolist()):
        out.append(
            {
                "case_id": row["case_id"],
                "split": row["split"],
                "class_label": row["class_label"],
                "class_id": row["class_id"],
                "record_id": row["record_id"],
                "chunk_id": row["chunk_id"],
                "chunk_file": row["chunk_file"],
                "final_pred_class": p,
                "final_pred_label": CLASSES[p],
                "correct": int(p == row["class_id"]),
            }
        )
    return out


def run_search() -> None:
    rows = recordlevel.load_chunk_rows()
    table = recordlevel.build_record_table(rows)
    records = table["records"]
    chunk_to_record = table["chunk_to_record"]

    search_rows = []
    eligible_count = 0
    selected = None
    selected_key = None
    selected_chunk_pred = None

    # Search/election phase: test metrics are not computed in this loop.
    for candidate in recordlevel.candidate_grid():
        _, chunk_pred = recordlevel.apply_candidate(records, chunk_to_record, candidate)
        train_metrics = recordlevel.metrics_for_chunk_pred(rows, chunk_pred, "train")
        val_metrics = recordlevel.metrics_for_chunk_pred(rows, chunk_pred, "val")
        eligible = train_metrics["accuracy"] >= TRAIN_ACC_FLOOR and val_metrics["accuracy"] >= VAL_ACC_FLOOR
        if eligible:
            eligible_count += 1
        search_rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "kind": candidate["kind"],
                "eligible": int(eligible),
                "params": json.dumps(candidate["params"], sort_keys=True),
                "tie_order": "|".join(str(x) for x in candidate["tie_order"]),
                "complexity": candidate["complexity"],
                "train_accuracy": train_metrics["accuracy"],
                "train_correct": train_metrics["correct"],
                "train_total": train_metrics["total"],
                "train_macro_f1": train_metrics["macro_f1"],
                "val_accuracy": val_metrics["accuracy"],
                "val_correct": val_metrics["correct"],
                "val_total": val_metrics["total"],
                "val_macro_f1": val_metrics["macro_f1"],
                "val_balanced_accuracy": val_metrics["balanced_accuracy"],
                "val_recall_range": val_metrics["recall_range"],
                "val_arr_recall": val_metrics["per_class"]["ARR"]["recall"],
            }
        )
        if not eligible:
            continue
        key = selection_key(train_metrics, val_metrics, candidate)
        if selected_key is None or key > selected_key:
            selected_key = key
            selected = {"candidate": candidate, "train": train_metrics, "val": val_metrics}
            selected_chunk_pred = chunk_pred

    write_csv(SEARCH_CSV, search_rows)
    if selected is None or selected_chunk_pred is None:
        raise RuntimeError("no candidate passed strict train/validation floors")

    # Final verification phase: test is evaluated once after selection.
    test_metrics = recordlevel.metrics_for_chunk_pred(rows, selected_chunk_pred, "test")
    selected["test"] = test_metrics
    selected["constraints"] = {
        "train_accuracy_floor": TRAIN_ACC_FLOOR,
        "val_accuracy_floor": VAL_ACC_FLOOR,
        "test_correct_target": TEST_CORRECT_TARGET,
        "eligible_candidate_count": eligible_count,
    }
    selected["note"] = (
        "No-oracle strict record-level search. Candidate search and selection used only train/validation metrics, "
        "with train and validation accuracy floors. Test metrics were computed once after validation selection."
    )
    SELECTED_JSON.write_text(json.dumps(selected, indent=2), encoding="utf-8")

    pred_rows = prediction_rows(rows, selected_chunk_pred)
    for split in rw.SPLITS:
        split_metrics = recordlevel.metrics_for_chunk_pred(rows, selected_chunk_pred, split)
        (RESULTS / f"no_oracle_record_level_strict_{split}_metrics.json").write_text(json.dumps(split_metrics, indent=2), encoding="utf-8")
        write_csv(RESULTS / f"no_oracle_record_level_strict_{split}_predictions.csv", [row for row in pred_rows if row["split"] == split])

    success = (
        selected["train"]["accuracy"] >= TRAIN_ACC_FLOOR
        and selected["val"]["accuracy"] >= VAL_ACC_FLOOR
        and test_metrics["correct"] >= TEST_CORRECT_TARGET
    )
    report = [
        "# No-Oracle Strict Record-Level Final Membrane Search",
        "",
        "Search and selection used only train/validation metrics. Test was evaluated once after the strict validation-selected candidate was fixed.",
        "",
        "## Constraints",
        "",
        f"- train accuracy >= {TRAIN_ACC_FLOOR*100:.0f}%",
        f"- validation accuracy >= {VAL_ACC_FLOOR*100:.0f}%",
        f"- test correct >= {TEST_CORRECT_TARGET}/36",
        f"- eligible candidates: {eligible_count}",
        "",
        "## Selected Candidate",
        "",
        f"- candidate_id: {selected['candidate']['candidate_id']}",
        f"- kind: {selected['candidate']['kind']}",
        f"- params: `{json.dumps(selected['candidate']['params'], sort_keys=True)}`",
        f"- tie_order: `{tuple(selected['candidate']['tie_order'])}`",
        "",
        "## Metrics",
        "",
        f"- train: {selected['train']['correct']}/{selected['train']['total']} = {selected['train']['accuracy']*100:.2f}%, macro-F1 {selected['train']['macro_f1']*100:.2f}%",
        f"- val: {selected['val']['correct']}/{selected['val']['total']} = {selected['val']['accuracy']*100:.2f}%, macro-F1 {selected['val']['macro_f1']*100:.2f}%",
        f"- test: {test_metrics['correct']}/{test_metrics['total']} = {test_metrics['accuracy']*100:.2f}%, macro-F1 {test_metrics['macro_f1']*100:.2f}%",
        f"- success: {success}",
        "",
        "## Test Confusion Matrix",
        "",
        "Rows=true, columns=pred, class order NSR/CHF/ARR/AFF.",
        "",
        "```text",
        json.dumps(test_metrics["confusion_matrix"]),
        "```",
    ]
    REPORT_MD.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(
        f"[strict-selected] id={selected['candidate']['candidate_id']} kind={selected['candidate']['kind']} "
        f"train={selected['train']['correct']}/{selected['train']['total']} "
        f"val={selected['val']['correct']}/{selected['val']['total']} "
        f"test={test_metrics['correct']}/{test_metrics['total']} "
        f"success={success}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    run_search()


if __name__ == "__main__":
    main()
