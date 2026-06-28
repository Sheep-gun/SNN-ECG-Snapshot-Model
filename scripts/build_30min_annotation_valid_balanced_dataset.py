from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from annotation_audit_30s_chunks import (  # noqa: E402
    count_beats,
    load_record_annotations,
    rhythm_overlap,
)


CLASSES = ("NSR", "CHF", "ARR", "AFF")
SPLIT_PATTERN = ("train", "val", "train", "test")
WINDOW_SEC = 30 * 60
WINDOW_SAMPLES = WINDOW_SEC * 1000
BYTES_PER_SAMPLE_LINE = 4


def load_fullrec_rows(repo: Path):
    manifests = [
        ("fullrec_afe", repo / "fullrec_afe" / "fullrec_manifest.csv"),
        ("fullrec_afe_remaining", repo / "fullrec_afe_remaining" / "fullrec_remaining_manifest.csv"),
    ]
    rows = []
    seen = set()
    for source_name, manifest_path in manifests:
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                key = (row["class_label"], row["record_id"])
                if key in seen:
                    raise RuntimeError(f"Duplicate record across manifests: {key}")
                seen.add(key)
                if row["record_id"] == "chf12":
                    continue
                row["dataset_source"] = source_name
                rel = Path(row["afe_adc_mem_file"].replace("/", os.sep))
                mem_path = repo / rel
                if not mem_path.exists():
                    mem_path = repo / source_name / row["split"] / row["class_label"] / f"{row['record_id']}.mem"
                if not mem_path.exists():
                    raise FileNotFoundError(f"Missing mem file: {row['afe_adc_mem_file']}")
                row["mem_path"] = str(mem_path)
                rows.append(row)
    return rows


def create_pool_rows(fullrec_rows):
    pool = []
    no_30min = []
    for rec in fullrec_rows:
        sample_rate = int(float(rec.get("sample_rate") or 1000))
        if sample_rate != 1000:
            raise RuntimeError(f"Unexpected sample_rate {sample_rate} for {rec['record_id']}")
        total_samples = int(float(rec["total_samples"]))
        settling_skip_sec = float(rec.get("settling_skip_sec") or 2)
        skip_samples = int(round(settling_skip_sec * sample_rate))
        usable = max(0, total_samples - skip_samples)
        chunks = usable // WINDOW_SAMPLES
        dropped_tail = usable % WINDOW_SAMPLES
        if chunks < 1:
            no_30min.append({
                "class_label": rec["class_label"],
                "record_id": rec["record_id"],
                "split": rec["split"],
                "source_db": rec["source_db"],
                "total_samples": total_samples,
                "usable_samples": usable,
                "reason": "shorter_than_30min_after_settling_skip",
            })
            continue
        for chunk_id in range(chunks):
            start_sample = skip_samples + chunk_id * WINDOW_SAMPLES
            end_sample = start_sample + WINDOW_SAMPLES - 1
            pool.append({
                "original_split": rec["split"],
                "class_label": rec["class_label"],
                "record_id": rec["record_id"],
                "dataset_source": rec["dataset_source"],
                "source_db": rec["source_db"],
                "chunk_id": str(chunk_id),
                "sample_rate": str(sample_rate),
                "window_sec": str(WINDOW_SEC),
                "window_samples": str(WINDOW_SAMPLES),
                "record_total_samples": str(total_samples),
                "settling_skip_samples": str(skip_samples),
                "start_sample": str(start_sample),
                "end_sample": str(end_sample),
                "source_mem_file": rec["mem_path"],
                "dropped_tail_samples": str(dropped_tail),
                "source_notes": rec.get("notes", ""),
            })
    return pool, no_30min


