from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np


REPO = Path(__file__).resolve().parents[1]
DATASET = REPO / "fullrec_afe_30min_annotation_valid_balanced"
MANIFEST = DATASET / "annotation_valid_balanced_30min_manifest.csv"
SOURCE_RESULTS = REPO / "results" / "final_membrane_30min"
RESULTS = REPO / "results" / "final_membrane_30min_recordwise"

CLASSES = ["NSR", "CHF", "ARR", "AFF"]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASSES)}
SPLITS = ["train", "val", "test"]
TARGET_CHUNKS_PER_CLASS = {"train": 17, "val": 8, "test": 9}
SNAPSHOTS_PER_CHUNK = 30

FEATURE_SUM_FIELDS = [
    "beat_count",
    "pnn_match_count",
    "pnn_mismatch_count",
    "dscr_flip_count",
    "dscr_slope_count",
    "ram_code_sum",
    "ram_code_count",
    "rdm_valid_count",
    "rdm_code_sum",
    "rdm_ge50_count",
    "rdm_ge100_count",
    "ectopic_pair_count",
    "qrs_maf_count",
    "qrs_width_abn_count",
    "qrs_complex_abn_count",
    "qrs_energy_abn_count",
    "rbbb_delay_like_count",
    "rbbb_delay_applied_count",
    "pre_qrs_bump_count",
    "eerg_gate_count",
    "eerg_applied_count",
    "eerg_ecp_count",
    "abnormal_evidence_count",
    "rhythm_irregular_evidence_count",
    "morphology_evidence_count",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


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


def safe_int(value, default: int = 0) -> int:
    if value in ("", None):
        return default
    return int(float(value))


def load_manifest() -> list[dict[str, str]]:
    rows = read_csv(MANIFEST)
    if len(rows) != 136:
        raise RuntimeError(f"expected 136 rows, got {len(rows)}")
    for row in rows:
        if row["class_label"] not in CLASSES:
            raise RuntimeError(f"unexpected class: {row['class_label']}")
        if row.get("annotation_valid") not in ("1", "true", "True"):
            raise RuntimeError(f"non annotation-valid row found: {row.get('chunk_file')}")
        if "chf12" in row["record_id"].lower() or "chf12" in row["chunk_file"].lower():
            raise RuntimeError("chf12 outlier is present; expected excluded dataset")
        chunk_path = DATASET / row["chunk_file"]
        if not chunk_path.exists():
            raise FileNotFoundError(chunk_path)
        if safe_int(row["window_samples"]) != 1_800_000:
            raise RuntimeError(f"unexpected non-30min chunk: {row['chunk_file']}")
    return rows


def record_key(row: dict[str, str]) -> tuple[str, str]:
    return row["class_label"], row["record_id"]


def write_leakage_audit(rows: list[dict[str, str]]) -> None:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[record_key(row)].append(row)
    audit = []
    for (cls, record_id), group in sorted(grouped.items()):
        old_splits = sorted({row["split"] for row in group})
        audit.append(
            {
                "class_label": cls,
                "record_id": record_id,
                "chunk_count": len(group),
                "old_splits": "|".join(old_splits),
                "leakage": int(len(old_splits) > 1),
                "chunk_ids": "|".join(str(row["chunk_id"]) for row in sorted(group, key=lambda r: safe_int(r["chunk_id"]))),
            }
        )
    write_csv(RESULTS / "recordwise_original_leakage_audit.csv", audit)


def best_class_assignment(records: list[dict]) -> dict[str, str]:
    records = sorted(records, key=lambda r: (str(r["record_id"])))
    targets = TARGET_CHUNKS_PER_CLASS
    counts = [int(record["chunk_count"]) for record in records]
    n = len(records)

    @lru_cache(maxsize=None)
    def exact(idx: int, train_count: int, val_count: int, test_count: int):
        if train_count > targets["train"] or val_count > targets["val"] or test_count > targets["test"]:
            return None
        if idx == n:
            if (
                train_count == targets["train"]
                and val_count == targets["val"]
                and test_count == targets["test"]
            ):
                return ()
            return None
        c = counts[idx]
        # Prefer train/val/test target fill order for deterministic balanced splits.
        for split, next_counts in [
            ("train", (train_count + c, val_count, test_count)),
            ("val", (train_count, val_count + c, test_count)),
            ("test", (train_count, val_count, test_count + c)),
        ]:
            rest = exact(idx + 1, *next_counts)
            if rest is not None:
                return (split,) + rest
        return None

    assignment_tuple = exact(0, 0, 0, 0)
    if assignment_tuple is None:
        @lru_cache(maxsize=None)
        def best(idx: int, train_count: int, val_count: int, test_count: int):
            if idx == n:
                final_counts = {"train": train_count, "val": val_count, "test": test_count}
                score = (
                    sum(abs(final_counts[split] - targets[split]) for split in SPLITS),
                    sum((final_counts[split] - targets[split]) ** 2 for split in SPLITS),
                    max(final_counts.values()) - min(final_counts.values()),
                )
                return score, ()
            c = counts[idx]
            choices = []
            for split, next_counts in [
                ("train", (train_count + c, val_count, test_count)),
                ("val", (train_count, val_count + c, test_count)),
                ("test", (train_count, val_count, test_count + c)),
            ]:
                score, rest = best(idx + 1, *next_counts)
                choices.append((score, (split,) + rest))
            return min(choices, key=lambda item: item[0])

        _, assignment_tuple = best(0, 0, 0, 0)

    return {record["record_id"]: split for record, split in zip(records, assignment_tuple)}


def make_recordwise_split(rows: list[dict[str, str]]) -> tuple[list[dict], dict[tuple[str, str], str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[record_key(row)].append(row)

    split_by_record: dict[tuple[str, str], str] = {}
    for cls in CLASSES:
        records = [
            {"class_label": c, "record_id": rid, "chunk_count": len(group)}
            for (c, rid), group in grouped.items()
            if c == cls
        ]
        assign = best_class_assignment(records)
        for record_id, split in assign.items():
            split_by_record[(cls, record_id)] = split

    out_rows = []
    next_case = 0
    for row in sorted(rows, key=lambda r: (split_by_record[record_key(r)], r["class_label"], r["record_id"], safe_int(r["chunk_id"]))):
        new = dict(row)
        new["old_balanced_split"] = row["split"]
        new["recordwise_split"] = split_by_record[record_key(row)]
        new["recordwise_case_id"] = next_case
        out_rows.append(new)
        next_case += 1
    return out_rows, split_by_record


def write_split_audits(recordwise_rows: list[dict]) -> None:
    write_csv(RESULTS / "recordwise_manifest.csv", recordwise_rows)
    summary_rows = []
    record_rows = []
    chunk_counts = Counter((row["recordwise_split"], row["class_label"]) for row in recordwise_rows)
    records_by_split_class: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in recordwise_rows:
        records_by_split_class[(row["recordwise_split"], row["class_label"])].add(row["record_id"])
    for split in SPLITS:
        for cls in CLASSES:
            summary_rows.append(
                {
                    "split": split,
                    "class_label": cls,
                    "record_count": len(records_by_split_class[(split, cls)]),
                    "chunk_count": chunk_counts[(split, cls)],
                    "snapshot_count": chunk_counts[(split, cls)] * SNAPSHOTS_PER_CHUNK,
                }
            )
    write_csv(RESULTS / "recordwise_split_audit_summary.csv", summary_rows)

    by_record: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in recordwise_rows:
        by_record[(row["recordwise_split"], row["class_label"], row["record_id"])].append(row)
    for (split, cls, record_id), group in sorted(by_record.items()):
        old_splits = sorted({row["old_balanced_split"] for row in group})
        record_rows.append(
            {
                "split": split,
                "class_label": cls,
                "record_id": record_id,
                "chunk_count": len(group),
                "old_balanced_splits": "|".join(old_splits),
                "chunk_ids": "|".join(str(row["chunk_id"]) for row in sorted(group, key=lambda r: safe_int(r["chunk_id"]))),
                "chunk_files": "|".join(row["chunk_file"] for row in sorted(group, key=lambda r: safe_int(r["chunk_id"]))),
            }
        )
    write_csv(RESULTS / "recordwise_split_audit_records.csv", record_rows)

    leakage = []
    by_record2: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in recordwise_rows:
        by_record2[(row["class_label"], row["record_id"])].add(row["recordwise_split"])
    for (cls, record_id), splits in sorted(by_record2.items()):
        if len(splits) > 1:
            leakage.append({"class_label": cls, "record_id": record_id, "splits": "|".join(sorted(splits))})
    write_csv(RESULTS / "recordwise_split_leakage_check.csv", leakage, fields=["class_label", "record_id", "splits"])
    if leakage:
        raise RuntimeError(f"record-wise leakage remains: {leakage[:5]}")


def snapshot_sources() -> list[dict[str, str]]:
    rows = []
    for split in SPLITS:
        rows.extend(read_csv(SOURCE_RESULTS / f"snapshot_dump_{split}.csv"))
    if len(rows) != 136 * SNAPSHOTS_PER_CHUNK:
        raise RuntimeError(f"unexpected source snapshot row count: {len(rows)}")
    return rows


def rewrite_snapshot_dumps(recordwise_rows: list[dict]) -> None:
    # Source snapshot rows were generated by the fixed Snapshot C24 Python model.
    # We only reassign rows to the new record-wise split and preserve all C24
    # feature outputs bit-for-bit.
    manifest_by_key = {
        (row["class_label"], row["record_id"], str(row["chunk_id"])): row
        for row in recordwise_rows
    }
    out_by_split = {split: [] for split in SPLITS}
    for row in snapshot_sources():
        key = (row["class_label"], row["record_id"], str(row["chunk_id"]))
        if key not in manifest_by_key:
            raise RuntimeError(f"snapshot row not found in manifest: {key}")
        manifest_row = manifest_by_key[key]
        out = dict(row)
        out["old_case_id"] = row["case_id"]
        out["old_balanced_split"] = row["split"]
        out["case_id"] = manifest_row["recordwise_case_id"]
        out["split"] = manifest_row["recordwise_split"]
        out["class_id"] = CLASS_TO_ID[row["class_label"]]
        out["chunk_file"] = manifest_row["chunk_file"]
        out_by_split[out["split"]].append(out)
    for split in SPLITS:
        out_by_split[split].sort(key=lambda r: (safe_int(r["case_id"]), safe_int(r["snapshot_id"])))
        write_csv(RESULTS / f"snapshot_dump_{split}.csv", out_by_split[split])


def load_recordwise_snapshot_dumps() -> dict[str, list[dict[str, str]]]:
    dumps = {split: read_csv(RESULTS / f"snapshot_dump_{split}.csv") for split in SPLITS}
    for split in SPLITS:
        dumps[split].sort(key=lambda r: (safe_int(r["case_id"]), safe_int(r["snapshot_id"])))
    return dumps


def build_chunks(snapshot_rows: list[dict[str, str]]) -> list[dict]:
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in snapshot_rows:
        grouped[safe_int(row["case_id"])].append(row)
    chunks = []
    for case_id in sorted(grouped):
        snaps = sorted(grouped[case_id], key=lambda r: safe_int(r["snapshot_id"]))
        if len(snaps) != SNAPSHOTS_PER_CHUNK:
            raise RuntimeError(f"case_id {case_id} has {len(snaps)} snapshots")
        first = snaps[0]
        chunks.append(
            {
                "case_id": case_id,
                "split": first["split"],
                "class_label": first["class_label"],
                "class_id": safe_int(first["class_id"]),
                "record_id": first["record_id"],
                "chunk_id": first["chunk_id"],
                "chunk_file": first["chunk_file"],
                "snapshots": snaps,
            }
        )
    return chunks


def class_mems(row: dict[str, str]) -> list[int]:
    return [safe_int(row[f"class_mem_{cls}"]) for cls in CLASSES]


def metrics_from_pred(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    cm = [[0 for _ in CLASSES] for _ in CLASSES]
    for true, pred in zip(y_true.tolist(), y_pred.tolist()):
        cm[true][pred] += 1
    total = int(len(y_true))
    correct = int(sum(cm[i][i] for i in range(4)))
    per_class = {}
    precisions = []
    recalls = []
    f1s = []
    for i, cls in enumerate(CLASSES):
        tp = cm[i][i]
        fp = sum(cm[r][i] for r in range(4) if r != i)
        fn = sum(cm[i][c] for c in range(4) if c != i)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[cls] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(cm[i])}
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
    return {
        "accuracy": correct / total if total else 0.0,
        "correct": correct,
        "total": total,
        "macro_precision": float(sum(precisions) / 4.0),
        "macro_recall": float(sum(recalls) / 4.0),
        "macro_f1": float(sum(f1s) / 4.0),
        "balanced_accuracy": float(sum(recalls) / 4.0),
        "min_recall": float(min(recalls)),
        "recall_range": float(max(recalls) - min(recalls)),
        "per_class": per_class,
        "confusion_matrix": cm,
    }


def baseline_metrics() -> None:
    dumps = load_recordwise_snapshot_dumps()
    rows = []
    payload = {}
    for split in SPLITS:
        chunks = build_chunks(dumps[split])
        y = []
        majority_pred = []
        avg_mem_pred = []
        sum_mem_pred = []
        for chunk in chunks:
            pred_counts = [0, 0, 0, 0]
            mem_sum = [0, 0, 0, 0]
            for snap in chunk["snapshots"]:
                pred_counts[safe_int(snap["snapshot_pred_class"])] += 1
                for i, value in enumerate(class_mems(snap)):
                    mem_sum[i] += value
            maj = int(max(range(4), key=lambda i: (pred_counts[i], -i)))
            avg = int(max(range(4), key=lambda i: (mem_sum[i], -i)))
            y.append(chunk["class_id"])
            majority_pred.append(maj)
            avg_mem_pred.append(avg)
            sum_mem_pred.append(avg)
            rows.append(
                {
                    "split": split,
                    "case_id": chunk["case_id"],
                    "class_label": chunk["class_label"],
                    "record_id": chunk["record_id"],
                    "chunk_id": chunk["chunk_id"],
                    "chunk_file": chunk["chunk_file"],
                    "majority_pred_class": maj,
                    "majority_pred_label": CLASSES[maj],
                    "avg_mem_pred_class": avg,
                    "avg_mem_pred_label": CLASSES[avg],
                    "pred_count_NSR": pred_counts[0],
                    "pred_count_CHF": pred_counts[1],
                    "pred_count_ARR": pred_counts[2],
                    "pred_count_AFF": pred_counts[3],
                    "mem_sum_NSR": mem_sum[0],
                    "mem_sum_CHF": mem_sum[1],
                    "mem_sum_ARR": mem_sum[2],
                    "mem_sum_AFF": mem_sum[3],
                }
            )
        y_arr = np.array(y, dtype=np.int64)
        payload[split] = {
            "majority_vote": metrics_from_pred(y_arr, np.array(majority_pred, dtype=np.int64)),
            "average_class_mem": metrics_from_pred(y_arr, np.array(avg_mem_pred, dtype=np.int64)),
            "raw_sum_class_mem": metrics_from_pred(y_arr, np.array(sum_mem_pred, dtype=np.int64)),
        }
    write_csv(RESULTS / "recordwise_baseline_predictions.csv", rows)
    (RESULTS / "recordwise_baseline_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def cmd_split() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = load_manifest()
    write_leakage_audit(rows)
    recordwise_rows, _ = make_recordwise_split(rows)
    write_split_audits(recordwise_rows)
    rewrite_snapshot_dumps(recordwise_rows)
    baseline_metrics()
    print(f"[recordwise] wrote split/audit/snapshot dumps to {RESULTS}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("split")
    args = parser.parse_args()
    if args.cmd == "split":
        cmd_split()


if __name__ == "__main__":
    main()
