from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "final_membrane_v2_snn"
OLD_DUMP_PREFIX = "HEAD:results/final_membrane_30min_recordwise"

CLASSES = ["NSR", "CHF", "ARR", "AFF"]
CLASS_TO_ID = {name: idx for idx, name in enumerate(CLASSES)}
SPLITS = ["train", "val", "test"]

GIT_CANDIDATES = [
    REPO / ".git" / "unused",
    Path(r"C:\Users\YangGeon\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"),
    Path(r"C:\Users\YangGeon\AppData\Local\GitHubDesktop\app-3.6.1\resources\app\git\cmd\git.exe"),
]

EERG_GATE = [5042413, 1853587, -6346411, -825955]
EERG_APPLIED = [4717413, -4196413, 2653589, -1775955]
EERG_LIKE = EERG_GATE[:]

WINDOW_FIELDS = [
    "case_id",
    "split",
    "class_label",
    "class_id",
    "record_id",
    "chunk_id",
    "balanced_index",
    "chunk_file",
    "snapshot_id",
    "snapshot_pred_class",
    "snapshot_pred_label",
    "pred_valid",
    "class_mem_NSR",
    "class_mem_CHF",
    "class_mem_ARR",
    "class_mem_AFF",
    "beat_count",
    "pnn_match_count",
    "pnn_mismatch_count",
    "dscr_flip_count",
    "dscr_slope_count",
    "ram_code_sum",
    "ram_code_count",
    "rdm_valid_count",
    "rdm_code_sum",
    "ectopic_pair_count",
    "qrs_maf_count",
    "qrs_width_abn_count",
    "qrs_complex_abn_count",
    "qrs_energy_abn_count",
    "rbbb_delay_like_count",
    "rbbb_delay_applied_count",
    "pre_qrs_bump_count",
    "abnormal_evidence_count",
    "rhythm_irregular_evidence_count",
    "morphology_evidence_count",
    "pnn_decision_count",
    "pnn_mismatch_rate_bp",
    "rdm_avg_code_q8",
    "ram_avg_code_q8",
    "qrs_maf_rate_bp",
    "v2_eerg_like_removed",
]

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
    "ectopic_pair_count",
    "qrs_maf_count",
    "qrs_width_abn_count",
    "qrs_complex_abn_count",
    "qrs_energy_abn_count",
    "rbbb_delay_like_count",
    "rbbb_delay_applied_count",
    "pre_qrs_bump_count",
    "abnormal_evidence_count",
    "rhythm_irregular_evidence_count",
    "morphology_evidence_count",
]


def find_git() -> Path:
    for candidate in GIT_CANDIDATES:
        if candidate.exists() and candidate.name.lower() == "git.exe":
            return candidate
    return Path("git")


