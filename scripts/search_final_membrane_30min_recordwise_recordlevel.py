from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import final_membrane_30min_recordwise_pipeline as rw  # noqa: E402
import search_final_membrane_30min_recordwise as chunk_search  # noqa: E402


RESULTS = rw.RESULTS
CLASSES = rw.CLASSES

SEARCH_CSV = RESULTS / "no_oracle_record_level_search.csv"
SELECTED_JSON = RESULTS / "no_oracle_record_level_selected_params.json"
REPORT_MD = RESULTS / "no_oracle_record_level_report.md"

EVIDENCE_FIELDS = [
    "abnormal_evidence_count",
    "rhythm_irregular_evidence_count",
    "morphology_evidence_count",
    "qrs_maf_count",
    "ectopic_pair_count",
    "rbbb_delay_like_count",
    "eerg_ecp_count",
    "pnn_mismatch_count",
    "rdm_ge50_count",
]


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


def load_chunk_rows() -> list[dict]:
    chunks = chunk_search.load_chunks()
    rows = []
    for split in rw.SPLITS:
        for chunk in chunks[split]:
            pred_count = np.zeros(4, dtype=np.int64)
            mem_sum = np.zeros(4, dtype=np.int64)
            evidence = {field: 0 for field in EVIDENCE_FIELDS}
            for snap in chunk["snapshots"]:
                pred_count[rw.safe_int(snap["snapshot_pred_class"])] += 1
                for idx, cls in enumerate(CLASSES):
                    mem_sum[idx] += rw.safe_int(snap[f"class_mem_{cls}"])
                for field in EVIDENCE_FIELDS:
                    evidence[field] += rw.safe_int(snap.get(field, 0))
            rows.append(
                {
                    "case_id": int(chunk["case_id"]),
                    "split": split,
                    "class_label": chunk["class_label"],
                    "class_id": int(chunk["class_id"]),
                    "record_id": chunk["record_id"],
                    "chunk_id": chunk["chunk_id"],
                    "chunk_file": chunk["chunk_file"],
                    "pred_count": pred_count,
                    "mem_sum": mem_sum,
                    "evidence": evidence,
                }
            )
    return rows


def build_record_table(rows: list[dict]) -> dict:
    record_map: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        record_map[(row["split"], row["class_label"], row["record_id"])].append(idx)

    records = []
    chunk_to_record = np.zeros(len(rows), dtype=np.int64)
    for rec_idx, (key, chunk_indices) in enumerate(sorted(record_map.items())):
        split, class_label, record_id = key
        pred_count = np.zeros(4, dtype=np.int64)
        mem_sum = np.zeros(4, dtype=np.int64)
        evidence = {field: 0 for field in EVIDENCE_FIELDS}
        for chunk_idx in chunk_indices:
            chunk_to_record[chunk_idx] = rec_idx
            pred_count += rows[chunk_idx]["pred_count"]
            mem_sum += rows[chunk_idx]["mem_sum"]
            for field in EVIDENCE_FIELDS:
                evidence[field] += rows[chunk_idx]["evidence"][field]
        records.append(
            {
                "record_index": rec_idx,
                "split": split,
                "class_label": class_label,
                "class_id": int(rows[chunk_indices[0]]["class_id"]),
                "record_id": record_id,
                "chunk_indices": chunk_indices,
                "pred_count": pred_count,
                "mem_sum": mem_sum,
                "evidence": evidence,
            }
        )
    return {"records": records, "chunk_to_record": chunk_to_record}


def metrics_for_chunk_pred(rows: list[dict], pred: np.ndarray, split: str) -> dict:
    mask = np.array([row["split"] == split for row in rows], dtype=bool)
    y_true = np.array([row["class_id"] for row in rows], dtype=np.int64)
    return rw.metrics_from_pred(y_true[mask], pred[mask].astype(np.int64))


def record_score_to_pred(score: np.ndarray, tie_order: tuple[int, int, int, int]) -> np.ndarray:
    adjusted = score.astype(np.float64).copy()
    for rank, cls in enumerate(tie_order):
        adjusted[:, cls] += (4 - rank) * 1e-6
    return np.argmax(adjusted, axis=1).astype(np.int64)


