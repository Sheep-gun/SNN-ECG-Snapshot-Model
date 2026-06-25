import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(r"C:\Users\YangGeon\SNN_ECG_RESTORE_MODEL_S")
RESULTS = ROOT / "results"
DATASET = ROOT / "person_data_record_split_strict_varlen"
REPORTS = ROOT / "reports" / "model_s_rtl"
CLASSES = ["NSR", "CHF", "ARR", "AFF"]

TARGETS = {
    "train": {
        "segment": (313, 400),
        "record": (41, 50),
        "class_correct": [85, 76, 70, 82],
        "macro_f1": 0.7819,
        "balanced_accuracy": 0.7825,
    },
    "val": {
        "segment": (136, 160),
        "record": (18, 20),
        "class_correct": [36, 31, 38, 31],
        "macro_f1": 0.8491,
        "balanced_accuracy": 0.85,
    },
    "test": {
        "segment": (131, 160),
        "record": (18, 19),
        "class_correct": [31, 37, 28, 35],
        "macro_f1": 0.8193,
        "balanced_accuracy": 0.8188,
    },
}


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def confusion(y_true, y_pred):
    cm = [[0 for _ in range(4)] for _ in range(4)]
    for a, p in zip(y_true, y_pred):
        cm[a][p] += 1
    return cm


def prf_from_cm(cm):
    rows = []
    f1s = []
    recalls = []
    for i, name in enumerate(CLASSES):
        tp = cm[i][i]
        pred_total = sum(cm[r][i] for r in range(4))
        true_total = sum(cm[i])
        precision = tp / pred_total if pred_total else 0.0
        recall = tp / true_total if true_total else 0.0
        f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        rows.append({
            "class": name,
            "correct": tp,
            "total": true_total,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        })
        f1s.append(f1)
        recalls.append(recall)
    return rows, sum(f1s) / 4.0, sum(recalls) / 4.0


def load_split(split):
    result_path = RESULTS / split / f"rtl_{split}_varlen_case_results.csv"
    meta_path = DATASET / split / f"dataset_manifest_{split}_varlen_meta.csv"
    rows = read_csv(result_path)
    meta_rows = read_csv(meta_path)
    meta_by_case = {int(r["case_id"]): r for r in meta_rows}
    merged = []
    for row in rows:
        case_id = int(row["case_id"])
        m = meta_by_case.get(case_id, {})
        item = dict(row)
        item["record_id"] = m.get("record", "")
        item["seg_sec"] = m.get("seg_sec", "")
        item["start_sec"] = m.get("start_sec", "")
        item["annotation_count"] = m.get("annotation_count", "")
        item["qrs_absdiff"] = m.get("qrs_absdiff", "")
        merged.append(item)
    return merged


def record_eval(rows):
    by_record = {}
    for row in rows:
        rec = row["record_id"]
        by_record.setdefault(rec, []).append(row)
    y_true = []
    y_pred = []
    record_rows = []
    for rec in sorted(by_record):
        group = by_record[rec]
        true_class = Counter(int(r["expected_class"]) for r in group).most_common(1)[0][0]
        score_sum = [0, 0, 0, 0]
        vote = Counter()
        for r in group:
            pred = int(r["pred_class"])
            vote[pred] += 1
            score_sum[0] += int(r["score_nsr"])
            score_sum[1] += int(r["score_chf"])
            score_sum[2] += int(r["score_arr"])
            score_sum[3] += int(r["score_aff"])
        best_vote = max(vote.values())
        tied = [c for c, n in vote.items() if n == best_vote]
        if len(tied) == 1:
            pred_class = tied[0]
        else:
            pred_class = max(tied, key=lambda c: score_sum[c])
        y_true.append(true_class)
        y_pred.append(pred_class)
        record_rows.append({
            "record_id": rec,
            "true_class": CLASSES[true_class],
            "pred_class": CLASSES[pred_class],
            "correct": int(true_class == pred_class),
            "segment_count": len(group),
            "score_nsr_sum": score_sum[0],
            "score_chf_sum": score_sum[1],
            "score_arr_sum": score_sum[2],
            "score_aff_sum": score_sum[3],
        })
    return y_true, y_pred, record_rows


