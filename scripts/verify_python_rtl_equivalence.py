from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parents[0]
sys.path.insert(0, str(SCRIPT_DIR))

from fullrec_patient_membrane_layer import (  # noqa: E402
    CLASSES,
    CLASS_TO_ID,
    WINDOW_SAMPLES,
    read_csv,
    write_csv,
)
from snapshot_c24_rtl_exact import run_qrs_on_mem  # noqa: E402


RESULTS = REPO / "results" / "python_rtl_equivalence"
PATIENT_RESULTS = REPO / "results" / "patient_membrane_layer"
WEIGHTS_PATH = REPO / "results" / "c24_rtl_equivalence" / "c24_folded_weights_for_rtl.json"
FULLREC_MANIFEST = REPO / "fullrec_afe" / "fullrec_manifest.csv"
SIM_SRC = REPO / "SNN_ECG.srcs" / "sources_1" / "new"
BASE_TB = REPO / "sim" / "tb_snn_ecg_3feat_dataset.v"
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
    "snn_ecg_model_a_plus_core.v",
]

FEATURE_COLUMNS = [
    "beat_count",
    "pnn_match_count",
    "pnn_mismatch_count",
    "dscr_flip_count",
    "dscr_slope_count",
    "ram_code_sum",
    "ram_code_count",
    "rdm_valid_count",
    "rdm_code_sum",
    "rdm_ge10_count",
    "rdm_ge20_count",
    "rdm_ge30_count",
    "rdm_ge40_count",
    "rdm_ge50_count",
    "rdm_ge60_count",
    "rdm_ge70_count",
    "rdm_ge80_count",
    "rdm_ge90_count",
    "rdm_ge100_count",
    "rdm_ge110_count",
    "rdm_ge120_count",
    "rdm_ge130_count",
    "rdm_ge140_count",
    "rdm_ge150_count",
    "ectopic_pair_count",
    "qrs_maf_valid_count",
    "qrs_maf_count",
    "qrs_maf_code_sum",
    "qrs_width_abn_count",
    "qrs_complex_abn_count",
    "qrs_energy_abn_count",
    "qrs_terminal_delay_count",
    "qrs_late_energy_count",
    "qrs_asymmetry_count",
    "qrs_peak_to_tail_count",
    "qrs_pvc_like_count",
    "qrs_rbbb_like_count",
    "qrs_maf_width_sum",
    "qrs_maf_complex_sum",
    "qrs_maf_energy_sum",
    "rbbb_delay_valid_count",
    "rbbb_delay_wide_count",
    "rbbb_delay_terminal_count",
    "rbbb_delay_like_count",
    "rbbb_delay_segment_count",
    "rbbb_delay_applied_count",
    "pre_qrs_bump_count",
    "eerg_gate_count",
    "eerg_applied_count",
    "eerg_pre_qrs_bump_count",
    "eerg_early_count",
    "eerg_ecp_count",
    "eerg_pnn_decision_count",
    "eerg_pnn_mismatch_count",
    "eerg_rdm_valid_count",
    "eerg_rdm_code_sum",
]

MEM_COLUMNS = ["class_mem_NSR", "class_mem_CHF", "class_mem_ARR", "class_mem_AFF"]
RTL_MEM_COLUMNS = ["c24_mem_NSR", "c24_mem_CHF", "c24_mem_ARR", "c24_mem_AFF"]


def slash(path: Path) -> str:
    return path.resolve().as_posix()


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value)


def load_window_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for split in ["train", "val", "test"]:
        path = PATIENT_RESULTS / f"window_snapshot_dump_{split}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        rows.extend(read_csv(path))
    return rows


