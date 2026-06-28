from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import numpy as np

from final_membrane_30min_recordwise_pipeline import CLASSES, DATASET, RESULTS, SPLITS, metrics_from_pred, read_csv, write_csv


REPO = Path(__file__).resolve().parents[1]
WORK = RESULTS / "xsim_stream_work"
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


def build_manifest(split: str) -> Path:
    rows = read_csv(RESULTS / f"python_{split}_predictions.csv")
    manifest = RESULTS / f"xsim_{split}_manifest.txt"
    lines = []
    for row in rows:
        mem_path = DATASET / row["chunk_file"]
        if not mem_path.exists():
            raise FileNotFoundError(mem_path)
        lines.append(f"{row['case_id']} {row['class_id']} 1800000 {slash(mem_path)}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return manifest


def write_wrapper(split: str, manifest: Path) -> Path:
    wrapper = WORK / f"tb_snn_ecg_30min_recordwise_{split}.v"
    result_csv = RESULTS / f"xsim_{split}_predictions.csv"
    wrapper.write_text(
        f"""`timescale 1ns/1ps

module tb_snn_ecg_30min_recordwise_{split};
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


def write_metrics(split: str) -> dict:
    rows = read_csv(RESULTS / f"xsim_{split}_predictions.csv")
    y_true = np.array([int(row["expected_class"]) for row in rows], dtype=np.int64)
    y_pred = np.array([int(row["final_pred_class"]) for row in rows], dtype=np.int64)
    metrics = metrics_from_pred(y_true, y_pred)
    (RESULTS / f"xsim_{split}_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def run_split(split: str) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(split)
    wrapper = write_wrapper(split, manifest)
    prj, tcl = write_project(split, wrapper)
    top = f"tb_snn_ecg_30min_recordwise_{split}"
    snap = f"{top}_behav"
    run([str(XVLOG), "--nolog", "-prj", slash(prj)], WORK, RESULTS / f"xsim_{split}_xvlog.log")
    run([str(XELAB), "--nolog", "-debug", "typical", top, "-s", snap], WORK, RESULTS / f"xsim_{split}_xelab.log")
    run([str(XSIM), snap, "--nolog", "-tclbatch", slash(tcl)], WORK, RESULTS / f"xsim_{split}.log")
    m = write_metrics(split)
    print(f"[xsim] {split} {m['correct']}/{m['total']} acc={m['accuracy']:.4f}", flush=True)


def compare_python_xsim() -> None:
    rows = []
    for split in SPLITS:
        py_rows = {row["case_id"]: row for row in read_csv(RESULTS / f"python_{split}_predictions.csv")}
        for row in read_csv(RESULTS / f"xsim_{split}_predictions.csv"):
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
                mismatch = int((py is None) or (py_mem != xsim_mem))
                out[f"python_final_mem_{cls}"] = py_mem if py else ""
                out[f"xsim_final_mem_{cls}"] = xsim_mem
                out[f"final_mem_{cls}_mismatch"] = mismatch
                any_mem |= mismatch
            out["any_final_mem_mismatch"] = any_mem
            rows.append(out)
    write_csv(RESULTS / "python_vs_xsim_compare.csv", rows)
    print(
        f"[compare] rows={len(rows)} pred_mismatch={sum(int(r['pred_mismatch']) for r in rows)} "
        f"mem_mismatch={sum(int(r['any_final_mem_mismatch']) for r in rows)}",
        flush=True,
    )


def main() -> None:
    for split in SPLITS:
        run_split(split)
    compare_python_xsim()


if __name__ == "__main__":
    main()
