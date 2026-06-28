from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parents[0]
sys.path.insert(0, str(SCRIPT_DIR))

import final_membrane_30min_recordwise_pipeline as rw  # noqa: E402


RESULTS = rw.RESULTS
CLASSES = rw.CLASSES
SPLITS = rw.SPLITS

SEARCH_CSV = RESULTS / "final_layer_search.csv"
SELECTED_JSON = RESULTS / "final_layer_selected_params.json"


EXTRA_SNAPSHOT_FIELDS = [
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


@dataclass
class Candidate:
    candidate_id: int
    kind: str
    params: dict
    train_pred: np.ndarray
    val_pred: np.ndarray
    complexity: int
    model: object | None = None


@dataclass
class TreeNode:
    pred_class: int
    feature: int | None = None
    threshold: float | None = None
    left: "TreeNode | None" = None
    right: "TreeNode | None" = None


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


def load_chunks() -> dict[str, list[dict]]:
    dumps = rw.load_recordwise_snapshot_dumps()
    return {split: rw.build_chunks(dumps[split]) for split in SPLITS}


def summarize_chunk(chunk: dict) -> dict:
    pred_count = [0, 0, 0, 0]
    mem_sum = [0, 0, 0, 0]
    mem_max = [-10**18] * 4
    mem_min = [10**18] * 4
    sums = {field: 0 for field in rw.FEATURE_SUM_FIELDS + EXTRA_SNAPSHOT_FIELDS}
    active = {field: 0 for field in rw.FEATURE_SUM_FIELDS + EXTRA_SNAPSHOT_FIELDS}
    maxs = {field: -10**18 for field in rw.FEATURE_SUM_FIELDS + EXTRA_SNAPSHOT_FIELDS}

    for snap in chunk["snapshots"]:
        pred_count[rw.safe_int(snap["snapshot_pred_class"])] += 1
        for i, cls in enumerate(CLASSES):
            value = rw.safe_int(snap[f"class_mem_{cls}"])
            mem_sum[i] += value
            mem_max[i] = max(mem_max[i], value)
            mem_min[i] = min(mem_min[i], value)
        for field in sums:
            value = rw.safe_int(snap.get(field, 0))
            sums[field] += value
            active[field] += int(value > 0)
            maxs[field] = max(maxs[field], value)

    majority = int(max(range(4), key=lambda i: (pred_count[i], -i)))
    avg_mem = int(max(range(4), key=lambda i: (mem_sum[i], -i)))
    feats: dict[str, int] = {
        "majority_pred_class": majority,
        "avg_mem_pred_class": avg_mem,
        "majority_margin": pred_count[majority] - sorted(pred_count, reverse=True)[1],
    }
    for i, cls in enumerate(CLASSES):
        feats[f"pred_count_{cls}"] = pred_count[i]
        feats[f"mem_sum_{cls}"] = mem_sum[i]
        feats[f"mem_max_{cls}"] = mem_max[i]
        feats[f"mem_min_{cls}"] = mem_min[i]
    for i, a in enumerate(CLASSES):
        for j, b in enumerate(CLASSES):
            if i < j:
                feats[f"pred_count_diff_{a}_{b}"] = pred_count[i] - pred_count[j]
                feats[f"mem_sum_diff_{a}_{b}"] = mem_sum[i] - mem_sum[j]
    for field in sums:
        feats[f"{field}_sum"] = sums[field]
        feats[f"{field}_active"] = active[field]
        feats[f"{field}_max"] = maxs[field]
    return {
        "case_id": chunk["case_id"],
        "split": chunk["split"],
        "class_label": chunk["class_label"],
        "class_id": int(chunk["class_id"]),
        "record_id": chunk["record_id"],
        "chunk_id": chunk["chunk_id"],
        "chunk_file": chunk["chunk_file"],
        "features": feats,
    }


def build_table(chunks: dict[str, list[dict]]):
    rows = []
    for split in SPLITS:
        rows.extend(summarize_chunk(chunk) for chunk in chunks[split])
    feature_names = sorted({key for row in rows for key in row["features"]})
    x = np.array([[row["features"].get(name, 0) for name in feature_names] for row in rows], dtype=np.float64)
    y = np.array([row["class_id"] for row in rows], dtype=np.int64)
    split_names = np.array([row["split"] for row in rows])
    return rows, feature_names, x, y, split_names


def metrics(y_true: np.ndarray, pred: np.ndarray) -> dict:
    return rw.metrics_from_pred(y_true.astype(np.int64), pred.astype(np.int64))


def split_pred(pred: np.ndarray, split_names: np.ndarray, split: str) -> np.ndarray:
    return pred[split_names == split]


def metric_for_split(y: np.ndarray, split_names: np.ndarray, pred: np.ndarray, split: str) -> dict:
    mask = split_names == split
    return metrics(y[mask], pred[mask])


def majority_pred(x: np.ndarray, feature_names: list[str]) -> np.ndarray:
    return x[:, feature_names.index("majority_pred_class")].astype(np.int64)


def avg_mem_pred(x: np.ndarray, feature_names: list[str]) -> np.ndarray:
    return x[:, feature_names.index("avg_mem_pred_class")].astype(np.int64)


def pred_from_rule(rows: list[dict], arr_param, aff_quiet_param, aff_persistent_param, nsr_param) -> np.ndarray:
    pred = []
    for row in rows:
        f = row["features"]
        p = int(f["majority_pred_class"])
        arr_protect = False
        if arr_param is not None:
            arr_th, abnormal_sum_th, qrs_maf_active_th = arr_param
            arr_protect = (
                f["pred_count_ARR"] >= arr_th
                and f["abnormal_evidence_count_sum"] >= abnormal_sum_th
                and f["qrs_maf_count_active"] >= qrs_maf_active_th
            )
            if arr_protect:
                pred.append(2)
                continue

        if nsr_param is not None and not arr_protect:
            (nsr_count_th,) = nsr_param
            abnormal_block = (
                f["pred_count_ARR"] >= 15
                or f["rbbb_delay_like_count_sum"] > 0
                or f["rbbb_delay_applied_count_sum"] > 0
                or f["eerg_applied_count_sum"] > 0
                or f["eerg_ecp_count_sum"] > 0
                or f["rdm_ge50_count_sum"] > 0
                or f["qrs_maf_count_sum"] > 0
                or f["ectopic_pair_count_sum"] > 0
                or f["pnn_mismatch_count_sum"] > 0
            )
            if f["pred_count_NSR"] >= nsr_count_th and not abnormal_block:
                pred.append(0)
                continue

        if aff_persistent_param is not None:
            chf_min, aff_min, abnormal_min = aff_persistent_param
            if (
                p == 1
                and f["pred_count_CHF"] >= chf_min
                and f["pred_count_AFF"] >= aff_min
                and f["abnormal_evidence_count_sum"] >= abnormal_min
            ):
                pred.append(3)
                continue

        if aff_quiet_param is not None:
            chf_th, aff_max, abnormal_max, qrs_maf_max = aff_quiet_param
            if (
                p == 1
                and f["pred_count_CHF"] >= chf_th
                and f["pred_count_AFF"] <= aff_max
                and f["abnormal_evidence_count_sum"] <= abnormal_max
                and f["qrs_maf_count_sum"] <= qrs_maf_max
            ):
                pred.append(3)
                continue

        pred.append(p)
    return np.array(pred, dtype=np.int64)


def selected_guarded_scores(rows: list[dict], params: dict) -> tuple[np.ndarray, np.ndarray]:
    scores = []
    pred = []
    for row in rows:
        f = row["features"]
        nsr = int(f["pred_count_NSR"])
        chf = int(f["pred_count_CHF"])
        arr = int(f["pred_count_ARR"])
        aff = int(f["pred_count_AFF"])
        score = [nsr, chf, arr, aff]
        majority_chf = chf > nsr and chf >= arr and chf >= aff
        arr_param = params.get("arr")
        aff_persistent = params.get("aff_persistent")
        aff_quiet = params.get("aff_quiet")
        arr_fire = False
        if arr_param is not None:
            arr_th, abnormal_sum_th, qrs_maf_active_th = arr_param
            arr_fire = (
                arr >= arr_th
                and int(f["abnormal_evidence_count_sum"]) >= abnormal_sum_th
                and int(f["qrs_maf_count_active"]) >= qrs_maf_active_th
            )
        if arr_fire:
            score[2] += 64
        elif aff_persistent is not None:
            chf_min, aff_min, abnormal_min = aff_persistent
            if majority_chf and chf >= chf_min and aff >= aff_min and int(f["abnormal_evidence_count_sum"]) >= abnormal_min:
                score[3] += 64
        elif aff_quiet is not None:
            chf_th, aff_max, abnormal_max, qrs_maf_max = aff_quiet
            if (
                majority_chf
                and chf >= chf_th
                and aff <= aff_max
                and int(f["abnormal_evidence_count_sum"]) <= abnormal_max
                and int(f["qrs_maf_count_sum"]) <= qrs_maf_max
            ):
                score[3] += 64
        p = int(max(range(4), key=lambda i: (score[i], -i)))
        scores.append(score)
        pred.append(p)
    return np.array(pred, dtype=np.int64), np.array(scores, dtype=np.int32)


def mask_arr(rows: list[dict], param) -> np.ndarray:
    if param is None:
        return np.zeros(len(rows), dtype=bool)
    arr_th, abnormal_sum_th, qrs_maf_active_th = param
    return np.array(
        [
            row["features"]["pred_count_ARR"] >= arr_th
            and row["features"]["abnormal_evidence_count_sum"] >= abnormal_sum_th
            and row["features"]["qrs_maf_count_active"] >= qrs_maf_active_th
            for row in rows
        ],
        dtype=bool,
    )


def mask_aff_quiet(rows: list[dict], param) -> np.ndarray:
    if param is None:
        return np.zeros(len(rows), dtype=bool)
    chf_th, aff_max, abnormal_max, qrs_max = param
    return np.array(
        [
            row["features"]["majority_pred_class"] == 1
            and row["features"]["pred_count_CHF"] >= chf_th
            and row["features"]["pred_count_AFF"] <= aff_max
            and row["features"]["abnormal_evidence_count_sum"] <= abnormal_max
            and row["features"]["qrs_maf_count_sum"] <= qrs_max
            for row in rows
        ],
        dtype=bool,
    )


def mask_aff_persistent(rows: list[dict], param) -> np.ndarray:
    if param is None:
        return np.zeros(len(rows), dtype=bool)
    chf_min, aff_min, abnormal_min = param
    return np.array(
        [
            row["features"]["majority_pred_class"] == 1
            and row["features"]["pred_count_CHF"] >= chf_min
            and row["features"]["pred_count_AFF"] >= aff_min
            and row["features"]["abnormal_evidence_count_sum"] >= abnormal_min
            for row in rows
        ],
        dtype=bool,
    )


def mask_nsr(rows: list[dict], param) -> np.ndarray:
    if param is None:
        return np.zeros(len(rows), dtype=bool)
    (nsr_count_th,) = param
    out = []
    for row in rows:
        f = row["features"]
        abnormal_block = (
            f["pred_count_ARR"] >= 15
            or f["rbbb_delay_like_count_sum"] > 0
            or f["rbbb_delay_applied_count_sum"] > 0
            or f["eerg_applied_count_sum"] > 0
            or f["eerg_ecp_count_sum"] > 0
            or f["rdm_ge50_count_sum"] > 0
            or f["qrs_maf_count_sum"] > 0
            or f["ectopic_pair_count_sum"] > 0
            or f["pnn_mismatch_count_sum"] > 0
        )
        out.append(f["pred_count_NSR"] >= nsr_count_th and not abnormal_block)
    return np.array(out, dtype=bool)


def dedupe_params(params: list, train_rows: list[dict], val_rows: list[dict], mask_fn) -> list:
    seen = {}
    ordered = []
    for param in params:
        key = (mask_fn(train_rows, param).tobytes(), mask_fn(val_rows, param).tobytes())
        if key not in seen:
            seen[key] = param
            ordered.append(param)
    return ordered


def rule_candidates(rows: list[dict], split_names: np.ndarray, next_id: int) -> list[Candidate]:
    candidates = []
    train_rows = [row for row, s in zip(rows, split_names.tolist()) if s == "train"]
    val_rows = [row for row, s in zip(rows, split_names.tolist()) if s == "val"]

    arr_params = [None] + [
        (arr_th, abnormal_sum_th, qrs_active_th)
        for arr_th in [8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20]
        for abnormal_sum_th in [0, 250, 500, 1000, 1500, 2000, 3000, 4000, 5000]
        for qrs_active_th in [0, 5, 10, 15, 20, 25, 30]
    ]
    aff_quiet_params = [None] + [
        (chf_th, aff_max, abnormal_max, qrs_max)
        for chf_th in [14, 16, 18, 20, 23, 25, 27, 28, 29, 30]
        for aff_max in [0, 1, 2, 4, 6, 9, 12]
        for abnormal_max in [0, 5, 10, 20, 30, 50, 75, 100, 150, 250]
        for qrs_max in [0, 2, 5, 10, 25]
    ]
    aff_persistent_params = [None] + [
        (chf_min, aff_min, abnormal_min)
        for chf_min in [8, 10, 12, 14, 16, 18, 20, 22, 25]
        for aff_min in [3, 5, 8, 10, 11, 12, 14, 16]
        for abnormal_min in [500, 1000, 1500, 2000, 2500, 3000]
    ]
    nsr_params = [None, (13,), (15,), (18,), (20,), (23,), (25,)]

    arr_params = dedupe_params(arr_params, train_rows, val_rows, mask_arr)
    aff_quiet_params = dedupe_params(aff_quiet_params, train_rows, val_rows, mask_aff_quiet)
    aff_persistent_params = dedupe_params(aff_persistent_params, train_rows, val_rows, mask_aff_persistent)
    nsr_params = dedupe_params(nsr_params, train_rows, val_rows, mask_nsr)

    seen = set()
    for arr in arr_params:
        for quiet in aff_quiet_params:
            for persistent in aff_persistent_params:
                for nsr in nsr_params:
                    if nsr is not None and arr is None and quiet is None and persistent is None:
                        continue
                    train_pred = pred_from_rule(train_rows, arr, quiet, persistent, nsr)
                    val_pred = pred_from_rule(val_rows, arr, quiet, persistent, nsr)
                    key = (train_pred.tobytes(), val_pred.tobytes())
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(
                        Candidate(
                            candidate_id=next_id + len(candidates),
                            kind="guarded_rule",
                            params={"arr": arr, "aff_quiet": quiet, "aff_persistent": persistent, "nsr": nsr},
                            train_pred=train_pred,
                            val_pred=val_pred,
                            complexity=sum(x is not None for x in [arr, quiet, persistent, nsr]),
                        )
                    )
    return candidates


def gini(labels: np.ndarray) -> float:
    if len(labels) == 0:
        return 0.0
    counts = np.bincount(labels, minlength=4).astype(np.float64) / float(len(labels))
    return 1.0 - float(np.sum(counts * counts))


def threshold_candidates(values: np.ndarray) -> np.ndarray:
    unique = np.unique(values)
    if len(unique) <= 1:
        return np.array([], dtype=np.float64)
    if len(unique) <= 40:
        return (unique[:-1] + unique[1:]) / 2.0
    return np.unique(np.percentile(unique, [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95]))


def best_split(x: np.ndarray, y: np.ndarray, idx: np.ndarray, feature_indices, min_leaf: int):
    base_gini = gini(y[idx])
    best = (0.0, None, None, None, None)
    n = len(idx)
    for feature in feature_indices:
        values = x[idx, feature]
        for threshold in threshold_candidates(values):
            left = idx[values <= threshold]
            right = idx[values > threshold]
            if len(left) < min_leaf or len(right) < min_leaf:
                continue
            gain = base_gini - (len(left) / n) * gini(y[left]) - (len(right) / n) * gini(y[right])
            if gain > best[0]:
                best = (gain, feature, float(threshold), left, right)
    return best


def build_tree(x: np.ndarray, y: np.ndarray, idx: np.ndarray, *, depth: int, max_depth: int, min_leaf: int, feature_indices) -> TreeNode:
    counts = np.bincount(y[idx], minlength=4)
    pred_class = int(np.argmax(counts))
    if depth >= max_depth or len(idx) <= min_leaf or counts[pred_class] == len(idx):
        return TreeNode(pred_class=pred_class)
    gain, feature, threshold, left, right = best_split(x, y, idx, feature_indices, min_leaf)
    if feature is None or gain <= 1e-12:
        return TreeNode(pred_class=pred_class)
    return TreeNode(
        pred_class=pred_class,
        feature=int(feature),
        threshold=float(threshold),
        left=build_tree(x, y, left, depth=depth + 1, max_depth=max_depth, min_leaf=min_leaf, feature_indices=feature_indices),
        right=build_tree(x, y, right, depth=depth + 1, max_depth=max_depth, min_leaf=min_leaf, feature_indices=feature_indices),
    )


def predict_tree(node: TreeNode, x: np.ndarray) -> np.ndarray:
    out = []
    for i in range(x.shape[0]):
        cur = node
        while cur.feature is not None:
            cur = cur.left if x[i, cur.feature] <= cur.threshold else cur.right
        out.append(cur.pred_class)
    return np.array(out, dtype=np.int64)


def count_nodes(node: TreeNode) -> int:
    if node.feature is None:
        return 1
    return 1 + count_nodes(node.left) + count_nodes(node.right)


def tree_to_dict(node: TreeNode, feature_names: list[str]) -> dict:
    if node.feature is None:
        return {"leaf_class": CLASSES[node.pred_class], "leaf_class_id": node.pred_class}
    return {
        "feature": feature_names[node.feature],
        "feature_index": node.feature,
        "threshold": node.threshold,
        "if_le": tree_to_dict(node.left, feature_names),
        "if_gt": tree_to_dict(node.right, feature_names),
    }


def tree_candidates(x: np.ndarray, y: np.ndarray, split_names: np.ndarray, next_id: int) -> list[Candidate]:
    train_idx = np.where(split_names == "train")[0]
    train_local = np.where(split_names[split_names != "test"] == "train")[0]
    val_local = np.where(split_names[split_names != "test"] == "val")[0]
    x_trainval = x[split_names != "test"]
    y_trainval = y[split_names != "test"]
    feature_indices = range(x.shape[1])
    candidates = []
    for depth in range(2, 8):
        for min_leaf in [1, 2, 3, 4, 5, 6]:
            tree = build_tree(x, y, train_idx, depth=0, max_depth=depth, min_leaf=min_leaf, feature_indices=feature_indices)
            pred_tv = predict_tree(tree, x_trainval)
            candidates.append(
                Candidate(
                    candidate_id=next_id + len(candidates),
                    kind="threshold_tree",
                    params={"scope": "train_only", "max_depth": depth, "min_leaf": min_leaf},
                    train_pred=pred_tv[train_local],
                    val_pred=pred_tv[val_local],
                    complexity=count_nodes(tree),
                    model=tree,
                )
            )
    return candidates


def selection_key(val_m: dict, candidate: Candidate) -> tuple:
    return (
        val_m["macro_f1"],
        val_m["balanced_accuracy"],
        -val_m["recall_range"],
        val_m["accuracy"],
        -candidate.complexity,
    )


def prediction_rows(rows: list[dict], pred: np.ndarray, scores: np.ndarray | None = None) -> list[dict]:
    out = []
    if scores is None:
        scores = np.zeros((len(rows), 4), dtype=np.int32)
        for i, p in enumerate(pred.tolist()):
            scores[i, p] = 1
    for row, p, score in zip(rows, pred.tolist(), scores.tolist()):
        out.append(
            {
                "case_id": row["case_id"],
                "split": row["split"],
                "class_label": row["class_label"],
                "class_id": row["class_id"],
                "record_id": row["record_id"],
                "chunk_id": row["chunk_id"],
                "chunk_file": row["chunk_file"],
                "final_pred_class": p,
                "final_pred_label": CLASSES[p],
                "correct": int(p == row["class_id"]),
                "final_mem_NSR": int(score[0]),
                "final_mem_CHF": int(score[1]),
                "final_mem_ARR": int(score[2]),
                "final_mem_AFF": int(score[3]),
            }
        )
    return out


def run_search() -> None:
    chunks = load_chunks()
    rows, feature_names, x, y, split_names = build_table(chunks)
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]
    test_rows = [row for row in rows if row["split"] == "test"]
    y_train = np.array([row["class_id"] for row in train_rows], dtype=np.int64)
    y_val = np.array([row["class_id"] for row in val_rows], dtype=np.int64)
    y_test = np.array([row["class_id"] for row in test_rows], dtype=np.int64)

    candidates: list[Candidate] = []
    maj = majority_pred(x, feature_names)
    avg = avg_mem_pred(x, feature_names)
    candidates.append(Candidate(0, "majority_vote", {}, split_pred(maj, split_names, "train"), split_pred(maj, split_names, "val"), 1))
    candidates.append(Candidate(1, "average_class_mem", {}, split_pred(avg, split_names, "train"), split_pred(avg, split_names, "val"), 1))
    candidates.extend(rule_candidates(rows, split_names, len(candidates)))
    candidates.extend(tree_candidates(x, y, split_names, len(candidates)))

    search_rows = []
    selected = None
    selected_key = None
    for cand in candidates:
        train_m = metrics(y_train, cand.train_pred)
        val_m = metrics(y_val, cand.val_pred)
        row = {
            "candidate_id": cand.candidate_id,
            "kind": cand.kind,
            "params": json.dumps(cand.params, sort_keys=True),
            "complexity": cand.complexity,
            "train_accuracy": train_m["accuracy"],
            "train_macro_f1": train_m["macro_f1"],
            "train_balanced_accuracy": train_m["balanced_accuracy"],
            "train_recall_range": train_m["recall_range"],
            "val_accuracy": val_m["accuracy"],
            "val_macro_f1": val_m["macro_f1"],
            "val_balanced_accuracy": val_m["balanced_accuracy"],
            "val_recall_range": val_m["recall_range"],
            "val_min_recall": val_m["min_recall"],
        }
        search_rows.append(row)
        key = selection_key(val_m, cand)
        if selected_key is None or key > selected_key:
            selected_key = key
            selected = (cand, train_m, val_m)

    write_csv(SEARCH_CSV, search_rows)
    if selected is None:
        raise RuntimeError("no selected candidate")

    cand, train_m, val_m = selected
    score_by_split = {}
    if cand.kind == "threshold_tree":
        test_pred = predict_tree(cand.model, x[split_names == "test"])
        model_payload = tree_to_dict(cand.model, feature_names)
    elif cand.kind == "guarded_rule":
        train_pred_guard, train_scores = selected_guarded_scores(train_rows, cand.params)
        val_pred_guard, val_scores = selected_guarded_scores(val_rows, cand.params)
        test_pred, test_scores = selected_guarded_scores(test_rows, cand.params)
        cand.train_pred = train_pred_guard
        cand.val_pred = val_pred_guard
        score_by_split = {"train": train_scores, "val": val_scores, "test": test_scores}
        model_payload = cand.params
    elif cand.kind == "majority_vote":
        test_pred = split_pred(maj, split_names, "test")
        model_payload = {}
    else:
        test_pred = split_pred(avg, split_names, "test")
        model_payload = {}

    test_m = metrics(y_test, test_pred)
    for split, pred, split_rows, split_y, split_m in [
        ("train", cand.train_pred, train_rows, y_train, train_m),
        ("val", cand.val_pred, val_rows, y_val, val_m),
        ("test", test_pred, test_rows, y_test, test_m),
    ]:
        (RESULTS / f"python_{split}_metrics.json").write_text(json.dumps(split_m, indent=2), encoding="utf-8")
        write_csv(RESULTS / f"python_{split}_predictions.csv", prediction_rows(split_rows, pred, score_by_split.get(split)))

    selected_payload = {
        "note": "Record-wise holdout search. Test is evaluated only after validation-selected candidate is fixed.",
        "classes": CLASSES,
        "candidate_id": cand.candidate_id,
        "kind": cand.kind,
        "params": cand.params,
        "complexity": cand.complexity,
        "selection_rule": "validation macro-F1, balanced accuracy, recall balance, accuracy, then simplicity",
        "model": model_payload,
        "metrics": {"train": train_m, "val": val_m, "test": test_m},
    }
    SELECTED_JSON.write_text(json.dumps(selected_payload, indent=2), encoding="utf-8")
    print(
        f"[selected] id={cand.candidate_id} kind={cand.kind} "
        f"train={train_m['correct']}/{train_m['total']} "
        f"val={val_m['correct']}/{val_m['total']} "
        f"test={test_m['correct']}/{test_m['total']} "
        f"test_acc={test_m['accuracy']:.4f}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", action="store_true")
    args = parser.parse_args()
    if args.search:
        run_search()
    else:
        run_search()


if __name__ == "__main__":
    main()