def apply_candidate(records: list[dict], chunk_to_record: np.ndarray, candidate: dict) -> tuple[np.ndarray, np.ndarray]:
    record_count = len(records)
    score = np.zeros((record_count, 4), dtype=np.float64)
    kind = candidate["kind"]
    if kind in {"record_snapshot_count", "record_arr_rescue", "record_aff_rescue"}:
        for idx, record in enumerate(records):
            score[idx] = record["pred_count"].astype(np.float64)
    elif kind == "record_mem_sum":
        for idx, record in enumerate(records):
            score[idx] = record["mem_sum"].astype(np.float64) / 1e8
    elif kind == "record_weighted_count":
        weight = np.array(candidate["params"]["weight"], dtype=np.float64)
        bias = np.array(candidate["params"]["bias"], dtype=np.float64)
        for idx, record in enumerate(records):
            score[idx] = record["pred_count"].astype(np.float64) * weight + bias
    else:
        raise ValueError(f"unknown candidate kind: {kind}")

    params = candidate["params"]
    if kind == "record_arr_rescue":
        arr_th = int(params["arr_th"])
        abnormal_th = int(params["abnormal_th"])
        boost = int(params["boost"])
        for idx, record in enumerate(records):
            if record["pred_count"][2] >= arr_th and record["evidence"]["abnormal_evidence_count"] >= abnormal_th:
                score[idx, 2] += boost
    elif kind == "record_aff_rescue":
        aff_th = int(params["aff_th"])
        irregular_th = int(params["irregular_th"])
        boost = int(params["boost"])
        for idx, record in enumerate(records):
            if record["pred_count"][3] >= aff_th and record["evidence"]["rhythm_irregular_evidence_count"] >= irregular_th:
                score[idx, 3] += boost

    record_pred = record_score_to_pred(score, tuple(candidate["tie_order"]))
    chunk_pred = record_pred[chunk_to_record]
    return record_pred, chunk_pred


def candidate_grid() -> list[dict]:
    candidates = []
    candidate_id = 0
    tie_orders = [
        (0, 1, 2, 3),
        (0, 2, 1, 3),
        (1, 0, 2, 3),
        (2, 0, 1, 3),
        (3, 1, 2, 0),
        (3, 2, 1, 0),
    ]
    for kind in ["record_snapshot_count", "record_mem_sum"]:
        for order in tie_orders:
            candidates.append({"candidate_id": candidate_id, "kind": kind, "params": {}, "tie_order": order, "complexity": 1})
            candidate_id += 1

    weight_values = [0.75, 1.0, 1.25, 1.5, 2.0]
    bias_values = [
        (0, 0, 0, 0),
        (0, 0, 2, 0),
        (0, 0, 0, 2),
        (2, 0, 0, 0),
        (0, 2, 0, 0),
        (0, 0, 2, 2),
        (-1, 0, 1, 1),
        (1, 0, 0, 0),
    ]
    for weight in np.array(np.meshgrid(*([weight_values] * 4))).T.reshape(-1, 4):
        for bias in bias_values:
            for order in tie_orders[:3]:
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "kind": "record_weighted_count",
                        "params": {"weight": weight.tolist(), "bias": list(bias)},
                        "tie_order": order,
                        "complexity": 3,
                    }
                )
                candidate_id += 1

    for arr_th in [5, 8, 10, 15, 20, 25, 30, 35]:
        for abnormal_th in [0, 1000, 3000, 6000, 10000]:
            for boost in [8, 16, 32, 64]:
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "kind": "record_arr_rescue",
                        "params": {"arr_th": arr_th, "abnormal_th": abnormal_th, "boost": boost},
                        "tie_order": (0, 1, 2, 3),
                        "complexity": 2,
                    }
                )
                candidate_id += 1

    for aff_th in [5, 8, 10, 15, 20, 25, 30, 35]:
        for irregular_th in [0, 1000, 3000, 6000, 10000]:
            for boost in [8, 16, 32, 64]:
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "kind": "record_aff_rescue",
                        "params": {"aff_th": aff_th, "irregular_th": irregular_th, "boost": boost},
                        "tie_order": (0, 1, 2, 3),
                        "complexity": 2,
                    }
                )
                candidate_id += 1
    return candidates


