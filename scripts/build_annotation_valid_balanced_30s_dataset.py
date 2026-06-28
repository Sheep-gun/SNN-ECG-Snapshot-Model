import argparse
import csv
import os
import shutil
from collections import defaultdict
from pathlib import Path


CLASSES = ("NSR", "CHF", "ARR", "AFF")
SPLIT_PATTERN = ("train", "val", "train", "test")


def evenly_pick(rows, count):
    if count >= len(rows):
        return list(rows)
    picked = []
    used = set()
    n = len(rows)
    for i in range(count):
        idx = int((i + 0.5) * n / count)
        idx = min(idx, n - 1)
        step = 0
        while idx in used:
            step += 1
            alt = idx + step
            if alt < n and alt not in used:
                idx = alt
                break
            alt = idx - step
            if alt >= 0 and alt not in used:
                idx = alt
                break
        used.add(idx)
        picked.append(rows[idx])
    return picked


def balanced_record_quotas(capacities, target):
    records = sorted(capacities)
    if sum(capacities.values()) < target:
        raise RuntimeError("Not enough capacity")
    if sum(capacities.values()) == target:
        return dict(capacities)
    quotas = {r: min(capacities[r], target // len(records)) for r in records}
    remaining = target - sum(quotas.values())
    while remaining > 0:
        candidates = [r for r in records if quotas[r] < capacities[r]]
        candidates.sort(key=lambda r: (quotas[r], r))
        if not candidates:
            raise RuntimeError(f"Cannot allocate quotas, remaining={remaining}")
        for r in candidates:
            if remaining <= 0:
                break
            quotas[r] += 1
            remaining -= 1
    return quotas


def class_split_targets(total):
    train = (total + 1) // 2
    remaining = total - train
    val = remaining // 2
    test = remaining - val
    return {"train": train, "val": val, "test": test}


def split_quotas(selected_grouped, targets):
    total = sum(len(v) for v in selected_grouped.values())
    quotas = {}
    for record_id, rows in selected_grouped.items():
        k = len(rows)
        ideals = {s: k * targets[s] / total for s in targets}
        q = {s: int(ideals[s]) for s in targets}
        rem = k - sum(q.values())
        order = sorted(targets, key=lambda s: (ideals[s] - q[s], targets[s]), reverse=True)
        for s in order[:rem]:
            q[s] += 1
        quotas[record_id] = q
    current = {s: sum(q[s] for q in quotas.values()) for s in targets}
    guard = 0
    while current != targets:
        guard += 1
        if guard > 10000:
            raise RuntimeError(f"Cannot balance splits: {current} vs {targets}")
        surplus = [s for s in targets if current[s] > targets[s]]
        deficit = [s for s in targets if current[s] < targets[s]]
        moved = False
        for src in surplus:
            for dst in deficit:
                for r in sorted(quotas, key=lambda x: quotas[x][src], reverse=True):
                    if quotas[r][src] > 0:
                        quotas[r][src] -= 1
                        quotas[r][dst] += 1
                        current[src] -= 1
                        current[dst] += 1
                        moved = True
                        break
                if moved:
                    break
            if moved:
                break
        if not moved:
            raise RuntimeError(f"Cannot move split quota: {current} vs {targets}")
    return quotas


def assign_labels(n, quotas):
    remaining = dict(quotas)
    labels = []
    while len(labels) < n:
        progressed = False
        for s in SPLIT_PATTERN:
            if remaining.get(s, 0) > 0:
                labels.append(s)
                remaining[s] -= 1
                progressed = True
                if len(labels) == n:
                    break
        if not progressed:
            raise RuntimeError(f"Could not assign labels: {remaining}")
    return labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--audit", default="results/annotation_audit_30s_chunks/chunk_annotation_valid_manifest.csv")
    parser.add_argument("--source-chunks", default="fullrec_afe_30s_balanced_chunks")
    parser.add_argument("--output", default="fullrec_afe_30s_annotation_valid_balanced")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo)
    audit_path = repo / args.audit
    source_root = repo / args.source_chunks
    out = repo / args.output
    if out.exists():
        if not args.force:
            raise RuntimeError(f"Output exists: {out}. Use --force.")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    with audit_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["class_label"] not in CLASSES:
                continue
            if str(row.get("annotation_valid", "")) != "1":
                continue
            row["chunk_id_int"] = int(row["chunk_id"])
            rows.append(row)

    by_class = defaultdict(list)
    for row in rows:
        by_class[row["class_label"]].append(row)
    counts = {cls: len(by_class[cls]) for cls in CLASSES}
    target = min(counts.values())

    selected = []
    record_summary = []
    for cls in CLASSES:
        grouped = defaultdict(list)
        for row in by_class[cls]:
            grouped[row["record_id"]].append(row)
        for record_id in grouped:
            grouped[record_id].sort(key=lambda r: r["chunk_id_int"])
        quotas = balanced_record_quotas({r: len(grouped[r]) for r in grouped}, target)
        selected_grouped = {}
        for record_id in sorted(grouped):
            take = quotas[record_id]
            chosen = evenly_pick(grouped[record_id], take)
            selected_grouped[record_id] = chosen
            record_summary.append({
                "class_label": cls,
                "record_id": record_id,
                "valid_available_chunks": len(grouped[record_id]),
                "selected_chunks": take,
                "excluded_valid_chunks": len(grouped[record_id]) - take,
            })
        targets = class_split_targets(target)
        sq = split_quotas(selected_grouped, targets)
        idx = 0
        for record_id in sorted(selected_grouped):
            labels = assign_labels(len(selected_grouped[record_id]), sq[record_id])
            for row, split in zip(selected_grouped[record_id], labels):
                row = dict(row)
                row["split"] = split
                row["balanced_index"] = idx
                selected.append(row)
                idx += 1

    manifest_fields = list(selected[0].keys())
    # Keep original split and file path explicitly because split gets reassigned.
    if "new_chunk_file" not in manifest_fields:
        manifest_fields.append("new_chunk_file")
    if "audit_source_chunk_file" not in manifest_fields:
        manifest_fields.append("audit_source_chunk_file")

    manifest_path = out / "annotation_valid_balanced_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=manifest_fields)
        writer.writeheader()
        for row in selected:
            src_rel = Path(row["chunk_file"].replace("/", os.sep))
            src_file = source_root / row.get("original_split", row["split"]) / row["class_label"] / row["record_id"] / src_rel.name
            if not src_file.exists():
                src_file = source_root / src_rel
            if not src_file.exists():
                raise FileNotFoundError(f"Missing source chunk: {row['chunk_file']} / {src_file}")
            dest_dir = out / row["split"] / row["class_label"] / row["record_id"]
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src_file.name
            shutil.copy2(src_file, dest)
            row["audit_source_chunk_file"] = row["chunk_file"]
            row["new_chunk_file"] = str(dest.relative_to(out)).replace(os.sep, "/")
            writer.writerow(row)

    summary_rows = []
    for cls in CLASSES:
        cls_rows = [r for r in selected if r["class_label"] == cls]
        for split in ("train", "val", "test"):
            sub = [r for r in cls_rows if r["split"] == split]
            summary_rows.append({
                "split": split,
                "class_label": cls,
                "records": len({r["record_id"] for r in sub}),
                "chunks_30s": len(sub),
            })
        summary_rows.append({
            "split": "ALL",
            "class_label": cls,
            "records": len({r["record_id"] for r in cls_rows}),
            "chunks_30s": len(cls_rows),
        })
    summary_rows.append({
        "split": "ALL",
        "class_label": "ALL",
        "records": len({(r["class_label"], r["record_id"]) for r in selected}),
        "chunks_30s": len(selected),
    })
    with (out / "dataset_summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["split", "class_label", "records", "chunks_30s"])
        writer.writeheader()
        writer.writerows(summary_rows)

    for rs in record_summary:
        rs["train_chunks"] = sum(1 for r in selected if r["class_label"] == rs["class_label"] and r["record_id"] == rs["record_id"] and r["split"] == "train")
        rs["val_chunks"] = sum(1 for r in selected if r["class_label"] == rs["class_label"] and r["record_id"] == rs["record_id"] and r["split"] == "val")
        rs["test_chunks"] = sum(1 for r in selected if r["class_label"] == rs["class_label"] and r["record_id"] == rs["record_id"] and r["split"] == "test")
    with (out / "record_selection_summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "class_label", "record_id", "valid_available_chunks", "selected_chunks",
                "excluded_valid_chunks", "train_chunks", "val_chunks", "test_chunks",
            ],
        )
        writer.writeheader()
        writer.writerows(record_summary)

    (out / "README.md").write_text(
        f"""# Annotation-valid balanced 30-second AFE+ADC chunk dataset

Source audit:
- `{audit_path}`

Rules:
- Only chunks with `annotation_valid=1` are used.
- `chf12` is already excluded by the source balanced chunk dataset.
- Class count is balanced to the minimum annotation-valid class.
- Target chunks per class: {target}
- Total chunks: {len(selected)}
- Split is chunk-level train/val/test = 50/25/25.
- Chunks are selected as evenly as possible across records and across each record's time axis.

Outputs:
- `annotation_valid_balanced_manifest.csv`
- `dataset_summary.csv`
- `record_selection_summary.csv`
""",
        encoding="utf-8",
    )

    print({
        "output_dir": str(out),
        "valid_available_counts": counts,
        "target_per_class": target,
        "total_chunks": len(selected),
        "manifest": str(manifest_path),
    })


if __name__ == "__main__":
    main()
