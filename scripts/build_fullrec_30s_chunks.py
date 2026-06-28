import argparse
import csv
import json
import os
import shutil
import time
from collections import defaultdict
from pathlib import Path


WINDOW_SAMPLES = 30_000
BYTES_PER_SAMPLE_LINE = 4


def load_manifest(root, source_name, manifest_path):
    rows = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            row["dataset_source"] = source_name
            rel_mem = Path(row["afe_adc_mem_file"].replace("/", os.sep))
            mem_path = root / rel_mem
            if not mem_path.exists():
                mem_path = root / source_name / row["split"] / row["class_label"] / f"{row['record_id']}.mem"
            if not mem_path.exists():
                raise FileNotFoundError(f"Missing mem file: {row['afe_adc_mem_file']}")
            row["mem_path"] = str(mem_path)
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", default="fullrec_afe_30s_chunks")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    out = root / args.output
    sources = [
        ("fullrec_afe", root / "fullrec_afe" / "fullrec_manifest.csv"),
        ("fullrec_afe_remaining", root / "fullrec_afe_remaining" / "fullrec_remaining_manifest.csv"),
    ]

    if not str(out).startswith(str(root)):
        raise RuntimeError(f"Refusing to write outside root: {out}")
    if out.exists():
        if not args.force:
            raise RuntimeError(f"Output exists: {out}. Use --force to replace it.")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    seen = set()
    for source_name, manifest_path in sources:
        for row in load_manifest(root, source_name, manifest_path):
            key = (row["class_label"], row["record_id"])
            if key in seen:
                raise RuntimeError(f"Duplicate record across manifests: {key}")
            seen.add(key)
            rows.append(row)

    chunk_manifest_path = out / "chunk_manifest.csv"
    record_manifest_path = out / "record_manifest_merged.csv"
    summary_path = out / "dataset_summary.csv"
    report_path = out / "README.md"

    chunk_fields = [
        "split", "class_label", "record_id", "dataset_source", "source_db",
        "chunk_id", "chunk_file", "sample_rate", "window_sec", "window_samples",
        "record_total_samples", "settling_skip_samples", "start_sample", "end_sample",
        "source_mem_file", "dropped_tail_samples", "notes",
    ]
    record_fields = [
        "split", "class_label", "record_id", "dataset_source", "source_db",
        "source_mem_file", "sample_rate", "adc_format", "total_samples",
        "total_duration_sec", "settling_skip_sec", "settling_skip_samples",
        "valid_30s_chunks", "dropped_tail_samples", "dropped_tail_sec", "notes",
    ]

    counts = defaultdict(int)
    record_rows = []
    start_time = time.time()
    window_bytes = WINDOW_SAMPLES * BYTES_PER_SAMPLE_LINE

    with chunk_manifest_path.open("w", encoding="utf-8", newline="") as cmf:
        writer = csv.DictWriter(cmf, fieldnames=chunk_fields)
        writer.writeheader()

        for idx, rec in enumerate(rows, 1):
            split = rec["split"]
            cls = rec["class_label"]
            rid = rec["record_id"]
            mem_path = Path(rec["mem_path"])
            sample_rate = int(float(rec.get("sample_rate") or 1000))
            if sample_rate != 1000:
                raise RuntimeError(f"Unexpected sample rate for {rid}: {sample_rate}")
            total_samples = int(float(rec["total_samples"]))
            settling_sec = float(rec.get("settling_skip_sec") or 2)
            skip_samples = int(round(settling_sec * sample_rate))
            usable_samples = max(0, total_samples - skip_samples)
            chunks = usable_samples // WINDOW_SAMPLES
            dropped_tail_samples = usable_samples % WINDOW_SAMPLES
            expected_size = total_samples * BYTES_PER_SAMPLE_LINE
            actual_size = mem_path.stat().st_size
            size_note = ""
            if actual_size != expected_size:
                size_note = f"size_warning:actual_bytes={actual_size},expected_bytes={expected_size}"

            rec_out_dir = out / split / cls / rid
            rec_out_dir.mkdir(parents=True, exist_ok=True)

            with mem_path.open("rb") as src:
                src.seek(skip_samples * BYTES_PER_SAMPLE_LINE)
                for chunk_id in range(chunks):
                    data = src.read(window_bytes)
                    if len(data) != window_bytes:
                        raise RuntimeError(f"Short read {rid} chunk {chunk_id}: {len(data)} bytes")
                    chunk_name = f"{rid}_w{chunk_id:05d}.mem"
                    chunk_path = rec_out_dir / chunk_name
                    with chunk_path.open("wb") as dst:
                        dst.write(data)
                    start_sample = skip_samples + chunk_id * WINDOW_SAMPLES
                    end_sample = start_sample + WINDOW_SAMPLES - 1
                    writer.writerow({
                        "split": split,
                        "class_label": cls,
                        "record_id": rid,
                        "dataset_source": rec["dataset_source"],
                        "source_db": rec.get("source_db", ""),
                        "chunk_id": chunk_id,
                        "chunk_file": str(chunk_path.relative_to(out)).replace(os.sep, "/"),
                        "sample_rate": sample_rate,
                        "window_sec": 30,
                        "window_samples": WINDOW_SAMPLES,
                        "record_total_samples": total_samples,
                        "settling_skip_samples": skip_samples,
                        "start_sample": start_sample,
                        "end_sample": end_sample,
                        "source_mem_file": str(mem_path),
                        "dropped_tail_samples": dropped_tail_samples,
                        "notes": size_note,
                    })
                    counts[(split, cls)] += 1
                    counts[("ALL", cls)] += 1
                    counts[("ALL", "ALL")] += 1

            notes = rec.get("notes", "")
            if size_note:
                notes = f"{notes};{size_note}" if notes else size_note
            record_rows.append({
                "split": split,
                "class_label": cls,
                "record_id": rid,
                "dataset_source": rec["dataset_source"],
                "source_db": rec.get("source_db", ""),
                "source_mem_file": str(mem_path),
                "sample_rate": sample_rate,
                "adc_format": rec.get("adc_format", "signed12"),
                "total_samples": total_samples,
                "total_duration_sec": rec.get("total_duration_sec", ""),
                "settling_skip_sec": settling_sec,
                "settling_skip_samples": skip_samples,
                "valid_30s_chunks": chunks,
                "dropped_tail_samples": dropped_tail_samples,
                "dropped_tail_sec": round(dropped_tail_samples / sample_rate, 3),
                "notes": notes,
            })

            if idx % 10 == 0 or idx == len(rows):
                elapsed = time.time() - start_time
                print(
                    f"processed_records={idx}/{len(rows)} chunks={counts[('ALL','ALL')]} "
                    f"elapsed_sec={elapsed:.1f}",
                    flush=True,
                )

    with record_manifest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=record_fields)
        writer.writeheader()
        writer.writerows(record_rows)

    summary_rows = []
    for (split, cls), count in sorted(counts.items()):
        if split == "ALL" and cls == "ALL":
            continue
        if split == "ALL":
            records = sum(1 for r in record_rows if r["class_label"] == cls)
        else:
            records = sum(1 for r in record_rows if r["split"] == split and r["class_label"] == cls)
        summary_rows.append({
            "split": split,
            "class_label": cls,
            "records": records,
            "chunks_30s": count,
        })
    summary_rows.append({
        "split": "ALL",
        "class_label": "ALL",
        "records": len(record_rows),
        "chunks_30s": counts[("ALL", "ALL")],
    })
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["split", "class_label", "records", "chunks_30s"])
        writer.writeheader()
        writer.writerows(summary_rows)

    elapsed = time.time() - start_time
    report_path.write_text(
        f"""# Full-record AFE+ADC 30-second chunk dataset

Generated from:
- {root / 'fullrec_afe'}
- {root / 'fullrec_afe_remaining'}

Rules:
- Input format: signed 12-bit, 1 kSPS, 3-hex Verilog readmemh-compatible `.mem`.
- Each source `.mem` is a full-record AFE+ADC stream.
- First 2 seconds are skipped using each manifest's `settling_skip_sec`.
- Window length: 30 seconds = 30,000 samples.
- Non-overlapping chunks only.
- Tail shorter than 30 seconds is discarded.
- `unassigned` split is preserved for records outside the strict split pool.
- `chf12` is included if present in remaining data, but remains a known CHF quality/outlier caution record.

Outputs:
- `chunk_manifest.csv`: every 30s chunk path and source offset.
- `record_manifest_merged.csv`: merged full-record source manifest and chunk counts.
- `dataset_summary.csv`: record/chunk counts by split/class.

Total records: {len(record_rows)}
Total 30s chunks: {counts[('ALL', 'ALL')]}
Elapsed seconds: {elapsed:.1f}
""",
        encoding="utf-8",
    )

    print(json.dumps({
        "output_dir": str(out),
        "records": len(record_rows),
        "chunks_30s": counts[("ALL", "ALL")],
        "elapsed_sec": round(elapsed, 1),
        "summary_csv": str(summary_path),
        "chunk_manifest_csv": str(chunk_manifest_path),
        "record_manifest_csv": str(record_manifest_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