def read_csv_text(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def read_csv_file(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", newline="", encoding="utf-8", errors="replace") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def safe_int(value: Any, default: int = 0) -> int:
    if value in ("", None):
        return default
    return int(float(value))


def ge_pct(num: int, den: int, pct: int) -> bool:
    return den != 0 and num * 100 >= den * pct


def le_pct(num: int, den: int, pct: int) -> bool:
    return den != 0 and num * 100 <= den * pct


def le_avg(sum_value: int, count: int, threshold: int) -> bool:
    return count != 0 and sum_value <= count * threshold


def eerg_like_from_old_row(row: dict[str, str]) -> bool:
    return (
        safe_int(row.get("rbbb_delay_like_count")) == 0
        and safe_int(row.get("eerg_pre_qrs_bump_count")) >= 1
        and (safe_int(row.get("eerg_early_count")) >= 10 or safe_int(row.get("eerg_ecp_count")) >= 3)
        and le_pct(safe_int(row.get("eerg_pnn_mismatch_count")), safe_int(row.get("eerg_pnn_decision_count")), 15)
        and le_avg(safe_int(row.get("eerg_rdm_code_sum")), safe_int(row.get("eerg_rdm_valid_count")), 5)
    )


def v2_scores_from_old_row(row: dict[str, str]) -> tuple[list[int], int]:
    scores = [safe_int(row[f"class_mem_{cls}"]) for cls in CLASSES]
    if safe_int(row.get("eerg_applied_count")) > 0:
        for idx in range(4):
            scores[idx] -= EERG_GATE[idx] + EERG_APPLIED[idx]
    removed_like = int(eerg_like_from_old_row(row))
    if removed_like:
        for idx in range(4):
            scores[idx] -= EERG_LIKE[idx]
    return scores, removed_like


def argmax4(values: list[int]) -> int:
    best = 0
    for idx in range(1, 4):
        if values[idx] > values[best]:
            best = idx
    return best


def load_old_dump_from_git(split: str) -> list[dict[str, str]]:
    git = find_git()
    object_name = f"{OLD_DUMP_PREFIX}/snapshot_dump_{split}.csv"
    proc = subprocess.run(
        [str(git), "show", object_name],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
        errors="replace",
        check=True,
    )
    return read_csv_text(proc.stdout)


def make_v2_window_dump(split: str) -> list[dict[str, Any]]:
    out_path = RESULTS / f"window_dump_{split}.csv"
    if out_path.exists():
        return read_csv_file(out_path)
    old_rows = load_old_dump_from_git(split)
    new_rows: list[dict[str, Any]] = []
    for old in old_rows:
        scores, removed_like = v2_scores_from_old_row(old)
        pred = argmax4(scores)
        row: dict[str, Any] = {}
        for field in WINDOW_FIELDS:
            if field.startswith("class_mem_"):
                continue
            row[field] = old.get(field, "")
        row["snapshot_pred_class"] = pred
        row["snapshot_pred_label"] = CLASSES[pred]
        row["pred_valid"] = old.get("pred_valid", "1")
        for idx, cls in enumerate(CLASSES):
            row[f"class_mem_{cls}"] = scores[idx]
        row["v2_eerg_like_removed"] = removed_like
        if not row.get("snapshot_id"):
            row["snapshot_id"] = old.get("snapshot_id", "")
        new_rows.append(row)
    write_csv(out_path, new_rows, WINDOW_FIELDS)
    return new_rows


@dataclass
class Chunk:
    case_id: str
    split: str
    class_id: int
    class_label: str
    record_id: str
    chunk_id: str
    chunk_file: str
    pred_count: list[int]
    mem_sum: list[int]
    mem_max: list[int]
    feature_sum: dict[str, int]

    @property
    def base_pred(self) -> int:
        return argmax4(self.pred_count)

    @property
    def base_count(self) -> int:
        return self.pred_count[self.base_pred]

    @property
    def second_count(self) -> int:
        ordered = sorted(self.pred_count, reverse=True)
        return ordered[1]


def build_chunks(rows: Iterable[dict[str, Any]]) -> list[Chunk]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["case_id"])].append(row)
    chunks: list[Chunk] = []
    for case_id, group in sorted(grouped.items(), key=lambda item: safe_int(item[0])):
        group.sort(key=lambda row: safe_int(row.get("snapshot_id")))
        first = group[0]
        pred_count = [0, 0, 0, 0]
        mem_sum = [0, 0, 0, 0]
        mem_max = [-(1 << 62)] * 4
        feature_sum = {field: 0 for field in FEATURE_SUM_FIELDS}
        for row in group:
            pred_count[safe_int(row["snapshot_pred_class"])] += 1
            for idx, cls in enumerate(CLASSES):
                mem = safe_int(row[f"class_mem_{cls}"])
                mem_sum[idx] += mem
                mem_max[idx] = max(mem_max[idx], mem)
            for field in FEATURE_SUM_FIELDS:
                feature_sum[field] += safe_int(row.get(field))
        chunks.append(
            Chunk(
                case_id=case_id,
                split=str(first["split"]),
                class_id=safe_int(first["class_id"]),
                class_label=str(first["class_label"]),
                record_id=str(first.get("record_id", "")),
                chunk_id=str(first.get("chunk_id", "")),
                chunk_file=str(first.get("chunk_file", "")),
                pred_count=pred_count,
                mem_sum=mem_sum,
                mem_max=mem_max,
                feature_sum=feature_sum,
            )
        )
    return chunks


def metric_for_predictions(chunks: list[Chunk], predictions: dict[str, int]) -> dict[str, Any]:
    cm = [[0 for _ in CLASSES] for _ in CLASSES]
    for chunk in chunks:
        cm[chunk.class_id][predictions[chunk.case_id]] += 1
    total = sum(sum(row) for row in cm)
    correct = sum(cm[idx][idx] for idx in range(4))
    per_class: dict[str, dict[str, float | int]] = {}
    for idx, cls in enumerate(CLASSES):
        tp = cm[idx][idx]
        fp = sum(cm[r][idx] for r in range(4) if r != idx)
        fn = sum(cm[idx][c] for c in range(4) if c != idx)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[cls] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(cm[idx])}
    recalls = [float(per_class[cls]["recall"]) for cls in CLASSES]
    return {
        "correct": correct,
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": sum(float(per_class[cls]["f1"]) for cls in CLASSES) / 4.0,
        "balanced_accuracy": sum(recalls) / 4.0,
        "min_recall": min(recalls) if recalls else 0.0,
        "recall_range": (max(recalls) - min(recalls)) if recalls else 0.0,
        "per_class": per_class,
        "confusion_matrix": cm,
    }


def majority_predictions(chunks: list[Chunk]) -> dict[str, int]:
    return {chunk.case_id: chunk.base_pred for chunk in chunks}


def score_sum_predictions(chunks: list[Chunk]) -> dict[str, int]:
    return {chunk.case_id: argmax4(chunk.mem_sum) for chunk in chunks}


def mem_base(chunk: Chunk, params: dict[str, Any]) -> list[int]:
    vote_shift = params["vote_shift"]
    mem_shift = params["mem_shift"]
    use_mem = params["use_mem"]
    final = [params[f"bias_{cls}"] for cls in CLASSES]
    for idx in range(4):
        final[idx] += chunk.pred_count[idx] << vote_shift
        if use_mem == "sum":
            final[idx] += chunk.mem_sum[idx] >> mem_shift
        elif use_mem == "max":
            final[idx] += chunk.mem_max[idx] >> mem_shift
    return final