def selection_key(val_metrics: dict, train_metrics: dict, candidate: dict) -> tuple:
    return (
        val_metrics["macro_f1"],
        val_metrics["balanced_accuracy"],
        -val_metrics["recall_range"],
        val_metrics["accuracy"],
        min(train_metrics["macro_f1"], val_metrics["macro_f1"]),
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
    rows = load_chunk_rows()
    table = build_record_table(rows)
    records = table["records"]
    chunk_to_record = table["chunk_to_record"]

    search_rows = []
    selected = None
    selected_key = None
    selected_record_pred = None
    selected_chunk_pred = None

    # Search/election phase: no test metrics are computed here.
    for candidate in candidate_grid():
        _, chunk_pred = apply_candidate(records, chunk_to_record, candidate)
        train_metrics = metrics_for_chunk_pred(rows, chunk_pred, "train")
        val_metrics = metrics_for_chunk_pred(rows, chunk_pred, "val")
        search_rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "kind": candidate["kind"],
                "params": json.dumps(candidate["params"], sort_keys=True),
                "tie_order": "|".join(str(x) for x in candidate["tie_order"]),
                "complexity": candidate["complexity"],
                "train_accuracy": train_metrics["accuracy"],
                "train_macro_f1": train_metrics["macro_f1"],
                "val_accuracy": val_metrics["accuracy"],
                "val_macro_f1": val_metrics["macro_f1"],
                "val_balanced_accuracy": val_metrics["balanced_accuracy"],
                "val_recall_range": val_metrics["recall_range"],
                "val_arr_recall": val_metrics["per_class"]["ARR"]["recall"],
            }
        )
        key = selection_key(val_metrics, train_metrics, candidate)
        if selected_key is None or key > selected_key:
            selected_key = key
            selected = {"candidate": candidate, "train": train_metrics, "val": val_metrics}
            selected_record_pred, selected_chunk_pred = apply_candidate(records, chunk_to_record, candidate)

    if selected is None or selected_chunk_pred is None or selected_record_pred is None:
        raise RuntimeError("no selected candidate")

    write_csv(SEARCH_CSV, search_rows)

    # Final verification phase: test is evaluated once for the selected candidate.
    test_metrics = metrics_for_chunk_pred(rows, selected_chunk_pred, "test")
    selected["test"] = test_metrics
    selected["note"] = (
        "No-oracle record-level search. Candidate search and selection used only train/validation metrics. "
        "Test metrics were computed once after validation selection."
    )

    SELECTED_JSON.write_text(json.dumps(selected, indent=2), encoding="utf-8")
    for split in rw.SPLITS:
        split_metrics = metrics_for_chunk_pred(rows, selected_chunk_pred, split)
        (RESULTS / f"no_oracle_record_level_{split}_metrics.json").write_text(json.dumps(split_metrics, indent=2), encoding="utf-8")
        split_rows = [row for row in prediction_rows(rows, selected_chunk_pred) if row["split"] == split]
        write_csv(RESULTS / f"no_oracle_record_level_{split}_predictions.csv", split_rows)

    report = [
        "# No-Oracle Record-Level Final Membrane Search",
        "",
        "Search and selection used only train/validation metrics. Test was evaluated once after the validation-selected candidate was fixed.",
        "",
        "## Selected Candidate",
        "",
        f"- candidate_id: {selected['candidate']['candidate_id']}",
        f"- kind: {selected['candidate']['kind']}",
        f"- params: `{json.dumps(selected['candidate']['params'], sort_keys=True)}`",
        f"- tie_order: `{selected['candidate']['tie_order']}`",
        "",
        "## Metrics",
        "",
        f"- train: {selected['train']['correct']}/{selected['train']['total']} = {selected['train']['accuracy']*100:.2f}%, macro-F1 {selected['train']['macro_f1']*100:.2f}%",
        f"- val: {selected['val']['correct']}/{selected['val']['total']} = {selected['val']['accuracy']*100:.2f}%, macro-F1 {selected['val']['macro_f1']*100:.2f}%",
        f"- test: {test_metrics['correct']}/{test_metrics['total']} = {test_metrics['accuracy']*100:.2f}%, macro-F1 {test_metrics['macro_f1']*100:.2f}%",
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
        f"[selected] id={selected['candidate']['candidate_id']} kind={selected['candidate']['kind']} "
        f"val={selected['val']['correct']}/{selected['val']['total']} "
        f"test={test_metrics['correct']}/{test_metrics['total']} acc={test_metrics['accuracy']:.4f}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    run_search()


if __name__ == "__main__":
    main()
