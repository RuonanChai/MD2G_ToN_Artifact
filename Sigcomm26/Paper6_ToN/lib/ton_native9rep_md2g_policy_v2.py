#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""command111 — md2g_v2 native Rep1–9 policy (does NOT overwrite V1).

Mechanism (from COMMAND111_V1_FAILURE_ATLAS):
- V1 sticky Rep3 under-exploits residual capacity / group reuse.
- V2: sustainable Pareto anchor → residual upgrades by marginal
  quality/reuse/completion per marginal byte → switch hysteresis →
  last-playable fallback.

Internal score ≠ paper_U. Never tunes on holdout.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

TON = Path(__file__).resolve().parents[1]
STATE = TON / "state"

# Import shared helpers from V1 without altering V1 selection logic.
from ton_native9rep_md2g_policy import (  # noqa: E402
    REP_META_DEFAULT,
    _env_float,
    _env_on,
    base_enh_to_rep,
    load_content_bitrates,
    load_quality_map,
    rep_to_base_enh,
)


def load_pareto_graph() -> dict:
    p = STATE / "COMMAND111_REP_PARETO_GRAPH.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"reps": [], "dominated": [7, 9], "upgrade_edges": [], "pareto_efficient": list(range(1, 10))}


def _device_need(rid: int) -> float:
    return {1: 0.65, 2: 0.45, 3: 0.0, 4: 0.70, 5: 0.78, 6: 0.50, 7: 0.58, 8: 0.05, 9: 0.25}.get(rid, 0.5)


def feasible(rid: int, *, device: float, tp: float, rates: dict[int, float], margin: float) -> bool:
    br = rates.get(rid, 1.0)
    return device + 1e-9 >= _device_need(rid) and tp + 1e-9 >= br * margin


def choose_anchor(
    *,
    device: float,
    tp: float,
    rates: dict[int, float],
    qmap: dict[int, dict],
    graph: dict,
    last_playable: int | None,
) -> int:
    """Highest-quality feasible Pareto (or special) rep with BaseGuard margin."""
    dominated = set(graph.get("dominated") or [])
    margin = _env_float("TON_MD2G_V2_ANCHOR_MARGIN", 1.12)
    cands = []
    for rid in range(1, 10):
        if rid in dominated and rid != 3:
            continue
        if feasible(rid, device=device, tp=tp, rates=rates, margin=margin):
            cands.append(rid)
    if not cands:
        # last-playable fallback chain
        for rid in (last_playable, 3, 8, 2, 1):
            if rid and feasible(rid, device=device, tp=tp, rates=rates, margin=1.02):
                return int(rid)
        return 3
    # prefer quality, then lower bitrate (efficiency), prefer non-dominated
    return max(cands, key=lambda r: (qmap[r]["q"], -rates.get(r, 9.0)))


def upgrade_score(
    *,
    anchor: int,
    cand: int,
    qmap: dict[int, dict],
    rates: dict[int, float],
    device: float,
    tp: float,
    group_share: float,
    util: float,
    n_users: int,
) -> float | None:
    if cand == anchor:
        return 0.0
    if qmap[cand]["q"] + 1e-12 < qmap[anchor]["q"]:
        return None
    br_a = rates.get(anchor, 1.0)
    br_c = rates.get(cand, 1.0)
    margin = _env_float("TON_MD2G_V2_UPGRADE_MARGIN", 1.05)
    if not feasible(cand, device=device, tp=tp, rates=rates, margin=margin):
        return None
    dq = qmap[cand]["q"] - qmap[anchor]["q"]
    dbytes = max(0.0, br_c - br_a)
    if dbytes <= 1e-6:
        dbytes = 0.05 * max(br_c, 0.2)
    cross = qmap[cand]["base"] != qmap[anchor]["base"]
    switch = _env_float("TON_MD2G_V2_SWITCH_SAME", 0.12) if not cross else _env_float("TON_MD2G_V2_SWITCH_CROSS", 0.40)
    # group reuse: shared publisher amortizes bytes
    reuse = 1.0 + _env_float("TON_MD2G_V2_REUSE_GAIN", 0.55) * max(0.0, min(1.0, group_share))
    # completion: prefer upgrades that leave headroom
    head = max(0.0, tp - br_c * margin)
    completion = _env_float("TON_MD2G_V2_COMPLETION", 0.35) * min(1.0, head / max(br_c, 0.5))
    wq = _env_float("TON_MD2G_V2_WQ", 1.0)
    wo = _env_float("TON_MD2G_V2_WO", 0.45)
    wc = _env_float("TON_MD2G_V2_WC", 0.30)
    wb = _env_float("TON_MD2G_V2_WB", 1.0)
    ws = _env_float("TON_MD2G_V2_WS", 1.0)
    cong = _env_float("TON_MD2G_V2_CONGESTION", 0.85) * util * (br_c / 8.0)
    numer = wq * dq + wo * (reuse - 1.0) + wc * completion + 0.08 * device
    denom = 1e-3 + wb * dbytes + ws * switch + cong
    scale = 1.0
    if _env_on("MM26_MD2G_MU_SCALE_NORM") or True:
        scale = 1.0 / max(1.0, (n_users / 20.0) ** 0.5)
    return scale * numer / denom


