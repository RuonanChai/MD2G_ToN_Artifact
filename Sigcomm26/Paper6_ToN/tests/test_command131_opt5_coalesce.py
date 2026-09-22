#!/usr/bin/env python3
"""opt5 keeps a singleton group-common gain-rep; opt4 still requires count>=2."""
from __future__ import annotations

import os
import sys
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "lib"))
from ton_native9rep_md2g_policy_g2 import apply_native9rep_policy_g2  # noqa: E402


def _decisions():
    return {
        1: {
            "selected_rep": 4, "rep_id": 4, "md2g_group_id": 1, "device_score": 0.97,
            "access_capacity_mbps": 20.0, "throughput_mbps": 20.0, "delivered_mbps": 4.0,
            "base_version": 1, "enhanced_level": 1,
        },
        2: {
            "selected_rep": 3, "rep_id": 3, "md2g_group_id": 1, "device_score": 0.48,
            "access_capacity_mbps": 1.0, "throughput_mbps": 1.0, "delivered_mbps": 0.8,
            "base_version": 3, "enhanced_level": 0,
        },
    }


def test_opt4_smashes_singleton_gain():
    os.environ["TON_NATIVE9REP_MD2G"] = "1"
    os.environ["TON_MD2G_CANDIDATE"] = "G2_OPT4_NATIVE9_STRUCTURAL"
    os.environ["TON_G2_OPT4_STRUCTURAL"] = "1"
    os.environ.pop("TON_G2_OPT5_COMMON_ANCHOR", None)
    d = _decisions()
    apply_native9rep_policy_g2(d, content="redandblack", util=0.2)
    assert int(d[1]["selected_rep"]) == 3


def test_opt5_keeps_singleton_common_gain():
    os.environ["TON_NATIVE9REP_MD2G"] = "1"
    os.environ["TON_MD2G_CANDIDATE"] = "G2_OPT5_FEASIBLE_COMMON_ANCHOR"
    os.environ["TON_G2_OPT5_COMMON_ANCHOR"] = "1"
    os.environ.pop("TON_G2_OPT4_STRUCTURAL", None)
    d = _decisions()
    apply_native9rep_policy_g2(d, content="redandblack", util=0.2)
    assert int(d[1]["selected_rep"]) in (1, 2, 4, 5, 6, 7)
    assert int(d[2]["selected_rep"]) == int(d[1]["selected_rep"])


if __name__ == "__main__":
    test_opt4_smashes_singleton_gain()
    print("PASS test_opt4_smashes_singleton_gain")
    test_opt5_keeps_singleton_common_gain()
    print("PASS test_opt5_keeps_singleton_common_gain")
    print("PASS test_command131_opt5_coalesce")
