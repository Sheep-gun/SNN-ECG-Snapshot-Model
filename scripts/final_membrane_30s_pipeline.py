from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parents[0]
sys.path.insert(0, str(SCRIPT_DIR))

from snapshot_c24_rtl_exact import run_qrs_on_mem  # noqa: E402


CLASSES = ["NSR", "CHF", "ARR", "AFF"]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASSES)}
DATASET = REPO / "fullrec_afe_30s_annotation_valid_balanced"
MANIFEST = DATASET / "annotation_valid_balanced_manifest.csv"
RESULTS = REPO / "results" / "final_membrane_30s"
RTL_OUT = REPO / "rtl" / "final_membrane_layer.v"
TB_OUT = REPO / "sim" / "tb_final_membrane_layer_dataset.v"
XVLOG = Path(r"C:\Xilinx\Vivado\2020.2\bin\xvlog.bat")
XELAB = Path(r"C:\Xilinx\Vivado\2020.2\bin\xelab.bat")
XSIM = Path(r"C:\Xilinx\Vivado\2020.2\bin\xsim.bat")

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
BASE_DUMP_COLUMNS = [
    "case_id",
    "split",
    "class_label",
    "class_id",
    "record_id",
    "chunk_id",
    "chunk_file",
    "start_sample",
    "end_sample",
    "start_sec",
    "end_sec",
    "source_db",
    "pred_class",
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
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load_manifest() -> list[dict[str, str]]:
    rows = read_csv(MANIFEST)
    expected = {
        ("train", "NSR"): 270,
        ("train", "CHF"): 270,
        ("train", "ARR"): 270,
        ("train", "AFF"): 270,
        ("val", "NSR"): 134,
        ("val", "CHF"): 134,
        ("val", "ARR"): 134,
        ("val", "AFF"): 134,
        ("test", "NSR"): 135,
        ("test", "CHF"): 135,
        ("test", "ARR"): 135,
        ("test", "AFF"): 135,
    }
    counts = Counter((r["split"], r["class_label"]) for r in rows)
    if counts != expected:
        raise RuntimeError(f"unexpected split/class counts: {counts}")
    missing = []
    for r in rows:
        path = DATASET / r["new_chunk_file"]
        if not path.exists():
            missing.append(str(path))
    if missing:
        raise FileNotFoundError(f"missing chunk files: {missing[:5]}")
    return rows


def safe_int(value, default: int = 0) -> int:
    if value in ("", None):
        return default
    return int(float(value))


def bp(num: int, den: int) -> int:
    return int((num * 10000) // den) if den else 0


def q8_avg(total: int, den: int) -> int:
    return int((total * 256) // den) if den else 0


def dump_row(case_id: int, row: dict[str, str]) -> dict:
    chunk_path = DATASET / row["new_chunk_file"]
    feat = run_qrs_on_mem(chunk_path)
    pred = int(feat["pred_class"])
    pnn_dec = int(feat.get("pnn_match_count", 0)) + int(feat.get("pnn_mismatch_count", 0))
    rdm_valid = int(feat.get("rdm_valid_count", 0))
    ram_count = int(feat.get("ram_code_count", 0))
    beat_count = int(feat.get("beat_count", 0))
    rbbb_valid = int(feat.get("rbbb_delay_valid_count", 0))
    qrs_maf = int(feat.get("qrs_maf_count", 0))
    rbbb_like = int(feat.get("rbbb_delay_like_count", 0))
    pnn_mis = int(feat.get("pnn_mismatch_count", 0))
    rdm_ge50 = int(feat.get("rdm_ge50_count", 0))
    ect = int(feat.get("ectopic_pair_count", 0))
    morph = (
        qrs_maf
        + int(feat.get("qrs_width_abn_count", 0))
        + int(feat.get("qrs_complex_abn_count", 0))
        + int(feat.get("qrs_energy_abn_count", 0))
        + rbbb_like
    )
    rhythm = pnn_mis + rdm_ge50 + ect
    out = {
        "case_id": case_id,
        "split": row["split"],
        "class_label": row["class_label"],
        "class_id": CLASS_TO_ID[row["class_label"]],
        "record_id": row["record_id"],
        "chunk_id": row["chunk_id"],
        "chunk_file": row["new_chunk_file"],
        "start_sample": row["start_sample"],
        "end_sample": row["end_sample"],
        "start_sec": row["start_sec"],
        "end_sec": row["end_sec"],
        "source_db": row.get("source_db", ""),
        "pred_class": pred,
        "pred_label": CLASSES[pred],
        "pred_valid": int(feat.get("pred_valid", 0)),
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
    for col in MEM_COLUMNS:
        out[col] = int(feat[col])
    for col in FEATURE_COLUMNS:
        out[col] = int(feat.get(col, 0))
    return out


def generate_window_dumps(force: bool = False) -> None:
    rows = load_manifest()
    RESULTS.mkdir(parents=True, exist_ok=True)
    expected_by_split = {"train": 1080, "val": 536, "test": 540}
    if not force:
        reusable = True
        for split, n in expected_by_split.items():
            path = RESULTS / f"window_dump_{split}.csv"
            if not path.exists() or len(read_csv(path)) != n:
                reusable = False
        if reusable:
            print("[dump] existing complete window dumps found; use --force to regenerate", flush=True)
            return

    writers: dict[str, csv.DictWriter] = {}
    files = {}
    try:
        for split in ["train", "val", "test"]:
            path = RESULTS / f"window_dump_{split}.csv"
            f = path.open("w", newline="", encoding="utf-8-sig")
            files[split] = f
            w = csv.DictWriter(f, fieldnames=BASE_DUMP_COLUMNS, extrasaction="ignore")
            w.writeheader()
            writers[split] = w

        total = len(rows)
        for idx, row in enumerate(rows):
            out = dump_row(idx, row)
            writers[row["split"]].writerow(out)
            files[row["split"]].flush()
            if (idx + 1) % 25 == 0 or idx == total - 1:
                print(f"[dump] {idx + 1}/{total} {row['split']} {row['class_label']} {row['record_id']} {row['chunk_id']}", flush=True)
    finally:
        for f in files.values():
            f.close()


def load_dumps() -> dict[str, list[dict[str, str]]]:
    return {split: read_csv(RESULTS / f"window_dump_{split}.csv") for split in ["train", "val", "test"]}


def class_mems(row: dict[str, str]) -> list[int]:
    return [safe_int(row[f"class_mem_{c}"]) for c in CLASSES]


def top_class_and_margin(row: dict[str, str]) -> tuple[int, int]:
    mems = class_mems(row)
    order = sorted(range(4), key=lambda i: (-mems[i], i))
    return order[0], mems[order[0]] - mems[order[1]]


def build_feature_specs() -> list[dict]:
    specs: list[dict] = [{"name": "bias", "kind": "always"}]
    margin_ths = [0, 1_000_000, 2_500_000, 5_000_000, 10_000_000, 20_000_000, 40_000_000, 80_000_000]
    mem_ge_ths = [-80_000_000, -40_000_000, -20_000_000, 0, 20_000_000, 40_000_000, 80_000_000]
    for cls, name in enumerate(CLASSES):
        specs.append({"name": f"pred_eq_{name}", "kind": "pred_eq", "class": cls})
        specs.append({"name": f"top_eq_{name}", "kind": "top_eq", "class": cls})
        for th in margin_ths:
            specs.append({"name": f"top_{name}_margin_ge_{th}", "kind": "top_margin_ge", "class": cls, "threshold": th})
        for th in mem_ge_ths:
            specs.append({"name": f"mem_{name}_ge_{th}", "kind": "mem_ge", "class": cls, "threshold": th})
    for field, ths in [
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
    ]:
        for th in ths:
            specs.append({"name": f"{field}_ge_{th}", "kind": "count_ge", "field": field, "threshold": th})
    for field, ths in [
        ("pnn_mismatch_count", [0, 1, 3, 5, 8, 12]),
        ("qrs_maf_count", [0, 1, 3, 5, 8]),
        ("ectopic_pair_count", [0, 1, 3, 5]),
        ("rdm_ge50_count", [0, 1, 3, 5, 8]),
        ("rbbb_delay_like_count", [0, 1, 3, 5]),
    ]:
        for th in ths:
            specs.append({"name": f"{field}_le_{th}", "kind": "count_le", "field": field, "threshold": th})
    for pct in [3, 5, 8, 10, 15, 20, 30, 40, 55]:
        specs.append({"name": f"pnn_mis_rate_ge_{pct}", "kind": "ratio_ge", "num": "pnn_mismatch_count", "den": "pnn_decision_count", "pct": pct})
    for pct in [3, 5, 8, 10, 15, 20, 30, 40, 55]:
        specs.append({"name": f"rdm_ge50_rate_ge_{pct}", "kind": "ratio_ge", "num": "rdm_ge50_count", "den": "rdm_valid_count", "pct": pct})
    for pct in [3, 5, 8, 10, 15, 20, 30, 40, 55]:
        specs.append({"name": f"qrs_maf_rate_ge_{pct}", "kind": "ratio_ge", "num": "qrs_maf_count", "den": "beat_count", "pct": pct})
    for avg in [1, 2, 4, 6, 8, 10, 12, 16, 20]:
        specs.append({"name": f"rdm_avg_ge_{avg}", "kind": "avg_ge", "sum": "rdm_code_sum", "den": "rdm_valid_count", "threshold": avg})
    for avg in [2, 4, 6, 8, 10, 14, 18, 24]:
        specs.append({"name": f"ram_avg_ge_{avg}", "kind": "avg_ge", "sum": "ram_code_sum", "den": "ram_code_count", "threshold": avg})
    specs.extend(
        [
            {"name": "nsr_stability_strict", "kind": "custom", "custom": "nsr_stability_strict"},
            {"name": "nsr_stability_soft", "kind": "custom", "custom": "nsr_stability_soft"},
            {"name": "arr_burst_strong", "kind": "custom", "custom": "arr_burst_strong"},
            {"name": "arr_episodic_soft", "kind": "custom", "custom": "arr_episodic_soft"},
            {"name": "aff_irregular_persistent", "kind": "custom", "custom": "aff_irregular_persistent"},
            {"name": "aff_irregular_soft", "kind": "custom", "custom": "aff_irregular_soft"},
            {"name": "chf_morphology_low_irreg", "kind": "custom", "custom": "chf_morphology_low_irreg"},
            {"name": "abnormal_priority_any", "kind": "custom", "custom": "abnormal_priority_any"},
            {"name": "abnormal_priority_strong", "kind": "custom", "custom": "abnormal_priority_strong"},
        ]
    )
    return specs


def spec_value(row: dict[str, str], spec: dict) -> int:
    kind = spec["kind"]
    if kind == "always":
        return 1
    pred = safe_int(row["pred_class"])
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
            return int((cls == "ARR" and (pnn_mis >= 5 or qrs_maf >= 8 or ect >= 3)))
        if name == "aff_irregular_persistent":
            return int(mis_rate_ge_25 and rdm50_rate_ge_30)
        if name == "aff_irregular_soft":
            return int((cls == "AFF" and (mis_rate_ge_12 or rdm50_rate_ge_15)))
        if name == "chf_morphology_low_irreg":
            return int(cls == "CHF" and pnn_mis <= 8 and qrs_maf <= 8)
        if name == "abnormal_priority_any":
            return int(pnn_mis >= 5 or ect >= 3 or qrs_maf >= 5 or rbbb_like >= 3)
        if name == "abnormal_priority_strong":
            return int(pnn_mis >= 15 or ect >= 8 or qrs_maf >= 15 or rbbb_like >= 8)
    raise ValueError(f"unsupported feature spec: {spec}")


def build_matrix(rows: list[dict[str, str]], specs: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    x = np.zeros((len(rows), len(specs)), dtype=np.int8)
    y = np.zeros((len(rows),), dtype=np.int64)
    for i, row in enumerate(rows):
        y[i] = safe_int(row["class_id"])
        for j, spec in enumerate(specs):
            x[i, j] = spec_value(row, spec)
    return x, y


def predict_scores(x: np.ndarray, weights: np.ndarray, cap: int = 0, leak: int = 0) -> np.ndarray:
    scores = x.astype(np.int32) @ weights.T.astype(np.int32)
    if leak > 0:
        scores = np.where(scores > leak, scores - leak, np.where(scores < -leak, scores + leak, 0))
    if cap > 0:
        scores = np.clip(scores, -cap, cap)
    return scores


def predict_classes(x: np.ndarray, weights: np.ndarray, cap: int = 0, leak: int = 0) -> np.ndarray:
    return np.argmax(predict_scores(x, weights, cap, leak), axis=1).astype(np.int64)


def confusion(y_true: np.ndarray, y_pred: np.ndarray) -> list[list[int]]:
    cm = [[0 for _ in CLASSES] for _ in CLASSES]
    for t, p in zip(y_true.tolist(), y_pred.tolist()):
        cm[t][p] += 1
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


def init_weights(specs: list[dict], pred_init: int, top_init: int, mem_init: int) -> np.ndarray:
    w = np.zeros((4, len(specs)), dtype=np.int32)
    for j, spec in enumerate(specs):
        if spec["kind"] == "pred_eq":
            c = int(spec["class"])
            w[c, j] += pred_init
            for k in range(4):
                if k != c:
                    w[k, j] -= pred_init // 2
        elif spec["kind"] == "top_eq":
            c = int(spec["class"])
            w[c, j] += top_init
        elif spec["kind"] == "mem_ge" and int(spec["threshold"]) >= 0:
            c = int(spec["class"])
            w[c, j] += mem_init
    return w


def train_perceptron(x: np.ndarray, y: np.ndarray, specs: list[dict], *, epochs: int, lr: int, seed: int, pred_init: int, top_init: int, mem_init: int) -> np.ndarray:
    weights = init_weights(specs, pred_init=pred_init, top_init=top_init, mem_init=mem_init)
    order = list(range(len(y)))
    rng = random.Random(seed)
    for _ in range(epochs):
        rng.shuffle(order)
        for i in order:
            scores = x[i].astype(np.int32) @ weights.T
            pred = int(np.argmax(scores))
            true = int(y[i])
            if pred != true:
                active = x[i].astype(np.int32)
                weights[true] += lr * active
                weights[pred] -= lr * active
    return weights


def score_key(metrics: dict, nnz: int) -> tuple:
    return (
        metrics["accuracy"],
        metrics["macro_f1"],
        metrics["balanced_accuracy"],
        metrics["min_recall"],
        -metrics["recall_range"],
        -nnz,
    )


def run_search() -> None:
    dumps = load_dumps()
    specs = build_feature_specs()
    train_x, train_y = build_matrix(dumps["train"], specs)
    val_x, val_y = build_matrix(dumps["val"], specs)
    test_x, test_y = build_matrix(dumps["test"], specs)

    search_rows = []
    best = None
    best_payload = None
    candidate_id = 0

    def evaluate_candidate(weights: np.ndarray, cap: int, leak: int, params: dict) -> None:
        nonlocal candidate_id, best, best_payload
        train_pred = predict_classes(train_x, weights, cap, leak)
        val_pred = predict_classes(val_x, weights, cap, leak)
        train_m = metrics_from_pred(train_y, train_pred)
        val_m = metrics_from_pred(val_y, val_pred)
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
        key = score_key(val_m, nnz)
        if best is None or key > best:
            best = key
            best_payload = {
                "candidate_id": candidate_id,
                "params": {**params, "cap": cap, "leak": leak, "tie_break": "lowest_class_index"},
                "weights": weights.copy(),
                "train_metrics": train_m,
                "val_metrics": val_m,
            }
        candidate_id += 1

    # Snapshot-compatible baselines are included in the search table, but final
    # selection still follows validation metrics and may choose a learned readout.
    for pred_init, top_init, mem_init in [(32, 0, 0), (0, 32, 0), (24, 16, 0), (16, 16, 2)]:
        w = init_weights(specs, pred_init=pred_init, top_init=top_init, mem_init=mem_init)
        for cap in [0, 128, 256, 512, 1024]:
            for leak in [0, 2, 8]:
                evaluate_candidate(w, cap, leak, {"kind": "baseline", "epochs": 0, "lr": 0, "seed": 0, "pred_init": pred_init, "top_init": top_init, "mem_init": mem_init})

    for epochs in [2, 4, 6, 10, 14, 20]:
        for lr in [1, 2, 4]:
            for pred_init in [0, 8, 16, 32]:
                for top_init in [0, 8, 16]:
                    for mem_init in [0, 1, 2]:
                        for seed in [0, 1, 2]:
                            weights = train_perceptron(
                                train_x,
                                train_y,
                                specs,
                                epochs=epochs,
                                lr=lr,
                                seed=seed,
                                pred_init=pred_init,
                                top_init=top_init,
                                mem_init=mem_init,
                            )
                            for cap in [0, 256, 512, 1024, 2048, 4096]:
                                for leak in [0, 2, 8]:
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
        print(f"[search] completed epochs={epochs} candidates={candidate_id}", flush=True)

    assert best_payload is not None
    write_csv(RESULTS / "final_layer_search.csv", search_rows)

    selected_weights = best_payload["weights"]
    selected_cap = int(best_payload["params"]["cap"])
    selected_leak = int(best_payload["params"]["leak"])
    split_payloads = {}
    for split, x, y in [("train", train_x, train_y), ("val", val_x, val_y), ("test", test_x, test_y)]:
        pred = predict_classes(x, selected_weights, selected_cap, selected_leak)
        scores = predict_scores(x, selected_weights, selected_cap, selected_leak)
        metrics = metrics_from_pred(y, pred)
        split_payloads[split] = metrics
        (RESULTS / f"python_{split}_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        pred_rows = []
        for row, p, score in zip(dumps[split], pred.tolist(), scores.tolist()):
            pred_rows.append(
                {
                    "case_id": row["case_id"],
                    "split": split,
                    "class_label": row["class_label"],
                    "class_id": row["class_id"],
                    "record_id": row["record_id"],
                    "chunk_id": row["chunk_id"],
                    "snapshot_pred_class": row["pred_class"],
                    "final_pred_class": p,
                    "final_pred_label": CLASSES[p],
                    "correct": int(p == safe_int(row["class_id"])),
                    "final_mem_NSR": int(score[0]),
                    "final_mem_CHF": int(score[1]),
                    "final_mem_ARR": int(score[2]),
                    "final_mem_AFF": int(score[3]),
                }
            )
        write_csv(RESULTS / f"python_{split}_predictions.csv", pred_rows)

    selected = {
        "classes": CLASSES,
        "selection_rule": "validation accuracy, macro-F1, balanced accuracy, min recall, recall range, then nnz",
        "candidate_id": best_payload["candidate_id"],
        "params": best_payload["params"],
        "feature_specs": specs,
        "weights_by_class": {cls: [int(v) for v in selected_weights[i].tolist()] for i, cls in enumerate(CLASSES)},
        "metrics": split_payloads,
        "note": "Snapshot C24 parameters are fixed; only this final membrane readout was trained on train and selected on validation.",
    }
    (RESULTS / "final_layer_selected_params.json").write_text(json.dumps(selected, indent=2), encoding="utf-8")
    print(
        "[search] selected "
        f"id={best_payload['candidate_id']} "
        f"val_acc={split_payloads['val']['accuracy']:.4f} "
        f"test_acc={split_payloads['test']['accuracy']:.4f}",
        flush=True,
    )


def load_selected() -> dict:
    return json.loads((RESULTS / "final_layer_selected_params.json").read_text(encoding="utf-8"))


def rtl_input_fields(specs: list[dict]) -> list[str]:
    fields: list[str] = []

    def add(name: str) -> None:
        if name not in fields:
            fields.append(name)

    for spec in specs:
        kind = spec["kind"]
        if kind in ("count_ge", "count_le"):
            add(spec["field"])
        elif kind == "ratio_ge":
            add(spec["num"])
            add(spec["den"])
        elif kind == "avg_ge":
            add(spec["sum"])
            add(spec["den"])
    for name in [
        "pnn_mismatch_count",
        "pnn_decision_count",
        "rdm_ge50_count",
        "rdm_valid_count",
        "ectopic_pair_count",
        "qrs_maf_count",
        "rbbb_delay_like_count",
    ]:
        add(name)
    return fields


def v_signed(width: int, value: int) -> str:
    value = int(value)
    if value < 0:
        return f"-{width}'sd{abs(value)}"
    return f"{width}'sd{value}"


def shift_add_expr(name: str, const: int) -> str:
    const = int(const)
    if const == 0:
        return "32'd0"
    terms = []
    bit = 0
    c = const
    while c:
        if c & 1:
            if bit == 0:
                terms.append(f"{{16'd0, {name}[15:0]}}" if name.endswith("_count") else f"{name}")
            else:
                base = f"{{16'd0, {name}[15:0]}}" if name.endswith("_count") else f"{name}"
                terms.append(f"({base} << {bit})")
        bit += 1
        c >>= 1
    return " + ".join(terms)


def ratio_ge_v(num: str, den: str, pct: int) -> str:
    return f"(({den} != 32'd0) && (({shift_add_expr(num, 100)}) >= ({shift_add_expr(den, pct)})))"


def avg_ge_v(total: str, den: str, threshold: int) -> str:
    return f"(({den} != 32'd0) && ({total} >= ({shift_add_expr(den, threshold)})))"


def top_condition_v(cls: int) -> str:
    names = ["class_mem_nsr", "class_mem_chf", "class_mem_arr", "class_mem_aff"]
    exprs = []
    for i, name in enumerate(names):
        if i == cls:
            continue
        op = ">=" if cls < i else ">"
        exprs.append(f"({names[cls]} {op} {name})")
    return " && ".join(exprs)


def max_other_expr(cls: int) -> str:
    names = ["class_mem_nsr", "class_mem_chf", "class_mem_arr", "class_mem_aff"]
    others = [names[i] for i in range(4) if i != cls]
    expr = others[0]
    for name in others[1:]:
        expr = f"(({expr} >= {name}) ? {expr} : {name})"
    return expr


def cond_expr_v(spec: dict) -> str:
    kind = spec["kind"]
    if kind == "always":
        return "1'b1"
    if kind == "pred_eq":
        return f"(pred_valid && (pred_class == 2'd{int(spec['class'])}))"
    if kind == "top_eq":
        return f"({top_condition_v(int(spec['class']))})"
    if kind == "top_margin_ge":
        cls = int(spec["class"])
        mem = ["class_mem_nsr", "class_mem_chf", "class_mem_arr", "class_mem_aff"][cls]
        return f"(({top_condition_v(cls)}) && (({mem} - {max_other_expr(cls)}) >= {v_signed(64, int(spec['threshold']))}))"
    if kind == "mem_ge":
        mem = ["class_mem_nsr", "class_mem_chf", "class_mem_arr", "class_mem_aff"][int(spec["class"])]
        return f"({mem} >= {v_signed(64, int(spec['threshold']))})"
    if kind == "count_ge":
        return f"({spec['field']} >= 32'd{int(spec['threshold'])})"
    if kind == "count_le":
        return f"({spec['field']} <= 32'd{int(spec['threshold'])})"
    if kind == "ratio_ge":
        return ratio_ge_v(spec["num"], spec["den"], int(spec["pct"]))
    if kind == "avg_ge":
        return avg_ge_v(spec["sum"], spec["den"], int(spec["threshold"]))
    if kind == "custom":
        name = spec["custom"]
        mis_rate_ge_12 = ratio_ge_v("pnn_mismatch_count", "pnn_decision_count", 12)
        mis_rate_ge_25 = ratio_ge_v("pnn_mismatch_count", "pnn_decision_count", 25)
        rdm50_rate_ge_15 = ratio_ge_v("rdm_ge50_count", "rdm_valid_count", 15)
        rdm50_rate_ge_30 = ratio_ge_v("rdm_ge50_count", "rdm_valid_count", 30)
        if name == "nsr_stability_strict":
            return "((pred_valid && (pred_class == 2'd0)) && (pnn_mismatch_count <= 32'd1) && (ectopic_pair_count == 32'd0) && (qrs_maf_count <= 32'd1) && (rbbb_delay_like_count == 32'd0))"
        if name == "nsr_stability_soft":
            return "((pred_valid && (pred_class == 2'd0)) && (pnn_mismatch_count <= 32'd5) && (ectopic_pair_count <= 32'd1) && (qrs_maf_count <= 32'd3))"
        if name == "arr_burst_strong":
            return "(((pnn_mismatch_count >= 32'd12) && (ectopic_pair_count >= 32'd3)) || (qrs_maf_count >= 32'd18))"
        if name == "arr_episodic_soft":
            return "((pred_valid && (pred_class == 2'd2)) && ((pnn_mismatch_count >= 32'd5) || (qrs_maf_count >= 32'd8) || (ectopic_pair_count >= 32'd3)))"
        if name == "aff_irregular_persistent":
            return f"(({mis_rate_ge_25}) && ({rdm50_rate_ge_30}))"
        if name == "aff_irregular_soft":
            return f"((pred_valid && (pred_class == 2'd3)) && (({mis_rate_ge_12}) || ({rdm50_rate_ge_15})))"
        if name == "chf_morphology_low_irreg":
            return "((pred_valid && (pred_class == 2'd1)) && (pnn_mismatch_count <= 32'd8) && (qrs_maf_count <= 32'd8))"
        if name == "abnormal_priority_any":
            return "((pnn_mismatch_count >= 32'd5) || (ectopic_pair_count >= 32'd3) || (qrs_maf_count >= 32'd5) || (rbbb_delay_like_count >= 32'd3))"
        if name == "abnormal_priority_strong":
            return "((pnn_mismatch_count >= 32'd15) || (ectopic_pair_count >= 32'd8) || (qrs_maf_count >= 32'd15) || (rbbb_delay_like_count >= 32'd8))"
    raise ValueError(f"unsupported RTL spec: {spec}")


def generate_rtl() -> None:
    selected = load_selected()
    specs = selected["feature_specs"]
    fields = rtl_input_fields(specs)
    weights = [[int(v) for v in selected["weights_by_class"][cls]] for cls in CLASSES]
    cap = int(selected["params"].get("cap", 0))
    leak = int(selected["params"].get("leak", 0))
    RTL_OUT.parent.mkdir(parents=True, exist_ok=True)
    TB_OUT.parent.mkdir(parents=True, exist_ok=True)

    port_lines = [
        "    input clk",
        "    input rst",
        "    input clear",
        "    input window_done",
        "    input pred_valid",
        "    input [1:0] pred_class",
        "    input signed [63:0] class_mem_nsr",
        "    input signed [63:0] class_mem_chf",
        "    input signed [63:0] class_mem_arr",
        "    input signed [63:0] class_mem_aff",
    ]
    for field in fields:
        port_lines.append(f"    input [31:0] {field}")
    port_lines.extend(
        [
            "    output reg final_valid",
            "    output reg [1:0] final_pred_class",
            "    output reg signed [31:0] final_mem_nsr",
            "    output reg signed [31:0] final_mem_chf",
            "    output reg signed [31:0] final_mem_arr",
            "    output reg signed [31:0] final_mem_aff",
        ]
    )
    lines = [
        "`timescale 1ns / 1ps",
        "",
        "module final_membrane_layer(",
        ",\n".join(port_lines),
        ");",
        "",
        "    reg signed [31:0] m_nsr;",
        "    reg signed [31:0] m_chf;",
        "    reg signed [31:0] m_arr;",
        "    reg signed [31:0] m_aff;",
        "    reg signed [31:0] best_score;",
        "    reg [1:0] best_class;",
        "",
    ]
    if cap > 0:
        lines.extend(
            [
                "    function signed [31:0] cap_score;",
                "        input signed [31:0] value;",
                "        begin",
                f"            if (value > {v_signed(32, cap)}) cap_score = {v_signed(32, cap)};",
                f"            else if (value < {v_signed(32, -cap)}) cap_score = {v_signed(32, -cap)};",
                "            else cap_score = value;",
                "        end",
                "    endfunction",
                "",
            ]
        )
    if leak > 0:
        lines.extend(
            [
                "    function signed [31:0] leak_score;",
                "        input signed [31:0] value;",
                "        begin",
                f"            if (value > {v_signed(32, leak)}) leak_score = value - {v_signed(32, leak)};",
                f"            else if (value < {v_signed(32, -leak)}) leak_score = value + {v_signed(32, leak)};",
                "            else leak_score = 32'sd0;",
                "        end",
                "    endfunction",
                "",
            ]
        )
    lines.extend(
        [
            "    always @(posedge clk) begin",
            "        if (rst || clear) begin",
            "            final_valid <= 1'b0;",
            "            final_pred_class <= 2'd0;",
            "            final_mem_nsr <= 32'sd0;",
            "            final_mem_chf <= 32'sd0;",
            "            final_mem_arr <= 32'sd0;",
            "            final_mem_aff <= 32'sd0;",
            "        end else if (window_done) begin",
            "            m_nsr = 32'sd0;",
            "            m_chf = 32'sd0;",
            "            m_arr = 32'sd0;",
            "            m_aff = 32'sd0;",
        ]
    )
    for idx, spec in enumerate(specs):
        ws = [weights[c][idx] for c in range(4)]
        if not any(ws):
            continue
        cond = cond_expr_v(spec)
        lines.append(f"            if ({cond}) begin  // {idx}: {spec['name']}")
        if ws[0]:
            lines.append(f"                m_nsr = m_nsr + {v_signed(32, ws[0])};")
        if ws[1]:
            lines.append(f"                m_chf = m_chf + {v_signed(32, ws[1])};")
        if ws[2]:
            lines.append(f"                m_arr = m_arr + {v_signed(32, ws[2])};")
        if ws[3]:
            lines.append(f"                m_aff = m_aff + {v_signed(32, ws[3])};")
        lines.append("            end")
    if cap > 0:
        if leak > 0:
            lines.extend(
                [
                    "            m_nsr = leak_score(m_nsr);",
                    "            m_chf = leak_score(m_chf);",
                    "            m_arr = leak_score(m_arr);",
                    "            m_aff = leak_score(m_aff);",
                ]
            )
        lines.extend(
            [
                "            m_nsr = cap_score(m_nsr);",
                "            m_chf = cap_score(m_chf);",
                "            m_arr = cap_score(m_arr);",
                "            m_aff = cap_score(m_aff);",
            ]
        )
    elif leak > 0:
        lines.extend(
            [
                "            m_nsr = leak_score(m_nsr);",
                "            m_chf = leak_score(m_chf);",
                "            m_arr = leak_score(m_arr);",
                "            m_aff = leak_score(m_aff);",
            ]
        )
    lines.extend(
        [
            "            best_score = m_nsr;",
            "            best_class = 2'd0;",
            "            if (m_chf > best_score) begin best_score = m_chf; best_class = 2'd1; end",
            "            if (m_arr > best_score) begin best_score = m_arr; best_class = 2'd2; end",
            "            if (m_aff > best_score) begin best_score = m_aff; best_class = 2'd3; end",
            "            final_valid <= 1'b1;",
            "            final_pred_class <= best_class;",
            "            final_mem_nsr <= m_nsr;",
            "            final_mem_chf <= m_chf;",
            "            final_mem_arr <= m_arr;",
            "            final_mem_aff <= m_aff;",
            "        end else begin",
            "            final_valid <= 1'b0;",
            "        end",
            "    end",
            "",
            "endmodule",
            "",
        ]
    )
    RTL_OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    generate_xsim_inputs(fields)
    generate_tb(fields)
    print(f"[rtl] wrote {RTL_OUT}")
    print(f"[rtl] wrote {TB_OUT}")


def generate_xsim_inputs(fields: list[str]) -> None:
    for split in ["train", "val", "test"]:
        rows = read_csv(RESULTS / f"window_dump_{split}.csv")
        path = RESULTS / f"xsim_input_{split}.txt"
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                values = [
                    safe_int(row["case_id"]),
                    safe_int(row["class_id"]),
                    safe_int(row["pred_valid"]),
                    safe_int(row["pred_class"]),
                    safe_int(row["class_mem_NSR"]),
                    safe_int(row["class_mem_CHF"]),
                    safe_int(row["class_mem_ARR"]),
                    safe_int(row["class_mem_AFF"]),
                ]
                values.extend(safe_int(row[field]) for field in fields)
                f.write(" ".join(str(v) for v in values) + "\n")


def generate_tb(fields: list[str]) -> None:
    input_decl = []
    scan_vars = [
        "case_id_i",
        "expected_i",
        "pred_valid_i",
        "pred_class_i",
        "cm_nsr_i",
        "cm_chf_i",
        "cm_arr_i",
        "cm_aff_i",
    ]
    for field in fields:
        scan_vars.append(f"{field}_i")
        input_decl.append(f"    reg [31:0] {field};")
    fmt = " ".join(["%d"] * len(scan_vars)) + "\\n"
    fscanf_args = ", ".join(scan_vars)
    assign_lines = [
        "                    pred_valid = pred_valid_i != 0;",
        "                    pred_class = pred_class_i[1:0];",
        "                    class_mem_nsr = cm_nsr_i;",
        "                    class_mem_chf = cm_chf_i;",
        "                    class_mem_arr = cm_arr_i;",
        "                    class_mem_aff = cm_aff_i;",
    ]
    for field in fields:
        assign_lines.append(f"                    {field} = {field}_i[31:0];")
    dut_ports = [
        "        .clk(clk)",
        "        .rst(rst)",
        "        .clear(clear)",
        "        .window_done(window_done)",
        "        .pred_valid(pred_valid)",
        "        .pred_class(pred_class)",
        "        .class_mem_nsr(class_mem_nsr)",
        "        .class_mem_chf(class_mem_chf)",
        "        .class_mem_arr(class_mem_arr)",
        "        .class_mem_aff(class_mem_aff)",
    ]
    for field in fields:
        dut_ports.append(f"        .{field}({field})")
    dut_ports.extend(
        [
            "        .final_valid(final_valid)",
            "        .final_pred_class(final_pred_class)",
            "        .final_mem_nsr(final_mem_nsr)",
            "        .final_mem_chf(final_mem_chf)",
            "        .final_mem_arr(final_mem_arr)",
            "        .final_mem_aff(final_mem_aff)",
        ]
    )
    int_decl = "\n".join(f"    integer {v};" for v in scan_vars)
    lines = [
        "`timescale 1ns / 1ps",
        "",
        "module tb_final_membrane_layer_dataset;",
        "    reg clk;",
        "    reg rst;",
        "    reg clear;",
        "    reg window_done;",
        "    reg pred_valid;",
        "    reg [1:0] pred_class;",
        "    reg signed [63:0] class_mem_nsr;",
        "    reg signed [63:0] class_mem_chf;",
        "    reg signed [63:0] class_mem_arr;",
        "    reg signed [63:0] class_mem_aff;",
        *input_decl,
        "    wire final_valid;",
        "    wire [1:0] final_pred_class;",
        "    wire signed [31:0] final_mem_nsr;",
        "    wire signed [31:0] final_mem_chf;",
        "    wire signed [31:0] final_mem_arr;",
        "    wire signed [31:0] final_mem_aff;",
        "",
        int_decl,
        "    integer fd;",
        "    integer out_fd;",
        "    integer scan_count;",
        "    integer total;",
        "    integer correct;",
        "",
        "    final_membrane_layer dut(",
        ",\n".join(dut_ports),
        "    );",
        "",
        "    always #5 clk = ~clk;",
        "",
        "    task run_split;",
        "        input [8*512-1:0] input_path;",
        "        input [8*512-1:0] output_path;",
        "        begin",
        "            fd = $fopen(input_path, \"r\");",
        "            if (fd == 0) begin $display(\"FAIL open input %0s\", input_path); $finish; end",
        "            out_fd = $fopen(output_path, \"w\");",
        "            if (out_fd == 0) begin $display(\"FAIL open output %0s\", output_path); $finish; end",
        "            $fdisplay(out_fd, \"case_id,expected_class,final_pred_class,correct,final_mem_NSR,final_mem_CHF,final_mem_ARR,final_mem_AFF\");",
        "            total = 0;",
        "            correct = 0;",
        "            while (!$feof(fd)) begin",
        f"                scan_count = $fscanf(fd, \"{fmt}\", {fscanf_args});",
        f"                if (scan_count == {len(scan_vars)}) begin",
        *assign_lines,
        "                    @(negedge clk);",
        "                    window_done = 1'b1;",
        "                    @(posedge clk);",
        "                    #1;",
        "                    window_done = 1'b0;",
        "                    total = total + 1;",
        "                    if (final_valid && (final_pred_class == expected_i[1:0])) correct = correct + 1;",
        "                    $fdisplay(out_fd, \"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d\",",
        "                              case_id_i, expected_i, final_pred_class, final_valid && (final_pred_class == expected_i[1:0]),",
        "                              final_mem_nsr, final_mem_chf, final_mem_arr, final_mem_aff);",
        "                end",
        "            end",
        "            $display(\"SPLIT_RESULT %0s correct/total=%0d/%0d\", input_path, correct, total);",
        "            $fclose(fd);",
        "            $fclose(out_fd);",
        "        end",
        "    endtask",
        "",
        "    initial begin",
        "        clk = 1'b0;",
        "        rst = 1'b1;",
        "        clear = 1'b0;",
        "        window_done = 1'b0;",
        "        pred_valid = 1'b0;",
        "        pred_class = 2'd0;",
        "        class_mem_nsr = 64'sd0;",
        "        class_mem_chf = 64'sd0;",
        "        class_mem_arr = 64'sd0;",
        "        class_mem_aff = 64'sd0;",
    ]
    for field in fields:
        lines.append(f"        {field} = 32'd0;")
    split_paths = {
        split: (
            str((RESULTS / f"xsim_input_{split}.txt").resolve()).replace("\\", "/"),
            str((RESULTS / f"xsim_{split}_predictions.csv").resolve()).replace("\\", "/"),
        )
        for split in ["train", "val", "test"]
    }
    lines.extend(
        [
            "        repeat (4) @(posedge clk);",
            "        rst = 1'b0;",
            f"        run_split(\"{split_paths['train'][0]}\", \"{split_paths['train'][1]}\");",
            f"        run_split(\"{split_paths['val'][0]}\", \"{split_paths['val'][1]}\");",
            f"        run_split(\"{split_paths['test'][0]}\", \"{split_paths['test'][1]}\");",
            "        $display(\"PASS tb_final_membrane_layer_dataset completed\");",
            "        $finish;",
            "    end",
            "endmodule",
            "",
        ]
    )
    TB_OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def slash(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def run_cmd(cmd: list[str], cwd: Path, log: Path) -> None:
    print("$ " + " ".join(cmd), flush=True)
    with log.open("w", encoding="utf-8", errors="replace") as f:
        proc = subprocess.run(cmd, cwd=str(cwd), stdout=f, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed {proc.returncode}: {' '.join(cmd)}; see {log}")


def run_xsim() -> None:
    for tool in [XVLOG, XELAB, XSIM]:
        if not tool.exists():
            raise FileNotFoundError(tool)
    if not RTL_OUT.exists() or not TB_OUT.exists():
        generate_rtl()
    work = RESULTS / "xsim_work"
    work.mkdir(parents=True, exist_ok=True)
    prj = work / "sources.prj"
    prj.write_text(
        "\n".join(
            [
                f'verilog work "{slash(RTL_OUT)}"',
                f'verilog work "{slash(TB_OUT)}"',
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tcl = work / "run.tcl"
    tcl.write_text("run all\nquit\n", encoding="utf-8", newline="\n")
    run_cmd([str(XVLOG), "--nolog", "-prj", slash(prj)], work, RESULTS / "xsim_xvlog.log")
    run_cmd([str(XELAB), "--nolog", "-debug", "typical", "tb_final_membrane_layer_dataset", "-s", "tb_final_membrane_layer_dataset_behav"], work, RESULTS / "xsim_xelab.log")
    run_cmd([str(XSIM), "tb_final_membrane_layer_dataset_behav", "--nolog", "-tclbatch", slash(tcl)], work, RESULTS / "xsim.log")
    summarize_xsim()


def summarize_xsim() -> None:
    compare_rows = []
    for split in ["train", "val", "test"]:
        xsim_rows = read_csv(RESULTS / f"xsim_{split}_predictions.csv")
        py_rows = {r["case_id"]: r for r in read_csv(RESULTS / f"python_{split}_predictions.csv")}
        y_true = []
        y_pred = []
        for row in xsim_rows:
            case_id = row["case_id"]
            py = py_rows[case_id]
            pred = safe_int(row["final_pred_class"])
            y_pred.append(pred)
            y_true.append(safe_int(row["expected_class"]))
            mem_mismatch = 0
            for cls in CLASSES:
                mem_mismatch |= int(safe_int(row[f"final_mem_{cls}"]) != safe_int(py[f"final_mem_{cls}"]))
            compare_rows.append(
                {
                    "split": split,
                    "case_id": case_id,
                    "python_pred_class": py["final_pred_class"],
                    "xsim_pred_class": pred,
                    "pred_mismatch": int(safe_int(py["final_pred_class"]) != pred),
                    "final_mem_mismatch": mem_mismatch,
                }
            )
        metrics = metrics_from_pred(np.array(y_true, dtype=np.int64), np.array(y_pred, dtype=np.int64))
        (RESULTS / f"xsim_{split}_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    write_csv(RESULTS / "python_vs_xsim_compare.csv", compare_rows)
    print("[xsim] wrote metrics and python_vs_xsim_compare.csv", flush=True)


def write_report() -> None:
    lines = [
        "# Final Membrane Layer 30s Report",
        "",
        "## Scope",
        "",
        "- Dataset: `fullrec_afe_30s_annotation_valid_balanced`.",
        "- Snapshot C24 was fixed. Its Python model is the bit-exact model in `scripts/snapshot_c24_rtl_exact.py`.",
        "- Only the final membrane readout was trained using train data and selected by validation metrics.",
        "- Test was evaluated once after selecting the validation winner.",
        "- XSim verifies `rtl/final_membrane_layer.v` using the frozen Snapshot C24 dump columns as inputs to the final readout.",
        "",
        "## Snapshot C24 Baseline",
        "",
    ]
    for split in ["train", "val", "test"]:
        rows = read_csv(RESULTS / f"window_dump_{split}.csv")
        y = np.array([safe_int(r["class_id"]) for r in rows], dtype=np.int64)
        p = np.array([safe_int(r["pred_class"]) for r in rows], dtype=np.int64)
        m = metrics_from_pred(y, p)
        lines.append(f"- {split}: {m['correct']}/{m['total']} = {m['accuracy'] * 100:.2f}%, macro-F1 {m['macro_f1']:.3f}")
    lines += ["", "## Selected Final Layer", ""]
    selected = load_selected()
    lines.append(f"- selected candidate: {selected['candidate_id']}")
    lines.append(f"- params: `{json.dumps(selected['params'], sort_keys=True)}`")
    lines.append(f"- feature spikes/conditions: {len(selected['feature_specs'])}")
    lines.append("- RTL structure: fixed condition spikes add signed integer weights into NSR/CHF/ARR/AFF final membranes, followed by WTA.")
    lines.append("- DSP/floating point: none in the final-layer RTL source; thresholds use comparisons and constant shift/add expressions.")
    lines += ["", "## Python Metrics", ""]
    for split in ["train", "val", "test"]:
        m = json.loads((RESULTS / f"python_{split}_metrics.json").read_text(encoding="utf-8"))
        lines.append(f"- {split}: {m['correct']}/{m['total']} = {m['accuracy'] * 100:.2f}%, macro-F1 {m['macro_f1']:.3f}, balanced {m['balanced_accuracy']:.3f}, min recall {m['min_recall']:.3f}")
    lines += ["", "## XSim Metrics", ""]
    if all((RESULTS / f"xsim_{split}_metrics.json").exists() for split in ["train", "val", "test"]):
        for split in ["train", "val", "test"]:
            m = json.loads((RESULTS / f"xsim_{split}_metrics.json").read_text(encoding="utf-8"))
            lines.append(f"- {split}: {m['correct']}/{m['total']} = {m['accuracy'] * 100:.2f}%, macro-F1 {m['macro_f1']:.3f}, balanced {m['balanced_accuracy']:.3f}, min recall {m['min_recall']:.3f}")
            lines.append(f"  - confusion matrix rows=true NSR/CHF/ARR/AFF, cols=pred NSR/CHF/ARR/AFF: `{m['confusion_matrix']}`")
            for cls in CLASSES:
                d = m["per_class"][cls]
                lines.append(f"  - {cls}: precision {d['precision']:.3f}, recall {d['recall']:.3f}, F1 {d['f1']:.3f}, support {d['support']}")
        comp = read_csv(RESULTS / "python_vs_xsim_compare.csv")
        pred_mis = sum(safe_int(r["pred_mismatch"]) for r in comp)
        mem_mis = sum(safe_int(r["final_mem_mismatch"]) for r in comp)
        lines += ["", "## Python vs XSim", ""]
        lines.append(f"- compared cases: {len(comp)}")
        lines.append(f"- pred_class mismatches: {pred_mis}")
        lines.append(f"- final_mem mismatches: {mem_mis}")
    else:
        lines.append("- XSim metrics are not available yet.")
    lines += ["", "## Conclusion", ""]
    if (RESULTS / "xsim_test_metrics.json").exists():
        tm = json.loads((RESULTS / "xsim_test_metrics.json").read_text(encoding="utf-8"))
        if tm["accuracy"] >= 0.80:
            lines.append(f"Success: XSim test accuracy is {tm['accuracy'] * 100:.2f}%, meeting the 80% target.")
        else:
            lines.append(f"Target not met: XSim test accuracy is {tm['accuracy'] * 100:.2f}%. ARR is the likely bottleneck and should be separated from Snapshot C24 limitations in follow-up analysis.")
    else:
        lines.append("XSim has not been run yet, so completion is not established.")
    (RESULTS / "final_membrane_layer_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[report] wrote {RESULTS / 'final_membrane_layer_report.md'}")


def summarize_manifest() -> None:
    rows = load_manifest()
    counts = Counter((r["split"], r["class_label"]) for r in rows)
    print("[manifest] rows", len(rows))
    for key in sorted(counts):
        print("[manifest]", key[0], key[1], counts[key])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["manifest", "dump", "search", "rtl", "xsim", "report", "all"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.command == "manifest":
        summarize_manifest()
    elif args.command == "dump":
        generate_window_dumps(force=args.force)
    elif args.command == "search":
        run_search()
    elif args.command == "rtl":
        generate_rtl()
    elif args.command == "xsim":
        run_xsim()
    elif args.command == "report":
        write_report()
    elif args.command == "all":
        summarize_manifest()
        generate_window_dumps(force=args.force)
        run_search()
        generate_rtl()
        run_xsim()
        write_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