def validate_30min_chunk(cls: str, beat: dict, af_ratio: float):
    beat_count = beat["beat_count"]
    abnormal = beat["abnormal_beat_count"]
    abnormal_ratio = beat["abnormal_beat_ratio"]
    reasons = []
    valid = True

    if beat_count < 300:
        valid = False
        reasons.append("low_beat_count")

    if cls == "NSR":
        if abnormal_ratio > 0.05:
            valid = False
            reasons.append("nsr_high_abnormal_ratio")
        if abnormal > 30:
            valid = False
            reasons.append("nsr_high_abnormal_count")
        if af_ratio >= 0.2:
            valid = False
            reasons.append("nsr_afib_afl_contamination")
    elif cls == "ARR":
        if not (abnormal >= 10 or abnormal_ratio >= 0.01):
            valid = False
            reasons.append("arr_insufficient_abnormal_evidence")
        if af_ratio >= 0.8:
            valid = False
            reasons.append("arr_afib_like_chunk")
    elif cls == "AFF":
        if af_ratio < 0.8:
            valid = False
            reasons.append("aff_low_afib_afl_overlap")
    elif cls == "CHF":
        if af_ratio >= 0.5:
            valid = False
            reasons.append("chf_afib_afl_contamination")
        # CHF is a record-level disease label. Annotation validates rhythm/quality
        # only; it cannot directly prove CHF morphology.
    else:
        valid = False
        reasons.append("unknown_class")

    if not reasons:
        reasons.append("valid")
    return valid, "|".join(reasons)


def audit_pool(pool_rows, source_root: Path):
    records = {}
    audited = []
    for idx, row in enumerate(pool_rows, 1):
        key = (row["source_db"], row["record_id"])
        if key not in records:
            records[key] = load_record_annotations(source_root, row["source_db"], row["record_id"])
        record = records[key]
        start_sec = int(row["start_sample"]) / 1000.0
        end_sec = (int(row["end_sample"]) + 1) / 1000.0
        symbol_counts, beat = count_beats(record, start_sec, end_sec)
        af_sec, af_ratio, rhythm_labels = rhythm_overlap(record, start_sec, end_sec)
        valid, reason = validate_30min_chunk(row["class_label"], beat, af_ratio)
        out = dict(row)
        out.update({
            "start_sec": f"{start_sec:.3f}",
            "end_sec": f"{end_sec:.3f}",
            "native_fs": record["fs"],
            "beat_count": beat["beat_count"],
            "normal_beat_count": beat["normal_beat_count"],
            "abnormal_beat_count": beat["abnormal_beat_count"],
            "abnormal_beat_ratio": f"{beat['abnormal_beat_ratio']:.6f}",
            "rbbb_count": beat["rbbb_count"],
            "pvc_count": beat["pvc_count"],
            "pac_sv_count": beat["pac_sv_count"],
            "fusion_paced_unknown_count": beat["fusion_paced_unknown_count"],
            "afib_afl_overlap_sec": f"{af_sec:.3f}",
            "afib_afl_ratio": f"{af_ratio:.6f}",
            "rhythm_labels": rhythm_labels,
            "annotation_symbols": ";".join(f"{k}:{v}" for k, v in symbol_counts.most_common()),
            "annotation_valid": str(int(valid)),
            "exclusion_reason": reason,
            "beat_annotation_file": record["beat_annotation_file"],
            "rhythm_annotation_file": record["rhythm_annotation_file"],
        })
        audited.append(out)
        if idx % 500 == 0 or idx == len(pool_rows):
            print(f"audited_30min={idx}/{len(pool_rows)}", flush=True)
    return audited


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
            hi = idx + step
            lo = idx - step
            if hi < n and hi not in used:
                idx = hi
                break
            if lo >= 0 and lo not in used:
                idx = lo
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
            raise RuntimeError(f"Could not allocate target, remaining={remaining}")
        for r in candidates:
            if remaining <= 0:
                break
            quotas[r] += 1
            remaining -= 1
    return quotas


def split_targets(total):
    train = total // 2
    rem = total - train
    val = rem // 2
    test = rem - val
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
            raise RuntimeError(f"Cannot balance splits {current} vs {targets}")
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
            raise RuntimeError(f"Cannot move split quota {current} vs {targets}")
    return quotas


