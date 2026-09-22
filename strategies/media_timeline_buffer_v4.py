#!/usr/bin/env python3
"""Re-export Metric V4 media-timeline helpers for dispatch (command60/61).

Loads ``md2g_metric_v4_timeline`` from Paper6_ToN/scripts via importlib so dispatch
does not depend on scripts being a package.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TIMELINE_PATH = (
    _REPO_ROOT / "Sigcomm26" / "Paper6_ToN" / "scripts" / "md2g_metric_v4_timeline.py"
)
_mod: Any = None


def _load() -> Any:
    global _mod
    if _mod is not None:
        return _mod
    spec = importlib.util.spec_from_file_location("md2g_metric_v4_timeline", _TIMELINE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load metric timeline module from {_TIMELINE_PATH}")
    _mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_mod)
    return _mod


def playable_buffer_seconds(events: Sequence[Mapping[str, Any]]) -> float:
    return _load().playable_buffer_seconds(events)


def stall_intervals(
    events: Sequence[Mapping[str, Any]],
    duration_s: float,
) -> list[tuple[float, float]]:
    return _load().stall_intervals(events, duration_s)


def payload_ttfb_ms(
    first_media_object_wall_ts: float,
    session_start_wall_ts: float,
) -> float:
    return _load().payload_ttfb_ms(first_media_object_wall_ts, session_start_wall_ts)


def completion_ratio(
    launched_users: Sequence[str],
    per_user_media_covered_s: Mapping[str, float],
    session_s: float,
) -> float:
    return _load().completion_ratio(launched_users, per_user_media_covered_s, session_s)


def timeline_metrics_at(
    events: Sequence[Mapping[str, Any]],
    duration_s: float,
) -> tuple[float, float, list[tuple[float, float]]]:
    """Return ``(buffer_sec, playhead_media_sec, stall_intervals)`` at ``duration_s``."""
    mod = _load()
    playhead, buffer_sec, _started, _raw_stalls = mod._simulate_playback(events, duration_s)
    stalls = mod.stall_intervals(events, duration_s)
    return buffer_sec, playhead, stalls
