#!/usr/bin/env python3
"""Common native9 base-switch and opt7 overlap justification."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
import dispatch_strategy_enhanced_unified_Sigcomm as disp  # noqa: E402


def test_common_native9_enables_base_switch():
    os.environ["SIGCOMM_NATIVE9REP_DECISION"] = "1"
    os.environ.pop("TON_G2_OPT6_HONOR_BASE_SWITCH", None)
    try:
        assert disp._common_native9_base_switch() is True
    finally:
        os.environ.pop("SIGCOMM_NATIVE9REP_DECISION", None)


def test_opt7_justifies_positive_delta_u():
    # Rep3→Rep2: ΔQs=+0.2, overlap extra Rb small at 4 Mbps
    assert disp._opt7_overlap_justified(3, 2, 4.0, 0.84, 1.74) is True


def test_opt7_rejects_when_capacity_cannot_finish():
    assert disp._opt7_overlap_justified(3, 2, 0.5, 0.84, 1.74) is False


def test_opt7_rejects_nonpositive_qs():
    assert disp._opt7_overlap_justified(2, 3, 10.0, 1.74, 0.84) is False


if __name__ == "__main__":
    test_common_native9_enables_base_switch()
    test_opt7_justifies_positive_delta_u()
    test_opt7_rejects_when_capacity_cannot_finish()
    test_opt7_rejects_nonpositive_qs()
    print("PASS test_command131_opt7_handoff")