def assign_labels(n, quotas):
    labels = []
    remaining = dict(quotas)
    while len(labels) < n:
        progressed = False
        for split in SPLIT_PATTERN:
            if remaining.get(split, 0) > 0:
                labels.append(split)
                remaining[split] -= 1
                progressed = True
                if len(labels) == n:
                    break
        if not progressed:
            raise RuntimeError(f"Cannot assign split labels: {remaining}")
    return labels


def select_balanced(valid_rows):
    by_class = defaultdict(list)
    for row in valid_rows:
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
            grouped[record_id].sort(key=lambda r: int(r["chunk_id"]))
        quotas = balanced_record_quotas({r: len(grouped[r]) for r in grouped}, target)
        selected_grouped = {}
        for record_id in sorted(grouped):
            chosen = evenly_pick(grouped[record_id], quotas[record_id])
            selected_grouped[record_id] = chosen
            record_summary.append({
                "class_label": cls,
                "record_id": record_id,
                "valid_available_chunks": len(grouped[record_id]),
                "selected_chunks": len(chosen),
                "excluded_valid_chunks": len(grouped[record_id]) - len(chosen),
            })
        s_targets = split_targets(target)
        s_quotas = split_quotas(selected_grouped, s_targets)
        idx = 0
        for record_id in sorted(selected_grouped):
            labels = assign_labels(len(selected_grouped[record_id]), s_quotas[record_id])
            for row, split in zip(selected_grouped[record_id], labels):
                out = dict(row)
                out["split"] = split
                out["balanced_index"] = str(idx)
                selected.append(out)
                idx += 1
    return selected, record_summary, counts, target


