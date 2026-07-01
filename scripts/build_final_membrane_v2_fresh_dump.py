from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
from pathlib import Path
from typing import Any

from snapshot_c24_rtl_exact import SnapshotFrontEnd, s12_from_hex_mem
from snapshot_c24_v2_search import CLASSES, install_score_mask
from search_final_membrane_v2_snn import RESULTS, WINDOW_FIELDS, write_csv


REPO = Path(__file__).resolve().parents[1]
DATASET = REPO / "fullrec_afe_30min_annotation_valid_balanced"
MANIFEST = DATASET / "annotation_valid_balanced_30min_manifest.csv"
WINDOW_SAMPLES = 60000
WINDOWS_PER_CHUNK = 30


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        return list(csv.DictReader(f))


def resolve_chunk(row: dict[str, str], dataset: Path) -> Path:
    raw = row["chunk_file"]
    path = Path(raw)
    if path.is_absolute():
        return path
    return dataset / path


def int_out(out: dict[str, Any], name: str) -> int:
    return int(out.get(name, 0))


def run_window(samples) -> dict[str, int]:
    install_score_mask({"EERG"})
    out = SnapshotFrontEnd().run_window(samples)
    row = {key: int_out(out, key) for key in out}
    return row


def process_chunk(job: dict[str, str]) -> list[dict[str, Any]]:
    split = job["split"]
    class_label = job["class_label"]
    class_id = CLASSES.index(class_label)
    balanced_index = job.get("balanced_index", "")
    case_id = job["case_id"]
    chunk_path = Path(job["resolved_chunk_file"])
    samples = s12_from_hex_mem(chunk_path)
    if samples.size < WINDOW_SAMPLES * WINDOWS_PER_CHUNK:
        raise ValueError(f"{chunk_path} has {samples.size} samples, expected at least {WINDOW_SAMPLES * WINDOWS_PER_CHUNK}")

    rows: list[dict[str, Any]] = []
    for snapshot_id in range(WINDOWS_PER_CHUNK):
        start = snapshot_id * WINDOW_SAMPLES
        out = run_window(samples[start : start + WINDOW_SAMPLES])
        pred = int(out["pred_class"])
        pnn_match = int_out(out, "pnn_match_count")
        pnn_mis = int_out(out, "pnn_mismatch_count")
        rdm_valid = int_out(out, "rdm_valid_count")
        rdm_sum = int_out(out, "rdm_code_sum")
        ram_count = int_out(out, "ram_code_count")
        ram_sum = int_out(out, "ram_code_sum")
        qrs_maf_valid = int_out(out, "qrs_maf_valid_count")
        qrs_maf = int_out(out, "qrs_maf_count")
        qrs_width = int_out(out, "qrs_width_abn_count")
        qrs_complex = int_out(out, "qrs_complex_abn_count")
        qrs_energy = int_out(out, "qrs_energy_abn_count")
        ectopic = int_out(out, "ectopic_pair_count")
        rbbb_like = int_out(out, "rbbb_delay_like_count")
        dscr_flip = int_out(out, "dscr_flip_count")
        pre_qrs = int_out(out, "pre_qrs_bump_count")
        abnormal = pnn_mis + ectopic + qrs_maf + qrs_width + qrs_complex + qrs_energy + rbbb_like
        rhythm = pnn_mis + rdm_sum + ectopic
        morphology = dscr_flip + qrs_maf + qrs_width + qrs_complex + qrs_energy + rbbb_like
        rows.append(
            {
                "case_id": case_id,
                "split": split,
                "class_label": class_label,
                "class_id": class_id,
                "record_id": job["record_id"],
                "chunk_id": job["chunk_id"],
                "balanced_index": balanced_index,
                "chunk_file": job["chunk_file"],
                "snapshot_id": snapshot_id,
                "snapshot_pred_class": pred,
                "snapshot_pred_label": CLASSES[pred],
                "pred_valid": int_out(out, "pred_valid"),
                "class_mem_NSR": int_out(out, "class_mem_NSR"),
                "class_mem_CHF": int_out(out, "class_mem_CHF"),
                "class_mem_ARR": int_out(out, "class_mem_ARR"),
                "class_mem_AFF": int_out(out, "class_mem_AFF"),
                "beat_count": int_out(out, "beat_count"),
                "pnn_match_count": pnn_match,
                "pnn_mismatch_count": pnn_mis,
                "dscr_flip_count": dscr_flip,
                "dscr_slope_count": int_out(out, "dscr_slope_count"),
                "ram_code_sum": ram_sum,
                "ram_code_count": ram_count,
                "rdm_valid_count": rdm_valid,
                "rdm_code_sum": rdm_sum,
                "ectopic_pair_count": ectopic,
                "qrs_maf_count": qrs_maf,
                "qrs_width_abn_count": qrs_width,
                "qrs_complex_abn_count": qrs_complex,
                "qrs_energy_abn_count": qrs_energy,
                "rbbb_delay_like_count": rbbb_like,
                "rbbb_delay_applied_count": int_out(out, "rbbb_delay_applied_count"),
                "pre_qrs_bump_count": pre_qrs,
                "abnormal_evidence_count": abnormal,
                "rhythm_irregular_evidence_count": rhythm,
                "morphology_evidence_count": morphology,
                "pnn_decision_count": pnn_match + pnn_mis,
                "pnn_mismatch_rate_bp": (pnn_mis * 10000 // (pnn_match + pnn_mis)) if (pnn_match + pnn_mis) else 0,
                "rdm_avg_code_q8": (rdm_sum * 256 // rdm_valid) if rdm_valid else 0,
                "ram_avg_code_q8": (ram_sum * 256 // ram_count) if ram_count else 0,
                "qrs_maf_rate_bp": (qrs_maf * 10000 // qrs_maf_valid) if qrs_maf_valid else 0,
                "v2_eerg_like_removed": 0,
            }
        )
    return rows


def build_jobs(splits: list[str], dataset: Path) -> list[dict[str, str]]:
    jobs = []
    split_case_id = {split: 0 for split in splits}
    for idx, row in enumerate(read_manifest(dataset / "annotation_valid_balanced_30min_manifest.csv")):
        if row["split"] not in splits:
            continue
        job = dict(row)
        job["row_index"] = str(idx)
        job["case_id"] = str(split_case_id[row["split"]])
        split_case_id[row["split"]] += 1
        job["resolved_chunk_file"] = str(resolve_chunk(row, dataset))
        jobs.append(job)
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fresh Snapshot V2 60s dumps from 30min chunks.")
    parser.add_argument("--dataset-root", default=str(DATASET))
    parser.add_argument("--out-dir", default=str(RESULTS))
    parser.add_argument("--splits", nargs="+", default=["train", "val"], choices=["train", "val", "test"])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--chunksize", type=int, default=1)
    args = parser.parse_args()

    dataset = Path(args.dataset_root)
    out_dir = Path(args.out_dir)
    jobs = build_jobs(args.splits, dataset)
    rows_by_split = {split: [] for split in args.splits}
    with mp.Pool(processes=args.workers) as pool:
        for idx, chunk_rows in enumerate(pool.imap_unordered(process_chunk, jobs, chunksize=args.chunksize), 1):
            rows_by_split[str(chunk_rows[0]["split"])].extend(chunk_rows)
            if idx % 4 == 0 or idx == len(jobs):
                print(f"fresh dump chunks {idx}/{len(jobs)}", flush=True)
    for split, rows in rows_by_split.items():
        rows.sort(key=lambda row: (int(row["case_id"]), int(row["snapshot_id"])))
        write_csv(out_dir / f"window_dump_{split}.csv", rows, WINDOW_FIELDS)
        print(f"{split}: wrote {len(rows)} windows", flush=True)


if __name__ == "__main__":
    mp.freeze_support()
    main()
