#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""command117 md2g_g2_v2_repagg — group representation aggregation projection.

Student remains the proposal/ranking engine. This module is a network-aware
projection onto economically justified (group, rep) streams.

Does NOT change grouping membership (G2-v1 path).
Does NOT set a strategy-specific Ro mode.
Does NOT use TON_G2_GROUPING=REUSE_V2.
Does NOT impose an arbitrary always-one-rep or Rep3-only policy.
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

from ton_native9rep_md2g_policy import (
    _env_float,
    _env_on,
    base_enh_to_rep,
    load_content_bitrates,
    load_quality_map,
    rep_to_base_enh,
)
from ton_native9rep_md2g_policy_g2 import _neural_rep_scores
from ton_native9rep_md2g_policy_v2 import _device_need, feasible
from ton_native9rep_md2g_policy_v3 import _capacity_mbps, _delivered_mbps, choose_anchor_v3, load_pareto_graph
from ton_ro_native9 import paper_u_native9, ro_native9_interval

# gid -> last projected active set / per-user assignment (hysteresis across ticks)
_LAST: dict[Any, dict] = {}


def full_stream_open_cost(active_reps: set[int] | frozenset[int], new_rep: int, rates: dict[int, float]) -> float:
    """Keeping existing streams and adding r' costs the FULL bitrate of r'."""
    if int(new_rep) in {int(x) for x in active_reps}:
        return 0.0
    return float(rates.get(int(new_rep), 0.0))


def replace_stream_delta_cost(old_rep: int, new_rep: int, rates: dict[int, float]) -> float:
    """Replacing the sole common stream r with r' costs bitrate delta (can be negative)."""
    return float(rates.get(int(new_rep), 0.0)) - float(rates.get(int(old_rep), 0.0))


def _q(qmap: dict, rid: int) -> float:
    return float(qmap.get(int(rid), {}).get("q", 1.0))


def _commit(d: dict, rid: int, *, proposal: int, anchor: int, active: set[int], reason: str) -> None:
    b, e = rep_to_base_enh(int(rid))
    d["base_version"] = b
    d["enhanced_level"] = e
    d["enh_level"] = e
    d["pull_enhanced"] = e > 0
    d["selected_rep"] = int(rid)
    d["rep_id"] = int(rid)
    d["ton_last_playable"] = int(rid)
    d["ton_native9rep_policy"] = "g2_v2_repagg_projection"
    d["ton_native9rep_anchor"] = int(anchor)
    d["ton_g2_neural_proposal"] = int(proposal)
    d["ton_g2_projected_rep"] = int(rid)
    d["ton_g2_repagg_anchor"] = int(anchor)
    d["ton_g2_repagg_active_streams"] = sorted(int(x) for x in active)
    d["ton_g2_repagg_reason"] = reason
    d["ton_g2_repagg_opened_secondary"] = int(len(active) > 1)


def _proposal_for_user(
    *,
    uid: Any,
    m: dict,
    rates: dict,
    qmap: dict,
    neural: dict | None,
    cur: int,
) -> int:
    logits = (neural or {}).get(str(uid), {}).get("rep_logits") or [0.0] * 9
    best, best_s = None, -1e18
    for cand in range(1, 10):
        if not feasible(cand, device=m["device"], tp=m["cap"], rates=rates, margin=1.02):
            continue
        bonus = 0.15 * float(logits[cand - 1]) if neural else 0.0
        s = _q(qmap, cand) + bonus - 0.02 * rates.get(cand, 1.0)
        if cand == cur:
            s += 0.04  # mild stay-on-current among proposals only
        if s > best_s:
            best_s, best = s, cand
    if best is None:
        return 3 if feasible(3, device=m["device"], tp=m["cap"], rates=rates, margin=1.02) else cur
    return int(best)


def _weak_ok(assign: dict, members: list, meta: dict, qmap: dict, anchor: int, floor_device: float) -> bool:
    aq = _q(qmap, anchor)
    for u in members:
        if meta[u]["device"] + 1e-9 < floor_device:
            if _q(qmap, assign[u]) + 1e-12 < aq:
                return False
    return True


def _u_hat(assign: dict, members: list, meta: dict, rates: dict, qmap: dict, mean_buf: float) -> float:
    uids = list(members)
    reps = [int(assign[u]) for u in uids]
    gids = [int(meta[u]["gid"] if meta[u]["gid"] is not None else 0) for u in uids]
    ro = ro_native9_interval(selected_reps=reps, group_ids=gids, bitrates=rates)
    rq = sum(_q(qmap, r) / 4.0 for r in reps) / max(1, len(reps))
    n_streams = ro["n_shared_streams"]
    extra = max(0, n_streams - len({g for g in gids}))
    rb = 0.04 * extra + (0.25 if mean_buf < 2.0 else 0.0)
    return paper_u_native9(ro["Ro_native9"], rq, min(1.0, rb))


