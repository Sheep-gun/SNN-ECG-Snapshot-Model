from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

CLASSES = ["NSR", "CHF", "ARR", "AFF"]

REPO = Path(__file__).resolve().parents[1]
DATASET = REPO / "60s_afe_datasets" / "afe_output_xmodelmatch_curated_v2_128_64_64_balanced"
RESULTS = REPO / "results" / "snapshot_c24_v2_search"
WORK = RESULTS / "xsim_snapshot_v2_work"
XVLOG = Path(r"C:\Xilinx\Vivado\2020.2\bin\xvlog.bat")
XELAB = Path(r"C:\Xilinx\Vivado\2020.2\bin\xelab.bat")
XSIM = Path(r"C:\Xilinx\Vivado\2020.2\bin\xsim.bat")

SOURCES = [
    "ecg_event_encoder.v",
    "ecg_event_encoder_adaptive.v",
    "snn_ecg_input_normalizer.v",
    "qrs_lif_detector.v",
    "pnn_rhythm_predictor.v",
    "dscr_spike_counter.v",
    "ram_peak_accumulator.v",
    "rdm_variability_neuron.v",
    "ectopic_pair_neuron.v",
    "qrs_maf_neuron.v",
    "rbbb_qrs_delay_bank.v",
    "abandoned_feature_stubs.v",
    "class_score_neurons.v",
    "snn_ecg_3feat_top.v",
]


