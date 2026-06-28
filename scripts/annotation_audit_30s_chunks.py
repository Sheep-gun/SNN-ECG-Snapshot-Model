import argparse
import bisect
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


ANN_SYMBOL = {
    0: "NOTQRS",
    1: "N",
    2: "L",
    3: "R",
    4: "a",
    5: "V",
    6: "F",
    7: "J",
    8: "A",
    9: "S",
    10: "E",
    11: "j",
    12: "/",
    13: "Q",
    14: "~",
    16: "|",
    18: "s",
    19: "T",
    20: "*",
    21: "D",
    22: '"',
    23: "=",
    24: "p",
    25: "B",
    26: "^",
    27: "t",
    28: "+",
    29: "u",
    30: "?",
    31: "!",
    32: "[",
    33: "]",
    34: "e",
    35: "n",
    36: "@",
}

SPECIAL_AUX = 63
SPECIAL_SKIP = 59
SPECIAL_NUM = 60
SPECIAL_SUB = 61
SPECIAL_CHN = 62

NORMAL_BEATS = {"N"}
RBBB_BEATS = {"R"}
PVC_BEATS = {"V", "E"}
PAC_SV_BEATS = {"A", "a", "J", "S", "e", "j", "n"}
FUSION_PACED_UNKNOWN = {"F", "f", "/", "Q", "L", "R"}
COUNTED_BEATS = NORMAL_BEATS | RBBB_BEATS | PVC_BEATS | PAC_SV_BEATS | FUSION_PACED_UNKNOWN
ARR_ABNORMAL_BEATS = RBBB_BEATS | PVC_BEATS | PAC_SV_BEATS | FUSION_PACED_UNKNOWN


@dataclass
class Annotation:
    sample: int
    code: int
    symbol: str
    aux: str = ""


def parse_header_fs(header_path: Path) -> float:
    first = header_path.read_text(errors="ignore").splitlines()[0].strip().split()
    if len(first) < 3:
        raise RuntimeError(f"Cannot parse fs from {header_path}")
    return float(first[2].split("/")[0])


def parse_wfdb_annotation(path: Path):
    data = path.read_bytes()
    pos = 0
    sample = 0
    anns = []
    while pos + 1 < len(data):
        b0 = data[pos]
        b1 = data[pos + 1]
        pos += 2
        interval = b0 + ((b1 & 0x03) << 8)
        code = b1 >> 2
        if code == 0 and interval == 0:
            break
        if code == SPECIAL_SKIP:
            if pos + 3 >= len(data):
                break
            # WFDB long skip is stored in the following four bytes, little-endian in practice
            # for the public databases used here.
            interval = data[pos] | (data[pos + 1] << 8) | (data[pos + 2] << 16) | (data[pos + 3] << 24)
            pos += 4
            sample += interval
            continue
        if code == SPECIAL_AUX:
            aux_len = interval
            aux_bytes = data[pos:pos + aux_len]
            pos += aux_len
            if aux_len & 1:
                pos += 1
            aux = aux_bytes.decode("latin1", errors="ignore").strip("\x00\r\n ")
            anns.append(Annotation(sample=sample, code=code, symbol="AUX", aux=aux))
            continue
        if code in {SPECIAL_NUM, SPECIAL_SUB, SPECIAL_CHN}:
            # Metadata fields do not create beat/rhythm evidence for this audit.
            continue
        sample += interval
        anns.append(Annotation(sample=sample, code=code, symbol=ANN_SYMBOL.get(code, f"CODE{code}")))
    return anns


def source_paths(source_root: Path, source_db: str, record_id: str):
    if source_db == "nsrdb":
        d = source_root / "nsrdb" / "1.0.0"
        return d / f"{record_id}.hea", d / f"{record_id}.atr", None
    if source_db == "chfdb":
        d = source_root / "chfdb" / "1.0.0"
        return d / f"{record_id}.hea", d / f"{record_id}.ecg", None
    if source_db == "x_mitdb":
        d = source_root / "mitdb" / "1.0.0" / "x_mitdb"
        return d / f"{record_id}.hea", d / f"{record_id}.atr", None
    if source_db == "mitdb":
        d = source_root / "mitdb" / "1.0.0"
        return d / f"{record_id}.hea", d / f"{record_id}.atr", None
    if source_db == "afdb":
        d = source_root / "afdb" / "1.0.0"
        return d / f"{record_id}.hea", d / f"{record_id}.qrs", d / f"{record_id}.atr"
    raise RuntimeError(f"Unknown source_db: {source_db}")


