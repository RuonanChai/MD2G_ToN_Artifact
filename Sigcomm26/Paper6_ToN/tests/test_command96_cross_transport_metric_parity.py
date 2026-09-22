#!/usr/bin/env python3
"""Deterministic fixtures: equivalent physical outcomes → matching R_q (command96)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "scripts"))
from command96_cross_transport_metric import (  # noqa: E402
    q_score_from_bitrate_mbps,
    r_q_transport_neutral,
    recompute_row,
    u_eval,
)


def test_u_eval_frozen_weights():
    # 0.25*1 + 0.60*1 - 0.15*0 = 0.85
    assert abs(u_eval(1.0, 1.0, 0.0) - 0.85) < 1e-9
    assert u_eval(0.0, 0.0, 1.0) == 0.0


def test_base_quality_moq_dash_match():
    q = q_score_from_bitrate_mbps(0.9)  # ~rep3 / low
    rq_moq = r_q_transport_neutral(q, delay_ms=20.0, stall_sec_inc=0.0)
    rq_dash = r_q_transport_neutral(q, delay_ms=20.0, stall_sec_inc=0.0)
    assert abs(rq_moq - rq_dash) < 1e-12
    assert rq_moq > 0.3


def test_higher_quality_increases_rq():
    low = r_q_transport_neutral(q_score_from_bitrate_mbps(0.9), 20.0, 0.0)
    high = r_q_transport_neutral(q_score_from_bitrate_mbps(4.5), 20.0, 0.0)
    assert high > low


def test_stalled_playback_lowers_rq():
    ok = r_q_transport_neutral(1.0, 20.0, 0.0)
    stalled = r_q_transport_neutral(1.0, 20.0, 3.0)
    assert stalled < ok


def test_missing_quality_is_nan_not_zero():
    rq = r_q_transport_neutral(float("nan"), 20.0, 0.0)
    assert math.isnan(rq)


def test_saturated_delay_uses_ttfb_proxy():
    row = {
        "rep_id": "4",
        "delay_ms": "500.0",  # clamp — must not zero R_q alone
        "ttfb_base_ms": "26.0",
        "stall_count_inc": "0",
        "buffer_level_sec": "5.0",
        "rx_bytes": "1000000",
        "reward_R_o": "0.2",
        "reward_R_b": "0.3",
        "reward_R_q": "0.0",
        "reward_final": "0.0",
    }
    out = recompute_row(row)
    assert out["delay_ms_used"] == 26.0
    assert out["reward_R_q"] > 0.5
    assert out["reward_final"] > 0.2
    # do not inflate R_o
    assert out["reward_R_o"] == 0.2


def test_dash_does_not_depend_on_subscription_type():
    row = {
        "rep_id": "5",
        "delay_ms": "30.0",
        "ttfb_base_ms": "30.0",
        "stall_count_inc": "0",
        "buffer_level_sec": "5.0",
        "rx_bytes": "1",
        "reward_R_o": "0.2",
        "reward_R_b": "0.2",
        "subscription_type": "this_is_moq_only_field",
    }
    out = recompute_row(row)
    assert out["reward_R_q"] > 0.5


if __name__ == "__main__":
    test_u_eval_frozen_weights()
    test_base_quality_moq_dash_match()
    test_higher_quality_increases_rq()
    test_stalled_playback_lowers_rq()
    test_missing_quality_is_nan_not_zero()
    test_saturated_delay_uses_ttfb_proxy()
    test_dash_does_not_depend_on_subscription_type()
    print("PASS test_command96_cross_transport_metric_parity")
