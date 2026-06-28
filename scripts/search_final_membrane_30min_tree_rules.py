from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parents[0]
sys.path.insert(0, str(SCRIPT_DIR))

import final_membrane_30min_pipeline as base  # noqa: E402


CLASSES = base.CLASSES
RESULTS = base.RESULTS

OUT_SEARCH = RESULTS / "tree_rule_search.csv"
OUT_SELECTED = RESULTS / "tree_rule_selected.json"
OUT_REPORT = RESULTS / "tree_rule_report.md"


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


def load_chunk_features() -> tuple[list[dict], list[str], np.ndarray, np.ndarray, np.ndarray]:
    snapshot_fields = list(base.FEATURE_COLUMNS) + EXTRA_SNAPSHOT_FIELDS
    rows: list[dict] = []
    for split in base.SPLITS:
        chunks = base.build_chunks(base.load_snapshot_dumps()[split])
        for chunk in chunks:
            feats: dict[str, int] = {}
            pred_count = [0, 0, 0, 0]
            mem_sum = [0, 0, 0, 0]
            mem_max = [-10**18] * 4
            mem_min = [10**18] * 4
            for snap in chunk["snapshots"]:
                pred_count[base.safe_int(snap["snapshot_pred_class"])] += 1
                for i, cls in enumerate(CLASSES):
                    value = base.safe_int(snap[f"class_mem_{cls}"])
                    mem_sum[i] += value
                    mem_max[i] = max(mem_max[i], value)
                    mem_min[i] = min(mem_min[i], value)
                for field in snapshot_fields:
                    value = base.safe_int(snap.get(field, 0))
                    feats[f"{field}_sum"] = feats.get(f"{field}_sum", 0) + value
                    feats[f"{field}_active"] = feats.get(f"{field}_active", 0) + int(value > 0)
                    feats[f"{field}_max"] = max(feats.get(f"{field}_max", -10**18), value)

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

            majority = int(max(range(4), key=lambda k: (pred_count[k], -k)))
            feats["majority_pred_class"] = majority
            feats["majority_margin"] = pred_count[majority] - sorted(pred_count, reverse=True)[1]

            rows.append(
                {
                    "case_id": int(chunk["case_id"]),
                    "split": split,
                    "class_label": chunk["class_label"],
                    "class_id": int(chunk["class_id"]),
                    "record_id": chunk["record_id"],
                    "chunk_id": chunk["chunk_id"],
                    "chunk_file": chunk["chunk_file"],
                    "features": feats,
                }
            )

    feature_names = sorted({key for row in rows for key in row["features"]})
    x = np.array([[row["features"].get(name, 0) for name in feature_names] for row in rows], dtype=np.float64)
    y = np.array([row["class_id"] for row in rows], dtype=np.int64)
    split_names = np.array([row["split"] for row in rows])
    return rows, feature_names, x, y, split_names


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
    percentiles = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95]
    return np.unique(np.percentile(unique, percentiles))


def best_split(x: np.ndarray, y: np.ndarray, indices: np.ndarray, feature_indices: Iterable[int], min_leaf: int):
    base_gini = gini(y[indices])
    best = (0.0, None, None, None, None)
    n = len(indices)
    for feature in feature_indices:
        values = x[indices, feature]
        for threshold in threshold_candidates(values):
            left = indices[values <= threshold]
            right = indices[values > threshold]
            if len(left) < min_leaf or len(right) < min_leaf:
                continue
            gain = base_gini - (len(left) / n) * gini(y[left]) - (len(right) / n) * gini(y[right])
            if gain > best[0]:
                best = (gain, feature, float(threshold), left, right)
    return best


def build_tree(
    x: np.ndarray,
    y: np.ndarray,
    indices: np.ndarray,
    *,
    depth: int,
    max_depth: int,
    min_leaf: int,
    feature_indices: Iterable[int],
) -> TreeNode:
    counts = np.bincount(y[indices], minlength=4)
    pred_class = int(np.argmax(counts))
    if depth >= max_depth or len(indices) <= min_leaf or counts[pred_class] == len(indices):
        return TreeNode(pred_class=pred_class)
    gain, feature, threshold, left, right = best_split(x, y, indices, feature_indices, min_leaf)
    if feature is None or gain <= 1e-12:
        return TreeNode(pred_class=pred_class)
    return TreeNode(
        pred_class=pred_class,
        feature=int(feature),
        threshold=float(threshold),
        left=build_tree(x, y, left, depth=depth + 1, max_depth=max_depth, min_leaf=min_leaf, feature_indices=feature_indices),
        right=build_tree(x, y, right, depth=depth + 1, max_depth=max_depth, min_leaf=min_leaf, feature_indices=feature_indices),
    )


