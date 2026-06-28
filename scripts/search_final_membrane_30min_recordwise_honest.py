from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import final_membrane_30min_recordwise_pipeline as rw  # noqa: E402
import search_final_membrane_30min_recordwise as prior_search  # noqa: E402


RESULTS = rw.RESULTS
CLASSES = rw.CLASSES
OUT_SEARCH = RESULTS / "honest_final_layer_search.csv"
OUT_SELECTED = RESULTS / "honest_final_layer_selected_params.json"
OUT_REPORT = RESULTS / "honest_final_layer_report.md"


@dataclass
class Candidate:
    candidate_id: int
    kind: str
    params: dict
    train_pred: np.ndarray
    val_pred: np.ndarray
    complexity: int
    model: dict | None = None


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


def metric(y_true: np.ndarray, pred: np.ndarray) -> dict:
    return rw.metrics_from_pred(y_true.astype(np.int64), pred.astype(np.int64))


def arr_recall(metrics: dict) -> float:
    return float(metrics["per_class"]["ARR"]["recall"])


def load_table():
    chunks = prior_search.load_chunks()
    rows, feature_names, x, y, split_names = prior_search.build_table(chunks)
    masks = {split: split_names == split for split in rw.SPLITS}
    return rows, feature_names, x, y, split_names, masks


def split_rows(rows: list[dict], split_names: np.ndarray, split: str) -> list[dict]:
    return [row for row, s in zip(rows, split_names.tolist()) if s == split]


def split_pred(pred: np.ndarray, split_names: np.ndarray, split: str) -> np.ndarray:
    return pred[split_names == split]


def feature_indices(feature_names: list[str], mode: str) -> list[int]:
    compact_exact = {
        "majority_margin",
        "majority_pred_class",
        "avg_mem_pred_class",
    }
    compact_prefixes = (
        "pred_count_",
        "mem_sum_",
        "pred_count_diff_",
        "mem_sum_diff_",
        "abnormal_evidence_count_",
        "rhythm_irregular_evidence_count_",
        "morphology_evidence_count_",
        "qrs_maf_count_",
        "qrs_maf_rate_bp_",
        "rbbb_delay_like_count_",
        "rbbb_delay_applied_count_",
        "rbbb_like_rate_bp_",
        "eerg_applied_count_",
        "eerg_ecp_count_",
        "ectopic_pair_count_",
        "rdm_ge50_count_",
        "rdm_ge80_count_",
        "rdm_ge100_count_",
        "pnn_mismatch_count_",
        "pnn_mismatch_rate_bp_",
        "dscr_flip_count_",
        "dscr_slope_count_",
        "ram_code_sum_",
        "ram_avg_code_q8_",
    )
    pred_prefixes = ("pred_count_", "pred_count_diff_", "majority_margin")
    mem_prefixes = ("pred_count_", "mem_sum_", "mem_sum_diff_", "majority_margin")

    out = []
    for i, name in enumerate(feature_names):
        if mode == "pred":
            keep = name == "majority_margin" or name.startswith(("pred_count_", "pred_count_diff_"))
        elif mode == "mem":
            keep = name == "majority_margin" or name.startswith(mem_prefixes)
        elif mode == "compact":
            keep = name in compact_exact or name.startswith(compact_prefixes)
        elif mode == "evidence":
            keep = name in compact_exact or name.startswith(compact_prefixes) or name.startswith(("mem_max_", "mem_min_"))
        elif mode == "all":
            keep = True
        else:
            raise ValueError(mode)
        if keep:
            out.append(i)
    return out


