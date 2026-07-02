from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "final_membrane_v2_snn"
SYNTH = RESULTS / "vivado_snn_ecg_v2"
VIVADO = Path(r"C:\Xilinx\Vivado\2020.2\bin\vivado.bat")

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


def write_tcl() -> Path:
    SYNTH.mkdir(parents=True, exist_ok=True)
    proj_dir = SYNTH / "project"
    report_dir = SYNTH / "reports"
    bit_dir = SYNTH / "bitstream"
    tcl = SYNTH / "build_snn_ecg_v2_bitstream.tcl"
    rtl_files = [f"rtl/core/{src}" for src in CORE_SOURCES]
    rtl_files.extend(
        [
            "rtl/final_membrane_layer.v",
            "rtl/snn_ecg_30min_final_top.v",
            "rtl/board/snn_ecg_v2_nexys_a7_top.v",
        ]
    )
    file_list = " \\\n    ".join(f'"{path}"' for path in rtl_files)
    tcl.write_text(
        f"""set repo_dir "{slash(REPO)}"
set proj_dir "{slash(proj_dir)}"
set report_dir "{slash(report_dir)}"
set bit_dir "{slash(bit_dir)}"
file mkdir $report_dir
file mkdir $bit_dir

create_project -force SNN_ECG_V2 $proj_dir -part xc7a100tcsg324-1
cd $repo_dir

set rtl_files [list \\
    {file_list} \\
]

add_files -fileset sources_1 $rtl_files
add_files -fileset constrs_1 "constraints/nexys_a7_snn_ecg_v2.xdc"
set_property top snn_ecg_v2_nexys_a7_top [current_fileset]
update_compile_order -fileset sources_1

launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {{[get_property STATUS [get_runs synth_1]] != "synth_design Complete!"}} {{
    error "synth_1 failed: [get_property STATUS [get_runs synth_1]]"
}}
open_run synth_1
report_utilization -file "$report_dir/snn_ecg_v2_synth_utilization.rpt"
report_utilization -hierarchical -file "$report_dir/snn_ecg_v2_synth_utilization_hier.rpt"

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {{[get_property PROGRESS [get_runs impl_1]] != "100%"}} {{
    error "impl_1 did not complete"
}}
open_run impl_1
report_utilization -file "$report_dir/snn_ecg_v2_impl_utilization.rpt"
report_utilization -hierarchical -file "$report_dir/snn_ecg_v2_impl_utilization_hier.rpt"
report_timing_summary -file "$report_dir/snn_ecg_v2_timing_summary.rpt"
report_power -file "$report_dir/snn_ecg_v2_power.rpt"
write_checkpoint -force "$report_dir/snn_ecg_v2_impl.dcp"

set bit_file "$proj_dir/SNN_ECG_V2.runs/impl_1/snn_ecg_v2_nexys_a7_top.bit"
if {{![file exists $bit_file]}} {{
    error "Bitstream not found: $bit_file"
}}
file copy -force $bit_file "$bit_dir/snn_ecg_v2_nexys_a7_top.bit"
puts "BITSTREAM=$bit_dir/snn_ecg_v2_nexys_a7_top.bit"
exit
""",
        encoding="utf-8",
        newline="\n",
    )
    return tcl


def run_vivado(tcl: Path) -> None:
    log = SYNTH / "vivado_snn_ecg_v2_build.log"
    with log.open("w", encoding="utf-8", errors="replace") as f:
        proc = subprocess.run(
            [str(VIVADO), "-mode", "batch", "-source", slash(tcl)],
            cwd=REPO,
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"Vivado failed with code {proc.returncode}; see {log}")


def parse_util(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, str] = {}
    patterns = {
        "slice_lut": r"\|\s*Slice LUTs\s*\|\s*([0-9]+)",
        "slice_reg": r"\|\s*Slice Registers\s*\|\s*([0-9]+)",
        "ff": r"\|\s*Register as Flip Flop\s*\|\s*([0-9]+)",
        "bram_tile": r"\|\s*Block RAM Tile\s*\|\s*([0-9.]+)",
        "dsp": r"\|\s*DSPs\s*\|\s*([0-9]+)",
        "uram": r"\|\s*URAM\s*\|\s*([0-9]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            out[key] = match.group(1)
    return out


def parse_power(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, str] = {}
    for key, pattern in {
        "total_on_chip_power_w": r"Total On-Chip Power \(W\)\s*\|\s*([0-9.]+)",
        "dynamic_power_w": r"Dynamic \(W\)\s*\|\s*([0-9.]+)",
        "device_static_power_w": r"Device Static \(W\)\s*\|\s*([0-9.]+)",
    }.items():
        match = re.search(pattern, text)
        if match:
            out[key] = match.group(1)
    return out


def write_summary() -> None:
    report_dir = SYNTH / "reports"
    bit = SYNTH / "bitstream" / "snn_ecg_v2_nexys_a7_top.bit"
    util = parse_util(report_dir / "snn_ecg_v2_impl_utilization.rpt")
    power = parse_power(report_dir / "snn_ecg_v2_power.rpt")
    summary = {
        "top": "snn_ecg_v2_nexys_a7_top",
        "part": "xc7a100tcsg324-1",
        "bitstream": str(bit),
        "bitstream_exists": bit.exists(),
        "utilization": util,
        "power": power,
        "reports": {
            "utilization": str(report_dir / "snn_ecg_v2_impl_utilization.rpt"),
            "utilization_hier": str(report_dir / "snn_ecg_v2_impl_utilization_hier.rpt"),
            "timing": str(report_dir / "snn_ecg_v2_timing_summary.rpt"),
            "power": str(report_dir / "snn_ecg_v2_power.rpt"),
        },
    }
    (SYNTH / "snn_ecg_v2_vivado_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        "# SNN ECG V2 Vivado Resource Report",
        "",
        f"Top: `{summary['top']}`",
        f"Part: `{summary['part']}`",
        f"Bitstream: `{summary['bitstream']}`",
        "",
        "| Resource | Used |",
        "|---|---:|",
    ]
    for key in ["slice_lut", "slice_reg", "ff", "bram_tile", "dsp", "uram"]:
        if key in util:
            lines.append(f"| {key} | {util[key]} |")
    if power:
        lines.extend(["", "| Power | W |", "|---|---:|"])
        for key, value in power.items():
            lines.append(f"| {key} | {value} |")
    (SYNTH / "snn_ecg_v2_vivado_resource_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    tcl = write_tcl()
    run_vivado(tcl)
    write_summary()
    print(SYNTH / "snn_ecg_v2_vivado_summary.json")


if __name__ == "__main__":
    main()
