from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


ADC_WIDTH = 12
QRS_MEM_W = 12
QRS_REF_W = 10
CLASSES = ("NSR", "CHF", "ARR", "AFF")
CLASS_SCORE_RTL = Path(__file__).resolve().parents[1] / "rtl" / "core" / "class_score_neurons.v"


def s12_from_hex_mem(path: Path) -> np.ndarray:
    raw = np.fromfile(path, dtype=np.uint8)
    if raw.size % 4 != 0:
        raise ValueError(f"{path} byte size is not a multiple of 4")
    a = raw.reshape((-1, 4))[:, :3]
    n = np.empty_like(a)
    digit = (a >= ord("0")) & (a <= ord("9"))
    upper = (a >= ord("A")) & (a <= ord("F"))
    lower = (a >= ord("a")) & (a <= ord("f"))
    ok = digit | upper | lower
    if not np.all(ok):
        raise ValueError(f"{path} contains non-hex sample text")
    n[digit] = a[digit] - ord("0")
    n[upper] = a[upper] - ord("A") + 10
    n[lower] = a[lower] - ord("a") + 10
    u = ((n[:, 0].astype(np.uint16) << 8) | (n[:, 1].astype(np.uint16) << 4) | n[:, 2].astype(np.uint16))
    signed = u.astype(np.int16)
    signed[u >= 0x800] -= 0x1000
    return signed


def sat_u(value: int, width: int) -> int:
    mask = (1 << width) - 1
    return int(value) & mask


def to_signed(value: int, width: int) -> int:
    value &= (1 << width) - 1
    sign = 1 << (width - 1)
    return value - (1 << width) if value & sign else value


def to_unsigned(value: int, width: int) -> int:
    return int(value) & ((1 << width) - 1)


def abs_signed(value: int) -> int:
    return -value if value < 0 else value


_SIGNED_RE = re.compile(r"(?P<sign>-?)\s*(?P<bits>\d+)'sd(?P<value>\d+)")


def parse_verilog_signed(token: str) -> int:
    m = _SIGNED_RE.search(token)
    if not m:
        raise ValueError(f"cannot parse Verilog signed literal: {token}")
    value = int(m.group("value"))
    return -value if m.group("sign") == "-" else value


def load_class_score_constants() -> tuple[dict[str, int], dict[str, list[int]], dict[str, list[int]]]:
    text = CLASS_SCORE_RTL.read_text(encoding="utf-8")
    consts: dict[str, int] = {}
    for m in re.finditer(r"localparam\s+signed\s+\[[^\]]+\]\s+(\w+)\s*=\s*([^;]+);", text):
        if "'sd" in m.group(2):
            consts[m.group(1)] = parse_verilog_signed(m.group(2))

    c24_rdm: dict[str, list[int]] = {}
    local_rdm: dict[str, list[int]] = {}
    for cls in CLASSES:
        cls_l = cls.lower()
        fm = re.search(
            rf"function\s+signed\s+\[63:0\]\s+c24_rdm_level_{cls_l};(?P<body>.*?)endfunction",
            text,
            re.S,
        )
        if not fm:
            raise ValueError(f"missing c24_rdm_level_{cls_l}")
        arr = [0] * 15
        for idx, val in re.findall(rf"(\d+):\s*c24_rdm_level_{cls_l}\s*=\s*([^;]+);", fm.group("body")):
            arr[int(idx)] = parse_verilog_signed(val)
        c24_rdm[cls] = arr

        lm = re.search(
            rf"function\s+signed\s+\[SCORE_WIDTH-1:0\]\s+w_rdm_ge_{cls_l};(?P<body>.*?)endfunction",
            text,
            re.S,
        )
        if not lm:
            raise ValueError(f"missing w_rdm_ge_{cls_l}")
        larr = [0] * 15
        for idx, val in re.findall(rf"(\d+):\s*w_rdm_ge_{cls_l}\s*=\s*([^;]+);", lm.group("body")):
            larr[int(idx)] = parse_verilog_signed(val)
        local_rdm[cls] = larr
    return consts, c24_rdm, local_rdm


_CLASS_CONSTS, _C24_RDM_LEVEL, _LOCAL_RDM_GE = load_class_score_constants()


def c24_ge_pct(num: int, den: int, th: int) -> bool:
    return den != 0 and num * 100 >= den * th


def c24_le_pct(num: int, den: int, th: int) -> bool:
    return den == 0 or num * 100 <= den * th


def c24_ge_avg(total: int, den: int, th: int) -> bool:
    return den != 0 and total >= den * th


def c24_le_avg(total: int, den: int, th: int) -> bool:
    return den == 0 or total <= den * th


def scale_q4_from_ticks(ticks: int) -> int:
    for scale, limit in enumerate(range(3750, 56251, 3750), start=1):
        if ticks <= limit:
            return scale
    return 16


def scale_score_q4(score: int, scale_q4: int) -> int:
    return (score * scale_q4) >> 4


@dataclass
class EcgEventEncoderAdaptive:
    t_event: int = 5
    t_slope: int = 4
    enable_amp_event: int = 0
    t_amp_event: int = 4
    enable_adaptive: int = 1
    adapt_use_bank: int = 1
    adapt_calib_samples: int = 2000
    adapt_min_event_th: int = 4
    adapt_pct_target: int = 1900
    adapt_target_event_count: int = 100
    bank_thresholds: tuple[int, ...] = (4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 40, 48)

    prev_sample: int = 0
    delta: int = 0
    abs_delta: int = 0
    sample_seen: int = 0
    strong_event: int = 0
    up_event: int = 0
    down_event: int = 0
    slope_valid: int = 0
    adaptive_ready: int = 0
    adaptive_event_th: int = 5
    calib_count: int = 0
    hist: list[int] = field(default_factory=lambda: [0] * 64)
    bank_count: list[int] = field(default_factory=lambda: [0] * 12)

    def reset(self) -> None:
        self.prev_sample = 0
        self.delta = 0
        self.abs_delta = 0
        self.sample_seen = 0
        self.strong_event = 0
        self.up_event = 0
        self.down_event = 0
        self.slope_valid = 0
        self.adaptive_ready = 0
        self.adaptive_event_th = self.t_event & 0xFF
        self.calib_count = 0
        self.hist = [0] * 64
        self.bank_count = [0] * 12

    def tick(self, sample_valid: int, segment_start: int, adc_data: int) -> None:
        old_prev = self.prev_sample
        old_sample_seen = self.sample_seen
        old_ready = self.adaptive_ready
        old_event_th = self.adaptive_event_th
        old_calib = self.calib_count
        old_hist = self.hist[:]
        old_bank = self.bank_count[:]

        next_prev = self.prev_sample
        next_delta = self.delta
        next_abs_delta = self.abs_delta
        next_sample_seen = self.sample_seen
        next_strong = 0
        next_up = 0
        next_down = 0
        next_slope_valid = 0
        next_ready = self.adaptive_ready
        next_event_th = self.adaptive_event_th
        next_calib = self.calib_count
        next_hist = self.hist[:]
        next_bank = self.bank_count[:]

        if segment_start:
            next_ready = 0
            next_event_th = self.t_event & 0xFF
            next_calib = 0
            next_hist = [0] * 64
            next_bank = [0] * 12

        if sample_valid:
            if not old_sample_seen:
                next_prev = int(adc_data)
                next_delta = 0
                next_abs_delta = 0
                next_sample_seen = 1
            else:
                delta_calc = int(adc_data) - int(old_prev)
                abs_delta_calc = abs_signed(delta_calc)
                abs_adc = abs_signed(int(adc_data))
                abs_prev = abs_signed(int(old_prev))
                amp_cross_event = bool(self.enable_amp_event and abs_adc > self.t_amp_event and abs_prev <= self.t_amp_event)
                active_th = old_event_th if (self.enable_adaptive and old_ready) else (self.t_event & 0xFF)
                next_prev = int(adc_data)
                next_delta = delta_calc
                next_abs_delta = abs_delta_calc
                next_strong = int((abs_delta_calc > active_th) or amp_cross_event)
                if delta_calc > self.t_slope:
                    next_up = 1
                    next_slope_valid = 1
                elif delta_calc < -self.t_slope:
                    next_down = 1
                    next_slope_valid = 1

                if self.enable_adaptive and not old_ready:
                    if old_calib < self.adapt_calib_samples:
                        hist_bin = 63 if (abs_delta_calc >> 6) != 0 else (abs_delta_calc & 0x3F)
                        next_hist[hist_bin] = sat_u(next_hist[hist_bin] + 1, 16)
                        for i, th in enumerate(self.bank_thresholds):
                            if abs_delta_calc > th:
                                next_bank[i] = sat_u(next_bank[i] + 1, 16)
                        next_calib = sat_u(old_calib + 1, 16)

                    if old_calib == self.adapt_calib_samples - 1:
                        if self.adapt_use_bank:
                            selected = self.bank_thresholds[-1]
                            for i, th in enumerate(self.bank_thresholds):
                                if old_bank[i] <= self.adapt_target_event_count:
                                    selected = th
                                    break
                            next_event_th = max(selected, self.adapt_min_event_th) & 0xFF
                        else:
                            accum = 0
                            pct_bin = self.adapt_min_event_th & 0x3F
                            found = False
                            for i, count in enumerate(old_hist):
                                accum = sat_u(accum + count, 16)
                                if not found and accum >= self.adapt_pct_target:
                                    pct_bin = i
                                    found = True
                            next_event_th = max(pct_bin, self.adapt_min_event_th) & 0xFF
                        next_ready = 1

        self.prev_sample = int(next_prev)
        self.delta = int(next_delta)
        self.abs_delta = int(next_abs_delta)
        self.sample_seen = int(next_sample_seen)
        self.strong_event = int(next_strong)
        self.up_event = int(next_up)
        self.down_event = int(next_down)
        self.slope_valid = int(next_slope_valid)
        self.adaptive_ready = int(next_ready)
        self.adaptive_event_th = int(next_event_th)
        self.calib_count = int(next_calib)
        self.hist = next_hist
        self.bank_count = next_bank


@dataclass
class QrsLifDetector:
    w_event: int = 8
    leak_qrs: int = 0
    t_qrs: int = 16
    t_ref: int = 280

    qrs_mem: int = 0
    refractory_cnt: int = 0
    beat_spike: int = 0

    def reset(self) -> None:
        self.qrs_mem = 0
        self.refractory_cnt = 0
        self.beat_spike = 0

    def tick(self, sample_valid: int, strong_event: int) -> None:
        qrs_mem_next = self.qrs_mem
        refractory_next = self.refractory_cnt
        beat_next = 0
        if sample_valid:
            if self.refractory_cnt != 0:
                qrs_mem_next = 0
                refractory_next = sat_u(self.refractory_cnt - 1, QRS_REF_W)
            else:
                if self.qrs_mem > self.leak_qrs:
                    mem_after_leak = self.qrs_mem - self.leak_qrs
                else:
                    mem_after_leak = 0
                mem_after_event = mem_after_leak + self.w_event if strong_event else mem_after_leak
                if mem_after_event >= self.t_qrs:
                    beat_next = 1
                    qrs_mem_next = 0
                    refractory_next = self.t_ref & ((1 << QRS_REF_W) - 1)
                else:
                    qrs_mem_next = mem_after_event & ((1 << QRS_MEM_W) - 1)
        self.qrs_mem = int(qrs_mem_next)
        self.refractory_cnt = int(refractory_next)
        self.beat_spike = int(beat_next)


