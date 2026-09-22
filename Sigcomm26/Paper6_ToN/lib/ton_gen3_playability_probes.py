#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""command120 G3 diagnostic probe policies (NOT the learned Gen3 controller).

Arms:
  P0 COMMON_ONLY
  P1 OPEN_IMMEDIATE
  P2 OPEN_AFTER_COMMON_PLAYABLE
  P3 BUFFER_GUARDED_OPEN

Fail-closed if required playability fields are missing. No mean_buf=5.0.
Uses deployable access_capacity_mbps from telemetry, never oracle-only.
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

from ton_actuation_plan import apply_actuation_plan, assert_plan_is_physical_authority, build_group_plan
from ton_playability_telemetry import missing_required
from ton_native9rep_md2g_policy import load_content_bitrates, load_quality_map
from ton_native9rep_md2g_policy_v2 import feasible
from ton_native9rep_md2g_policy_v3 import choose_anchor_v3, load_pareto_graph

# Predeclared BUFFER_GUARDED_OPEN feasibility (frozen before any probe results).
BUF_OPEN_MIN_SEC = 2.0
TTP_OPEN_MAX_SEC = 1.5
COMMON_PLAYABLE_MIN_SEC = 1.0
COMMON_COMPLETION_MIN = 0.85


def probe_arm() -> str:
    return (os.environ.get("TON_GEN3_PROBE_ARM") or "COMMON_ONLY").strip().upper()


def _gid(d: dict) -> Any:
    return d.get("md2g_group_id", d.get("group_id", d.get("grouping_id", 0)))


