from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
from itertools import combinations
from collections import Counter
from pathlib import Path
from typing import Any

from snapshot_c24_rtl_exact import CLASSES, C24ScoreNeurons, SnapshotFrontEnd, _CLASS_CONSTS, s12_from_hex_mem


REPO = Path(__file__).resolve().parents[1]
DATASET = REPO / "60s_afe_datasets" / "afe_output_xmodelmatch_curated_v2_128_64_64_balanced"
OUT = REPO / "results" / "snapshot_c24_v2_search"

FEATURE_COLUMNS = [
    "beat_count",
    "pnn_match_count",
    "pnn_mismatch_count",
    "rdm_valid_count",
    "rdm_code_sum",
    "dscr_slope_count",
    "dscr_flip_count",
    "ram_code_count",
    "ram_code_sum",
    "ectopic_pair_count",
    "qrs_maf_valid_count",
    "qrs_maf_count",
    "qrs_width_abn_count",
    "qrs_complex_abn_count",
    "qrs_energy_abn_count",
    "pre_qrs_bump_count",
    "rbbb_delay_valid_count",
    "rbbb_delay_wide_count",
    "rbbb_delay_terminal_count",
    "rbbb_delay_like_count",
    "rbbb_delay_segment_count",
    "rbbb_delay_applied_count",
    "eerg_gate_count",
    "eerg_applied_count",
    "eerg_pre_qrs_bump_count",
    "eerg_early_count",
    "eerg_ecp_count",
    "eerg_pnn_decision_count",
    "eerg_pnn_mismatch_count",
    "eerg_rdm_valid_count",
    "eerg_rdm_code_sum",
    "strong_event_count",
]

FEATURE_GROUPS = ["PNN", "RDM", "DSCR", "RAM", "ECP", "QRS_MAF", "RBBB", "EERG"]

EERG_GATE = [5042413, 1853587, -6346411, -825955]
EERG_APPLIED = [4717413, -4196413, 2653589, -1775955]
EERG_LIKE = EERG_GATE[:]

for _prefix, _values in (
    ("C24_W_EERG_GATE", EERG_GATE),
    ("C24_W_EERG_APPLIED", EERG_APPLIED),
    ("C24_W_GATE_EERG_LIKE", EERG_LIKE),
):
    for _cls, _value in zip(CLASSES, _values):
        _CLASS_CONSTS.setdefault(f"{_prefix}_{_cls}", _value)

_ORIGINAL_SCORE_TICK = C24ScoreNeurons.tick
_ACTIVE_FEATURE_OFF: set[str] = set()
_MASK_INSTALLED = False


def eerg_like_from_score(score: C24ScoreNeurons) -> bool:
    return (
        score.rbbb_like_seg_count == 0
        and score.eerg_pre_qrs_bump_count >= 1
        and (score.eerg_early_count >= 10 or score.eerg_ecp_count >= 3)
        and score.eerg_pnn_decision_count != 0
        and score.eerg_pnn_mismatch_count * 100 <= score.eerg_pnn_decision_count * 15
        and score.eerg_rdm_valid_count != 0
        and score.eerg_rdm_code_sum <= score.eerg_rdm_valid_count * 5
    )