def select_windows(rows: list[dict[str, str]], target_count: int) -> list[dict[str, str]]:
    selected: dict[tuple[str, str, str], dict[str, str]] = {}

    def add(row: dict[str, str], tag: str) -> None:
        key = (row["split"], row["record_id"], row["window_id"])
        existing = selected.get(key)
        if existing is None:
            new = dict(row)
            new["selection_tags"] = tag
            selected[key] = new
        elif tag not in existing["selection_tags"].split("|"):
            existing["selection_tags"] += "|" + tag

    by_record: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    by_split_class: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_record[(row["split"], row["true_record_class"], row["record_id"])].append(row)
        by_split_class[(row["split"], row["true_record_class"])].append(row)

    for rec_key, rec_rows in by_record.items():
        rec_rows.sort(key=lambda r: int(float(r["window_id"])))
        positions = [
            ("record_start", rec_rows[0]),
            ("record_middle", rec_rows[len(rec_rows) // 2]),
            ("record_end", rec_rows[-1]),
        ]
        for tag, row in positions:
            add(row, tag)

    for group_key, group_rows in by_split_class.items():
        correct = [r for r in group_rows if int(float(r["pred_class_id"])) == int(float(r["true_class_id"]))]
        wrong = [r for r in group_rows if int(float(r["pred_class_id"])) != int(float(r["true_class_id"]))]
        if correct:
            add(correct[len(correct) // 2], "python_correct_window")
        if wrong:
            add(wrong[len(wrong) // 2], "python_misclassified_window")
        low = min(group_rows, key=lambda r: int(float(r["top_margin"])))
        add(low, "python_low_confidence_window")

    if len(selected) < target_count:
        rng = np.random.default_rng(20260628)
        for group_key, group_rows in sorted(by_split_class.items()):
            need = max(0, target_count - len(selected))
            if need <= 0:
                break
            take = min(max(1, target_count // max(1, len(by_split_class))), len(group_rows))
            idxs = rng.choice(len(group_rows), size=min(take, len(group_rows)), replace=False)
            for idx in idxs:
                add(group_rows[int(idx)], "stratified_fill")
                if len(selected) >= target_count:
                    break

    if len(selected) < target_count:
        rng = np.random.default_rng(20260629)
        remaining = [
            r for r in rows
            if (r["split"], r["record_id"], r["window_id"]) not in selected
        ]
        idxs = rng.choice(len(remaining), size=min(target_count - len(selected), len(remaining)), replace=False)
        for idx in idxs:
            add(remaining[int(idx)], "random_fill")

    ordered = list(selected.values())
    ordered.sort(key=lambda r: (r["split"], r["true_record_class"], r["record_id"], int(float(r["window_id"]))))
    return ordered


def copy_window_mem(selection: list[dict[str, str]], out_dir: Path) -> None:
    manifest_rows = read_csv(FULLREC_MANIFEST)
    fullrec_path = {(r["split"], r["class_label"], r["record_id"]): REPO / r["afe_adc_mem_file"] for r in manifest_rows}
    mem_dir = out_dir / "windows"
    if mem_dir.exists():
        shutil.rmtree(mem_dir)
    mem_dir.mkdir(parents=True, exist_ok=True)
    for case_id, row in enumerate(selection):
        src = fullrec_path[(row["split"], row["true_record_class"], row["record_id"])]
        start = int(float(row["start_sample"]))
        name = f"case{case_id:04d}_{row['split']}_{row['true_record_class']}_{safe_id(row['record_id'])}_w{int(float(row['window_id'])):05d}.mem"
        dst = mem_dir / name
        with src.open("rb") as fin, dst.open("wb") as fout:
            fin.seek(start * 4)
            data = fin.read(WINDOW_SAMPLES * 4)
            if len(data) != WINDOW_SAMPLES * 4:
                raise ValueError(f"short window read: {src} start={start} bytes={len(data)}")
            fout.write(data)
        row["case_id"] = str(case_id)
        row["window_mem_file"] = str(dst)


def write_xsim_inputs(selection: list[dict[str, str]], out_dir: Path) -> tuple[Path, Path, Path]:
    write_csv(out_dir / "selected_windows.csv", selection)
    manifest = out_dir / "xsim_manifest.txt"
    with manifest.open("w", encoding="utf-8", newline="\n") as f:
        for row in selection:
            label = row["true_record_class"]
            f.write(f"{CLASS_TO_ID[label]} {label} {WINDOW_SAMPLES} {slash(Path(row['window_mem_file']))}\n")

    work = out_dir / "xsim_work"
    work.mkdir(parents=True, exist_ok=True)
    tb = work / "tb_snn_ecg_3feat_dataset_c24dump.v"
    text = BASE_TB.read_text(encoding="utf-8")
    text = text.replace("module tb_snn_ecg_3feat_dataset;", "module tb_snn_ecg_3feat_dataset_c24dump;")
    text = text.replace(
        "score_arr_before_eerg,mem_file",
        "score_arr_before_eerg,c24_mem_NSR,c24_mem_CHF,c24_mem_ARR,c24_mem_AFF,mem_file",
    )
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "$fdisplay(result_fd" in line and "%0d,%0s" in line and line.rstrip().endswith('",'):
            prefix, suffix = line.rsplit(",%0s", 1)
            lines[i] = prefix + ",%0d,%0d,%0d,%0d,%0s" + suffix
            break
    text = "\n".join(lines) + "\n"
    text = text.replace(
        "score_arr_before_eerg,\n                          path);",
        "score_arr_before_eerg,\n                          dut.u_class.c24_mem_nsr, dut.u_class.c24_mem_chf,\n                          dut.u_class.c24_mem_arr, dut.u_class.c24_mem_aff,\n                          path);",
    )
    tb.write_text(text, encoding="utf-8", newline="\n")

    wrapper = work / "tb_python_rtl_equivalence.v"
    result_csv = out_dir / "rtl_xsim_window_dump.csv"
    subwindow_csv = out_dir / "rtl_xsim_subwindow_dump.csv"
    wrapper.write_text(
        f"""`timescale 1ns/1ps

module tb_python_rtl_equivalence;
    tb_snn_ecg_3feat_dataset_c24dump #(
        .MAX_SAMPLES({WINDOW_SAMPLES}),
        .MANIFEST_FILE("{slash(manifest)}"),
        .WRITE_CASE_CSV(1),
        .RESULT_CSV("{slash(result_csv)}"),
        .WRITE_SUBWINDOW_CSV(0),
        .SUBWINDOW_CSV("{slash(subwindow_csv)}"),
        .MANIFEST_HAS_SAMPLE_COUNT(1),
        .ENABLE_INPUT_NORMALIZER(0)
    ) tb();
endmodule
""",
        encoding="utf-8",
        newline="\n",
    )
    return work, tb, wrapper


def run(cmd: list[str], cwd: Path, log_path: Path) -> None:
    print("$ " + " ".join(cmd), flush=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]
        raise SystemExit(f"command failed: {' '.join(cmd)}\nlog={log_path}\n" + "\n".join(tail))


def run_xsim(work: Path, tb: Path, wrapper: Path, out_dir: Path) -> None:
    for tool in [XVLOG, XELAB, XSIM]:
        if not tool.exists():
            raise FileNotFoundError(tool)
    prj = work / "sources.prj"
    lines = [f'verilog work "{slash(SIM_SRC / source)}"' for source in SOURCES]
    lines.append(f'verilog work "{slash(tb)}"')
    lines.append(f'verilog work "{slash(wrapper)}"')
    prj.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    tcl = work / "run.tcl"
    tcl.write_text("run all\nquit\n", encoding="utf-8", newline="\n")
    run([str(XVLOG), "--nolog", "-prj", slash(prj)], work, out_dir / "xvlog.log")
    run([str(XELAB), "--nolog", "-debug", "typical", "tb_python_rtl_equivalence", "-s", "tb_python_rtl_equivalence_behav"], work, out_dir / "xelab.log")
    run([str(XSIM), "tb_python_rtl_equivalence_behav", "--nolog", "-tclbatch", slash(tcl)], work, out_dir / "xsim.log")


def python_dump(selection: list[dict[str, str]], out_dir: Path) -> list[dict[str, int | str]]:
    rows = []
    for row in selection:
        feat = run_qrs_on_mem(Path(row["window_mem_file"]))
        out = {
            "case_id": row["case_id"],
            "split": row["split"],
            "record_id": row["record_id"],
            "window_id": row["window_id"],
            "true_class": row["true_record_class"],
            "expected_class": row["true_class_id"],
            "pred_class": int(feat["pred_class"]),
            "pred_valid": int(feat["pred_valid"]),
            "class_mem_NSR": int(feat["class_mem_NSR"]),
            "class_mem_CHF": int(feat["class_mem_CHF"]),
            "class_mem_ARR": int(feat["class_mem_ARR"]),
            "class_mem_AFF": int(feat["class_mem_AFF"]),
            "mem_file": row["window_mem_file"],
        }
        for col in FEATURE_COLUMNS:
            out[col] = int(feat.get(col, 0))
        rows.append(out)
    write_csv(out_dir / "python_window_dump.csv", rows)
    return rows


def to_int(row: dict[str, str | int], key: str) -> int:
    value = row.get(key, 0)
    if value in ("", None):
        return 0
    return int(float(value))


def compare_outputs(selection: list[dict[str, str]], py_rows: list[dict[str, int | str]], out_dir: Path) -> None:
    rtl_rows = read_csv(out_dir / "rtl_xsim_window_dump.csv")
    selected_by_case = {int(row["case_id"]): row for row in selection}
    py_by_case = {int(row["case_id"]): row for row in py_rows}
    rtl_by_case = {int(row["case_id"]): row for row in rtl_rows}
    compare_rows = []
    field_stats: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"compared": 0, "mismatches": 0, "max_abs_diff": 0})

    def update(stage: str, field: str, diff: int) -> None:
        stat = field_stats[(stage, field)]
        stat["compared"] += 1
        if diff != 0:
            stat["mismatches"] += 1
            stat["max_abs_diff"] = max(stat["max_abs_diff"], abs(diff))

    for case_id in sorted(py_by_case):
        sel = selected_by_case[case_id]
        py = py_by_case[case_id]
        rtl = rtl_by_case[case_id]
        row: dict[str, int | str] = {
            "case_id": case_id,
            "split": sel["split"],
            "record_id": sel["record_id"],
            "window_id": sel["window_id"],
            "true_class": sel["true_record_class"],
            "selection_tags": sel["selection_tags"],
            "mem_file": sel["window_mem_file"],
        }
        first_stage = "PASS"
        feature_mismatch = 0
        qrs_diff = to_int(py, "beat_count") - to_int(rtl, "beat_count")
        update("A_QRS_detector", "beat_count", qrs_diff)
        row["py_qrs_count"] = to_int(py, "beat_count")
        row["rtl_qrs_count"] = to_int(rtl, "beat_count")
        row["qrs_count_diff"] = qrs_diff
        if qrs_diff:
            first_stage = "A_QRS_detector"
        for col in FEATURE_COLUMNS:
            py_v = to_int(py, col)
            rtl_v = to_int(rtl, col)
            diff = py_v - rtl_v
            if col != "beat_count":
                update("B_feature_layer", col, diff)
            row[f"py_{col}"] = py_v
            row[f"rtl_{col}"] = rtl_v
            row[f"diff_{col}"] = diff
            if diff:
                feature_mismatch = 1
        if first_stage == "PASS" and feature_mismatch:
            first_stage = "B_feature_layer"

        mem_mismatch = 0
        for py_col, rtl_col, cls in zip(MEM_COLUMNS, RTL_MEM_COLUMNS, CLASSES):
            py_v = to_int(py, py_col)
            rtl_v = to_int(rtl, rtl_col)
            diff = py_v - rtl_v
            update("C_snapshot_readout", f"class_mem_{cls}", diff)
            row[f"py_class_mem_{cls}"] = py_v
            row[f"rtl_class_mem_{cls}"] = rtl_v
            row[f"diff_class_mem_{cls}"] = diff
            if diff:
                mem_mismatch = 1
        py_pred = to_int(py, "pred_class")
        rtl_pred = to_int(rtl, "pred_class")
        pred_diff = py_pred - rtl_pred
        update("C_snapshot_readout", "pred_class", pred_diff)
        row["py_pred_class"] = py_pred
        row["rtl_pred_class"] = rtl_pred
        row["pred_class_mismatch"] = int(pred_diff != 0)
        row["class_mem_mismatch"] = mem_mismatch
        if first_stage == "PASS" and (mem_mismatch or pred_diff):
            first_stage = "C_snapshot_readout"
        row["first_mismatch_stage"] = first_stage
        row["complete_match"] = int(first_stage == "PASS")
        row["final_layer_compared"] = 0
        row["final_layer_note"] = "no RTL patient final layer implementation in current repo"
        compare_rows.append(row)

    write_csv(out_dir / "python_rtl_equivalence_window_compare.csv", compare_rows)

    summary_rows = []
    for (stage, field), stat in sorted(field_stats.items()):
        compared = stat["compared"]
        mismatches = stat["mismatches"]
        summary_rows.append(
            {
                "stage": stage,
                "field": field,
                "compared": compared,
                "mismatches": mismatches,
                "mismatch_rate": mismatches / compared if compared else 0.0,
                "max_abs_diff": stat["max_abs_diff"],
            }
        )
    summary_rows.append(
        {
            "stage": "D_patient_final_layer",
            "field": "patient_mem_and_patient_pred",
            "compared": 0,
            "mismatches": "",
            "mismatch_rate": "",
            "max_abs_diff": "",
            "note": "not compared: current repo has Python final layer only, no RTL patient final layer",
        }
    )
    write_csv(out_dir / "stage_mismatch_summary.csv", summary_rows)
    write_report(compare_rows, summary_rows, out_dir)


def write_report(compare_rows: list[dict[str, int | str]], summary_rows: list[dict[str, int | float | str]], out_dir: Path) -> None:
    total = len(compare_rows)
    complete = sum(int(r["complete_match"]) for r in compare_rows)
    pred_mis = sum(int(r["pred_class_mismatch"]) for r in compare_rows)
    mem_mis = sum(int(r["class_mem_mismatch"]) for r in compare_rows)
    stage_counts = Counter(str(r["first_mismatch_stage"]) for r in compare_rows)
    feature_mismatch_fields = [
        r for r in summary_rows
        if r.get("stage") == "B_feature_layer" and int(r.get("mismatches") or 0) > 0
    ]
    lines = [
        "# Python vs RTL/XSim Equivalence Report",
        "",
        "## Scope",
        "",
        "- Snapshot C24 RTL parameters and Python final-layer parameters were kept fixed.",
        "- The compared Python path is `scripts/snapshot_c24_rtl_exact.py`, which translates the RTL event/front-end, feature, RBBB/EERG gate, and C24 readout state machines directly.",
        "- XSim used the current synthesizable RTL and a generated dump testbench that also exposes internal `dut.u_class.c24_mem_*` registers.",
        "- The patient-level final layer is not implemented in RTL in the current repo, so stage D cannot be bit-exact compared yet.",
        "",
        "## Summary",
        "",
        f"- compared windows: {total}",
        f"- completely matching windows: {complete}",
        f"- pred_class mismatches: {pred_mis}",
        f"- class_mem mismatching windows: {mem_mis}",
        "",
        "## First Mismatch Stage",
        "",
        "| stage | windows |",
        "|---|---:|",
    ]
    for stage, count in sorted(stage_counts.items()):
        lines.append(f"| {stage} | {count} |")
    lines += [
        "",
        "## Feature Mismatch Fields",
        "",
        "| field | mismatches | compared | max abs diff |",
        "|---|---:|---:|---:|",
    ]
    for r in feature_mismatch_fields[:80]:
        lines.append(f"| {r['field']} | {r['mismatches']} | {r['compared']} | {r['max_abs_diff']} |")
    if not feature_mismatch_fields:
        lines.append("| none | 0 | 0 | 0 |")
    lines += [
        "",
        "## Conclusion",
        "",
    ]
    if complete == total and total > 0:
        lines.append("The Python model is bit-exact with RTL for the compared Snapshot C24 windows.")
    else:
        lines.append("The Python Snapshot C24 model is not fully bit-exact for the compared windows. See the first mismatch stage and field table above.")
        lines.append("")
        lines.append("Any nonzero mismatch should be treated as a model/RTL translation bug before using this Python path for downstream patient-layer exploration.")
    lines.append("")
    lines.append("Stage D remains unverified because there is no patient-level final-layer RTL module in this repo yet.")
    (out_dir / "python_rtl_equivalence_mismatch_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--skip-xsim", action="store_true")
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.skip_xsim and (RESULTS / "selected_windows.csv").exists():
        selection = read_csv(RESULTS / "selected_windows.csv")
        work = RESULTS / "xsim_work"
        tb = work / "tb_snn_ecg_3feat_dataset_c24dump.v"
        wrapper = work / "tb_python_rtl_equivalence.v"
    else:
        rows = load_window_rows()
        selection = select_windows(rows, args.count)
        copy_window_mem(selection, RESULTS)
        work, tb, wrapper = write_xsim_inputs(selection, RESULTS)
    if not args.skip_xsim:
        run_xsim(work, tb, wrapper, RESULTS)
    py_rows = python_dump(selection, RESULTS)
    if (RESULTS / "rtl_xsim_window_dump.csv").exists():
        compare_outputs(selection, py_rows, RESULTS)
    print(f"[done] compared {len(selection)} windows -> {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
