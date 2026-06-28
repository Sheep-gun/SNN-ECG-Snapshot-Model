from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


CLASSES = ["NSR", "CHF", "ARR", "AFF"]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASSES)}
SAMPLE_RATE = 1000
SETTLING_SKIP = 2000
WINDOW_SAMPLES = 60000


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields: list[str] | None = None) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def load_weights(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def vec_from_map(d: dict[str, int | float]) -> np.ndarray:
    return np.array([int(d[c]) for c in CLASSES], dtype=np.int64)


def parse_mem_file(path: Path) -> np.ndarray:
    raw = np.fromfile(path, dtype=np.uint8)
    if raw.size % 4 != 0:
        raise ValueError(f"{path} byte size is not a multiple of 4")
    a = raw.reshape((-1, 4))[:, :3]
    n = np.empty_like(a)
    digit = (a >= ord("0")) & (a <= ord("9"))
    upper = (a >= ord("A")) & (a <= ord("F"))
    lower = (a >= ord("a")) & (a <= ord("f"))
    if not np.all(digit | upper | lower):
        raise ValueError(f"{path} contains non-hex sample text")
    n[digit] = a[digit] - ord("0")
    n[upper] = a[upper] - ord("A") + 10
    n[lower] = a[lower] - ord("a") + 10
    u = ((n[:, 0].astype(np.uint16) << 8) | (n[:, 1].astype(np.uint16) << 4) | n[:, 2].astype(np.uint16))
    signed = u.astype(np.int16)
    signed[u >= 0x800] -= 0x1000
    return signed


def moving_average_abs(x: np.ndarray, width: int) -> np.ndarray:
    if x.size == 0:
        return x.astype(np.float64)
    kernel = np.ones(width, dtype=np.float64) / float(width)
    return np.convolve(np.abs(x), kernel, mode="same")


def robust_scale(x: np.ndarray) -> tuple[float, float, float]:
    med = float(np.median(x))
    centered = x.astype(np.float64) - med
    mad = float(np.median(np.abs(centered))) + 1.0
    return med, mad, float(np.percentile(np.abs(centered), 95))


def detect_peaks(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    med, mad, p95 = robust_scale(samples)
    centered = samples.astype(np.float64) - med
    env = moving_average_abs(centered, 24)
    thr = max(float(np.percentile(env, 90)), 2.8 * mad, 0.45 * p95)
    mask = env >= thr
    peaks: list[int] = []
    values: list[float] = []
    i = 0
    n = mask.size
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i + 1
        while j < n and mask[j]:
            j += 1
        if j - i >= 8:
            local = i + int(np.argmax(np.abs(centered[i:j])))
            value = float(abs(centered[local]))
            if peaks and local - peaks[-1] < 250:
                if value > values[-1]:
                    peaks[-1] = local
                    values[-1] = value
            else:
                peaks.append(local)
                values.append(value)
        i = j + 1
    return np.array(peaks, dtype=np.int32), np.array(values, dtype=np.float64), centered


def estimate_widths(centered: np.ndarray, peaks: np.ndarray, peak_values: np.ndarray) -> np.ndarray:
    widths = []
    n = centered.size
    for peak, amp in zip(peaks, peak_values):
        if amp <= 0:
            widths.append(0)
            continue
        th = max(amp * 0.45, 8.0)
        left = int(peak)
        while left > 0 and abs(centered[left]) >= th and peak - left < 220:
            left -= 1
        right = int(peak)
        while right < n - 1 and abs(centered[right]) >= th and right - peak < 220:
            right += 1
        widths.append(max(0, right - left))
    return np.array(widths, dtype=np.int32)


def div(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


def pct_count(num: int, den: int, pct: float) -> bool:
    return den > 0 and num * 100.0 >= pct * den


def pct_count_le(num: int, den: int, pct: float) -> bool:
    return den == 0 or num * 100.0 <= pct * den


def avg_ge(total: int, den: int, th: float) -> bool:
    return den > 0 and total >= th * den


def avg_le(total: int, den: int, th: float) -> bool:
    return den == 0 or total <= th * den


def row_val(row: dict[str, int | float | str], key: str) -> float:
    value = row.get(key, 0)
    if value in ("", None):
        return 0.0
    return float(value)


def extract_window_features(samples: np.ndarray) -> dict[str, int | float]:
    peaks, peak_values, centered = detect_peaks(samples)
    widths = estimate_widths(centered, peaks, peak_values)
    beat = int(peaks.size)
    rr = np.diff(peaks).astype(np.float64)
    rr_valid = rr[(rr >= 280) & (rr <= 2200)]
    median_rr = float(np.median(rr_valid)) if rr_valid.size else 0.0

    pnn_match = 0
    pnn_mis = 0
    rdm_codes: list[int] = []
    ectopic_pair = 0
    if rr_valid.size >= 2 and median_rr > 0:
        for idx in range(1, rr_valid.size):
            cur = float(rr_valid[idx])
            prev = float(rr_valid[idx - 1])
            pred = prev
            err = abs(cur - pred)
            mismatch = err > max(140.0, 0.18 * pred)
            pnn_mis += int(mismatch)
            pnn_match += int(not mismatch)
            code = int(min(150, round(abs(cur - median_rr) * 100.0 / median_rr)))
            rdm_codes.append(code)
            if idx + 1 < rr_valid.size:
                nxt = float(rr_valid[idx + 1])
                if cur < 0.78 * median_rr and nxt > 1.18 * median_rr:
                    ectopic_pair += 1

    amp_med = float(np.median(peak_values)) if peak_values.size else 0.0
    amp_mad = float(np.median(np.abs(peak_values - amp_med))) + 1.0 if peak_values.size else 1.0
    amp_codes = [int(min(31, max(0, round((v - amp_med + 3 * amp_mad) / max(amp_mad, 1.0) * 2)))) for v in peak_values]
    ram_code_sum = int(sum(amp_codes))
    ram_code_count = int(len(amp_codes))

    qrs_width_abn = int(np.sum((widths > 125) | (widths < 35))) if widths.size else 0
    qrs_energy_abn = int(np.sum(np.abs(peak_values - amp_med) > 2.5 * amp_mad)) if peak_values.size else 0
    qrs_complex_abn = int(np.sum(widths > 165)) if widths.size else 0
    qrs_maf_count = int(np.sum(((widths > 125) | (widths < 35)) | (np.abs(peak_values - amp_med) > 2.5 * amp_mad))) if widths.size else 0

    ds = np.diff(centered[::10])
    slope_sign = np.sign(ds[np.abs(ds) > max(1.0, np.percentile(np.abs(ds), 55) if ds.size else 1.0)])
    dscr_slope = int(slope_sign.size)
    dscr_flip = int(np.sum(slope_sign[1:] * slope_sign[:-1] < 0)) if slope_sign.size > 1 else 0

    rdm_valid = len(rdm_codes)
    rdm_sum = int(sum(rdm_codes))
    rdm_counts = {f"rdm_ge{th}_count": int(sum(code >= th for code in rdm_codes)) for th in range(10, 160, 10)}

    pre_qrs = 0
    env = moving_average_abs(centered, 24)
    for p, amp in zip(peaks, peak_values):
        lo = max(0, int(p) - 220)
        hi = max(0, int(p) - 70)
        if hi > lo and np.max(env[lo:hi]) > max(20.0, 0.28 * amp):
            pre_qrs += 1

    rbbb_delay_valid = beat
    rbbb_delay_wide = int(np.sum(widths > 120)) if widths.size else 0
    rbbb_delay_terminal = int(np.sum(widths > 150)) if widths.size else 0
    rbbb_delay_like = int(np.sum(widths > 135)) if widths.size else 0
    rbbb_delay_segment = int(rbbb_delay_like > 0)
    rbbb_delay_applied = rbbb_delay_like

    eerg_gate = int(pre_qrs > 0)
    eerg_early = int(pre_qrs)
    eerg_ecp = int(ectopic_pair)
    eerg_pnn_decision = pnn_match + pnn_mis
    eerg_pnn_mismatch = pnn_mis
    eerg_rdm_valid = rdm_valid
    eerg_rdm_code_sum = rdm_sum
    eerg_applied = int(eerg_gate and (eerg_early >= 10 or eerg_ecp >= 3))

    row: dict[str, int | float] = {
        "beat_count": beat,
        "pnn_match_count": pnn_match,
        "pnn_mismatch_count": pnn_mis,
        "dscr_flip_count": dscr_flip,
        "dscr_slope_count": dscr_slope,
        "ram_code_sum": ram_code_sum,
        "ram_code_count": ram_code_count,
        "rdm_valid_count": rdm_valid,
        "rdm_code_sum": rdm_sum,
        "ectopic_pair_count": ectopic_pair,
        "pre_qrs_bump_count": pre_qrs,
        "qrs_maf_valid_count": beat,
        "qrs_maf_count": qrs_maf_count,
        "qrs_maf_code_sum": qrs_width_abn + qrs_energy_abn,
        "qrs_width_abn_count": qrs_width_abn,
        "qrs_complex_abn_count": qrs_complex_abn,
        "qrs_energy_abn_count": qrs_energy_abn,
        "qrs_terminal_delay_count": rbbb_delay_terminal,
        "qrs_late_energy_count": 0,
        "qrs_asymmetry_count": 0,
        "qrs_peak_to_tail_count": 0,
        "qrs_pvc_like_count": qrs_width_abn,
        "qrs_rbbb_like_count": rbbb_delay_like,
        "qrs_maf_width_sum": int(np.sum(widths)) if widths.size else 0,
        "qrs_maf_complex_sum": qrs_complex_abn,
        "qrs_maf_energy_sum": int(np.sum(np.clip(np.abs(peak_values - amp_med) / max(amp_mad, 1.0), 0, 31))) if peak_values.size else 0,
        "rbbb_delay_valid_count": rbbb_delay_valid,
        "rbbb_delay_wide_count": rbbb_delay_wide,
        "rbbb_delay_terminal_count": rbbb_delay_terminal,
        "rbbb_delay_like_count": rbbb_delay_like,
        "rbbb_delay_segment_count": rbbb_delay_segment,
        "rbbb_delay_applied_count": rbbb_delay_applied,
        "eerg_gate_count": eerg_gate,
        "eerg_applied_count": eerg_applied,
        "eerg_pre_qrs_bump_count": pre_qrs,
        "eerg_early_count": eerg_early,
        "eerg_ecp_count": eerg_ecp,
        "eerg_pnn_decision_count": eerg_pnn_decision,
        "eerg_pnn_mismatch_count": eerg_pnn_mismatch,
        "eerg_rdm_valid_count": eerg_rdm_valid,
        "eerg_rdm_code_sum": eerg_rdm_code_sum,
    }
    row.update(rdm_counts)
    return row


def add_weight(mem: np.ndarray, weight_map: dict[str, dict[str, int]], key: str) -> None:
    if key in weight_map:
        mem += vec_from_map(weight_map[key])


def c24_mem(row: dict[str, int | float | str], weights: dict) -> np.ndarray:
    mem = vec_from_map(weights["c24_mem_init"]).copy()
    continuous = weights["continuous_event_weights"]
    for key, col in [
        ("PNN_MATCH", "pnn_match_count"),
        ("PNN_MIS", "pnn_mismatch_count"),
        ("DSCR_FLIP", "dscr_flip_count"),
        ("DSCR_SLOPE", "dscr_slope_count"),
        ("RAM_COUNT", "ram_code_count"),
        ("RAM_CODE", "ram_code_sum"),
        ("RDM_VALID", "rdm_valid_count"),
        ("RDM_CODE", "rdm_code_sum"),
        ("ECT_PAIR", "ectopic_pair_count"),
        ("PRE_QRS", "pre_qrs_bump_count"),
        ("QRS_MAF", "qrs_maf_count"),
        ("QRS_WIDTH", "qrs_width_abn_count"),
        ("QRS_COMPLEX", "qrs_complex_abn_count"),
        ("QRS_ENERGY", "qrs_energy_abn_count"),
        ("RBBB_LIKE", "rbbb_delay_like_count"),
        ("RBBB_SEGMENT", "rbbb_delay_segment_count"),
        ("RBBB_APPLIED", "rbbb_delay_applied_count"),
        ("EERG_GATE", "eerg_gate_count"),
        ("EERG_APPLIED", "eerg_applied_count"),
    ]:
        if key in continuous:
            mem += int(row_val(row, col)) * vec_from_map(continuous[key])
    if "SECOND" in continuous:
        mem += 60 * vec_from_map(continuous["SECOND"])

    rdm_level = weights["rdm_level_weights"]
    for th in range(10, 160, 10):
        key = f"rdm_ge{th}"
        mem += int(row_val(row, f"{key}_count")) * vec_from_map(rdm_level[key])

    pden = int(row_val(row, "pnn_match_count") + row_val(row, "pnn_mismatch_count"))
    pmis = int(row_val(row, "pnn_mismatch_count"))
    rn = int(row_val(row, "rdm_valid_count"))
    rsum = int(row_val(row, "rdm_code_sum"))
    ramn = int(row_val(row, "ram_code_count"))
    rams = int(row_val(row, "ram_code_sum"))
    ecp = int(row_val(row, "ectopic_pair_count"))
    if pden and rn and ramn and pmis * 100 >= 12 * pden and pmis * 100 <= 65 * pden and rsum >= 5 * rn and rsum <= 12 * rn and rams >= 12 * ramn and ecp * 100 >= 4 * rn and ecp * 100 <= 35 * rn:
        add_weight(mem, continuous, "ARR_HIGH_IRR")

    binary = weights["binary_feature_weights"]
    beat = int(row_val(row, "beat_count"))
    dscr_flip = int(row_val(row, "dscr_flip_count"))
    dscr_slope = int(row_val(row, "dscr_slope_count"))
    ram_sum = int(row_val(row, "ram_code_sum"))
    ram_n = int(row_val(row, "ram_code_count"))
    qrs_valid = int(row_val(row, "qrs_maf_valid_count"))
    qrs = int(row_val(row, "qrs_maf_count"))
    qrs_width = int(row_val(row, "qrs_width_abn_count"))
    qrs_energy = int(row_val(row, "qrs_energy_abn_count"))
    rbbb_valid = int(row_val(row, "rbbb_delay_valid_count"))
    rbbb_like = int(row_val(row, "rbbb_delay_like_count"))
    rbbb_wide = int(row_val(row, "rbbb_delay_wide_count"))
    rbbb_term = int(row_val(row, "rbbb_delay_terminal_count"))
    pre = int(row_val(row, "pre_qrs_bump_count"))

    for th in [1, 2, 4, 8, 15, 25, 45]:
        if pct_count(pmis, pden, th):
            add_weight(mem, binary, f"pnn_mis_ge_{th:g}")
    for th in [1, 2, 4, 8, 15]:
        if pct_count_le(pmis, pden, th):
            add_weight(mem, binary, f"pnn_mis_le_{th:g}")
    for th in [1, 2, 4, 7, 10, 14]:
        if avg_ge(rsum, rn, th):
            add_weight(mem, binary, f"rdm_avg_ge_{th:g}")
    for th in [1, 2, 4, 7]:
        if avg_le(rsum, rn, th):
            add_weight(mem, binary, f"rdm_avg_le_{th:g}")
    for key in ["rdm_ge20", "rdm_ge50", "rdm_ge80", "rdm_ge100"]:
        num = int(row_val(row, f"{key}_count"))
        for th in [1, 3, 8, 15, 30]:
            if pct_count(num, rn, th):
                add_weight(mem, binary, f"{key}_ge_{th:g}")
    for th in [1, 2, 5, 10, 20]:
        if pct_count(dscr_flip, dscr_slope, th):
            add_weight(mem, binary, f"dscr_ge_{th:g}")
    for th in [1, 2, 5]:
        if pct_count_le(dscr_flip, dscr_slope, th):
            add_weight(mem, binary, f"dscr_le_{th:g}")
    for th in [1, 2, 4, 7, 10, 14]:
        if avg_ge(ram_sum, ram_n, th):
            add_weight(mem, binary, f"ram_ge_{th:g}")
    for th in [1, 2, 4, 7]:
        if avg_le(ram_sum, ram_n, th):
            add_weight(mem, binary, f"ram_le_{th:g}")
    for th in [1, 2, 4, 8, 15, 25]:
        if pct_count(ecp, beat, th):
            add_weight(mem, binary, f"ecp_ge_{th:g}")
    for th in [1, 2, 5, 10]:
        if pct_count(pre, beat, th):
            add_weight(mem, binary, f"pre_ge_{th:g}")
    for th in [1, 3, 8, 20, 40]:
        if pct_count(qrs, qrs_valid, th):
            add_weight(mem, binary, f"qrs_ge_{th:g}")
    for th in [1, 3, 8, 15]:
        if pct_count(qrs_width, qrs_valid, th):
            add_weight(mem, binary, f"qrs_width_ge_{th:g}")
    for th in [1, 3, 8, 20, 40]:
        if pct_count(qrs_energy, qrs_valid, th):
            add_weight(mem, binary, f"qrs_energy_ge_{th:g}")
    for th in [1, 3, 8, 15]:
        if pct_count(rbbb_like, beat, th):
            add_weight(mem, binary, f"rbbb_ge_{th:g}")
        if pct_count(rbbb_wide, rbbb_valid, th):
            add_weight(mem, binary, f"rbbb_wide_ge_{th:g}")
        if pct_count(rbbb_term, rbbb_valid, th):
            add_weight(mem, binary, f"rbbb_terminal_ge_{th:g}")

    if pct_count_le(pmis, pden, 15) and pct_count(rbbb_like, beat, 2):
        add_weight(mem, binary, "gate_regular_rbbb_rescue")
    if pct_count_le(pmis, pden, 15) and (pct_count(qrs_width, qrs_valid, 2) or pct_count(qrs_energy, qrs_valid, 35)):
        add_weight(mem, binary, "gate_regular_qrs_arr_rescue")
    if pct_count(ecp, beat, 3) and pct_count_le(pmis, pden, 35) and avg_le(rsum, rn, 8):
        add_weight(mem, binary, "gate_episodic_ectopic_arr")
    if rbbb_like == 0 and pre >= 1 and (int(row_val(row, "eerg_early_count")) >= 10 or int(row_val(row, "eerg_ecp_count")) >= 3) and pct_count_le(int(row_val(row, "eerg_pnn_mismatch_count")), int(row_val(row, "eerg_pnn_decision_count")), 15) and avg_le(int(row_val(row, "eerg_rdm_code_sum")), int(row_val(row, "eerg_rdm_valid_count")), 5):
        add_weight(mem, binary, "gate_eerg_like")
    if pct_count(pmis, pden, 25) and avg_ge(rsum, rn, 7) and pct_count(ecp, beat, 5):
        add_weight(mem, binary, "gate_aff_persistent_irreg")
    if pct_count(pmis, pden, 5) and pct_count_le(pmis, pden, 30) and avg_ge(rsum, rn, 2) and avg_le(rsum, rn, 9):
        add_weight(mem, binary, "gate_arr_mid_irreg")
    if pct_count_le(dscr_flip, dscr_slope, 3) and pct_count_le(pmis, pden, 20):
        add_weight(mem, binary, "gate_chf_low_dscr_low_irreg")
    if pct_count(dscr_flip, dscr_slope, 5) and pct_count_le(pmis, pden, 15) and avg_le(rsum, rn, 5):
        add_weight(mem, binary, "gate_nsr_high_dscr_low_irreg")
    if avg_ge(ram_sum, ram_n, 10) and pct_count_le(pmis, pden, 20):
        add_weight(mem, binary, "gate_ram_high_regular")
    if avg_le(ram_sum, ram_n, 5) and pct_count(pmis, pden, 15):
        add_weight(mem, binary, "gate_ram_low_irregular")
    return mem


def split_counts(manifest_rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in manifest_rows:
        counts[row["split"]][row["class_label"]] += 1
    return {s: {c: counts[s].get(c, 0) for c in CLASSES} for s in ["train", "val", "test"]}


def manifest_summary(workspace: Path, manifest_rows: list[dict[str, str]]) -> list[dict[str, int | str]]:
    rows = []
    for row in manifest_rows:
        total = int(float(row["total_samples"]))
        valid = max(0, total - SETTLING_SKIP)
        windows = valid // WINDOW_SAMPLES
        mem_path = workspace / row["afe_adc_mem_file"]
        rows.append(
            {
                "split": row["split"],
                "class_label": row["class_label"],
                "record_id": row["record_id"],
                "total_samples": total,
                "valid_window_count": int(windows),
                "mem_file": str(mem_path),
                "exists": int(mem_path.exists()),
                "byte_size_ok": int(mem_path.exists() and mem_path.stat().st_size == total * 4),
            }
        )
    return rows


def build_window_dump(workspace: Path, manifest_rows: list[dict[str, str]], weights: dict, out_dir: Path, force: bool) -> dict[str, list[dict[str, int | float | str]]]:
    dump_paths = {split: out_dir / f"window_snapshot_dump_{split}.csv" for split in ["train", "val", "test"]}
    if not force and all(path.exists() for path in dump_paths.values()):
        return {split: read_csv(path) for split, path in dump_paths.items()}

    by_split: dict[str, list[dict[str, int | float | str]]] = {"train": [], "val": [], "test": []}
    total_records = len(manifest_rows)
    for rec_idx, meta in enumerate(manifest_rows, start=1):
        split = meta["split"]
        label = meta["class_label"]
        record_id = meta["record_id"]
        total = int(float(meta["total_samples"]))
        mem_path = workspace / meta["afe_adc_mem_file"]
        samples = parse_mem_file(mem_path)
        usable = max(0, min(samples.size, total) - SETTLING_SKIP)
        windows = usable // WINDOW_SAMPLES
        print(f"[window] {rec_idx:02d}/{total_records} {split}/{label}/{record_id}: {windows} windows", flush=True)
        for window_id in range(windows):
            start = SETTLING_SKIP + window_id * WINDOW_SAMPLES
            end = start + WINDOW_SAMPLES
            feat = extract_window_features(samples[start:end])
            mem = c24_mem(feat, weights)
            pred = int(np.argmax(mem))
            sorted_mem = np.sort(mem)
            margin = int(sorted_mem[-1] - sorted_mem[-2])
            pden = int(feat["pnn_match_count"] + feat["pnn_mismatch_count"])
            rdm_n = int(feat["rdm_valid_count"])
            ram_n = int(feat["ram_code_count"])
            qrs_n = int(feat["qrs_maf_valid_count"])
            row = {
                "split": split,
                "record_id": record_id,
                "true_record_class": label,
                "true_class_id": CLASS_TO_ID[label],
                "window_id": window_id,
                "start_sample": start,
                "end_sample": end,
                "pred_class": CLASSES[pred],
                "pred_class_id": pred,
                "class_mem_NSR": int(mem[0]),
                "class_mem_CHF": int(mem[1]),
                "class_mem_ARR": int(mem[2]),
                "class_mem_AFF": int(mem[3]),
                "top_margin": margin,
                "pnn_mismatch_rate": 100.0 * div(float(feat["pnn_mismatch_count"]), pden),
                "rdm_avg": div(float(feat["rdm_code_sum"]), rdm_n),
                "dscr_flip_rate": 100.0 * div(float(feat["dscr_flip_count"]), float(feat["dscr_slope_count"])),
                "ram_avg": div(float(feat["ram_code_sum"]), ram_n),
                "ecp_rate": 100.0 * div(float(feat["ectopic_pair_count"]), float(feat["beat_count"])),
                "qrs_maf_rate": 100.0 * div(float(feat["qrs_maf_count"]), qrs_n),
                "qrs_width_rate": 100.0 * div(float(feat["qrs_width_abn_count"]), qrs_n),
                "qrs_energy_rate": 100.0 * div(float(feat["qrs_energy_abn_count"]), qrs_n),
                "rbbb_like_rate": 100.0 * div(float(feat["rbbb_delay_like_count"]), float(feat["beat_count"])),
                "aff_like_spike": int(pct_count(int(feat["pnn_mismatch_count"]), pden, 25) and avg_ge(int(feat["rdm_code_sum"]), rdm_n, 7)),
                "arr_burst_spike": int(pct_count(int(feat["ectopic_pair_count"]), int(feat["beat_count"]), 2) or pct_count(int(feat["qrs_maf_count"]), qrs_n, 8)),
                "chf_morph_spike": int(avg_le(int(feat["ram_code_sum"]), ram_n, 6) and pct_count_le(int(feat["pnn_mismatch_count"]), pden, 20)),
                "nsr_stable_spike": int(pred == 0 and pct_count_le(int(feat["pnn_mismatch_count"]), pden, 8) and avg_le(int(feat["rdm_code_sum"]), rdm_n, 5) and pct_count_le(int(feat["qrs_maf_count"]), qrs_n, 3)),
            }
            row.update(feat)
            by_split[split].append(row)

    for split, path in dump_paths.items():
        write_csv(path, by_split[split])
    return by_split


def class_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[list[dict[str, int | float | str]], np.ndarray, float, float, float]:
    cm = np.zeros((4, 4), dtype=np.int64)
    for actual, pred in zip(y_true, y_pred):
        cm[int(actual), int(pred)] += 1
    rows = []
    f1s = []
    recalls = []
    for i, cls in enumerate(CLASSES):
        tp = int(cm[i, i])
        pred_n = int(cm[:, i].sum())
        true_n = int(cm[i, :].sum())
        precision = tp / pred_n if pred_n else 0.0
        recall = tp / true_n if true_n else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows.append({"class": cls, "precision": precision, "recall": recall, "f1": f1, "support": true_n, "correct": tp})
        f1s.append(f1)
        recalls.append(recall)
    accuracy = float((y_true == y_pred).mean()) if len(y_true) else 0.0
    return rows, cm, accuracy, float(np.mean(f1s)), float(np.mean(recalls))


def confusion_rows(cm: np.ndarray) -> list[dict[str, int | str]]:
    return [{"actual": CLASSES[i], **{CLASSES[j]: int(cm[i, j]) for j in range(4)}} for i in range(4)]


def window_event_vector(row: dict[str, str | int | float], margin_th: int, use_rates: bool) -> tuple[np.ndarray, list[str]]:
    pred = int(float(row["pred_class_id"]))
    mem = np.array([float(row[f"class_mem_{cls}"]) for cls in CLASSES], dtype=np.float64)
    shifted = mem - float(np.max(mem))
    margin = int(float(row["top_margin"]))
    names: list[str] = ["window_bias"]
    vals: list[float] = [1.0]
    for cls_idx, cls in enumerate(CLASSES):
        names.append(f"pred_{cls}")
        vals.append(1.0 if pred == cls_idx else 0.0)
    if margin >= margin_th:
        names.append(f"conf_pred_{CLASSES[pred]}")
        vals.append(1.0)
    else:
        names.append("low_confidence")
        vals.append(1.0)
    for cls_idx, cls in enumerate(CLASSES):
        names.append(f"scorebin_{cls}")
        vals.append(max(0.0, min(3.0, (shifted[cls_idx] + margin_th * 3.0) / max(margin_th, 1))))

    evidence_cols = [
        "aff_like_spike",
        "arr_burst_spike",
        "chf_morph_spike",
        "nsr_stable_spike",
    ]
    for col in evidence_cols:
        names.append(col)
        vals.append(float(row.get(col, 0) or 0))

    if use_rates:
        rate_cols = [
            "pnn_mismatch_rate",
            "rdm_avg",
            "dscr_flip_rate",
            "ram_avg",
            "ecp_rate",
            "qrs_maf_rate",
            "qrs_width_rate",
            "qrs_energy_rate",
            "rbbb_like_rate",
        ]
        for col in rate_cols:
            names.append(f"rate_{col}")
            vals.append(float(row.get(col, 0) or 0) / 100.0)
    return np.array(vals, dtype=np.float64), names


def aggregate_records(rows_by_split: dict[str, list[dict[str, str]]], margin_th: int, use_rates: bool) -> tuple[dict[str, dict], list[str]]:
    result: dict[str, dict] = {}
    feature_names: list[str] | None = None
    for split, rows in rows_by_split.items():
        by_record: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            by_record[str(row["record_id"])].append(row)
        rec_rows = []
        X = []
        y = []
        for record_id in sorted(by_record):
            rec = by_record[record_id]
            agg = None
            names = None
            for row in rec:
                v, names = window_event_vector(row, margin_th, use_rates)
                agg = v if agg is None else agg + v
            assert agg is not None and names is not None
            if feature_names is None:
                feature_names = names
            rec_rows.append(
                {
                    "split": split,
                    "record_id": record_id,
                    "true_class": rec[0]["true_record_class"],
                    "true_class_id": int(float(rec[0]["true_class_id"])),
                    "valid_window_count": len(rec),
                }
            )
            X.append(agg / max(1, len(rec)))
            y.append(int(float(rec[0]["true_class_id"])))
        result[split] = {"records": rec_rows, "X": np.vstack(X), "y": np.array(y, dtype=np.int64)}
    return result, list(feature_names or [])


def fit_ridge(X: np.ndarray, y: np.ndarray, l2: float, boosts: dict[int, float]) -> np.ndarray:
    n, d = X.shape
    Y = np.full((n, 4), -1.0, dtype=np.float64)
    Y[np.arange(n), y] = 1.0
    sw = np.ones(n, dtype=np.float64)
    for cls, boost in boosts.items():
        sw[y == cls] *= boost
    root = np.sqrt(sw)[:, None]
    Xa = np.hstack([X, np.ones((n, 1), dtype=np.float64)])
    Xw = Xa * root
    Yw = Y * root
    reg = np.eye(d + 1, dtype=np.float64) * l2
    reg[-1, -1] = l2 * 0.01
    return np.linalg.solve(Xw.T @ Xw + reg, Xw.T @ Yw)


def predict_scores(X: np.ndarray, coef: np.ndarray) -> np.ndarray:
    Xa = np.hstack([X, np.ones((X.shape[0], 1), dtype=np.float64)])
    return Xa @ coef


def metric_dict(y: np.ndarray, scores: np.ndarray) -> dict:
    pred = np.argmax(scores, axis=1)
    class_rows, cm, acc, macro_f1, bal_acc = class_metrics(y, pred)
    return {
        "record_accuracy": acc,
        "record_correct": int((pred == y).sum()),
        "record_total": int(len(y)),
        "macro_f1": macro_f1,
        "balanced_accuracy": bal_acc,
        "class_metrics": class_rows,
        "confusion": cm,
        "pred": pred,
    }


def objective(m: dict) -> float:
    recalls = {row["class"]: float(row["recall"]) for row in m["class_metrics"]}
    min_recall = min(recalls.values()) if recalls else 0.0
    return 1.4 * m["macro_f1"] + 1.1 * m["balanced_accuracy"] + 0.6 * m["record_accuracy"] + 0.4 * min_recall


def quantize_membrane_weights(coef: np.ndarray, scale: int = 2048) -> np.ndarray:
    return np.rint(coef * scale).astype(np.int64)


def evaluate_quantized(X: np.ndarray, qcoef: np.ndarray) -> np.ndarray:
    Xi = np.rint(X * 1024).astype(np.int64)
    qw = qcoef[:-1, :]
    qb = qcoef[-1, :] * 1024
    return Xi @ qw + qb


def train_final_layer(rows_by_split: dict[str, list[dict[str, str]]], out_dir: Path) -> dict:
    search_rows = []
    best = None
    cid = 0
    for margin_th in [1_000_000, 5_000_000, 10_000_000, 25_000_000, 50_000_000, 100_000_000]:
        for use_rates in [0, 1]:
            data, names = aggregate_records(rows_by_split, margin_th, bool(use_rates))
            Xtr = data["train"]["X"]
            ytr = data["train"]["y"]
            Xv = data["val"]["X"]
            yv = data["val"]["y"]
            mean = Xtr.mean(axis=0)
            std = Xtr.std(axis=0)
            std[std < 1e-9] = 1.0
            Xtrn = (Xtr - mean) / std
            Xvn = (Xv - mean) / std
            for l2 in [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]:
                for nsr_boost in [0.8, 1.0, 1.2]:
                    for chf_boost in [0.9, 1.2, 1.6, 2.0]:
                        for arr_boost in [0.9, 1.2, 1.6, 2.0]:
                            for aff_boost in [0.9, 1.2, 1.6, 2.0]:
                                boosts = {0: nsr_boost, 1: chf_boost, 2: arr_boost, 3: aff_boost}
                                coef = fit_ridge(Xtrn, ytr, l2, boosts)
                                tm = metric_dict(ytr, predict_scores(Xtrn, coef))
                                vm = metric_dict(yv, predict_scores(Xvn, coef))
                                obj = objective(vm)
                                row = {
                                    "candidate_id": cid,
                                    "margin_threshold": margin_th,
                                    "use_rates": use_rates,
                                    "l2": l2,
                                    "nsr_boost": nsr_boost,
                                    "chf_boost": chf_boost,
                                    "arr_boost": arr_boost,
                                    "aff_boost": aff_boost,
                                    "objective": obj,
                                    "train_record_accuracy": tm["record_accuracy"],
                                    "train_macro_f1": tm["macro_f1"],
                                    "train_balanced_accuracy": tm["balanced_accuracy"],
                                    "val_record_accuracy": vm["record_accuracy"],
                                    "val_macro_f1": vm["macro_f1"],
                                    "val_balanced_accuracy": vm["balanced_accuracy"],
                                }
                                for cr in vm["class_metrics"]:
                                    row[f"val_{cr['class']}_recall"] = cr["recall"]
                                search_rows.append(row)
                                key = (
                                    obj,
                                    vm["macro_f1"],
                                    vm["balanced_accuracy"],
                                    vm["record_accuracy"],
                                    -max(0.0, tm["record_accuracy"] - vm["record_accuracy"]),
                                )
                                if best is None or key > best["key"]:
                                    best = {
                                        "key": key,
                                        "candidate_id": cid,
                                        "margin_threshold": margin_th,
                                        "use_rates": bool(use_rates),
                                        "l2": l2,
                                        "boosts": boosts,
                                        "coef": coef,
                                        "mean": mean,
                                        "std": std,
                                        "feature_names": names,
                                        "train": tm,
                                        "val": vm,
                                    }
                                cid += 1
    assert best is not None
    search_rows.sort(key=lambda r: (r["objective"], r["val_macro_f1"], r["val_balanced_accuracy"], r["val_record_accuracy"]), reverse=True)
    write_csv(out_dir / "final_layer_search_train_val.csv", search_rows)

    all_data, _ = aggregate_records(rows_by_split, best["margin_threshold"], best["use_rates"])
    final = {}
    qcoef = quantize_membrane_weights(best["coef"])
    for split in ["train", "val", "test"]:
        X = all_data[split]["X"]
        Xn = (X - best["mean"]) / best["std"]
        scores = predict_scores(Xn, best["coef"])
        m = metric_dict(all_data[split]["y"], scores)
        q_scores = evaluate_quantized(Xn, qcoef)
        q_pred = np.argmax(q_scores, axis=1)
        pred = np.argmax(scores, axis=1)
        m["float_vs_fixed_mismatch"] = int(np.sum(pred != q_pred))
        final[split] = m

        pred_rows = []
        for idx, rec in enumerate(all_data[split]["records"]):
            pred_rows.append(
                {
                    **rec,
                    "pred_class": CLASSES[int(pred[idx])],
                    "pred_class_id": int(pred[idx]),
                    "correct": int(pred[idx] == int(rec["true_class_id"])),
                    "fixed_pred_class": CLASSES[int(q_pred[idx])],
                    "fixed_match": int(pred[idx] == q_pred[idx]),
                    "patient_mem_NSR": float(scores[idx, 0]),
                    "patient_mem_CHF": float(scores[idx, 1]),
                    "patient_mem_ARR": float(scores[idx, 2]),
                    "patient_mem_AFF": float(scores[idx, 3]),
                }
            )
        write_csv(out_dir / f"final_layer_{split}_record_predictions.csv", pred_rows)
        write_csv(out_dir / f"final_layer_{split}_confusion_matrix.csv", confusion_rows(m["confusion"]))
        if split == "val":
            write_csv(out_dir / "final_layer_validation_record_predictions.csv", pred_rows)
            write_csv(out_dir / "final_layer_validation_confusion_matrix.csv", confusion_rows(m["confusion"]))

    selected = {
        "selection_policy": "Train/validation only. Snapshot C24 fixed; patient-level membrane layer only is trained. Test is evaluated once after selection.",
        "candidate_id": best["candidate_id"],
        "margin_threshold": best["margin_threshold"],
        "use_rates": best["use_rates"],
        "l2": best["l2"],
        "boosts": {CLASSES[k]: v for k, v in best["boosts"].items()},
        "feature_names": best["feature_names"],
        "normalization": {
            "mean": {name: float(best["mean"][i]) for i, name in enumerate(best["feature_names"])},
            "std": {name: float(best["std"][i]) for i, name in enumerate(best["feature_names"])},
        },
        "float_weights": {
            name: {cls: float(best["coef"][i, ci]) for ci, cls in enumerate(CLASSES)}
            for i, name in enumerate(best["feature_names"] + ["record_bias"])
        },
        "fixed_point": {
            "feature_scale": 1024,
            "weight_scale": 2048,
            "weights": {
                name: {cls: int(qcoef[i, ci]) for ci, cls in enumerate(CLASSES)}
                for i, name in enumerate(best["feature_names"] + ["record_bias"])
            },
        },
    }
    (out_dir / "final_layer_selected_params.json").write_text(json.dumps(selected, indent=2), encoding="utf-8",)

    for split in ["train", "val", "test"]:
        metrics_json = {
            "record_accuracy": final[split]["record_accuracy"],
            "record_correct": final[split]["record_correct"],
            "record_total": final[split]["record_total"],
            "macro_f1": final[split]["macro_f1"],
            "balanced_accuracy": final[split]["balanced_accuracy"],
            "class_metrics": final[split]["class_metrics"],
            "float_vs_fixed_mismatch": final[split]["float_vs_fixed_mismatch"],
        }
        (out_dir / f"final_layer_{split}_metrics.json").write_text(json.dumps(metrics_json, indent=2), encoding="utf-8")
        if split == "val":
            (out_dir / "final_layer_validation_metrics.json").write_text(json.dumps(metrics_json, indent=2), encoding="utf-8")

    return {"best": best, "final": final}


def baseline_record_predictions(rows_by_split: dict[str, list[dict[str, str]]], out_dir: Path) -> dict[str, dict]:
    results: dict[str, dict] = {}
    summary_rows = []
    for split, rows in rows_by_split.items():
        by_record: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            by_record[str(row["record_id"])].append(row)
        for mode in ["majority_vote", "mean_c24_mem"]:
            y_true = []
            y_pred = []
            pred_rows = []
            for record_id in sorted(by_record):
                rec = by_record[record_id]
                true = int(float(rec[0]["true_class_id"]))
                if mode == "majority_vote":
                    counts = np.zeros(4, dtype=np.float64)
                    for row in rec:
                        counts[int(float(row["pred_class_id"]))] += 1.0
                    pred = int(np.argmax(counts))
                    scores = counts
                else:
                    mem = np.zeros(4, dtype=np.float64)
                    for row in rec:
                        mem += np.array([float(row[f"class_mem_{cls}"]) for cls in CLASSES], dtype=np.float64)
                    scores = mem / max(1, len(rec))
                    pred = int(np.argmax(scores))
                y_true.append(true)
                y_pred.append(pred)
                pred_rows.append(
                    {
                        "split": split,
                        "baseline": mode,
                        "record_id": record_id,
                        "true_class": CLASSES[true],
                        "pred_class": CLASSES[pred],
                        "correct": int(true == pred),
                        "valid_window_count": len(rec),
                        "score_NSR": float(scores[0]),
                        "score_CHF": float(scores[1]),
                        "score_ARR": float(scores[2]),
                        "score_AFF": float(scores[3]),
                    }
                )
            yt = np.array(y_true, dtype=np.int64)
            yp = np.array(y_pred, dtype=np.int64)
            class_rows, cm, acc, macro_f1, bal_acc = class_metrics(yt, yp)
            results[f"{split}_{mode}"] = {
                "record_accuracy": acc,
                "record_correct": int((yt == yp).sum()),
                "record_total": int(len(yt)),
                "macro_f1": macro_f1,
                "balanced_accuracy": bal_acc,
                "class_metrics": class_rows,
                "confusion": cm,
            }
            summary_rows.append(
                {
                    "split": split,
                    "baseline": mode,
                    "record_accuracy": acc,
                    "record_correct": int((yt == yp).sum()),
                    "record_total": int(len(yt)),
                    "macro_f1": macro_f1,
                    "balanced_accuracy": bal_acc,
                }
            )
            write_csv(out_dir / f"baseline_{mode}_{split}_record_predictions.csv", pred_rows)
            write_csv(out_dir / f"baseline_{mode}_{split}_confusion_matrix.csv", confusion_rows(cm))
    write_csv(out_dir / "baseline_record_metrics.csv", summary_rows)
    return results


def write_report(out_dir: Path, manifest_counts: dict, record_summary: list[dict], result: dict, baselines: dict[str, dict]) -> None:
    lines = [
        "# Patient-Level Membrane Layer Python Equivalent",
        "",
        "## Dataset",
        "",
        "| split | NSR | CHF | ARR | AFF | total | windows |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    windows_by_split = Counter()
    records_by_split = Counter()
    for row in record_summary:
        windows_by_split[row["split"]] += int(row["valid_window_count"])
        records_by_split[row["split"]] += 1
    for split in ["train", "val", "test"]:
        c = manifest_counts[split]
        lines.append(f"| {split} | {c['NSR']} | {c['CHF']} | {c['ARR']} | {c['AFF']} | {records_by_split[split]} | {windows_by_split[split]} |")

    best = result["best"]
    lines += [
        "",
        "## Selected Final Layer",
        "",
        f"- candidate_id: {best['candidate_id']}",
        f"- margin_threshold: {best['margin_threshold']}",
        f"- use_rates: {best['use_rates']}",
        f"- l2: {best['l2']}",
        f"- boosts: { {CLASSES[k]: v for k, v in best['boosts'].items()} }",
        "- structure: each 60 s Snapshot C24 window emits pred/confidence/evidence spikes; patient_mem[4] accumulates learned signed integer weights; record_done uses WTA.",
        "",
        "## Metrics",
        "",
        "| split | accuracy | correct/total | macro-F1 | balanced accuracy | fixed mismatch |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for split in ["train", "val", "test"]:
        m = result["final"][split]
        lines.append(
            f"| {split} | {m['record_accuracy']:.4f} | {m['record_correct']}/{m['record_total']} | {m['macro_f1']:.4f} | {m['balanced_accuracy']:.4f} | {m['float_vs_fixed_mismatch']} |"
        )
    lines += [
        "",
        "## Baselines",
        "",
        "| split | baseline | accuracy | correct/total | macro-F1 | balanced accuracy |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for split in ["train", "val", "test"]:
        for mode in ["majority_vote", "mean_c24_mem"]:
            m = baselines[f"{split}_{mode}"]
            lines.append(
                f"| {split} | {mode} | {m['record_accuracy']:.4f} | {m['record_correct']}/{m['record_total']} | {m['macro_f1']:.4f} | {m['balanced_accuracy']:.4f} |"
            )
    lines += [
        "",
        "## Notes",
        "",
        "- Snapshot C24 weights are fixed from `results/c24_rtl_equivalence/c24_folded_weights_for_rtl.json`.",
        "- This is a Python equivalent exploration of the patient-level final layer, not an RTL/XSim equivalence result.",
        "- Test-set records are evaluated only after selecting the final-layer candidate from train/validation.",
    ]
    (out_dir / "patient_membrane_layer_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--force-window-dump", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    out_dir = workspace / "results" / "patient_membrane_layer"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = workspace / "fullrec_afe" / "fullrec_manifest.csv"
    weights_path = workspace / "results" / "c24_rtl_equivalence" / "c24_folded_weights_for_rtl.json"

    manifest_rows = read_csv(manifest_path)
    counts = split_counts(manifest_rows)
    summary = manifest_summary(workspace, manifest_rows)
    write_csv(out_dir / "fullrec_record_window_summary.csv", summary)
    missing = [row for row in summary if not row["exists"]]
    bad_size = [row for row in summary if not row["byte_size_ok"]]
    if missing or bad_size:
        raise SystemExit(f"fullrec_afe verification failed: missing={len(missing)} byte_size_bad={len(bad_size)}")

    weights = load_weights(weights_path)
    rows_by_split = build_window_dump(workspace, manifest_rows, weights, out_dir, args.force_window_dump)
    baselines = baseline_record_predictions(rows_by_split, out_dir)
    result = train_final_layer(rows_by_split, out_dir)
    write_report(out_dir, counts, summary, result, baselines)

    print("[done] patient membrane layer outputs:", out_dir)
    for split in ["train", "val", "test"]:
        m = result["final"][split]
        print(
            f"[metrics] {split}: acc={m['record_accuracy']:.4f} correct={m['record_correct']}/{m['record_total']} "
            f"macro_f1={m['macro_f1']:.4f} bal_acc={m['balanced_accuracy']:.4f} fixed_mismatch={m['float_vs_fixed_mismatch']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