def slash(path: Path) -> str:
    return str(path).replace("\\", "/")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run(cmd: list[str], cwd: Path, log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8", errors="replace") as f:
        proc = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed {proc.returncode}: {' '.join(cmd)}; see {log}")


def read_manifest(split: str, dataset: Path) -> list[dict[str, str]]:
    manifest = dataset / f"afe_manifest_{split}.csv"
    if not manifest.exists():
        raise FileNotFoundError(manifest)
    return read_csv(manifest)


def resolve_mem(row: dict[str, str], dataset: Path) -> Path:
    for key in ("afe_adc_signed_file", "signed_mem_file", "mem_file", "afe_mem_file"):
        value = row.get(key, "")
        if value:
            path = Path(value)
            if not path.is_absolute():
                direct = dataset / path
                from_parent = dataset.parent / path
                path = direct if direct.exists() else from_parent
            return path
    raise KeyError(f"no signed mem path column found in manifest row: {row.keys()}")


def write_manifest(split: str, dataset: Path) -> Path:
    manifest_rows = read_manifest(split, dataset)
    manifest_path = RESULTS / f"xsim_snapshot_v2_{split}_manifest.txt"
    lines: list[str] = []
    for row in manifest_rows:
        row_index = int(row.get("row_index", len(lines))) if row.get("row_index") else len(lines)
        mem_path = resolve_mem(row, dataset)
        lines.append(f"{row_index} {int(row['class_id'])} 60000 {slash(mem_path)}")
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return manifest_path


def write_wrapper(split: str, manifest: Path) -> Path:
    wrapper = WORK / f"tb_snapshot_v2_{split}.v"
    result_csv = RESULTS / f"xsim_snapshot_v2_{split}_predictions.csv"
    wrapper.write_text(
        f"""`timescale 1ns/1ps

module tb_snapshot_v2_{split};
    tb_snapshot_c24_dataset #(
        .MAX_SAMPLES(60000),
        .MANIFEST_FILE("{slash(manifest)}"),
        .RESULT_CSV("{slash(result_csv)}")
    ) tb();
endmodule
""",
        encoding="utf-8",
        newline="\n",
    )
    return wrapper


def write_project(split: str, wrapper: Path) -> tuple[Path, Path]:
    prj = WORK / f"sources_snapshot_v2_{split}.prj"
    lines = [f'verilog work "{slash(REPO / "rtl" / "core" / src)}"' for src in SOURCES]
    lines.extend(
        [
            f'verilog work "{slash(REPO / "sim" / "tb_snapshot_c24_dataset.v")}"',
            f'verilog work "{slash(wrapper)}"',
        ]
    )
    prj.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    tcl = WORK / f"run_snapshot_v2_{split}.tcl"
    tcl.write_text("run all\nquit\n", encoding="utf-8", newline="\n")
    return prj, tcl


def metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    cm = {t: {p: 0 for p in CLASSES} for t in CLASSES}
    for row in rows:
        true_label = CLASSES[int(row["expected_class"])]
        pred_label = CLASSES[int(row["pred_class"])]
        cm[true_label][pred_label] += 1
    total = len(rows)
    correct = sum(cm[c][c] for c in CLASSES)
    per_class: dict[str, dict[str, float]] = {}
    for cls in CLASSES:
        tp = cm[cls][cls]
        fp = sum(cm[t][cls] for t in CLASSES if t != cls)
        fn = sum(cm[cls][p] for p in CLASSES if p != cls)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[cls] = {"precision": precision, "recall": recall, "f1": f1}
    return {
        "correct": correct,
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "macro_f1": sum(per_class[c]["f1"] for c in CLASSES) / len(CLASSES),
        "balanced_accuracy": sum(per_class[c]["recall"] for c in CLASSES) / len(CLASSES),
        "per_class": per_class,
        "confusion": cm,
    }


def compare_split(split: str) -> dict[str, object]:
    xsim_rows = read_csv(RESULTS / f"xsim_snapshot_v2_{split}_predictions.csv")
    expected_path = RESULTS / f"snapshot_v2_python_expected_{split}.csv"
    expected_rows = read_csv(expected_path) if expected_path.exists() else []
    expected_by_case = {row["case_id"]: row for row in expected_rows}
    compare: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    pred_mismatch = 0
    mem_mismatch = 0
    valid_mismatch = 0
    for row in xsim_rows:
        exp = expected_by_case.get(row["case_id"], {})
        pred_match = exp.get("expected_pred_class", row["pred_class"]) == row["pred_class"]
        mem_match = True
        mem_fields: dict[str, object] = {}
        for cls in CLASSES:
            x_key = f"class_mem_{cls}"
            p_key = f"expected_class_mem_{cls}"
            py_value = exp.get(p_key, row[x_key])
            x_value = row[x_key]
            delta = int(x_value) - int(py_value)
            mem_fields[f"python_{x_key}"] = py_value
            mem_fields[f"xsim_{x_key}"] = x_value
            mem_fields[f"delta_{x_key}"] = delta
            if delta != 0:
                mem_match = False
        if not pred_match:
            pred_mismatch += 1
        if not mem_match:
            mem_mismatch += 1
        if row["pred_valid"] != "1":
            valid_mismatch += 1
        compare.append(
            {
                "split": split,
                "case_id": row["case_id"],
                "expected_class": row["expected_class"],
                "python_pred_class": exp.get("expected_pred_class", ""),
                "xsim_pred_class": row["pred_class"],
                "pred_match": int(pred_match),
                "correct": row["correct"],
                "pred_valid": row["pred_valid"],
                "mem_match": int(mem_match),
                **mem_fields,
            }
        )
        metric_rows.append({"expected_class": row["expected_class"], "pred_class": row["pred_class"]})
    write_csv(RESULTS / f"python_vs_xsim_snapshot_v2_compare_{split}.csv", compare)
    result = metrics(metric_rows)
    result["python_expected_rows"] = len(expected_rows)
    result["pred_mismatch_vs_python"] = pred_mismatch
    result["mem_mismatch_rows_vs_python"] = mem_mismatch
    result["pred_valid_not_1"] = valid_mismatch
    (RESULTS / f"xsim_snapshot_v2_{split}_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_split(split: str, dataset: Path) -> dict[str, object]:
    if not XVLOG.exists() or not XELAB.exists() or not XSIM.exists():
        raise FileNotFoundError("Vivado 2020.2 XSim tools were not found under C:\\Xilinx\\Vivado\\2020.2\\bin")
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = write_manifest(split, dataset)
    wrapper = write_wrapper(split, manifest)
    prj, tcl = write_project(split, wrapper)
    top = f"tb_snapshot_v2_{split}"
    snap = f"{top}_behav"
    run([str(XVLOG), "--nolog", "-prj", slash(prj)], WORK, RESULTS / f"xsim_snapshot_v2_{split}_xvlog.log")
    run([str(XELAB), "--nolog", "-debug", "typical", top, "-s", snap], WORK, RESULTS / f"xsim_snapshot_v2_{split}_xelab.log")
    run([str(XSIM), snap, "--nolog", "-tclbatch", slash(tcl)], WORK, RESULTS / f"xsim_snapshot_v2_{split}.log")
    result = compare_split(split)
    print(
        f"[xsim-snapshot-v2] {split} {result['correct']}/{result['total']} "
        f"acc={result['accuracy']:.4f}",
        flush=True,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", default=str(DATASET))
    parser.add_argument("--split", choices=["train", "val", "test", "all"], default="all")
    args = parser.parse_args()
    dataset = Path(args.dataset_root)
    splits = ["train", "val", "test"] if args.split == "all" else [args.split]
    summary_path = RESULTS / "xsim_snapshot_v2_summary.json"
    if summary_path.exists() and args.split != "all":
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {}
    for split in splits:
        summary[split] = run_split(split, dataset)
    ordered = {split: summary[split] for split in ["train", "val", "test"] if split in summary}
    summary_path.write_text(json.dumps(ordered, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
