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

import pytest

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))

from ton_playability_telemetry import build_playability_payload
from ton_gen3_playability_probes import apply_gen3_probe_policy


def _play(**over):
    kw = dict(
        buffer_level_sec=3.0,
        stall_active=False,
        stall_elapsed_sec=0.0,
        last_playable_timestamp=10.0,
        active_rep=3,
        object_bytes=800_000,
        received_bytes=400_000,
        bytes_remaining_by_rep={3: 400_000, 5: 700_000},
        recent_object_completion_s=1.0,
        stream_open_latency_s=0.1,
        switch_latency_s=0.05,
        delivery_rate_mbps=6.0,
        access_capacity_mbps=10.0,
        app_limited=False,
        group_id=1,
        active_group_rep_streams=[[1, 3]],
        weak_user_quality_deficit=0.2,
    )
    kw.update(over)
    p = build_playability_payload(**kw)
    p.update({
        "md2g_group_id": 1,
        "device_score": 0.7,
        "selected_rep": 3,
        "rep_id": 3,
    })
    return p


def test_probe_fail_closed_without_playability():
    os.environ["TON_GEN3_PROBE_ARM"] = "COMMON_ONLY"
    os.environ["TON_GEN3_PROBE_STRICT"] = "1"
    with pytest.raises(RuntimeError, match="PLAYABILITY_FAIL_CLOSED"):
        apply_gen3_probe_policy({1: {"selected_rep": 3, "md2g_group_id": 1}})


def test_common_only_does_not_open_secondary():
    os.environ["TON_GEN3_PROBE_ARM"] = "COMMON_ONLY"
    d = {1: _play(), 2: _play(buffer_level_sec=4.0)}
    out = apply_gen3_probe_policy(d, content="redandblack")
    assert out["applied"] is True
    assert all(len(v) == 1 for v in out["active_streams"].values())


def test_open_immediate_may_add_secondary_when_capacity_allows():
    os.environ["TON_GEN3_PROBE_ARM"] = "OPEN_IMMEDIATE"
    d = {1: _play(access_capacity_mbps=20.0), 2: _play(access_capacity_mbps=18.0, buffer_level_sec=5.0)}
    out = apply_gen3_probe_policy(d, content="redandblack")
    assert out["applied"] is True
    assert out["arm"] == "OPEN_IMMEDIATE"