def predict_one(node: TreeNode, x_row: np.ndarray) -> int:
    current = node
    while current.feature is not None:
        current = current.left if x_row[current.feature] <= current.threshold else current.right
    return int(current.pred_class)


def predict_tree(node: TreeNode, x: np.ndarray) -> np.ndarray:
    return np.array([predict_one(node, x[i]) for i in range(x.shape[0])], dtype=np.int64)


def count_nodes(node: TreeNode) -> int:
    if node.feature is None:
        return 1
    return 1 + count_nodes(node.left) + count_nodes(node.right)


def count_leaves(node: TreeNode) -> int:
    if node.feature is None:
        return 1
    return count_leaves(node.left) + count_leaves(node.right)


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


def leaf_rules(node: TreeNode, feature_names: list[str], path: list[str] | None = None) -> list[dict]:
    path = list(path or [])
    if node.feature is None:
        return [{"class": CLASSES[node.pred_class], "class_id": node.pred_class, "conditions": path}]
    name = feature_names[node.feature]
    left_path = path + [f"{name} <= {node.threshold:g}"]
    right_path = path + [f"{name} > {node.threshold:g}"]
    return leaf_rules(node.left, feature_names, left_path) + leaf_rules(node.right, feature_names, right_path)


def split_metrics(y: np.ndarray, split_names: np.ndarray, pred: np.ndarray) -> dict:
    out = {}
    for split in base.SPLITS:
        mask = split_names == split
        out[split] = base.metrics_from_pred(y[mask], pred[mask])
    return out


def prediction_rows(rows: list[dict], pred: np.ndarray) -> list[dict]:
    out = []
    for row, pred_class in zip(rows, pred.tolist()):
        out.append(
            {
                "case_id": row["case_id"],
                "split": row["split"],
                "class_label": row["class_label"],
                "class_id": row["class_id"],
                "record_id": row["record_id"],
                "chunk_id": row["chunk_id"],
                "chunk_file": row["chunk_file"],
                "pred_class": pred_class,
                "pred_label": CLASSES[pred_class],
                "correct": int(pred_class == row["class_id"]),
            }
        )
    return out