def install_score_mask(feature_off: set[str]) -> None:
    global _ACTIVE_FEATURE_OFF, _MASK_INSTALLED
    _ACTIVE_FEATURE_OFF = set(feature_off)
    if _MASK_INSTALLED:
        return

    def masked_tick(
        self: C24ScoreNeurons,
        clear: int,
        rhythm_tick: int,
        segment_done: int,
        beat_spike: int,
        qrs_maf_valid_spike: int,
        rbbb_qrs_valid_spike: int,
        rbbb_qrs_wide_spike: int,
        rbbb_qrs_terminal_spike: int,
        rbbb_qrs_like_beat_spike: int,
        pnn_match_spike: int,
        pnn_mismatch_spike: int,
        dscr_valid_slope_spike: int,
        dscr_sign_flip_spike: int,
        ram_amp_spike: int,
        ram_amp_code: int,
        rdm_valid_spike: int,
        rdm_level_spike: int,
        rdm_level_code: int,
        ectopic_pair_spike: int,
        ectopic_early_spike: int,
        pre_qrs_bump_spike: int,
        qrs_width_abn_spike: int,
        qrs_complex_abn_spike: int,
        qrs_energy_abn_spike: int,
        rbbb_qrs_delay_segment_spike: int,
        rbbb_qrs_like_count: int,
    ) -> None:
        feature_off = _ACTIVE_FEATURE_OFF
        if "PNN" in feature_off:
            pnn_match_spike = 0
            pnn_mismatch_spike = 0
        if "RDM" in feature_off:
            rdm_valid_spike = 0
            rdm_level_spike = 0
            rdm_level_code = 0
        if "DSCR" in feature_off:
            dscr_valid_slope_spike = 0
            dscr_sign_flip_spike = 0
        if "RAM" in feature_off:
            ram_amp_spike = 0
            ram_amp_code = 0
        if "ECP" in feature_off:
            ectopic_pair_spike = 0
            ectopic_early_spike = 0
        if "QRS_MAF" in feature_off:
            qrs_maf_valid_spike = 0
            pre_qrs_bump_spike = 0
            qrs_width_abn_spike = 0
            qrs_complex_abn_spike = 0
            qrs_energy_abn_spike = 0
        if "RBBB" in feature_off:
            rbbb_qrs_valid_spike = 0
            rbbb_qrs_wide_spike = 0
            rbbb_qrs_terminal_spike = 0
            rbbb_qrs_like_beat_spike = 0
            rbbb_qrs_delay_segment_spike = 0
            rbbb_qrs_like_count = 0

        eerg_like_next = False
        if "EERG" in feature_off and segment_done:
            rbbb_like_seg_next = self.rbbb_like_seg_count + (1 if rbbb_qrs_like_beat_spike else 0)
            pre_bump_seg_next = self.pre_qrs_bump_seg_count + (1 if pre_qrs_bump_spike else 0)
            ect_early_seg_next = self.ectopic_early_seg_count + (1 if ectopic_early_spike else 0)
            ect_pair_seg_next = self.ectopic_pair_seg_count + (1 if ectopic_pair_spike else 0)
            pnn_mis_seg_next = self.pnn_mis_seg_count + (1 if pnn_mismatch_spike else 0)
            pnn_match_seg_next = self.pnn_match_seg_count + (1 if pnn_match_spike else 0)
            pnn_decision_seg = pnn_mis_seg_next + pnn_match_seg_next
            rdm_valid_seg_next = self.rdm_valid_seg_count + (1 if rdm_valid_spike else 0)
            rdm_code_seg_next = self.rdm_code_seg_sum + (int(rdm_level_code) if rdm_valid_spike else 0)
            eerg_like_next = (
                rbbb_like_seg_next == 0
                and pre_bump_seg_next >= 1
                and (ect_early_seg_next >= 10 or ect_pair_seg_next >= 3)
                and pnn_decision_seg != 0
                and pnn_mis_seg_next * 100 <= pnn_decision_seg * 15
                and rdm_valid_seg_next != 0
                and rdm_code_seg_next <= rdm_valid_seg_next * 5
            )

        _ORIGINAL_SCORE_TICK(
            self,
            clear,
            rhythm_tick,
            segment_done,
            beat_spike,
            qrs_maf_valid_spike,
            rbbb_qrs_valid_spike,
            rbbb_qrs_wide_spike,
            rbbb_qrs_terminal_spike,
            rbbb_qrs_like_beat_spike,
            pnn_match_spike,
            pnn_mismatch_spike,
            dscr_valid_slope_spike,
            dscr_sign_flip_spike,
            ram_amp_spike,
            ram_amp_code,
            rdm_valid_spike,
            rdm_level_spike,
            rdm_level_code,
            ectopic_pair_spike,
            ectopic_early_spike,
            pre_qrs_bump_spike,
            qrs_width_abn_spike,
            qrs_complex_abn_spike,
            qrs_energy_abn_spike,
            rbbb_qrs_delay_segment_spike,
            rbbb_qrs_like_count,
        )

        # Snapshot V2 removes both direct EERG contribution and the C24
        # EERG-like global gate while keeping upstream rhythm/morphology
        # counters intact for analysis.
        if "EERG" in feature_off and segment_done:
            if self.eerg_applied:
                for ci in range(4):
                    self.c24_mem[ci] -= EERG_GATE[ci] + EERG_APPLIED[ci]
            if eerg_like_next:
                for ci in range(4):
                    self.c24_mem[ci] -= EERG_LIKE[ci]
            self.pred_class = self.argmax4(self.c24_mem)

    C24ScoreNeurons.tick = masked_tick
    _MASK_INSTALLED = True


def read_manifest(split: str, dataset: Path) -> list[dict[str, str]]:
    path = dataset / f"afe_manifest_{split}.csv"
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def resolve_mem(row: dict[str, str], dataset: Path) -> Path:
    raw = row.get("afe_adc_signed_file") or row.get("chunk_file") or ""
    candidates = []
    p = Path(raw)
    if p.is_absolute():
        candidates.append(p)
    candidates.extend([dataset.parent / raw, dataset / raw])
    if raw:
        candidates.extend((dataset / "signed" / row["split"]).rglob(Path(raw).name))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(raw)


def job_rows(splits: list[str], dataset: Path) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for split in splits:
        for idx, row in enumerate(read_manifest(split, dataset)):
            jobs.append(
                {
                    "split": split,
                    "row_index": idx,
                    "segment_id": row.get("segment_id", ""),
                    "record_id": row.get("record_id", ""),
                    "class_label": row["class_label"],
                    "class_id": int(row["class_id"]),
                    "mem_path": str(resolve_mem(row, dataset)),
                }
            )
    return jobs


def run_one(job: dict[str, Any]) -> dict[str, Any]:
    install_score_mask(set(job.get("feature_off", ())))
    samples = s12_from_hex_mem(Path(job["mem_path"]))
    out = SnapshotFrontEnd().run_window(samples)
    row = {
        "split": job["split"],
        "row_index": job["row_index"],
        "segment_id": job["segment_id"],
        "record_id": job["record_id"],
        "class_label": job["class_label"],
        "class_id": job["class_id"],
        "pred_class": int(out["pred_class"]),
        "pred_label": CLASSES[int(out["pred_class"])],
        "correct": int(int(out["pred_class"]) == job["class_id"]),
        "class_mem_NSR": int(out["class_mem_NSR"]),
        "class_mem_CHF": int(out["class_mem_CHF"]),
        "class_mem_ARR": int(out["class_mem_ARR"]),
        "class_mem_AFF": int(out["class_mem_AFF"]),
    }
    for col in FEATURE_COLUMNS:
        row[col] = int(out.get(col, 0))
    row["pnn_mismatch_rate_pct"] = (
        100.0 * row["pnn_mismatch_count"] / (row["pnn_match_count"] + row["pnn_mismatch_count"])
        if row["pnn_match_count"] + row["pnn_mismatch_count"]
        else 0.0
    )
    row["rdm_avg"] = row["rdm_code_sum"] / row["rdm_valid_count"] if row["rdm_valid_count"] else 0.0
    row["ram_avg"] = row["ram_code_sum"] / row["ram_code_count"] if row["ram_code_count"] else 0.0
    row["qrs_maf_rate_pct"] = 100.0 * row["qrs_maf_count"] / row["qrs_maf_valid_count"] if row["qrs_maf_valid_count"] else 0.0
    return row