def candidate_predict(chunk: Chunk, params: dict[str, Any]) -> tuple[int, list[int], dict[str, int]]:
    mem = mem_base(chunk, params)
    flags: dict[str, int] = {}

    base = argmax4(mem) if params["base_from"] == "mem" else chunk.base_pred
    counts = chunk.pred_count
    fs = chunk.feature_sum
    nsr_arr_margin = counts[0] - counts[2]
    chf_aff_margin = counts[1] - counts[3]
    arr_aff_margin = counts[2] - counts[3]
    chf_nsr_margin = counts[1] - counts[0]

    aff_low_rescue = (
        base == 1
        and params.get("aff_low_enable", 0)
        and fs["abnormal_evidence_count"] <= params["aff_low_abn_le"]
        and fs["morphology_evidence_count"] <= params["aff_low_morph_le"]
        and fs["rbbb_delay_like_count"] <= params["aff_low_rbbb_le"]
        and (
            (
                fs["rdm_valid_count"] > 0
                and fs["rdm_code_sum"] >= fs["rdm_valid_count"] * params["aff_low_rdm_ge"]
            )
            or (
                params.get("aff_low_allow_zero_rdm", 0)
                and fs["rdm_valid_count"] == 0
                and fs["rdm_code_sum"] == 0
                and fs["rhythm_irregular_evidence_count"] <= params.get("aff_low_zero_rhythm_le", 0)
                and fs["qrs_maf_count"] <= params.get("aff_low_zero_qrs_le", 0)
                and fs["pre_qrs_bump_count"] <= params.get("aff_low_zero_pre_le", 0)
            )
        )
        and counts[1] >= params["aff_low_chf_count_ge"]
    )
    if aff_low_rescue:
        mem[3] += params["aff_low_boost"]
        mem[1] -= params["aff_low_inhibit_chf"]
    flags["aff_low_rescue"] = int(aff_low_rescue)

    nsr_from_chf_rescue = (
        base == 1
        and counts[0] >= params["nsr_from_chf_nsr_count_ge"]
        and fs["abnormal_evidence_count"] <= params["nsr_from_chf_abn_le"]
        and fs["qrs_maf_count"] <= params["nsr_from_chf_qrs_le"]
        and fs["rbbb_delay_like_count"] <= params["nsr_from_chf_rbbb_le"]
        and fs["morphology_evidence_count"] <= params["nsr_from_chf_morph_le"]
    )
    if nsr_from_chf_rescue:
        mem[0] += params["nsr_from_chf_boost"]
        mem[1] -= params["nsr_from_chf_inhibit_chf"]
    flags["nsr_from_chf_rescue"] = int(nsr_from_chf_rescue)

    chf_from_aff_rescue = (
        base == 3
        and counts[1] >= params["chf_from_aff_chf_count_ge"]
        and fs["morphology_evidence_count"] <= params["chf_from_aff_morph_le"]
        and fs["qrs_maf_count"] <= params["chf_from_aff_qrs_le"]
        and fs["rbbb_delay_like_count"] <= params["chf_from_aff_rbbb_le"]
    )
    if chf_from_aff_rescue:
        mem[1] += params["chf_from_aff_boost"]
        mem[3] -= params["chf_from_aff_inhibit_aff"]
    flags["chf_from_aff_rescue"] = int(chf_from_aff_rescue)

    strong_nsr = (
        base == 0
        and (
            counts[0] >= params["strong_nsr_count_ge"]
            or (
                nsr_arr_margin >= params["strong_nsr_margin_ge"]
                and fs["morphology_evidence_count"] <= params["strong_nsr_morph_le"]
                and fs["qrs_maf_count"] <= params["strong_nsr_qrs_le"]
            )
        )
    )
    strong_chf = (
        base == 1
        and (
            counts[1] >= params["strong_chf_count_ge"]
            or chf_aff_margin >= params["strong_chf_margin_ge"]
        )
    )
    flags["strong_nsr"] = int(strong_nsr)
    flags["strong_chf"] = int(strong_chf)

    arr_rescue = (
        base in (0, 1, 3)
        and not strong_nsr
        and counts[2] >= params["arr_count_ge"]
        and counts[3] <= params.get("arr_aff_count_le", 99)
        and nsr_arr_margin <= params["arr_nsr_margin_le"]
        and fs["morphology_evidence_count"] >= params["arr_morph_ge"]
        and fs["qrs_maf_count"] >= params["arr_qrs_ge"]
        and fs["rbbb_delay_like_count"] >= params["arr_rbbb_ge"]
        and fs["pre_qrs_bump_count"] >= params["arr_pre_ge"]
    )
    if arr_rescue:
        mem[2] += params["arr_boost"]
        mem[0] -= params["arr_inhibit_nsr"]
        mem[1] -= params["arr_inhibit_chf"]
        mem[3] -= params.get("arr_inhibit_aff", 0)
    flags["arr_rescue"] = int(arr_rescue)

    arr_over_aff = (
        base == 3
        and counts[2] >= params["arr_aff_arr_count_ge"]
        and fs["qrs_maf_count"] >= params["arr_aff_qrs_ge"]
        and fs["morphology_evidence_count"] >= params["arr_aff_morph_ge"]
    )
    if arr_over_aff:
        mem[2] += params["arr_aff_boost"]
        mem[3] -= params["arr_aff_aff_inh"]
    flags["arr_over_aff"] = int(arr_over_aff)

    aff_rescue = (
        base in (1, 2)
        and not strong_chf
        and counts[2] < params["aff_block_arr_count_ge"]
        and counts[3] >= params["aff_count_ge"]
        and chf_aff_margin <= params["aff_chf_margin_le"]
        and fs["rhythm_irregular_evidence_count"] >= params["aff_rhythm_ge"]
        and fs["ectopic_pair_count"] >= params["aff_ecp_ge"]
        and fs["ectopic_pair_count"] <= params.get("aff_ecp_le", 999999)
    )
    if aff_rescue:
        mem[3] += params["aff_boost"]
        mem[1] -= params["aff_inhibit_chf"]
        mem[2] -= params["aff_inhibit_arr"]
    flags["aff_rescue"] = int(aff_rescue)

    arr_aff_boundary = (
        base in (2, 3)
        and counts[3] >= params["aff_boundary_count_ge"]
        and arr_aff_margin <= params["arr_aff_margin_le"]
        and fs["pnn_mismatch_count"] >= params["aff_pnn_ge"]
        and fs["rbbb_delay_like_count"] <= params["aff_rbbb_le"]
    )
    if arr_aff_boundary:
        mem[3] += params["aff_boundary_boost"]
        mem[2] -= params["aff_boundary_inhibit_arr"]
    flags["arr_aff_boundary"] = int(arr_aff_boundary)

    if strong_nsr:
        mem[0] += params["strong_nsr_boost"]
        mem[2] -= params["strong_nsr_inhibit_arr"]
    if strong_chf:
        mem[1] += params["strong_chf_boost"]
        mem[3] -= params["strong_chf_inhibit_aff"]

    arr_low_rescue = (
        base in (0, 1, 3)
        and counts[2] >= params["arr_low_count_ge"]
        and counts[3] <= params.get("arr_low_aff_count_le", 99)
        and fs["pre_qrs_bump_count"] >= params["arr_low_pre_ge"]
        and fs["qrs_maf_count"] >= params["arr_low_qrs_ge"]
        and fs["rbbb_delay_like_count"] >= params["arr_low_rbbb_ge"]
        and fs["morphology_evidence_count"] >= params["arr_low_morph_ge"]
        and fs["abnormal_evidence_count"] >= params["arr_low_abn_ge"]
    )
    if arr_low_rescue:
        mem[2] += params["arr_low_boost"]
        mem[0] -= params["arr_low_inhibit_nsr"]
        mem[1] -= params["arr_low_inhibit_chf"]
        mem[3] -= params["arr_low_inhibit_aff"]
    flags["arr_low_rescue"] = int(arr_low_rescue)

    arr_silent_rescue = (
        base == 0
        and counts[0] >= params.get("arr_silent_nsr_count_ge", 99)
        and counts[2] <= params.get("arr_silent_arr_count_le", -1)
        and fs["abnormal_evidence_count"] >= params.get("arr_silent_abn_ge", 999999)
        and fs["abnormal_evidence_count"] <= params.get("arr_silent_abn_le", -1)
        and fs["morphology_evidence_count"] >= params.get("arr_silent_morph_ge", 999999)
        and fs["morphology_evidence_count"] <= params.get("arr_silent_morph_le", -1)
        and fs["qrs_maf_count"] <= params.get("arr_silent_qrs_le", -1)
        and fs["rbbb_delay_like_count"] <= params.get("arr_silent_rbbb_le", -1)
        and fs["pnn_mismatch_count"] >= params.get("arr_silent_pnn_ge", 999999)
        and fs["ectopic_pair_count"] >= params.get("arr_silent_ecp_ge", 999999)
        and fs["rdm_code_sum"] >= params.get("arr_silent_rdm_ge", 999999)
        and fs["rdm_code_sum"] <= params.get("arr_silent_rdm_le", -1)
    )
    if arr_silent_rescue:
        mem[2] += params.get("arr_silent_boost", 0)
        mem[0] -= params.get("arr_silent_inhibit_nsr", 0)
    flags["arr_silent_rescue"] = int(arr_silent_rescue)

    return argmax4(mem), mem, flags