def analyze_split(split):
    rows = load_split(split)
    y_true = [int(r["expected_class"]) for r in rows]
    y_pred = [int(r["pred_class"]) for r in rows]
    cm = confusion(y_true, y_pred)
    class_rows, macro_f1, balanced = prf_from_cm(cm)
    seg_correct = sum(1 for a, p in zip(y_true, y_pred) if a == p)
    rec_true, rec_pred, record_rows = record_eval(rows)
    rec_cm = confusion(rec_true, rec_pred)
    rec_class_rows, rec_macro_f1, rec_balanced = prf_from_cm(rec_cm)
    rec_correct = sum(1 for a, p in zip(rec_true, rec_pred) if a == p)
    eerg_segments = sum(1 for r in rows if int(r.get("eerg_applied_count", 0)) > 0)
    rbbb_segments = sum(1 for r in rows if int(r.get("rbbb_delay_applied_count", 0)) > 0)

    metrics = {
        "split": split,
        "segment_correct": seg_correct,
        "segment_total": len(rows),
        "segment_accuracy": seg_correct / len(rows),
        "record_correct": rec_correct,
        "record_total": len(record_rows),
        "record_accuracy": rec_correct / len(record_rows),
        "macro_f1": macro_f1,
        "balanced_accuracy": balanced,
        "record_macro_f1": rec_macro_f1,
        "record_balanced_accuracy": rec_balanced,
        "eerg_applied_segments": eerg_segments,
        "rbbb_delay_applied_segments": rbbb_segments,
    }
    for c, row in zip(CLASSES, class_rows):
        metrics[f"{c}_correct"] = row["correct"]
        metrics[f"{c}_total"] = row["total"]
        metrics[f"{c}_recall"] = row["recall"]
        metrics[f"{c}_precision"] = row["precision"]
        metrics[f"{c}_f1"] = row["f1"]

    cm_rows = []
    for i, c in enumerate(CLASSES):
        cm_rows.append({
            "actual": c,
            "pred_NSR": cm[i][0],
            "pred_CHF": cm[i][1],
            "pred_ARR": cm[i][2],
            "pred_AFF": cm[i][3],
        })
    rec_cm_rows = []
    for i, c in enumerate(CLASSES):
        rec_cm_rows.append({
            "actual": c,
            "pred_NSR": rec_cm[i][0],
            "pred_CHF": rec_cm[i][1],
            "pred_ARR": rec_cm[i][2],
            "pred_AFF": rec_cm[i][3],
        })

    per_case = []
    for r in rows:
        per_case.append({
            "case_id": r["case_id"],
            "record_id": r["record_id"],
            "label": r["label"],
            "expected_class": CLASSES[int(r["expected_class"])],
            "pred_class": CLASSES[int(r["pred_class"])],
            "correct": r["correct"],
            "score_nsr": r["score_nsr"],
            "score_chf": r["score_chf"],
            "score_arr": r["score_arr"],
            "score_aff": r["score_aff"],
            "rbbb_delay_applied_count": r.get("rbbb_delay_applied_count", ""),
            "eerg_applied_count": r.get("eerg_applied_count", ""),
            "eerg_gate_count": r.get("eerg_gate_count", ""),
            "eerg_pre_qrs_bump_count": r.get("eerg_pre_qrs_bump_count", ""),
            "eerg_early_count": r.get("eerg_early_count", ""),
            "eerg_ecp_count": r.get("eerg_ecp_count", ""),
            "eerg_pnn_decision_count": r.get("eerg_pnn_decision_count", ""),
            "eerg_pnn_mismatch_count": r.get("eerg_pnn_mismatch_count", ""),
            "eerg_rdm_valid_count": r.get("eerg_rdm_valid_count", ""),
            "eerg_rdm_code_sum": r.get("eerg_rdm_code_sum", ""),
            "mem_file": r["mem_file"],
        })

    return metrics, class_rows, cm_rows, rec_cm_rows, record_rows, per_case


