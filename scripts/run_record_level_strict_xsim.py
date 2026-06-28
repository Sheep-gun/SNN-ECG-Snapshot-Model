from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np

from final_membrane_30min_recordwise_pipeline import CLASSES, DATASET, RESULTS, SPLITS, metrics_from_pred, read_csv, write_csv


REPO = Path(__file__).resolve().parents[1]
WORK = RESULTS / "xsim_record_level_strict_work"
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


def run(cmd: list[str], cwd: Path, log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8", errors="replace") as f:
        proc = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed {proc.returncode}: {' '.join(cmd)}; see {log}")


def sort_key(row: dict) -> tuple:
    return (row["class_label"], row["record_id"], int(row["chunk_id"]), int(row["case_id"]))


def build_manifest(split: str) -> Path:
    rows = sorted(read_csv(RESULTS / f"no_oracle_record_level_strict_{split}_predictions.csv"), key=sort_key)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["class_label"], row["record_id"])].append(row)

    manifest = RESULTS / f"xsim_record_level_strict_{split}_manifest.txt"
    lines = []
    for key in sorted(groups):
        group = sorted(groups[key], key=sort_key)
        for idx, row in enumerate(group):
            mem_path = DATASET / row["chunk_file"]
            if not mem_path.exists():
                raise FileNotFoundError(mem_path)
            record_start = 1 if idx == 0 else 0
            record_done = 1 if idx == (len(group) - 1) else 0
            lines.append(
                f"{row['case_id']} {row['class_id']} 1800000 {record_start} {record_done} {slash(mem_path)}"
            )
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return manifest


def write_wrapper(split: str, manifest: Path) -> Path:
    wrapper = WORK / f"tb_record_level_strict_{split}.v"
    result_csv = RESULTS / f"xsim_record_level_strict_{split}_predictions.csv"
    wrapper.write_text(
        f"""`timescale 1ns/1ps

module tb_record_level_strict_{split};
    tb_snn_ecg_30min_record_level_dataset #(
        .MAX_SAMPLES(1800000),
        .MAX_RECORD_CHUNKS(128),
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
    prj = WORK / f"sources_record_level_strict_{split}.prj"
    lines = [f'verilog work "{slash(REPO / "rtl" / "core" / src)}"' for src in SOURCES]
    lines.extend(
        [
            f'verilog work "{slash(REPO / "rtl" / "final_membrane_layer.v")}"',
            f'verilog work "{slash(REPO / "rtl" / "record_level_final_membrane_layer.v")}"',
            f'verilog work "{slash(REPO / "rtl" / "snn_ecg_30min_final_top.v")}"',
            f'verilog work "{slash(REPO / "sim" / "tb_snn_ecg_30min_record_level_dataset.v")}"',
            f'verilog work "{slash(wrapper)}"',
        ]
    )
    prj.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    tcl = WORK / f"run_record_level_strict_{split}.tcl"
    tcl.write_text("run all\nquit\n", encoding="utf-8", newline="\n")
    return prj, tcl


def write_metrics(split: str) -> dict:
    rows = read_csv(RESULTS / f"xsim_record_level_strict_{split}_predictions.csv")
    y_true = np.array([int(row["expected_class"]) for row in rows], dtype=np.int64)
    y_pred = np.array([int(row["final_pred_class"]) for row in rows], dtype=np.int64)
    metrics = metrics_from_pred(y_true, y_pred)
    (RESULTS / f"xsim_record_level_strict_{split}_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def run_split(split: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(split)
    wrapper = write_wrapper(split, manifest)
    prj, tcl = write_project(split, wrapper)
    top = f"tb_record_level_strict_{split}"
    snap = f"{top}_behav"
    run([str(XVLOG), "--nolog", "-prj", slash(prj)], WORK, RESULTS / f"xsim_record_level_strict_{split}_xvlog.log")
    run([str(XELAB), "--nolog", "-debug", "typical", top, "-s", snap], WORK, RESULTS / f"xsim_record_level_strict_{split}_xelab.log")
    run([str(XSIM), snap, "--nolog", "-tclbatch", slash(tcl)], WORK, RESULTS / f"xsim_record_level_strict_{split}.log")
    metrics = write_metrics(split)
    print(f"[xsim-record] {split} {metrics['correct']}/{metrics['total']} acc={metrics['accuracy']:.4f}", flush=True)


def compare_python_xsim(splits: list[str]) -> None:
    rows = []
    for split in splits:
        py_rows = {
            row["case_id"]: row
            for row in read_csv(RESULTS / f"no_oracle_record_level_strict_{split}_predictions.csv")
        }
        for row in read_csv(RESULTS / f"xsim_record_level_strict_{split}_predictions.csv"):
            py = py_rows.get(row["case_id"])
            pred_mismatch = int((py is None) or (py["final_pred_class"] != row["final_pred_class"]))
            rows.append(
                {
                    "split": split,
                    "case_id": row["case_id"],
                    "expected_class": row["expected_class"],
                    "python_pred_class": py["final_pred_class"] if py else "",
                    "xsim_pred_class": row["final_pred_class"],
                    "pred_mismatch": pred_mismatch,
                    "xsim_final_valid": row["final_valid"],
                    "xsim_samples_driven": row["samples_driven"],
                    "xsim_final_mem_NSR": row["final_mem_NSR"],
                    "xsim_final_mem_CHF": row["final_mem_CHF"],
                    "xsim_final_mem_ARR": row["final_mem_ARR"],
                    "xsim_final_mem_AFF": row["final_mem_AFF"],
                }
            )
    write_csv(RESULTS / "python_vs_xsim_record_level_strict_compare.csv", rows)
    print(
        f"[compare-record] rows={len(rows)} pred_mismatch={sum(int(r['pred_mismatch']) for r in rows)}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=[*SPLITS, "all"], default="all")
    args = parser.parse_args()
    splits = SPLITS if args.split == "all" else [args.split]
    for split in splits:
        run_split(split)
    compare_python_xsim(splits)


if __name__ == "__main__":
    main()