def apply_candidate(chunks: list[Chunk], params: dict[str, Any]) -> tuple[dict[str, int], dict[str, dict[str, Any]]]:
    pred: dict[str, int] = {}
    details: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        p, mem, flags = candidate_predict(chunk, params)
        pred[chunk.case_id] = p
        details[chunk.case_id] = {
            "final_mem_NSR": mem[0],
            "final_mem_CHF": mem[1],
            "final_mem_ARR": mem[2],
            "final_mem_AFF": mem[3],
            **flags,
        }
    return pred, details


def candidate_grid() -> Iterable[dict[str, Any]]:
    base_common = {
        "base_from": "majority",
        "use_mem": "none",
        "vote_shift": 0,
        "mem_shift": 24,
        "bias_NSR": 0,
        "bias_CHF": 0,
        "bias_ARR": 0,
        "bias_AFF": 0,
        "strong_nsr_count_ge": 27,
        "strong_chf_count_ge": 27,
        "strong_nsr_margin_ge": 18,
        "strong_chf_margin_ge": 16,
        "strong_nsr_morph_le": 160,
        "strong_nsr_qrs_le": 80,
        "strong_nsr_boost": 4096,
        "strong_nsr_inhibit_arr": 2048,
        "strong_chf_boost": 4096,
        "strong_chf_inhibit_aff": 2048,
        "aff_boundary_count_ge": 4,
        "arr_aff_margin_le": 8,
        "aff_pnn_ge": 350,
        "aff_rbbb_le": 60,
        "aff_boundary_boost": 4096,
        "aff_boundary_inhibit_arr": 1024,
        "aff_low_enable": 0,
        "aff_low_abn_le": 0,
        "aff_low_morph_le": 0,
        "aff_low_rbbb_le": 0,
        "aff_low_rdm_ge": 99,
        "aff_low_chf_count_ge": 31,
        "aff_low_boost": 0,
        "aff_low_inhibit_chf": 0,
        "arr_aff_arr_count_ge": 99,
        "arr_aff_qrs_ge": 999999,
        "arr_aff_morph_ge": 999999,
        "arr_aff_boost": 0,
        "arr_aff_aff_inh": 0,
        "aff_block_arr_count_ge": 99,
        "arr_low_count_ge": 99,
        "arr_low_pre_ge": 999999,
        "arr_low_qrs_ge": 999999,
        "arr_low_rbbb_ge": 999999,
        "arr_low_morph_ge": 999999,
        "arr_low_abn_ge": 999999,
        "arr_low_boost": 0,
        "arr_low_inhibit_nsr": 0,
        "arr_low_inhibit_chf": 0,
        "arr_low_inhibit_aff": 0,
        "nsr_from_chf_nsr_count_ge": 99,
        "nsr_from_chf_abn_le": 0,
        "nsr_from_chf_qrs_le": 0,
        "nsr_from_chf_rbbb_le": 0,
        "nsr_from_chf_morph_le": 0,
        "nsr_from_chf_boost": 0,
        "nsr_from_chf_inhibit_chf": 0,
        "chf_from_aff_chf_count_ge": 99,
        "chf_from_aff_morph_le": 0,
        "chf_from_aff_qrs_le": 0,
        "chf_from_aff_rbbb_le": 0,
        "chf_from_aff_boost": 0,
        "chf_from_aff_inhibit_aff": 0,
    }
    arr_space = [
        {
            "arr_count_ge": c,
            "arr_nsr_margin_le": m,
            "arr_morph_ge": morph,
            "arr_qrs_ge": qrs,
            "arr_rbbb_ge": rbbb,
            "arr_pre_ge": pre,
            "arr_boost": boost,
            "arr_inhibit_nsr": inhib_nsr,
            "arr_inhibit_chf": inhib_chf,
        }
        for c in [3, 4, 5, 6, 8, 10, 12]
        for m in [8, 12, 16, 20, 24, 30]
        for morph in [80, 120, 180, 250, 350, 500]
        for qrs in [40, 80, 120, 180, 250]
        for rbbb in [0, 5, 10, 15, 20, 30, 50]
        for pre in [0, 1800, 2200, 2600, 3000]
        for boost in [4096, 8192, 16384, 32768]
        for inhib_nsr in [0, 2048, 4096, 8192, 16384]
        for inhib_chf in [0, 2048, 4096, 8192]
    ]
    aff_space = [
        {
            "aff_count_ge": c,
            "aff_chf_margin_le": m,
            "aff_rhythm_ge": rhythm,
            "aff_ecp_ge": ecp,
            "aff_boost": boost,
            "aff_inhibit_chf": inhib_chf,
            "aff_inhibit_arr": inhib_arr,
        }
        for c in [1, 2, 4, 6, 8, 10, 12]
        for m in [4, 8, 12, 16, 20]
        for rhythm in [1200, 1600, 2000, 2400]
        for ecp in [20, 50, 80, 120, 180]
        for boost in [4096, 8192, 16384, 32768]
        for inhib_chf in [0, 2048, 4096, 8192]
        for inhib_arr in [0, 1024, 2048, 4096]
    ]
    idx = 0
    # Keep the product bounded by pairing broad ARR search with a compact AFF center
    # and then broad AFF search with a compact ARR center.
    aff_center = {
        "aff_count_ge": 4,
        "aff_chf_margin_le": 12,
        "aff_block_arr_count_ge": 99,
        "aff_rhythm_ge": 1800,
        "aff_ecp_ge": 50,
        "aff_boost": 8192,
        "aff_inhibit_chf": 4096,
        "aff_inhibit_arr": 1024,
    }
    arr_center = {
        "arr_count_ge": 4,
        "arr_nsr_margin_le": 20,
        "arr_morph_ge": 120,
        "arr_qrs_ge": 80,
        "arr_rbbb_ge": 10,
        "arr_pre_ge": 2200,
        "arr_boost": 8192,
        "arr_inhibit_nsr": 4096,
        "arr_inhibit_chf": 2048,
    }
    for arr in arr_space:
        idx += 1
        yield {"candidate_id": f"arr_sweep_{idx:07d}", **base_common, **arr, **aff_center}
    for aff in aff_space:
        idx += 1
        yield {"candidate_id": f"aff_sweep_{idx:07d}", **base_common, **arr_center, **aff}
    # Scale/bias ablations around the center.
    for use_mem in ["none", "sum", "max"]:
        for base_from in ["majority", "mem"]:
            for vote_shift in [7, 8, 9, 10]:
                for mem_shift in [20, 22, 24, 26, 28]:
                    for bias_arr in [0, 512, 1024, 2048, 4096]:
                        for bias_aff in [0, 512, 1024, 2048, 4096]:
                            idx += 1
                            yield {
                                "candidate_id": f"scale_{idx:07d}",
                                **base_common,
                                **arr_center,
                                **aff_center,
                                "use_mem": use_mem,
                                "base_from": base_from,
                                "vote_shift": vote_shift,
                                "mem_shift": mem_shift,
                                "bias_ARR": bias_arr,
                                "bias_AFF": bias_aff,
                            }


