#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""command112 — md2g_v3 two-timescale native Rep1–9 controller.

Does NOT overwrite V1/V2.

Layer A (grouping): left to MM26 FoV/MU on access_capacity plane; this module
does not fragment groups based on high-rep infeasibility.

Layer B (representation):
- capacity signal = access_capacity (NOT delivered goodput) for residual budget
- delivered used only as health/completion cue
- sustainable anchor + residual upgrades with shared-link marginal bytes
- weak-user deficit-aware residual ranking
- switch-aware hysteresis; last-playable fallback
"""
from __future__ import annotations

import os
from typing import Any

from ton_native9rep_md2g_policy import (
    _env_float,
    _env_on,
    base_enh_to_rep,
    load_content_bitrates,
    load_quality_map,
    rep_to_base_enh,
)
from ton_native9rep_md2g_policy_v2 import (
    _device_need,
    feasible,
    load_pareto_graph,
)


def _capacity_mbps(d: dict) -> float:
    """Prefer access capacity; never trust delivered-only for residual (cmd112 root cause)."""
    for k in ("access_capacity_mbps", "access_bw_mbps", "configured_bw_mbps"):
        try:
            v = float(d.get(k) or 0.0)
            if v > 1e-6:
                return v
        except Exception:
            pass
    # throughput_mbps may already be remapped to capacity when MM26_MD2G_TP_SIGNAL=access_capacity
    try:
        tp = float(d.get("throughput_mbps", d.get("bandwidth", 0.0)) or 0.0)
    except Exception:
        tp = 0.0
    delivered = 0.0
    try:
        delivered = float(d.get("delivered_mbps", d.get("goodput_mbps", 0.0)) or 0.0)
    except Exception:
        pass
    # If tp looks like post-rep goodput (< 2.5) while no explicit capacity, inflate via env floor
    floor = _env_float("TON_MD2G_V3_CAPACITY_FLOOR_MBPS", 8.0)
    if tp < 2.5 and delivered <= tp + 1e-6:
        return max(tp, floor)
    return max(tp, floor if tp < 1e-6 else tp)


def _delivered_mbps(d: dict) -> float:
    for k in ("delivered_mbps", "goodput_mbps"):
        try:
            v = float(d.get(k) or 0.0)
            if v > 0:
                return v
        except Exception:
            pass
    try:
        return float(d.get("throughput_mbps", 0.0) or 0.0)
    except Exception:
        return 0.0


def choose_anchor_v3(
    *,
    device: float,
    capacity: float,
    rates: dict[int, float],
    qmap: dict[int, dict],
    graph: dict,
    last_playable: int | None,
    weak: bool,
) -> int:
    dominated = set(graph.get("dominated") or [])
    # BaseGuard reserve applies to anchor continuity only (not double-charged later)
    margin = _env_float("TON_MD2G_V3_ANCHOR_MARGIN", 1.08)
    if weak:
        margin = max(margin, _env_float("TON_MD2G_V3_WEAK_ANCHOR_MARGIN", 1.15))
    cands = []
    for rid in range(1, 10):
        if rid in dominated and rid not in (3, 8):
            continue
        if feasible(rid, device=device, tp=capacity, rates=rates, margin=margin):
            cands.append(rid)
    if not cands:
        for rid in (last_playable, 3, 8, 2):
            if rid and feasible(rid, device=device, tp=capacity, rates=rates, margin=1.02):
                return int(rid)
        return 3
    # efficiency: quality then lower bitrate
    return max(cands, key=lambda r: (qmap[r]["q"], -rates.get(r, 9.0)))


def marginal_shared_bytes(anchor: int, cand: int, rates: dict[int, float], group_k: int) -> float:
    """Actual shared-link marginal cost: multicast upgrade counted once, not ×k users."""
    dbr = max(0.0, rates.get(cand, 0.0) - rates.get(anchor, 0.0))
    k = max(1, group_k)
    # per-user branch share of shared cost
    return dbr / float(k)


def score_upgrade_v3(
    *,
    anchor: int,
    cand: int,
    cur: int,
    qmap: dict,
    rates: dict,
    device: float,
    capacity: float,
    delivered: float,
    group_k: int,
    util: float,
    deficit: float,
) -> tuple[float | None, str]:
    if cand == anchor:
        return 0.0, "KEEP_ANCHOR"
    if qmap[cand]["q"] + 1e-12 < qmap[anchor]["q"]:
        return None, "QUALITY_GAIN_TOO_SMALL"
    margin = _env_float("TON_MD2G_V3_UPGRADE_MARGIN", 1.05)
    if device + 1e-9 < _device_need(cand):
        return None, "BASEGUARD_RESERVE"
    br_c = rates.get(cand, 1.0)
    # residual after anchor bytes (not total-rep double charge)
    residual = capacity - rates.get(anchor, 0.0) * _env_float("TON_MD2G_V3_ANCHOR_RESERVE", 1.05)
    mbytes = marginal_shared_bytes(anchor, cand, rates, group_k)
    if residual + 1e-9 < mbytes * margin:
        return None, "NO_RESIDUAL_BUDGET"
    if capacity + 1e-9 < br_c * margin:
        return None, "NO_RESIDUAL_BUDGET"
    dq = qmap[cand]["q"] - qmap[anchor]["q"]
    cross = qmap[cand]["base"] != qmap[cur]["base"]
    hyst = _env_float("TON_MD2G_V3_HYST_SAME", 0.06) if not cross else _env_float("TON_MD2G_V3_HYST_CROSS", 0.20)
    if cand != cur and dq < hyst and cand != anchor:
        return None, "HYSTERESIS_TOO_HIGH"
    switch = _env_float("TON_MD2G_V3_SWITCH_SAME", 0.10) if not cross else _env_float("TON_MD2G_V3_SWITCH_CROSS", 0.35)
    # completion: prefer when delivered already near anchor (stable) and residual clear
    completion = _env_float("TON_MD2G_V3_COMPLETION", 0.40) * min(1.0, max(0.0, residual) / max(br_c, 0.5))
    cong = _env_float("TON_MD2G_V3_CONGESTION", 0.55) * util * (mbytes / 4.0)
    # deficit-aware: boost weak users
    fair = _env_float("TON_MD2G_V3_DEFICIT_GAIN", 0.55) * max(0.0, deficit)
    numer = _env_float("TON_MD2G_V3_WQ", 1.0) * dq + completion + fair + 0.05 * device
    denom = 1e-3 + _env_float("TON_MD2G_V3_WB", 1.0) * mbytes + switch + cong
    return numer / denom, "OK"


def select_rep_v3(
    *,
    cur_rep: int,
    device_score: float,
    capacity_mbps: float,
    delivered_mbps: float,
    group_k: int = 1,
    util: float = 0.0,
    deficit: float = 0.0,
    content: str | None = None,
    last_playable: int | None = None,
) -> dict[str, Any]:
    qmap = load_quality_map()
    rates = load_content_bitrates(content)
    graph = load_pareto_graph()
    weak = deficit > 0.15 or device_score < 0.5
    anchor = choose_anchor_v3(
        device=device_score,
        capacity=capacity_mbps,
        rates=rates,
        qmap=qmap,
        graph=graph,
        last_playable=last_playable or cur_rep,
        weak=weak,
    )
    best = anchor
    best_s = -1e18
    reject_log = []
    for cand in range(1, 10):
        s, reason = score_upgrade_v3(
            anchor=anchor,
            cand=cand,
            cur=cur_rep,
            qmap=qmap,
            rates=rates,
            device=device_score,
            capacity=capacity_mbps,
            delivered=delivered_mbps,
            group_k=group_k,
            util=util,
            deficit=deficit,
        )
        if s is None:
            reject_log.append({"cand": cand, "reason": reason})
            continue
        if s > best_s:
            best_s = s
            best = cand
    if not feasible(best, device=device_score, tp=capacity_mbps, rates=rates, margin=1.02):
        best = anchor if feasible(anchor, device=device_score, tp=capacity_mbps, rates=rates, margin=1.02) else 3
    b, e = rep_to_base_enh(best)
    return {
        "selected_rep": best,
        "base_version": b,
        "enhanced_level": e,
        "pull_enhanced": e > 0,
        "policy": "v3_decoupled_capacity_residual",
        "anchor": anchor,
        "capacity_mbps": capacity_mbps,
        "delivered_mbps": delivered_mbps,
        "score": best_s if best_s > -1e17 else None,
        "last_playable": best,
        "reject_sample": reject_log[:5],
    }


def apply_native9rep_policy_v3(decisions: dict, *, content: str | None = None, util: float = 0.0) -> dict:
    if not _env_on("TON_NATIVE9REP_MD2G"):
        return {"applied": False, "version": "V3"}
    n = max(1, len(decisions))
    gcounts: dict[Any, int] = {}
    for d in decisions.values():
        if not isinstance(d, dict):
            continue
        gid = d.get("md2g_group_id", d.get("grouping_id", d.get("base_version", 0)))
        gcounts[gid] = gcounts.get(gid, 0) + 1

    # deficit from current quality proxy
    qmap = load_quality_map()
    quals = []
    for d in decisions.values():
        if not isinstance(d, dict):
            continue
        try:
            cur = int(d.get("selected_rep") or d.get("rep_id") or 3)
            if d.get("base_version") is not None:
                cur = base_enh_to_rep(int(d.get("base_version") or 3), int(d.get("enhanced_level") or 0))
            quals.append(qmap.get(cur, {}).get("q", 1.0))
        except Exception:
            quals.append(1.0)
    qmean = sum(quals) / max(1, len(quals))

    # Pass 1: anchors for all (continuity / weak protection)
    anchors = {}
    meta = {}
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
        delivered = _delivered_mbps(d)
        gid = d.get("md2g_group_id", d.get("grouping_id", d.get("base_version", 0)))
        deficit = max(0.0, qmean - qmap.get(cur, {}).get("q", qmean))
        # weak users get deficit boost
        if device < 0.5:
            deficit += 0.2
        meta[uid] = {
            "cur": cur,
            "device": device,
            "cap": cap,
            "delivered": delivered,
            "gid": gid,
            "group_k": gcounts.get(gid, 1),
            "deficit": deficit,
            "last": d.get("ton_last_playable"),
        }

    # Rank upgrades: weak/deficit first consumes residual (fairness guard)
    order = sorted(meta.keys(), key=lambda u: (-meta[u]["deficit"], meta[u]["device"]))
    # shared residual pool per group (Mbps)
    group_residual: dict[Any, float] = {}
    for uid, m in meta.items():
        rates = load_content_bitrates(content)
        qmap = load_quality_map()
        graph = load_pareto_graph()
        weak = m["deficit"] > 0.15 or m["device"] < 0.5
        anc = choose_anchor_v3(
            device=m["device"], capacity=m["cap"], rates=rates, qmap=qmap, graph=graph,
            last_playable=int(m["last"]) if m["last"] is not None else m["cur"], weak=weak,
        )
        anchors[uid] = anc
        # initialize residual pool once per group
        if m["gid"] not in group_residual:
            group_residual[m["gid"]] = max(0.0, m["cap"] - rates.get(anc, 0.0) * 1.05)

    changed = 0
    for uid in order:
        d = decisions[uid]
        m = meta[uid]
        rates = load_content_bitrates(content)
        # temporarily bind group residual into capacity for scoring
        eff_cap = max(m["cap"], group_residual.get(m["gid"], 0.0) + rates.get(anchors[uid], 0.0))
        out = select_rep_v3(
            cur_rep=m["cur"],
            device_score=m["device"],
            capacity_mbps=eff_cap,
            delivered_mbps=m["delivered"],
            group_k=m["group_k"],
            util=util,
            deficit=m["deficit"],
            content=content,
            last_playable=int(m["last"]) if m["last"] is not None else m["cur"],
        )
        # charge group residual for upgrades above anchor
        anc = out["anchor"]
        sel = out["selected_rep"]
        extra = marginal_shared_bytes(anc, sel, rates, m["group_k"])
        group_residual[m["gid"]] = max(0.0, group_residual.get(m["gid"], 0.0) - extra)

        d["base_version"] = out["base_version"]
        d["enhanced_level"] = out["enhanced_level"]
        d["enh_level"] = out["enhanced_level"]
        d["pull_enhanced"] = out["pull_enhanced"]
        d["selected_rep"] = out["selected_rep"]
        d["rep_id"] = out["selected_rep"]
        d["ton_native9rep_policy"] = out.get("policy")
        d["ton_native9rep_anchor"] = out.get("anchor")
        d["ton_last_playable"] = out.get("last_playable")
        d["ton_v3_capacity_mbps"] = out.get("capacity_mbps")
        changed += 1
    return {"applied": True, "n_users": changed, "version": "V3", "scale_users": n}
