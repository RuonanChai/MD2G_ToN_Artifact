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

"""Command60/61: buffer must not derive from interface RX (dispatch wiring)."""
import sys
from pathlib import Path

import pytest

REPO = artifact_root()
sys.path.insert(0, str(REPO))

from strategies.media_timeline_buffer_v4 import (  # noqa: E402
    playable_buffer_seconds,
    timeline_metrics_at,
)

DISPATCH = REPO / "dispatch_strategy_enhanced_unified_Sigcomm.py"


def test_dispatch_source_wires_metric_v4_timeline() -> None:
    src = DISPATCH.read_text(encoding="utf-8")
    assert "SIGCOMM_METRIC_V4_TIMELINE" in src
    assert "playable_buffer_seconds" in src
    assert "media_timeline_buffer_v4" in src
    assert "media_events" in src
    assert "delta_dump_bytes" in src


def test_large_rx_proxy_zero_media_events_keeps_buffer_low() -> None:
    """Simulate high RX with no media payload → timeline buffer stays ~0."""
    # No media events despite hypothetical large RX (bytes field ignored for buffer).
    events: list[dict] = []
    buf, playhead, stalls = timeline_metrics_at(events, duration_s=10.0)
    assert buf == pytest.approx(0.0)
    assert playhead == pytest.approx(0.0)
    assert stalls == []


def test_media_events_raise_buffer_not_rx_bytes() -> None:
    """Media timeline arrivals increase buffer; byte count does not."""
    sparse_media = [
        {
            "t_wall": 0.0,
            "t_media_start": 0.0,
            "t_media_end": 6.0,
            "rep_id": 3,
            "bytes": 500,
        }
    ]
    huge_bytes_same_media = [
        {
            "t_wall": 0.0,
            "t_media_start": 0.0,
            "t_media_end": 6.0,
            "rep_id": 3,
            "bytes": 50_000_000,
        }
    ]
    assert playable_buffer_seconds(sparse_media) == pytest.approx(
        playable_buffer_seconds(huge_bytes_same_media)
    )
    assert playable_buffer_seconds(sparse_media) > 0.0

    # Incremental arrivals grow playable buffer at t=2s.
    incremental = [
        {
            "t_wall": 0.0,
            "t_media_start": 0.0,
            "t_media_end": 2.0,
            "rep_id": 3,
            "bytes": 100,
        },
        {
            "t_wall": 1.0,
            "t_media_start": 2.0,
            "t_media_end": 5.0,
            "rep_id": 3,
            "bytes": 200,
        },
    ]
    buf_at_2s, _, _ = timeline_metrics_at(incremental, duration_s=2.0)
    assert buf_at_2s > 0.0