def balanced_candidate_grid() -> Iterable[dict[str, Any]]:
    idx = 0
    base = {
        "base_from": "majority",
        "use_mem": "none",
        "vote_shift": 0,
        "mem_shift": 24,
        "bias_NSR": 0,
        "bias_CHF": 0,
        "bias_ARR": 0,
        "bias_AFF": 0,
        "strong_nsr_count_ge": 99,
        "strong_chf_count_ge": 99,
        "strong_nsr_margin_ge": 99,
        "strong_chf_margin_ge": 99,
        "strong_nsr_morph_le": 0,
        "strong_nsr_qrs_le": 0,
        "strong_nsr_boost": 0,
        "strong_nsr_inhibit_arr": 0,
        "strong_chf_boost": 0,
        "strong_chf_inhibit_aff": 0,
        "aff_boundary_count_ge": 99,
        "arr_aff_margin_le": -99,
        "aff_pnn_ge": 999999,
        "aff_rbbb_le": -1,
        "aff_boundary_boost": 0,
        "aff_boundary_inhibit_arr": 0,
        "aff_count_ge": 6,
        "aff_chf_margin_le": 14,
        "aff_block_arr_count_ge": 15,
        "aff_rhythm_ge": 1800,
        "aff_ecp_ge": 0,
        "aff_morph_ge": 150,
        "aff_boost": 25,
        "aff_inhibit_chf": 15,
        "aff_inhibit_arr": 0,
        "arr_aff_arr_count_ge": 99,
        "arr_aff_qrs_ge": 500,
        "arr_aff_morph_ge": 1000,
        "arr_aff_boost": 0,
        "arr_aff_aff_inh": 0,
        "arr_low_count_ge": 9,
        "arr_low_pre_ge": 1800,
        "arr_low_qrs_ge": 40,
        "arr_low_rbbb_ge": 0,
        "arr_low_morph_ge": 350,
        "arr_low_abn_ge": 0,
        "arr_low_boost": 30,
        "arr_low_inhibit_nsr": 20,
        "arr_low_inhibit_chf": 10,
        "arr_low_inhibit_aff": 5,
        "nsr_from_chf_nsr_count_ge": 10,
        "nsr_from_chf_abn_le": 150,
        "nsr_from_chf_qrs_le": 30,
        "nsr_from_chf_rbbb_le": 2,
        "nsr_from_chf_morph_le": 1500,
        "nsr_from_chf_boost": 30,
        "nsr_from_chf_inhibit_chf": 20,
        "chf_from_aff_chf_count_ge": 3,
        "chf_from_aff_morph_le": 200,
        "chf_from_aff_qrs_le": 80,
        "chf_from_aff_rbbb_le": 5,
        "chf_from_aff_boost": 30,
        "chf_from_aff_inhibit_aff": 20,
    }
    for aff_low_abn_le in [10, 20, 35, 50]:
        for aff_low_morph_le in [5, 10, 20, 40]:
            for aff_low_rdm_ge in [9, 10, 11, 12]:
                for aff_low_chf_count_ge in [20, 24, 26]:
                    for arr_count_ge in [4, 5, 8, 10]:
                        for arr_morph_ge in [80, 100, 120, 180, 250]:
                            for arr_qrs_ge in [40, 60, 80, 120]:
                                for arr_rbbb_ge in [5, 8, 10, 15, 20]:
                                    for arr_pre_ge in [1800, 2200, 2600, 3000]:
                                        idx += 1
                                        yield {
                                            "candidate_id": f"balanced_{idx:07d}",
                                            **base,
                                            "aff_low_enable": 1,
                                            "aff_low_abn_le": aff_low_abn_le,
                                            "aff_low_morph_le": aff_low_morph_le,
                                            "aff_low_rbbb_le": 5,
                                            "aff_low_rdm_ge": aff_low_rdm_ge,
                                            "aff_low_chf_count_ge": aff_low_chf_count_ge,
                                            "aff_low_boost": 40,
                                            "aff_low_inhibit_chf": 20,
                                            "arr_count_ge": arr_count_ge,
                                            "arr_nsr_margin_le": 99,
                                            "arr_morph_ge": arr_morph_ge,
                                            "arr_qrs_ge": arr_qrs_ge,
                                            "arr_rbbb_ge": arr_rbbb_ge,
                                            "arr_pre_ge": arr_pre_ge,
                                            "arr_boost": 30,
                                            "arr_inhibit_nsr": 20,
                                            "arr_inhibit_chf": 10,
                                            "arr_inhibit_aff": 5,
                                        }