def load_record_annotations(source_root: Path, source_db: str, record_id: str):
    hea, beat_path, rhythm_path = source_paths(source_root, source_db, record_id)
    fs = parse_header_fs(hea)
    beat_anns = parse_wfdb_annotation(beat_path) if beat_path and beat_path.exists() else []
    rhythm_anns = parse_wfdb_annotation(rhythm_path) if rhythm_path and rhythm_path.exists() else []
    if not rhythm_anns and source_db != "afdb":
        rhythm_anns = beat_anns

    beat_samples = []
    beat_symbols = []
    for ann in beat_anns:
        if ann.symbol in COUNTED_BEATS:
            beat_samples.append(ann.sample)
            beat_symbols.append(ann.symbol)

    rhythm_events = []
    for ann in rhythm_anns:
        txt = ann.aux.strip()
        if not txt:
            continue
        if txt.startswith("(") or "AFIB" in txt or "AFL" in txt or "N" == txt:
            rhythm_events.append((ann.sample / fs, txt))
    rhythm_events.sort()
    return {
        "fs": fs,
        "beat_samples": beat_samples,
        "beat_symbols": beat_symbols,
        "rhythm_events": rhythm_events,
        "beat_annotation_file": str(beat_path),
        "rhythm_annotation_file": str(rhythm_path or beat_path),
    }


def count_beats(record, start_sec, end_sec):
    fs = record["fs"]
    start_native = int(start_sec * fs)
    end_native = int(end_sec * fs)
    samples = record["beat_samples"]
    symbols = record["beat_symbols"]
    i0 = bisect.bisect_left(samples, start_native)
    i1 = bisect.bisect_right(samples, end_native)
    c = Counter(symbols[i0:i1])
    beat_count = sum(c.values())
    rbbb = sum(c[s] for s in RBBB_BEATS)
    pvc = sum(c[s] for s in PVC_BEATS)
    pac_sv = sum(c[s] for s in PAC_SV_BEATS)
    fusion_paced_unknown = sum(c[s] for s in FUSION_PACED_UNKNOWN - RBBB_BEATS)
    abnormal = sum(c[s] for s in ARR_ABNORMAL_BEATS)
    normal = sum(c[s] for s in NORMAL_BEATS)
    return c, {
        "beat_count": beat_count,
        "normal_beat_count": normal,
        "abnormal_beat_count": abnormal,
        "abnormal_beat_ratio": abnormal / beat_count if beat_count else 0.0,
        "rbbb_count": rbbb,
        "pvc_count": pvc,
        "pac_sv_count": pac_sv,
        "fusion_paced_unknown_count": fusion_paced_unknown,
    }


def rhythm_overlap(record, start_sec, end_sec):
    events = record["rhythm_events"]
    if not events:
        return 0.0, 0.0, ""
    total_af = 0.0
    labels = Counter()
    for idx, (t, label) in enumerate(events):
        next_t = events[idx + 1][0] if idx + 1 < len(events) else end_sec
        ov0 = max(start_sec, t)
        ov1 = min(end_sec, next_t)
        if ov1 <= ov0:
            continue
        dur = ov1 - ov0
        labels[label] += dur
        upper = label.upper()
        if "AFIB" in upper or "AFL" in upper:
            total_af += dur
    return total_af, total_af / max(1e-9, end_sec - start_sec), ";".join(f"{k}:{v:.1f}" for k, v in labels.most_common())


