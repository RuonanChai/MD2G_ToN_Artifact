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
"""command122 OnlineCapacityEstimator: demand-limited freeze + bounded probe."""
import inspect
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))

from ton_playability_telemetry import (  # noqa: E402
    CANDIDATE_SECONDARY_MBPS,
    CAPACITY_SIGNAL_PROVENANCE,
    OnlineCapacityEstimator,
    build_playability_payload,
)


def _sim(
    true_mbps: float,
    *,
    requested: float = 0.838404,
    duration_s: float = 20.0,
    dt: float = 0.25,
    drop_to: float | None = None,
    drop_at: float | None = None,
    probe: bool = True,
    transport_pacing: float | None = None,
) -> OnlineCapacityEstimator:
    est = OnlineCapacityEstimator(alpha=0.35, init_mbps=1.0, probe_enabled=probe)
    t = 0.0
    buf = 2.0
    while t < duration_s:
        path = true_mbps
        if drop_to is not None and drop_at is not None and t >= drop_at:
            path = drop_to
        snap = est.last_snapshot or {}
        probing = bool(snap.get("probe_active"))
        demand = requested
        if probing:
            demand = max(requested, est.probe_target_mbps)
        delivered = min(demand, path)
        media = min(delivered, requested)
        extra = max(0.0, delivered - requested) if probing else 0.0
        media_rx = media * 1e6 / 8.0 * dt
        probe_rx = extra * 1e6 / 8.0 * dt
        stall = buf < 0.05
        if delivered >= requested:
            buf = min(12.0, max(0.25, buf + 0.01))
        else:
            buf = min(12.0, max(0.25, buf - 0.05))
        est.update(
            rx_bytes_delta=media_rx,
            dt_s=dt,
            buffer_level_sec=buf,
            outstanding_bytes=50_000,
            requested_mbps=requested,
            stall_active=stall,
            now_s=t,
            probe_rx_bytes=probe_rx,
            transport_pacing_mbps=transport_pacing,
        )
        t += dt
    return est


def test_legacy_tracks_when_not_app_limited():
    est = OnlineCapacityEstimator(alpha=0.5, init_mbps=1.0, probe_enabled=False)
    cap1, lim1 = est.update(
        rx_bytes_delta=1_000_000, dt_s=1.0, buffer_level_sec=1.0, outstanding_bytes=500_000,
    )
    cap2, lim2 = est.update(
        rx_bytes_delta=2_000_000, dt_s=1.0, buffer_level_sec=1.0, outstanding_bytes=500_000,
    )
    assert lim1 is False and lim2 is False
    assert cap2 > cap1


def test_demand_limited_does_not_self_lock_to_common_goodput():
    """Reproduce the prefix defect: buf≈1s, outstanding≫1, delivery≈0.88, app_limited was False."""
    est = OnlineCapacityEstimator(probe_enabled=False, init_mbps=1.0)
    for i in range(40):
        rx = 0.838404 * 1e6 / 8.0
        est.update(
            rx_bytes_delta=rx, dt_s=1.0, buffer_level_sec=1.03, outstanding_bytes=80_000,
            requested_mbps=0.838404, stall_active=False, now_s=float(i),
        )
    # Without probe, freeze must NOT follow 0.88 down from a higher NAL... here never had NAL,
    # so estimate stays near init, not 0.88.
    assert est.last_snapshot["demand_limited"] is True
    assert abs(est.ema_mbps - 0.838404) > 0.05
    assert est.ema_mbps >= 0.9


def test_probe_discovers_headroom_on_fat_pipe():
    est = _sim(8.0, duration_s=16.0)
    cap = est.ema_mbps
    assert cap >= CANDIDATE_SECONDARY_MBPS
    assert cap > 1.2
    assert not (0.70 <= cap <= 1.05), cap  # must not remain pinned near 0.88


def test_probe_bytes_accounted_separately_on_fat_pipe():
    est = _sim(12.0, duration_s=16.0)
    assert est.probe_bytes_total > 0
    assert est.last_snapshot["probe_bytes"] > 0
    assert est.ema_mbps + 1e-9 >= CANDIDATE_SECONDARY_MBPS



def test_infeasible_on_1_2_mbps():
    est = _sim(1.2, duration_s=16.0)
    assert est.ema_mbps + 1e-9 < CANDIDATE_SECONDARY_MBPS


def test_feasible_on_2_0_mbps():
    est = _sim(2.0, duration_s=16.0)
    assert est.ema_mbps + 1e-9 >= CANDIDATE_SECONDARY_MBPS


def test_downward_after_capacity_drop():
    est = _sim(8.0, duration_s=24.0, drop_to=1.2, drop_at=12.0)
    assert est.ema_mbps + 1e-9 < CANDIDATE_SECONDARY_MBPS


def test_oracle_kwargs_never_enter_estimate():
    est = OnlineCapacityEstimator(probe_enabled=False, init_mbps=1.0)
    cap, _ = est.update(
        rx_bytes_delta=0.838404 * 1e6 / 8.0, dt_s=1.0, buffer_level_sec=1.0,
        outstanding_bytes=80_000, requested_mbps=0.838404, stall_active=False, now_s=0.0,
        configured_bw_mbps=40.0, oracle_mininet_configured_mbps=40.0, mininet_bw_mbps=40.0,
    )
    assert cap < 5.0
    src = inspect.getsource(OnlineCapacityEstimator.update)
    # Decision path must not read those names except to ignore them.
    assert "kwargs" in src
    payload = build_playability_payload(
        buffer_level_sec=4.0, stall_active=False, stall_elapsed_sec=0.0,
        last_playable_timestamp=1.0, active_rep=3, object_bytes=1e6, received_bytes=4e5,
        bytes_remaining_by_rep={3: 6e5}, recent_object_completion_s=1.0,
        stream_open_latency_s=0.1, switch_latency_s=0.05, delivery_rate_mbps=0.88,
        access_capacity_mbps=cap, app_limited=True, group_id=1,
        active_group_rep_streams=[[1, 3]], weak_user_quality_deficit=0.1,
        oracle_mininet_configured_mbps=40.0,
    )
    assert payload["access_capacity_mbps"] == cap
    assert payload["oracle_mininet_configured_mbps"] == 40.0
    assert payload["capacity_signal_provenance"] == CAPACITY_SIGNAL_PROVENANCE


def test_l1_transport_pacing_preferred():
    est = OnlineCapacityEstimator(probe_enabled=False, init_mbps=1.0)
    cap, _ = est.update(
        rx_bytes_delta=0.838404 * 1e6 / 8.0, dt_s=1.0, buffer_level_sec=1.0,
        outstanding_bytes=80_000, requested_mbps=0.838404, stall_active=False, now_s=0.0,
        transport_pacing_mbps=12.0,
    )
    assert cap >= 10.0
    assert est.last_snapshot["estimator_source"].startswith("l1_")


def test_stability_no_feasibility_chatter_on_fat_pipe():
    est = _sim(30.0, duration_s=20.0, dt=0.25)
    hist = est._feas_hist[-12:]
    assert hist and all(hist)
