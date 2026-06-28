import argparse
import csv
import json
import os
import shutil
from collections import defaultdict, deque
from pathlib import Path


CLASSES = ("NSR", "CHF", "ARR", "AFF")
SPLIT_PATTERN = ("train", "val", "train", "test")  # 50 / 25 / 25


def evenly_pick(rows, count):
    if count >= len(rows):
        return list(rows)
    picked = []
    used = set()
    n = len(rows)
    for i in range(count):
        idx = int((i + 0.5) * n / count)
        if idx >= n:
            idx = n - 1
        while idx in used and idx + 1 < n:
            idx += 1
        while idx in used and idx - 1 >= 0:
            idx -= 1
        used.add(idx)
        picked.append(rows[idx])
    return picked


def interleave_by_record(grouped):
    queues = {record_id: deque(rows) for record_id, rows in sorted(grouped.items())}
    out = []
    while queues:
        empty = []
        for record_id in list(queues):
            q = queues[record_id]
            if q:
                out.append(q.popleft())
            if not q:
                empty.append(record_id)
        for record_id in empty:
            queues.pop(record_id, None)
    return out


def balanced_record_quotas(capacities, target):
    records = sorted(capacities)
    total_available = sum(capacities.values())
    if target > total_available:
        raise RuntimeError(f"Target {target} exceeds available {total_available}")
    if target == total_available:
        return dict(capacities)

    quotas = {record_id: 0 for record_id in records}
    base = target // len(records)
    rem = target % len(records)
    for idx, record_id in enumerate(records):
        want = base + (1 if idx < rem else 0)
        quotas[record_id] = min(capacities[record_id], want)

    remaining = target - sum(quotas.values())
    while remaining > 0:
        candidates = [
            record_id for record_id in records
            if quotas[record_id] < capacities[record_id]
        ]
        if not candidates:
            raise RuntimeError(f"Could not allocate target. remaining={remaining}")
        candidates.sort(key=lambda r: (quotas[r], r))
        for record_id in candidates:
            if remaining <= 0:
                break
            quotas[record_id] += 1
            remaining -= 1

    return quotas


def class_split_targets(total):
    train = (total + 1) // 2
    remaining = total - train
    val = remaining // 2
    test = remaining - val
    return {"train": train, "val": val, "test": test}


def split_quotas_by_record(selected_grouped, split_targets):
    total = sum(len(rows) for rows in selected_grouped.values())
    quotas = {}
    for record_id, rows in selected_grouped.items():
        k = len(rows)
        ideals = {split: k * target / total for split, target in split_targets.items()}
        q = {split: int(ideals[split]) for split in split_targets}
        remainder = k - sum(q.values())
        order = sorted(split_targets, key=lambda s: (ideals[s] - q[s], split_targets[s]), reverse=True)
        for split in order[:remainder]:
            q[split] += 1
        quotas[record_id] = q

    current = {split: sum(q[split] for q in quotas.values()) for split in split_targets}
    guard = 0
    while current != split_targets:
        guard += 1
        if guard > 10000:
            raise RuntimeError(f"Could not balance split quotas: current={current}, target={split_targets}")
        surplus = [s for s in split_targets if current[s] > split_targets[s]]
        deficit = [s for s in split_targets if current[s] < split_targets[s]]
        if not surplus or not deficit:
            break
        moved = False
        for src in surplus:
            for dst in deficit:
                for record_id in sorted(quotas, key=lambda r: quotas[r][src], reverse=True):
                    min_keep = 1 if len(selected_grouped[record_id]) >= 3 else 0
                    if quotas[record_id][src] > min_keep:
                        quotas[record_id][src] -= 1
                        quotas[record_id][dst] += 1
                        current[src] -= 1
                        current[dst] += 1
                        moved = True
                        break
                if moved:
                    break
            if moved:
                break
        if not moved:
            raise RuntimeError(f"No legal move for split quota balance: current={current}, target={split_targets}")

    return quotas