@dataclass
class PnnRhythmPredictor:
    num_hyp: int = 46
    age_width: int = 12
    base_delay: int = 250
    delay_step: int = 50
    window_half: int = 125

    token_active: int = 0
    token_age: int = 0
    rr_interval: int = 0
    winner_id: int = 0
    predictor_id: int = 0
    winner_valid: int = 0
    predictor_valid: int = 0
    winner_error: int = (1 << 12) - 1
    predictor_error: int = (1 << 12) - 1
    pnn_match_spike: int = 0
    pnn_mismatch_spike: int = 0
    evaluating: int = 0
    eval_idx: int = 0
    eval_age: int = 0
    eval_best_id: int = 0
    eval_best_err: int = (1 << 12) - 1
    eval_predictor_id: int = 0
    eval_predictor_valid: int = 0

    @property
    def max_age(self) -> int:
        return (1 << self.age_width) - 1

    def reset(self) -> None:
        self.token_active = 0
        self.token_age = 0
        self.rr_interval = 0
        self.winner_id = 0
        self.predictor_id = 0
        self.winner_valid = 0
        self.predictor_valid = 0
        self.winner_error = self.max_age
        self.predictor_error = self.max_age
        self.pnn_match_spike = 0
        self.pnn_mismatch_spike = 0
        self.evaluating = 0
        self.eval_idx = 0
        self.eval_age = 0
        self.eval_best_id = 0
        self.eval_best_err = self.max_age
        self.eval_predictor_id = 0
        self.eval_predictor_valid = 0

    def sat_age_inc(self, value: int) -> int:
        return value if value == self.max_age else value + 1

    def hyp_center(self, idx: int) -> int:
        center = self.base_delay + idx * self.delay_step
        if center > self.max_age:
            return self.max_age
        return center

    @staticmethod
    def abs_diff(a: int, b: int) -> int:
        return a - b if a >= b else b - a

    def tick(self, clear: int, rhythm_tick: int, beat_spike: int) -> None:
        old_token_active = self.token_active
        old_token_age = self.token_age
        old_predictor_id = self.predictor_id
        old_predictor_valid = self.predictor_valid
        old_evaluating = self.evaluating
        old_eval_idx = self.eval_idx
        old_eval_age = self.eval_age
        old_eval_best_id = self.eval_best_id
        old_eval_best_err = self.eval_best_err
        old_eval_predictor_id = self.eval_predictor_id
        old_eval_predictor_valid = self.eval_predictor_valid

        n = {
            "token_active": self.token_active,
            "token_age": self.token_age,
            "rr_interval": self.rr_interval,
            "winner_id": self.winner_id,
            "predictor_id": self.predictor_id,
            "winner_valid": self.winner_valid,
            "predictor_valid": self.predictor_valid,
            "winner_error": self.winner_error,
            "predictor_error": self.predictor_error,
            "pnn_match_spike": 0,
            "pnn_mismatch_spike": 0,
            "evaluating": self.evaluating,
            "eval_idx": self.eval_idx,
            "eval_age": self.eval_age,
            "eval_best_id": self.eval_best_id,
            "eval_best_err": self.eval_best_err,
            "eval_predictor_id": self.eval_predictor_id,
            "eval_predictor_valid": self.eval_predictor_valid,
        }

        if clear:
            self.reset()
            return

        age_eval = self.sat_age_inc(old_token_age) if (old_token_active and rhythm_tick) else old_token_age
        scan_center = self.hyp_center(old_eval_idx)
        scan_err = self.abs_diff(old_eval_age, scan_center)
        scan_better = scan_err < old_eval_best_err
        scan_best_id_next = old_eval_idx if scan_better else old_eval_best_id
        scan_best_err_next = scan_err if scan_better else old_eval_best_err
        predictor_err_next = self.abs_diff(old_eval_age, self.hyp_center(old_eval_predictor_id))
        match_next = old_eval_predictor_valid and predictor_err_next <= self.window_half

        if beat_spike:
            if old_token_active:
                n["rr_interval"] = age_eval
                n["eval_age"] = age_eval
                n["eval_idx"] = 0
                n["eval_best_id"] = 0
                n["eval_best_err"] = self.max_age
                n["eval_predictor_id"] = old_predictor_id
                n["eval_predictor_valid"] = old_predictor_valid
                n["evaluating"] = 1
            else:
                n["winner_valid"] = 0
                n["predictor_valid"] = 0
                n["predictor_error"] = self.max_age
                n["evaluating"] = 0
            n["token_active"] = 1
            n["token_age"] = 0
        else:
            if old_evaluating:
                if old_eval_idx == self.num_hyp - 1:
                    n["winner_id"] = scan_best_id_next
                    n["winner_error"] = scan_best_err_next
                    n["winner_valid"] = 1
                    n["predictor_id"] = scan_best_id_next
                    n["predictor_valid"] = 1
                    n["evaluating"] = 0
                    if old_eval_predictor_valid:
                        n["predictor_error"] = predictor_err_next
                        n["pnn_match_spike"] = int(match_next)
                        n["pnn_mismatch_spike"] = int(not match_next)
                    else:
                        n["predictor_error"] = self.max_age
                else:
                    n["eval_best_id"] = scan_best_id_next
                    n["eval_best_err"] = scan_best_err_next
                    n["eval_idx"] = old_eval_idx + 1
            if rhythm_tick and old_token_active:
                n["token_age"] = age_eval

        self.token_active = int(n["token_active"])
        self.token_age = int(n["token_age"])
        self.rr_interval = int(n["rr_interval"])
        self.winner_id = int(n["winner_id"])
        self.predictor_id = int(n["predictor_id"])
        self.winner_valid = int(n["winner_valid"])
        self.predictor_valid = int(n["predictor_valid"])
        self.winner_error = int(n["winner_error"])
        self.predictor_error = int(n["predictor_error"])
        self.pnn_match_spike = int(n["pnn_match_spike"])
        self.pnn_mismatch_spike = int(n["pnn_mismatch_spike"])
        self.evaluating = int(n["evaluating"])
        self.eval_idx = int(n["eval_idx"])
        self.eval_age = int(n["eval_age"])
        self.eval_best_id = int(n["eval_best_id"])
        self.eval_best_err = int(n["eval_best_err"])
        self.eval_predictor_id = int(n["eval_predictor_id"])
        self.eval_predictor_valid = int(n["eval_predictor_valid"])


@dataclass
class RdmVariabilityNeuron:
    thresholds: tuple[int, ...] = (10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150)
    prev_rr_valid: int = 0
    current_rr: int = 0
    prev_rr: int = 0
    rr_diff: int = 0
    rr_diff_valid_spike: int = 0
    rdm_level_spike: int = 0
    rdm_level_code: int = 0

    def reset(self) -> None:
        self.prev_rr_valid = 0
        self.current_rr = 0
        self.prev_rr = 0
        self.rr_diff = 0
        self.rr_diff_valid_spike = 0
        self.rdm_level_spike = 0
        self.rdm_level_code = 0

    @staticmethod
    def abs_diff(a: int, b: int) -> int:
        return a - b if a >= b else b - a

    def tick(self, clear: int, rr_interval_valid_spike: int, rr_interval_in: int) -> None:
        old_prev_valid = self.prev_rr_valid
        old_prev_rr = self.prev_rr

        next_prev_valid = self.prev_rr_valid
        next_current_rr = self.current_rr
        next_prev_rr = self.prev_rr
        next_rr_diff = self.rr_diff
        next_valid = 0
        next_level = 0
        next_code = 0

        if clear:
            next_prev_valid = 0
            next_current_rr = 0
            next_prev_rr = 0
            next_rr_diff = 0
        elif rr_interval_valid_spike:
            diff = self.abs_diff(int(rr_interval_in), old_prev_rr)
            level = 0
            code = 0
            for i, th in enumerate(self.thresholds):
                if diff >= th:
                    level |= 1 << i
                    code = i + 1
            next_current_rr = int(rr_interval_in)
            if old_prev_valid:
                next_rr_diff = diff
                next_valid = 1
                next_level = level
                next_code = code
            next_prev_rr = int(rr_interval_in)
            next_prev_valid = 1

        self.prev_rr_valid = int(next_prev_valid)
        self.current_rr = int(next_current_rr)
        self.prev_rr = int(next_prev_rr)
        self.rr_diff = int(next_rr_diff)
        self.rr_diff_valid_spike = int(next_valid)
        self.rdm_level_spike = int(next_level)
        self.rdm_level_code = int(next_code)


@dataclass
class EctopicPairNeuron:
    rr_delta_th: int = 120
    ref_shift: int = 4
    ref_valid: int = 0
    prev_pattern: int = 0
    rr_ref: int = 0
    early_rr_spike: int = 0
    late_rr_spike: int = 0
    ectopic_pair_spike: int = 0

    def reset(self) -> None:
        self.ref_valid = 0
        self.prev_pattern = 0
        self.rr_ref = 0
        self.early_rr_spike = 0
        self.late_rr_spike = 0
        self.ectopic_pair_spike = 0

    def tick(self, clear: int, rr_interval_valid_spike: int, rr_interval_in: int) -> None:
        old_ref_valid = self.ref_valid
        old_prev_pattern = self.prev_pattern
        old_rr_ref = self.rr_ref
        next_ref_valid = self.ref_valid
        next_prev_pattern = self.prev_pattern
        next_rr_ref = self.rr_ref
        next_early = 0
        next_late = 0
        next_pair = 0

        curr_pattern = 0
        if old_ref_valid:
            rr_plus_delta = (int(rr_interval_in) + self.rr_delta_th) & ((1 << 12) - 1)
            ref_plus_delta = (old_rr_ref + self.rr_delta_th) & ((1 << 12) - 1)
            if rr_plus_delta < old_rr_ref:
                curr_pattern = 1
            elif int(rr_interval_in) > ref_plus_delta:
                curr_pattern = 2
        diff_ref = abs(int(rr_interval_in) - old_rr_ref)
        ref_step = diff_ref >> self.ref_shift

        if clear:
            next_ref_valid = 0
            next_prev_pattern = 0
            next_rr_ref = 0
        elif rr_interval_valid_spike:
            if not old_ref_valid:
                next_rr_ref = int(rr_interval_in)
                next_ref_valid = 1
                next_prev_pattern = 0
            else:
                next_early = int(curr_pattern == 1)
                next_late = int(curr_pattern == 2)
                if curr_pattern != 0 and old_prev_pattern != 0 and curr_pattern != old_prev_pattern:
                    next_pair = 1
                if curr_pattern != 0:
                    next_prev_pattern = curr_pattern
                if int(rr_interval_in) >= old_rr_ref:
                    next_rr_ref = (old_rr_ref + ref_step) & ((1 << 12) - 1)
                else:
                    next_rr_ref = (old_rr_ref - ref_step) & ((1 << 12) - 1)

        self.ref_valid = int(next_ref_valid)
        self.prev_pattern = int(next_prev_pattern)
        self.rr_ref = int(next_rr_ref)
        self.early_rr_spike = int(next_early)
        self.late_rr_spike = int(next_late)
        self.ectopic_pair_spike = int(next_pair)


@dataclass
class DscrSpikeCounter:
    filter_shift: int = 4
    filter_frac: int = 8
    slope_input_shift: int = 0
    slope_leak: int = 8
    slope_threshold: int = 8
    sign_leak: int = 0
    sign_weight: int = 1
    sign_threshold: int = 1
    filter_width: int = ADC_WIDTH + 8 + 4
    mem_width: int = 16

    sample_seen: int = 0
    filt_mem: int = 0
    up_mem: int = 0
    down_mem: int = 0
    sign_mem: int = 0
    prev_slope_valid: int = 0
    prev_slope_sign: int = 0
    valid_slope_spike: int = 0
    sign_flip_spike: int = 0

    def reset(self) -> None:
        self.sample_seen = 0
        self.filt_mem = 0
        self.up_mem = 0
        self.down_mem = 0
        self.sign_mem = 0
        self.prev_slope_valid = 0
        self.prev_slope_sign = 0
        self.valid_slope_spike = 0
        self.sign_flip_spike = 0

    @staticmethod
    def leak_mem(value: int, leak: int) -> int:
        return value - leak if value > leak else 0

    def sat_mem_add(self, value: int, add_value: int) -> int:
        total = value + add_value
        if total >= (1 << self.mem_width):
            return (1 << self.mem_width) - 1
        return total

    def tick(self, clear: int, sample_valid: int, adc_data: int) -> None:
        next_valid = 0
        next_flip = 0

        if clear:
            self.reset()
            return

        if sample_valid:
            if not self.sample_seen:
                self.sample_seen = 1
                self.filt_mem = to_signed(int(adc_data) << self.filter_frac, self.filter_width)
            else:
                adc_fp = to_signed(int(adc_data) << self.filter_frac, self.filter_width)
                filter_error = to_signed(adc_fp - self.filt_mem, self.filter_width + 1)
                filter_update = filter_error >> self.filter_shift
                filt_next = to_signed(self.filt_mem + to_unsigned(filter_update, self.filter_width), self.filter_width)
                abs_update = abs(filter_update)
                slope_raw = abs_update >> self.filter_frac
                slope_shifted = slope_raw >> self.slope_input_shift
                if slope_shifted >> self.mem_width:
                    slope_input = (1 << self.mem_width) - 1
                else:
                    slope_input = slope_shifted & ((1 << self.mem_width) - 1)

                up_next = self.leak_mem(self.up_mem, self.slope_leak)
                down_next = self.leak_mem(self.down_mem, self.slope_leak)
                sign_next = self.leak_mem(self.sign_mem, self.sign_leak)
                curr_slope_spike = 0
                curr_slope_sign = 0

                if filter_update > 0 and slope_input != 0:
                    up_next = self.sat_mem_add(up_next, slope_input)
                    if up_next >= self.slope_threshold:
                        curr_slope_spike = 1
                        curr_slope_sign = 1
                        up_next = 0
                        down_next = 0
                elif filter_update < 0 and slope_input != 0:
                    down_next = self.sat_mem_add(down_next, slope_input)
                    if down_next >= self.slope_threshold:
                        curr_slope_spike = 1
                        curr_slope_sign = 0
                        up_next = 0
                        down_next = 0

                if curr_slope_spike:
                    next_valid = 1
                    if self.prev_slope_valid and curr_slope_sign != self.prev_slope_sign:
                        sign_next = self.sat_mem_add(sign_next, self.sign_weight)
                        if sign_next >= self.sign_threshold:
                            next_flip = 1
                            sign_next = 0
                    self.prev_slope_valid = 1
                    self.prev_slope_sign = curr_slope_sign

                self.up_mem = up_next
                self.down_mem = down_next
                self.sign_mem = sign_next
                self.filt_mem = filt_next

        self.valid_slope_spike = int(next_valid)
        self.sign_flip_spike = int(next_flip)


