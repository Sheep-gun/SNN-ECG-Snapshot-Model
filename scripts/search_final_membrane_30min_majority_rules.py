from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parents[0]
sys.path.insert(0, str(SCRIPT_DIR))

import final_membrane_30min_pipeline as base  # noqa: E402


CLASSES = base.CLASSES
RESULTS = base.RESULTS
OUT_SEARCH = RESULTS / "rule_search_majority_guard.csv"
OUT_SELECTED = RESULTS / "rule_search_majority_guard_selected.json"
OUT_REPORT = RESULTS / "rule_search_majority_guard_report.md"


SUMMARY_FIELDS = [
    "abnormal_evidence_count",
    "rhythm_irregular_evidence_count",
    "morphology_evidence_count",
    "rdm_ge50_count",
    "rdm_ge100_count",
    "qrs_maf_count",
    "rbbb_delay_like_count",
    "rbbb_delay_applied_count",
    "eerg_ecp_count",
    "eerg_applied_count",
    "ectopic_pair_count",
    "pnn_mismatch_count",
]


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


def summarize_split(split: str) -> list[dict]:
    dumps = base.load_snapshot_dumps()
    chunks = base.build_chunks(dumps[split])
    rows: list[dict] = []
    for chunk in chunks:
        pred_count = [0, 0, 0, 0]
        mem_sum = [0, 0, 0, 0]
        sums = {field: 0 for field in SUMMARY_FIELDS}
        active = {field: 0 for field in SUMMARY_FIELDS}
        for snap in chunk["snapshots"]:
            pred_count[base.safe_int(snap["snapshot_pred_class"])] += 1
            for i, cls in enumerate(CLASSES):
                mem_sum[i] += base.safe_int(snap[f"class_mem_{cls}"])
            for field in SUMMARY_FIELDS:
                value = base.safe_int(snap.get(field, 0))
                sums[field] += value
                active[field] += int(value > 0)

        majority = int(max(range(4), key=lambda i: (pred_count[i], -i)))
        second_count = sorted(pred_count, reverse=True)[1]
        rows.append(
            {
                "case_id": int(chunk["case_id"]),
                "split": chunk["split"],
                "class_label": chunk["class_label"],
                "class_id": int(chunk["class_id"]),
                "record_id": chunk["record_id"],
                "chunk_id": chunk["chunk_id"],
                "chunk_file": chunk["chunk_file"],
                "majority_pred": majority,
                "majority_label": CLASSES[majority],
                "majority_margin": pred_count[majority] - second_count,
                "pred_count": pred_count,
                "mem_sum": mem_sum,
                "sum": sums,
                "active": active,
            }
        )
    return rows


def metrics(rows: list[dict], pred: np.ndarray) -> dict:
    y = np.array([row["class_id"] for row in rows], dtype=np.int64)
    return base.metrics_from_pred(y, pred.astype(np.int64))


def majority_pred(rows: list[dict]) -> np.ndarray:
    return np.array([row["majority_pred"] for row in rows], dtype=np.int64)


def mask_arr(rows: list[dict], param: tuple[int, int, int] | None) -> np.ndarray:
    if param is None:
        return np.zeros(len(rows), dtype=bool)
    arr_th, abnormal_sum_th, qrs_maf_active_th = param
    return np.array(
        [
            row["pred_count"][2] >= arr_th
            and row["sum"]["abnormal_evidence_count"] >= abnormal_sum_th
            and row["active"]["qrs_maf_count"] >= qrs_maf_active_th
            for row in rows
        ],
        dtype=bool,
    )


def mask_aff_quiet(rows: list[dict], param: tuple[int, int, int, int] | None) -> np.ndarray:
    if param is None:
        return np.zeros(len(rows), dtype=bool)
    chf_count_th, aff_count_max, abnormal_sum_max, qrs_maf_sum_max = param
    return np.array(
        [
            row["majority_pred"] == 1
            and row["pred_count"][1] >= chf_count_th
            and row["pred_count"][3] <= aff_count_max
            and row["sum"]["abnormal_evidence_count"] <= abnormal_sum_max
            and row["sum"]["qrs_maf_count"] <= qrs_maf_sum_max
            for row in rows
        ],
        dtype=bool,
    )


def mask_aff_persistent(rows: list[dict], param: tuple[int, int, int] | None) -> np.ndarray:
    if param is None:
        return np.zeros(len(rows), dtype=bool)
    chf_count_min, aff_count_min, abnormal_sum_min = param
    return np.array(
        [
            row["majority_pred"] == 1
            and row["pred_count"][1] >= chf_count_min
            and row["pred_count"][3] >= aff_count_min
            and row["sum"]["abnormal_evidence_count"] >= abnormal_sum_min
            for row in rows
        ],
        dtype=bool,
    )