def assign_splits_for_record(rows, quotas):
    remaining = dict(quotas)
    labels = []
    while len(labels) < len(rows):
        progressed = False
        for split in SPLIT_PATTERN:
            if remaining.get(split, 0) > 0:
                labels.append(split)
                remaining[split] -= 1
                progressed = True
                if len(labels) == len(rows):
                    break
        if not progressed:
            raise RuntimeError(f"Could not assign split labels, remaining={remaining}")
    return labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--input", default="fullrec_afe_30s_chunks")
    parser.add_argument("--output", default="fullrec_afe_30s_balanced_chunks")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    src_root = root / args.input
    out_root = root / args.output
    manifest_path = src_root / "chunk_manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    if out_root.exists():
        if not args.force:
            raise RuntimeError(f"Output exists: {out_root}. Use --force to replace it.")
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["class_label"] not in CLASSES:
                continue
            if row["record_id"] == "chf12":
                continue
            row["chunk_id_int"] = int(row["chunk_id"])
            rows.append(row)

    by_class = defaultdict(list)
    for row in rows:
        by_class[row["class_label"]].append(row)

    available_counts = {cls: len(by_class[cls]) for cls in CLASSES}
    target_per_class = min(available_counts.values())
    if target_per_class <= 0:
        raise RuntimeError(f"Invalid target_per_class: {target_per_class}, counts={available_counts}")

    selected_rows = []
    record_summary_rows = []
    for cls in CLASSES:
        grouped = defaultdict(list)
        for row in by_class[cls]:
            grouped[row["record_id"]].append(row)
        for record_id in grouped:
            grouped[record_id].sort(key=lambda r: r["chunk_id_int"])

        record_ids = sorted(grouped)
        quotas = balanced_record_quotas(
            {record_id: len(grouped[record_id]) for record_id in record_ids},
            target_per_class,
        )
        selected_grouped = {}
        for record_id in record_ids:
            available = len(grouped[record_id])
            take = quotas[record_id]
            chosen = evenly_pick(grouped[record_id], take)
            selected_grouped[record_id] = chosen
            record_summary_rows.append({
                "class_label": cls,
                "record_id": record_id,
                "available_chunks": available,
                "selected_chunks": take,
                "excluded_chunks": available - take,
                "note": "chf12_excluded" if record_id == "chf12" else "",
            })

        split_targets = class_split_targets(target_per_class)
        split_quotas = split_quotas_by_record(selected_grouped, split_targets)
        balanced_index = 0
        for record_id in sorted(selected_grouped):
            rows_for_record = selected_grouped[record_id]
            labels = assign_splits_for_record(rows_for_record, split_quotas[record_id])
            for row, split in zip(rows_for_record, labels):
                row = dict(row)
                row["balanced_split"] = split
                row["balanced_index"] = balanced_index
                selected_rows.append(row)
                balanced_index += 1
        if balanced_index != target_per_class:
            raise RuntimeError(f"Selection count mismatch for {cls}: {balanced_index} != {target_per_class}")

    out_manifest = out_root / "balanced_chunk_manifest.csv"
    out_record_summary = out_root / "record_selection_summary.csv"
    out_summary = out_root / "dataset_summary.csv"
    copied = 0
    split_counts = defaultdict(int)
    class_counts = defaultdict(int)
    record_split_counts = defaultdict(int)

    fields = [
        "split", "class_label", "record_id", "chunk_id", "chunk_file",
        "sample_rate", "window_sec", "window_samples", "start_sample", "end_sample",
        "original_split", "original_chunk_file", "source_mem_file", "dataset_source",
        "source_db", "record_total_samples", "settling_skip_samples", "dropped_tail_samples",
        "balanced_index", "notes",
    ]

    with out_manifest.open("w", encoding="utf-8", newline="") as mf:
        writer = csv.DictWriter(mf, fieldnames=fields)
        writer.writeheader()
        for row in selected_rows:
            split = row["balanced_split"]
            cls = row["class_label"]
            record_id = row["record_id"]
            src_chunk = src_root / row["chunk_file"]
            if not src_chunk.exists():
                raise FileNotFoundError(src_chunk)
            dest_dir = out_root / split / cls / record_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_chunk = dest_dir / src_chunk.name
            shutil.copy2(src_chunk, dest_chunk)
            copied += 1
            split_counts[(split, cls)] += 1
            class_counts[cls] += 1
            record_split_counts[(cls, record_id, split)] += 1
            writer.writerow({
                "split": split,
                "class_label": cls,
                "record_id": record_id,
                "chunk_id": row["chunk_id"],
                "chunk_file": str(dest_chunk.relative_to(out_root)).replace(os.sep, "/"),
                "sample_rate": row["sample_rate"],
                "window_sec": row["window_sec"],
                "window_samples": row["window_samples"],
                "start_sample": row["start_sample"],
                "end_sample": row["end_sample"],
                "original_split": row["split"],
                "original_chunk_file": row["chunk_file"],
                "source_mem_file": row["source_mem_file"],
                "dataset_source": row["dataset_source"],
                "source_db": row["source_db"],
                "record_total_samples": row["record_total_samples"],
                "settling_skip_samples": row["settling_skip_samples"],
                "dropped_tail_samples": row["dropped_tail_samples"],
                "balanced_index": row["balanced_index"],
                "notes": row.get("notes", ""),
            })

    summary_rows = []
    for cls in CLASSES:
        for split in ("train", "val", "test"):
            records = len({
                record_id
                for c, record_id, s in record_split_counts
                if c == cls and s == split and record_split_counts[(c, record_id, s)] > 0
            })
            summary_rows.append({
                "split": split,
                "class_label": cls,
                "records": records,
                "chunks_30s": split_counts[(split, cls)],
            })
    for cls in CLASSES:
        records = len({r["record_id"] for r in selected_rows if r["class_label"] == cls})
        summary_rows.append({
            "split": "ALL",
            "class_label": cls,
            "records": records,
            "chunks_30s": class_counts[cls],
        })
    summary_rows.append({
        "split": "ALL",
        "class_label": "ALL",
        "records": len({(r["class_label"], r["record_id"]) for r in selected_rows}),
        "chunks_30s": copied,
    })
    with out_summary.open("w", encoding="utf-8", newline="") as sf:
        writer = csv.DictWriter(sf, fieldnames=["split", "class_label", "records", "chunks_30s"])
        writer.writeheader()
        writer.writerows(summary_rows)

    for row in record_summary_rows:
        cls = row["class_label"]
        record_id = row["record_id"]
        row["train_chunks"] = record_split_counts[(cls, record_id, "train")]
        row["val_chunks"] = record_split_counts[(cls, record_id, "val")]
        row["test_chunks"] = record_split_counts[(cls, record_id, "test")]
    with out_record_summary.open("w", encoding="utf-8", newline="") as rf:
        writer = csv.DictWriter(
            rf,
            fieldnames=[
                "class_label", "record_id", "available_chunks", "selected_chunks", "excluded_chunks",
                "train_chunks", "val_chunks", "test_chunks", "note",
            ],
        )
        writer.writeheader()
        writer.writerows(record_summary_rows)

    readme = f"""# Balanced 30-second AFE+ADC chunk dataset

Source dataset:
- `{src_root}`

Rules:
- Input chunks are 30-second signed 12-bit AFE+ADC `.mem` files.
- `chf12` is excluded.
- Class count is balanced to the smallest available class after exclusion.
- Target chunks per class: {target_per_class}
- Total chunks: {copied}
- Split policy is chunk-level, not record-wise holdout.
- New split ratio: train/val/test = 50/25/25 via repeating pattern `train, val, train, test`.
- Within each class, chunks are selected as evenly as possible from records.
- Within each selected record, chunks are sampled across the time axis rather than only from the front.
- Original split is preserved as `original_split` in `balanced_chunk_manifest.csv`.
- Unassigned ARR records are included and redistributed into train/val/test.

Outputs:
- `balanced_chunk_manifest.csv`
- `record_selection_summary.csv`
- `dataset_summary.csv`
"""
    (out_root / "README.md").write_text(readme, encoding="utf-8")

    print(json.dumps({
        "output_dir": str(out_root),
        "target_per_class": target_per_class,
        "total_chunks": copied,
        "available_counts_after_chf12_exclusion": available_counts,
        "summary_csv": str(out_summary),
        "manifest_csv": str(out_manifest),
        "record_summary_csv": str(out_record_summary),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