def validate_chunk(cls, beat, af_ratio):
    beat_count = beat["beat_count"]
    abnormal = beat["abnormal_beat_count"]
    abnormal_ratio = beat["abnormal_beat_ratio"]
    reasons = []
    valid = True
    weak = False
    if beat_count < 8:
        valid = False
        reasons.append("low_beat_count")

    if cls == "NSR":
        if abnormal > 2 and abnormal_ratio > 0.05:
            valid = False
            reasons.append("nsr_high_abnormal_beats")
        if af_ratio >= 0.2:
            valid = False
            reasons.append("nsr_afib_afl_contamination")
    elif cls == "ARR":
        if abnormal >= 2 or abnormal_ratio >= 0.05:
            valid = valid and True
        elif abnormal >= 1:
            weak = True
            valid = False
            reasons.append("arr_weak_single_abnormal_beat")
        else:
            valid = False
            reasons.append("arr_no_abnormal_beat_in_chunk")
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
        # CHF is a record-level disease label; beat/rhythm annotations cannot prove
        # CHF morphology. This flag means clean-enough CHF-labeled ECG chunk.
    else:
        valid = False
        reasons.append("unknown_class")

    if not reasons:
        reasons.append("valid")
    return valid, weak, "|".join(reasons)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--chunk-manifest", default="fullrec_afe_30s_balanced_chunks/balanced_chunk_manifest.csv")
    parser.add_argument("--out-dir", default="results/annotation_audit_30s_chunks")
    args = parser.parse_args()

    repo = Path(args.repo)
    source_root = Path(args.source_root)
    chunk_manifest = repo / args.chunk_manifest
    out_dir = repo / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = {}
    audit_rows = []
    valid_rows = []
    excluded_rows = []

    with chunk_manifest.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    for idx, row in enumerate(rows, 1):
        key = (row["source_db"], row["record_id"])
        if key not in records:
            records[key] = load_record_annotations(source_root, row["source_db"], row["record_id"])
        record = records[key]
        start_sec = int(row["start_sample"]) / 1000.0
        end_sec = (int(row["end_sample"]) + 1) / 1000.0
        symbol_counts, beat = count_beats(record, start_sec, end_sec)
        af_sec, af_ratio, rhythm_labels = rhythm_overlap(record, start_sec, end_sec)
        valid, weak, reason = validate_chunk(row["class_label"], beat, af_ratio)
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
            "annotation_valid": int(valid),
            "annotation_weak": int(weak),
            "exclusion_reason": reason,
            "beat_annotation_file": record["beat_annotation_file"],
            "rhythm_annotation_file": record["rhythm_annotation_file"],
        })
        audit_rows.append(out)
        if valid:
            valid_rows.append(out)
        else:
            excluded_rows.append(out)
        if idx % 2000 == 0 or idx == len(rows):
            print(f"audited {idx}/{len(rows)} chunks", flush=True)

    audit_fields = list(audit_rows[0].keys()) if audit_rows else []
    for name, data in [
        ("chunk_annotation_audit.csv", audit_rows),
        ("chunk_annotation_valid_manifest.csv", valid_rows),
        ("chunk_annotation_excluded_manifest.csv", excluded_rows),
    ]:
        with (out_dir / name).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=audit_fields)
            writer.writeheader()
            writer.writerows(data)

    summary_rows = []
    for group_name, filt in [
        ("ALL", lambda r: True),
        ("VALID", lambda r: r["annotation_valid"] == 1),
        ("EXCLUDED", lambda r: r["annotation_valid"] == 0),
    ]:
        subset = [r for r in audit_rows if filt(r)]
        by_cls = defaultdict(list)
        for r in subset:
            by_cls[r["class_label"]].append(r)
        for cls in sorted(by_cls):
            items = by_cls[cls]
            summary_rows.append({
                "group": group_name,
                "class_label": cls,
                "chunks": len(items),
                "records": len({r["record_id"] for r in items}),
                "mean_beat_count": f"{sum(int(r['beat_count']) for r in items)/len(items):.3f}" if items else "0",
                "mean_abnormal_ratio": f"{sum(float(r['abnormal_beat_ratio']) for r in items)/len(items):.6f}" if items else "0",
                "mean_afib_afl_ratio": f"{sum(float(r['afib_afl_ratio']) for r in items)/len(items):.6f}" if items else "0",
            })
    reason_counter = Counter()
    for r in excluded_rows:
        for reason in r["exclusion_reason"].split("|"):
            reason_counter[(r["class_label"], reason)] += 1
    for (cls, reason), count in sorted(reason_counter.items()):
        summary_rows.append({
            "group": "EXCLUSION_REASON",
            "class_label": cls,
            "chunks": count,
            "records": "",
            "mean_beat_count": "",
            "mean_abnormal_ratio": reason,
            "mean_afib_afl_ratio": "",
        })

    summary_fields = ["group", "class_label", "chunks", "records", "mean_beat_count", "mean_abnormal_ratio", "mean_afib_afl_ratio"]
    with (out_dir / "annotation_audit_summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    valid_by_class = Counter(r["class_label"] for r in valid_rows)
    excluded_by_class = Counter(r["class_label"] for r in excluded_rows)
    lines = [
        "# 30-second chunk annotation audit",
        "",
        "Inputs:",
        f"- Chunk manifest: `{chunk_manifest}`",
        f"- Source annotations: `{source_root}`",
        "",
        "Validation rules:",
        "- NSR: low abnormal-beat contamination.",
        "- ARR: at least 2 abnormal beats or abnormal-beat ratio >= 5%, excluding AFIB/AFL-dominant chunks.",
        "- AFF: AFIB/AFL rhythm overlap >= 80%.",
        "- CHF: record-level CHF label retained; audit checks beat count and AFIB/AFL contamination only.",
        "",
        f"Total chunks: {len(audit_rows)}",
        f"Valid chunks: {len(valid_rows)}",
        f"Excluded/ambiguous chunks: {len(excluded_rows)}",
        "",
        "| Class | Valid | Excluded |",
        "|---|---:|---:|",
    ]
    for cls in sorted(set(valid_by_class) | set(excluded_by_class)):
        lines.append(f"| {cls} | {valid_by_class[cls]} | {excluded_by_class[cls]} |")
    lines.extend([
        "",
        "Important caveat:",
        "CHF is not directly provable from beat/rhythm annotation. CHF-valid means clean-enough chunk from a CHF-labeled record, not a direct CHF morphology proof.",
        "",
        "Outputs:",
        "- `chunk_annotation_audit.csv`",
        "- `chunk_annotation_valid_manifest.csv`",
        "- `chunk_annotation_excluded_manifest.csv`",
        "- `annotation_audit_summary.csv`",
    ])
    (out_dir / "annotation_audit_report.md").write_text("\n".join(lines), encoding="utf-8")

    print({
        "total": len(audit_rows),
        "valid": len(valid_rows),
        "excluded": len(excluded_rows),
        "out_dir": str(out_dir),
    })


if __name__ == "__main__":
    main()
