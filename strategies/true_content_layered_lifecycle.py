#!/usr/bin/env python3
"""True content-layered subscription lifecycle (COMMAND135)."""
from __future__ import annotations

from dataclasses import dataclass, field


PHYSICAL = (
    "base1",
    "base2",
    "base3",
    "base1_enh1_only",
    "base1_enh2_only",
    "base2_enh1_only",
    "base2_enh2_only",
    "base3_enh1_only",
    "base3_enh2_only",
)


def publisher_track_keys(true_layering: bool) -> list[str]:
    keys = [f"base{i}" for i in (1, 2, 3)]
    for b in (1, 2, 3):
        for e in (1, 2):
            keys.append(f"base{b}_enh{e}_only" if true_layering else f"base{b}_enhanced{e}")
    return keys


def playable_bitrate_bps(tracks: dict, base_level: int, enh_depth: int) -> int:
    """Sum physical-track bit_rate_bps for the subscribed/playable layer set.

    E1/E2 enter the denominator only when those enhancement-only tracks are
    actually in the playable set (enh_depth >= 1 / >= 2).
    """
    names = physical_set(base_level, enh_depth)
    total = 0
    missing = []
    for n in sorted(names):
        meta = tracks.get(n) or {}
        br = meta.get("bit_rate_bps")
        if not br:
            missing.append(n)
            continue
        total += int(br)
    if missing or total <= 0:
        raise ValueError(f"layered playable bitrate missing={missing} total={total}")
    return total


def media_seconds_from_useful_bytes(useful_bytes: int, playable_bps: int) -> float:
    return (float(useful_bytes) * 8.0) / max(1.0, float(playable_bps))


def physical_set(base_level: int, enh_depth: int) -> frozenset[str]:
    b = int(base_level)
    d = int(enh_depth)
    if b not in (1, 2, 3) or d not in (0, 1, 2):
        raise ValueError(f"illegal action base={b} depth={d}")
    names = [f"base{b}"]
    if d >= 1:
        names.append(f"base{b}_enh1_only")
    if d >= 2:
        names.append(f"base{b}_enh2_only")
    return frozenset(names)


def same_family_delta(old_b: int, old_d: int, new_b: int, new_d: int) -> dict:
    """Return start/stop sets. Base must not restart on enhancement-only change."""
    old_s = physical_set(old_b, old_d)
    new_s = physical_set(new_b, new_d)
    start = set(new_s - old_s)
    stop = set(old_s - new_s)
    base_restart = False
    if old_b == new_b:
        base_name = f"base{old_b}"
        if base_name in start or base_name in stop:
            base_restart = True
    else:
        base_restart = True
    return {
        "start": sorted(start),
        "stop": sorted(stop),
        "keep": sorted(old_s & new_s),
        "base_restarts": base_restart,
        "cross_family": old_b != new_b,
        "illegal_mix": False,
    }


@dataclass
class LayeredLifecycle:
    base_level: int = 3
    enh_depth: int = 0
    active: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.active = set(physical_set(self.base_level, self.enh_depth))

    def apply(self, base_level: int, enh_depth: int) -> dict:
        delta = same_family_delta(self.base_level, self.enh_depth, base_level, enh_depth)
        if self.base_level == base_level and delta["base_restarts"]:
            raise RuntimeError("enhancement-only transition must not restart Base")
        self.base_level = int(base_level)
        self.enh_depth = int(enh_depth)
        self.active = set(physical_set(self.base_level, self.enh_depth))
        return delta