def select_rep_v2(
    *,
    cur_rep: int,
    device_score: float,
    tp_mbps: float,
    pull_enhanced: bool,
    group_share: float = 0.3,
    util: float = 0.0,
    n_users: int = 20,
    content: str | None = None,
    last_playable: int | None = None,
) -> dict[str, Any]:
    qmap = load_quality_map()
    rates = load_content_bitrates(content)
    graph = load_pareto_graph()
    dominated = set(graph.get("dominated") or [])

    anchor = choose_anchor(
        device=device_score,
        tp=tp_mbps,
        rates=rates,
        qmap=qmap,
        graph=graph,
        last_playable=last_playable or cur_rep,
    )

    # If actor does not pull enhanced and env forbids, still allow same-family
    # depth upgrades when residual capacity is large (fixes V1 under-exploitation).
    allow_upgrade = True
    if not pull_enhanced and _env_on("TON_MD2G_V2_REQUIRE_PULL"):
        allow_upgrade = False

    chosen = anchor
    best_s = -1e18
    if allow_upgrade:
        for cand in range(1, 10):
            if cand in dominated and cand != anchor:
                # down-rank dominated unless huge residual and still best efficiency
                if tp_mbps < rates.get(cand, 9) * 1.25:
                    continue
            s = upgrade_score(
                anchor=anchor,
                cand=cand,
                qmap=qmap,
                rates=rates,
                device=device_score,
                tp=tp_mbps,
                group_share=group_share,
                util=util,
                n_users=n_users,
            )
            if s is None:
                continue
            # hysteresis vs current
            if cand != cur_rep:
                cross = qmap[cand]["base"] != qmap.get(cur_rep, {}).get("base", qmap[cand]["base"])
                need = _env_float("TON_MD2G_V2_HYST_SAME", 0.08) if not cross else _env_float("TON_MD2G_V2_HYST_CROSS", 0.22)
                dq = qmap[cand]["q"] - qmap.get(cur_rep, qmap[anchor])["q"]
                if dq < need and cand != anchor:
                    continue
            if s > best_s:
                best_s = s
                chosen = cand

    # last-playable fallback if chosen suddenly infeasible
    if not feasible(chosen, device=device_score, tp=tp_mbps, rates=rates, margin=1.02):
        chosen = anchor if feasible(anchor, device=device_score, tp=tp_mbps, rates=rates, margin=1.02) else 3

    b, e = rep_to_base_enh(chosen)
    return {
        "selected_rep": chosen,
        "base_version": b,
        "enhanced_level": e,
        "pull_enhanced": e > 0,
        "policy": "v2_anchor_marginal_upgrade",
        "anchor": anchor,
        "score": best_s if best_s > -1e17 else None,
        "last_playable": chosen,
    }


def apply_native9rep_policy_v2(decisions: dict, *, content: str | None = None, util: float = 0.0) -> dict:
    if not _env_on("TON_NATIVE9REP_MD2G"):
        return {"applied": False, "version": "V2"}
    n = max(1, len(decisions))
    # estimate group share: fraction choosing same base among decisions (pre-pass)
    base_counts: dict[int, int] = {}
    for d in decisions.values():
        if not isinstance(d, dict):
            continue
        try:
            b = int(d.get("base_version") or 3)
        except Exception:
            b = 3
        base_counts[b] = base_counts.get(b, 0) + 1

    changed = 0
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
        tp = float(d.get("throughput_mbps", d.get("bandwidth", 10.0)) or 10.0)
        pull = bool(d.get("pull_enhanced", True))  # V2 default allow residual upgrades
        try:
            bcur = int(d.get("base_version") or REP_META_DEFAULT[cur]["base"])
        except Exception:
            bcur = 3
        group_share = base_counts.get(bcur, 1) / float(n)
        last = d.get("ton_last_playable")
        out = select_rep_v2(
            cur_rep=cur,
            device_score=device,
            tp_mbps=tp,
            pull_enhanced=pull,
            group_share=group_share,
            util=util,
            n_users=n,
            content=content,
            last_playable=int(last) if last is not None else cur,
        )
        d["base_version"] = out["base_version"]
        d["enhanced_level"] = out["enhanced_level"]
        d["enh_level"] = out["enhanced_level"]
        d["pull_enhanced"] = out["pull_enhanced"]
        d["selected_rep"] = out["selected_rep"]
        d["rep_id"] = out["selected_rep"]
        d["ton_native9rep_policy"] = out.get("policy")
        d["ton_native9rep_anchor"] = out.get("anchor")
        d["ton_last_playable"] = out.get("last_playable")
        changed += 1
    return {"applied": True, "n_users": changed, "version": "V2"}