def write_csv(path: Path, rows, fields=None):
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def copy_selected_chunks(selected_rows, out_dir: Path):
    manifest_rows = []
    fields = None
    window_bytes = WINDOW_SAMPLES * BYTES_PER_SAMPLE_LINE
    for row in selected_rows:
        src_path = Path(row["source_mem_file"])
        split = row["split"]
        cls = row["class_label"]
        record_id = row["record_id"]
        chunk_id = int(row["chunk_id"])
        chunk_name = f"{record_id}_30min_w{chunk_id:03d}.mem"
        dest_dir = out_dir / split / cls / record_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / chunk_name
        with src_path.open("rb") as src:
            src.seek(int(row["start_sample"]) * BYTES_PER_SAMPLE_LINE)
            data = src.read(window_bytes)
            if len(data) != window_bytes:
                raise RuntimeError(f"Short read {record_id} chunk {chunk_id}: {len(data)}")
        with dest.open("wb") as f:
            f.write(data)
        out = dict(row)
        out["chunk_file"] = str(dest.relative_to(out_dir)).replace(os.sep, "/")
        manifest_rows.append(out)
        if fields is None:
            fields = list(out.keys())
    write_csv(out_dir / "annotation_valid_balanced_30min_manifest.csv", manifest_rows, fields)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--output", default="fullrec_afe_30min_annotation_valid_balanced")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo)
    source_root = Path(args.source_root)
    out = repo / args.output
    if out.exists():
        if not args.force:
            raise RuntimeError(f"Output exists: {out}. Use --force.")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    fullrec_rows = load_fullrec_rows(repo)
    pool_rows, no_30min = create_pool_rows(fullrec_rows)
    write_csv(out / "pool_30min_manifest.csv", pool_rows)
    write_csv(out / "records_shorter_than_30min.csv", no_30min)

    audited = audit_pool(pool_rows, source_root)
    valid = [r for r in audited if r["annotation_valid"] == "1"]
    excluded = [r for r in audited if r["annotation_valid"] != "1"]
    write_csv(out / "pool_annotation_audit.csv", audited)
    write_csv(out / "pool_annotation_valid_manifest.csv", valid)
    write_csv(out / "pool_annotation_excluded_manifest.csv", excluded)

    selected, record_summary, valid_counts, target = select_balanced(valid)
    copy_selected_chunks(selected, out)

    selected_counter = Counter((r["split"], r["class_label"]) for r in selected)
    class_counter = Counter(r["class_label"] for r in selected)
    summary_rows = []
    for cls in CLASSES:
        for split in ("train", "val", "test"):
            sub = [r for r in selected if r["class_label"] == cls and r["split"] == split]
            summary_rows.append({
                "split": split,
                "class_label": cls,
                "records": len({r["record_id"] for r in sub}),
                "chunks_30min": selected_counter[(split, cls)],
            })
        cls_rows = [r for r in selected if r["class_label"] == cls]
        summary_rows.append({
            "split": "ALL",
            "class_label": cls,
            "records": len({r["record_id"] for r in cls_rows}),
            "chunks_30min": class_counter[cls],
        })
    summary_rows.append({
        "split": "ALL",
        "class_label": "ALL",
        "records": len({(r["class_label"], r["record_id"]) for r in selected}),
        "chunks_30min": len(selected),
    })
    write_csv(out / "dataset_summary.csv", summary_rows)

    for rs in record_summary:
        rs["train_chunks"] = sum(
            1 for r in selected
            if r["class_label"] == rs["class_label"] and r["record_id"] == rs["record_id"] and r["split"] == "train"
        )
        rs["val_chunks"] = sum(
            1 for r in selected
            if r["class_label"] == rs["class_label"] and r["record_id"] == rs["record_id"] and r["split"] == "val"
        )
        rs["test_chunks"] = sum(
            1 for r in selected
            if r["class_label"] == rs["class_label"] and r["record_id"] == rs["record_id"] and r["split"] == "test"
        )
    write_csv(out / "record_selection_summary.csv", record_summary)

    reason_counter = Counter()
    for r in excluded:
        for reason in r["exclusion_reason"].split("|"):
            reason_counter[(r["class_label"], reason)] += 1
    audit_summary = []
    for cls in CLASSES:
        audit_summary.append({
            "class_label": cls,
            "pool_chunks": sum(1 for r in audited if r["class_label"] == cls),
            "annotation_valid_chunks": valid_counts.get(cls, 0),
            "annotation_excluded_chunks": sum(1 for r in excluded if r["class_label"] == cls),
            "final_selected_chunks": class_counter[cls],
        })
    write_csv(out / "annotation_audit_summary.csv", audit_summary)
    reason_rows = [
        {"class_label": cls, "reason": reason, "count": count}
        for (cls, reason), count in sorted(reason_counter.items())
    ]
    write_csv(out / "annotation_exclusion_reasons.csv", reason_rows)

    readme = f"""# Annotation-valid balanced 30-minute AFE+ADC chunk dataset

Sources:
- `{repo / 'fullrec_afe'}`
- `{repo / 'fullrec_afe_remaining'}`

Rules:
- `chf12` is excluded before chunk generation.
- First 2 seconds are skipped using each source manifest's settling skip.
- Window length is 30 minutes = {WINDOW_SAMPLES} samples at 1 kSPS.
- Tail shorter than 30 minutes is discarded.
- Records shorter than 30 minutes after settling skip are listed in `records_shorter_than_30min.csv`.
- Annotation audit is applied before final balancing.
- Final class count is balanced to the minimum annotation-valid class.

Final target per class: {target}
Final total chunks: {len(selected)}

Important caveat:
- CHF cannot be directly proven by beat/rhythm annotations. CHF-valid means clean-enough chunk from a CHF-labeled record with no strong AFIB/AFL contamination.

Outputs:
- `pool_30min_manifest.csv`: all possible 30-minute chunks before annotation filtering.
- `pool_annotation_audit.csv`: annotation audit for all pool chunks.
- `pool_annotation_valid_manifest.csv`: annotation-valid pool chunks.
- `annotation_valid_balanced_30min_manifest.csv`: final selected dataset.
- `dataset_summary.csv`: final split/class counts.
- `record_selection_summary.csv`: selected chunks by record.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")

    result = {
        "output_dir": str(out),
        "pool_chunks": len(pool_rows),
        "records_shorter_than_30min": len(no_30min),
        "annotation_valid_counts": valid_counts,
        "target_per_class": target,
        "final_total_chunks": len(selected),
    }
    (out / "build_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
