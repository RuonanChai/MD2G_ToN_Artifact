#!/usr/bin/env python3
"""opt6 must request a moq-sub when honored base changes even if enh stays 0."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "strategies"))
from rep_lifecycle_v2 import plan_transition  # noqa: E402
import dispatch_strategy_enhanced_unified_Sigcomm as disp  # noqa: E402


def test_plan_transition_base_change_needs_switch():
    target, need = plan_transition(3, 2, 0)
    assert target == 2
    assert need is True


def test_opt6_gate_off_by_default():
    os.environ.pop("TON_G2_OPT6_HONOR_BASE_SWITCH", None)
    assert disp._opt6_honor_base_switch() is False


def test_opt6_gate_on():
    os.environ["TON_G2_OPT6_HONOR_BASE_SWITCH"] = "1"
    try:
        assert disp._opt6_honor_base_switch() is True
        target, need = plan_transition(3, 2, 0)
        assert need and disp._opt6_honor_base_switch()
        last_decision = 0
        decision = 0
        enter = (
            decision != last_decision
            or (need and disp._opt6_honor_base_switch())
        )
        assert enter is True
    finally:
        os.environ.pop("TON_G2_OPT6_HONOR_BASE_SWITCH", None)


if __name__ == "__main__":
    test_plan_transition_base_change_needs_switch()
    test_opt6_gate_off_by_default()
    test_opt6_gate_on()
    print("PASS test_command131_opt6_base_switch")
