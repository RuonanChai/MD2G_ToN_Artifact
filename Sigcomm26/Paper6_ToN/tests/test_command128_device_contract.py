#!/usr/bin/env python3
"""command128: label rename + soft device contract does not change default G2."""
from __future__ import annotations

import os
import sys
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "lib"))

from ton_native9rep_md2g_policy_g2 import score_g2, _feasible_g2  # noqa: E402
from ton_native9rep_md2g_policy_v2 import _device_need  # noqa: E402

QMAP = {r: {"q": q, "base": {1: 1, 2: 2, 3: 3, 4: 1, 5: 1, 6: 2, 7: 2, 8: 3, 9: 3}[r]} for r, q in {
    1: 0.8, 2: 0.6, 3: 0.4, 4: 1.0, 5: 1.0, 6: 0.6, 7: 0.8, 8: 0.4, 9: 0.4
}.items()}
RATES = {1: 3.07, 2: 1.79, 3: 0.87, 4: 4.54, 5: 6.42, 6: 2.8, 7: 3.91, 8: 1.43, 9: 1.97}


def _score(device: float, cand: int = 4):
    return score_g2(
        anchor=3, cand=cand, cur=3, qmap=QMAP, rates=RATES,
        device=device, capacity=40.0, delivered=2.0, group_k=4, util=0.1, deficit=0.2,
    )


def test_default_hard_gate_renamed_not_weakened():
    os.environ.pop("TON_G2_DEVICE_CONTRACT_SOFT", None)
    os.environ["TON_MD2G_CANDIDATE"] = "G2"
    s, reason = _score(0.45, 4)
    assert s is None
    assert reason == "DEVICE_CAPABILITY_INFEASIBLE"
    assert _device_need(4) == 0.70
    assert not _feasible_g2(4, device=0.45, tp=40.0, rates=RATES, margin=1.05)


def test_soft_contract_keeps_capacity():
    os.environ["TON_G2_DEVICE_CONTRACT_SOFT"] = "1"
    os.environ["TON_MD2G_CANDIDATE"] = "G2_OPT3_DEVICE_CONTRACT"
    s, reason = _score(0.45, 4)
    assert s is not None
    assert reason == "OK"
    assert _feasible_g2(4, device=0.45, tp=40.0, rates=RATES, margin=1.05)
    assert not _feasible_g2(4, device=0.45, tp=1.0, rates=RATES, margin=1.05)
    os.environ.pop("TON_G2_DEVICE_CONTRACT_SOFT", None)
    os.environ["TON_MD2G_CANDIDATE"] = "G2"


def test_avp_still_passes_default():
    os.environ.pop("TON_G2_DEVICE_CONTRACT_SOFT", None)
    os.environ["TON_MD2G_CANDIDATE"] = "G2"
    s, reason = _score(0.975, 4)
    assert s is not None


if __name__ == "__main__":
    test_default_hard_gate_renamed_not_weakened()
    print("PASS test_default_hard_gate_renamed_not_weakened")
    test_soft_contract_keeps_capacity()
    print("PASS test_soft_contract_keeps_capacity")
    test_avp_still_passes_default()
    print("PASS test_avp_still_passes_default")
    print("PASS test_command128_device_contract")
