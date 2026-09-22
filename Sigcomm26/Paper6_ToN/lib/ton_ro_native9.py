#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical native-nine-rep Ro: representation-invariant, bitrate-aware reuse.

paper_U weights stay 0.25 / 0.60 / 0.15. This module does not look at strategy
aggregates; it only defines the interval operator.

Lineage: selected_rep_equivalent_bytes
  B_unicast = sum_u bitrate(selected_rep_u) * dt
  B_shared  = sum_{(group,rep)} bitrate(rep) * dt   # each actual shared stream once
  Ro = clip(1 - B_shared / max(B_unicast, eps), 0, 1)

Do NOT use end-host Σrx as B_shared.
Do NOT use legacy Enhanced-as-unicast two-track accounting.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping, Sequence

EPS = 1e-12


def clip01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


def ro_native9_interval(
    *,
    selected_reps: Sequence[int],
    group_ids: Sequence[int],
    bitrates: Mapping[int, float],
    dt_s: float = 1.0,
    served_mask: Sequence[bool] | None = None,
) -> dict:
    """Compute Ro for one evaluation interval.

    Unserved users (served_mask False) are omitted from both B_unicast and
    B_shared so dropping users cannot inflate Ro toward 1.0 via a smaller K/N
    on a hidden full population. Service coverage is a separate gate.
    """
    n = len(selected_reps)
    if len(group_ids) != n:
        raise ValueError("selected_reps and group_ids length mismatch")
    if served_mask is None:
        served_mask = [True] * n
    uni = 0.0
    streams: dict[tuple[int, int], float] = {}
    n_served = 0
    for u in range(n):
        if not served_mask[u]:
            continue
        rid = int(selected_reps[u])
        if rid < 1:
            continue
        br = float(bitrates.get(rid, 0.0))
        if br <= 0.0:
            continue
        n_served += 1
        uni += br * dt_s
        key = (int(group_ids[u]), rid)
        streams[key] = br * dt_s  # once per (group,rep), not per recipient
    shared = float(sum(streams.values()))
    ro = clip01(1.0 - shared / max(uni, EPS)) if uni > EPS else 0.0
    return {
        "Ro_native9": ro,
        "B_unicast_equiv": uni,
        "B_shared_equiv": shared,
        "n_shared_streams": len(streams),
        "n_served": n_served,
        "n_expected": n,
        "dt_s": dt_s,
        "lineage": "selected_rep_equivalent_bytes",
    }


def mean_ro(interval_ros: Iterable[float]) -> float | None:
    xs = [float(x) for x in interval_ros]
    if not xs:
        return None
    return sum(xs) / len(xs)


def paper_u_native9(ro: float, rq: float, rb: float) -> float:
    """Frozen weights. Never change after seeing results."""
    return clip01(0.25 * float(ro) + 0.60 * float(rq) - 0.15 * float(rb))
