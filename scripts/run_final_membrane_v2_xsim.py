from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "final_membrane_v2_snn"
DATASET = REPO / "fullrec_afe_30min_annotation_valid_balanced"
WORK = RESULTS / "xsim_snn_ecg_v2_work"
XVLOG = Path(r"C:\Xilinx\Vivado\2020.2\bin\xvlog.bat")
XELAB = Path(r"C:\Xilinx\Vivado\2020.2\bin\xelab.bat")
XSIM = Path(r"C:\Xilinx\Vivado\2020.2\bin\xsim.bat")

CLASSES = ["NSR", "CHF", "ARR", "AFF"]
SPLITS = ["train", "val", "test"]

CORE_SOURCES = [
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


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


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


def margin4(values: list[int]) -> int:
    order = sorted(range(4), key=lambda idx: values[idx], reverse=True)
    return values[order[0]] - values[order[1]]


def metrics(chunks: list[Any], pred: dict[str, int]) -> dict[str, Any]:
    cm = [[0 for _ in CLASSES] for _ in CLASSES]
    for chunk in chunks:
        cm[chunk.class_id][pred[chunk.case_id]] += 1
    total = sum(sum(row) for row in cm)
    correct = sum(cm[idx][idx] for idx in range(4))
    per_class: dict[str, dict[str, float | int]] = {}
    for idx, cls in enumerate(CLASSES):
        tp = cm[idx][idx]
        fp = sum(cm[row][idx] for row in range(4) if row != idx)
        fn = sum(cm[idx][col] for col in range(4) if col != idx)
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
        "per_class": per_class,
        "confusion_matrix": cm,
    }


def resolve_chunk_file(chunk_file: str) -> Path:
    path = Path(chunk_file)
    if path.is_absolute():
        return path
    return DATASET / path


def infer_margin_evidence_0038974(snn_mod: Any, arr_mod: Any, chunk: Any, base_params: dict[str, Any], arr_params: dict[str, Any]) -> tuple[int, list[int], dict[str, int]]:
    pred, mem, flags = arr_mod.infer_one(snn_mod, chunk, base_params, arr_params)
    fs = chunk.feature_sum
    rescue = int(
        pred == 3
        and margin4(mem) <= 12
        and chunk.pred_count[2] >= 3
        and fs["rdm_code_sum"] >= 512
        and fs["pnn_mismatch_count"] >= 800
        and fs["ectopic_pair_count"] >= 256
        and fs["abnormal_evidence_count"] >= 256
    )
    if rescue:
        mem = list(mem)
        mem[2] += 4
        mem[3] -= 16
        pred = argmax4(mem)
    return pred, list(mem), {"margin_evidence_rescue": rescue, **{k: int(v) for k, v in flags.items()}}