def nsr_overlay_blocked(row: dict) -> bool:
    return (
        row["pred_count"][2] >= 15
        or row["sum"]["rbbb_delay_like_count"] > 0
        or row["sum"]["rbbb_delay_applied_count"] > 0
        or row["sum"]["eerg_applied_count"] > 0
        or row["sum"]["eerg_ecp_count"] > 0
        or row["sum"]["rdm_ge50_count"] > 0
        or row["sum"]["qrs_maf_count"] > 0
        or row["sum"]["ectopic_pair_count"] > 0
        or row["sum"]["pnn_mismatch_count"] > 0
    )


def mask_nsr_gated(rows: list[dict], param: tuple[int] | None) -> np.ndarray:
    if param is None:
        return np.zeros(len(rows), dtype=bool)
    (nsr_count_th,) = param
    return np.array(
        [
            row["pred_count"][0] >= nsr_count_th
            and not nsr_overlay_blocked(row)
            for row in rows
        ],
        dtype=bool,
    )


def dedupe_rule_params(rows_by_split: dict[str, list[dict]], params: list, fn):
    seen = {}
    ordered = []
    for param in params:
        key = tuple(fn(rows_by_split[split], param).tobytes() for split in ["train", "val"])
        if key not in seen:
            seen[key] = param
            ordered.append(param)
    return ordered


def apply_rule_set(
    rows: list[dict],
    arr_param,
    aff_quiet_param,
    aff_persistent_param,
    nsr_param,
) -> np.ndarray:
    pred = majority_pred(rows)

    # ARR protection runs first. This also guarantees a later NSR overlay cannot
    # flip an ARR-majority/protected chunk.
    arr_mask = mask_arr(rows, arr_param)
    pred[arr_mask] = 2

    # NSR overlay is gated and deliberately weak. It is never used alone by the
    # selector; abnormal/RBBB/EERG/ECP/RDM/QRS-MAF evidence blocks it.
    nsr_mask = mask_nsr_gated(rows, nsr_param) & (~arr_mask)
    pred[nsr_mask] = 0

    high_mask = mask_aff_persistent(rows, aff_persistent_param) & (~arr_mask)
    pred[high_mask] = 3

    quiet_mask = mask_aff_quiet(rows, aff_quiet_param) & (~arr_mask)
    pred[quiet_mask] = 3
    return pred


