#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""command108 — native Rep1–9 MD2G policy generalization (DEV / frozen candidates).

MM26 lessons transferred with 9-rep semantics:
- base-first continuity (BaseGuard generalization)
- marginal quality gain / marginal measured bytes
- switch-aware hysteresis
- MU / congestion / scale-norm as soft priors on candidate scores

Does NOT change paper_U weights. Does NOT use longdress/soldier/loot for tuning.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

TON = Path(__file__).resolve().parents[1]
STATE = TON / "state"
REPO = TON.parents[1]

# Lifecycle inverse: legal (base_family, depth) → rep_id (rep_lifecycle_v2)
REP_META_DEFAULT = {
    1: {"base": 1, "depth": 0, "q": 3.0, "rank": 6},
    2: {"base": 2, "depth": 0, "q": 2.0, "rank": 3},
    3: {"base": 3, "depth": 0, "q": 1.0, "rank": 1},
    4: {"base": 1, "depth": 1, "q": 3.5, "rank": 8},
    5: {"base": 1, "depth": 2, "q": 4.0, "rank": 9},
    6: {"base": 2, "depth": 1, "q": 2.5, "rank": 5},
    7: {"base": 2, "depth": 2, "q": 3.2, "rank": 7},
    8: {"base": 3, "depth": 1, "q": 1.5, "rank": 2},
    9: {"base": 3, "depth": 2, "q": 2.2, "rank": 4},
}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)) or default)
    except ValueError:
        return default


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def load_quality_map() -> dict[int, dict]:
    p = STATE / "COMMAND103_REP_QUALITY_MAP.json"
    out = {k: dict(v) for k, v in REP_META_DEFAULT.items()}
    if not p.exists():
        return out
    try:
        rows = json.loads(p.read_text()).get("reps") or []
        for r in rows:
            rid = int(r["rep_id"])
            out[rid] = {
                "base": {"Base1": 1, "Base2": 2, "Base3": 3}.get(r.get("base_family"), out[rid]["base"]),
                "depth": int(r.get("refinement_depth", out[rid]["depth"])),
                "q": float(r.get("paper_quality_score", out[rid]["q"])),
                "rank": int(r.get("semantic_quality_rank", out[rid]["rank"])),
                "br": float(r.get("measured_bitrate_mbps") or 0.0),
            }
    except Exception:
        pass
    return out


def load_content_bitrates(content: str | None) -> dict[int, float]:
    p = STATE / "COMMAND106_CONTENT_REP_BITRATES.json"
    rates = {rid: float(REP_META_DEFAULT[rid].get("br", 1.0) if "br" in REP_META_DEFAULT[rid] else
                        {1: 3.07, 2: 1.79, 3: 0.87, 4: 4.54, 5: 6.42, 6: 2.8, 7: 3.91, 8: 1.43, 9: 1.97}[rid])
             for rid in range(1, 10)}
    # defaults from quality map RB-ish
    rates = {
        1: 3.07, 2: 1.79, 3: 0.87, 4: 4.54, 5: 6.42, 6: 2.80, 7: 3.91, 8: 1.43, 9: 1.97
    }
    if p.exists():
        try:
            blob = json.loads(p.read_text())
            key = content or os.environ.get("TON_CONTENT_ID") or "redandblack"
            for rid_s, mbps in (blob.get(key) or {}).items():
                rates[int(rid_s)] = float(mbps)
        except Exception:
            pass
    # env override
    for rid in range(1, 10):
        env = os.environ.get(f"REP{rid}_BITRATE_MBPS")
        if env:
            try:
                rates[rid] = float(env)
            except ValueError:
                pass
    return rates


def rep_to_base_enh(rep_id: int) -> tuple[int, int]:
    m = REP_META_DEFAULT[int(rep_id)]
    return int(m["base"]), int(m["depth"])


def base_enh_to_rep(base: int, depth: int) -> int:
    for rid, m in REP_META_DEFAULT.items():
        if m["base"] == base and m["depth"] == depth:
            return rid
    return 3