@dataclass
class RamPeakAccumulator:
    code_width: int = 6
    bank_size: int = 32
    bank_base: int = 32
    bank_step: int = 32
    ram_post_hold: int = 80

    amp_window_active: int = 0
    amp_window_cnt: int = 0
    r_peak_abs: int = 0
    ram_amp_spike: int = 0
    ram_amp_code: int = 0
    ram_window_open_d: int = 0
    beat_seen: int = 0
    post_hold_active: int = 0
    post_hold_cnt: int = 0

    def reset(self) -> None:
        self.amp_window_active = 0
        self.amp_window_cnt = 0
        self.r_peak_abs = 0
        self.ram_amp_spike = 0
        self.ram_amp_code = 0
        self.ram_window_open_d = 0
        self.beat_seen = 0
        self.post_hold_active = 0
        self.post_hold_cnt = 0

    def encode_amp_code(self, amplitude: int) -> int:
        code = 0
        for i in range(self.bank_size):
            if amplitude >= self.bank_base + i * self.bank_step:
                code = i + 1
        return code & ((1 << self.code_width) - 1)

    def tick(self, clear: int, sample_valid: int, ram_window_open: int, beat_spike: int, adc_data: int, baseline: int = 0) -> None:
        old_window_d = self.ram_window_open_d
        old_post_active = self.post_hold_active
        old_post_cnt = self.post_hold_cnt
        old_beat_seen = self.beat_seen
        old_r_peak_abs = self.r_peak_abs
        capture_active = bool(ram_window_open or old_post_active)
        pos_amp = int(adc_data) - int(baseline)
        if pos_amp < 0:
            pos_amp = 0

        next_amp_active = self.amp_window_active
        next_amp_cnt = self.amp_window_cnt
        next_r_peak_abs = self.r_peak_abs
        next_spike = 0
        next_code = self.ram_amp_code
        next_window_d = 1 if ram_window_open else 0
        next_beat_seen = self.beat_seen
        next_post_active = self.post_hold_active
        next_post_cnt = self.post_hold_cnt

        if clear:
            self.reset()
            return

        if ram_window_open and not old_window_d:
            next_amp_active = 1
            next_amp_cnt = 0
            next_r_peak_abs = 0
            next_beat_seen = 0
            next_post_active = 0
            next_post_cnt = 0
            capture_active = bool(ram_window_open)

        if capture_active:
            peak_code_next = old_r_peak_abs & ((1 << self.code_width) - 1)
            if sample_valid:
                sample_code = self.encode_amp_code(pos_amp)
                if sample_code > peak_code_next:
                    peak_code_next = sample_code
                next_r_peak_abs = peak_code_next
            if beat_spike and ram_window_open:
                next_beat_seen = 1
                next_post_active = 1
                next_post_cnt = self.ram_post_hold
            elif old_post_active and sample_valid:
                if old_post_cnt <= 1:
                    next_post_active = 0
                    next_post_cnt = 0
                else:
                    next_post_cnt = (old_post_cnt - 1) & 0xFF

        if (not ram_window_open) and old_window_d and (not old_beat_seen) and (not old_post_active):
            next_amp_active = 0
            next_amp_cnt = old_r_peak_abs & ((1 << self.code_width) - 1)
            next_beat_seen = 0

        if old_post_active and sample_valid and old_post_cnt <= 1:
            next_amp_active = 0
            next_amp_cnt = old_r_peak_abs & ((1 << self.code_width) - 1)
            if old_beat_seen:
                next_code = old_r_peak_abs & ((1 << self.code_width) - 1)
                next_spike = 1
            next_beat_seen = 0

        self.amp_window_active = int(next_amp_active)
        self.amp_window_cnt = int(next_amp_cnt)
        self.r_peak_abs = int(next_r_peak_abs)
        self.ram_amp_spike = int(next_spike)
        self.ram_amp_code = int(next_code)
        self.ram_window_open_d = int(next_window_d)
        self.beat_seen = int(next_beat_seen)
        self.post_hold_active = int(next_post_active)
        self.post_hold_cnt = int(next_post_cnt)


@dataclass
class QrsMafNeuron:
    code_width: int = 6
    pre_win: int = 120
    post_win: int = 100
    width_th: int = 120
    width_dev_th: int = 40
    complex_th: int = 6
    energy_shift: int = 5
    energy_dev_th: int = 8
    ref_shift: int = 3

    pre_strong_sr: list[int] = field(default_factory=lambda: [0] * 120)
    pre_flip_sr: list[int] = field(default_factory=lambda: [0] * 120)
    pre_energy_sr: list[int] = field(default_factory=lambda: [0] * 120)
    pre_strong_count: int = 0
    pre_flip_count: int = 0
    pre_energy_sum: int = 0
    window_active: int = 0
    post_count: int = 0
    event_seen: int = 0
    first_pos: int = 0
    last_pos: int = 0
    event_count: int = 0
    flip_count: int = 0
    energy_sum: int = 0
    pre_strong_at_beat: int = 0
    pre_flip_at_beat: int = 0
    pre_energy_at_beat: int = 0
    width_ref: int = 0
    energy_ref: int = 0
    width_ref_valid: int = 0
    energy_ref_valid: int = 0
    qrs_maf_valid_spike: int = 0
    qrs_width_abn_spike: int = 0
    qrs_complex_abn_spike: int = 0
    qrs_energy_abn_spike: int = 0
    pre_qrs_bump_spike: int = 0
    qrs_width_value: int = 0
    qrs_complex_count: int = 0
    qrs_energy_code: int = 0

    @property
    def code_max(self) -> int:
        return (1 << self.code_width) - 1

    def reset(self) -> None:
        self.pre_strong_sr = [0] * self.pre_win
        self.pre_flip_sr = [0] * self.pre_win
        self.pre_energy_sr = [0] * self.pre_win
        self.pre_strong_count = 0
        self.pre_flip_count = 0
        self.pre_energy_sum = 0
        self.window_active = 0
        self.post_count = 0
        self.event_seen = 0
        self.first_pos = 0
        self.last_pos = 0
        self.event_count = 0
        self.flip_count = 0
        self.energy_sum = 0
        self.pre_strong_at_beat = 0
        self.pre_flip_at_beat = 0
        self.pre_energy_at_beat = 0
        self.width_ref = 0
        self.energy_ref = 0
        self.width_ref_valid = 0
        self.energy_ref_valid = 0
        self.qrs_maf_valid_spike = 0
        self.qrs_width_abn_spike = 0
        self.qrs_complex_abn_spike = 0
        self.qrs_energy_abn_spike = 0
        self.pre_qrs_bump_spike = 0
        self.qrs_width_value = 0
        self.qrs_complex_count = 0
        self.qrs_energy_code = 0

    def pre_positions(self) -> tuple[int, int, int]:
        seen = 0
        first = 0
        last = 0
        for i in range(self.pre_win):
            if self.pre_strong_sr[self.pre_win - 1 - i]:
                if not seen:
                    seen = 1
                    first = i & 0xFF
                last = i & 0xFF
        return seen, first, last

    def energy_sample_code(self, adc_data: int, baseline: int = 0) -> int:
        diff = int(adc_data) - int(baseline)
        if diff < 0:
            diff = -diff
        shifted = diff >> self.energy_shift
        return 0xFF if shifted > 0xFF else shifted & 0xFF

    def tick(
        self,
        clear: int,
        sample_valid: int,
        adc_data: int,
        strong_event: int,
        dscr_sign_flip_spike: int,
        beat_spike: int,
        baseline: int = 0,
    ) -> None:
        old_pre_strong_sr = self.pre_strong_sr[:]
        old_pre_flip_sr = self.pre_flip_sr[:]
        old_pre_energy_sr = self.pre_energy_sr[:]
        old_pre_strong_count = self.pre_strong_count
        old_pre_flip_count = self.pre_flip_count
        old_pre_energy_sum = self.pre_energy_sum
        old_window_active = self.window_active
        old_post_count = self.post_count
        old_event_seen = self.event_seen
        old_first_pos = self.first_pos
        old_last_pos = self.last_pos
        old_flip_count = self.flip_count
        old_energy_sum = self.energy_sum
        old_width_ref = self.width_ref
        old_energy_ref = self.energy_ref
        old_width_ref_valid = self.width_ref_valid
        old_energy_ref_valid = self.energy_ref_valid
        old_pre_strong_at_beat = self.pre_strong_at_beat
        old_pre_flip_at_beat = self.pre_flip_at_beat
        old_pre_energy_at_beat = self.pre_energy_at_beat

        if clear:
            self.reset()
            return

        next_pre_strong_sr = old_pre_strong_sr[:]
        next_pre_flip_sr = old_pre_flip_sr[:]
        next_pre_energy_sr = old_pre_energy_sr[:]
        next_pre_strong_count = old_pre_strong_count
        next_pre_flip_count = old_pre_flip_count
        next_pre_energy_sum = old_pre_energy_sum
        next_window_active = self.window_active
        next_post_count = self.post_count
        next_event_seen = self.event_seen
        next_first_pos = self.first_pos
        next_last_pos = self.last_pos
        next_event_count = self.event_count
        next_flip_count = self.flip_count
        next_energy_sum = self.energy_sum
        next_pre_strong_at_beat = self.pre_strong_at_beat
        next_pre_flip_at_beat = self.pre_flip_at_beat
        next_pre_energy_at_beat = self.pre_energy_at_beat
        next_width_ref = self.width_ref
        next_energy_ref = self.energy_ref
        next_width_ref_valid = self.width_ref_valid
        next_energy_ref_valid = self.energy_ref_valid
        next_valid = 0
        next_width_abn = 0
        next_complex_abn = 0
        next_energy_abn = 0
        next_pre_bump = 0
        next_width_value = self.qrs_width_value
        next_complex_count = self.qrs_complex_count
        next_energy_code_reg = self.qrs_energy_code

        pre_seen, pre_first, pre_last = self.pre_positions()
        energy_code = self.energy_sample_code(adc_data, baseline)
        event_seen_eval = int(bool(old_event_seen or strong_event))
        first_pos_eval = old_first_pos
        if (not old_event_seen) and strong_event:
            first_pos_eval = (self.pre_win + old_post_count) & 0xFF
        last_pos_eval = ((self.pre_win + old_post_count) & 0xFF) if strong_event else old_last_pos
        width_eval = ((last_pos_eval - first_pos_eval) & 0xFF) if event_seen_eval else 0
        width_diff_abs = abs(width_eval - old_width_ref)
        flip_count_eval = (old_flip_count + (1 if dscr_sign_flip_spike else 0)) & 0xFF
        if old_energy_sum <= 0xFFFF - energy_code:
            energy_sum_eval = old_energy_sum + energy_code
        else:
            energy_sum_eval = 0xFFFF
        energy_shifted = energy_sum_eval >> 6
        energy_code_next = self.code_max if energy_shifted > self.code_max else energy_shifted & self.code_max
        energy_diff_abs = abs(energy_code_next - old_energy_ref)
        complex_next = self.code_max if flip_count_eval > self.code_max else flip_count_eval & self.code_max
        wide_cond = int((width_eval >= self.width_th) or (old_width_ref_valid and (width_diff_abs >= self.width_dev_th)))
        complex_cond = int(complex_next >= self.complex_th)
        energy_cond = int(old_energy_ref_valid and (energy_diff_abs >= self.energy_dev_th))

        if sample_valid:
            next_pre_strong_sr = [1 if strong_event else 0] + old_pre_strong_sr[:-1]
            next_pre_flip_sr = [1 if dscr_sign_flip_spike else 0] + old_pre_flip_sr[:-1]
            next_pre_energy_sr = [energy_code] + old_pre_energy_sr[:-1]
            next_pre_strong_count = (old_pre_strong_count + (1 if strong_event else 0) - old_pre_strong_sr[-1]) & 0xFF
            next_pre_flip_count = (old_pre_flip_count + (1 if dscr_sign_flip_spike else 0) - old_pre_flip_sr[-1]) & 0xFF
            next_pre_energy_sum = (old_pre_energy_sum + energy_code - old_pre_energy_sr[-1]) & 0xFFFF

            if beat_spike:
                next_window_active = 1
                next_post_count = 1
                next_event_seen = int(bool(pre_seen or strong_event))
                next_first_pos = pre_first if pre_seen else (self.pre_win if strong_event else 0)
                next_last_pos = self.pre_win if strong_event else (pre_last if pre_seen else 0)
                next_event_count = (old_pre_strong_count + (1 if strong_event else 0)) & 0xFF
                next_flip_count = (old_pre_flip_count + (1 if dscr_sign_flip_spike else 0)) & 0xFF
                next_energy_sum = (old_pre_energy_sum + energy_code) & 0xFFFF
                next_pre_strong_at_beat = old_pre_strong_count
                next_pre_flip_at_beat = old_pre_flip_count
                next_pre_energy_at_beat = old_pre_energy_sum
            elif old_window_active:
                if strong_event:
                    if not old_event_seen:
                        next_event_seen = 1
                        next_first_pos = (self.pre_win + old_post_count) & 0xFF
                    next_last_pos = (self.pre_win + old_post_count) & 0xFF
                    if self.event_count != 0xFF:
                        next_event_count = (self.event_count + 1) & 0xFF
                if dscr_sign_flip_spike and self.flip_count != 0xFF:
                    next_flip_count = (self.flip_count + 1) & 0xFF
                next_energy_sum = energy_sum_eval

                if old_post_count >= (self.post_win - 1):
                    next_window_active = 0
                    next_valid = 1
                    next_width_value = width_eval
                    next_complex_count = complex_next
                    next_energy_code_reg = energy_code_next
                    next_width_abn = wide_cond
                    next_complex_abn = complex_cond
                    next_energy_abn = energy_cond
                    next_pre_bump = int(
                        (old_pre_strong_at_beat != 0)
                        or (old_pre_flip_at_beat >= 2)
                        or (old_pre_energy_at_beat >= 32)
                    )
                    if not old_width_ref_valid:
                        next_width_ref = width_eval
                        next_width_ref_valid = 1
                    elif width_eval >= old_width_ref:
                        next_width_ref = (old_width_ref + ((width_eval - old_width_ref) >> self.ref_shift)) & 0xFF
                    else:
                        next_width_ref = (old_width_ref - ((old_width_ref - width_eval) >> self.ref_shift)) & 0xFF
                    if not old_energy_ref_valid:
                        next_energy_ref = energy_code_next
                        next_energy_ref_valid = 1
                    elif energy_code_next >= old_energy_ref:
                        next_energy_ref = (old_energy_ref + ((energy_code_next - old_energy_ref) >> self.ref_shift)) & self.code_max
                    else:
                        next_energy_ref = (old_energy_ref - ((old_energy_ref - energy_code_next) >> self.ref_shift)) & self.code_max
                else:
                    next_post_count = (old_post_count + 1) & 0xFF

        self.pre_strong_sr = next_pre_strong_sr
        self.pre_flip_sr = next_pre_flip_sr
        self.pre_energy_sr = next_pre_energy_sr
        self.pre_strong_count = int(next_pre_strong_count)
        self.pre_flip_count = int(next_pre_flip_count)
        self.pre_energy_sum = int(next_pre_energy_sum)
        self.window_active = int(next_window_active)
        self.post_count = int(next_post_count)
        self.event_seen = int(next_event_seen)
        self.first_pos = int(next_first_pos)
        self.last_pos = int(next_last_pos)
        self.event_count = int(next_event_count)
        self.flip_count = int(next_flip_count)
        self.energy_sum = int(next_energy_sum)
        self.pre_strong_at_beat = int(next_pre_strong_at_beat)
        self.pre_flip_at_beat = int(next_pre_flip_at_beat)
        self.pre_energy_at_beat = int(next_pre_energy_at_beat)
        self.width_ref = int(next_width_ref)
        self.energy_ref = int(next_energy_ref)
        self.width_ref_valid = int(next_width_ref_valid)
        self.energy_ref_valid = int(next_energy_ref_valid)
        self.qrs_maf_valid_spike = int(next_valid)
        self.qrs_width_abn_spike = int(next_width_abn)
        self.qrs_complex_abn_spike = int(next_complex_abn)
        self.qrs_energy_abn_spike = int(next_energy_abn)
        self.pre_qrs_bump_spike = int(next_pre_bump)
        self.qrs_width_value = int(next_width_value)
        self.qrs_complex_count = int(next_complex_count)
        self.qrs_energy_code = int(next_energy_code_reg)