def _coalesce_to_active(members, meta, proposals, active: set[int], rates, qmap, q_tol: float, anchor: int) -> dict:
    assign = {}
    for u in members:
        prop = proposals[u]
        if prop in active and feasible(prop, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.02):
            assign[u] = prop
            continue
        best, best_loss = anchor, 1e18
        pq = _q(qmap, prop)
        for r in active:
            if not feasible(r, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.02):
                continue
            loss = max(0.0, pq - _q(qmap, r))
            # prefer higher quality among those within tolerance, else closest
            score = (0 if loss <= q_tol else 1, loss, -_q(qmap, r))
            if score < (0 if best_loss <= q_tol else 1, best_loss, -_q(qmap, best)):
                best, best_loss = r, loss
        if not feasible(best, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.02):
            best = 3 if feasible(3, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.02) else proposals[u]
        assign[u] = int(best)
    return assign


def project_group(
    members: list,
    meta: dict,
    proposals: dict,
    rates: dict,
    qmap: dict,
    graph: dict,
    *,
    mean_buf: float,
    mean_stall: float,
) -> tuple[dict, set[int], int, str]:
    weakest = min(members, key=lambda u: (meta[u]["device"], meta[u]["cap"]))
    mw = meta[weakest]
    anchor = choose_anchor_v3(
        device=mw["device"], capacity=mw["cap"], rates=rates, qmap=qmap, graph=graph,
        last_playable=int(mw["last"]) if mw["last"] is not None else mw["cur"],
        weak=True,
    )
    if not feasible(anchor, device=mw["device"], tp=mw["cap"], rates=rates, margin=1.02):
        anchor = 3
    q_tol = _env_float("TON_G2_REPAGG_Q_TOL", 0.35)
    floor_dev = _env_float("TON_G2_REPAGG_WEAK_DEVICE", 0.50)
    max_extra = int(_env_float("TON_G2_REPAGG_MAX_EXTRA", 1.0))
    buf_min = _env_float("TON_G2_REPAGG_BUF_OPEN_MIN", 2.0)
    hyst_u = _env_float("TON_G2_REPAGG_HYST_U", 0.008)
    allow_open = mean_buf >= buf_min and mean_stall < 0.80

    candidates: list[tuple[set[int], str, float]] = []
    # COMMON_ONLY
    candidates.append(({int(anchor)}, "COMMON_ONLY", 0.0))

    extras = sorted({int(proposals[u]) for u in members if int(proposals[u]) != int(anchor)})
    if allow_open and max_extra >= 1:
        for r in extras:
            # opening r while keeping anchor costs FULL bytes(r)
            cost = full_stream_open_cost({int(anchor)}, r, rates)
            if cost <= 1e-12:
                continue
            # require some users who can take r and would gain quality
            able = [
                u for u in members
                if feasible(r, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.02)
                and _q(qmap, r) + 1e-12 >= _q(qmap, anchor)
            ]
            if len(able) < 2:
                continue
            dq = sum(max(0.0, _q(qmap, r) - _q(qmap, anchor)) for u in able)
            if dq / max(cost, 0.05) < _env_float("TON_G2_REPAGG_OPEN_GAIN_PER_MBPS", 0.12):
                continue
            candidates.append(({int(anchor), int(r)}, f"COMMON_PLUS_{r}", 0.0))

    # replace whole group with a higher common stream if everyone can take it
    for r in extras:
        if r == anchor:
            continue
        if not all(feasible(r, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.05) for u in members):
            continue
        # replacement delta, not full extra
        if _q(qmap, r) + 1e-12 < _q(qmap, anchor):
            continue
        candidates.append(({int(r)}, f"REPLACE_COMMON_{r}", 0.02))

    last = _LAST.get(mw["gid"]) or {}
    last_active = set(int(x) for x in (last.get("active") or []))
    if last_active and last_active <= ({int(anchor)} | set(extras) | {int(anchor)}):
        if all(
            any(feasible(r, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.02) for r in last_active)
            for u in members
        ):
            candidates.append((last_active, "HYSTERESIS_KEEP", hyst_u))

    best_assign, best_active, best_u, best_why = None, {int(anchor)}, -1e18, "COMMON_ONLY"
    for active, why, bonus in candidates:
        if len(active) - 1 > max_extra:
            continue
        assign = _coalesce_to_active(members, meta, proposals, active, rates, qmap, q_tol, anchor)
        # users who can take a higher active stream should get it (not forced to low)
        for u in members:
            for r in active:
                if feasible(r, device=meta[u]["device"], tp=meta[u]["cap"], rates=rates, margin=1.02):
                    if _q(qmap, r) > _q(qmap, assign[u]) + 1e-12:
                        # only if r is the user's proposal or quality gain exceeds hysteresis
                        if r == proposals[u] or _q(qmap, r) - _q(qmap, assign[u]) >= _env_float("TON_G2_REPAGG_HYST_Q", 0.15):
                            assign[u] = int(r)
        if not _weak_ok(assign, members, meta, qmap, anchor, floor_dev):
            continue
        uhat = _u_hat(assign, members, meta, rates, qmap, mean_buf) + bonus
        if uhat > best_u:
            best_u, best_assign, best_active, best_why = uhat, assign, set(active), why
    if best_assign is None:
        best_assign = {u: int(anchor) for u in members}
        best_active = {int(anchor)}
        best_why = "WEAK_FLOOR_FALLBACK_ANCHOR"
    _LAST[mw["gid"]] = {"active": sorted(best_active), "assign": dict(best_assign)}
    return best_assign, best_active, int(anchor), best_why


