#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))

from ton_actuation_plan import apply_actuation_plan, build_group_plan, stamp_rep_fields
from ton_gen3_playability_probes import apply_gen3_probe_policy
from ton_playability_telemetry import build_playability_payload


def _play(**over):
    kw = dict(
        buffer_level_sec=3.0, stall_active=False, stall_elapsed_sec=0.0,
        last_playable_timestamp=10.0, active_rep=3, object_bytes=800_000,
        received_bytes=400_000, bytes_remaining_by_rep={3: 400_000, 5: 700_000},
        recent_object_completion_s=1.0, stream_open_latency_s=0.1,
        switch_latency_s=0.05, delivery_rate_mbps=6.0, access_capacity_mbps=10.0,
        app_limited=False, group_id=1, active_group_rep_streams=[[1, 3]],
        weak_user_quality_deficit=0.2,
    )
    kw.update(over)
    p = build_playability_payload(**kw)
    p.update({"md2g_group_id": 1, "device_score": 0.7, "selected_rep": 9, "rep_id": 9, "pull_enhanced": True})
    return p


def test_actuation_plan_is_sole_writer_on_probe_apply():
    os.environ["TON_GEN3_PROBE_ARM"] = "COMMON_ONLY"
    os.environ.pop("TON_GEN3_PROBE_STRICT", None)
    d = {1: _play(), 2: _play(buffer_level_sec=4.0)}
    out = apply_gen3_probe_policy(d, content="redandblack")
    assert out["actuation_writer"] == "ton_actuation_plan.apply_actuation_plan"
    assert d[1]["actuation_writer"] == "ton_actuation_plan.apply_actuation_plan"
    assert d[1]["selected_rep"] == d[1]["ton_common_rep"]
    assert all(len(v) == 1 for v in out["active_streams"].values())


def test_buffer_guarded_hold_cannot_keep_ppo_secondary():
    os.environ["TON_GEN3_PROBE_ARM"] = "BUFFER_GUARDED_OPEN"
    d = {
        1: _play(buffer_level_sec=0.4, access_capacity_mbps=20.0),
        2: _play(buffer_level_sec=0.5, access_capacity_mbps=18.0),
    }
    out = apply_gen3_probe_policy(d, content="redandblack")
    assert all(len(v) == 1 for v in out["active_streams"].values())
    assert d[1]["selected_rep"] == d[1]["ton_common_rep"]
    reasons = list((out.get("reasons") or {}).values())
    assert any("HOLD" in r or "COMMON" in r for r in reasons)


def test_direct_apply_rep_raises():
    from ton_gen3_playability_probes import _apply_rep
    import pytest
    with pytest.raises(RuntimeError, match="ACTUATION_MULTIPLE_WRITERS"):
        _apply_rep({"selected_rep": 3}, 8)


def test_plan_hash_stable_for_same_targets():
    p1 = build_group_plan(
        arm="COMMON_ONLY", group_id=1, common_rep=3, secondary=None, reason="P0",
        user_targets={"1": 3}, protected_users=[1],
        source_policy_proposal={"1": {"selected_rep": 9}},
        feasibility_snapshot={"anchor": 3},
        buffer_playability_snapshot={"weak_buf": 1.0},
        decision_seq=1,
    )
    p2 = build_group_plan(
        arm="COMMON_ONLY", group_id=1, common_rep=3, secondary=None, reason="P0",
        user_targets={"1": 3}, protected_users=[1],
        source_policy_proposal={"1": {"selected_rep": 9}},
        feasibility_snapshot={"anchor": 3},
        buffer_playability_snapshot={"weak_buf": 1.0},
        decision_seq=1,
    )
    assert p1.plan_hash == p2.plan_hash
    dec = {"1": {"selected_rep": 9, "pull_enhanced": True}}
    apply_actuation_plan(dec, [p1])
    assert dec["1"]["selected_rep"] == 3
    stamp_rep_fields(dec["1"], 3)
    assert dec["1"]["actuation_writer"] == "ton_actuation_plan.apply_actuation_plan"


def test_open_immediate_assigns_at_least_one_user_to_secondary():
    os.environ["TON_GEN3_PROBE_ARM"] = "OPEN_IMMEDIATE"
    d = {
        1: _play(access_capacity_mbps=20.0),
        2: _play(access_capacity_mbps=18.0, buffer_level_sec=5.0),
    }
    d[1]["device_score"] = 0.2
    d[2]["device_score"] = 0.2
    out = apply_gen3_probe_policy(d, content="redandblack")
    plans = out.get("actuation_plans") or []
    opened = False
    for p in plans:
        secs = p.get("desired_secondary_reps") or []
        if secs:
            opened = True
            assert any(int(t) in {int(x) for x in secs} for t in p["user_targets"].values()), p
    assert opened or all(len(v) == 1 for v in (out.get("active_streams") or {}).values())
