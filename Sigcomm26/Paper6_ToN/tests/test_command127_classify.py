#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "scripts"))
from command127_classify_and_continue import classify  # noqa: E402


def _diag(agg: dict) -> dict:
    return {"aggregate": agg, "rows": []}


def test_case_a_projector():
    body = classify(
        _diag(
            {
                "teacher_top1_gain_frac": 0.42,
                "selected_gain_frac": 0.01,
                "frac_rep3": 0.97,
                "mean_Qs": 0.4,
            }
        )
    )
    assert body["case"] == "A"
    assert body["classification"] == "PROJECTOR_FEASIBILITY_BOTTLENECK"


def test_case_c_teacher():
    body = classify(
        _diag(
            {
                "teacher_top1_gain_frac": 0.02,
                "selected_gain_frac": 0.0,
                "frac_rep3": 1.0,
                "mean_Qs": 0.4,
            }
        )
    )
    assert body["case"] == "C"
    assert body["classification"] == "TEACHER_OBJECTIVE_OR_DATA_BOTTLENECK"


def test_case_b_distill():
    body = classify(
        _diag(
            {
                "teacher_top1_gain_frac": 0.35,
                "selected_gain_frac": 0.28,
                "frac_rep3": 0.4,
                "mean_Qs": 0.55,
                "mean_Rq": 0.40,
                "mean_Rq_g2": 0.28,
                "mean_U": 0.41,
                "mean_U_opt1": 0.39,
                "mean_U_g2": 0.40,
            }
        )
    )
    assert body["case"] == "B"
    assert body["classification"] == "DISTILLATION_BOTTLENECK"


def test_case_d_tradeoff():
    body = classify(
        _diag(
            {
                "teacher_top1_gain_frac": 0.40,
                "selected_gain_frac": 0.30,
                "frac_rep3": 0.3,
                "mean_Qs": 0.62,
                "mean_Rq": 0.45,
                "mean_Rq_g2": 0.28,
                "mean_U": 0.30,
                "mean_U_g2": 0.40,
                "mean_U_opt1": 0.39,
                "mean_stall": 3.0,
                "mean_stall_g2": 1.0,
            }
        )
    )
    assert body["case"] == "D"
    assert body["classification"] == "QUALITY_REUSE_TRADEOFF_FAILURE"


if __name__ == "__main__":
    for t in (test_case_a_projector, test_case_c_teacher, test_case_b_distill, test_case_d_tradeoff):
        t()
        print(f"PASS {t.__name__}")
    print("PASS test_command127_classify")
