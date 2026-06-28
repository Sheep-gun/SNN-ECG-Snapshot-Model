from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

import numpy as np


REPO = Path(__file__).resolve().parents[1]
DATASET = REPO / "fullrec_afe_30min_annotation_valid_balanced"
MANIFEST = DATASET / "annotation_valid_balanced_30min_manifest.csv"
RESULTS = REPO / "results" / "final_membrane_30min"
WORK = RESULTS / "xsim_stream_work"

XVLOG = Path(r"C:\Xilinx\Vivado\2020.2\bin\xvlog.bat")
XELAB = Path(r"C:\Xilinx\Vivado\2020.2\bin\xelab.bat")
XSIM = Path(r"C:\Xilinx\Vivado\2020.2\bin\xsim.bat")

CLASSES = ["NSR", "CHF", "ARR", "AFF"]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASSES)}
SPLITS = ["train", "val", "test"]
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
    return path.resolve().as_posix()


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


def run(cmd: list[str], cwd: Path, log_path: Path) -> None:
    print("$ " + " ".join(cmd), flush=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-120:]
        raise SystemExit(f"command failed: {' '.join(cmd)}\nlog: {log_path}\n" + "\n".join(tail))


def metrics_from_pred(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    cm = [[0 for _ in CLASSES] for _ in CLASSES]
    for t, p in zip(y_true.tolist(), y_pred.tolist()):
        cm[int(t)][int(p)] += 1
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
        "min_recall": float(min(recalls)) if recalls else 0.0,
        "recall_range": float(max(recalls) - min(recalls)) if recalls else 0.0,
        "per_class": per_class,
        "confusion_matrix": cm,
    }


def build_manifest(split: str, limit: int = 0) -> Path:
    snapshot_rows = read_csv(RESULTS / f"snapshot_dump_{split}.csv")
    grouped: dict[int, dict[str, str]] = {}
    for row in snapshot_rows:
        case_id = int(row["case_id"])
        if int(row["snapshot_id"]) == 0:
            grouped[case_id] = row
    rows = [grouped[case_id] for case_id in sorted(grouped)]
    if limit > 0:
        rows = rows[:limit]
    out = RESULTS / f"xsim_{split}_manifest.txt"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            case_id = int(row["case_id"])
            class_id = CLASS_TO_ID[row["class_label"]]
            mem_path = DATASET / row["chunk_file"]
            if not mem_path.exists():
                raise FileNotFoundError(mem_path)
            f.write(f"{case_id} {class_id} 1800000 {slash(mem_path)}\n")
    return out


def write_wrapper(split: str, manifest: Path) -> Path:
    wrapper = WORK / f"tb_snn_ecg_30min_final_{split}.v"
    result_csv = RESULTS / f"xsim_{split}_predictions.csv"
    wrapper.write_text(
        f"""`timescale 1ns/1ps

module tb_snn_ecg_30min_final_{split};
    tb_snn_ecg_30min_final_dataset #(
        .MAX_SAMPLES(1800000),
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
    prj = WORK / f"sources_{split}.prj"
    lines = [f'verilog work "{slash(REPO / "rtl" / "core" / src)}"' for src in SOURCES]
    lines.extend(
        [
            f'verilog work "{slash(REPO / "rtl" / "final_membrane_layer.v")}"',
            f'verilog work "{slash(REPO / "rtl" / "snn_ecg_30min_final_top.v")}"',
            f'verilog work "{slash(REPO / "sim" / "tb_snn_ecg_30min_final_dataset.v")}"',
            f'verilog work "{slash(wrapper)}"',
        ]
    )
    prj.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    tcl = WORK / f"run_{split}.tcl"
    tcl.write_text("run all\nquit\n", encoding="utf-8", newline="\n")
    return prj, tcl


def run_split(split: str, limit: int = 0) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(split, limit)
    wrapper = write_wrapper(split, manifest)
    prj, tcl = write_project(split, wrapper)
    top = f"tb_snn_ecg_30min_final_{split}"
    snap = f"{top}_behav"
    run([str(XVLOG), "--nolog", "-prj", slash(prj)], WORK, RESULTS / f"xsim_{split}_xvlog.log")
    run([str(XELAB), "--nolog", "-debug", "typical", top, "-s", snap], WORK, RESULTS / f"xsim_{split}_xelab.log")
    run([str(XSIM), snap, "--nolog", "-tclbatch", slash(tcl)], WORK, RESULTS / f"xsim_{split}.log")
    write_metrics(split)


def write_metrics(split: str) -> dict:
    rows = read_csv(RESULTS / f"xsim_{split}_predictions.csv")
    y_true = np.array([int(row["expected_class"]) for row in rows], dtype=np.int64)
    y_pred = np.array([int(row["final_pred_class"]) for row in rows], dtype=np.int64)
    metrics = metrics_from_pred(y_true, y_pred)
    (RESULTS / f"xsim_{split}_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"[metrics] {split} {metrics['correct']}/{metrics['total']} acc={metrics['accuracy']:.4f}", flush=True)
    return metrics


def compare_python_xsim() -> None:
    rows = []
    for split in SPLITS:
        py_path = RESULTS / f"python_{split}_predictions.csv"
        xsim_path = RESULTS / f"xsim_{split}_predictions.csv"
        if not py_path.exists() or not xsim_path.exists():
            continue
        py_rows = {row["case_id"]: row for row in read_csv(py_path)}
        for row in read_csv(xsim_path):
            py = py_rows.get(row["case_id"])
            out = {
                "split": split,
                "case_id": row["case_id"],
                "expected_class": row["expected_class"],
                "python_pred_class": py["final_pred_class"] if py else "",
                "xsim_pred_class": row["final_pred_class"],
                "pred_mismatch": int((py is None) or (py["final_pred_class"] != row["final_pred_class"])),
                "xsim_final_valid": row["final_valid"],
                "xsim_samples_driven": row["samples_driven"],
            }
            any_mem = 0
            for cls in CLASSES:
                py_mem = int(py[f"final_mem_{cls}"]) if py else 0
                xsim_mem = int(row[f"final_mem_{cls}"])
                out[f"python_final_mem_{cls}"] = py_mem if py else ""
                out[f"xsim_final_mem_{cls}"] = xsim_mem
                out[f"final_mem_{cls}_mismatch"] = int((py is None) or (py_mem != xsim_mem))
                any_mem |= out[f"final_mem_{cls}_mismatch"]
            out["any_final_mem_mismatch"] = any_mem
            rows.append(out)
    write_csv(RESULTS / "python_vs_xsim_compare.csv", rows)
    print(
        f"[compare] rows={len(rows)} pred_mismatch={sum(int(r['pred_mismatch']) for r in rows)} "
        f"mem_mismatch={sum(int(r['any_final_mem_mismatch']) for r in rows)}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=SPLITS + ["all"], default="all")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--compare-only", action="store_true")
    args = parser.parse_args()
    if args.compare_only:
        for split in SPLITS:
            if (RESULTS / f"xsim_{split}_predictions.csv").exists():
                write_metrics(split)
        compare_python_xsim()
        return
    splits = SPLITS if args.split == "all" else [args.split]
    for split in splits:
        run_split(split, args.limit)
    compare_python_xsim()


if __name__ == "__main__":
    main()