def _cap(d: dict) -> float:
    try:
        return float(d.get("access_capacity_mbps") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _apply_rep(d: dict, rid: int) -> None:
    """Deprecated direct writer. Probe policy must go through ActuationPlan."""
    raise RuntimeError(
        "ACTUATION_MULTIPLE_WRITERS: _apply_rep is not a physical authority; "
        "use ActuationPlan / stamp_rep_fields via apply_actuation_plan"
    )


def apply_gen3_probe_policy(decisions: dict, *, content: str | None = None, util: float = 0.0) -> dict:
    arm = probe_arm()
    qmap = load_quality_map()
    rates = load_content_bitrates(content)
    graph = load_pareto_graph()
    by_g: dict[Any, list] = defaultdict(list)
    missing = []
    for uid, d in decisions.items():
        if not isinstance(d, dict):
            continue
        miss = missing_required(d)
        if miss:
            missing.append({"uid": uid, "missing": miss})
        by_g[_gid(d)].append(uid)

    if missing:
        strict = os.environ.get("TON_GEN3_PROBE_STRICT", "").strip().lower() in ("1", "true", "yes")
        if strict:
            raise RuntimeError(
                "PLAYABILITY_FAIL_CLOSED probe missing="
                + str(missing[:3])
                + " (no default mean_buf=5.0)"
            )
        # Live startup: refuse secondary opens this tick; do not invent buffer=5.0.
        arm = "COMMON_ONLY"
        startup_hold = True
    else:
        startup_hold = False

    reasons = {}
    active_streams = {}
    plans = []
    for gid, members in by_g.items():
        meta = {}
        for uid in members:
            d = decisions[uid]
            cap = _cap(d)
            device = float(d.get("device_score") or 0.5)
            cur = int(d.get("selected_rep") or d.get("rep_id") or 3)
            meta[uid] = {"cap": cap, "device": device, "cur": cur, "d": d}
        # Common sustainable stream: same HV3-like anchor chooser (diagnostic, not learned)
        # Common sustainable stream: weakest-user feasible anchor (diagnostic, not learned)
        weak_uid = min(members, key=lambda u: (float(meta[u]["d"].get("buffer_level_sec") or 0.0), meta[u]["cap"]))
        try:
            anchor = choose_anchor_v3(
                device=meta[weak_uid]["device"],
                capacity=meta[weak_uid]["cap"],
                rates=rates,
                qmap=qmap,
                graph=graph,
                last_playable=meta[weak_uid]["cur"],
                weak=True,
            )
        except Exception:
            anchor = 3
            for rid in (3, 2, 8, 9, 1, 6, 4, 7, 5):
                if feasible(rid, device=meta[weak_uid]["device"], tp=meta[weak_uid]["cap"], rates=rates, margin=1.08):
                    anchor = rid
                    break
        bufs = [float(meta[u]["d"].get("buffer_level_sec") or 0.0) for u in members]
        ttps = [float(meta[u]["d"].get("time_to_playable_s") or 0.0) for u in members]
        comps = [float(meta[u]["d"].get("rep_completion_frac") or 0.0) for u in members]
        mean_buf = sum(bufs) / max(1, len(bufs))
        mean_ttp = sum(ttps) / max(1, len(ttps))
        mean_comp = sum(comps) / max(1, len(comps))
        weak_buf = min(bufs) if bufs else 0.0

        secondary = None
        why = "COMMON_ONLY"
        if arm == "COMMON_ONLY":
            secondary = None
            why = "P0_COMMON_ONLY"
        elif arm == "OPEN_IMMEDIATE":
            # open one higher-quality full stream as soon as any member can nominally afford it
            for rid in (5, 4, 7, 6, 1, 9, 8, 2):
                if rid == anchor:
                    continue
                if any(feasible(rid, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.05) for u in members):
                    secondary = rid
                    why = "P1_OPEN_IMMEDIATE"
                    break
        elif arm == "OPEN_AFTER_COMMON_PLAYABLE":
            common_ready = mean_buf >= COMMON_PLAYABLE_MIN_SEC or mean_comp >= COMMON_COMPLETION_MIN
            if common_ready:
                for rid in (5, 4, 7, 6, 1, 9, 8, 2):
                    if rid == anchor:
                        continue
                    if any(feasible(rid, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.05) for u in members):
                        secondary = rid
                        why = "P2_OPEN_AFTER_COMMON_PLAYABLE"
                        break
            else:
                why = "P2_HOLD_UNTIL_COMMON_PLAYABLE"
        elif arm == "BUFFER_GUARDED_OPEN":
            ok = weak_buf >= BUF_OPEN_MIN_SEC and mean_ttp <= TTP_OPEN_MAX_SEC
            if ok:
                for rid in (5, 4, 7, 6, 1, 9, 8, 2):
                    if rid == anchor:
                        continue
                    if any(feasible(rid, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.05) for u in members):
                        secondary = rid
                        why = "P3_BUFFER_GUARDED_OPEN"
                        break
            else:
                why = "P3_HOLD_BUFFER_OR_TTP"
        else:
            why = f"UNKNOWN_ARM_{arm}"

        streams = {anchor}
        if secondary is not None:
            streams.add(int(secondary))
        active_streams[str(gid)] = sorted(streams)
        reasons[str(gid)] = why
        user_targets = {}
        proposals = {}
        for uid in members:
            d = decisions[uid]
            proposals[str(uid)] = {
                "selected_rep": d.get("selected_rep"),
                "rep_id": d.get("rep_id"),
                "pull_enhanced": d.get("pull_enhanced"),
                "base_version": d.get("base_version"),
                "enhanced_level": d.get("enhanced_level"),
            }
            # Map user onto the active shared-stream set (not independent per-user IDs).
            target = anchor
            if secondary is not None:
                # stronger users take secondary if feasible; weak stay on common
                if feasible(secondary, device=meta[uid]["device"], tp=meta[uid]["cap"], rates=rates, margin=1.05) and float(d.get("device_score") or 0) >= 0.45:
                    target = secondary
            user_targets[str(uid)] = int(target)
        if secondary is not None and not any(int(t) == int(secondary) for t in user_targets.values()):
            # Plan contains a secondary stream: at least one user must subscribe or OPEN has no payload.
            ranked = sorted(
                members,
                key=lambda u: (meta[u]["device"], meta[u]["cap"]),
                reverse=True,
            )
            pick = None
            for u in ranked:
                if feasible(int(secondary), device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.05):
                    pick = u
                    break
            if pick is None:
                pick = ranked[0]
            user_targets[str(pick)] = int(secondary)
        buf_snap = {
            "mean_buf": mean_buf, "mean_ttp": mean_ttp, "mean_comp": mean_comp, "weak_buf": weak_buf,
        }
        feas_snap = {
            "anchor": int(anchor),
            "secondary": None if secondary is None else int(secondary),
            "candidate_order": [5, 4, 7, 6, 1, 9, 8, 2],
            "margin_secondary": 1.05,
        }
        plan = build_group_plan(
            arm=arm,
            group_id=gid,
            common_rep=int(anchor),
            secondary=None if secondary is None else int(secondary),
            reason=why,
            user_targets=user_targets,
            protected_users=[u for u in members if user_targets.get(str(u)) == int(anchor)],
            source_policy_proposal=proposals,
            feasibility_snapshot=feas_snap,
            buffer_playability_snapshot=buf_snap,
            startup_hold=startup_hold,
        )
        plans.append(plan)

    apply_audit = apply_actuation_plan(decisions, plans)
    for d in decisions.values():
        if isinstance(d, dict) and d.get("actuation_writer"):
            assert_plan_is_physical_authority(d)

    return {
        "applied": True,
        "arm": arm,
        "n_users": len(decisions),
        "n_groups": len(by_g),
        "reasons": reasons,
        "active_streams": active_streams,
        "startup_hold": startup_hold,
        "n_missing_playability": len(missing),
        "version": "gen3_probe_v1_actuation_plan",
        "learned": False,
        "actuation_plans": [p.to_dict() for p in plans],
        "actuation_apply": apply_audit,
        "actuation_writer": "ton_actuation_plan.apply_actuation_plan",
    }
