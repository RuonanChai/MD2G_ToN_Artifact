#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""command115 G2-v2 reuse-preserving FoV grouping + HV3 diagnostic grouping.

Does not overwrite G2-v1 `group_by_multicast_utility` unless TON_G2_GROUPING / G2_V2
is set. Device/bandwidth never split an otherwise useful multicast group.
"""
from __future__ import annotations

import os
from typing import Any

import numpy as np

_STATE: dict[tuple, dict[str, Any]] = {}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)) or default)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.environ.get(name, str(default)) or default))
    except ValueError:
        return default


def _relay_key(n: int) -> tuple:
    return (
        n,
        os.environ.get("TON_CONTENT_ID", ""),
        os.environ.get("MM26_RELAY_ID")
        or os.environ.get("RELAY_ID")
        or os.environ.get("CONTROLLER_RELAY", "r"),
        os.environ.get("MM26_SEED", ""),
    )


def group_by_hv3_logged(device_scores, bandwidths, fov_scores, num_groups=3):
    """Replicate HV3 heuristic bandwidth_utility chunk grouping (diagnostic only)."""
    ds = np.clip(np.asarray(device_scores, dtype=float), 0.0, 1.0)
    bw = np.asarray(bandwidths, dtype=float)
    n = int(ds.size)
    if n <= 1:
        return np.zeros(n, dtype=np.int32)
    chunk = max(2, _env_int("MM26_HEURISTIC_GROUP_CHUNK", 4))
    util = ds * np.log1p(np.maximum(bw, 0.01))
    order = list(np.argsort(-util))
    assign = np.zeros(n, dtype=np.int32)
    gid = 0
    for i in range(0, n, chunk):
        for j in order[i : i + chunk]:
            assign[int(j)] = gid
        gid += 1
    return assign


def _pairwise_overlap(fs: np.ndarray) -> np.ndarray:
    fs = np.clip(fs, 0.0, 1.0)
    return 1.0 - np.abs(fs[:, None] - fs[None, :])


def _agglomerative(ov: np.ndarray, min_ov: float, max_groups: int) -> np.ndarray:
    n = ov.shape[0]
    groups = [[i] for i in range(n)]

    def mean_ov(a, b):
        return float(np.mean(ov[np.ix_(a, b)]))

    while len(groups) > max(1, max_groups):
        best, pair = -1.0, None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                m = mean_ov(groups[i], groups[j])
                if m > best:
                    best, pair = m, (i, j)
        if pair is None or best < min_ov:
            break
        i, j = pair
        groups[i] = groups[i] + groups[j]
        del groups[j]
    # continue merging while overlap is stably high
    while len(groups) > 1:
        best, pair = -1.0, None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                m = mean_ov(groups[i], groups[j])
                if m > best:
                    best, pair = m, (i, j)
        if pair is None or best < min_ov:
            break
        i, j = pair
        groups[i] = groups[i] + groups[j]
        del groups[j]
    assign = np.zeros(n, dtype=np.int32)
    for gid, members in enumerate(groups):
        for idx in members:
            assign[idx] = gid
    return assign


def _within_group_overlap(assign: np.ndarray, ov: np.ndarray, uid: int) -> float:
    members = np.where(assign == assign[uid])[0]
    if members.size <= 1:
        return 1.0
    others = members[members != uid]
    return float(np.mean(ov[uid, others]))


def group_by_reuse_preserving_fov(device_scores, bandwidths, fov_scores, num_groups=3):
    """Slow reuse-first FoV grouping with split/merge hysteresis.

    Device/bandwidth are ignored for membership (they constrain representation only).
    """
    fs = np.clip(np.asarray(fov_scores, dtype=float), 0.0, 1.0)
    n = int(fs.size)
    if n <= 1:
        return np.zeros(max(n, 0), dtype=np.int32)
    ov = _pairwise_overlap(fs)
    t_split = _env_float("TON_G2V2_SPLIT_OV", 0.35)
    t_merge = _env_float("TON_G2V2_MERGE_OV", 0.70)
    hyst = max(1, _env_int("TON_G2V2_HYST", 3))
    max_groups = max(2, min(int(num_groups), n))
    key = _relay_key(n)
    st = _STATE.get(key)

    if st is None or np.asarray(st.get("assign")).size != n:
        assign = _agglomerative(ov, min_ov=t_merge, max_groups=max_groups)
        _STATE[key] = {
            "assign": assign.copy(),
            "low_ov_strikes": np.zeros(n, dtype=np.int32),
            "merge_strikes": {},
            "tick": 0,
        }
        return assign

    prev = np.asarray(st["assign"], dtype=np.int32).copy()
    strikes = np.asarray(st["low_ov_strikes"], dtype=np.int32)
    merge_strikes: dict = dict(st.get("merge_strikes") or {})
    assign = prev.copy()

    # Split: only after sustained low overlap with current group (not device/bw).
    for i in range(n):
        wov = _within_group_overlap(assign, ov, i)
        if wov < t_split and int(np.sum(assign == assign[i])) > 1:
            strikes[i] += 1
        else:
            strikes[i] = 0
        if strikes[i] >= hyst:
            used = set(int(g) for g in assign.tolist())
            new_g = 0
            while new_g in used:
                new_g += 1
            assign[i] = new_g
            strikes[i] = 0

    # Merge: two groups with stably high cross-overlap.
    gids = sorted(set(int(g) for g in assign.tolist()))
    merged = set()
    for a in gids:
        if a in merged:
            continue
        ia = np.where(assign == a)[0]
        for b in gids:
            if b <= a or b in merged:
                continue
            ib = np.where(assign == b)[0]
            cross = float(np.mean(ov[np.ix_(ia, ib)]))
            mk = (min(a, b), max(a, b))
            if cross >= t_merge:
                merge_strikes[mk] = int(merge_strikes.get(mk, 0)) + 1
            else:
                merge_strikes[mk] = 0
            if merge_strikes.get(mk, 0) >= hyst:
                assign[assign == b] = a
                merged.add(b)
                merge_strikes[mk] = 0

    # Prevent a single giant group when overlap is actually low.
    if len(set(int(g) for g in assign.tolist())) == 1 and float(np.mean(ov)) < t_merge:
        assign = _agglomerative(ov, min_ov=t_merge, max_groups=max_groups)

    _STATE[key] = {
        "assign": assign.copy(),
        "low_ov_strikes": strikes,
        "merge_strikes": merge_strikes,
        "tick": int(st.get("tick", 0)) + 1,
        # device/bw recorded only for provenance — not used
        "ignored_device_std": float(np.std(np.asarray(device_scores, dtype=float))) if device_scores is not None else 0.0,
        "ignored_bw_std": float(np.std(np.asarray(bandwidths, dtype=float))) if bandwidths is not None else 0.0,
    }
    return assign


def grouping_mode() -> str:
    cand = os.environ.get("TON_MD2G_CANDIDATE", "").strip().upper()
    mode = os.environ.get("TON_G2_GROUPING", "").strip().upper()
    if cand in ("G2_V2", "G2V2") or mode in ("REUSE_V2", "G2_V2", "G2V2"):
        return "G2_V2"
    if mode in ("HV3", "HEURISTIC", "HV3_RELAY"):
        return "HV3_DIAG"
    return "LEGACY_UTILITY"


def dispatch_group_assignments(device_scores, bandwidths, fov_scores, num_groups=3):
    mode = grouping_mode()
    if mode == "G2_V2":
        return group_by_reuse_preserving_fov(device_scores, bandwidths, fov_scores, num_groups=num_groups)
    if mode == "HV3_DIAG":
        return group_by_hv3_logged(device_scores, bandwidths, fov_scores, num_groups=num_groups)
    return None