@dataclass
class RbbbQrsDelayBank:
    activity_mode: int = 1
    low_slope_th: int = 5
    onset_ref: int = 200
    max_qrs_obs_win: int = 200
    activity_gap_end: int = 15
    terminal_start: int = 90
    terminal_end: int = 170
    wide_width_th: int = 120
    terminal_count_th: int = 4
    rbbb_repeat_th: int = 5
    high_rdm_suppress: int = 0
    high_rdm_mode: int = 0
    high_rdm_level: int = 11
    high_rdm_pct: int = 5
    high_rdm_avg_code: int = 9

    qrs_active: int = 0
    prev_activity: int = 0
    onset_ref_cnt: int = 0
    qrs_age: int = 0
    activity_gap_cnt: int = 0
    hyp_match: int = 0
    terminal_count_work: int = 0
    pnn_match_count: int = 0
    pnn_mismatch_count: int = 0
    rdm_valid_count: int = 0
    rdm_high_count: int = 0
    rdm_code_sum: int = 0
    qrs_onset_spike: int = 0
    qrs_valid_spike: int = 0
    wide_qrs_spike: int = 0
    terminal_delay_spike: int = 0
    rbbb_like_beat_spike: int = 0
    last_matched_width: int = 0
    terminal_activity_count: int = 0
    max_last_matched_width: int = 0
    valid_qrs_count: int = 0
    wide_qrs_count: int = 0
    terminal_delay_count: int = 0
    rbbb_like_beat_count: int = 0

    def reset(self) -> None:
        self.qrs_active = 0
        self.prev_activity = 0
        self.onset_ref_cnt = 0
        self.qrs_age = 0
        self.activity_gap_cnt = 0
        self.hyp_match = 0
        self.terminal_count_work = 0
        self.pnn_match_count = 0
        self.pnn_mismatch_count = 0
        self.rdm_valid_count = 0
        self.rdm_high_count = 0
        self.rdm_code_sum = 0
        self.qrs_onset_spike = 0
        self.qrs_valid_spike = 0
        self.wide_qrs_spike = 0
        self.terminal_delay_spike = 0
        self.rbbb_like_beat_spike = 0
        self.last_matched_width = 0
        self.terminal_activity_count = 0
        self.max_last_matched_width = 0
        self.valid_qrs_count = 0
        self.wide_qrs_count = 0
        self.terminal_delay_count = 0
        self.rbbb_like_beat_count = 0

    def activity_event(self, strong_event: int, slope_valid: int, abs_delta: int) -> int:
        low_slope_event = int(int(abs_delta) >= self.low_slope_th)
        activity = int(bool(slope_valid))
        if self.activity_mode == 1:
            activity = low_slope_event
        elif self.activity_mode == 2:
            activity = int(bool(strong_event or slope_valid))
        elif self.activity_mode == 3:
            activity = int(bool(strong_event or low_slope_event))
        return activity

    def high_rdm_event(self, rdm_level_spike: int) -> int:
        for j in range(self.high_rdm_level, 15):
            if rdm_level_spike & (1 << j):
                return 1
        return 0

    def low_irregularity(self) -> int:
        total = self.pnn_match_count + self.pnn_mismatch_count
        return int(total == 0 or (self.pnn_mismatch_count * 100) <= (total * 18))

    def high_rdm_irregularity(self) -> int:
        if self.rdm_valid_count == 0:
            return 0
        if self.high_rdm_mode == 1:
            return int(self.rdm_code_sum >= self.rdm_valid_count * self.high_rdm_avg_code)
        return int(self.rdm_high_count * 100 >= self.rdm_valid_count * self.high_rdm_pct)

    def segment_spike(self, segment_done: int) -> int:
        return int(
            bool(segment_done)
            and bool(self.low_irregularity())
            and ((self.high_rdm_suppress == 0) or not self.high_rdm_irregularity())
            and (self.rbbb_like_beat_count >= self.rbbb_repeat_th)
        )

    @staticmethod
    def last_width_from_hyp(hyp_match: int) -> int:
        for bit, width in [(8, 160), (7, 150), (6, 140), (5, 130), (4, 120), (3, 110), (2, 100), (1, 90), (0, 80)]:
            if hyp_match & (1 << bit):
                return width
        return 0

    def tick(
        self,
        clear: int,
        sample_valid: int,
        segment_done: int,
        strong_event: int,
        slope_valid: int,
        abs_delta: int,
        pnn_match_spike: int,
        pnn_mismatch_spike: int,
        rdm_valid_spike: int,
        rdm_level_spike: int,
        rdm_level_code: int,
    ) -> None:
        old_qrs_active = self.qrs_active
        old_prev_activity = self.prev_activity
        old_onset_ref_cnt = self.onset_ref_cnt
        old_qrs_age = self.qrs_age
        old_gap = self.activity_gap_cnt
        old_hyp_match = self.hyp_match
        old_terminal_count = self.terminal_count_work

        if clear:
            self.reset()
            return

        activity = self.activity_event(strong_event, slope_valid, abs_delta)
        onset_fire = int(bool(sample_valid and activity and (not old_prev_activity) and (not old_qrs_active) and old_onset_ref_cnt == 0))
        qrs_age_next = (old_qrs_age + 1) & 0xFF
        gap_next = 0 if activity else ((old_gap + 1) & 0xFF if old_gap != 0xFF else old_gap)
        terminal_zone = int(qrs_age_next >= self.terminal_start and qrs_age_next < self.terminal_end)
        hyp_match_next = old_hyp_match
        if activity:
            for bit, age in enumerate([80, 90, 100, 110, 120, 130, 140, 150, 160]):
                if qrs_age_next == age:
                    hyp_match_next |= 1 << bit
        terminal_count_next = old_terminal_count
        if activity and terminal_zone and old_terminal_count != 0xFF:
            terminal_count_next = (old_terminal_count + 1) & 0xFF
        qrs_end_fire = int(bool(sample_valid and old_qrs_active and ((qrs_age_next >= self.max_qrs_obs_win) or (gap_next >= self.activity_gap_end))))
        last_width_calc = self.last_width_from_hyp(hyp_match_next)
        wide_cond = int(last_width_calc >= self.wide_width_th)
        terminal_cond = int(terminal_count_next >= self.terminal_count_th)
        rbbb_cond = int(bool(wide_cond and terminal_cond))

        next_qrs_active = self.qrs_active
        next_prev_activity = self.prev_activity
        next_onset_ref_cnt = self.onset_ref_cnt
        next_qrs_age = self.qrs_age
        next_gap = self.activity_gap_cnt
        next_hyp_match = self.hyp_match
        next_terminal_count = self.terminal_count_work
        next_pnn_match_count = self.pnn_match_count
        next_pnn_mismatch_count = self.pnn_mismatch_count
        next_rdm_valid_count = self.rdm_valid_count
        next_rdm_high_count = self.rdm_high_count
        next_rdm_code_sum = self.rdm_code_sum
        next_onset = 0
        next_valid = 0
        next_wide = 0
        next_terminal = 0
        next_like = 0
        next_last_width = self.last_matched_width
        next_terminal_activity = self.terminal_activity_count
        next_max_width = self.max_last_matched_width
        next_valid_count = self.valid_qrs_count
        next_wide_count = self.wide_qrs_count
        next_terminal_delay_count = self.terminal_delay_count
        next_like_count = self.rbbb_like_beat_count

        if pnn_match_spike and next_pnn_match_count != 0xFFFF:
            next_pnn_match_count += 1
        if pnn_mismatch_spike and next_pnn_mismatch_count != 0xFFFF:
            next_pnn_mismatch_count += 1
        if rdm_valid_spike and next_rdm_valid_count != 0xFFFF:
            next_rdm_valid_count += 1
        if rdm_valid_spike:
            next_rdm_code_sum = (next_rdm_code_sum + int(rdm_level_code)) & ((1 << 20) - 1)
        if rdm_valid_spike and self.high_rdm_event(rdm_level_spike) and next_rdm_high_count != 0xFFFF:
            next_rdm_high_count += 1

        if sample_valid:
            next_prev_activity = activity
            if old_onset_ref_cnt != 0:
                next_onset_ref_cnt = (old_onset_ref_cnt - 1) & 0xFF
            if onset_fire:
                next_qrs_active = 1
                next_onset = 1
                next_onset_ref_cnt = self.onset_ref & 0xFF
                next_qrs_age = 0
                next_gap = 0
                next_hyp_match = 0
                next_terminal_count = 0
            elif old_qrs_active:
                next_qrs_age = qrs_age_next
                next_gap = gap_next
                next_hyp_match = hyp_match_next
                next_terminal_count = terminal_count_next
                if qrs_end_fire:
                    next_qrs_active = 0
                    next_valid = 1
                    next_wide = wide_cond
                    next_terminal = terminal_cond
                    next_like = rbbb_cond
                    next_last_width = last_width_calc
                    next_terminal_activity = terminal_count_next
                    if last_width_calc > next_max_width:
                        next_max_width = last_width_calc
                    if next_valid_count != 0xFF:
                        next_valid_count = (next_valid_count + 1) & 0xFF
                    if wide_cond and next_wide_count != 0xFF:
                        next_wide_count = (next_wide_count + 1) & 0xFF
                    if terminal_cond and next_terminal_delay_count != 0xFF:
                        next_terminal_delay_count = (next_terminal_delay_count + 1) & 0xFF
                    if rbbb_cond and next_like_count != 0xFF:
                        next_like_count = (next_like_count + 1) & 0xFF

        if segment_done:
            next_qrs_active = 0
            next_qrs_age = 0
            next_gap = 0
            next_hyp_match = 0
            next_terminal_count = 0
            next_pnn_match_count = 0
            next_pnn_mismatch_count = 0
            next_rdm_valid_count = 0
            next_rdm_high_count = 0
            next_rdm_code_sum = 0
            next_valid_count = 0
            next_wide_count = 0
            next_terminal_delay_count = 0
            next_like_count = 0
            next_max_width = 0

        self.qrs_active = int(next_qrs_active)
        self.prev_activity = int(next_prev_activity)
        self.onset_ref_cnt = int(next_onset_ref_cnt)
        self.qrs_age = int(next_qrs_age)
        self.activity_gap_cnt = int(next_gap)
        self.hyp_match = int(next_hyp_match)
        self.terminal_count_work = int(next_terminal_count)
        self.pnn_match_count = int(next_pnn_match_count)
        self.pnn_mismatch_count = int(next_pnn_mismatch_count)
        self.rdm_valid_count = int(next_rdm_valid_count)
        self.rdm_high_count = int(next_rdm_high_count)
        self.rdm_code_sum = int(next_rdm_code_sum)
        self.qrs_onset_spike = int(next_onset)
        self.qrs_valid_spike = int(next_valid)
        self.wide_qrs_spike = int(next_wide)
        self.terminal_delay_spike = int(next_terminal)
        self.rbbb_like_beat_spike = int(next_like)
        self.last_matched_width = int(next_last_width)
        self.terminal_activity_count = int(next_terminal_activity)
        self.max_last_matched_width = int(next_max_width)
        self.valid_qrs_count = int(next_valid_count)
        self.wide_qrs_count = int(next_wide_count)
        self.terminal_delay_count = int(next_terminal_delay_count)
        self.rbbb_like_beat_count = int(next_like_count)