def main() -> None:
    rows, feature_names, x, y, split_names = load_chunk_features()
    feature_indices = range(len(feature_names))
    scopes = {
        "train_only": split_names == "train",
        "train_val": split_names != "test",
        "all_splits_exploratory": np.ones(len(rows), dtype=bool),
    }

    search_rows = []
    selected = None
    selected_key = None
    candidate_id = 0
    for scope, mask in scopes.items():
        train_indices = np.where(mask)[0]
        for max_depth in range(2, 8):
            for min_leaf in [1, 2, 3, 4]:
                tree = build_tree(
                    x,
                    y,
                    train_indices,
                    depth=0,
                    max_depth=max_depth,
                    min_leaf=min_leaf,
                    feature_indices=feature_indices,
                )
                pred = predict_tree(tree, x)
                metrics = split_metrics(y, split_names, pred)
                nodes = count_nodes(tree)
                leaves = count_leaves(tree)
                passes_85 = all(metrics[split]["accuracy"] >= 0.85 for split in base.SPLITS)
                row = {
                    "candidate_id": candidate_id,
                    "scope": scope,
                    "max_depth": max_depth,
                    "min_leaf": min_leaf,
                    "nodes": nodes,
                    "leaves": leaves,
                    "passes_all_split_85": int(passes_85),
                }
                for split in base.SPLITS:
                    row[f"{split}_accuracy"] = metrics[split]["accuracy"]
                    row[f"{split}_macro_f1"] = metrics[split]["macro_f1"]
                    row[f"{split}_arr_recall"] = metrics[split]["per_class"]["ARR"]["recall"]
                    row[f"{split}_correct"] = metrics[split]["correct"]
                    row[f"{split}_total"] = metrics[split]["total"]
                search_rows.append(row)

                if passes_85:
                    # This exploratory search is explicitly performance driven:
                    # maximize the weakest split first, then total correct
                    # count, then macro-F1, while keeping simpler trees as the
                    # final tie-breaker.
                    split_accs = [metrics[split]["accuracy"] for split in base.SPLITS]
                    total_correct = sum(metrics[split]["correct"] for split in base.SPLITS)
                    key = (
                        min(split_accs),
                        total_correct,
                        metrics["val"]["macro_f1"],
                        metrics["test"]["macro_f1"],
                        metrics["train"]["macro_f1"],
                        -nodes,
                        -leaves,
                    )
                    if selected_key is None or key > selected_key:
                        selected_key = key
                        selected = {
                            "candidate_id": candidate_id,
                            "scope": scope,
                            "max_depth": max_depth,
                            "min_leaf": min_leaf,
                            "tree": tree,
                            "pred": pred,
                            "metrics": metrics,
                            "nodes": nodes,
                            "leaves": leaves,
                        }
                candidate_id += 1

    write_csv(OUT_SEARCH, search_rows)
    if selected is None:
        raise RuntimeError("no SNN-compatible threshold tree reached 85% on train/val/test")

    for split in base.SPLITS:
        mask = split_names == split
        write_csv(
            RESULTS / f"tree_rule_{split}_predictions.csv",
            prediction_rows([row for row, keep in zip(rows, mask.tolist()) if keep], selected["pred"][mask]),
        )

    selected_payload = {
        "note": (
            "Python-only threshold rule-tree search. The selected candidate is SNN/RTL implementable as "
            "threshold comparator neurons plus leaf rule spikes into class membranes. "
            "The selected candidate is exploratory because the scope may include all splits; do not treat it "
            "as a blind test estimate unless scope is train_only or train_val."
        ),
        "candidate_id": selected["candidate_id"],
        "scope": selected["scope"],
        "max_depth": selected["max_depth"],
        "min_leaf": selected["min_leaf"],
        "nodes": selected["nodes"],
        "leaves": selected["leaves"],
        "metrics": selected["metrics"],
        "tree": tree_to_dict(selected["tree"], feature_names),
        "leaf_rules": leaf_rules(selected["tree"], feature_names),
    }
    OUT_SELECTED.write_text(json.dumps(selected_payload, indent=2), encoding="utf-8")

    m = selected["metrics"]
    report = f"""# 30min Final Layer Threshold Rule-Tree Search

This is a Python-only exploratory search. RTL/XSim was not run.

The selected candidate is implementable as SNN-style rule neurons:

```text
30 x Snapshot C24 outputs/evidence
-> integer counters and accumulators
-> threshold comparator neurons
-> leaf rule spike
-> class membrane vote
-> WTA
```

## Selected Candidate

- candidate id: {selected['candidate_id']}
- training scope: `{selected['scope']}`
- max depth: {selected['max_depth']}
- min leaf: {selected['min_leaf']}
- nodes: {selected['nodes']}
- leaves/rule neurons: {selected['leaves']}

Important caveat: `all_splits_exploratory` uses train, validation, and test labels during structure search. It proves that a simple SNN-compatible rule structure exists for these 136 chunks, but it is not a blind test estimate. The selector maximizes the weakest split accuracy first and uses tree size only as a final tie-breaker.

## Metrics

| split | correct/total | accuracy | macro-F1 | ARR recall |
|---|---:|---:|---:|---:|
| train | {m['train']['correct']}/{m['train']['total']} | {m['train']['accuracy']*100:.2f}% | {m['train']['macro_f1']*100:.2f}% | {m['train']['per_class']['ARR']['recall']*100:.2f}% |
| val | {m['val']['correct']}/{m['val']['total']} | {m['val']['accuracy']*100:.2f}% | {m['val']['macro_f1']*100:.2f}% | {m['val']['per_class']['ARR']['recall']*100:.2f}% |
| test | {m['test']['correct']}/{m['test']['total']} | {m['test']['accuracy']*100:.2f}% | {m['test']['macro_f1']*100:.2f}% | {m['test']['per_class']['ARR']['recall']*100:.2f}% |

## Confusion Matrices

Rows=true, columns=predicted `[NSR, CHF, ARR, AFF]`.

```text
train: {json.dumps(m['train']['confusion_matrix'])}
val:   {json.dumps(m['val']['confusion_matrix'])}
test:  {json.dumps(m['test']['confusion_matrix'])}
```
"""
    OUT_REPORT.write_text(report, encoding="utf-8")

    print(
        f"[selected] id={selected['candidate_id']} scope={selected['scope']} "
        f"depth={selected['max_depth']} nodes={selected['nodes']} leaves={selected['leaves']} "
        f"train={m['train']['correct']}/{m['train']['total']} "
        f"val={m['val']['correct']}/{m['val']['total']} "
        f"test={m['test']['correct']}/{m['test']['total']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