def eval_jobs(jobs: list[dict[str, Any]], workers: int, chunksize: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with mp.Pool(processes=workers) as pool:
        for idx, row in enumerate(pool.imap_unordered(run_one, jobs, chunksize=chunksize), 1):
            rows.append(row)
            if idx % 64 == 0 or idx == len(jobs):
                print(f"done {idx}/{len(jobs)}", flush=True)
    rows.sort(key=lambda r: (r["split"], int(r["row_index"])))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def metric_dict(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cm = {t: {p: 0 for p in CLASSES} for t in CLASSES}
    for row in rows:
        cm[row["class_label"]][row["pred_label"]] += 1
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


def metric_from_predictions(rows: list[dict[str, Any]], pred_key: str) -> dict[str, Any]:
    converted = []
    for row in rows:
        item = dict(row)
        pred = int(row[pred_key])
        item["pred_label"] = CLASSES[pred]
        converted.append(item)
    return metric_dict(converted)


def class_mem(row: dict[str, Any]) -> list[int]:
    return [int(row[f"class_mem_{cls}"]) for cls in CLASSES]


def top2(scores: list[int]) -> tuple[int, int, int]:
    order = sorted(range(4), key=lambda idx: scores[idx], reverse=True)
    return order[0], order[1], scores[order[0]] - scores[order[1]]


def pred(scores: list[int]) -> int:
    best = 0
    for idx in range(1, 4):
        if scores[idx] > scores[best]:
            best = idx
    return best


def x10(value: Any) -> int:
    return int(round(float(value) * 10.0))


def x100(value: Any) -> int:
    return int(round(float(value) * 100.0))


def add(scores: list[int], cls: str, weight: int) -> None:
    scores[CLASSES.index(cls)] += int(weight)


def chf_guard(row: dict[str, Any], params: dict[str, Any]) -> bool:
    return (
        (
            int(row["dscr_flip_count"]) <= params["chf_dscr_flip_le"]
            or int(row["dscr_slope_count"]) <= params["chf_dscr_slope_le"]
        )
        and x100(row["ram_avg"]) <= params["chf_ram_x100_le"]
        and x100(row["rdm_avg"]) <= params["chf_rdm_x100_le"]
        and x10(row["pnn_mismatch_rate_pct"]) <= params["chf_pnn_x10_le"]
    )


def apply_candidate(row: dict[str, Any], params: dict[str, Any]) -> int:
    scores = class_mem(row)
    if params.get("eerg_off") and int(row.get("eerg_applied_count", 0)):
        for ci in range(4):
            scores[ci] -= EERG_GATE[ci] + EERG_APPLIED[ci]

    guard = params.get("chf_guard") and chf_guard(row, params)
    if guard:
        add(scores, "CHF", params["chf_boost"])
        add(scores, "ARR", -params["chf_arr_penalty"])
        add(scores, "AFF", -params["chf_aff_penalty"])

    if params.get("arr_aff_resolver"):
        first, second, margin = top2(scores)
        near_arr_aff = {first, second} == {2, 3} or abs(scores[2] - scores[3]) <= params["arr_aff_margin"]
        if near_arr_aff and not guard:
            ram = x100(row["ram_avg"])
            rbbb = int(row["rbbb_delay_like_count"])
            if ram >= params["arr_ram_x100_ge"] and rbbb <= params["arr_rbbb_le"]:
                add(scores, "ARR", params["arr_over_aff_boost"])
            if ram <= params["aff_ram_x100_le"] and rbbb >= params["aff_rbbb_ge"]:
                add(scores, "AFF", params["aff_over_arr_boost"])

    if params.get("nsr_clean_guard"):
        clean = (
            x10(row["pnn_mismatch_rate_pct"]) <= params["nsr_pnn_x10_le"]
            and x100(row["rdm_avg"]) <= params["nsr_rdm_x100_le"]
            and int(row["ectopic_pair_count"]) <= params["nsr_ecp_le"]
            and x10(row["qrs_maf_rate_pct"]) <= params["nsr_qrs_x10_le"]
            and x100(row["ram_avg"]) >= params["nsr_ram_x100_ge"]
            and int(row["rbbb_delay_like_count"]) <= params["nsr_rbbb_le"]
        )
        if clean:
            add(scores, "NSR", params["nsr_boost"])
            add(scores, "ARR", -params["nsr_arr_penalty"])
            add(scores, "AFF", -params["nsr_aff_penalty"])

    return pred(scores)


def candidate_grid() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = [{"candidate": "baseline"}]
    candidates.append({"candidate": "eerg_off", "eerg_off": True})

    chf_candidates: list[dict[str, Any]] = []
    for flip in [1, 8, 32]:
        for slope in [50, 250]:
            for ram in [800, 1000]:
                for pnn in [280, 320]:
                    for boost in [2_000_000, 4_000_000, 8_000_000]:
                        for penalty in [0, 2_000_000]:
                            chf_candidates.append(
                                {
                                    "chf_guard": True,
                                    "chf_dscr_flip_le": flip,
                                    "chf_dscr_slope_le": slope,
                                    "chf_ram_x100_le": ram,
                                    "chf_rdm_x100_le": 600,
                                    "chf_pnn_x10_le": pnn,
                                    "chf_boost": boost,
                                    "chf_arr_penalty": penalty,
                                    "chf_aff_penalty": penalty,
                                }
                            )
    for idx, base in enumerate(chf_candidates):
        candidates.append({"candidate": f"chf_guard_{idx:03d}", **base})
        candidates.append({"candidate": f"eerg_off_chf_guard_{idx:03d}", "eerg_off": True, **base})

    resolver_candidates: list[dict[str, Any]] = []
    for arr_ram in [1200, 1400]:
        for arr_rbbb in [4, 8]:
            for aff_ram in [1000, 1200]:
                for aff_rbbb in [8, 16, 24]:
                    for boost in [2_000_000, 4_000_000]:
                        for margin in [30_000_000, 80_000_000]:
                            resolver_candidates.append(
                                {
                                    "arr_aff_resolver": True,
                                    "arr_aff_margin": margin,
                                    "arr_ram_x100_ge": arr_ram,
                                    "arr_rbbb_le": arr_rbbb,
                                    "aff_ram_x100_le": aff_ram,
                                    "aff_rbbb_ge": aff_rbbb,
                                    "arr_over_aff_boost": boost,
                                    "aff_over_arr_boost": boost,
                                }
                            )
    for idx, base in enumerate(resolver_candidates):
        candidates.append({"candidate": f"arr_aff_resolver_{idx:03d}", **base})
        candidates.append({"candidate": f"eerg_off_arr_aff_resolver_{idx:03d}", "eerg_off": True, **base})

    for idx, chf in enumerate(chf_candidates[::12]):
        for jdx, resolver in enumerate(resolver_candidates[::16]):
            candidates.append({"candidate": f"chf_resolver_{idx:02d}_{jdx:02d}", **chf, **resolver})
            candidates.append({"candidate": f"eerg_chf_resolver_{idx:02d}_{jdx:02d}", "eerg_off": True, **chf, **resolver})

    for pnn in [80, 100, 120]:
        for rdm in [350, 400, 450]:
            for ram in [1200, 1400]:
                candidates.append(
                    {
                        "candidate": f"nsr_clean_p{pnn}_r{rdm}_ram{ram}",
                        "nsr_clean_guard": True,
                        "nsr_pnn_x10_le": pnn,
                        "nsr_rdm_x100_le": rdm,
                        "nsr_ecp_le": 1,
                        "nsr_qrs_x10_le": 50,
                        "nsr_ram_x100_ge": ram,
                        "nsr_rbbb_le": 1,
                        "nsr_boost": 2_000_000,
                        "nsr_arr_penalty": 2_000_000,
                        "nsr_aff_penalty": 2_000_000,
                    }
                )
    return candidates


def candidate_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float, float]:
    return (
        float(row["val_macro_f1"]),
        float(row["val_balanced_accuracy"]),
        float(row["val_worst_recall"]),
        float(row["val_accuracy"]),
        -float(row.get("complexity", 0)),
    )


def command_rule_search(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    rows = read_rows(out_dir / "window_dump_train_val.csv")
    candidates = candidate_grid()
    output: list[dict[str, Any]] = []
    confusions: dict[str, Any] = {}
    for idx, params in enumerate(candidates, 1):
        evaluated = []
        for row in rows:
            item = dict(row)
            item["rule_pred"] = apply_candidate(row, params)
            evaluated.append(item)
        metrics_by_split = {
            split: metric_from_predictions([r for r in evaluated if r["split"] == split], "rule_pred")
            for split in ["train", "val"]
        }
        train = metrics_by_split["train"]
        val = metrics_by_split["val"]
        recalls = [val["per_class"][cls]["recall"] for cls in CLASSES]
        complexity = sum(1 for k, v in params.items() if k != "candidate" and v not in (False, None, 0))
        row_out: dict[str, Any] = {
            "candidate": params["candidate"],
            "params_json": json.dumps(params, sort_keys=True),
            "complexity": complexity,
            "train_accuracy": train["accuracy"],
            "train_macro_f1": train["macro_f1"],
            "train_balanced_accuracy": train["balanced_accuracy"],
            "val_accuracy": val["accuracy"],
            "val_macro_f1": val["macro_f1"],
            "val_balanced_accuracy": val["balanced_accuracy"],
            "val_worst_recall": min(recalls),
            "val_recall_spread": max(recalls) - min(recalls),
        }
        for split_name, metric in [("train", train), ("val", val)]:
            for cls in CLASSES:
                row_out[f"{split_name}_{cls}_recall"] = metric["per_class"][cls]["recall"]
                row_out[f"{split_name}_{cls}_precision"] = metric["per_class"][cls]["precision"]
                row_out[f"{split_name}_{cls}_f1"] = metric["per_class"][cls]["f1"]
        output.append(row_out)
        confusions[params["candidate"]] = {split: metric["confusion"] for split, metric in metrics_by_split.items()}
        if idx % 100 == 0 or idx == len(candidates):
            print(f"evaluated {idx}/{len(candidates)}", flush=True)
    output.sort(key=candidate_sort_key, reverse=True)
    write_csv(out_dir / "rule_search_train_val.csv", output)
    write_csv(out_dir / "rule_search_top50.csv", output[:50])
    (out_dir / "rule_search_confusions.json").write_text(json.dumps(confusions, indent=2), encoding="utf-8")
    (out_dir / "rule_search_best_params.json").write_text(output[0]["params_json"], encoding="utf-8")
    print(json.dumps(output[0], indent=2), flush=True)


def fixed_subset_candidate_grid(feature_off: tuple[str, ...]) -> list[dict[str, Any]]:
    """Return rule candidates for an already-masked feature subset.

    EERG is special because it is removed by editing the class membrane after
    the C24 internal gate fires. If the masked dump already disabled EERG, an
    `eerg_off` rule would subtract the same contribution twice. If the masked
    dump did not disable EERG, allowing `eerg_off` would silently change the
    feature subset. Therefore subset-specific searches exclude rule-level
    `eerg_off`; EERG-off itself is represented as a fixed feature mask.
    """
    dedup: dict[str, dict[str, Any]] = {}
    for params in candidate_grid():
        if params.get("eerg_off"):
            continue
        key_params = {k: v for k, v in params.items() if k != "candidate"}
        key = json.dumps(key_params, sort_keys=True)
        if key not in dedup:
            name = params.get("candidate", "candidate")
            dedup[key] = {**key_params, "candidate": name}
    return list(dedup.values())


def subset_name(feature_off: tuple[str, ...]) -> str:
    return "full_feature" if not feature_off else "off_" + "_".join(feature_off)


def parse_feature_mask(raw: str) -> tuple[str, ...]:
    raw = raw.strip()
    if raw.upper() in {"", "NONE", "FULL", "FULL_FEATURE"}:
        return ()
    parts = tuple(part.strip().upper() for part in raw.replace(",", "+").split("+") if part.strip())
    unknown = [part for part in parts if part not in FEATURE_GROUPS]
    if unknown:
        raise ValueError(f"unknown feature groups in mask {raw!r}: {unknown}")
    return parts


def command_subset_rule_search(args: argparse.Namespace) -> None:
    dataset = Path(args.dataset_root)
    out_dir = Path(args.out_dir)
    masks = [parse_feature_mask(mask) for mask in args.masks]
    base_jobs = job_rows(["train", "val"], dataset)
    best_rows: list[dict[str, Any]] = []
    all_top_rows: list[dict[str, Any]] = []
    confusions: dict[str, Any] = {}

    for feature_off in masks:
        name = subset_name(feature_off)
        masked_jobs = [dict(job, feature_off=feature_off) for job in base_jobs]
        print(f"subset rule-search: {name}, windows={len(masked_jobs)}", flush=True)
        rows = eval_jobs(masked_jobs, args.workers, args.chunksize)
        if args.write_window_dumps:
            write_csv(out_dir / f"subset_window_dump_{name}.csv", rows)

        baseline_metrics = {split: metric_dict([r for r in rows if r["split"] == split]) for split in ["train", "val"]}
        subset_candidates = fixed_subset_candidate_grid(feature_off)
        output: list[dict[str, Any]] = []
        for params in subset_candidates:
            metrics_by_split = evaluate_params(rows, params)
            train = metrics_by_split["train"]
            val = metrics_by_split["val"]
            recalls = [val["per_class"][cls]["recall"] for cls in CLASSES]
            complexity = sum(1 for k, v in params.items() if k != "candidate" and v not in (False, None, 0))
            row_out: dict[str, Any] = {
                "subset": name,
                "feature_off": "+".join(feature_off) if feature_off else "NONE",
                "candidate": params["candidate"],
                "params_json": json.dumps(params, sort_keys=True),
                "complexity": complexity,
                "train_accuracy": train["accuracy"],
                "train_macro_f1": train["macro_f1"],
                "train_balanced_accuracy": train["balanced_accuracy"],
                "val_accuracy": val["accuracy"],
                "val_macro_f1": val["macro_f1"],
                "val_balanced_accuracy": val["balanced_accuracy"],
                "val_worst_recall": min(recalls),
                "val_recall_spread": max(recalls) - min(recalls),
                "audit_only_post_test": True,
            }
            for split_name, metric in [("train", train), ("val", val)]:
                for cls in CLASSES:
                    row_out[f"{split_name}_{cls}_recall"] = metric["per_class"][cls]["recall"]
                    row_out[f"{split_name}_{cls}_precision"] = metric["per_class"][cls]["precision"]
                    row_out[f"{split_name}_{cls}_f1"] = metric["per_class"][cls]["f1"]
            output.append(row_out)
            confusions[f"{name}:{params['candidate']}"] = {
                split: metric["confusion"] for split, metric in metrics_by_split.items()
            }

        output.sort(key=candidate_sort_key, reverse=True)
        top_path = out_dir / f"subset_rule_search_top20_{name}.csv"
        write_csv(top_path, output[:20])
        all_top_rows.extend(output[:20])

        best = dict(output[0])
        best["subset_baseline_train_accuracy"] = baseline_metrics["train"]["accuracy"]
        best["subset_baseline_train_macro_f1"] = baseline_metrics["train"]["macro_f1"]
        best["subset_baseline_val_accuracy"] = baseline_metrics["val"]["accuracy"]
        best["subset_baseline_val_macro_f1"] = baseline_metrics["val"]["macro_f1"]
        best["subset_baseline_val_balanced_accuracy"] = baseline_metrics["val"]["balanced_accuracy"]
        best_rows.append(best)
        print(json.dumps(best, indent=2), flush=True)

    best_rows.sort(key=candidate_sort_key, reverse=True)
    all_top_rows.sort(key=candidate_sort_key, reverse=True)
    write_csv(out_dir / "subset_rule_search_best_train_val.csv", best_rows)
    write_csv(out_dir / "subset_rule_search_top_all_train_val.csv", all_top_rows)
    (out_dir / "subset_rule_search_confusions.json").write_text(json.dumps(confusions, indent=2), encoding="utf-8")
    print(f"wrote {out_dir / 'subset_rule_search_best_train_val.csv'}", flush=True)


def evaluate_params(rows: list[dict[str, Any]], params: dict[str, Any], pred_key: str = "rule_pred") -> dict[str, Any]:
    evaluated = []
    for row in rows:
        item = dict(row)
        item[pred_key] = apply_candidate(row, params)
        evaluated.append(item)
    return {
        split: metric_from_predictions([r for r in evaluated if r["split"] == split], pred_key)
        for split in ["train", "val"]
    }


def stability_variants(best: dict[str, Any]) -> list[dict[str, Any]]:
    variants = [
        {"candidate": "baseline"},
        {"candidate": "eerg_off", "eerg_off": True},
        {**{k: v for k, v in best.items() if k != "eerg_off"}, "candidate": "chf_guard_only"},
        {**best, "candidate": "best_current"},
    ]
    for boost in [500_000, 1_000_000, 2_000_000, 4_000_000, 8_000_000]:
        variant = dict(best)
        variant["candidate"] = f"boost_{boost}"
        variant["chf_boost"] = boost
        variants.append(variant)
    jitter = {
        "chf_pnn_x10_le": [260, 280, 300],
        "chf_ram_x100_le": [750, 800, 850],
        "chf_rdm_x100_le": [550, 600, 650],
        "chf_dscr_slope_le": [40, 50, 60],
        "chf_dscr_flip_le": [0, 1, 2],
    }
    for key, values in jitter.items():
        for value in values:
            variant = dict(best)
            variant["candidate"] = f"jitter_{key}_{value}"
            variant[key] = value
            variants.append(variant)
    drop_specs = {
        "drop_pnn": ("chf_pnn_x10_le", 99999),
        "drop_ram": ("chf_ram_x100_le", 99999),
        "drop_rdm": ("chf_rdm_x100_le", 99999),
        "flip_only": ("chf_dscr_slope_le", -1),
        "slope_only": ("chf_dscr_flip_le", -1),
        "drop_dscr": ("chf_dscr_flip_le", 99999),
    }
    for name, (key, value) in drop_specs.items():
        variant = dict(best)
        variant["candidate"] = name
        variant[key] = value
        variants.append(variant)
    return variants


def command_stability_check(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    rows = read_rows(out_dir / "window_dump_train_val.csv")
    best = json.loads((out_dir / "rule_search_best_params.json").read_text(encoding="utf-8"))
    output: list[dict[str, Any]] = []
    for params in stability_variants(best):
        metrics = evaluate_params(rows, params)
        train = metrics["train"]
        val = metrics["val"]
        recalls = [val["per_class"][cls]["recall"] for cls in CLASSES]
        row_out: dict[str, Any] = {
            "candidate": params["candidate"],
            "params_json": json.dumps(params, sort_keys=True),
            "train_accuracy": train["accuracy"],
            "train_macro_f1": train["macro_f1"],
            "train_balanced_accuracy": train["balanced_accuracy"],
            "val_accuracy": val["accuracy"],
            "val_macro_f1": val["macro_f1"],
            "val_balanced_accuracy": val["balanced_accuracy"],
            "val_worst_recall": min(recalls),
            "val_recall_spread": max(recalls) - min(recalls),
        }
        for split_name, metric in [("train", train), ("val", val)]:
            for cls in CLASSES:
                row_out[f"{split_name}_{cls}_recall"] = metric["per_class"][cls]["recall"]
        output.append(row_out)
    output.sort(key=candidate_sort_key, reverse=True)
    write_csv(out_dir / "stability_check_train_val.csv", output)

    audit_rows: list[dict[str, Any]] = []
    eerg_params = {"candidate": "eerg_off", "eerg_off": True}
    for row in rows:
        scores = class_mem(row)
        first, second, margin = top2(scores)
        guard = bool(best.get("chf_guard") and chf_guard(row, best))
        audit_rows.append(
            {
                "split": row["split"],
                "row_index": row["row_index"],
                "segment_id": row["segment_id"],
                "record_id": row["record_id"],
                "true_label": row["class_label"],
                "baseline_pred": row["pred_label"],
                "eerg_off_pred": CLASSES[apply_candidate(row, eerg_params)],
                "best_pred": CLASSES[apply_candidate(row, best)],
                "baseline_correct": int(row["correct"]),
                "best_correct": int(CLASSES[apply_candidate(row, best)] == row["class_label"]),
                "guard_fired": int(guard),
                "top1": CLASSES[first],
                "top2": CLASSES[second],
                "top_margin": margin,
                "pnn_x10": x10(row["pnn_mismatch_rate_pct"]),
                "ram_x100": x100(row["ram_avg"]),
                "rdm_x100": x100(row["rdm_avg"]),
                "dscr_flip_count": row["dscr_flip_count"],
                "dscr_slope_count": row["dscr_slope_count"],
                "dist_pnn": best.get("chf_pnn_x10_le", 0) - x10(row["pnn_mismatch_rate_pct"]),
                "dist_ram": best.get("chf_ram_x100_le", 0) - x100(row["ram_avg"]),
                "dist_rdm": best.get("chf_rdm_x100_le", 0) - x100(row["rdm_avg"]),
                "dist_dscr_flip": best.get("chf_dscr_flip_le", 0) - int(row["dscr_flip_count"]),
                "dist_dscr_slope": best.get("chf_dscr_slope_le", 0) - int(row["dscr_slope_count"]),
            }
        )
    write_csv(out_dir / "best_candidate_paired_audit_train_val.csv", audit_rows)
    summary = Counter((r["split"], r["true_label"], r["baseline_correct"], r["guard_fired"], r["best_correct"]) for r in audit_rows)
    summary_rows = [
        {
            "split": split,
            "true_label": cls,
            "baseline_correct": base_ok,
            "guard_fired": guard,
            "best_correct": best_ok,
            "count": count,
        }
        for (split, cls, base_ok, guard, best_ok), count in sorted(summary.items())
    ]
    write_csv(out_dir / "best_candidate_trigger_summary_train_val.csv", summary_rows)
    print(json.dumps(output[0], indent=2), flush=True)


def command_freeze_candidate(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    best = json.loads((out_dir / "rule_search_best_params.json").read_text(encoding="utf-8"))
    stability = read_rows(out_dir / "stability_check_train_val.csv")
    best_row = next(row for row in stability if row["candidate"] == "best_current")
    selected = {
        "candidate_name": "snapshot_c24_v2_eerg_off_chf_guard",
        "source": "train_validation_only",
        "test_used_for_selection": False,
        "base_model": "Snapshot C24 exact Python equivalent",
        "params": best,
        "train_val_metrics": best_row,
        "selection_rationale": [
            "Improves validation from 231/256 to 232/256.",
            "Improves validation macro-F1 from 0.902700 to 0.906795.",
            "Improves validation worst-class recall from 0.875000 to 0.890625.",
            "Preserves NSR, ARR, and AFF validation recall while correcting one CHF sample.",
            "Stable under one-factor threshold jitter around the selected guard.",
            "RTL-mappable: EERG C24 contribution zero plus fixed comparator CHF guard and signed class-membrane add.",
        ],
        "frozen_before_test": True,
    }
    path = out_dir / "selected_candidate_train_val_frozen.json"
    path.write_text(json.dumps(selected, indent=2), encoding="utf-8")
    print(path)


def command_final_test(args: argparse.Namespace) -> None:
    dataset = Path(args.dataset_root)
    out_dir = Path(args.out_dir)
    lock = out_dir / "FINAL_TEST_ONCE_OPENED.lock"
    if lock.exists() and not args.allow_rerun:
        raise SystemExit(f"final test lock exists: {lock}. Pass --allow-rerun only for audit/reproduction.")
    selected_path = out_dir / "selected_candidate_train_val_frozen.json"
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    params = selected["params"]
    jobs = job_rows(["test"], dataset)
    print(f"FINAL TEST: extracting {len(jobs)} held-out windows", flush=True)
    rows = eval_jobs(jobs, args.workers, args.chunksize)
    for row in rows:
        row["final_pred_class"] = apply_candidate(row, params)
        row["final_pred_label"] = CLASSES[int(row["final_pred_class"])]
        row["final_correct"] = int(row["final_pred_label"] == row["class_label"])
    write_csv(out_dir / "final_test_window_predictions.csv", rows)
    baseline = metric_dict(rows)
    final = metric_from_predictions(rows, "final_pred_class")
    result = {
        "candidate_name": selected["candidate_name"],
        "test_used_for_selection": False,
        "note": "This command is the locked final held-out test evaluation for the frozen train/validation-selected candidate.",
        "baseline_c24_test": baseline,
        "final_candidate_test": final,
    }
    (out_dir / "final_test_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lock.write_text("Final held-out test was opened by snapshot_c24_v2_search.py final-test.\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


def quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "p10": 0.0, "p50": 0.0, "p90": 0.0}
    values = sorted(values)

    def q(frac: float) -> float:
        idx = round((len(values) - 1) * frac)
        return float(values[idx])

    return {"mean": sum(values) / len(values), "p10": q(0.10), "p50": q(0.50), "p90": q(0.90)}


def feature_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for split in sorted({str(r["split"]) for r in rows}):
        split_rows = [r for r in rows if r["split"] == split]
        for cls in CLASSES:
            cls_rows = [r for r in split_rows if r["class_label"] == cls]
            for col in FEATURE_COLUMNS + ["pnn_mismatch_rate_pct", "rdm_avg", "ram_avg", "qrs_maf_rate_pct"]:
                vals = [float(r[col]) for r in cls_rows]
                q = quantiles(vals)
                summary.append({"split": split, "class_label": cls, "feature": col, "n": len(vals), **q})
    return summary


def command_extract(args: argparse.Namespace) -> None:
    dataset = Path(args.dataset_root)
    out_dir = Path(args.out_dir)
    splits = args.splits
    jobs = job_rows(splits, dataset)
    print(f"extracting {len(jobs)} windows from {dataset}")
    rows = eval_jobs(jobs, args.workers, args.chunksize)
    write_csv(out_dir / "window_dump_train_val.csv", rows)
    for split in splits:
        split_rows = [r for r in rows if r["split"] == split]
        write_csv(out_dir / f"window_dump_{split}.csv", split_rows)
    metrics = {split: metric_dict([r for r in rows if r["split"] == split]) for split in splits}
    (out_dir / "baseline_train_val_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    write_csv(out_dir / "train_val_feature_summary.csv", feature_summary(rows))
    split_counts = Counter((r["split"], r["class_label"]) for r in rows)
    (out_dir / "train_val_counts.json").write_text(
        json.dumps({f"{s}:{c}": n for (s, c), n in sorted(split_counts.items())}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2), flush=True)


def flatten_metric(candidate: str, feature_off: tuple[str, ...], split: str, metrics: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "candidate": candidate,
        "feature_off": "+".join(feature_off) if feature_off else "NONE",
        "split": split,
        "correct": metrics["correct"],
        "total": metrics["total"],
        "accuracy": metrics["accuracy"],
        "macro_f1": metrics["macro_f1"],
        "balanced_accuracy": metrics["balanced_accuracy"],
    }
    for cls in CLASSES:
        row[f"{cls}_precision"] = metrics["per_class"][cls]["precision"]
        row[f"{cls}_recall"] = metrics["per_class"][cls]["recall"]
        row[f"{cls}_f1"] = metrics["per_class"][cls]["f1"]
    return row


def command_single_ablation(args: argparse.Namespace) -> None:
    dataset = Path(args.dataset_root)
    out_dir = Path(args.out_dir)
    base_jobs = job_rows(["train", "val"], dataset)
    rows_out: list[dict[str, Any]] = []
    confusion: dict[str, Any] = {}
    for group in FEATURE_GROUPS:
        feature_off = (group,)
        jobs = [dict(job, feature_off=feature_off) for job in base_jobs]
        print(f"single ablation: off={group}, windows={len(jobs)}", flush=True)
        rows = eval_jobs(jobs, args.workers, args.chunksize)
        for split in ["train", "val"]:
            metrics = metric_dict([r for r in rows if r["split"] == split])
            rows_out.append(flatten_metric(f"off_{group}", feature_off, split, metrics))
            confusion[f"off_{group}:{split}"] = metrics["confusion"]
    write_csv(out_dir / "single_feature_off_ablation.csv", rows_out)
    (out_dir / "single_feature_off_confusion.json").write_text(json.dumps(confusion, indent=2), encoding="utf-8")
    print(f"wrote {out_dir / 'single_feature_off_ablation.csv'}", flush=True)


def combo_metric_rows(
    name: str,
    feature_off: tuple[str, ...],
    jobs: list[dict[str, Any]],
    workers: int,
    chunksize: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    masked_jobs = [dict(job, feature_off=feature_off) for job in jobs]
    print(f"combo ablation: {name}, off={'+'.join(feature_off)}, windows={len(masked_jobs)}", flush=True)
    rows = eval_jobs(masked_jobs, workers, chunksize)
    metric_rows = []
    confusion = {}
    for split in ["train", "val"]:
        metrics = metric_dict([r for r in rows if r["split"] == split])
        metric_rows.append(flatten_metric(name, feature_off, split, metrics))
        confusion[split] = metrics["confusion"]
    return metric_rows, confusion


def command_combo_ablation(args: argparse.Namespace) -> None:
    dataset = Path(args.dataset_root)
    out_dir = Path(args.out_dir)
    jobs = job_rows(["train", "val"], dataset)
    if args.mode == "pair":
        combos = list(combinations(FEATURE_GROUPS, 2))
        out_csv = out_dir / "pair_feature_off_ablation.csv"
        out_json = out_dir / "pair_feature_off_confusion.json"
    else:
        combos = [
            ("EERG", "QRS_MAF", "RBBB"),
            ("EERG", "QRS_MAF", "ECP"),
            ("EERG", "QRS_MAF", "PNN"),
            ("EERG", "RBBB", "ECP"),
            ("EERG", "RBBB", "RAM"),
            ("EERG", "ECP", "RAM"),
            ("QRS_MAF", "RBBB", "ECP"),
            ("QRS_MAF", "RBBB", "RAM"),
            ("QRS_MAF", "ECP", "RAM"),
            ("RBBB", "ECP", "RAM"),
        ]
        out_csv = out_dir / "limited_triple_feature_off_ablation.csv"
        out_json = out_dir / "limited_triple_feature_off_confusion.json"
    all_rows: list[dict[str, Any]] = []
    all_confusions: dict[str, Any] = {}
    if out_csv.exists() and args.resume:
        existing = read_rows(out_csv)
        done = {tuple(str(row["feature_off"]).split("+")) for row in existing if row.get("split") == "val"}
        all_rows.extend(existing)
        if out_json.exists():
            all_confusions.update(json.loads(out_json.read_text(encoding="utf-8")))
    else:
        done = set()
    for idx, combo in enumerate(combos, 1):
        combo = tuple(combo)
        if combo in done:
            print(f"skip existing {combo}", flush=True)
            continue
        name = "off_" + "_".join(combo)
        rows, confusion = combo_metric_rows(name, combo, jobs, args.workers, args.chunksize)
        all_rows.extend(rows)
        all_confusions[name] = confusion
        write_csv(out_csv, all_rows)
        out_json.write_text(json.dumps(all_confusions, indent=2), encoding="utf-8")
        print(f"completed {idx}/{len(combos)} -> {name}", flush=True)
    print(f"wrote {out_csv}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Python-only Snapshot C24 v2 search utilities.")
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser("extract-dev")
    p.add_argument("--dataset-root", default=str(DATASET))
    p.add_argument("--out-dir", default=str(OUT))
    p.add_argument("--splits", nargs="+", default=["train", "val"], choices=["train", "val"])
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--chunksize", type=int, default=4)
    p.set_defaults(func=command_extract)
    p = sub.add_parser("single-ablation")
    p.add_argument("--dataset-root", default=str(DATASET))
    p.add_argument("--out-dir", default=str(OUT))
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--chunksize", type=int, default=4)
    p.set_defaults(func=command_single_ablation)
    p = sub.add_parser("combo-ablation")
    p.add_argument("--dataset-root", default=str(DATASET))
    p.add_argument("--out-dir", default=str(OUT))
    p.add_argument("--mode", choices=["pair", "triple-limited"], required=True)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--chunksize", type=int, default=4)
    p.add_argument("--resume", action="store_true")
    p.set_defaults(func=command_combo_ablation)
    p = sub.add_parser("rule-search")
    p.add_argument("--out-dir", default=str(OUT))
    p.set_defaults(func=command_rule_search)
    p = sub.add_parser("subset-rule-search")
    p.add_argument("--dataset-root", default=str(DATASET))
    p.add_argument("--out-dir", default=str(OUT))
    p.add_argument("--masks", nargs="+", required=True, help="Feature masks such as NONE EERG QRS_MAF+EERG.")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--chunksize", type=int, default=4)
    p.add_argument("--write-window-dumps", action="store_true")
    p.set_defaults(func=command_subset_rule_search)
    p = sub.add_parser("stability-check")
    p.add_argument("--out-dir", default=str(OUT))
    p.set_defaults(func=command_stability_check)
    p = sub.add_parser("freeze-candidate")
    p.add_argument("--out-dir", default=str(OUT))
    p.set_defaults(func=command_freeze_candidate)
    p = sub.add_parser("final-test")
    p.add_argument("--dataset-root", default=str(DATASET))
    p.add_argument("--out-dir", default=str(OUT))
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--chunksize", type=int, default=4)
    p.add_argument("--allow-rerun", action="store_true")
    p.set_defaults(func=command_final_test)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    mp.freeze_support()
    main()