def prediction_rows(rows: list[dict], pred: np.ndarray) -> list[dict]:
    out = []
    for row, p in zip(rows, pred.tolist()):
        out.append(
            {
                "case_id": row["case_id"],
                "split": row["split"],
                "class_label": row["class_label"],
                "class_id": row["class_id"],
                "record_id": row["record_id"],
                "chunk_id": row["chunk_id"],
                "chunk_file": row["chunk_file"],
                "majority_pred_class": row["majority_pred"],
                "majority_pred_label": row["majority_label"],
                "final_pred_class": p,
                "final_pred_label": CLASSES[p],
                "correct": int(p == row["class_id"]),
                "pred_count_NSR": row["pred_count"][0],
                "pred_count_CHF": row["pred_count"][1],
                "pred_count_ARR": row["pred_count"][2],
                "pred_count_AFF": row["pred_count"][3],
                "abnormal_evidence_sum": row["sum"]["abnormal_evidence_count"],
                "qrs_maf_sum": row["sum"]["qrs_maf_count"],
                "eerg_ecp_sum": row["sum"]["eerg_ecp_count"],
                "rdm_ge50_sum": row["sum"]["rdm_ge50_count"],
            }
        )
    return out


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows_by_split = {split: summarize_split(split) for split in base.SPLITS}
    baseline_pred = {split: majority_pred(rows_by_split[split]) for split in base.SPLITS}
    baseline = {split: metrics(rows_by_split[split], baseline_pred[split]) for split in base.SPLITS}

    arr_params = [None] + [
        (arr_th, abnormal_sum_th, qrs_maf_active_th)
        for arr_th in [9, 10, 11, 12, 13, 14, 15, 16, 18, 20]
        for abnormal_sum_th in [0, 250, 500, 1000, 1500, 2000, 3000, 4000, 5000]
        for qrs_maf_active_th in [0, 5, 10, 15, 20, 25, 30]
    ]
    aff_quiet_params = [None] + [
        (chf_count_th, aff_count_max, abnormal_sum_max, qrs_maf_sum_max)
        for chf_count_th in [18, 20, 23, 25, 27, 28, 29, 30]
        for aff_count_max in [0, 1, 2, 4, 6, 9, 12]
        for abnormal_sum_max in [0, 5, 10, 20, 30, 50, 75, 100, 150, 250]
        for qrs_maf_sum_max in [0, 2, 5, 10, 25]
    ]
    aff_persistent_params = [None] + [
        (chf_count_min, aff_count_min, abnormal_sum_min)
        for chf_count_min in [10, 12, 14, 16, 18, 20, 22, 25]
        for aff_count_min in [5, 8, 10, 11, 12, 14, 16]
        for abnormal_sum_min in [500, 1000, 1500, 2000, 2500, 3000]
    ]
    nsr_params = [None] + [(13,), (15,), (18,), (20,), (23,), (25,)]

    arr_params = dedupe_rule_params(rows_by_split, arr_params, mask_arr)
    aff_quiet_params = dedupe_rule_params(rows_by_split, aff_quiet_params, mask_aff_quiet)
    aff_persistent_params = dedupe_rule_params(rows_by_split, aff_persistent_params, mask_aff_persistent)
    nsr_params = dedupe_rule_params(rows_by_split, nsr_params, mask_nsr_gated)

    search_rows = []
    selected = None
    selected_key = None
    candidate_id = 0

    val_base = baseline["val"]
    train_base = baseline["train"]

    for arr_param in arr_params:
        for aff_quiet_param in aff_quiet_params:
            for aff_persistent_param in aff_persistent_params:
                for nsr_param in nsr_params:
                    if nsr_param is not None and arr_param is None and aff_quiet_param is None and aff_persistent_param is None:
                        continue
                    train_pred = apply_rule_set(rows_by_split["train"], arr_param, aff_quiet_param, aff_persistent_param, nsr_param)
                    val_pred = apply_rule_set(rows_by_split["val"], arr_param, aff_quiet_param, aff_persistent_param, nsr_param)
                    train_m = metrics(rows_by_split["train"], train_pred)
                    val_m = metrics(rows_by_split["val"], val_pred)
                    passes_core = (
                        val_m["macro_f1"] > val_base["macro_f1"]
                        and val_m["per_class"]["ARR"]["recall"] > val_base["per_class"]["ARR"]["recall"]
                    )
                    passes_balanced_guard = (
                        passes_core
                        and train_m["macro_f1"] >= train_base["macro_f1"]
                        and val_m["min_recall"] >= val_base["min_recall"]
                    )
                    row = {
                        "candidate_id": candidate_id,
                        "arr_param": json.dumps(arr_param),
                        "aff_quiet_param": json.dumps(aff_quiet_param),
                        "aff_persistent_param": json.dumps(aff_persistent_param),
                        "nsr_param": json.dumps(nsr_param),
                        "passes_core": int(passes_core),
                        "passes_balanced_guard": int(passes_balanced_guard),
                        "train_accuracy": train_m["accuracy"],
                        "train_macro_f1": train_m["macro_f1"],
                        "train_arr_recall": train_m["per_class"]["ARR"]["recall"],
                        "train_min_recall": train_m["min_recall"],
                        "val_accuracy": val_m["accuracy"],
                        "val_macro_f1": val_m["macro_f1"],
                        "val_arr_recall": val_m["per_class"]["ARR"]["recall"],
                        "val_min_recall": val_m["min_recall"],
                        "val_recall_range": val_m["recall_range"],
                    }
                    search_rows.append(row)
                    if passes_balanced_guard:
                        key = (
                            val_m["macro_f1"],
                            val_m["accuracy"],
                            val_m["per_class"]["ARR"]["recall"],
                            val_m["min_recall"],
                            train_m["macro_f1"],
                            train_m["accuracy"],
                            -val_m["recall_range"],
                        )
                        if selected_key is None or key > selected_key:
                            selected_key = key
                            selected = {
                                "candidate_id": candidate_id,
                                "arr_param": arr_param,
                                "aff_quiet_param": aff_quiet_param,
                                "aff_persistent_param": aff_persistent_param,
                                "nsr_param": nsr_param,
                                "train_metrics": train_m,
                                "val_metrics": val_m,
                                "train_pred": train_pred,
                                "val_pred": val_pred,
                            }
                    candidate_id += 1

    write_csv(OUT_SEARCH, search_rows)
    if selected is None:
        raise RuntimeError("no candidate passed the majority macro-F1 + ARR recall guards")

    test_pred = apply_rule_set(
        rows_by_split["test"],
        selected["arr_param"],
        selected["aff_quiet_param"],
        selected["aff_persistent_param"],
        selected["nsr_param"],
    )
    test_m = metrics(rows_by_split["test"], test_pred)
    selected["test_metrics"] = test_m

    selected_json = {
        "selection_note": (
            "Selected on train/validation only. Test is evaluated once after selection. "
            "Majority vote is the baseline; a candidate must improve validation macro-F1 "
            "and validation ARR recall simultaneously. NSR overlay is gated by abnormal "
            "evidence and is never allowed as a standalone rule."
        ),
        "baseline_majority": baseline,
        "candidate_id": selected["candidate_id"],
        "arr_param": selected["arr_param"],
        "aff_quiet_param": selected["aff_quiet_param"],
        "aff_persistent_param": selected["aff_persistent_param"],
        "nsr_param": selected["nsr_param"],
        "train_metrics": selected["train_metrics"],
        "val_metrics": selected["val_metrics"],
        "test_metrics": selected["test_metrics"],
    }
    OUT_SELECTED.write_text(json.dumps(selected_json, indent=2), encoding="utf-8")

    for split, pred in [
        ("train", selected["train_pred"]),
        ("val", selected["val_pred"]),
        ("test", test_pred),
    ]:
        write_csv(RESULTS / f"rule_search_majority_guard_{split}_predictions.csv", prediction_rows(rows_by_split[split], pred))

    report = f"""# Majority-Guard Final Membrane Rule Search

This is a Python-only search. RTL/XSim was intentionally not run.

## Baseline

Majority vote is the baseline.

| split | accuracy | macro-F1 | ARR recall |
|---|---:|---:|---:|
| train | {baseline['train']['accuracy']*100:.2f}% | {baseline['train']['macro_f1']*100:.2f}% | {baseline['train']['per_class']['ARR']['recall']*100:.2f}% |
| val | {baseline['val']['accuracy']*100:.2f}% | {baseline['val']['macro_f1']*100:.2f}% | {baseline['val']['per_class']['ARR']['recall']*100:.2f}% |
| test | {baseline['test']['accuracy']*100:.2f}% | {baseline['test']['macro_f1']*100:.2f}% | {baseline['test']['per_class']['ARR']['recall']*100:.2f}% |

## Selected Candidate

- candidate id: {selected['candidate_id']}
- ARR protection param: `{selected['arr_param']}`
- AFF quiet rescue param: `{selected['aff_quiet_param']}`
- AFF persistent rescue param: `{selected['aff_persistent_param']}`
- NSR overlay param: `{selected['nsr_param']}`

NSR overlay is not standalone. It is blocked by ARR protection and by any RBBB/EERG/ECP/RDM/QRS-MAF/ectopic/pNN abnormal evidence.

## Selected Metrics

| split | accuracy | macro-F1 | ARR recall |
|---|---:|---:|---:|
| train | {selected['train_metrics']['accuracy']*100:.2f}% | {selected['train_metrics']['macro_f1']*100:.2f}% | {selected['train_metrics']['per_class']['ARR']['recall']*100:.2f}% |
| val | {selected['val_metrics']['accuracy']*100:.2f}% | {selected['val_metrics']['macro_f1']*100:.2f}% | {selected['val_metrics']['per_class']['ARR']['recall']*100:.2f}% |
| test | {test_m['accuracy']*100:.2f}% | {test_m['macro_f1']*100:.2f}% | {test_m['per_class']['ARR']['recall']*100:.2f}% |

## Test Confusion Matrix

Rows=true, columns=predicted `[NSR, CHF, ARR, AFF]`.

```text
{json.dumps(test_m['confusion_matrix'])}
```
"""
    OUT_REPORT.write_text(report, encoding="utf-8")

    print(
        f"[selected] id={selected['candidate_id']} "
        f"val_acc={selected['val_metrics']['accuracy']:.4f} "
        f"val_macro_f1={selected['val_metrics']['macro_f1']:.4f} "
        f"val_arr_recall={selected['val_metrics']['per_class']['ARR']['recall']:.4f} "
        f"test_acc={test_m['accuracy']:.4f} "
        f"test_macro_f1={test_m['macro_f1']:.4f} "
        f"test_arr_recall={test_m['per_class']['ARR']['recall']:.4f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