@dataclass
class C24ScoreNeurons:
    subwindow_ticks: int = 60000
    bias_nsr: int = -5213
    bias_chf: int = -22414
    bias_arr: int = -7298
    bias_aff: int = 32767

    local_mem: list[int] = field(default_factory=list)
    score_mem: list[int] = field(default_factory=list)
    c24_mem: list[int] = field(default_factory=list)
    ms_count: int = 0
    subwindow_tick_count: int = 0
    beat_seg_count: int = 0
    dscr_flip_seg_count: int = 0
    dscr_slope_seg_count: int = 0
    ram_seg_count: int = 0
    ram_code_seg_sum: int = 0
    rdm_ge20_seg_count: int = 0
    rdm_ge50_seg_count: int = 0
    rdm_ge80_seg_count: int = 0
    rdm_ge100_seg_count: int = 0
    qrs_maf_valid_seg_count: int = 0
    qrs_maf_seg_count: int = 0
    qrs_width_abn_seg_count: int = 0
    qrs_energy_abn_seg_count: int = 0
    rbbb_valid_seg_count: int = 0
    rbbb_wide_seg_count: int = 0
    rbbb_terminal_seg_count: int = 0
    rbbb_like_seg_count: int = 0
    rbbb_segment_seg_count: int = 0
    ectopic_pair_win_count: int = 0
    ectopic_pair_seg_count: int = 0
    ectopic_early_seg_count: int = 0
    pre_qrs_bump_seg_count: int = 0
    pnn_match_win_count: int = 0
    pnn_mis_win_count: int = 0
    pnn_match_seg_count: int = 0
    pnn_mis_seg_count: int = 0
    rdm_valid_win_count: int = 0
    rdm_code_win_sum: int = 0
    rdm_valid_seg_count: int = 0
    rdm_code_seg_sum: int = 0
    ram_count_win: int = 0
    ram_code_win_sum: int = 0
    eerg_gate: int = 0
    eerg_applied: int = 0
    eerg_pre_qrs_bump_count: int = 0
    eerg_early_count: int = 0
    eerg_ecp_count: int = 0
    eerg_pnn_decision_count: int = 0
    eerg_pnn_mismatch_count: int = 0
    eerg_rdm_valid_count: int = 0
    eerg_rdm_code_sum: int = 0
    rbbb_qrs_delay_applied: int = 0
    score_arr_before_eerg: int = 0
    pred_class: int = 0
    pred_valid: int = 0

    def __post_init__(self) -> None:
        if not self.local_mem:
            self.reset()

    @property
    def biases(self) -> list[int]:
        return [self.bias_nsr, self.bias_chf, self.bias_arr, self.bias_aff]

    def reset(self) -> None:
        self.local_mem = self.biases[:]
        self.score_mem = self.biases[:]
        self.c24_mem = [
            _CLASS_CONSTS["C24_MEM_INIT_NSR"],
            _CLASS_CONSTS["C24_MEM_INIT_CHF"],
            _CLASS_CONSTS["C24_MEM_INIT_ARR"],
            _CLASS_CONSTS["C24_MEM_INIT_AFF"],
        ]
        self.ms_count = 0
        self.subwindow_tick_count = 0
        self.beat_seg_count = 0
        self.dscr_flip_seg_count = 0
        self.dscr_slope_seg_count = 0
        self.ram_seg_count = 0
        self.ram_code_seg_sum = 0
        self.rdm_ge20_seg_count = 0
        self.rdm_ge50_seg_count = 0
        self.rdm_ge80_seg_count = 0
        self.rdm_ge100_seg_count = 0
        self.qrs_maf_valid_seg_count = 0
        self.qrs_maf_seg_count = 0
        self.qrs_width_abn_seg_count = 0
        self.qrs_energy_abn_seg_count = 0
        self.rbbb_valid_seg_count = 0
        self.rbbb_wide_seg_count = 0
        self.rbbb_terminal_seg_count = 0
        self.rbbb_like_seg_count = 0
        self.rbbb_segment_seg_count = 0
        self.ectopic_pair_win_count = 0
        self.ectopic_pair_seg_count = 0
        self.ectopic_early_seg_count = 0
        self.pre_qrs_bump_seg_count = 0
        self.pnn_match_win_count = 0
        self.pnn_mis_win_count = 0
        self.pnn_match_seg_count = 0
        self.pnn_mis_seg_count = 0
        self.rdm_valid_win_count = 0
        self.rdm_code_win_sum = 0
        self.rdm_valid_seg_count = 0
        self.rdm_code_seg_sum = 0
        self.ram_count_win = 0
        self.ram_code_win_sum = 0
        self.eerg_gate = 0
        self.eerg_applied = 0
        self.eerg_pre_qrs_bump_count = 0
        self.eerg_early_count = 0
        self.eerg_ecp_count = 0
        self.eerg_pnn_decision_count = 0
        self.eerg_pnn_mismatch_count = 0
        self.eerg_rdm_valid_count = 0
        self.eerg_rdm_code_sum = 0
        self.rbbb_qrs_delay_applied = 0
        self.score_arr_before_eerg = self.score_mem[2]
        self.pred_class = 0
        self.pred_valid = 0

    def c24_weight(self, base: str) -> list[int]:
        return [_CLASS_CONSTS[f"{base}_{cls}"] for cls in CLASSES]

    def local_weight(self, base: str) -> list[int]:
        return [_CLASS_CONSTS[f"{base}_{cls}"] for cls in CLASSES]

    @staticmethod
    def add_vec(dst: list[int], src: list[int], scale: int = 1) -> None:
        for i in range(4):
            dst[i] += src[i] * scale

    def add_c24(self, c24_next: list[int], base: str, scale: int = 1) -> None:
        self.add_vec(c24_next, self.c24_weight(base), scale)

    def add_local(self, local_next: list[int], base: str, scale: int = 1) -> None:
        self.add_vec(local_next, self.local_weight(base), scale)

    @staticmethod
    def argmax4(values: list[int]) -> int:
        best = 0
        for i in range(1, 4):
            if values[i] > values[best]:
                best = i
        return best

    def tick(
        self,
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
        if clear:
            self.reset()
            return

        local_next = self.local_mem[:]
        score_next = self.score_mem[:]
        c24_next = self.c24_mem[:]

        beat_seg_next = self.beat_seg_count + (1 if beat_spike else 0)
        dscr_flip_seg_next = self.dscr_flip_seg_count + (1 if dscr_sign_flip_spike else 0)
        dscr_slope_seg_next = self.dscr_slope_seg_count + (1 if dscr_valid_slope_spike else 0)
        qrs_valid_seg_next = self.qrs_maf_valid_seg_count + (1 if qrs_maf_valid_spike else 0)
        qrs_maf_seg_next = self.qrs_maf_seg_count + (1 if (qrs_width_abn_spike or qrs_complex_abn_spike or qrs_energy_abn_spike) else 0)
        qrs_width_seg_next = self.qrs_width_abn_seg_count + (1 if qrs_width_abn_spike else 0)
        qrs_energy_seg_next = self.qrs_energy_abn_seg_count + (1 if qrs_energy_abn_spike else 0)
        rbbb_valid_seg_next = self.rbbb_valid_seg_count + (1 if rbbb_qrs_valid_spike else 0)
        rbbb_wide_seg_next = self.rbbb_wide_seg_count + (1 if rbbb_qrs_wide_spike else 0)
        rbbb_terminal_seg_next = self.rbbb_terminal_seg_count + (1 if rbbb_qrs_terminal_spike else 0)
        rbbb_like_seg_next = self.rbbb_like_seg_count + (1 if rbbb_qrs_like_beat_spike else 0)
        rbbb_segment_seg_next = self.rbbb_segment_seg_count + (1 if rbbb_qrs_delay_segment_spike else 0)
        ect_pair_win_next = self.ectopic_pair_win_count + (1 if ectopic_pair_spike else 0)
        ect_pair_seg_next = self.ectopic_pair_seg_count + (1 if ectopic_pair_spike else 0)
        ect_early_seg_next = self.ectopic_early_seg_count + (1 if ectopic_early_spike else 0)
        pre_bump_seg_next = self.pre_qrs_bump_seg_count + (1 if pre_qrs_bump_spike else 0)
        pnn_match_win_next = self.pnn_match_win_count + (1 if pnn_match_spike else 0)
        pnn_mis_win_next = self.pnn_mis_win_count + (1 if pnn_mismatch_spike else 0)
        pnn_match_seg_next = self.pnn_match_seg_count + (1 if pnn_match_spike else 0)
        pnn_mis_seg_next = self.pnn_mis_seg_count + (1 if pnn_mismatch_spike else 0)
        rdm_valid_win_next = self.rdm_valid_win_count
        rdm_code_win_next = self.rdm_code_win_sum
        rdm_valid_seg_next = self.rdm_valid_seg_count
        rdm_code_seg_next = self.rdm_code_seg_sum
        ram_count_win_next = self.ram_count_win
        ram_code_win_next = self.ram_code_win_sum
        ram_seg_next = self.ram_seg_count
        ram_code_seg_next = self.ram_code_seg_sum
        rdm_ge20_next = self.rdm_ge20_seg_count
        rdm_ge50_next = self.rdm_ge50_seg_count
        rdm_ge80_next = self.rdm_ge80_seg_count
        rdm_ge100_next = self.rdm_ge100_seg_count

        if pre_qrs_bump_spike:
            self.add_c24(c24_next, "C24_W_PRE_QRS")
        if rbbb_qrs_like_beat_spike:
            self.add_c24(c24_next, "C24_W_RBBB_LIKE")
        if rbbb_qrs_delay_segment_spike:
            self.add_c24(c24_next, "C24_W_RBBB_SEGMENT")
        if pnn_match_spike:
            self.add_c24(c24_next, "C24_W_PNN_MATCH")
            self.add_local(local_next, "W_PNN_MATCH")
        if pnn_mismatch_spike:
            self.add_c24(c24_next, "C24_W_PNN_MIS")
            self.add_local(local_next, "W_PNN_MIS")
        if dscr_valid_slope_spike:
            self.add_c24(c24_next, "C24_W_DSCR_SLOPE")
            local_next[0] += _CLASS_CONSTS["W_DSCR_SLOPE_NSR"]
            local_next[1] += _CLASS_CONSTS["W_DSCR_SLOPE_CHF"]
        if dscr_sign_flip_spike:
            self.add_c24(c24_next, "C24_W_DSCR_FLIP")
            local_next[0] += _CLASS_CONSTS["W_DSCR_FLIP_NSR"]
            local_next[1] += _CLASS_CONSTS["W_DSCR_FLIP_CHF"]
        if ram_amp_spike:
            for i, cls in enumerate(CLASSES):
                c24_next[i] += _CLASS_CONSTS[f"C24_W_RAM_COUNT_{cls}"] + _CLASS_CONSTS[f"C24_W_RAM_CODE_{cls}"] * int(ram_amp_code)
            local_next[2] += _CLASS_CONSTS["W_RAM_COUNT_ARR"] + _CLASS_CONSTS["W_RAM_SUM_ARR"] * int(ram_amp_code)
            local_next[3] += _CLASS_CONSTS["W_RAM_COUNT_AFF"] + _CLASS_CONSTS["W_RAM_SUM_AFF"] * int(ram_amp_code)
            ram_count_win_next += 1
            ram_code_win_next += int(ram_amp_code)
            ram_seg_next += 1
            ram_code_seg_next += int(ram_amp_code)
        if rdm_valid_spike:
            rdm_code_calc = 0
            for idx in range(15):
                if rdm_level_spike & (1 << idx):
                    rdm_code_calc += 1
                    for ci, cls in enumerate(CLASSES):
                        local_next[ci] += _LOCAL_RDM_GE[cls][idx]
                        c24_next[ci] += _C24_RDM_LEVEL[cls][idx]
            for ci, cls in enumerate(CLASSES):
                c24_next[ci] += _CLASS_CONSTS[f"C24_W_RDM_VALID_{cls}"] + _CLASS_CONSTS[f"C24_W_RDM_CODE_{cls}"] * rdm_code_calc
                local_next[ci] += _CLASS_CONSTS[f"W_RDM_VALID_{cls}"] + _CLASS_CONSTS[f"W_RDM_CODE_{cls}"] * rdm_code_calc
            rdm_valid_win_next += 1
            rdm_code_win_next += rdm_code_calc
            rdm_valid_seg_next += 1
            rdm_code_seg_next += rdm_code_calc
            if rdm_level_spike & (1 << 1):
                rdm_ge20_next += 1
            if rdm_level_spike & (1 << 4):
                rdm_ge50_next += 1
            if rdm_level_spike & (1 << 7):
                rdm_ge80_next += 1
            if rdm_level_spike & (1 << 9):
                rdm_ge100_next += 1
        if ectopic_pair_spike:
            self.add_c24(c24_next, "C24_W_ECT_PAIR")
            self.add_local(local_next, "W_ECT_PAIR")
        if qrs_width_abn_spike or qrs_complex_abn_spike or qrs_energy_abn_spike:
            self.add_c24(c24_next, "C24_W_QRS_MAF")
        if qrs_width_abn_spike:
            self.add_c24(c24_next, "C24_W_QRS_WIDTH")
            self.add_local(local_next, "W_QRS_WIDTH_COUNT")
        if qrs_complex_abn_spike:
            self.add_c24(c24_next, "C24_W_QRS_COMPLEX")
            self.add_local(local_next, "W_QRS_COMPLEX_COUNT")
        if qrs_energy_abn_spike:
            self.add_c24(c24_next, "C24_W_QRS_ENERGY")
            self.add_local(local_next, "W_QRS_ENERGY_COUNT")
        if rhythm_tick and self.ms_count == 999:
            self.add_c24(c24_next, "C24_W_SECOND")
            self.add_local(local_next, "W_SEC")

        subwindow_period_done = bool(rhythm_tick and self.subwindow_tick_count == self.subwindow_ticks - 1)
        finalize_window = bool(subwindow_period_done or (segment_done and self.subwindow_tick_count != 0))
        window_scale_q4 = 16 if subwindow_period_done else scale_q4_from_ticks(self.subwindow_tick_count)

        pnn_decision_win = pnn_match_win_next + pnn_mis_win_next
        pnn_decision_seg = pnn_match_seg_next + pnn_mis_seg_next
        arr_high = (
            finalize_window
            and pnn_decision_win != 0
            and c24_ge_pct(pnn_mis_win_next, pnn_decision_win, 12)
            and c24_le_pct(pnn_mis_win_next, pnn_decision_win, 65)
            and rdm_valid_win_next != 0
            and c24_ge_avg(rdm_code_win_next, rdm_valid_win_next, 5)
            and c24_le_avg(rdm_code_win_next, rdm_valid_win_next, 12)
            and ram_count_win_next != 0
            and c24_ge_avg(ram_code_win_next, ram_count_win_next, 12)
            and ect_pair_win_next * 100 >= rdm_valid_win_next * 4
            and ect_pair_win_next * 100 <= rdm_valid_win_next * 35
        )

        if finalize_window:
            commit = [
                scale_score_q4(local_next[i] - self.biases[i], window_scale_q4)
                for i in range(4)
            ]
            for i in range(4):
                score_next[i] += commit[i]
            if arr_high:
                score_next[2] += scale_score_q4(_CLASS_CONSTS["W_ARR_HIGH_IRR_TO_ARR"], window_scale_q4)
                self.add_c24(c24_next, "C24_W_ARR_HIGH_IRR")

        if segment_done and not finalize_window and rbbb_qrs_delay_segment_spike:
            rbbb_delay_chf_block = score_next[1] > score_next[2]
            if not rbbb_delay_chf_block:
                score_next[0] -= 100000
                score_next[2] += 100000
                self.rbbb_qrs_delay_applied = 1
                self.add_c24(c24_next, "C24_W_RBBB_APPLIED")
            else:
                self.rbbb_qrs_delay_applied = 0
        else:
            self.rbbb_qrs_delay_applied = 0

        eerg_gate_next = (
            bool(segment_done)
            and rbbb_qrs_like_count == 0
            and pre_bump_seg_next >= 1
            and (ect_early_seg_next >= 10 or ect_pair_seg_next >= 3)
            and pnn_decision_seg != 0
            and c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 15)
            and rdm_valid_seg_next != 0
            and c24_le_avg(rdm_code_seg_next, rdm_valid_seg_next, 5)
        )
        self.score_arr_before_eerg = score_next[2]
        if segment_done and eerg_gate_next:
            score_next[2] += 25000
            self.eerg_applied = 1
            self.add_c24(c24_next, "C24_W_EERG_GATE")
            self.add_c24(c24_next, "C24_W_EERG_APPLIED")
        else:
            self.eerg_applied = 0

        if segment_done:
            if c24_ge_pct(pnn_mis_seg_next, pnn_decision_seg, 3): self.add_c24(c24_next, "C24_W_PNN_MIS_GE_3")
            if c24_ge_pct(pnn_mis_seg_next, pnn_decision_seg, 8): self.add_c24(c24_next, "C24_W_PNN_MIS_GE_8")
            if c24_ge_pct(pnn_mis_seg_next, pnn_decision_seg, 15): self.add_c24(c24_next, "C24_W_PNN_MIS_GE_15")
            if c24_ge_pct(pnn_mis_seg_next, pnn_decision_seg, 25): self.add_c24(c24_next, "C24_W_PNN_MIS_GE_25")
            if c24_ge_pct(pnn_mis_seg_next, pnn_decision_seg, 45): self.add_c24(c24_next, "C24_W_PNN_MIS_GE_45")
            if c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 3): self.add_c24(c24_next, "C24_W_PNN_MIS_LE_3")
            if c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 8): self.add_c24(c24_next, "C24_W_PNN_MIS_LE_8")
            if c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 15): self.add_c24(c24_next, "C24_W_PNN_MIS_LE_15")
            if c24_ge_avg(rdm_code_seg_next, rdm_valid_seg_next, 2): self.add_c24(c24_next, "C24_W_RDM_AVG_GE_2")
            if c24_ge_avg(rdm_code_seg_next, rdm_valid_seg_next, 4): self.add_c24(c24_next, "C24_W_RDM_AVG_GE_4")
            if c24_ge_avg(rdm_code_seg_next, rdm_valid_seg_next, 6): self.add_c24(c24_next, "C24_W_RDM_AVG_GE_6")
            if c24_ge_avg(rdm_code_seg_next, rdm_valid_seg_next, 9): self.add_c24(c24_next, "C24_W_RDM_AVG_GE_9")
            if c24_ge_avg(rdm_code_seg_next, rdm_valid_seg_next, 12): self.add_c24(c24_next, "C24_W_RDM_AVG_GE_12")
            if c24_le_avg(rdm_code_seg_next, rdm_valid_seg_next, 2): self.add_c24(c24_next, "C24_W_RDM_AVG_LE_2")
            if c24_le_avg(rdm_code_seg_next, rdm_valid_seg_next, 4): self.add_c24(c24_next, "C24_W_RDM_AVG_LE_4")
            if c24_le_avg(rdm_code_seg_next, rdm_valid_seg_next, 6): self.add_c24(c24_next, "C24_W_RDM_AVG_LE_6")
            for base, count in [("RDM_GE20", rdm_ge20_next), ("RDM_GE50", rdm_ge50_next), ("RDM_GE80", rdm_ge80_next), ("RDM_GE100", rdm_ge100_next)]:
                for th in [3, 8, 20, 40]:
                    if c24_ge_pct(count, rdm_valid_seg_next, th):
                        self.add_c24(c24_next, f"C24_W_{base}_GE_{th}")
            for th in [1, 3, 5, 8, 12]:
                if c24_ge_pct(dscr_flip_seg_next, dscr_slope_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_DSCR_GE_{th}")
            for th in [1, 3, 5]:
                if c24_le_pct(dscr_flip_seg_next, dscr_slope_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_DSCR_LE_{th}")
            for th in [2, 4, 6, 10, 14]:
                if c24_ge_avg(ram_code_seg_next, ram_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_RAM_GE_{th}")
            for th in [2, 4, 6]:
                if c24_le_avg(ram_code_seg_next, ram_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_RAM_LE_{th}")
            for th in [1, 3, 8, 15, 25]:
                if c24_ge_pct(ect_pair_seg_next, beat_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_ECP_GE_{th}")
            for th in [1, 3, 8]:
                if c24_ge_pct(pre_bump_seg_next, beat_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_PRE_GE_{th}")
            for th in [1, 3, 8, 20, 40]:
                if c24_ge_pct(qrs_maf_seg_next, qrs_valid_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_QRS_GE_{th}")
            for th in [1, 3, 8, 15]:
                if c24_ge_pct(qrs_width_seg_next, qrs_valid_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_QRS_WIDTH_GE_{th}")
            for th in [1, 3, 8, 20, 40]:
                if c24_ge_pct(qrs_energy_seg_next, qrs_valid_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_QRS_ENERGY_GE_{th}")
            for th in [1, 3, 8, 15]:
                if c24_ge_pct(rbbb_like_seg_next, beat_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_RBBB_GE_{th}")
            for th in [1, 3, 8, 15]:
                if c24_ge_pct(rbbb_wide_seg_next, rbbb_valid_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_RBBB_WIDE_GE_{th}")
                if c24_ge_pct(rbbb_terminal_seg_next, rbbb_valid_seg_next, th):
                    self.add_c24(c24_next, f"C24_W_RBBB_TERMINAL_GE_{th}")
            if c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 15) and c24_ge_pct(rbbb_like_seg_next, beat_seg_next, 2):
                self.add_c24(c24_next, "C24_W_GATE_REGULAR_RBBB_RESCUE")
            if c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 15) and (
                c24_ge_pct(qrs_width_seg_next, qrs_valid_seg_next, 2)
                or c24_ge_pct(qrs_energy_seg_next, qrs_valid_seg_next, 35)
            ):
                self.add_c24(c24_next, "C24_W_GATE_REGULAR_QRS_ARR_RESCUE")
            if (
                c24_ge_pct(ect_pair_seg_next, beat_seg_next, 3)
                and c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 35)
                and c24_le_avg(rdm_code_seg_next, rdm_valid_seg_next, 8)
            ):
                self.add_c24(c24_next, "C24_W_GATE_EPISODIC_ECTOPIC_ARR")
            if (
                rbbb_like_seg_next == 0
                and pre_bump_seg_next >= 1
                and (ect_early_seg_next >= 10 or ect_pair_seg_next >= 3)
                and c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 15)
                and c24_le_avg(rdm_code_seg_next, rdm_valid_seg_next, 5)
            ):
                self.add_c24(c24_next, "C24_W_GATE_EERG_LIKE")
            if (
                c24_ge_pct(pnn_mis_seg_next, pnn_decision_seg, 25)
                and c24_ge_avg(rdm_code_seg_next, rdm_valid_seg_next, 7)
                and c24_ge_pct(ect_pair_seg_next, beat_seg_next, 5)
            ):
                self.add_c24(c24_next, "C24_W_GATE_AFF_PERSISTENT_IRREG")
            if (
                c24_ge_pct(pnn_mis_seg_next, pnn_decision_seg, 5)
                and c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 30)
                and c24_ge_avg(rdm_code_seg_next, rdm_valid_seg_next, 2)
                and c24_le_avg(rdm_code_seg_next, rdm_valid_seg_next, 9)
            ):
                self.add_c24(c24_next, "C24_W_GATE_ARR_MID_IRREG")
            if c24_le_pct(dscr_flip_seg_next, dscr_slope_seg_next, 3) and c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 20):
                self.add_c24(c24_next, "C24_W_GATE_CHF_LOW_DSCR_LOW_IRREG")
            if (
                c24_ge_pct(dscr_flip_seg_next, dscr_slope_seg_next, 5)
                and c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 15)
                and c24_le_avg(rdm_code_seg_next, rdm_valid_seg_next, 5)
            ):
                self.add_c24(c24_next, "C24_W_GATE_NSR_HIGH_DSCR_LOW_IRREG")
            if c24_ge_avg(ram_code_seg_next, ram_seg_next, 10) and c24_le_pct(pnn_mis_seg_next, pnn_decision_seg, 20):
                self.add_c24(c24_next, "C24_W_GATE_RAM_HIGH_REGULAR")
            if c24_le_avg(ram_code_seg_next, ram_seg_next, 5) and c24_ge_pct(pnn_mis_seg_next, pnn_decision_seg, 15):
                self.add_c24(c24_next, "C24_W_GATE_RAM_LOW_IRREGULAR")

        if segment_done:
            self.pred_class = self.argmax4(c24_next)
            self.pred_valid = 1

        self.local_mem = self.biases[:] if finalize_window else local_next
        self.score_mem = score_next
        self.c24_mem = c24_next

        if rhythm_tick:
            self.ms_count = 0 if self.ms_count == 999 else self.ms_count + 1
            self.subwindow_tick_count = 0 if subwindow_period_done else self.subwindow_tick_count + 1

        if segment_done:
            self.eerg_gate = int(eerg_gate_next)
            self.eerg_pre_qrs_bump_count = pre_bump_seg_next
            self.eerg_early_count = ect_early_seg_next
            self.eerg_ecp_count = ect_pair_seg_next
            self.eerg_pnn_decision_count = pnn_decision_seg & 0xFFFF
            self.eerg_pnn_mismatch_count = pnn_mis_seg_next
            self.eerg_rdm_valid_count = rdm_valid_seg_next
            self.eerg_rdm_code_sum = rdm_code_seg_next
            self.beat_seg_count = 0
            self.dscr_flip_seg_count = 0
            self.dscr_slope_seg_count = 0
            self.ram_seg_count = 0
            self.ram_code_seg_sum = 0
            self.rdm_ge20_seg_count = 0
            self.rdm_ge50_seg_count = 0
            self.rdm_ge80_seg_count = 0
            self.rdm_ge100_seg_count = 0
            self.qrs_maf_valid_seg_count = 0
            self.qrs_maf_seg_count = 0
            self.qrs_width_abn_seg_count = 0
            self.qrs_energy_abn_seg_count = 0
            self.rbbb_valid_seg_count = 0
            self.rbbb_wide_seg_count = 0
            self.rbbb_terminal_seg_count = 0
            self.rbbb_like_seg_count = 0
            self.rbbb_segment_seg_count = 0
            self.ectopic_pair_seg_count = 0
            self.ectopic_early_seg_count = 0
            self.pre_qrs_bump_seg_count = 0
            self.pnn_match_seg_count = 0
            self.pnn_mis_seg_count = 0
            self.rdm_valid_seg_count = 0
            self.rdm_code_seg_sum = 0
        else:
            self.eerg_gate = 0
            self.beat_seg_count = beat_seg_next
            self.dscr_flip_seg_count = dscr_flip_seg_next
            self.dscr_slope_seg_count = dscr_slope_seg_next
            self.ram_seg_count = ram_seg_next
            self.ram_code_seg_sum = ram_code_seg_next
            self.rdm_ge20_seg_count = rdm_ge20_next
            self.rdm_ge50_seg_count = rdm_ge50_next
            self.rdm_ge80_seg_count = rdm_ge80_next
            self.rdm_ge100_seg_count = rdm_ge100_next
            self.qrs_maf_valid_seg_count = qrs_valid_seg_next
            self.qrs_maf_seg_count = qrs_maf_seg_next
            self.qrs_width_abn_seg_count = qrs_width_seg_next
            self.qrs_energy_abn_seg_count = qrs_energy_seg_next
            self.rbbb_valid_seg_count = rbbb_valid_seg_next
            self.rbbb_wide_seg_count = rbbb_wide_seg_next
            self.rbbb_terminal_seg_count = rbbb_terminal_seg_next
            self.rbbb_like_seg_count = rbbb_like_seg_next
            self.rbbb_segment_seg_count = rbbb_segment_seg_next
            self.ectopic_pair_seg_count = ect_pair_seg_next
            self.ectopic_early_seg_count = ect_early_seg_next
            self.pre_qrs_bump_seg_count = pre_bump_seg_next
            self.pnn_match_seg_count = pnn_match_seg_next
            self.pnn_mis_seg_count = pnn_mis_seg_next
            self.rdm_valid_seg_count = rdm_valid_seg_next
            self.rdm_code_seg_sum = rdm_code_seg_next

        if finalize_window:
            self.ectopic_pair_win_count = 0
            self.pnn_match_win_count = 0
            self.pnn_mis_win_count = 0
            self.rdm_valid_win_count = 0
            self.rdm_code_win_sum = 0
            self.ram_count_win = 0
            self.ram_code_win_sum = 0
        else:
            self.ectopic_pair_win_count = ect_pair_win_next
            self.pnn_match_win_count = pnn_match_win_next
            self.pnn_mis_win_count = pnn_mis_win_next
            self.rdm_valid_win_count = rdm_valid_win_next
            self.rdm_code_win_sum = rdm_code_win_next
            self.ram_count_win = ram_count_win_next
            self.ram_code_win_sum = ram_code_win_next


@dataclass
class SnapshotFrontEnd:
    event: EcgEventEncoderAdaptive = field(default_factory=EcgEventEncoderAdaptive)
    qrs: QrsLifDetector = field(default_factory=QrsLifDetector)
    pnn: PnnRhythmPredictor = field(default_factory=PnnRhythmPredictor)
    rdm: RdmVariabilityNeuron = field(default_factory=RdmVariabilityNeuron)
    ectopic: EctopicPairNeuron = field(default_factory=EctopicPairNeuron)
    dscr: DscrSpikeCounter = field(default_factory=DscrSpikeCounter)
    ram: RamPeakAccumulator = field(default_factory=RamPeakAccumulator)
    qrs_maf: QrsMafNeuron = field(default_factory=QrsMafNeuron)
    rbbb: RbbbQrsDelayBank = field(default_factory=RbbbQrsDelayBank)
    score: C24ScoreNeurons = field(default_factory=C24ScoreNeurons)
    qrs_sample_valid: int = 0
    rdm_rr_valid_delay: int = 0
    qrs_count: int = 0
    pnn_match_count: int = 0
    pnn_mismatch_count: int = 0
    dscr_flip_count: int = 0
    dscr_slope_count: int = 0
    ram_code_sum: int = 0
    ram_code_count: int = 0
    rdm_valid_count: int = 0
    rdm_code_sum: int = 0
    rdm_ge_count: list[int] = field(default_factory=lambda: [0] * 15)
    ectopic_pair_count: int = 0
    qrs_maf_valid_count: int = 0
    qrs_maf_count: int = 0
    qrs_maf_code_sum: int = 0
    qrs_width_abn_count: int = 0
    qrs_complex_abn_count: int = 0
    qrs_energy_abn_count: int = 0
    pre_qrs_bump_count: int = 0
    qrs_maf_width_sum: int = 0
    qrs_maf_complex_sum: int = 0
    qrs_maf_energy_sum: int = 0
    rbbb_delay_valid_count: int = 0
    rbbb_delay_wide_count: int = 0
    rbbb_delay_terminal_count: int = 0
    rbbb_delay_like_count: int = 0
    rbbb_delay_segment_count: int = 0
    rbbb_delay_applied_count: int = 0
    eerg_gate_count: int = 0
    eerg_applied_count: int = 0
    strong_event_count: int = 0

    def reset(self) -> None:
        self.event.reset()
        self.qrs.reset()
        self.pnn.reset()
        self.rdm.reset()
        self.ectopic.reset()
        self.dscr.reset()
        self.ram.reset()
        self.qrs_maf.reset()
        self.rbbb.reset()
        self.score.reset()
        self.qrs_sample_valid = 0
        self.rdm_rr_valid_delay = 0
        self.qrs_count = 0
        self.pnn_match_count = 0
        self.pnn_mismatch_count = 0
        self.dscr_flip_count = 0
        self.dscr_slope_count = 0
        self.ram_code_sum = 0
        self.ram_code_count = 0
        self.rdm_valid_count = 0
        self.rdm_code_sum = 0
        self.rdm_ge_count = [0] * 15
        self.ectopic_pair_count = 0
        self.qrs_maf_valid_count = 0
        self.qrs_maf_count = 0
        self.qrs_maf_code_sum = 0
        self.qrs_width_abn_count = 0
        self.qrs_complex_abn_count = 0
        self.qrs_energy_abn_count = 0
        self.pre_qrs_bump_count = 0
        self.qrs_maf_width_sum = 0
        self.qrs_maf_complex_sum = 0
        self.qrs_maf_energy_sum = 0
        self.rbbb_delay_valid_count = 0
        self.rbbb_delay_wide_count = 0
        self.rbbb_delay_terminal_count = 0
        self.rbbb_delay_like_count = 0
        self.rbbb_delay_segment_count = 0
        self.rbbb_delay_applied_count = 0
        self.eerg_gate_count = 0
        self.eerg_applied_count = 0
        self.strong_event_count = 0

    def tick(self, sample_valid: int, rhythm_tick: int, segment_start: int, segment_done: int = 0, adc_data: int = 0) -> None:
        old_qrs_sample_valid = self.qrs_sample_valid
        old_rdm_rr_valid_delay = self.rdm_rr_valid_delay
        old_strong_event = self.event.strong_event
        old_slope_valid = self.event.slope_valid
        old_abs_delta = self.event.abs_delta
        old_beat_spike = self.qrs.beat_spike
        old_pnn_match = self.pnn.pnn_match_spike
        old_pnn_mismatch = self.pnn.pnn_mismatch_spike
        old_pnn_token_active = self.pnn.token_active
        old_pnn_rr_interval = self.pnn.rr_interval
        old_rdm_valid = self.rdm.rr_diff_valid_spike
        old_rdm_level = self.rdm.rdm_level_spike
        old_rdm_code = self.rdm.rdm_level_code
        old_ectopic_pair = self.ectopic.ectopic_pair_spike
        old_dscr_valid = self.dscr.valid_slope_spike
        old_dscr_flip = self.dscr.sign_flip_spike
        old_ram_spike = self.ram.ram_amp_spike
        old_ram_code = self.ram.ram_amp_code
        old_qrs_maf_valid = self.qrs_maf.qrs_maf_valid_spike
        old_qrs_width_abn = self.qrs_maf.qrs_width_abn_spike
        old_qrs_complex_abn = self.qrs_maf.qrs_complex_abn_spike
        old_qrs_energy_abn = self.qrs_maf.qrs_energy_abn_spike
        old_pre_qrs_bump = self.qrs_maf.pre_qrs_bump_spike
        old_qrs_width_value = self.qrs_maf.qrs_width_value
        old_qrs_complex_count = self.qrs_maf.qrs_complex_count
        old_qrs_energy_code = self.qrs_maf.qrs_energy_code
        old_rbbb_valid = self.rbbb.qrs_valid_spike
        old_rbbb_wide = self.rbbb.wide_qrs_spike
        old_rbbb_terminal = self.rbbb.terminal_delay_spike
        old_rbbb_like = self.rbbb.rbbb_like_beat_spike
        old_rbbb_like_count = self.rbbb.rbbb_like_beat_count
        rbbb_segment_now = self.rbbb.segment_spike(segment_done)
        old_score_rbbb_applied = self.score.rbbb_qrs_delay_applied
        old_score_eerg_gate = self.score.eerg_gate
        old_score_eerg_applied = self.score.eerg_applied

        ram_predictor_center = self.pnn.hyp_center(self.pnn.predictor_id)
        ram_predictor_error = self.pnn.abs_diff(self.pnn.token_age, ram_predictor_center)
        old_ram_window_open = int(self.pnn.token_active and self.pnn.predictor_valid and ram_predictor_error <= self.pnn.window_half)

        if old_beat_spike:
            self.qrs_count += 1
        if old_pnn_match:
            self.pnn_match_count += 1
        if old_pnn_mismatch:
            self.pnn_mismatch_count += 1
        if old_rdm_valid:
            self.rdm_valid_count += 1
            self.rdm_code_sum += old_rdm_code
            for i in range(15):
                if old_rdm_level & (1 << i):
                    self.rdm_ge_count[i] += 1
        if old_ectopic_pair:
            self.ectopic_pair_count += 1
        if old_dscr_valid:
            self.dscr_slope_count += 1
        if old_dscr_flip:
            self.dscr_flip_count += 1
        if old_ram_spike:
            self.ram_code_count += 1
            self.ram_code_sum += old_ram_code
        if old_qrs_maf_valid:
            self.qrs_maf_valid_count += 1
            self.qrs_maf_width_sum += old_qrs_width_value
            self.qrs_maf_complex_sum += old_qrs_complex_count
            self.qrs_maf_energy_sum += old_qrs_energy_code
        if old_qrs_width_abn or old_qrs_complex_abn or old_qrs_energy_abn:
            self.qrs_maf_count += 1
            self.qrs_maf_code_sum += old_qrs_energy_code
        if old_qrs_width_abn:
            self.qrs_width_abn_count += 1
        if old_qrs_complex_abn:
            self.qrs_complex_abn_count += 1
        if old_qrs_energy_abn:
            self.qrs_energy_abn_count += 1
        if old_pre_qrs_bump:
            self.pre_qrs_bump_count += 1
        if old_rbbb_valid:
            self.rbbb_delay_valid_count += 1
        if old_rbbb_wide:
            self.rbbb_delay_wide_count += 1
        if old_rbbb_terminal:
            self.rbbb_delay_terminal_count += 1
        if old_rbbb_like:
            self.rbbb_delay_like_count += 1
        if rbbb_segment_now:
            self.rbbb_delay_segment_count += 1
        if old_score_rbbb_applied:
            self.rbbb_delay_applied_count += 1
        if old_score_eerg_gate:
            self.eerg_gate_count += 1
        if old_score_eerg_applied:
            self.eerg_applied_count += 1

        self.score.tick(
            clear=segment_start,
            rhythm_tick=rhythm_tick,
            segment_done=segment_done,
            beat_spike=old_beat_spike,
            qrs_maf_valid_spike=old_qrs_maf_valid,
            rbbb_qrs_valid_spike=old_rbbb_valid,
            rbbb_qrs_wide_spike=old_rbbb_wide,
            rbbb_qrs_terminal_spike=old_rbbb_terminal,
            rbbb_qrs_like_beat_spike=old_rbbb_like,
            pnn_match_spike=old_pnn_match,
            pnn_mismatch_spike=old_pnn_mismatch,
            dscr_valid_slope_spike=old_dscr_valid,
            dscr_sign_flip_spike=old_dscr_flip,
            ram_amp_spike=old_ram_spike,
            ram_amp_code=old_ram_code,
            rdm_valid_spike=old_rdm_valid,
            rdm_level_spike=old_rdm_level,
            rdm_level_code=old_rdm_code,
            ectopic_pair_spike=old_ectopic_pair,
            ectopic_early_spike=self.ectopic.early_rr_spike,
            pre_qrs_bump_spike=old_pre_qrs_bump,
            qrs_width_abn_spike=old_qrs_width_abn,
            qrs_complex_abn_spike=old_qrs_complex_abn,
            qrs_energy_abn_spike=old_qrs_energy_abn,
            rbbb_qrs_delay_segment_spike=rbbb_segment_now,
            rbbb_qrs_like_count=old_rbbb_like_count,
        )

        self.event.tick(sample_valid=sample_valid, segment_start=segment_start, adc_data=adc_data)
        self.qrs.tick(sample_valid=old_qrs_sample_valid, strong_event=old_strong_event)
        self.pnn.tick(clear=segment_start, rhythm_tick=rhythm_tick, beat_spike=old_beat_spike)
        self.rdm.tick(clear=segment_start, rr_interval_valid_spike=old_rdm_rr_valid_delay, rr_interval_in=old_pnn_rr_interval)
        self.ectopic.tick(clear=segment_start, rr_interval_valid_spike=old_rdm_rr_valid_delay, rr_interval_in=old_pnn_rr_interval)
        self.dscr.tick(clear=segment_start, sample_valid=old_qrs_sample_valid, adc_data=adc_data)
        self.ram.tick(clear=segment_start, sample_valid=sample_valid, ram_window_open=old_ram_window_open, beat_spike=old_beat_spike, adc_data=adc_data, baseline=0)
        self.qrs_maf.tick(
            clear=segment_start,
            sample_valid=sample_valid,
            adc_data=adc_data,
            strong_event=old_strong_event,
            dscr_sign_flip_spike=old_dscr_flip,
            beat_spike=old_beat_spike,
            baseline=0,
        )
        self.rbbb.tick(
            clear=segment_start,
            sample_valid=sample_valid,
            segment_done=segment_done,
            strong_event=old_strong_event,
            slope_valid=old_slope_valid,
            abs_delta=old_abs_delta,
            pnn_match_spike=old_pnn_match,
            pnn_mismatch_spike=old_pnn_mismatch,
            rdm_valid_spike=old_rdm_valid,
            rdm_level_spike=old_rdm_level,
            rdm_level_code=old_rdm_code,
        )
        self.qrs_sample_valid = 1 if sample_valid else 0
        self.rdm_rr_valid_delay = 1 if (old_beat_spike and old_pnn_token_active and not segment_start) else 0

        if self.event.strong_event:
            self.strong_event_count += 1

    def run_window(self, samples: np.ndarray) -> dict[str, int]:
        self.reset()
        last_sample = int(samples[0]) if len(samples) else 0
        self.tick(sample_valid=0, rhythm_tick=0, segment_start=1, segment_done=0, adc_data=0)
        for sample in samples:
            last_sample = int(sample)
            self.tick(sample_valid=1, rhythm_tick=1, segment_start=0, segment_done=0, adc_data=last_sample)
        self.tick(sample_valid=0, rhythm_tick=0, segment_start=0, segment_done=1, adc_data=last_sample)
        # The dataset testbench prints immediately after repeat(10) @(posedge clk).
        # The 10th edge's nonblocking counter/register updates are not visible to
        # that print, so the Python observation point is after 9 post-done ticks.
        for _ in range(9):
            self.tick(sample_valid=0, rhythm_tick=0, segment_start=0, segment_done=0, adc_data=last_sample)
        return {
            "beat_count": self.qrs_count,
            "pnn_match_count": self.pnn_match_count,
            "pnn_mismatch_count": self.pnn_mismatch_count,
            "dscr_flip_count": self.dscr_flip_count,
            "dscr_slope_count": self.dscr_slope_count,
            "ram_code_sum": self.ram_code_sum,
            "ram_code_count": self.ram_code_count,
            "rdm_valid_count": self.rdm_valid_count,
            "rdm_code_sum": self.rdm_code_sum,
            "ectopic_pair_count": self.ectopic_pair_count,
            "qrs_maf_valid_count": self.qrs_maf_valid_count,
            "qrs_maf_count": self.qrs_maf_count,
            "qrs_maf_code_sum": self.qrs_maf_code_sum,
            "qrs_width_abn_count": self.qrs_width_abn_count,
            "qrs_complex_abn_count": self.qrs_complex_abn_count,
            "qrs_energy_abn_count": self.qrs_energy_abn_count,
            "pre_qrs_bump_count": self.pre_qrs_bump_count,
            "qrs_maf_width_sum": self.qrs_maf_width_sum,
            "qrs_maf_complex_sum": self.qrs_maf_complex_sum,
            "qrs_maf_energy_sum": self.qrs_maf_energy_sum,
            "rbbb_delay_valid_count": self.rbbb_delay_valid_count,
            "rbbb_delay_wide_count": self.rbbb_delay_wide_count,
            "rbbb_delay_terminal_count": self.rbbb_delay_terminal_count,
            "rbbb_delay_like_count": self.rbbb_delay_like_count,
            "rbbb_delay_segment_count": self.rbbb_delay_segment_count,
            "rbbb_delay_applied_count": self.rbbb_delay_applied_count,
            "eerg_gate_count": self.eerg_gate_count,
            "eerg_applied_count": self.eerg_applied_count,
            "eerg_pre_qrs_bump_count": self.score.eerg_pre_qrs_bump_count,
            "eerg_early_count": self.score.eerg_early_count,
            "eerg_ecp_count": self.score.eerg_ecp_count,
            "eerg_pnn_decision_count": self.score.eerg_pnn_decision_count,
            "eerg_pnn_mismatch_count": self.score.eerg_pnn_mismatch_count,
            "eerg_rdm_valid_count": self.score.eerg_rdm_valid_count,
            "eerg_rdm_code_sum": self.score.eerg_rdm_code_sum,
            "score_arr_before_eerg": self.score.score_arr_before_eerg,
            "class_mem_NSR": self.score.c24_mem[0],
            "class_mem_CHF": self.score.c24_mem[1],
            "class_mem_ARR": self.score.c24_mem[2],
            "class_mem_AFF": self.score.c24_mem[3],
            "c24_mem_NSR": self.score.c24_mem[0],
            "c24_mem_CHF": self.score.c24_mem[1],
            "c24_mem_ARR": self.score.c24_mem[2],
            "c24_mem_AFF": self.score.c24_mem[3],
            "score_nsr": self.score.score_mem[0],
            "score_chf": self.score.score_mem[1],
            "score_arr": self.score.score_mem[2],
            "score_aff": self.score.score_mem[3],
            "pred_class": self.score.pred_class,
            "pred_valid": self.score.pred_valid,
            "strong_event_count": self.strong_event_count,
            "adaptive_event_th": self.event.adaptive_event_th,
            "adaptive_ready": self.event.adaptive_ready,
            **{f"rdm_ge{(i + 1) * 10}_count": self.rdm_ge_count[i] for i in range(15)},
        }


def run_qrs_on_mem(path: Path) -> dict[str, int]:
    samples = s12_from_hex_mem(path)
    return SnapshotFrontEnd().run_window(samples)