def sustainable_base_rep(device_score: float, tp_mbps: float, rates: dict[int, float]) -> int:
    """Base-first continuity: pick highest-quality base-only rep that fits link/device."""
    # Prefer Base3 always feasible; upgrade base family only if headroom + device allow.
    order = [3, 2, 1]  # try higher quality bases if affordable
    # quality order among bases: Base1(q3)>Base2(q2)>Base3(q1) but Base1 needs more bytes/device
    candidates = []
    for rid in (1, 2, 3):
        br = rates.get(rid, 0.87)
        need_dev = {1: 0.7, 2: 0.5, 3: 0.0}[rid]
        if device_score + 1e-9 >= need_dev and tp_mbps + 1e-9 >= br * 1.05:
            candidates.append(rid)
    if not candidates:
        return 3
    # choose max paper quality among feasible bases
    qmap = load_quality_map()
    return max(candidates, key=lambda r: qmap[r]["q"])


def score_candidate(
    *,
    cur_rep: int,
    cand: int,
    qmap: dict[int, dict],
    rates: dict[int, float],
    device_score: float,
    tp_mbps: float,
    group_pressure: float,
    util: float,
) -> float | None:
    """Marginal quality per marginal byte, minus switch/congestion penalties."""
    br_c = rates.get(cand, 1.0)
    br_cur = rates.get(cur_rep, 1.0)
    need_dev = {1: 0.7, 2: 0.5, 3: 0.0, 4: 0.7, 5: 0.75, 6: 0.5, 7: 0.55, 8: 0.0, 9: 0.2}.get(cand, 0.5)
    if device_score + 1e-9 < need_dev:
        return None
    if tp_mbps + 1e-9 < br_c * (1.05 + 0.15 * group_pressure):
        return None
    dq = float(qmap[cand]["q"]) - float(qmap[cur_rep]["q"])
    dbytes = max(1e-3, br_c - br_cur)  # Mbps proxy for marginal bytes/s
    # if downgrade in bitrate but quality up (non-monotonic ladder), still allow
    if br_c <= br_cur:
        dbytes = max(1e-3, 0.15 * br_c)
    mu_byte = dq / dbytes
    switch_pen = 0.0
    if cand != cur_rep:
        switch_pen = _env_float("TON_MD2G_SWITCH_COST", 0.35)
        # require meaningful quality gain for switches
        if dq <= _env_float("TON_MD2G_HYSTERESIS_DQ", 0.25):
            return None
    cong = _env_float("MM26_MD2G_CONGESTION_PRICE", 1.0) * util * (br_c / 8.0)
    scale = 1.0
    if _env_on("MM26_MD2G_MU_SCALE_NORM"):
        scale = 1.0 / max(1.0, group_pressure * 10.0)
    completion = 0.0
    if _env_float("MM26_MD2G_COMPLETION_WEIGHT", 1.0) > 0:
        # near-fit completion: prefer reps close to available headroom
        head = max(0.0, tp_mbps - br_c)
        completion = _env_float("MM26_MD2G_COMPLETION_WEIGHT", 1.0) * min(1.0, head / max(br_c, 0.5))
    return scale * (mu_byte + 0.15 * device_score + completion) - switch_pen - cong


def select_rep_for_user(
    *,
    cur_rep: int,
    device_score: float,
    tp_mbps: float,
    pull_enhanced: bool,
    group_pressure: float = 0.3,
    util: float = 0.0,
    content: str | None = None,
) -> dict[str, Any]:
    qmap = load_quality_map()
    rates = load_content_bitrates(content)
    base_rep = sustainable_base_rep(device_score, tp_mbps, rates)
    # Base-first: everyone gets at least base_rep
    floor = base_rep
    if not pull_enhanced and not _env_on("TON_MD2G_ALLOW_BASE_ONLY_UPGRADE"):
        # still allow moving to a better sustainable base if current is worse
        cur_q = qmap.get(cur_rep, {}).get("q", 0.0)
        if qmap[floor]["q"] >= cur_q or cur_rep not in qmap:
            chosen = floor
        else:
            chosen = cur_rep if cur_rep in rates else floor
        b, e = rep_to_base_enh(chosen)
        return {
            "selected_rep": chosen,
            "base_version": b,
            "enhanced_level": e,
            "pull_enhanced": e > 0,
            "policy": "base_first_floor",
            "base_floor": floor,
        }

    best = floor
    best_s = -1e18
    # candidates: all legal reps; prefer same or higher quality than floor
    for cand in range(1, 10):
        if qmap[cand]["q"] + 1e-9 < qmap[floor]["q"] and cand != floor:
            # never go below base floor quality unless already there
            continue
        s = score_candidate(
            cur_rep=cur_rep if cur_rep in rates else floor,
            cand=cand,
            qmap=qmap,
            rates=rates,
            device_score=device_score,
            tp_mbps=tp_mbps,
            group_pressure=group_pressure,
            util=util,
        )
        if s is None:
            continue
        if s > best_s:
            best_s = s
            best = cand
    b, e = rep_to_base_enh(best)
    return {
        "selected_rep": best,
        "base_version": b,
        "enhanced_level": e,
        "pull_enhanced": e > 0,
        "policy": "marginal_q_per_byte_v1",
        "score": best_s,
        "base_floor": floor,
    }


