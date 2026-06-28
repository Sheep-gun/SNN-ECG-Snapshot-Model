from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parents[0]
sys.path.insert(0, str(SCRIPT_DIR))

from snapshot_c24_rtl_exact import SnapshotFrontEnd, s12_from_hex_mem  # noqa: E402


CLASSES = ["NSR", "CHF", "ARR", "AFF"]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASSES)}
SPLITS = ["train", "val", "test"]

DATASET = REPO / "fullrec_afe_30min_annotation_valid_balanced"
MANIFEST = DATASET / "annotation_valid_balanced_30min_manifest.csv"
RESULTS = REPO / "results" / "final_membrane_30min"

SNAPSHOT_SAMPLES = 60_000
SNAPSHOTS_PER_CHUNK = 30
CHUNK_SAMPLES = SNAPSHOT_SAMPLES * SNAPSHOTS_PER_CHUNK

EXPECTED_SPLIT_CLASS_COUNTS = {
    ("train", "NSR"): 17,
    ("train", "CHF"): 17,
    ("train", "ARR"): 17,
    ("train", "AFF"): 17,
    ("val", "NSR"): 8,
    ("val", "CHF"): 8,
    ("val", "ARR"): 8,
    ("val", "AFF"): 8,
    ("test", "NSR"): 9,
    ("test", "CHF"): 9,
    ("test", "ARR"): 9,
    ("test", "AFF"): 9,
}

FEATURE_COLUMNS = [
    "beat_count",
    "pnn_match_count",
    "pnn_mismatch_count",
    "dscr_flip_count",
    "dscr_slope_count",
    "ram_code_sum",
    "ram_code_count",
    "rdm_valid_count",
    "rdm_code_sum",
    "rdm_ge10_count",
    "rdm_ge20_count",
    "rdm_ge30_count",
    "rdm_ge40_count",
    "rdm_ge50_count",
    "rdm_ge60_count",
    "rdm_ge70_count",
    "rdm_ge80_count",
    "rdm_ge90_count",
    "rdm_ge100_count",
    "rdm_ge110_count",
    "rdm_ge120_count",
    "rdm_ge130_count",
    "rdm_ge140_count",
    "rdm_ge150_count",
    "ectopic_pair_count",
    "qrs_maf_valid_count",
    "qrs_maf_count",
    "qrs_maf_code_sum",
    "qrs_width_abn_count",
    "qrs_complex_abn_count",
    "qrs_energy_abn_count",
    "qrs_maf_width_sum",
    "qrs_maf_complex_sum",
    "qrs_maf_energy_sum",
    "rbbb_delay_valid_count",
    "rbbb_delay_wide_count",
    "rbbb_delay_terminal_count",
    "rbbb_delay_like_count",
    "rbbb_delay_segment_count",
    "rbbb_delay_applied_count",
    "pre_qrs_bump_count",
    "eerg_gate_count",
    "eerg_applied_count",
    "eerg_pre_qrs_bump_count",
    "eerg_early_count",
    "eerg_ecp_count",
    "eerg_pnn_decision_count",
    "eerg_pnn_mismatch_count",
    "eerg_rdm_valid_count",
    "eerg_rdm_code_sum",
    "strong_event_count",
    "adaptive_event_th",
]

MEM_COLUMNS = ["class_mem_NSR", "class_mem_CHF", "class_mem_ARR", "class_mem_AFF"]

