#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C29 deterministic feasibility projector (part of the method).

All raw controller actions must pass through this projector before runtime apply.
Does not alter evaluation metrics; only rejects/downgrades unsafe actions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ProjectorConfig:
    base_reserve_mbps: float = 9.61
    enhancement_cost_mbps: float = 0.996
    shared_trunk_mbps: float = 200.0
    safety_margin: float = 0.05
    max_upgrades_per_tick: int = 5
    min_dwell_s: float = 2.0
    access_tail_guard: bool = True
    weak_access_capacity_mbps: float = 4.0


@dataclass
class ProjectorLog:
    accepted_upgrades: list[int] = field(default_factory=list)
    rejected_upgrades: list[dict[str, Any]] = field(default_factory=list)
    group_assignment: dict[int, int] = field(default_factory=dict)
    residual_mbps_after: float = 0.0
    contract_ok: bool = True


def project_actions(
    *,
    user_ids: list[int],
    raw_group: dict[int, int],
    raw_upgrade: dict[int, bool],
    access_capacity_mbps: dict[int, float],
    measured_residual_mbps: float | None,
    time_since_switch_s: dict[int, float],
    cfg: ProjectorConfig | None = None,
) -> tuple[dict[int, int], dict[int, bool], ProjectorLog]:
    """Enforce C29 capacity / base-playability / access / hysteresis constraints."""
    cfg = cfg or ProjectorConfig()
    log = ProjectorLog()
    # Head A: groups (stable map; missing → 0)
    groups = {u: int(raw_group.get(u, 0)) for u in user_ids}
    log.group_assignment = dict(groups)

    trunk = cfg.shared_trunk_mbps * (1.0 - cfg.safety_margin)
    residual = measured_residual_mbps
    if residual is None:
        residual = max(0.0, trunk - cfg.base_reserve_mbps)
    else:
        residual = max(0.0, float(residual))

    # Every user gets base (implicit); upgrades consume residual only
    upgrades: dict[int, bool] = {u: False for u in user_ids}
    # Prefer users already requested, sorted by access capacity descending (access-aware)
    candidates = [u for u in user_ids if bool(raw_upgrade.get(u, False))]
    candidates.sort(key=lambda u: (access_capacity_mbps.get(u, 0.0), -u), reverse=True)

    accepted = 0
    for u in candidates:
        if accepted >= cfg.max_upgrades_per_tick:
            log.rejected_upgrades.append({"user": u, "reason": "max_upgrades_per_tick"})
            continue
        if time_since_switch_s.get(u, 1e9) < cfg.min_dwell_s:
            log.rejected_upgrades.append({"user": u, "reason": "min_dwell"})
            continue
        ac = float(access_capacity_mbps.get(u, 0.0))
        if cfg.access_tail_guard and ac < cfg.weak_access_capacity_mbps:
            log.rejected_upgrades.append({"user": u, "reason": "weak_access_tail_guard", "access_mbps": ac})
            continue
        if residual < cfg.enhancement_cost_mbps:
            log.rejected_upgrades.append({"user": u, "reason": "insufficient_residual", "residual": residual})
            continue
        upgrades[u] = True
        residual -= cfg.enhancement_cost_mbps
        accepted += 1
        log.accepted_upgrades.append(u)

    log.residual_mbps_after = residual
    log.contract_ok = True  # projector always yields a feasible action
    return groups, upgrades, log


def log_as_dict(log: ProjectorLog) -> dict[str, Any]:
    return asdict(log)