def apply_native9rep_policy(decisions: dict, *, content: str | None = None, util: float = 0.0) -> dict:
    """Mutate controller decisions in-place toward native 9-rep semantics."""
    if not _env_on("TON_NATIVE9REP_MD2G"):
        return {"applied": False}
    # command111: dispatch to V2/V3 modules without overwriting V1 selection logic
    cand = os.environ.get("TON_MD2G_CANDIDATE", "V1").strip().upper()
    if cand in ("V2", "MD2G_V2"):
        from ton_native9rep_md2g_policy_v2 import apply_native9rep_policy_v2

        return apply_native9rep_policy_v2(decisions, content=content, util=util)
    if cand in ("V3", "MD2G_V3"):
        try:
            from ton_native9rep_md2g_policy_v3 import apply_native9rep_policy_v3

            return apply_native9rep_policy_v3(decisions, content=content, util=util)
        except ImportError:
            from ton_native9rep_md2g_policy_v2 import apply_native9rep_policy_v2

            return apply_native9rep_policy_v2(decisions, content=content, util=util)
    if cand in ("G2_V2_REPAGG", "G2V2_REPAGG"):
        from ton_native9rep_md2g_policy_g2_repagg import apply_native9rep_policy_g2_repagg

        return apply_native9rep_policy_g2_repagg(decisions, content=content, util=util)
    if cand.startswith("G2"):
        from ton_native9rep_md2g_policy_g2 import apply_native9rep_policy_g2

        return apply_native9rep_policy_g2(decisions, content=content, util=util)
    n = max(1, len(decisions))
    group_pressure = min(1.0, n / 100.0)
    changed = 0
    for uid, d in decisions.items():
        if not isinstance(d, dict):
            continue
        cur = int(d.get("selected_rep") or d.get("rep_id") or 3)
        # infer current from base/enh if present
        if d.get("base_version") is not None:
            try:
                cur = base_enh_to_rep(int(d.get("base_version") or 3), int(d.get("enhanced_level") or 0))
            except Exception:
                pass
        device = float(d.get("device_score", d.get("md2g_device_score", 0.5)) or 0.5)
        tp = float(d.get("throughput_mbps", d.get("bandwidth", 10.0)) or 10.0)
        pull = bool(d.get("pull_enhanced"))
        out = select_rep_for_user(
            cur_rep=cur,
            device_score=device,
            tp_mbps=tp,
            pull_enhanced=pull,
            group_pressure=group_pressure,
            util=util,
            content=content,
        )
        d["base_version"] = out["base_version"]
        d["enhanced_level"] = out["enhanced_level"]
        d["enh_level"] = out["enhanced_level"]
        d["pull_enhanced"] = out["pull_enhanced"]
        d["selected_rep"] = out["selected_rep"]
        d["rep_id"] = out["selected_rep"]
        d["ton_native9rep_policy"] = out.get("policy")
        d["ton_native9rep_base_floor"] = out.get("base_floor")
        changed += 1
    return {"applied": True, "n_users": changed, "version": os.environ.get("TON_MD2G_CANDIDATE", "V1")}