SNAPSHOT_DUMP_COLUMNS = [
    "case_id",
    "split",
    "class_label",
    "class_id",
    "record_id",
    "chunk_id",
    "balanced_index",
    "chunk_file",
    "chunk_start_sample",
    "chunk_end_sample",
    "snapshot_id",
    "snapshot_start_sample",
    "snapshot_end_sample",
    "snapshot_start_sec",
    "snapshot_end_sec",
    "source_db",
    "snapshot_pred_class",
    "pred_class",
    "snapshot_pred_label",
    "pred_label",
    "pred_valid",
    *MEM_COLUMNS,
    *FEATURE_COLUMNS,
    "pnn_decision_count",
    "pnn_mismatch_rate_bp",
    "rdm_avg_code_q8",
    "ram_avg_code_q8",
    "qrs_maf_rate_bp",
    "rbbb_like_rate_bp",
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


def bp(num: int, den: int) -> int:
    return int((num * 10_000) // den) if den else 0


def q8_avg(total: int, den: int) -> int:
    return int((total * 256) // den) if den else 0


def load_manifest() -> list[dict[str, str]]:
    rows = read_csv(MANIFEST)
    counts = Counter((row["split"], row["class_label"]) for row in rows)
    if counts != EXPECTED_SPLIT_CLASS_COUNTS:
        raise RuntimeError(f"unexpected split/class counts: {dict(counts)}")

    missing = []
    bad_sizes = []
    for row in rows:
        chunk_path = DATASET / row["chunk_file"]
        if not chunk_path.exists():
            missing.append(str(chunk_path))
            continue
        expected_bytes = CHUNK_SAMPLES * 4
        actual = chunk_path.stat().st_size
        if actual != expected_bytes:
            bad_sizes.append((str(chunk_path), actual, expected_bytes))
    if missing:
        raise FileNotFoundError(f"missing chunk files: {missing[:5]}")
    if bad_sizes:
        raise RuntimeError(f"unexpected chunk file byte sizes: {bad_sizes[:5]}")
    return rows


def class_mems(row: dict[str, str]) -> list[int]:
    return [safe_int(row[f"class_mem_{cls}"]) for cls in CLASSES]


def top_class_and_margin(row: dict[str, str]) -> tuple[int, int]:
    mems = class_mems(row)
    order = sorted(range(4), key=lambda i: (-mems[i], i))
    return order[0], mems[order[0]] - mems[order[1]]


def derive_evidence(feat: dict[str, int]) -> dict[str, int]:
    pnn_dec = int(feat.get("pnn_match_count", 0)) + int(feat.get("pnn_mismatch_count", 0))
    rdm_valid = int(feat.get("rdm_valid_count", 0))
    ram_count = int(feat.get("ram_code_count", 0))
    beat_count = int(feat.get("beat_count", 0))
    rbbb_valid = int(feat.get("rbbb_delay_valid_count", 0))
    pnn_mis = int(feat.get("pnn_mismatch_count", 0))
    rdm_ge50 = int(feat.get("rdm_ge50_count", 0))
    ect = int(feat.get("ectopic_pair_count", 0))
    qrs_maf = int(feat.get("qrs_maf_count", 0))
    rbbb_like = int(feat.get("rbbb_delay_like_count", 0))
    morph = (
        qrs_maf
        + int(feat.get("qrs_width_abn_count", 0))
        + int(feat.get("qrs_complex_abn_count", 0))
        + int(feat.get("qrs_energy_abn_count", 0))
        + rbbb_like
    )
    rhythm = pnn_mis + rdm_ge50 + ect
    return {
        "pnn_decision_count": pnn_dec,
        "pnn_mismatch_rate_bp": bp(pnn_mis, pnn_dec),
        "rdm_avg_code_q8": q8_avg(int(feat.get("rdm_code_sum", 0)), rdm_valid),
        "ram_avg_code_q8": q8_avg(int(feat.get("ram_code_sum", 0)), ram_count),
        "qrs_maf_rate_bp": bp(qrs_maf, beat_count),
        "rbbb_like_rate_bp": bp(rbbb_like, rbbb_valid),
        "abnormal_evidence_count": rhythm + morph,
        "rhythm_irregular_evidence_count": rhythm,
        "morphology_evidence_count": morph,
    }


def snapshot_dump_rows_for_chunk(args: tuple[int, dict[str, str]]) -> tuple[int, str, list[dict]]:
    case_id, manifest_row = args
    split = manifest_row["split"]
    chunk_path = DATASET / manifest_row["chunk_file"]
    samples = s12_from_hex_mem(chunk_path)
    if len(samples) != CHUNK_SAMPLES:
        raise RuntimeError(f"{chunk_path} has {len(samples)} samples, expected {CHUNK_SAMPLES}")

    rows = []
    chunk_start = safe_int(manifest_row.get("start_sample", 0))
    for snapshot_id in range(SNAPSHOTS_PER_CHUNK):
        local_start = snapshot_id * SNAPSHOT_SAMPLES
        local_end = local_start + SNAPSHOT_SAMPLES
        feat = SnapshotFrontEnd().run_window(samples[local_start:local_end])
        pred = int(feat["pred_class"])
        out = {
            "case_id": case_id,
            "split": split,
            "class_label": manifest_row["class_label"],
            "class_id": CLASS_TO_ID[manifest_row["class_label"]],
            "record_id": manifest_row["record_id"],
            "chunk_id": manifest_row["chunk_id"],
            "balanced_index": manifest_row["balanced_index"],
            "chunk_file": manifest_row["chunk_file"],
            "chunk_start_sample": manifest_row["start_sample"],
            "chunk_end_sample": manifest_row["end_sample"],
            "snapshot_id": snapshot_id,
            "snapshot_start_sample": chunk_start + local_start,
            "snapshot_end_sample": chunk_start + local_end - 1,
            "snapshot_start_sec": f"{(chunk_start + local_start) / 1000.0:.3f}",
            "snapshot_end_sec": f"{(chunk_start + local_end) / 1000.0:.3f}",
            "source_db": manifest_row.get("source_db", ""),
            "snapshot_pred_class": pred,
            "pred_class": pred,
            "snapshot_pred_label": CLASSES[pred],
            "pred_label": CLASSES[pred],
            "pred_valid": int(feat.get("pred_valid", 0)),
        }
        for col in MEM_COLUMNS:
            out[col] = int(feat[col])
        for col in FEATURE_COLUMNS:
            out[col] = int(feat.get(col, 0))
        out.update(derive_evidence(feat))
        rows.append(out)
    return case_id, split, rows


def expected_snapshot_counts() -> dict[str, int]:
    chunks_by_split = Counter(split for split, _cls in EXPECTED_SPLIT_CLASS_COUNTS for _ in range(EXPECTED_SPLIT_CLASS_COUNTS[(split, _cls)]))
    return {split: chunks_by_split[split] * SNAPSHOTS_PER_CHUNK for split in SPLITS}


def snapshot_dumps_complete() -> bool:
    expected = expected_snapshot_counts()
    for split, count in expected.items():
        path = RESULTS / f"snapshot_dump_{split}.csv"
        if not path.exists():
            return False
        try:
            if len(read_csv(path)) != count:
                return False
        except Exception:
            return False
    return True


def generate_snapshot_dumps(force: bool = False, workers: int | None = None) -> None:
    rows = load_manifest()
    RESULTS.mkdir(parents=True, exist_ok=True)
    if snapshot_dumps_complete() and not force:
        print("[dump] existing complete 30min snapshot dumps found; use --force to regenerate", flush=True)
        return

    if workers is None:
        workers = max(1, min(8, os.cpu_count() or 1))
    workers = max(1, workers)
    temp_paths = {split: RESULTS / f"snapshot_dump_{split}.csv.tmp" for split in SPLITS}
    final_paths = {split: RESULTS / f"snapshot_dump_{split}.csv" for split in SPLITS}
    writers: dict[str, csv.DictWriter] = {}
    files = {}
    start_time = time.time()
    try:
        for split in SPLITS:
            f = temp_paths[split].open("w", newline="", encoding="utf-8-sig")
            files[split] = f
            writer = csv.DictWriter(f, fieldnames=SNAPSHOT_DUMP_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writers[split] = writer

        total = len(rows)
        futures = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for case_id, row in enumerate(rows):
                futures.append(pool.submit(snapshot_dump_rows_for_chunk, (case_id, row)))
            completed = 0
            for fut in as_completed(futures):
                case_id, split, out_rows = fut.result()
                for out in out_rows:
                    writers[split].writerow(out)
                files[split].flush()
                completed += 1
                if completed % 4 == 0 or completed == total:
                    elapsed = time.time() - start_time
                    print(f"[dump] {completed}/{total} chunks complete ({elapsed:.1f}s), latest case_id={case_id}", flush=True)
    finally:
        for f in files.values():
            f.close()

    for split in SPLITS:
        temp_paths[split].replace(final_paths[split])
    print(f"[dump] wrote snapshot dumps under {RESULTS}", flush=True)


def load_snapshot_dumps() -> dict[str, list[dict[str, str]]]:
    dumps = {split: read_csv(RESULTS / f"snapshot_dump_{split}.csv") for split in SPLITS}
    for split in SPLITS:
        dumps[split].sort(key=lambda r: (safe_int(r["case_id"]), safe_int(r["snapshot_id"])))
    return dumps


def build_chunks(snapshot_rows: list[dict[str, str]]) -> list[dict]:
    groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in snapshot_rows:
        groups[safe_int(row["case_id"])].append(row)
    chunks = []
    for case_id in sorted(groups):
        snaps = sorted(groups[case_id], key=lambda r: safe_int(r["snapshot_id"]))
        if len(snaps) != SNAPSHOTS_PER_CHUNK:
            raise RuntimeError(f"case_id={case_id} has {len(snaps)} snapshots")
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


def build_feature_specs() -> list[dict]:
    specs: list[dict] = [{"name": "bias", "kind": "bias"}]

    margin_ths = [0, 1_000_000, 2_500_000, 5_000_000, 10_000_000, 20_000_000, 40_000_000, 80_000_000]
    mem_ge_ths = [-80_000_000, -40_000_000, -20_000_000, 0, 20_000_000, 40_000_000, 80_000_000]
    for cls, name in enumerate(CLASSES):
        specs.append({"name": f"pred_eq_{name}", "kind": "pred_eq", "class": cls})
        specs.append({"name": f"top_eq_{name}", "kind": "top_eq", "class": cls})
        for th in margin_ths:
            specs.append({"name": f"top_{name}_margin_ge_{th}", "kind": "top_margin_ge", "class": cls, "threshold": th})
        for th in mem_ge_ths:
            specs.append({"name": f"mem_{name}_ge_{th}", "kind": "mem_ge", "class": cls, "threshold": th})

    count_thresholds = [
        ("beat_count", [30, 40, 50, 60, 75, 90, 110, 130]),
        ("pnn_mismatch_count", [1, 3, 5, 8, 12, 18, 25, 35, 50]),
        ("ectopic_pair_count", [1, 3, 5, 8, 12, 18, 25]),
        ("rdm_ge50_count", [1, 3, 5, 8, 12, 18, 25, 40, 60]),
        ("rdm_ge100_count", [1, 3, 5, 8, 12, 18, 25]),
        ("qrs_maf_count", [1, 3, 5, 8, 12, 18, 25, 40]),
        ("qrs_width_abn_count", [1, 3, 5, 8, 12, 18, 25]),
        ("qrs_energy_abn_count", [1, 3, 5, 8, 12, 18, 25]),
        ("rbbb_delay_like_count", [1, 3, 5, 8, 12, 18, 25]),
        ("rbbb_delay_applied_count", [1, 3, 5, 8, 12, 18, 25]),
        ("pre_qrs_bump_count", [1, 5, 15, 30, 45, 60, 90]),
        ("dscr_flip_count", [1, 20, 50, 80, 120, 180, 250]),
        ("dscr_slope_count", [1, 250, 750, 1500, 3000, 6000, 10000]),
        ("abnormal_evidence_count", [1, 3, 5, 8, 12, 18, 25, 40, 60]),
        ("rhythm_irregular_evidence_count", [1, 3, 5, 8, 12, 18, 25, 40, 60]),
        ("morphology_evidence_count", [1, 3, 5, 8, 12, 18, 25, 40, 60]),
    ]
    for field, thresholds in count_thresholds:
        for th in thresholds:
            specs.append({"name": f"{field}_ge_{th}", "kind": "count_ge", "field": field, "threshold": th})

    for field, thresholds in [
        ("pnn_mismatch_count", [0, 1, 3, 5, 8, 12]),
        ("qrs_maf_count", [0, 1, 3, 5, 8]),
        ("ectopic_pair_count", [0, 1, 3, 5]),
        ("rdm_ge50_count", [0, 1, 3, 5, 8]),
        ("rbbb_delay_like_count", [0, 1, 3, 5]),
    ]:
        for th in thresholds:
            specs.append({"name": f"{field}_le_{th}", "kind": "count_le", "field": field, "threshold": th})

    for pct in [3, 5, 8, 10, 12, 15, 20, 30, 40, 55]:
        specs.append({"name": f"pnn_mis_rate_ge_{pct}", "kind": "ratio_ge", "num": "pnn_mismatch_count", "den": "pnn_decision_count", "pct": pct})
    for pct in [3, 5, 8, 10, 12, 15, 20, 30, 40, 55]:
        specs.append({"name": f"rdm_ge50_rate_ge_{pct}", "kind": "ratio_ge", "num": "rdm_ge50_count", "den": "rdm_valid_count", "pct": pct})
    for pct in [3, 5, 8, 10, 12, 15, 20, 30, 40, 55]:
        specs.append({"name": f"qrs_maf_rate_ge_{pct}", "kind": "ratio_ge", "num": "qrs_maf_count", "den": "beat_count", "pct": pct})

    for avg in [1, 2, 4, 6, 8, 10, 12, 16, 20]:
        specs.append({"name": f"rdm_avg_ge_{avg}", "kind": "avg_ge", "sum": "rdm_code_sum", "den": "rdm_valid_count", "threshold": avg})
    for avg in [2, 4, 6, 8, 10, 14, 18, 24]:
        specs.append({"name": f"ram_avg_ge_{avg}", "kind": "avg_ge", "sum": "ram_code_sum", "den": "ram_code_count", "threshold": avg})

    custom_names = [
        "nsr_stability_strict",
        "nsr_stability_soft",
        "arr_burst_strong",
        "arr_episodic_soft",
        "aff_irregular_persistent",
        "aff_irregular_soft",
        "chf_morphology_low_irreg",
        "abnormal_priority_any",
        "abnormal_priority_strong",
    ]
    for name in custom_names:
        specs.append({"name": name, "kind": "custom", "custom": name})

    # These fire once at the 30th snapshot when a persistence counter reaches
    # its threshold. RTL can implement them as small counters plus comparators.
    count_ths = [1, 3, 5, 8, 10, 13, 15, 18, 20, 23, 25, 28, 30]
    for cls, name in enumerate(CLASSES):
        for th in count_ths:
            specs.append({"name": f"pred_count_{name}_ge_{th}", "kind": "chunk_pred_count_ge", "class": cls, "threshold": th})
            specs.append({"name": f"top_count_{name}_ge_{th}", "kind": "chunk_top_count_ge", "class": cls, "threshold": th})
    for custom in custom_names:
        for th in count_ths:
            specs.append({"name": f"{custom}_count_ge_{th}", "kind": "chunk_custom_count_ge", "custom": custom, "threshold": th})
    return specs


def spec_value(row: dict[str, str], spec: dict) -> int:
    kind = spec["kind"]
    if kind == "bias":
        return 0
    if kind.startswith("chunk_"):
        return 0
    pred = safe_int(row["snapshot_pred_class"])
    top, margin = top_class_and_margin(row)
    if kind == "pred_eq":
        return int(pred == int(spec["class"]))
    if kind == "top_eq":
        return int(top == int(spec["class"]))
    if kind == "top_margin_ge":
        return int(top == int(spec["class"]) and margin >= int(spec["threshold"]))
    if kind == "mem_ge":
        return int(safe_int(row[f"class_mem_{CLASSES[int(spec['class'])]}"]) >= int(spec["threshold"]))
    if kind == "count_ge":
        return int(safe_int(row[spec["field"]]) >= int(spec["threshold"]))
    if kind == "count_le":
        return int(safe_int(row[spec["field"]]) <= int(spec["threshold"]))
    if kind == "ratio_ge":
        den = safe_int(row[spec["den"]])
        return int(den > 0 and safe_int(row[spec["num"]]) * 100 >= den * int(spec["pct"]))
    if kind == "avg_ge":
        den = safe_int(row[spec["den"]])
        return int(den > 0 and safe_int(row[spec["sum"]]) >= den * int(spec["threshold"]))
    if kind == "custom":
        pnn_mis = safe_int(row["pnn_mismatch_count"])
        pnn_dec = safe_int(row["pnn_decision_count"])
        rdm_ge50 = safe_int(row["rdm_ge50_count"])
        rdm_valid = safe_int(row["rdm_valid_count"])
        ect = safe_int(row["ectopic_pair_count"])
        qrs_maf = safe_int(row["qrs_maf_count"])
        rbbb_like = safe_int(row["rbbb_delay_like_count"])
        cls = CLASSES[pred]
        mis_rate_ge_12 = pnn_dec > 0 and pnn_mis * 100 >= pnn_dec * 12
        mis_rate_ge_25 = pnn_dec > 0 and pnn_mis * 100 >= pnn_dec * 25
        rdm50_rate_ge_15 = rdm_valid > 0 and rdm_ge50 * 100 >= rdm_valid * 15
        rdm50_rate_ge_30 = rdm_valid > 0 and rdm_ge50 * 100 >= rdm_valid * 30
        name = spec["custom"]
        if name == "nsr_stability_strict":
            return int(cls == "NSR" and pnn_mis <= 1 and ect == 0 and qrs_maf <= 1 and rbbb_like == 0)
        if name == "nsr_stability_soft":
            return int(cls == "NSR" and pnn_mis <= 5 and ect <= 1 and qrs_maf <= 3)
        if name == "arr_burst_strong":
            return int((pnn_mis >= 12 and ect >= 3) or qrs_maf >= 18)
        if name == "arr_episodic_soft":
            return int(cls == "ARR" and (pnn_mis >= 5 or qrs_maf >= 8 or ect >= 3))
        if name == "aff_irregular_persistent":
            return int(mis_rate_ge_25 and rdm50_rate_ge_30)
        if name == "aff_irregular_soft":
            return int(cls == "AFF" and (mis_rate_ge_12 or rdm50_rate_ge_15))
        if name == "chf_morphology_low_irreg":
            return int(cls == "CHF" and pnn_mis <= 8 and qrs_maf <= 8)
        if name == "abnormal_priority_any":
            return int(pnn_mis >= 5 or ect >= 3 or qrs_maf >= 5 or rbbb_like >= 3)
        if name == "abnormal_priority_strong":
            return int(pnn_mis >= 15 or ect >= 8 or qrs_maf >= 15 or rbbb_like >= 8)
    raise ValueError(f"unsupported feature spec: {spec}")


def build_sequence_matrix(chunks: list[dict], specs: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    x = np.zeros((len(chunks), SNAPSHOTS_PER_CHUNK, len(specs)), dtype=np.int8)
    y = np.zeros((len(chunks),), dtype=np.int64)
    for i, chunk in enumerate(chunks):
        y[i] = int(chunk["class_id"])
        for t, row in enumerate(chunk["snapshots"]):
            for j, spec in enumerate(specs):
                x[i, t, j] = spec_value(row, spec)
        x[i, :, 0] = 0
        for j, spec in enumerate(specs):
            kind = spec["kind"]
            if kind == "chunk_pred_count_ge":
                count = sum(1 for row in chunk["snapshots"] if safe_int(row["snapshot_pred_class"]) == int(spec["class"]))
                x[i, SNAPSHOTS_PER_CHUNK - 1, j] = int(count >= int(spec["threshold"]))
            elif kind == "chunk_top_count_ge":
                count = sum(1 for row in chunk["snapshots"] if top_class_and_margin(row)[0] == int(spec["class"]))
                x[i, SNAPSHOTS_PER_CHUNK - 1, j] = int(count >= int(spec["threshold"]))
            elif kind == "chunk_custom_count_ge":
                custom_spec = {"kind": "custom", "custom": spec["custom"]}
                count = sum(spec_value(row, custom_spec) for row in chunk["snapshots"])
                x[i, SNAPSHOTS_PER_CHUNK - 1, j] = int(count >= int(spec["threshold"]))
    return x, y


def aggregate_matrix(seq_x: np.ndarray) -> np.ndarray:
    agg = seq_x.sum(axis=1).astype(np.int16)
    agg[:, 0] = 1
    return agg


def init_weights(specs: list[dict], pred_init: int, top_init: int, mem_init: int) -> np.ndarray:
    weights = np.zeros((4, len(specs)), dtype=np.int32)
    for j, spec in enumerate(specs):
        kind = spec["kind"]
        if kind == "pred_eq":
            c = int(spec["class"])
            weights[c, j] += pred_init
            for k in range(4):
                if k != c:
                    weights[k, j] -= pred_init // 2
        elif kind == "top_eq":
            c = int(spec["class"])
            weights[c, j] += top_init
        elif kind == "mem_ge" and int(spec["threshold"]) >= 0:
            c = int(spec["class"])
            weights[c, j] += mem_init
    return weights


def train_perceptron(x: np.ndarray, y: np.ndarray, specs: list[dict], *, epochs: int, lr: int, seed: int, pred_init: int, top_init: int, mem_init: int) -> np.ndarray:
    weights = init_weights(specs, pred_init=pred_init, top_init=top_init, mem_init=mem_init)
    order = list(range(len(y)))
    rng = random.Random(seed)
    for _ in range(epochs):
        rng.shuffle(order)
        for idx in order:
            scores = x[idx].astype(np.int32) @ weights.T
            pred = int(np.argmax(scores))
            true = int(y[idx])
            if pred != true:
                active = x[idx].astype(np.int32)
                weights[true] += lr * active
                weights[pred] -= lr * active
    return weights


def apply_leak(scores: np.ndarray, leak: int) -> np.ndarray:
    if leak <= 0:
        return scores
    return np.where(scores > leak, scores - leak, np.where(scores < -leak, scores + leak, 0))


def predict_sequence_scores(seq_x: np.ndarray, weights: np.ndarray, cap: int = 0, leak: int = 0) -> np.ndarray:
    scores = np.tile(weights[:, 0], (seq_x.shape[0], 1)).astype(np.int32)
    per_snapshot_weights = weights.copy()
    per_snapshot_weights[:, 0] = 0
    for t in range(seq_x.shape[1]):
        scores += seq_x[:, t, :].astype(np.int32) @ per_snapshot_weights.T
        scores = apply_leak(scores, leak)
        if cap > 0:
            scores = np.clip(scores, -cap, cap)
    return scores


def predict_sequence_classes(seq_x: np.ndarray, weights: np.ndarray, cap: int = 0, leak: int = 0) -> np.ndarray:
    return np.argmax(predict_sequence_scores(seq_x, weights, cap, leak), axis=1).astype(np.int64)


def confusion(y_true: np.ndarray, y_pred: np.ndarray) -> list[list[int]]:
    cm = [[0 for _ in CLASSES] for _ in CLASSES]
    for true, pred in zip(y_true.tolist(), y_pred.tolist()):
        cm[true][pred] += 1
    return cm


def metrics_from_pred(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    cm = confusion(y_true, y_pred)
    total = int(len(y_true))
    correct = int(sum(cm[i][i] for i in range(4)))
    per_class = {}
    recalls = []
    f1s = []
    precisions = []
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


def score_key(metrics: dict, nnz: int, train_metrics: dict | None = None) -> tuple:
    train_accuracy = train_metrics["accuracy"] if train_metrics is not None else 0.0
    train_macro_f1 = train_metrics["macro_f1"] if train_metrics is not None else 0.0
    return (
        metrics["accuracy"],
        metrics["macro_f1"],
        metrics["balanced_accuracy"],
        metrics["min_recall"],
        -metrics["recall_range"],
        train_accuracy,
        train_macro_f1,
        -nnz,
    )


def load_chunks_and_matrices() -> tuple[dict[str, list[dict]], list[dict], dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray]]:
    dumps = load_snapshot_dumps()
    chunks = {split: build_chunks(dumps[split]) for split in SPLITS}
    specs = build_feature_specs()
    seq = {}
    agg = {}
    y = {}
    for split in SPLITS:
        seq[split], y[split] = build_sequence_matrix(chunks[split], specs)
        agg[split] = aggregate_matrix(seq[split])
    return chunks, specs, seq, agg, y


def write_prediction_csv(path: Path, chunks: list[dict], pred: np.ndarray, scores: np.ndarray) -> None:
    rows = []
    for chunk, p, score in zip(chunks, pred.tolist(), scores.tolist()):
        rows.append(
            {
                "case_id": chunk["case_id"],
                "split": chunk["split"],
                "class_label": chunk["class_label"],
                "class_id": chunk["class_id"],
                "record_id": chunk["record_id"],
                "chunk_id": chunk["chunk_id"],
                "chunk_file": chunk["chunk_file"],
                "final_pred_class": p,
                "final_pred_label": CLASSES[p],
                "correct": int(p == int(chunk["class_id"])),
                "final_mem_NSR": int(score[0]),
                "final_mem_CHF": int(score[1]),
                "final_mem_ARR": int(score[2]),
                "final_mem_AFF": int(score[3]),
            }
        )
    write_csv(path, rows)


def run_search() -> None:
    chunks, specs, seq, agg, y = load_chunks_and_matrices()
    chunk_feature_indices = [j for j, spec in enumerate(specs) if str(spec["kind"]).startswith("chunk_")]
    agg_base = {split: matrix.copy() for split, matrix in agg.items()}
    for split in SPLITS:
        if chunk_feature_indices:
            agg_base[split][:, chunk_feature_indices] = 0
    search_rows = []
    best_key = None
    best_payload = None
    candidate_id = 0

    def evaluate_candidate(weights: np.ndarray, cap: int, leak: int, params: dict) -> None:
        nonlocal candidate_id, best_key, best_payload
        train_scores = predict_sequence_scores(seq["train"], weights, cap, leak)
        val_scores = predict_sequence_scores(seq["val"], weights, cap, leak)
        train_pred = np.argmax(train_scores, axis=1).astype(np.int64)
        val_pred = np.argmax(val_scores, axis=1).astype(np.int64)
        train_m = metrics_from_pred(y["train"], train_pred)
        val_m = metrics_from_pred(y["val"], val_pred)
        nnz = int(np.count_nonzero(weights))
        row = {
            "candidate_id": candidate_id,
            **params,
            "cap": cap,
            "leak": leak,
            "nnz": nnz,
            "train_accuracy": train_m["accuracy"],
            "train_macro_f1": train_m["macro_f1"],
            "train_balanced_accuracy": train_m["balanced_accuracy"],
            "train_min_recall": train_m["min_recall"],
            "val_accuracy": val_m["accuracy"],
            "val_macro_f1": val_m["macro_f1"],
            "val_balanced_accuracy": val_m["balanced_accuracy"],
            "val_min_recall": val_m["min_recall"],
            "val_recall_range": val_m["recall_range"],
        }
        search_rows.append(row)
        key = score_key(val_m, nnz, train_m)
        if best_key is None or key > best_key:
            best_key = key
            best_payload = {
                "candidate_id": candidate_id,
                "params": {**params, "cap": cap, "leak": leak, "tie_break": "lowest_class_index"},
                "weights": weights.copy(),
                "train_metrics": train_m,
                "val_metrics": val_m,
            }
        candidate_id += 1

    for pred_init, top_init, mem_init in [(32, 0, 0), (0, 32, 0), (24, 16, 0), (16, 16, 1), (8, 16, 2)]:
        weights = init_weights(specs, pred_init=pred_init, top_init=top_init, mem_init=mem_init)
        for cap in [0, 512, 1024, 2048, 4096]:
            for leak in [0, 1, 2, 4]:
                evaluate_candidate(weights, cap, leak, {"kind": "baseline", "epochs": 0, "lr": 0, "seed": 0, "pred_init": pred_init, "top_init": top_init, "mem_init": mem_init})

    for epochs in [2, 4, 6, 10, 14, 20, 30]:
        for lr in [1, 2, 4]:
            for pred_init in [0, 8, 16, 32]:
                for top_init in [0, 8, 16]:
                    for mem_init in [0, 1, 2]:
                        for seed in [0, 1, 2, 3]:
                            weights = train_perceptron(
                                agg_base["train"],
                                y["train"],
                                specs,
                                epochs=epochs,
                                lr=lr,
                                seed=seed,
                                pred_init=pred_init,
                                top_init=top_init,
                                mem_init=mem_init,
                            )
                            for cap in [0, 1024, 2048, 4096, 8192]:
                                for leak in [0, 1, 2, 4]:
                                    evaluate_candidate(
                                        weights,
                                        cap,
                                        leak,
                                        {
                                            "kind": "perceptron",
                                            "epochs": epochs,
                                            "lr": lr,
                                            "seed": seed,
                                            "pred_init": pred_init,
                                            "top_init": top_init,
                                            "mem_init": mem_init,
                                        },
                                    )
        print(f"[search] completed epochs={epochs}, candidates={candidate_id}", flush=True)

    overlay_base = best_payload
    if overlay_base is not None:
        threshold_indices = [j for j, spec in enumerate(specs) if str(spec["kind"]).startswith("chunk_")]
        for j in threshold_indices:
            spec = specs[j]
            target_classes = [int(spec["class"])] if "class" in spec else list(range(4))
            for target in target_classes:
                for boost in [16, 64, 256, 1024, 4096, 16_384, 65_536, 131_072, 262_144, 524_288]:
                    weights = overlay_base["weights"].copy()
                    weights[target, j] += boost
                    for other in range(4):
                        if other != target:
                            weights[other, j] -= boost // 2
                    evaluate_candidate(
                        weights,
                        int(overlay_base["params"].get("cap", 0)),
                        int(overlay_base["params"].get("leak", 0)),
                        {
                            "kind": "threshold_overlay",
                            "epochs": overlay_base["params"].get("epochs", 0),
                            "lr": overlay_base["params"].get("lr", 0),
                            "seed": overlay_base["params"].get("seed", 0),
                            "pred_init": overlay_base["params"].get("pred_init", 0),
                            "top_init": overlay_base["params"].get("top_init", 0),
                            "mem_init": overlay_base["params"].get("mem_init", 0),
                            "base_candidate_id": overlay_base["candidate_id"],
                            "overlay_feature": spec["name"],
                            "overlay_target_class": CLASSES[target],
                            "overlay_boost": boost,
                        },
                    )
        print(f"[search] completed threshold overlays, candidates={candidate_id}", flush=True)

    assert best_payload is not None
    write_csv(RESULTS / "final_layer_search.csv", search_rows)

    selected_weights = best_payload["weights"]
    cap = int(best_payload["params"].get("cap", 0))
    leak = int(best_payload["params"].get("leak", 0))
    split_metrics = {}
    for split in SPLITS:
        scores = predict_sequence_scores(seq[split], selected_weights, cap, leak)
        pred = np.argmax(scores, axis=1).astype(np.int64)
        metrics = metrics_from_pred(y[split], pred)
        split_metrics[split] = metrics
        (RESULTS / f"python_{split}_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        write_prediction_csv(RESULTS / f"python_{split}_predictions.csv", chunks[split], pred, scores)

    selected = {
        "classes": CLASSES,
        "dataset": str(DATASET),
        "snapshot_samples": SNAPSHOT_SAMPLES,
        "snapshots_per_chunk": SNAPSHOTS_PER_CHUNK,
        "selection_rule": "validation accuracy, macro-F1, balanced accuracy, min recall, recall range, train accuracy/macro-F1 tie-break, then nnz",
        "candidate_id": best_payload["candidate_id"],
        "params": best_payload["params"],
        "feature_specs": specs,
        "weights_by_class": {cls: [int(v) for v in selected_weights[i].tolist()] for i, cls in enumerate(CLASSES)},
        "metrics": split_metrics,
        "note": "Snapshot C24 parameters are fixed. Only the 30min final membrane readout is trained on train and selected on validation. Test metrics are reported after selection and are not used for candidate selection.",
    }
    (RESULTS / "final_layer_selected_params.json").write_text(json.dumps(selected, indent=2), encoding="utf-8")
    print(
        "[search] selected "
        f"id={best_payload['candidate_id']} "
        f"val_acc={split_metrics['val']['accuracy']:.4f} "
        f"test_acc={split_metrics['test']['accuracy']:.4f}",
        flush=True,
    )


def snapshot_baseline_metrics() -> None:
    dumps = load_snapshot_dumps()
    rows = []
    payload = {}
    for split in SPLITS:
        chunks = build_chunks(dumps[split])
        true = []
        maj_pred = []
        avg_pred = []
        for chunk in chunks:
            true.append(int(chunk["class_id"]))
            pred_counts = [0, 0, 0, 0]
            mem_sum = [0, 0, 0, 0]
            for row in chunk["snapshots"]:
                pred_counts[safe_int(row["snapshot_pred_class"])] += 1
                for i, cls in enumerate(CLASSES):
                    mem_sum[i] += safe_int(row[f"class_mem_{cls}"])
            maj_pred.append(int(max(range(4), key=lambda i: (pred_counts[i], -i))))
            avg_pred.append(int(max(range(4), key=lambda i: (mem_sum[i], -i))))
            rows.append(
                {
                    "split": split,
                    "case_id": chunk["case_id"],
                    "class_label": chunk["class_label"],
                    "record_id": chunk["record_id"],
                    "chunk_id": chunk["chunk_id"],
                    "majority_pred_class": maj_pred[-1],
                    "majority_pred_label": CLASSES[maj_pred[-1]],
                    "avg_mem_pred_class": avg_pred[-1],
                    "avg_mem_pred_label": CLASSES[avg_pred[-1]],
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
        y = np.array(true, dtype=np.int64)
        payload[split] = {
            "majority_vote": metrics_from_pred(y, np.array(maj_pred, dtype=np.int64)),
            "average_class_mem": metrics_from_pred(y, np.array(avg_pred, dtype=np.int64)),
        }
    write_csv(RESULTS / "snapshot_baseline_predictions.csv", rows)
    (RESULTS / "snapshot_baseline_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("[baseline] wrote snapshot baseline metrics", flush=True)


def write_manifest_summary() -> None:
    rows = load_manifest()
    counts = Counter((row["split"], row["class_label"]) for row in rows)
    summary = []
    for split in SPLITS:
        for cls in CLASSES:
            summary.append({"split": split, "class_label": cls, "chunk_count": counts[(split, cls)], "snapshot_count": counts[(split, cls)] * SNAPSHOTS_PER_CHUNK})
    write_csv(RESULTS / "dataset_split_summary.csv", summary)


def main() -> None:
    parser = argparse.ArgumentParser(description="30min final membrane layer pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_dump = sub.add_parser("dump", help="generate 60s Snapshot C24 dumps from 30min chunks")
    p_dump.add_argument("--force", action="store_true")
    p_dump.add_argument("--workers", type=int, default=None)
    sub.add_parser("baseline", help="compute majority/average Snapshot baselines")
    sub.add_parser("search", help="train/validation final membrane search and one-time selected test report")
    sub.add_parser("all-python", help="run dump, baselines, and Python final-layer search")

    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    write_manifest_summary()
    if args.cmd == "dump":
        generate_snapshot_dumps(force=args.force, workers=args.workers)
    elif args.cmd == "baseline":
        snapshot_baseline_metrics()
    elif args.cmd == "search":
        run_search()
    elif args.cmd == "all-python":
        generate_snapshot_dumps(force=False, workers=args.workers)
        snapshot_baseline_metrics()
        run_search()


if __name__ == "__main__":
    main()