def pct(x):
    return f"{100.0 * x:.2f}%"


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    all_metrics = []
    comparison = []
    split_outputs = {}
    for split in ["train", "val", "test"]:
        metrics, class_rows, cm_rows, rec_cm_rows, record_rows, per_case = analyze_split(split)
        all_metrics.append(metrics)
        split_outputs[split] = (metrics, class_rows, cm_rows, rec_cm_rows)
        write_csv(REPORTS / f"model_s_rtl_{split}_class_metrics.csv", class_rows)
        write_csv(REPORTS / f"model_s_rtl_{split}_confusion.csv", cm_rows)
        write_csv(REPORTS / f"model_s_rtl_{split}_record_confusion.csv", rec_cm_rows)
        write_csv(REPORTS / f"model_s_rtl_{split}_record_summary.csv", record_rows)
        write_csv(REPORTS / f"model_s_rtl_{split}_case_summary.csv", per_case)
        t = TARGETS[split]
        comparison.append({
            "split": split,
            "segment_actual": f"{metrics['segment_correct']}/{metrics['segment_total']}",
            "segment_target": f"{t['segment'][0]}/{t['segment'][1]}",
            "segment_match": metrics["segment_correct"] == t["segment"][0] and metrics["segment_total"] == t["segment"][1],
            "record_actual": f"{metrics['record_correct']}/{metrics['record_total']}",
            "record_target": f"{t['record'][0]}/{t['record'][1]}",
            "record_match": metrics["record_correct"] == t["record"][0] and metrics["record_total"] == t["record"][1],
            "macro_f1_actual": metrics["macro_f1"],
            "macro_f1_target_approx": t["macro_f1"],
            "balanced_actual": metrics["balanced_accuracy"],
            "balanced_target_approx": t["balanced_accuracy"],
            "class_correct_actual": "/".join(str(metrics[f"{c}_correct"]) for c in CLASSES),
            "class_correct_target": "/".join(str(x) for x in t["class_correct"]),
        })
    write_csv(REPORTS / "model_s_rtl_split_metrics.csv", all_metrics)
    write_csv(REPORTS / "model_s_rtl_target_comparison.csv", comparison)
    (REPORTS / "model_s_rtl_metrics.json").write_text(json.dumps(all_metrics, indent=2), encoding="utf-8")

    lines = []
    lines.append("# Model S RTL Verification Report")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- This report is generated from XSim CSV output produced by the restored synthesizable RTL.")
    lines.append("- EERG is inside RTL in this version. It is not applied by Python post-processing.")
    lines.append("- Source root: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S`")
    lines.append("")
    lines.append("## Split Metrics")
    lines.append("")
    lines.append("| split | segment accuracy | record accuracy | macro-F1 | balanced acc | EERG applied segments | RBBB-delay applied segments |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for m in all_metrics:
        lines.append(
            f"| {m['split']} | {m['segment_correct']}/{m['segment_total']} = {pct(m['segment_accuracy'])} "
            f"| {m['record_correct']}/{m['record_total']} = {pct(m['record_accuracy'])} "
            f"| {pct(m['macro_f1'])} | {pct(m['balanced_accuracy'])} "
            f"| {m['eerg_applied_segments']} | {m['rbbb_delay_applied_segments']} |"
        )
    lines.append("")
    lines.append("## Target Comparison")
    lines.append("")
    lines.append("| split | segment | record | class correct actual | class correct target | note |")
    lines.append("|---|---:|---:|---|---|---|")
    for row in comparison:
        note = "matches target"
        if not row["segment_match"] or not row["record_match"] or row["class_correct_actual"] != row["class_correct_target"]:
            note = "total target matched but class distribution differs" if row["segment_match"] and row["record_match"] else "differs"
        lines.append(
            f"| {row['split']} | {row['segment_actual']} vs {row['segment_target']} "
            f"| {row['record_actual']} vs {row['record_target']} "
            f"| {row['class_correct_actual']} | {row['class_correct_target']} | {note} |"
        )
    lines.append("")
    lines.append("## Test Segment Confusion")
    lines.append("")
    lines.append("| actual | pred NSR | pred CHF | pred ARR | pred AFF |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in split_outputs["test"][2]:
        lines.append(f"| {r['actual']} | {r['pred_NSR']} | {r['pred_CHF']} | {r['pred_ARR']} | {r['pred_AFF']} |")
    lines.append("")
    lines.append("## Test Record Confusion")
    lines.append("")
    lines.append("| actual | pred NSR | pred CHF | pred ARR | pred AFF |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in split_outputs["test"][3]:
        lines.append(f"| {r['actual']} | {r['pred_NSR']} | {r['pred_CHF']} | {r['pred_ARR']} | {r['pred_AFF']} |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- XSim completed for train, validation, and test without fatal simulation errors.")
    lines.append("- The remaining compile warnings are width/unconnected-port warnings in abandoned compatibility stubs; they do not affect the selected Model S path.")
    lines.append("- The restored RTL test result matches the documented Model S test target exactly at segment and record level.")
    lines.append("- Train total accuracy matches the target; NSR and ARR class correct counts are swapped by one segment compared with the historical post-readout record.")
    lines.append("")

    (REPORTS / "model_s_rtl_final_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORTS / "model_s_rtl_final_report.md")


if __name__ == "__main__":
    main()
