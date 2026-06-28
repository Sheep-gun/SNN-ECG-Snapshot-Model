from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "final_membrane_30min"
SELECTED = RESULTS / "final_layer_selected_params.json"
RTL_OUT = REPO / "rtl" / "final_membrane_layer.v"

CLASSES = ["NSR", "CHF", "ARR", "AFF"]
LOWER = ["nsr", "chf", "arr", "aff"]


def v_signed(width: int, value: int) -> str:
    value = int(value)
    if value < 0:
        return f"-{width}'sd{abs(value)}"
    return f"{width}'sd{value}"


def shift_add_expr(name: str, const: int) -> str:
    const = int(const)
    if const == 0:
        return "32'd0"
    terms = []
    bit = 0
    while const:
        if const & 1:
            terms.append(name if bit == 0 else f"({name} << {bit})")
        const >>= 1
        bit += 1
    return " + ".join(terms)


def ratio_ge_v(num: str, den: str, pct: int) -> str:
    return f"(({den} != 32'd0) && (({shift_add_expr(num, 100)}) >= ({shift_add_expr(den, pct)})))"


def avg_ge_v(total: str, den: str, threshold: int) -> str:
    return f"(({den} != 32'd0) && ({total} >= ({shift_add_expr(den, threshold)})))"


def top_condition_v(cls: int) -> str:
    names = ["class_mem_nsr", "class_mem_chf", "class_mem_arr", "class_mem_aff"]
    parts = []
    for other, name in enumerate(names):
        if other == cls:
            continue
        op = ">=" if cls < other else ">"
        parts.append(f"({names[cls]} {op} {name})")
    return " && ".join(parts)


def max_other_expr(cls: int) -> str:
    names = ["class_mem_nsr", "class_mem_chf", "class_mem_arr", "class_mem_aff"]
    others = [names[i] for i in range(4) if i != cls]
    expr = others[0]
    for name in others[1:]:
        expr = f"(({expr} >= {name}) ? {expr} : {name})"
    return expr


def custom_cond_v(name: str) -> str:
    mis12 = ratio_ge_v("pnn_mismatch_count", "pnn_decision_count", 12)
    mis25 = ratio_ge_v("pnn_mismatch_count", "pnn_decision_count", 25)
    rdm15 = ratio_ge_v("rdm_ge50_count", "rdm_valid_count", 15)
    rdm30 = ratio_ge_v("rdm_ge50_count", "rdm_valid_count", 30)
    if name == "nsr_stability_strict":
        return "((pred_valid && (pred_class == 2'd0)) && (pnn_mismatch_count <= 32'd1) && (ectopic_pair_count == 32'd0) && (qrs_maf_count <= 32'd1) && (rbbb_delay_like_count == 32'd0))"
    if name == "nsr_stability_soft":
        return "((pred_valid && (pred_class == 2'd0)) && (pnn_mismatch_count <= 32'd5) && (ectopic_pair_count <= 32'd1) && (qrs_maf_count <= 32'd3))"
    if name == "arr_burst_strong":
        return "(((pnn_mismatch_count >= 32'd12) && (ectopic_pair_count >= 32'd3)) || (qrs_maf_count >= 32'd18))"
    if name == "arr_episodic_soft":
        return "((pred_valid && (pred_class == 2'd2)) && ((pnn_mismatch_count >= 32'd5) || (qrs_maf_count >= 32'd8) || (ectopic_pair_count >= 32'd3)))"
    if name == "aff_irregular_persistent":
        return f"(({mis25}) && ({rdm30}))"
    if name == "aff_irregular_soft":
        return f"((pred_valid && (pred_class == 2'd3)) && (({mis12}) || ({rdm15})))"
    if name == "chf_morphology_low_irreg":
        return "((pred_valid && (pred_class == 2'd1)) && (pnn_mismatch_count <= 32'd8) && (qrs_maf_count <= 32'd8))"
    if name == "abnormal_priority_any":
        return "((pnn_mismatch_count >= 32'd5) || (ectopic_pair_count >= 32'd3) || (qrs_maf_count >= 32'd5) || (rbbb_delay_like_count >= 32'd3))"
    if name == "abnormal_priority_strong":
        return "((pnn_mismatch_count >= 32'd15) || (ectopic_pair_count >= 32'd8) || (qrs_maf_count >= 32'd15) || (rbbb_delay_like_count >= 32'd8))"
    raise ValueError(f"unsupported custom condition: {name}")