def selection_key(train_m: dict[str, Any], val_m: dict[str, Any], candidate: dict[str, Any]) -> tuple[Any, ...]:
    # Prefer candidates that actually improve the validation bottleneck while
    # keeping train/validation from collapsing. Test is intentionally absent.
    return (
        train_m["accuracy"] >= 0.85 and val_m["accuracy"] >= 0.85,
        min(train_m["accuracy"], val_m["accuracy"]),
        val_m["macro_f1"],
        val_m["balanced_accuracy"],
        val_m["per_class"]["ARR"]["recall"],
        val_m["min_recall"],
        min(train_m["accuracy"], val_m["accuracy"]),
        -val_m["recall_range"],
        candidate.get("aff_low_rdm_ge", 0),
        candidate.get("arr_morph_ge", 0),
        -candidate_complexity(candidate),
    )


def candidate_complexity(candidate: dict[str, Any]) -> int:
    enabled = 0
    for name in [
        "arr_boost",
        "arr_inhibit_nsr",
        "arr_inhibit_chf",
        "aff_boost",
        "aff_inhibit_chf",
        "aff_inhibit_arr",
        "aff_boundary_boost",
        "aff_boundary_inhibit_arr",
        "strong_nsr_boost",
        "strong_chf_boost",
    ]:
        enabled += int(candidate.get(name, 0) != 0)
    enabled += int(candidate.get("use_mem") != "none")
    enabled += int(candidate.get("base_from") != "majority")
    return enabled


