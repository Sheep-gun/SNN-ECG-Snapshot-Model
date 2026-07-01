from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "final_membrane_v2_snn"
CLASSES = ["NSR", "CHF", "ARR", "AFF"]
BASELINE_PATH = RESULTS / "local_rules_seed41031_selected_train_val_locked.json"


def load_snn_module() -> Any:
    path = REPO / "scripts" / "search_final_membrane_v2_snn.py"
    spec = importlib.util.spec_from_file_location("final_membrane_v2_snn_mod", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["final_membrane_v2_snn_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def argmax4(values: list[int]) -> int:
    best = 0
    for idx in range(1, 4):
        if values[idx] > values[best]:
            best = idx
    return best


def choice(rng: random.Random, values: list[Any]) -> Any:
    return values[rng.randrange(len(values))]


def metric(chunks: list[Any], pred: dict[str, int]) -> dict[str, Any]:
    cm = [[0 for _ in range(4)] for _ in range(4)]
    for chunk in chunks:
        cm[chunk.class_id][pred[chunk.case_id]] += 1
    correct = sum(cm[i][i] for i in range(4))
    total = sum(sum(row) for row in cm)
    per_class: dict[str, dict[str, float | int]] = {}
    for idx, cls in enumerate(CLASSES):
        tp = cm[idx][idx]
        fp = sum(cm[row][idx] for row in range(4) if row != idx)
        fn = sum(cm[idx][col] for col in range(4) if col != idx)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[cls] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(cm[idx])}
    return {
        "correct": correct,
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": sum(float(per_class[cls]["f1"]) for cls in CLASSES) / 4.0,
        "balanced_accuracy": sum(float(per_class[cls]["recall"]) for cls in CLASSES) / 4.0,
        "min_recall": min(float(per_class[cls]["recall"]) for cls in CLASSES),
        "per_class": per_class,
        "confusion_matrix": cm,
    }


def load_baseline() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(f"baseline missing: {BASELINE_PATH}")
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return dict(payload["params"])


def baseline_pre(mod: Any, chunk: Any, base_params: dict[str, Any]) -> tuple[list[int], int, dict[str, int]]:
    pred, mem, flags = mod.candidate_predict(chunk, base_params)
    return list(mem), pred, flags


def infer_one(mod: Any, chunk: Any, base_params: dict[str, Any], p: dict[str, Any]) -> tuple[int, list[int], dict[str, int]]:
    mem, pre, base_flags = baseline_pre(mod, chunk, base_params)
    counts = chunk.pred_count
    fs = chunk.feature_sum
    flags = {f"base_{key}": int(value) for key, value in base_flags.items()}

    strong_nsr_veto = (
        p["strong_nsr_enable"]
        and counts[0] >= p["strong_nsr_count_ge"]
        and counts[0] >= counts[2] + p["strong_nsr_margin_ge"]
        and counts[3] <= p["strong_nsr_aff_le"]
        and fs["qrs_maf_count"] <= p["strong_nsr_qrs_le"]
        and fs["rbbb_delay_like_count"] <= p["strong_nsr_rbbb_le"]
    )
    if strong_nsr_veto:
        mem[2] -= p["strong_nsr_arr_inhibit"]

    arr_from_nsr = (
        p["arr_from_nsr_enable"]
        and pre == 0
        and counts[0] >= p["arr_from_nsr_nsr_ge"]
        and counts[2] >= p["arr_from_nsr_arr_ge"]
        and counts[3] <= p["arr_from_nsr_aff_le"]
        and counts[0] - counts[2] <= p["arr_from_nsr_margin_le"]
        and fs["morphology_evidence_count"] >= p["arr_from_nsr_morph_ge"]
        and fs["rdm_code_sum"] >= p["arr_from_nsr_rdm_ge"]
        and fs["pnn_mismatch_count"] >= p["arr_from_nsr_pnn_ge"]
        and fs["ectopic_pair_count"] >= p["arr_from_nsr_ecp_ge"]
        and fs["qrs_maf_count"] <= p["arr_from_nsr_qrs_le"]
        and fs["rbbb_delay_like_count"] <= p["arr_from_nsr_rbbb_le"]
        and not strong_nsr_veto
    )
    if arr_from_nsr:
        mem[2] += p["arr_from_nsr_boost"]
        mem[0] -= p["arr_from_nsr_inhibit_nsr"]
        mem[3] -= p["arr_from_nsr_inhibit_aff"]

    arr_from_chf = (
        p["arr_from_chf_enable"]
        and pre == 1
        and counts[2] >= p["arr_from_chf_arr_ge"]
        and counts[1] - counts[2] <= p["arr_from_chf_margin_le"]
        and fs["morphology_evidence_count"] >= p["arr_from_chf_morph_ge"]
        and fs["qrs_maf_count"] >= p["arr_from_chf_qrs_ge"]
        and fs["rbbb_delay_like_count"] >= p["arr_from_chf_rbbb_ge"]
        and fs["rdm_code_sum"] >= p["arr_from_chf_rdm_ge"]
        and fs["ectopic_pair_count"] >= p["arr_from_chf_ecp_ge"]
    )
    if arr_from_chf:
        mem[2] += p["arr_from_chf_boost"]
        mem[1] -= p["arr_from_chf_inhibit_chf"]

    arr_from_aff = (
        p["arr_from_aff_enable"]
        and pre == 3
        and counts[2] >= p["arr_from_aff_arr_ge"]
        and counts[3] - counts[2] <= p["arr_from_aff_margin_le"]
        and fs["morphology_evidence_count"] >= p["arr_from_aff_morph_ge"]
        and fs["rdm_code_sum"] >= p["arr_from_aff_rdm_ge"]
        and fs["pnn_mismatch_count"] >= p["arr_from_aff_pnn_ge"]
        and fs["ectopic_pair_count"] >= p["arr_from_aff_ecp_ge"]
        and fs["qrs_maf_count"] <= p["arr_from_aff_qrs_le"]
        and fs["rbbb_delay_like_count"] <= p["arr_from_aff_rbbb_le"]
    )
    if arr_from_aff:
        mem[2] += p["arr_from_aff_boost"]
        mem[3] -= p["arr_from_aff_inhibit_aff"]

    arr_zero_silent = (
        p["arr_zero_silent_enable"]
        and pre == 0
        and counts[0] >= p["arr_zero_silent_nsr_ge"]
        and counts[1] <= p["arr_zero_silent_chf_le"]
        and counts[2] <= p["arr_zero_silent_arr_le"]
        and counts[3] <= p["arr_zero_silent_aff_le"]
        and fs["morphology_evidence_count"] >= p["arr_zero_silent_morph_ge"]
        and fs["rdm_code_sum"] >= p["arr_zero_silent_rdm_ge"]
        and fs["abnormal_evidence_count"] <= p["arr_zero_silent_abn_le"]
        and fs["qrs_maf_count"] <= p["arr_zero_silent_qrs_le"]
        and fs["rbbb_delay_like_count"] <= p["arr_zero_silent_rbbb_le"]
    )
    if arr_zero_silent:
        mem[2] += p["arr_zero_silent_boost"]
        mem[0] -= p["arr_zero_silent_inhibit_nsr"]

    flags.update(
        {
            "strong_nsr_veto": int(strong_nsr_veto),
            "arr_from_nsr": int(arr_from_nsr),
            "arr_from_chf": int(arr_from_chf),
            "arr_from_aff": int(arr_from_aff),
            "arr_zero_silent": int(arr_zero_silent),
        }
    )
    return argmax4(mem), mem, flags


def apply_candidate(mod: Any, chunks: list[Any], base_params: dict[str, Any], p: dict[str, Any]) -> tuple[dict[str, int], dict[str, dict[str, Any]]]:
    pred: dict[str, int] = {}
    details: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        y, mem, flags = infer_one(mod, chunk, base_params, p)
        pred[chunk.case_id] = y
        details[chunk.case_id] = {
            "final_mem_NSR": mem[0],
            "final_mem_CHF": mem[1],
            "final_mem_ARR": mem[2],
            "final_mem_AFF": mem[3],
            **flags,
        }
    return pred, details


def random_params(rng: random.Random, idx: int) -> dict[str, Any]:
    return {
        "candidate_id": f"arr_focus_{idx:07d}",
        "strong_nsr_enable": choice(rng, [0, 0, 1]),
        "strong_nsr_count_ge": choice(rng, [18, 20, 22, 24, 26, 28]),
        "strong_nsr_margin_ge": choice(rng, [6, 8, 10, 12, 15, 18, 20]),
        "strong_nsr_aff_le": choice(rng, [0, 1, 3, 5, 8]),
        "strong_nsr_qrs_le": choice(rng, [4, 8, 16, 32, 64, 128]),
        "strong_nsr_rbbb_le": choice(rng, [0, 1, 2, 5]),
        "strong_nsr_arr_inhibit": choice(rng, [1, 2, 4, 8, 12, 16]),
        "arr_from_nsr_enable": choice(rng, [1, 1, 1, 0]),
        "arr_from_nsr_nsr_ge": choice(rng, [16, 18, 20, 21, 22, 24, 26]),
        "arr_from_nsr_arr_ge": choice(rng, [1, 2, 3, 4, 5, 6]),
        "arr_from_nsr_aff_le": choice(rng, [1, 3, 5, 8, 10]),
        "arr_from_nsr_margin_le": choice(rng, [12, 15, 18, 20, 22, 24, 28, 30]),
        "arr_from_nsr_morph_ge": choice(rng, [3000, 3800, 4500, 5000, 5500, 6000]),
        "arr_from_nsr_rdm_ge": choice(rng, [3000, 5000, 6500, 8000, 9500]),
        "arr_from_nsr_pnn_ge": choice(rng, [32, 64, 80, 100, 128, 200]),
        "arr_from_nsr_ecp_ge": choice(rng, [8, 16, 32, 50, 64]),
        "arr_from_nsr_qrs_le": choice(rng, [20, 40, 64, 128, 256, 512]),
        "arr_from_nsr_rbbb_le": choice(rng, [2, 5, 10, 20, 32]),
        "arr_from_nsr_boost": choice(rng, [16, 20, 24, 28, 32, 40, 48]),
        "arr_from_nsr_inhibit_nsr": choice(rng, [8, 12, 16, 20, 24, 32]),
        "arr_from_nsr_inhibit_aff": choice(rng, [0, 2, 4, 8, 12]),
        "arr_from_chf_enable": choice(rng, [1, 1, 0]),
        "arr_from_chf_arr_ge": choice(rng, [6, 8, 9, 10, 12]),
        "arr_from_chf_margin_le": choice(rng, [6, 8, 10, 12, 15]),
        "arr_from_chf_morph_ge": choice(rng, [300, 500, 650, 800, 1000, 1500]),
        "arr_from_chf_qrs_ge": choice(rng, [64, 128, 200, 256, 300]),
        "arr_from_chf_rbbb_ge": choice(rng, [2, 5, 8, 12, 16]),
        "arr_from_chf_rdm_ge": choice(rng, [3000, 5000, 8000, 9500]),
        "arr_from_chf_ecp_ge": choice(rng, [16, 32, 64, 128, 200]),
        "arr_from_chf_boost": choice(rng, [12, 16, 20, 24, 32]),
        "arr_from_chf_inhibit_chf": choice(rng, [8, 12, 16, 20, 24]),
        "arr_from_aff_enable": choice(rng, [1, 1, 0]),
        "arr_from_aff_arr_ge": choice(rng, [4, 5, 6, 7, 8, 10]),
        "arr_from_aff_margin_le": choice(rng, [10, 12, 15, 16, 18, 20]),
        "arr_from_aff_morph_ge": choice(rng, [1000, 1500, 2000, 3000, 4000]),
        "arr_from_aff_rdm_ge": choice(rng, [8000, 12000, 16000, 20000]),
        "arr_from_aff_pnn_ge": choice(rng, [256, 512, 800, 1000]),
        "arr_from_aff_ecp_ge": choice(rng, [64, 128, 256, 400]),
        "arr_from_aff_qrs_le": choice(rng, [64, 128, 256, 512, 1024]),
        "arr_from_aff_rbbb_le": choice(rng, [0, 2, 5, 10]),
        "arr_from_aff_boost": choice(rng, [16, 20, 24, 28, 32, 40]),
        "arr_from_aff_inhibit_aff": choice(rng, [8, 12, 16, 20, 24, 32]),
        "arr_zero_silent_enable": choice(rng, [0, 0, 0, 1]),
        "arr_zero_silent_nsr_ge": choice(rng, [26, 28, 30]),
        "arr_zero_silent_chf_le": choice(rng, [0, 1, 3]),
        "arr_zero_silent_arr_le": choice(rng, [0, 1, 2]),
        "arr_zero_silent_aff_le": choice(rng, [0, 1, 3]),
        "arr_zero_silent_morph_ge": choice(rng, [3000, 4000, 5000, 5400]),
        "arr_zero_silent_rdm_ge": choice(rng, [2500, 3000, 4000, 5000]),
        "arr_zero_silent_abn_le": choice(rng, [20, 32, 64, 100]),
        "arr_zero_silent_qrs_le": choice(rng, [2, 4, 8, 16]),
        "arr_zero_silent_rbbb_le": choice(rng, [0, 1, 2]),
        "arr_zero_silent_boost": choice(rng, [24, 32, 40, 48]),
        "arr_zero_silent_inhibit_nsr": choice(rng, [24, 32, 40, 48]),
    }


def rule_support(details: dict[str, dict[str, Any]]) -> dict[str, int]:
    keys = ["strong_nsr_veto", "arr_from_nsr", "arr_from_chf", "arr_from_aff", "arr_zero_silent"]
    return {key: sum(int(item.get(key, 0)) for item in details.values()) for key in keys}


def score_candidate(train_m: dict[str, Any], val_m: dict[str, Any], support: dict[str, int], baseline: dict[str, Any]) -> float:
    train_arr = float(train_m["per_class"]["ARR"]["recall"])
    val_arr = float(val_m["per_class"]["ARR"]["recall"])
    base_train_arr = float(baseline["train_metrics"]["per_class"]["ARR"]["recall"])
    complexity = sum(1 for key, value in support.items() if value)
    return (
        val_m["correct"] * 10000
        + val_arr * 5000
        + train_arr * 4000
        + train_m["macro_f1"] * 3000
        + train_m["correct"] * 250
        + val_m["macro_f1"] * 2000
        - complexity * 120
        + (train_arr > base_train_arr) * 2000
        + (train_m["correct"] > baseline["train_metrics"]["correct"]) * 2000
    )


def command_search(args: argparse.Namespace) -> None:
    mod = load_snn_module()
    base_params = load_baseline()
    chunks = mod.split_chunks(["train", "val"])
    train = chunks["train"]
    val = chunks["val"]
    base_train_pred, _ = mod.apply_candidate(train, base_params)
    base_val_pred, _ = mod.apply_candidate(val, base_params)
    baseline = {
        "train_metrics": metric(train, base_train_pred),
        "val_metrics": metric(val, base_val_pred),
    }
    rng = random.Random(args.seed)
    rows: list[dict[str, Any]] = []
    best: tuple[float, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, int]] | None = None
    for idx in range(1, args.candidates + 1):
        p = random_params(rng, idx)
        train_pred, train_details = apply_candidate(mod, train, base_params, p)
        val_pred, val_details = apply_candidate(mod, val, base_params, p)
        train_m = metric(train, train_pred)
        val_m = metric(val, val_pred)
        train_arr_ok = train_m["per_class"]["ARR"]["recall"] >= baseline["train_metrics"]["per_class"]["ARR"]["recall"]
        improves = (
            train_m["correct"] > baseline["train_metrics"]["correct"]
            or train_m["macro_f1"] > baseline["train_metrics"]["macro_f1"]
            or train_m["per_class"]["ARR"]["recall"] > baseline["train_metrics"]["per_class"]["ARR"]["recall"]
        )
        if val_m["correct"] < args.min_val_correct:
            continue
        if val_m["per_class"]["ARR"]["recall"] < args.min_val_arr_recall:
            continue
        if train_m["correct"] < args.min_train_correct:
            continue
        if not train_arr_ok or not improves:
            continue
        support = rule_support(train_details)
        score = score_candidate(train_m, val_m, support, baseline)
        rows.append(
            {
                "candidate_id": p["candidate_id"],
                "score": score,
                "train_correct": train_m["correct"],
                "train_macro_f1": train_m["macro_f1"],
                "train_arr_recall": train_m["per_class"]["ARR"]["recall"],
                "val_correct": val_m["correct"],
                "val_macro_f1": val_m["macro_f1"],
                "val_arr_recall": val_m["per_class"]["ARR"]["recall"],
                "support": json.dumps(support, sort_keys=True),
                "params": json.dumps(p, sort_keys=True),
            }
        )
        item = (score, p, train_m, val_m, support)
        if best is None or item[0] > best[0]:
            best = item
        if idx % 50000 == 0:
            if best:
                print(f"searched {idx}; best train={best[2]['correct']}/68 val={best[3]['correct']}/32 arr_train={best[2]['per_class']['ARR']['recall']:.3f}", flush=True)
            else:
                print(f"searched {idx}; no improving candidate yet", flush=True)

    rows.sort(
        key=lambda row: (
            row["val_correct"],
            row["val_arr_recall"],
            row["train_arr_recall"],
            row["train_correct"],
            row["train_macro_f1"],
            row["score"],
        ),
        reverse=True,
    )
    write_csv(RESULTS / "arr_focus_train_val_search.csv", rows[:1000])
    if best is None:
        raise SystemExit("no ARR-focus candidate beat baseline under train/validation gates")
    score, p, train_m, val_m, support = best
    payload = {
        "selection_note": "ARR-focus candidate selected using train/validation only. Test not loaded during search.",
        "baseline_locked": BASELINE_PATH.name,
        "baseline_train_metrics": baseline["train_metrics"],
        "baseline_val_metrics": baseline["val_metrics"],
        "score": score,
        "post_params": p,
        "train_metrics": train_m,
        "val_metrics": val_m,
        "train_rule_support": support,
    }
    write_json(RESULTS / "arr_focus_selected_train_val_locked.json", payload)
    print(
        f"selected {p['candidate_id']} train={train_m['correct']}/68 val={val_m['correct']}/32 "
        f"train_arr={train_m['per_class']['ARR']['recall']:.3f}",
        flush=True,
    )