def cond_expr_v(spec: dict) -> str | None:
    kind = spec["kind"]
    if kind == "bias" or kind.startswith("chunk_"):
        return None
    if kind == "pred_eq":
        return f"(pred_valid && (pred_class == 2'd{int(spec['class'])}))"
    if kind == "top_eq":
        return f"({top_condition_v(int(spec['class']))})"
    if kind == "top_margin_ge":
        cls = int(spec["class"])
        mem = ["class_mem_nsr", "class_mem_chf", "class_mem_arr", "class_mem_aff"][cls]
        return f"(({top_condition_v(cls)}) && (({mem} - {max_other_expr(cls)}) >= {v_signed(64, int(spec['threshold']))}))"
    if kind == "mem_ge":
        mem = ["class_mem_nsr", "class_mem_chf", "class_mem_arr", "class_mem_aff"][int(spec["class"])]
        return f"({mem} >= {v_signed(64, int(spec['threshold']))})"
    if kind == "count_ge":
        return f"({spec['field']} >= 32'd{int(spec['threshold'])})"
    if kind == "count_le":
        return f"({spec['field']} <= 32'd{int(spec['threshold'])})"
    if kind == "ratio_ge":
        return ratio_ge_v(spec["num"], spec["den"], int(spec["pct"]))
    if kind == "avg_ge":
        return avg_ge_v(spec["sum"], spec["den"], int(spec["threshold"]))
    if kind == "custom":
        return f"custom_{spec['custom']}"
    raise ValueError(f"unsupported spec kind: {kind}")


def chunk_cond_expr_v(spec: dict) -> str | None:
    kind = spec["kind"]
    if kind == "chunk_pred_count_ge":
        return f"(pred_count_{LOWER[int(spec['class'])]}_next >= 6'd{int(spec['threshold'])})"
    if kind == "chunk_top_count_ge":
        return f"(top_count_{LOWER[int(spec['class'])]}_next >= 6'd{int(spec['threshold'])})"
    if kind == "chunk_custom_count_ge":
        return f"(custom_count_{spec['custom']}_next >= 6'd{int(spec['threshold'])})"
    return None


def rtl_input_fields(specs: list[dict]) -> list[str]:
    fields: list[str] = []

    def add(name: str) -> None:
        if name not in fields:
            fields.append(name)

    for spec in specs:
        kind = spec["kind"]
        if kind in ("count_ge", "count_le"):
            add(spec["field"])
        elif kind == "ratio_ge":
            add(spec["num"])
            add(spec["den"])
        elif kind == "avg_ge":
            add(spec["sum"])
            add(spec["den"])
    for name in [
        "pnn_mismatch_count",
        "pnn_decision_count",
        "rdm_ge50_count",
        "rdm_valid_count",
        "ectopic_pair_count",
        "qrs_maf_count",
        "rbbb_delay_like_count",
    ]:
        add(name)
    return fields


def add_weight_lines(lines: list[str], weights: list[list[int]], idx: int, indent: str = "                ") -> None:
    targets = ["m_nsr", "m_chf", "m_arr", "m_aff"]
    for cls in range(4):
        weight = int(weights[cls][idx])
        if weight:
            lines.append(f"{indent}{targets[cls]} = {targets[cls]} + {v_signed(32, weight)};")


