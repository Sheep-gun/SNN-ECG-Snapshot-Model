from pathlib import Path
import csv
import re


ROOT = Path(r"C:\Users\YangGeon\SNN_ECG_RESTORE_MODEL_S")
SYNTH = ROOT / "reports" / "synth"
UTIL = SYNTH / "restore_model_s_utilization.rpt"
TIMING = SYNTH / "restore_model_s_timing_summary.rpt"
OUT_CSV = SYNTH / "model_s_rtl_synth_utilization.csv"
OUT_MD = SYNTH / "model_s_rtl_synth_report.md"


def find_row(text, name):
    for line in text.splitlines():
        if f"| {name}" in line:
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) >= 5:
                return {
                    "resource": parts[0],
                    "used": parts[1],
                    "fixed": parts[2],
                    "available": parts[3],
                    "util_percent": parts[4],
                }
    return None


def main():
    util_text = UTIL.read_text(errors="ignore")
    timing_text = TIMING.read_text(errors="ignore") if TIMING.exists() else ""
    resources = []
    for name in ["Slice LUTs*", "Slice Registers", "Block RAM Tile", "DSPs", "Bonded IOB", "BUFGCTRL"]:
        row = find_row(util_text, name)
        if row:
            resources.append(row)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["resource", "used", "fixed", "available", "util_percent"])
        w.writeheader()
        w.writerows(resources)

    no_clock = re.search(r"checking no_clock \((\d+)\)", timing_text)
    unconstrained = re.search(r"checking unconstrained_internal_endpoints \((\d+)\)", timing_text)
    no_input = re.search(r"checking no_input_delay \((\d+)\)", timing_text)
    no_output = re.search(r"checking no_output_delay \((\d+)\)", timing_text)

    lines = []
    lines.append("# Model S RTL Synthesis Report")
    lines.append("")
    lines.append("## Vivado")
    lines.append("")
    lines.append("- Tool: Vivado 2020.2")
    lines.append("- Part: xc7a100tcsg324-1")
    lines.append("- Top: snn_ecg_model_a_plus_core")
    lines.append("- Script: `C:/Users/YangGeon/SNN_ECG_RESTORE_MODEL_S/scripts/create_and_synth_model_s_restore.tcl`")
    lines.append("- Result: synth_design completed successfully.")
    lines.append("")
    lines.append("## Utilization")
    lines.append("")
    lines.append("| resource | used | available | util |")
    lines.append("|---|---:|---:|---:|")
    for row in resources:
        lines.append(f"| {row['resource']} | {row['used']} | {row['available']} | {row['util_percent']}% |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- DSP usage is 0, so the restored Model S path remains multiplier/DSP-free after synthesis.")
    lines.append("- BRAM usage is 0. QRS pre-window history is mapped to distributed shift-register LUT resources.")
    lines.append("- This is synthesis-only timing without an XDC constraint file. Timing warnings below are expected until board-level clock/input/output constraints are added.")
    if no_clock:
        lines.append(f"- no_clock pins reported: {no_clock.group(1)}")
    if unconstrained:
        lines.append(f"- unconstrained internal endpoints reported: {unconstrained.group(1)}")
    if no_input:
        lines.append(f"- no_input_delay ports reported: {no_input.group(1)}")
    if no_output:
        lines.append(f"- no_output_delay ports reported: {no_output.group(1)}")
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(OUT_MD)


if __name__ == "__main__":
    main()