def normalize_train(x_train: np.ndarray, x_other: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std[std < 1e-9] = 1.0
    train_z = np.clip((x_train - mean) / std, -8.0, 8.0)
    other_z = np.clip((x_other - mean) / std, -8.0, 8.0)
    return train_z, other_z, {"mean": mean, "std": std}


def add_bias(x: np.ndarray) -> np.ndarray:
    return np.concatenate([x, np.ones((x.shape[0], 1), dtype=x.dtype)], axis=1)


def ridge_candidates(x: np.ndarray, y: np.ndarray, split_names: np.ndarray, feature_names: list[str], start_id: int) -> list[Candidate]:
    candidates: list[Candidate] = []
    train_mask = split_names == "train"
    val_mask = split_names == "val"
    y_train = y[train_mask]
    target_modes = {
        "onehot_01": np.eye(4, dtype=np.float64)[y_train],
        "onehot_pm1": np.eye(4, dtype=np.float64)[y_train] * 2.0 - 1.0,
    }
    for mode in ["pred", "mem", "compact", "evidence", "all"]:
        idx = feature_indices(feature_names, mode)
        x_train = x[train_mask][:, idx]
        x_val = x[val_mask][:, idx]
        x_train_z, x_val_z, norm = normalize_train(x_train, x_val)
        a_train = add_bias(x_train_z)
        a_val = add_bias(x_val_z)
        for target_name, yy in target_modes.items():
            for lam in [0.001, 0.01, 0.1, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0]:
                reg = np.eye(a_train.shape[1], dtype=np.float64) * lam
                reg[-1, -1] = 0.0
                try:
                    weights = np.linalg.solve(a_train.T @ a_train + reg, a_train.T @ yy)
                except np.linalg.LinAlgError:
                    weights = np.linalg.pinv(a_train.T @ a_train + reg) @ a_train.T @ yy
                train_pred = np.argmax(a_train @ weights, axis=1).astype(np.int64)
                val_pred = np.argmax(a_val @ weights, axis=1).astype(np.int64)
                candidates.append(
                    Candidate(
                        candidate_id=start_id + len(candidates),
                        kind="ridge_membrane",
                        params={"feature_mode": mode, "target": target_name, "lambda": lam},
                        train_pred=train_pred,
                        val_pred=val_pred,
                        complexity=len(idx) + 4,
                        model={
                            "feature_mode": mode,
                            "feature_names": [feature_names[i] for i in idx],
                            "lambda": lam,
                            "target": target_name,
                            "weights": weights.tolist(),
                            "mean": norm["mean"].tolist(),
                            "std": norm["std"].tolist(),
                        },
                    )
                )
    return candidates


def centroid_candidates(x: np.ndarray, y: np.ndarray, split_names: np.ndarray, feature_names: list[str], start_id: int) -> list[Candidate]:
    candidates: list[Candidate] = []
    train_mask = split_names == "train"
    val_mask = split_names == "val"
    y_train = y[train_mask]
    for mode in ["pred", "mem", "compact", "evidence"]:
        idx = feature_indices(feature_names, mode)
        x_train = x[train_mask][:, idx]
        x_val = x[val_mask][:, idx]
        x_train_z, x_val_z, norm = normalize_train(x_train, x_val)
        centroids = np.vstack([x_train_z[y_train == cls].mean(axis=0) for cls in range(4)])
        for distance in ["l2", "l1"]:
            if distance == "l2":
                train_score = -np.sum((x_train_z[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
                val_score = -np.sum((x_val_z[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
            else:
                train_score = -np.sum(np.abs(x_train_z[:, None, :] - centroids[None, :, :]), axis=2)
                val_score = -np.sum(np.abs(x_val_z[:, None, :] - centroids[None, :, :]), axis=2)
            candidates.append(
                Candidate(
                    candidate_id=start_id + len(candidates),
                    kind="centroid_membrane",
                    params={"feature_mode": mode, "distance": distance},
                    train_pred=np.argmax(train_score, axis=1).astype(np.int64),
                    val_pred=np.argmax(val_score, axis=1).astype(np.int64),
                    complexity=len(idx),
                    model={
                        "feature_mode": mode,
                        "feature_names": [feature_names[i] for i in idx],
                        "distance": distance,
                        "centroids": centroids.tolist(),
                        "mean": norm["mean"].tolist(),
                        "std": norm["std"].tolist(),
                    },
                )
            )
    return candidates


def perceptron_candidates(x: np.ndarray, y: np.ndarray, split_names: np.ndarray, feature_names: list[str], start_id: int) -> list[Candidate]:
    candidates: list[Candidate] = []
    train_mask = split_names == "train"
    val_mask = split_names == "val"
    y_train = y[train_mask]
    for mode in ["pred", "mem", "compact", "evidence"]:
        idx = feature_indices(feature_names, mode)
        x_train = x[train_mask][:, idx]
        x_val = x[val_mask][:, idx]
        x_train_z, x_val_z, norm = normalize_train(x_train, x_val)
        a_train = add_bias(x_train_z)
        a_val = add_bias(x_val_z)
        order = np.arange(a_train.shape[0])
        for epochs in [1, 2, 3, 5, 8, 13, 21, 34, 55, 89]:
            w = np.zeros((a_train.shape[1], 4), dtype=np.float64)
            for _ in range(epochs):
                for i in order:
                    scores = a_train[i] @ w
                    pred = int(np.argmax(scores))
                    true = int(y_train[i])
                    if pred != true:
                        w[:, true] += a_train[i]
                        w[:, pred] -= a_train[i]
            candidates.append(
                Candidate(
                    candidate_id=start_id + len(candidates),
                    kind="perceptron_membrane",
                    params={"feature_mode": mode, "epochs": epochs},
                    train_pred=np.argmax(a_train @ w, axis=1).astype(np.int64),
                    val_pred=np.argmax(a_val @ w, axis=1).astype(np.int64),
                    complexity=len(idx) + epochs,
                    model={
                        "feature_mode": mode,
                        "feature_names": [feature_names[i] for i in idx],
                        "epochs": epochs,
                        "weights": w.tolist(),
                        "mean": norm["mean"].tolist(),
                        "std": norm["std"].tolist(),
                    },
                )
            )
    return candidates


def threshold_values(values: np.ndarray) -> list[float]:
    unique = np.unique(values)
    if len(unique) <= 1:
        return []
    if len(unique) <= 24:
        vals = ((unique[:-1] + unique[1:]) / 2.0).tolist()
    else:
        vals = np.unique(np.percentile(unique, [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95])).tolist()
    return [float(v) for v in vals]


def override_candidates(
    x: np.ndarray,
    y: np.ndarray,
    split_names: np.ndarray,
    feature_names: list[str],
    base_pred: np.ndarray,
    base_name: str,
    start_id: int,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    train_mask = split_names == "train"
    val_mask = split_names == "val"
    idx = feature_indices(feature_names, "evidence")
    # Keep this family explicitly interpretable and SNN-like: one thresholded
    # evidence spike gives a fixed rescue/inhibition override.
    for feature in idx:
        train_values = x[train_mask, feature]
        for threshold in threshold_values(train_values):
            for direction in ["le", "gt"]:
                cond_all = x[:, feature] <= threshold if direction == "le" else x[:, feature] > threshold
                for src in range(4):
                    src_mask = base_pred == src
                    if not np.any(src_mask & train_mask & cond_all):
                        continue
                    for dst in range(4):
                        if src == dst:
                            continue
                        pred = base_pred.copy()
                        pred[src_mask & cond_all] = dst
                        candidates.append(
                            Candidate(
                                candidate_id=start_id + len(candidates),
                                kind="single_threshold_override",
                                params={
                                    "base": base_name,
                                    "source_class": CLASSES[src],
                                    "target_class": CLASSES[dst],
                                    "feature": feature_names[feature],
                                    "direction": direction,
                                    "threshold": threshold,
                                },
                                train_pred=pred[train_mask].astype(np.int64),
                                val_pred=pred[val_mask].astype(np.int64),
                                complexity=3,
                            )
                        )
    return candidates


def dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    seen: set[tuple[bytes, bytes, str]] = set()
    out: list[Candidate] = []
    for cand in candidates:
        key = (cand.train_pred.tobytes(), cand.val_pred.tobytes(), cand.kind)
        if key in seen:
            continue
        seen.add(key)
        cand.candidate_id = len(out)
        out.append(cand)
    return out


def selection_key(val_m: dict, cand: Candidate) -> tuple:
    return (
        float(val_m["macro_f1"]),
        float(val_m["balanced_accuracy"]),
        float(arr_recall(val_m)),
        -float(val_m["recall_range"]),
        float(val_m["accuracy"]),
        -int(cand.complexity),
    )


def predict_full_candidate(cand: Candidate, x: np.ndarray, feature_names: list[str], split_names: np.ndarray, rows: list[dict]) -> np.ndarray:
    if cand.kind == "majority_vote":
        return prior_search.majority_pred(x, feature_names)
    if cand.kind == "average_class_mem":
        return prior_search.avg_mem_pred(x, feature_names)
    if cand.kind == "guarded_rule":
        train_rows = split_rows(rows, split_names, "train")
        val_rows = split_rows(rows, split_names, "val")
        test_rows = split_rows(rows, split_names, "test")
        parts = {
            "train": prior_search.pred_from_rule(train_rows, cand.params["arr"], cand.params["aff_quiet"], cand.params["aff_persistent"], cand.params["nsr"]),
            "val": prior_search.pred_from_rule(val_rows, cand.params["arr"], cand.params["aff_quiet"], cand.params["aff_persistent"], cand.params["nsr"]),
            "test": prior_search.pred_from_rule(test_rows, cand.params["arr"], cand.params["aff_quiet"], cand.params["aff_persistent"], cand.params["nsr"]),
        }
        out = np.zeros(len(rows), dtype=np.int64)
        for split, pred in parts.items():
            out[split_names == split] = pred
        return out
    if cand.kind == "threshold_tree":
        return prior_search.predict_tree(cand.model, x)
    if cand.kind == "single_threshold_override":
        base = prior_search.majority_pred(x, feature_names) if cand.params["base"] == "majority" else prior_search.avg_mem_pred(x, feature_names)
        feature = feature_names.index(cand.params["feature"])
        cond = x[:, feature] <= cand.params["threshold"] if cand.params["direction"] == "le" else x[:, feature] > cand.params["threshold"]
        src = CLASSES.index(cand.params["source_class"])
        dst = CLASSES.index(cand.params["target_class"])
        out = base.copy()
        out[(base == src) & cond] = dst
        return out.astype(np.int64)
    if cand.kind in {"ridge_membrane", "centroid_membrane", "perceptron_membrane"}:
        model = cand.model or {}
        idx = [feature_names.index(name) for name in model["feature_names"]]
        xx = x[:, idx]
        mean = np.asarray(model["mean"], dtype=np.float64)
        std = np.asarray(model["std"], dtype=np.float64)
        xx = np.clip((xx - mean) / std, -8.0, 8.0)
        if cand.kind == "centroid_membrane":
            centroids = np.asarray(model["centroids"], dtype=np.float64)
            if model["distance"] == "l2":
                score = -np.sum((xx[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
            else:
                score = -np.sum(np.abs(xx[:, None, :] - centroids[None, :, :]), axis=2)
            return np.argmax(score, axis=1).astype(np.int64)
        weights = np.asarray(model["weights"], dtype=np.float64)
        score = add_bias(xx) @ weights
        return np.argmax(score, axis=1).astype(np.int64)
    raise ValueError(cand.kind)


def prediction_rows(rows: list[dict], pred: np.ndarray) -> list[dict]:
    out = []
    for row, p in zip(rows, pred.tolist()):
        f = row["features"]
        # For reporting, final_mem is the simple vote membrane unless the model
        # family has a separate dense score. This keeps the CSV RTL-friendly.
        mem = [int(f.get(f"pred_count_{cls}", 0)) for cls in CLASSES]
        out.append(
            {
                "case_id": row["case_id"],
                "split": row["split"],
                "class_label": row["class_label"],
                "class_id": row["class_id"],
                "record_id": row["record_id"],
                "chunk_id": row["chunk_id"],
                "chunk_file": row["chunk_file"],
                "final_pred_class": int(p),
                "final_pred_label": CLASSES[int(p)],
                "correct": int(int(p) == int(row["class_id"])),
                "final_mem_NSR": mem[0],
                "final_mem_CHF": mem[1],
                "final_mem_ARR": mem[2],
                "final_mem_AFF": mem[3],
            }
        )
    return out


def run() -> None:
    rows, feature_names, x, y, split_names, masks = load_table()
    y_train = y[masks["train"]]
    y_val = y[masks["val"]]
    y_test = y[masks["test"]]

    maj = prior_search.majority_pred(x, feature_names)
    avg = prior_search.avg_mem_pred(x, feature_names)

    candidates: list[Candidate] = [
        Candidate(0, "majority_vote", {}, split_pred(maj, split_names, "train"), split_pred(maj, split_names, "val"), 1),
        Candidate(1, "average_class_mem", {}, split_pred(avg, split_names, "train"), split_pred(avg, split_names, "val"), 1),
    ]
    candidates.extend(prior_search.rule_candidates(rows, split_names, len(candidates)))
    candidates.extend(prior_search.tree_candidates(x, y, split_names, len(candidates)))
    candidates.extend(ridge_candidates(x, y, split_names, feature_names, len(candidates)))
    candidates.extend(centroid_candidates(x, y, split_names, feature_names, len(candidates)))
    candidates.extend(perceptron_candidates(x, y, split_names, feature_names, len(candidates)))
    candidates.extend(override_candidates(x, y, split_names, feature_names, maj, "majority", len(candidates)))
    candidates.extend(override_candidates(x, y, split_names, feature_names, avg, "average_mem", len(candidates)))
    candidates = dedupe_candidates(candidates)

    majority_train_m = metric(y_train, split_pred(maj, split_names, "train"))
    majority_val_m = metric(y_val, split_pred(maj, split_names, "val"))
    majority_test_m = metric(y_test, split_pred(maj, split_names, "test"))
    val_macro_floor = float(majority_val_m["macro_f1"])
    val_arr_floor = arr_recall(majority_val_m)

    search_rows = []
    selected: tuple[Candidate, dict, dict] | None = None
    selected_key: tuple | None = None
    admissible_count = 0
    for cand in candidates:
        train_m = metric(y_train, cand.train_pred)
        val_m = metric(y_val, cand.val_pred)
        admissible = (
            float(val_m["macro_f1"]) >= val_macro_floor - 1e-12
            and arr_recall(val_m) >= val_arr_floor - 1e-12
        )
        if admissible:
            admissible_count += 1
        row = {
            "candidate_id": cand.candidate_id,
            "kind": cand.kind,
            "admissible_vs_majority": int(admissible),
            "params": json.dumps(cand.params, sort_keys=True),
            "complexity": cand.complexity,
            "train_accuracy": train_m["accuracy"],
            "train_macro_f1": train_m["macro_f1"],
            "train_arr_recall": arr_recall(train_m),
            "train_balanced_accuracy": train_m["balanced_accuracy"],
            "train_recall_range": train_m["recall_range"],
            "val_accuracy": val_m["accuracy"],
            "val_macro_f1": val_m["macro_f1"],
            "val_arr_recall": arr_recall(val_m),
            "val_balanced_accuracy": val_m["balanced_accuracy"],
            "val_recall_range": val_m["recall_range"],
            "val_min_recall": val_m["min_recall"],
        }
        search_rows.append(row)
        if not admissible:
            continue
        key = selection_key(val_m, cand)
        if selected_key is None or key > selected_key:
            selected_key = key
            selected = (cand, train_m, val_m)

    if selected is None:
        selected = (candidates[0], majority_train_m, majority_val_m)

    cand, train_m, val_m = selected
    full_pred = predict_full_candidate(cand, x, feature_names, split_names, rows)
    test_pred = full_pred[masks["test"]]
    test_m = metric(y_test, test_pred)

    write_csv(OUT_SEARCH, search_rows)
    selected_payload = {
        "note": "Honest record-wise search: candidates are generated from train, selected by validation only; test is evaluated once after selection. Search CSV intentionally has no test metrics.",
        "classes": CLASSES,
        "selection_constraint": {
            "candidate_val_macro_f1_must_be_at_least_majority": val_macro_floor,
            "candidate_val_arr_recall_must_be_at_least_majority": val_arr_floor,
            "admissible_candidate_count": admissible_count,
        },
        "majority_baseline": {
            "train": majority_train_m,
            "val": majority_val_m,
            "test": majority_test_m,
        },
        "candidate_id": cand.candidate_id,
        "kind": cand.kind,
        "params": cand.params,
        "complexity": cand.complexity,
        "model": cand.model,
        "metrics": {
            "train": train_m,
            "val": val_m,
            "test": test_m,
        },
    }
    OUT_SELECTED.write_text(json.dumps(selected_payload, indent=2), encoding="utf-8")

    for split in rw.SPLITS:
        split_m = metric(y[masks[split]], full_pred[masks[split]])
        (RESULTS / f"honest_python_{split}_metrics.json").write_text(json.dumps(split_m, indent=2), encoding="utf-8")
        write_csv(
            RESULTS / f"honest_python_{split}_predictions.csv",
            prediction_rows([row for row, s in zip(rows, split_names.tolist()) if s == split], full_pred[masks[split]]),
        )

    report = [
        "# Honest Final Membrane Search",
        "",
        "No oracle/test-guided candidate selection was used.",
        "",
        "## Selection Rule",
        "",
        "- Generate candidates from train split only.",
        "- Select the final candidate by validation macro-F1, balanced accuracy, ARR recall, recall balance, accuracy, and simplicity.",
        "- A candidate is admissible only if validation macro-F1 and validation ARR recall are at least the majority-vote baseline.",
        "- Evaluate test once after the validation-selected candidate is fixed.",
        "",
        "## Majority Baseline",
        "",
        f"- train: {majority_train_m['correct']}/{majority_train_m['total']} = {majority_train_m['accuracy']*100:.2f}%, macro-F1 {majority_train_m['macro_f1']*100:.2f}%, ARR recall {arr_recall(majority_train_m)*100:.2f}%",
        f"- val: {majority_val_m['correct']}/{majority_val_m['total']} = {majority_val_m['accuracy']*100:.2f}%, macro-F1 {majority_val_m['macro_f1']*100:.2f}%, ARR recall {arr_recall(majority_val_m)*100:.2f}%",
        f"- test: {majority_test_m['correct']}/{majority_test_m['total']} = {majority_test_m['accuracy']*100:.2f}%, macro-F1 {majority_test_m['macro_f1']*100:.2f}%, ARR recall {arr_recall(majority_test_m)*100:.2f}%",
        "",
        "## Selected Candidate",
        "",
        f"- candidate_id: {cand.candidate_id}",
        f"- kind: {cand.kind}",
        f"- admissible candidates: {admissible_count}/{len(candidates)}",
        f"- params: `{json.dumps(cand.params, sort_keys=True)}`",
        "",
        "## Honest Result",
        "",
        f"- train: {train_m['correct']}/{train_m['total']} = {train_m['accuracy']*100:.2f}%, macro-F1 {train_m['macro_f1']*100:.2f}%, ARR recall {arr_recall(train_m)*100:.2f}%",
        f"- val: {val_m['correct']}/{val_m['total']} = {val_m['accuracy']*100:.2f}%, macro-F1 {val_m['macro_f1']*100:.2f}%, ARR recall {arr_recall(val_m)*100:.2f}%",
        f"- test: {test_m['correct']}/{test_m['total']} = {test_m['accuracy']*100:.2f}%, macro-F1 {test_m['macro_f1']*100:.2f}%, ARR recall {arr_recall(test_m)*100:.2f}%",
        "",
        "## Test Confusion Matrix",
        "",
        "Rows=true, columns=pred, class order NSR/CHF/ARR/AFF.",
        "",
        "```text",
        json.dumps(test_m["confusion_matrix"]),
        "```",
    ]
    OUT_REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(
        f"[honest-selected] id={cand.candidate_id} kind={cand.kind} "
        f"val={val_m['correct']}/{val_m['total']} macro_f1={val_m['macro_f1']:.4f} "
        f"test={test_m['correct']}/{test_m['total']} acc={test_m['accuracy']:.4f}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