def apply_native9rep_policy_g2_repagg(decisions: dict, *, content: str | None = None, util: float = 0.0) -> dict:
    if not _env_on("TON_NATIVE9REP_MD2G"):
        return {"applied": False, "version": "G2_V2_REPAGG"}
    n = max(1, len(decisions))
    rates = load_content_bitrates(content)
    qmap = load_quality_map()
    graph = load_pareto_graph()
    neural = _neural_rep_scores(decisions, content, rates, qmap)

    meta: dict[Any, dict] = {}
    by_g: dict[Any, list] = defaultdict(list)
    bufs, stalls = [], []
    for uid, d in decisions.items():
        if not isinstance(d, dict):
            continue
        cur = int(d.get("selected_rep") or d.get("rep_id") or 3)
        if d.get("base_version") is not None:
            try:
                cur = base_enh_to_rep(int(d.get("base_version") or 3), int(d.get("enhanced_level") or 0))
            except Exception:
                pass
        device = float(d.get("device_score", d.get("md2g_device_score", 0.5)) or 0.5)
        cap = _capacity_mbps(d)
        gid = d.get("md2g_group_id", d.get("grouping_id", 0))
        # NEVER rewrite grouping from the neural group head (command117)
        meta[uid] = {
            "cur": cur,
            "device": device,
            "cap": cap,
            "delivered": _delivered_mbps(d),
            "gid": gid,
            "last": d.get("ton_last_playable"),
        }
        by_g[gid].append(uid)
        try:
            bufs.append(float(d.get("buffer_level_sec", 5.0) or 5.0))
        except Exception:
            bufs.append(5.0)
        try:
            stalls.append(float(d.get("stall_sec", d.get("recent_stall_s", 0.0)) or 0.0))
        except Exception:
            stalls.append(0.0)

    mean_buf = sum(bufs) / max(1, len(bufs))
    mean_stall = sum(stalls) / max(1, len(stalls))
    proposals = {}
    for uid, m in meta.items():
        proposals[uid] = _proposal_for_user(
            uid=uid, m=m, rates=rates, qmap=qmap, neural=neural, cur=m["cur"],
        )

    changed = 0
    n_agree = 0
    group_info = {}
    for gid, members in by_g.items():
        assign, active, anchor, why = project_group(
            members, meta, proposals, rates, qmap, graph,
            mean_buf=mean_buf, mean_stall=mean_stall,
        )
        group_info[str(gid)] = {"anchor": anchor, "active": sorted(active), "reason": why, "n": len(members)}
        for uid in members:
            d = decisions[uid]
            prop = proposals[uid]
            rid = int(assign[uid])
            _commit(d, rid, proposal=prop, anchor=anchor, active=active, reason=why)
            d["ton_g2_capacity_mbps"] = meta[uid]["cap"]
            d["ton_g2_delivered_mbps"] = meta[uid]["delivered"]
            d["ton_g2_neural"] = bool(neural)
            if int(prop) == int(rid):
                n_agree += 1
            changed += 1

    return {
        "applied": True,
        "n_users": changed,
        "version": "G2_V2_REPAGG",
        "neural": bool(neural),
        "scale_users": n,
        "proposal_projection_agree": n_agree / max(1, changed),
        "groups": group_info,
        "safety_max_extra_streams_per_group": int(_env_float("TON_G2_REPAGG_MAX_EXTRA", 1.0)),
        "grouping_unchanged": True,
    }
