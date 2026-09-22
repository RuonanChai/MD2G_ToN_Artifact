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
"""command120: playability signals must change when the underlying event changes."""
import sys
from pathlib import Path

import pytest

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))

from ton_playability_telemetry import (
    REQUIRED_PLAYABILITY_FIELDS,
    OnlineCapacityEstimator,
    build_playability_payload,
    fail_closed_or_raise,
    missing_required,
    stamp_playability_into_decisions,
)


def _payload(**over):
    base = dict(
        buffer_level_sec=4.0,
        stall_active=False,
        stall_elapsed_sec=0.0,
        last_playable_timestamp=100.0,
        active_rep=3,
        object_bytes=1_000_000,
        received_bytes=400_000,
        bytes_remaining_by_rep={3: 600_000, 5: 800_000},
        recent_object_completion_s=1.0,
        stream_open_latency_s=0.12,
        switch_latency_s=0.05,
        delivery_rate_mbps=8.0,
        access_capacity_mbps=12.0,
        app_limited=False,
        group_id=1,
        active_group_rep_streams=[[1, 3]],
        weak_user_quality_deficit=0.1,
    )
    base.update(over)
    return build_playability_payload(**base)


def test_required_fields_present():
    p = _payload()
    assert missing_required(p) == []
    for k in REQUIRED_PLAYABILITY_FIELDS:
        assert k in p


def test_buffer_changes_playable_ahead():
    a = _payload(buffer_level_sec=1.0)
    b = _payload(buffer_level_sec=6.0)
    assert a["playable_ahead_sec"] != b["playable_ahead_sec"]
    assert b["playable_ahead_sec"] > a["playable_ahead_sec"]


def test_stall_flag_and_elapsed_change():
    a = _payload(stall_active=False, stall_elapsed_sec=0.0)
    b = _payload(stall_active=True, stall_elapsed_sec=2.5)
    assert a["stall_active"] is False
    assert b["stall_active"] is True
    assert b["stall_elapsed_sec"] > a["stall_elapsed_sec"]


def test_remaining_bytes_change_with_received():
    a = _payload(received_bytes=100_000, object_bytes=1_000_000)
    b = _payload(received_bytes=900_000, object_bytes=1_000_000)
    assert b["bytes_remaining_current_object"] < a["bytes_remaining_current_object"]
    assert b["rep_completion_frac"] > a["rep_completion_frac"]


def test_open_and_switch_latency_change():
    a = _payload(stream_open_latency_s=0.05, switch_latency_s=0.01)
    b = _payload(stream_open_latency_s=0.40, switch_latency_s=0.80)
    assert b["stream_open_latency_s"] > a["stream_open_latency_s"]
    assert b["switch_latency_s"] > a["switch_latency_s"]


def test_active_stream_set_changes():
    a = _payload(active_group_rep_streams=[[1, 3]])
    b = _payload(active_group_rep_streams=[[1, 3], [1, 5]])
    assert a["active_group_rep_streams"] != b["active_group_rep_streams"]


def test_fail_closed_no_default_buffer():
    with pytest.raises(RuntimeError, match="PLAYABILITY_FAIL_CLOSED"):
        fail_closed_or_raise({}, enabled=True)
    with pytest.raises(RuntimeError, match="no default mean_buf=5.0"):
        stamp_playability_into_decisions({1: {"selected_rep": 3}}, {}, fail_closed=True)


def test_capacity_estimator_tracks_delivery_when_not_app_limited():
    est = OnlineCapacityEstimator(alpha=0.5, init_mbps=1.0)
    cap1, lim1 = est.update(
        rx_bytes_delta=1_000_000, dt_s=1.0, buffer_level_sec=1.0, outstanding_bytes=500_000,
    )
    cap2, lim2 = est.update(
        rx_bytes_delta=2_000_000, dt_s=1.0, buffer_level_sec=1.0, outstanding_bytes=500_000,
    )
    assert lim1 is False and lim2 is False
    assert cap2 > cap1


def test_capacity_estimator_freezes_when_app_limited():
    est = OnlineCapacityEstimator(alpha=0.5, init_mbps=1.0)
    cap_busy, _ = est.update(
        rx_bytes_delta=1_250_000, dt_s=1.0, buffer_level_sec=1.0, outstanding_bytes=400_000,
    )
    cap_full, lim = est.update(
        rx_bytes_delta=10_000, dt_s=1.0, buffer_level_sec=11.5, buffer_cap_sec=12.0,
        outstanding_bytes=0.0,
    )
    assert lim is True
    assert abs(cap_full - cap_busy) < 1e-9


def test_oracle_not_used_as_access_capacity():
    p = _payload(access_capacity_mbps=9.0, oracle_trace_sample_mbps=40.0)
    assert p["access_capacity_mbps"] == 9.0
    assert p["oracle_trace_sample_mbps"] == 40.0
    assert p["capacity_signal_provenance"] == "command122_hybrid_demand_limited_probe"