def main() -> None:
    selected = json.loads(SELECTED.read_text(encoding="utf-8"))
    specs = selected["feature_specs"]
    weights = [[int(v) for v in selected["weights_by_class"][cls]] for cls in CLASSES]
    fields = rtl_input_fields(specs)
    custom_names = sorted({spec["custom"] for spec in specs if spec["kind"] in ("custom", "chunk_custom_count_ge")})

    lines: list[str] = []
    lines.extend(
        [
            "`timescale 1ns / 1ps",
            "",
            "// Auto-generated from results/final_membrane_30min/final_layer_selected_params.json.",
            "// Snapshot C24 is fixed; this module accumulates 30 snapshot evidence events.",
            "module final_membrane_layer(",
            "    input clk,",
            "    input rst,",
            "    input clear,",
            "    input snapshot_done,",
            "    input chunk_done,",
            "    input pred_valid,",
            "    input [1:0] pred_class,",
            "    input signed [63:0] class_mem_nsr,",
            "    input signed [63:0] class_mem_chf,",
            "    input signed [63:0] class_mem_arr,",
            "    input signed [63:0] class_mem_aff,",
        ]
    )
    for field in fields:
        lines.append(f"    input [31:0] {field},")
    lines.extend(
        [
            "    output reg final_valid,",
            "    output reg [1:0] final_pred_class,",
            "    output reg signed [31:0] final_mem_nsr,",
            "    output reg signed [31:0] final_mem_chf,",
            "    output reg signed [31:0] final_mem_arr,",
            "    output reg signed [31:0] final_mem_aff",
            ");",
            "",
            "    reg signed [31:0] m_nsr;",
            "    reg signed [31:0] m_chf;",
            "    reg signed [31:0] m_arr;",
            "    reg signed [31:0] m_aff;",
            "    reg signed [31:0] best_score;",
            "    reg [1:0] best_class;",
            "    reg [5:0] snapshot_count;",
            "    reg [5:0] snapshot_count_next;",
        ]
    )
    for name in LOWER:
        lines.append(f"    reg [5:0] pred_count_{name};")
        lines.append(f"    reg [5:0] pred_count_{name}_next;")
        lines.append(f"    reg [5:0] top_count_{name};")
        lines.append(f"    reg [5:0] top_count_{name}_next;")
    for name in custom_names:
        lines.append(f"    reg [5:0] custom_count_{name};")
        lines.append(f"    reg [5:0] custom_count_{name}_next;")
    lines.append("")
    for cls, name in enumerate(LOWER):
        lines.append(f"    wire top_is_{name} = {top_condition_v(cls)};")
    for name in custom_names:
        lines.append(f"    wire custom_{name} = {custom_cond_v(name)};")

    lines.extend(
        [
            "",
            "    always @(*) begin",
            "        m_nsr = final_mem_nsr;",
            "        m_chf = final_mem_chf;",
            "        m_arr = final_mem_arr;",
            "        m_aff = final_mem_aff;",
            "        snapshot_count_next = snapshot_count + 6'd1;",
        ]
    )
    for cls, name in enumerate(LOWER):
        lines.append(f"        pred_count_{name}_next = pred_count_{name} + ((pred_valid && (pred_class == 2'd{cls})) ? 6'd1 : 6'd0);")
        lines.append(f"        top_count_{name}_next = top_count_{name} + (top_is_{name} ? 6'd1 : 6'd0);")
    for name in custom_names:
        lines.append(f"        custom_count_{name}_next = custom_count_{name} + (custom_{name} ? 6'd1 : 6'd0);")

    lines.append("")
    lines.append("        if (snapshot_done) begin")
    for idx, spec in enumerate(specs):
        cond = cond_expr_v(spec)
        if cond is None:
            continue
        if not any(int(weights[cls][idx]) for cls in range(4)):
            continue
        lines.append(f"            if ({cond}) begin // {spec['name']}")
        add_weight_lines(lines, weights, idx)
        lines.append("            end")
    lines.append("")
    lines.append("            if (chunk_done) begin")
    for idx, spec in enumerate(specs):
        cond = chunk_cond_expr_v(spec)
        if cond is None:
            continue
        if not any(int(weights[cls][idx]) for cls in range(4)):
            continue
        lines.append(f"                if ({cond}) begin // {spec['name']}")
        add_weight_lines(lines, weights, idx, indent="                    ")
        lines.append("                end")
    lines.append("            end")
    lines.append("        end")
    lines.append("    end")

    lines.extend(
        [
            "",
            "    always @(posedge clk) begin",
            "        if (rst || clear) begin",
            f"            final_mem_nsr <= {v_signed(32, weights[0][0])};",
            f"            final_mem_chf <= {v_signed(32, weights[1][0])};",
            f"            final_mem_arr <= {v_signed(32, weights[2][0])};",
            f"            final_mem_aff <= {v_signed(32, weights[3][0])};",
            "            final_valid <= 1'b0;",
            "            final_pred_class <= 2'd0;",
            "            snapshot_count <= 6'd0;",
        ]
    )
    for name in LOWER:
        lines.append(f"            pred_count_{name} <= 6'd0;")
        lines.append(f"            top_count_{name} <= 6'd0;")
    for name in custom_names:
        lines.append(f"            custom_count_{name} <= 6'd0;")
    lines.extend(
        [
            "        end else begin",
            "            final_valid <= 1'b0;",
            "            if (snapshot_done) begin",
            "                final_mem_nsr <= m_nsr;",
            "                final_mem_chf <= m_chf;",
            "                final_mem_arr <= m_arr;",
            "                final_mem_aff <= m_aff;",
            "                if (chunk_done) begin",
            "                    snapshot_count <= 6'd0;",
        ]
    )
    for name in LOWER:
        lines.append(f"                    pred_count_{name} <= 6'd0;")
        lines.append(f"                    top_count_{name} <= 6'd0;")
    for name in custom_names:
        lines.append(f"                    custom_count_{name} <= 6'd0;")
    lines.extend(
        [
            "                    best_score = m_nsr;",
            "                    best_class = 2'd0;",
            "                    if (m_chf > best_score) begin best_score = m_chf; best_class = 2'd1; end",
            "                    if (m_arr > best_score) begin best_score = m_arr; best_class = 2'd2; end",
            "                    if (m_aff > best_score) begin best_score = m_aff; best_class = 2'd3; end",
            "                    final_pred_class <= best_class;",
            "                    final_valid <= 1'b1;",
            "                end else begin",
            "                    snapshot_count <= snapshot_count_next;",
        ]
    )
    for name in LOWER:
        lines.append(f"                    pred_count_{name} <= pred_count_{name}_next;")
        lines.append(f"                    top_count_{name} <= top_count_{name}_next;")
    for name in custom_names:
        lines.append(f"                    custom_count_{name} <= custom_count_{name}_next;")
    lines.extend(
        [
            "                end",
            "            end",
            "        end",
            "    end",
            "",
            "endmodule",
            "",
        ]
    )

    RTL_OUT.parent.mkdir(parents=True, exist_ok=True)
    RTL_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {RTL_OUT}")


if __name__ == "__main__":
    main()
