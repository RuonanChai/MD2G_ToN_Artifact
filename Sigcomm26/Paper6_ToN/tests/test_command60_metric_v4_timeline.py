#!/usr/bin/env python3
"""Regression tests for media-timeline Metric V4 helpers (command60/61)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from md2g_metric_v4_timeline import (  # noqa: E402
    DEFAULT_QS_TABLE_V4,
    completion_ratio,
    payload_ttfb_ms,
    playable_buffer_seconds,
    qs_v4,
    stall_intervals,
    time_weighted_qoe_v4,
    u_sys_v4,
)


def test_playable_buffer_from_media_timeline_not_rx_bytes() -> None:
    wide_timeline = [
        {
            "t_wall": 0.0,
            "t_media_start": 0.0,
            "t_media_end": 8.0,
            "rep_id": 3,
            "bytes": 100,
        }
    ]
    narrow_timeline_huge_bytes = [
        {
            "t_wall": 0.0,
            "t_media_start": 0.0,
            "t_media_end": 2.0,
            "rep_id": 3,
            "bytes": 9_999_999,
        }
    ]
    assert playable_buffer_seconds(wide_timeline) > playable_buffer_seconds(
        narrow_timeline_huge_bytes
    )
    # Same media span, different bytes → identical buffer (bytes ignored).
    same_media_a = [
        {"t_wall": 0.0, "t_media_start": 0.0, "t_media_end": 4.0, "rep_id": 1, "bytes": 10}
    ]
    same_media_b = [
        {"t_wall": 0.0, "t_media_start": 0.0, "t_media_end": 4.0, "rep_id": 1, "bytes": 10_000}
    ]
    assert playable_buffer_seconds(same_media_a) == pytest.approx(
        playable_buffer_seconds(same_media_b)
    )


def test_playable_buffer_consumes_during_playback() -> None:
    events = [
        {"t_wall": 0.0, "t_media_start": 0.0, "t_media_end": 3.0, "rep_id": 2, "bytes": 500},
    ]
    # Simulate through 2s of playback: 3s arrived − 2s consumed = ~1s buffer left.
    from md2g_metric_v4_timeline import _simulate_playback

    _, buf, started, _ = _simulate_playback(events, duration_s=2.0)
    assert started is True
    assert buf == pytest.approx(1.0, abs=0.05)


def test_stall_intervals_after_startup() -> None:
    events = [
        {"t_wall": 0.0, "t_media_start": 0.0, "t_media_end": 2.0, "rep_id": 3, "bytes": 100},
        {"t_wall": 5.0, "t_media_start": 2.0, "t_media_end": 4.0, "rep_id": 3, "bytes": 100},
    ]
    stalls = stall_intervals(events, duration_s=8.0)
    assert len(stalls) >= 1
    start, end = stalls[0]
    assert start == pytest.approx(2.0, abs=0.05)
    assert end == pytest.approx(5.0, abs=0.05)


def test_stall_none_before_playback_starts() -> None:
    events = [
        {"t_wall": 3.0, "t_media_start": 0.0, "t_media_end": 2.0, "rep_id": 1, "bytes": 50},
    ]
    assert stall_intervals(events, duration_s=5.0) == []


def test_completion_includes_zero_coverage_users() -> None:
    launched = ["u1", "u2", "u3"]
    covered = {"u1": 60.0, "u2": 0.0, "u3": 30.0}
    ratio = completion_ratio(launched, covered, session_s=120.0)
    # (0.5 + 0 + 0.25) / 3 launched users
    assert ratio == pytest.approx(0.25)


def test_completion_all_launched_in_denominator() -> None:
    launched = ["a", "b"]
    covered = {"a": 120.0}
    assert completion_ratio(launched, covered, session_s=120.0) == pytest.approx(0.5)


def test_payload_ttfb_from_first_media_object() -> None:
    assert payload_ttfb_ms(1.5, 1.0) == pytest.approx(500.0)
    assert payload_ttfb_ms(0.8, 1.0) == pytest.approx(0.0)


def test_default_qs_table_discriminates_rep3_and_rep8() -> None:
    assert qs_v4(3, DEFAULT_QS_TABLE_V4) == pytest.approx(0.50)
    assert qs_v4(8, DEFAULT_QS_TABLE_V4) == pytest.approx(0.72)
    assert qs_v4(3, DEFAULT_QS_TABLE_V4) != qs_v4(8, DEFAULT_QS_TABLE_V4)


def test_time_weighted_qoe_v4_uses_rendered_rep() -> None:
    segments_rep3 = [(0.0, 10.0, 3)]
    segments_rep8 = [(0.0, 10.0, 8)]
    q3 = time_weighted_qoe_v4(segments_rep3, stall_penalty=0.0, ttfb_ms=0.0)
    q8 = time_weighted_qoe_v4(segments_rep8, stall_penalty=0.0, ttfb_ms=0.0)
    assert q8 > q3


def test_u_sys_v4_identity_on_mean_qoe() -> None:
    assert u_sys_v4(0.42) == pytest.approx(0.42)
    assert u_sys_v4(1.2) == pytest.approx(1.0)
    assert u_sys_v4(-0.1) == pytest.approx(0.0)