def prediction_rows(chunks: list[Any], pred: dict[str, int], detail: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in chunks:
        item = detail[chunk.case_id]
        row = {
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
        }
        for idx, cls in enumerate(CLASSES):
            row[f"final_mem_{cls}"] = item["mem"][idx]
        row.update(item["flags"])
        rows.append(row)
    return rows


def build_python_expected(splits: list[str]) -> dict[str, dict[str, Any]]:
    snn_mod = load_module(REPO / "scripts" / "search_final_membrane_v2_snn.py", "fmv2_snn_mod")
    arr_mod = load_module(REPO / "scripts" / "search_final_membrane_v2_arr_focus.py", "fmv2_arr_mod")
    base_params = json.loads((RESULTS / "local_rules_seed41031_selected_train_val_locked.json").read_text(encoding="utf-8"))["params"]
    arr_params = json.loads((RESULTS / "arr_focus_final_test_summary.json").read_text(encoding="utf-8"))["post_params"]
    chunks_by_split = snn_mod.split_chunks(splits)
    out: dict[str, dict[str, Any]] = {}
    selected = {
        "selection_note": "Internal engineering baseline fixed from margin_evidence_0038974. Use for RTL regression/resource comparison, not as an unbiased final test-selection claim.",
        "baseline": "arr_focus_0042452",
        "candidate_id": "margin_evidence_0038974",
        "operation": {
            "source": "AFF",
            "target": "ARR",
            "condition": "arr_focus_pred == AFF and arr_focus_margin <= 12 and pred_count_ARR >= 3 and rdm_code_sum >= 512 and pnn_mismatch_count >= 800 and ectopic_pair_count >= 256 and abnormal_evidence_count >= 256",
            "boost_ARR": 4,
            "inhibit_AFF": 16,
        },
        "snn_style": "30 one-minute snapshot pred spikes and feature evidence counts feed fixed comparator neurons and signed final membrane currents.",
    }
    for split in splits:
        chunks = chunks_by_split[split]
        pred: dict[str, int] = {}
        detail: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            y, mem, flags = infer_margin_evidence_0038974(snn_mod, arr_mod, chunk, base_params, arr_params)
            pred[chunk.case_id] = y
            detail[chunk.case_id] = {"mem": mem, "flags": flags}
        m = metrics(chunks, pred)
        out[split] = {"chunks": chunks, "pred": pred, "detail": detail, "metrics": m}
        write_csv(RESULTS / f"margin_evidence_0038974_python_{split}_predictions.csv", prediction_rows(chunks, pred, detail))
        (RESULTS / f"margin_evidence_0038974_python_{split}_metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
        selected[f"{split}_metrics"] = m
    (RESULTS / "margin_evidence_0038974_selected_baseline.json").write_text(json.dumps(selected, indent=2), encoding="utf-8")
    return out


def build_manifest(split: str, python_out: dict[str, dict[str, Any]]) -> Path:
    manifest = RESULTS / f"xsim_snn_ecg_v2_{split}_manifest.txt"
    chunks = sorted(python_out[split]["chunks"], key=lambda chunk: int(chunk.case_id))
    lines = []
    for chunk in chunks:
        mem_path = resolve_chunk_file(chunk.chunk_file)
        if not mem_path.exists():
            raise FileNotFoundError(mem_path)
        lines.append(f"{chunk.case_id} {chunk.class_id} 1800000 {slash(mem_path)}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return manifest


def write_wrapper(split: str, manifest: Path) -> Path:
    wrapper = WORK / f"tb_snn_ecg_v2_{split}.v"
    result_csv = RESULTS / f"xsim_snn_ecg_v2_{split}_predictions.csv"
    wrapper.write_text(
        f"""`timescale 1ns/1ps

module tb_snn_ecg_v2_{split};
    tb_snn_ecg_30min_chunk_dataset #(
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
    prj = WORK / f"sources_snn_ecg_v2_{split}.prj"
    lines = [f'verilog work "{slash(REPO / "rtl" / "core" / src)}"' for src in CORE_SOURCES]
    lines.extend(
        [
            f'verilog work "{slash(REPO / "rtl" / "final_membrane_layer.v")}"',
            f'verilog work "{slash(REPO / "rtl" / "snn_ecg_30min_final_top.v")}"',
            f'verilog work "{slash(REPO / "sim" / "tb_snn_ecg_30min_chunk_dataset.v")}"',
            f'verilog work "{slash(wrapper)}"',
        ]
    )
    prj.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    tcl = WORK / f"run_snn_ecg_v2_{split}.tcl"
    tcl.write_text("run all\nquit\n", encoding="utf-8", newline="\n")
    return prj, tcl


def run(cmd: list[str], cwd: Path, log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8", errors="replace") as f:
        proc = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed {proc.returncode}: {' '.join(cmd)}; see {log}")


def run_xsim_split(split: str, python_out: dict[str, dict[str, Any]]) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(split, python_out)
    wrapper = write_wrapper(split, manifest)
    prj, tcl = write_project(split, wrapper)
    top = f"tb_snn_ecg_v2_{split}"
    snap = f"{top}_behav"
    run([str(XVLOG), "--nolog", "-prj", slash(prj)], WORK, RESULTS / f"xsim_snn_ecg_v2_{split}_xvlog.log")
    run([str(XELAB), "--nolog", "-debug", "typical", top, "-s", snap], WORK, RESULTS / f"xsim_snn_ecg_v2_{split}_xelab.log")
    run([str(XSIM), snap, "--nolog", "-tclbatch", slash(tcl)], WORK, RESULTS / f"xsim_snn_ecg_v2_{split}.log")
    xsim_rows = read_csv(RESULTS / f"xsim_snn_ecg_v2_{split}_predictions.csv")
    pred = {row["case_id"]: int(row["final_pred_class"]) for row in xsim_rows}
    chunks = python_out[split]["chunks"]
    m = metrics(chunks, pred)
    (RESULTS / f"xsim_snn_ecg_v2_{split}_metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    print(f"[xsim-snn-ecg-v2] {split} {m['correct']}/{m['total']} acc={m['accuracy']:.4f}", flush=True)


def compare_split(split: str, python_out: dict[str, dict[str, Any]]) -> dict[str, int]:
    py_pred = python_out[split]["pred"]
    py_detail = python_out[split]["detail"]
    rows = []
    pred_mismatch = 0
    mem_mismatch = 0
    for row in read_csv(RESULTS / f"xsim_snn_ecg_v2_{split}_predictions.csv"):
        case_id = row["case_id"]
        py_mem = py_detail[case_id]["mem"]
        x_mem = [int(row[f"final_mem_{cls}"]) for cls in CLASSES]
        pm = int(py_pred[case_id] != int(row["final_pred_class"]))
        mm = int(py_mem != x_mem)
        pred_mismatch += pm
        mem_mismatch += mm
        rows.append(
            {
                "split": split,
                "case_id": case_id,
                "expected_class": row["expected_class"],
                "python_pred_class": py_pred[case_id],
                "xsim_pred_class": row["final_pred_class"],
                "pred_mismatch": pm,
                "python_final_mem_NSR": py_mem[0],
                "python_final_mem_CHF": py_mem[1],
                "python_final_mem_ARR": py_mem[2],
                "python_final_mem_AFF": py_mem[3],
                "xsim_final_mem_NSR": x_mem[0],
                "xsim_final_mem_CHF": x_mem[1],
                "xsim_final_mem_ARR": x_mem[2],
                "xsim_final_mem_AFF": x_mem[3],
                "mem_mismatch": mm,
            }
        )
    write_csv(RESULTS / f"python_vs_xsim_snn_ecg_v2_compare_{split}.csv", rows)
    return {"rows": len(rows), "pred_mismatch": pred_mismatch, "mem_mismatch": mem_mismatch}


def write_summary(splits: list[str], compare: dict[str, dict[str, int]], python_out: dict[str, dict[str, Any]]) -> None:
    summary: dict[str, Any] = {
        "candidate_id": "margin_evidence_0038974",
        "structure": "30-minute stream -> timer neuron 60s snapshot spikes -> Snapshot V2 -> final membrane row612 WTA",
        "splits": {},
        "python_vs_xsim": compare,
    }
    for split in splits:
        xsim_m = json.loads((RESULTS / f"xsim_snn_ecg_v2_{split}_metrics.json").read_text(encoding="utf-8"))
        summary["splits"][split] = {
            "python": python_out[split]["metrics"],
            "xsim": xsim_m,
        }
    (RESULTS / "xsim_snn_ecg_v2_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# SNN ECG V2 Final Membrane XSim Report",
        "",
        "Candidate: `margin_evidence_0038974`.",
        "",
        "Structure: 30-minute ADC stream -> timer neuron emits one 60-second snapshot spike every 60000 accepted samples -> fixed Snapshot V2 -> final membrane signed current accumulation -> WTA.",
        "",
        "| Split | Python | XSim | Pred mismatch | Mem mismatch |",
        "|---|---:|---:|---:|---:|",
    ]
    for split in splits:
        py_m = python_out[split]["metrics"]
        xs_m = summary["splits"][split]["xsim"]
        cmp_m = compare[split]
        lines.append(
            f"| {split} | {py_m['correct']}/{py_m['total']} = {py_m['accuracy']:.4f} | "
            f"{xs_m['correct']}/{xs_m['total']} = {xs_m['accuracy']:.4f} | "
            f"{cmp_m['pred_mismatch']} | {cmp_m['mem_mismatch']} |"
        )
    lines.extend(
        [
            "",
            "The row612 neuron is comparator/add-sub only:",
            "",
            "```text",
            "if arr_focus_pred == AFF and arr_focus_margin <= 12 and pred_count_ARR >= 3 and rdm_code_sum >= 512",
            "   and pNN_mismatch >= 800 and ectopic_pair >= 256 and abnormal_evidence >= 256:",
            "    final_mem_ARR += 4",
            "    final_mem_AFF -= 16",
            "```",
        ]
    )
    (RESULTS / "snn_ecg_v2_xsim_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=[*SPLITS, "all"], default="all")
    parser.add_argument("--python-only", action="store_true")
    args = parser.parse_args()
    splits = SPLITS if args.split == "all" else [args.split]

    python_out = build_python_expected(splits)
    if args.python_only:
        for split in splits:
            m = python_out[split]["metrics"]
            print(f"[python-margin-evidence] {split} {m['correct']}/{m['total']} acc={m['accuracy']:.4f}", flush=True)
        return

    compare: dict[str, dict[str, int]] = {}
    for split in splits:
        run_xsim_split(split, python_out)
        compare[split] = compare_split(split, python_out)
        print(
            f"[compare] {split} pred_mismatch={compare[split]['pred_mismatch']} "
            f"mem_mismatch={compare[split]['mem_mismatch']}",
            flush=True,
        )
    write_summary(splits, compare, python_out)


if __name__ == "__main__":
    main()