def prediction_rows(chunks: list[Any], pred: dict[str, int], details: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in chunks:
        item = details[chunk.case_id]
        row = {
            "case_id": chunk.case_id,
            "split": chunk.split,
            "class_label": chunk.class_label,
            "class_id": chunk.class_id,
            "record_id": chunk.record_id,
            "chunk_id": chunk.chunk_id,
            "final_pred_class": pred[chunk.case_id],
            "final_pred_label": CLASSES[pred[chunk.case_id]],
            "correct": int(pred[chunk.case_id] == chunk.class_id),
        }
        for idx, cls in enumerate(CLASSES):
            row[f"pred_count_{cls}"] = chunk.pred_count[idx]
        row.update(item)
        rows.append(row)
    return rows


def command_final_test(args: argparse.Namespace) -> None:
    mod = load_snn_module()
    base_params = load_baseline()
    selected = json.loads((RESULTS / "arr_focus_selected_train_val_locked.json").read_text(encoding="utf-8"))
    p = selected["post_params"]
    out: dict[str, Any] = {}
    chunks = mod.split_chunks(["train", "val", "test"])
    for split in ["train", "val", "test"]:
        pred, details = apply_candidate(mod, chunks[split], base_params, p)
        out[split] = metric(chunks[split], pred)
        write_json(RESULTS / f"arr_focus_python_{split}_metrics.json", out[split])
        write_csv(RESULTS / f"arr_focus_python_{split}_predictions.csv", prediction_rows(chunks[split], pred, details))
    selected["final_train_metrics"] = out["train"]
    selected["final_val_metrics"] = out["val"]
    selected["test_metrics"] = out["test"]
    write_json(RESULTS / "arr_focus_final_test_summary.json", selected)
    print(
        "arr-focus-final-test "
        + " ".join(f"{split}={out[split]['correct']}/{out[split]['total']} ({out[split]['accuracy']*100:.2f}%)" for split in ["train", "val", "test"])
        + f" test_arr_recall={out['test']['per_class']['ARR']['recall']:.3f}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)
    p_search = sub.add_parser("search")
    p_search.add_argument("--seed", type=int, default=55201)
    p_search.add_argument("--candidates", type=int, default=200000)
    p_search.add_argument("--min-train-correct", type=int, default=58)
    p_search.add_argument("--min-val-correct", type=int, default=31)
    p_search.add_argument("--min-val-arr-recall", type=float, default=1.0)
    p_search.set_defaults(func=command_search)
    p_test = sub.add_parser("final-test")
    p_test.set_defaults(func=command_final_test)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