def split_chunks(splits: Iterable[str] | None = None) -> dict[str, list[Chunk]]:
    by_split: dict[str, list[Chunk]] = {}
    for split in (list(splits) if splits is not None else SPLITS):
        rows = make_v2_window_dump(split)
        by_split[split] = build_chunks(rows)
    return by_split


def write_metrics(path: Path, metrics: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def command_prepare(args: argparse.Namespace) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    splits = SPLITS if args.include_test else ["train", "val"]
    chunks = split_chunks(splits)
    audit_rows = []
    leakage = defaultdict(set)
    for split, split_chunks_ in chunks.items():
        for chunk in split_chunks_:
            leakage[(chunk.class_label, chunk.record_id)].add(split)
    for (class_label, record_id), splits in sorted(leakage.items()):
        audit_rows.append(
            {
                "class_label": class_label,
                "record_id": record_id,
                "splits": "|".join(sorted(splits)),
                "split_count": len(splits),
                "leakage": int(len(splits) > 1),
            }
        )
    write_csv(RESULTS / "record_split_audit.csv", audit_rows)
    summary_rows = []
    for split, split_chunks_ in chunks.items():
        counts = Counter(chunk.class_label for chunk in split_chunks_)
        for cls in CLASSES:
            summary_rows.append({"split": split, "class_label": cls, "chunks": counts[cls]})
    write_csv(RESULTS / "split_summary.csv", summary_rows)
    print(f"prepared window/chunk dumps under {RESULTS}")


def baseline_metrics(chunks: dict[str, list[Chunk]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split in chunks:
        split_chunks_ = chunks[split]
        out[split] = {
            "majority": metric_for_predictions(split_chunks_, majority_predictions(split_chunks_)),
            "score_sum": metric_for_predictions(split_chunks_, score_sum_predictions(split_chunks_)),
        }
    return out


def command_search(args: argparse.Namespace) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    chunks = split_chunks(["train", "val"])
    base = baseline_metrics(chunks)
    write_metrics(RESULTS / "baseline_metrics.json", base)
    train = chunks["train"]
    val = chunks["val"]

    selected: dict[str, Any] | None = None
    selected_train: dict[str, Any] | None = None
    selected_val: dict[str, Any] | None = None
    selected_key: tuple[Any, ...] | None = None
    top_rows: list[dict[str, Any]] = []

    grid = balanced_candidate_grid() if args.mode == "balanced" else candidate_grid()
    for idx, candidate in enumerate(grid, 1):
        train_pred, _ = apply_candidate(train, candidate)
        val_pred, _ = apply_candidate(val, candidate)
        train_m = metric_for_predictions(train, train_pred)
        val_m = metric_for_predictions(val, val_pred)
        key = selection_key(train_m, val_m, candidate)
        if selected_key is None or key > selected_key:
            selected = candidate
            selected_train = train_m
            selected_val = val_m
            selected_key = key
        top_rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "complexity": candidate_complexity(candidate),
                "train_accuracy": train_m["accuracy"],
                "train_correct": train_m["correct"],
                "train_macro_f1": train_m["macro_f1"],
                "train_arr_recall": train_m["per_class"]["ARR"]["recall"],
                "val_accuracy": val_m["accuracy"],
                "val_correct": val_m["correct"],
                "val_macro_f1": val_m["macro_f1"],
                "val_balanced_accuracy": val_m["balanced_accuracy"],
                "val_min_recall": val_m["min_recall"],
                "val_arr_recall": val_m["per_class"]["ARR"]["recall"],
                "params": json.dumps(candidate, sort_keys=True),
            }
        )
        if idx % 25000 == 0:
            assert selected_val is not None
            print(
                f"searched {idx}; best val={selected_val['correct']}/{selected_val['total']} "
                f"macro_f1={selected_val['macro_f1']:.4f}",
                flush=True,
            )
        if args.limit and idx >= args.limit:
            break

    top_rows.sort(
        key=lambda row: (
            row["val_macro_f1"],
            row["val_balanced_accuracy"],
            row["val_arr_recall"],
            row["val_min_recall"],
            row["train_accuracy"],
            -row["complexity"],
        ),
        reverse=True,
    )
    write_csv(RESULTS / "final_layer_search_top.csv", top_rows[:200])
    assert selected is not None and selected_train is not None and selected_val is not None
    selected_payload = {
        "selection_note": "Selected using train/validation only. Test is not evaluated by search.",
        "params": selected,
        "train_metrics": selected_train,
        "val_metrics": selected_val,
        "baseline": base,
        "chatgpt_55pro_used": True,
        "chatgpt_55pro_adopted": [
            "pairwise ARR rescue from weak NSR/CHF",
            "AFF rescue from weak CHF",
            "strong NSR/CHF guard",
            "integer accumulator, fixed add/subtract, comparator-only structure",
        ],
    }
    write_metrics(RESULTS / "selected_params_train_val_locked.json", selected_payload)
    write_metrics(RESULTS / "python_train_metrics.json", selected_train)
    write_metrics(RESULTS / "python_val_metrics.json", selected_val)
    print(
        f"selected {selected['candidate_id']} "
        f"train={selected_train['correct']}/{selected_train['total']} "
        f"val={selected_val['correct']}/{selected_val['total']} "
        f"val_macro_f1={selected_val['macro_f1']:.4f}",
        flush=True,
    )


def prediction_rows(chunks: list[Chunk], pred: dict[str, int], details: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in chunks:
        item = details[chunk.case_id]
        rows.append(
            {
                "case_id": chunk.case_id,
                "split": chunk.split,
                "class_label": chunk.class_label,
                "class_id": chunk.class_id,
                "record_id": chunk.record_id,
                "chunk_id": chunk.chunk_id,
                "chunk_file": chunk.chunk_file,
                "pred_count_NSR": chunk.pred_count[0],
                "pred_count_CHF": chunk.pred_count[1],
                "pred_count_ARR": chunk.pred_count[2],
                "pred_count_AFF": chunk.pred_count[3],
                "final_pred_class": pred[chunk.case_id],
                "final_pred_label": CLASSES[pred[chunk.case_id]],
                "correct": int(pred[chunk.case_id] == chunk.class_id),
                **item,
            }
        )
    return rows


def command_final_test(args: argparse.Namespace) -> None:
    lock = RESULTS / "FINAL_TEST_ONCE_OPENED.lock"
    if lock.exists() and not args.allow_rerun:
        raise SystemExit(f"final test lock exists: {lock}; pass --allow-rerun only for audit/reproduction")
    selected_path = RESULTS / "selected_params_train_val_locked.json"
    if not selected_path.exists():
        raise SystemExit("selected params missing; run search first")
    selected = json.loads(selected_path.read_text(encoding="utf-8"))["params"]
    chunks = split_chunks(SPLITS)
    all_metrics: dict[str, Any] = {}
    for split in SPLITS:
        pred, details = apply_candidate(chunks[split], selected)
        metrics = metric_for_predictions(chunks[split], pred)
        all_metrics[split] = metrics
        write_metrics(RESULTS / f"python_{split}_metrics.json", metrics)
        write_csv(RESULTS / f"python_{split}_predictions.csv", prediction_rows(chunks[split], pred, details))
    lock.write_text("Final held-out test opened by search_final_membrane_v2_snn.py final-test.\n", encoding="utf-8")
    write_metrics(RESULTS / "python_final_test_once_summary.json", all_metrics)
    print(
        "final-test "
        + " ".join(f"{split}={all_metrics[split]['correct']}/{all_metrics[split]['total']}" for split in SPLITS),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)
    p_prepare = sub.add_parser("prepare")
    p_prepare.add_argument("--include-test", action="store_true")
    p_prepare.set_defaults(func=command_prepare)
    p_search = sub.add_parser("search")
    p_search.add_argument("--limit", type=int, default=0)
    p_search.add_argument("--mode", choices=["full", "balanced"], default="full")
    p_search.set_defaults(func=command_search)
    p_test = sub.add_parser("final-test")
    p_test.add_argument("--allow-rerun", action="store_true")
    p_test.set_defaults(func=command_final_test)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
