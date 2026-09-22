#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""command114 Generation-2 native Rep1–9 two-timescale MD2G policy.

Does NOT overwrite V1/V2/V3. Does NOT wrap the MM26 binary student as the
final action policy. Neural 9-rep scores (if loaded) only rerank legal
candidates after fail-closed feasibility / BaseGuard / residual projection.
"""
from __future__ import annotations

import os
from collections import Counter
from typing import Any

from ton_native9rep_md2g_policy import (
    _env_float,
    _env_on,
    base_enh_to_rep,
    load_content_bitrates,
    load_quality_map,
    rep_to_base_enh,
)
from ton_native9rep_md2g_policy_v2 import _device_need, feasible
from ton_native9rep_md2g_policy_v3 import (
    _capacity_mbps,
    _delivered_mbps,
    choose_anchor_v3,
    load_pareto_graph,
    marginal_shared_bytes,
)

_MODEL = None
_MODEL_ERR = None
_STUDENT_DIAG = None
_STUDENT_DIAG_ERR = None


def _g2_version() -> str:
    return os.environ.get("TON_MD2G_CANDIDATE", "G2").strip().upper() or "G2"


def _is_teacher_diag() -> bool:
    v = _g2_version()
    return v in ("G2_TEACHER_DIAG", "G2TEACHERDIAG", "MD2G_G2_TEACHER_DIAG") or _env_on("TON_G2_TEACHER_DIAG")


def _is_opt4() -> bool:
    v = _g2_version()
    return v in ("G2_OPT4_NATIVE9_STRUCTURAL", "G2OPT4NATIVE9STRUCTURAL", "MD2G_G2_OPT4_NATIVE9_STRUCTURAL") or _env_on(
        "TON_G2_OPT4_STRUCTURAL"
    )


def _is_opt5() -> bool:
    v = _g2_version()
    return v in (
        "G2_OPT5_FEASIBLE_COMMON_ANCHOR",
        "G2OPT5FEASIBLECOMMONANCHOR",
        "MD2G_G2_OPT5_FEASIBLE_COMMON_ANCHOR",
    ) or _env_on("TON_G2_OPT5_COMMON_ANCHOR")


def _is_opt6() -> bool:
    v = _g2_version()
    return v in (
        "G2_OPT6_HONOR_BASE_SWITCH",
        "G2OPT6HONORBASESWITCH",
        "MD2G_G2_OPT6_HONOR_BASE_SWITCH",
    ) or _env_on("TON_G2_OPT6_HONOR_BASE_SWITCH")


def _is_opt7() -> bool:
    v = _g2_version()
    return v in (
        "G2_OPT7_COMPLETION_HANDOFF",
        "G2OPT7COMPLETIONHANDOFF",
        "MD2G_G2_OPT7_COMPLETION_HANDOFF",
    ) or _env_on("TON_G2_OPT7_MAKE_BEFORE_BREAK")


def _device_contract_soft() -> bool:
    """command128 opt3: device is a soft ranking feature, not a hard physical veto."""
    v = _g2_version()
    return (
        v in ("G2_OPT3_DEVICE_CONTRACT", "G2OPT3DEVICECONTRACT", "MD2G_G2_OPT3_DEVICE_CONTRACT")
        or _is_opt4()
        or _is_opt5()
        or _is_opt6()
        or _is_opt7()
        or _env_on("TON_G2_DEVICE_CONTRACT_SOFT")
    )


def _feasible_g2(rid: int, *, device: float, tp: float, rates: dict, margin: float) -> bool:
    if _device_contract_soft():
        br = rates.get(rid, 1.0)
        return tp + 1e-9 >= br * margin
    return feasible(rid, device=device, tp=tp, rates=rates, margin=margin)


def choose_anchor_g2(
    *,
    device: float,
    capacity: float,
    rates: dict,
    qmap: dict,
    graph: dict,
    last_playable: int | None,
    weak: bool,
) -> int:
    if not _device_contract_soft():
        return choose_anchor_v3(
            device=device,
            capacity=capacity,
            rates=rates,
            qmap=qmap,
            graph=graph,
            last_playable=last_playable,
            weak=weak,
        )
    dominated = set(graph.get("dominated") or [])
    margin = _env_float("TON_MD2G_V3_ANCHOR_MARGIN", 1.08)
    if weak:
        margin = max(margin, _env_float("TON_MD2G_V3_WEAK_ANCHOR_MARGIN", 1.15))
    cands = []
    for rid in range(1, 10):
        if rid in dominated and rid not in (3, 8):
            continue
        if _feasible_g2(rid, device=device, tp=capacity, rates=rates, margin=margin):
            cands.append(rid)
    if not cands:
        for rid in (last_playable, 3, 8, 2):
            if rid and _feasible_g2(rid, device=device, tp=capacity, rates=rates, margin=1.02):
                return int(rid)
        return 3
    return max(cands, key=lambda r: (qmap[r]["q"], -rates.get(r, 9.0)))


def _is_opt0() -> bool:
    """command125/126 aligned candidates: evaluator-Qs scoring + playback last_playable."""
    v = _g2_version()
    return v in (
        "G2_OPT0", "G2OPT0", "MD2G_G2_OPT0",
        "G2_OPT1", "G2OPT1", "MD2G_G2_OPT1",
        "G2_TEACHER_DIAG", "G2TEACHERDIAG", "MD2G_G2_TEACHER_DIAG",
        "G2_OPT2_PROJECTOR", "G2_OPT2_DISTILL", "G2_OPT2_RETRAIN",
        "G2_OPT3_DEVICE_CONTRACT",
        "G2_OPT4_NATIVE9_STRUCTURAL",
        "G2_OPT5_FEASIBLE_COMMON_ANCHOR",
        "G2_OPT6_HONOR_BASE_SWITCH",
        "G2_OPT7_COMPLETION_HANDOFF",
    ) or _env_on("TON_MD2G_G2_OPT0") or _env_on("TON_MD2G_G2_OPT1") or _is_teacher_diag() or _is_opt4() or _is_opt5() or _is_opt6() or _is_opt7()


# Live evaluator Table-1 Qs (SIGCOMM_QOE_EQ9). Opt0 scores against this so
# "upgrades" that earn no canonical Qs credit are not preferred.
_EVALUATOR_QS_TABLE1 = {
    1: 0.8, 2: 0.6, 3: 0.4, 4: 1.0, 5: 1.0, 6: 0.6, 7: 0.8, 8: 0.4, 9: 0.4,
}


def _qmap_for_scoring(qmap: dict) -> dict:
    """Opt0: replace policy paper_q with evaluator Qs for scoring/ranking only."""
    if not _is_opt0():
        return qmap
    out = {k: dict(v) for k, v in qmap.items()}
    for rid, qs in _EVALUATOR_QS_TABLE1.items():
        if rid in out:
            # Score with evaluator Qs in [0.4, 1.0] so Rep8/9 are not
            # treated as quality upgrades over Rep3 (both Qs=0.4).
            out[rid]["q"] = float(qs)
            out[rid]["q_source"] = "evaluator_table1_opt0"
    return out


def _use_neural() -> bool:
    if _g2_version() in ("G2_RULE", "G2_RULEONLY"):
        return False
    return os.environ.get("TON_G2_USE_NEURAL", "1").strip().lower() not in ("0", "false", "off")


def _playback_confirmed_playable(d: dict, requested_rep: int) -> tuple[bool, dict]:
    """H3: update last_playable only after real playback confirmation.

    Provenance chain (all required for opt0):
      requested_rep → bytes/completion evidence → playable_ahead → not stalling
    Never treat selected_rep or rendered_rep alone as playable.
    """
    prov = {
        "requested_rep": int(requested_rep),
        "playability_ok": bool(d.get("playability_ok")),
        "active_rep": d.get("active_rep"),
        "playable_ahead_sec": d.get("playable_ahead_sec"),
        "buffer_level_sec": d.get("buffer_level_sec"),
        "stall_active": d.get("stall_active"),
        "rep_completion_frac": d.get("rep_completion_frac"),
        "delivery_rate_mbps": d.get("delivery_rate_mbps"),
        "bytes_remaining_current_object": d.get("bytes_remaining_current_object"),
    }
    if not d.get("playability_ok"):
        prov["reject"] = "PLAYABILITY_TELEMETRY_MISSING"
        return False, prov
    if d.get("stall_active"):
        prov["reject"] = "STALL_ACTIVE"
        return False, prov
    try:
        ahead = float(d.get("playable_ahead_sec", d.get("buffer_level_sec")) or 0.0)
    except (TypeError, ValueError):
        ahead = 0.0
    if ahead < 1.0:
        prov["reject"] = "PLAYABLE_AHEAD_LT_1S"
        return False, prov
    active = d.get("active_rep")
    if active is None:
        prov["reject"] = "ACTIVE_REP_MISSING"
        return False, prov
    try:
        if int(active) != int(requested_rep):
            prov["reject"] = "ACTIVE_NE_REQUESTED"
            return False, prov
    except (TypeError, ValueError):
        prov["reject"] = "ACTIVE_REP_INVALID"
        return False, prov
    try:
        frac = float(d.get("rep_completion_frac") or 0.0)
    except (TypeError, ValueError):
        frac = 0.0
    try:
        rate = float(d.get("delivery_rate_mbps") or 0.0)
    except (TypeError, ValueError):
        rate = 0.0
    # bytes-received / completion evidence (not merely a render intent)
    if frac < 0.05 and rate <= 1e-6:
        prov["reject"] = "NO_BYTES_OR_COMPLETION_EVIDENCE"
        return False, prov
    prov["accept"] = "REQUESTED_BYTES_PLAYABLE_CONFIRMED"
    return True, prov


def _load_model():
    global _MODEL, _MODEL_ERR
    if _MODEL is not None or _MODEL_ERR is not None:
        return _MODEL
    if not _use_neural():
        _MODEL_ERR = "rule_only"
        return None
    if _is_teacher_diag():
        path = os.environ.get("TON_G2_TEACHER_PATH") or os.environ.get("TON_G2_STUDENT_PATH")
    else:
        path = os.environ.get("TON_G2_STUDENT_PATH") or os.environ.get("TON_G2_TEACHER_PATH")
    if not path or not os.path.isfile(path):
        _MODEL_ERR = "no_checkpoint"
        return None
    try:
        import sys
        from pathlib import Path

        import torch

        ton = Path(__file__).resolve().parents[1]
        if str(ton) not in sys.path:
            sys.path.insert(0, str(ton))
        from controllers.g2_native9rep_model import build_student, build_teacher

        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        latent = int((ckpt.get("cfg") or {}).get("latent") or 64)
        net = build_teacher() if latent >= 96 else build_student()
        net.load_state_dict(ckpt["state_dict"])
        net.eval()
        _MODEL = net
        return _MODEL
    except Exception as exc:
        _MODEL_ERR = str(exc)
        return None


def _load_student_diag():
    """Comparison-only student for teacher-direct isolation. Never actuates."""
    global _STUDENT_DIAG, _STUDENT_DIAG_ERR
    if _STUDENT_DIAG is not None or _STUDENT_DIAG_ERR is not None:
        return _STUDENT_DIAG
    path = os.environ.get("TON_G2_STUDENT_PATH")
    if not path or not os.path.isfile(path):
        _STUDENT_DIAG_ERR = "no_student"
        return None
    try:
        import sys
        from pathlib import Path

        import torch

        ton = Path(__file__).resolve().parents[1]
        if str(ton) not in sys.path:
            sys.path.insert(0, str(ton))
        from controllers.g2_native9rep_model import build_student, build_teacher

        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        latent = int((ckpt.get("cfg") or {}).get("latent") or 64)
        net = build_teacher() if latent >= 96 else build_student()
        net.load_state_dict(ckpt["state_dict"])
        net.eval()
        _STUDENT_DIAG = net
        return _STUDENT_DIAG
    except Exception as exc:
        _STUDENT_DIAG_ERR = str(exc)
        return None


def _topk_reps(logits: list[float], k: int = 3) -> list[int]:
    order = sorted(range(1, 10), key=lambda r: float(logits[r - 1]) if r - 1 < len(logits) else -1e18, reverse=True)
    return order[:k]


def _append_teacher_diag(rec: dict) -> None:
    path = os.environ.get("TON_G2_TEACHER_DIAG_LOG")
    if not path:
        return
    try:
        import json

        with open(path, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _user_feats(d: dict, *, cap: float, delivered: float, cur: int, qmap: dict, rates: dict, n: int) -> list[float]:
    device = float(d.get("device_score", d.get("md2g_device_score", 0.5)) or 0.5)
    q = float(qmap.get(cur, {}).get("q", 1.0))
    br = float(rates.get(cur, 1.0))
    gid = float(d.get("md2g_group_id", 0) or 0)
    stall = float(d.get("stall_sec", d.get("recent_stall_s", 0.0)) or 0.0)
    buf = float(d.get("buffer_level_sec", 5.0) or 5.0)
    last = int(d.get("ton_last_playable") or cur)
    return [
        device,
        cap / 40.0,
        delivered / 10.0,
        q / 4.0,
        br / 8.0,
        gid / 3.0,
        min(1.0, n / 100.0),
        min(1.0, stall / 5.0),
        min(1.0, buf / 10.0),
        float(qmap.get(cur, {}).get("base", 3)) / 3.0,
        float(qmap.get(cur, {}).get("depth", 0)) / 2.0,
        float(qmap.get(last, {}).get("q", q)) / 4.0,
        min(1.0, max(0.0, cap - br) / 20.0),
        1.0 if d.get("pull_enhanced") else 0.0,
        float(d.get("fov_overlap") if d.get("fov_overlap") is not None else 0.5)
        if not (
            os.environ.get("TON_FOV_UNAVAILABLE", "").strip().lower() in ("1", "true", "yes", "on")
            or d.get("fov_available") is False
        )
        else 0.5,
        1.0,
    ]


def _content_feats(content: str | None, rates: dict, qmap: dict) -> list[float]:
    # ladder summary — not a single ordinal rep_id
    qs = [float(qmap[i]["q"]) for i in range(1, 10)]
    brs = [float(rates.get(i, 1.0)) for i in range(1, 10)]
    cid = {"redandblack": 0.0, "longdress": 1.0}.get(str(content or "").lower(), 0.5)
    return [
        cid,
        max(qs) / 4.0,
        min(qs) / 4.0,
        max(brs) / 8.0,
        min(brs) / 8.0,
        sum(qs) / 36.0,
        sum(brs) / 72.0,
        9.0 / 9.0,
        1.0,
        0.0,
        0.0,
        0.0,
    ]


def _neural_rep_scores_with(net, decisions: dict, content: str | None, rates: dict, qmap: dict):
    if net is None:
        return None
    try:
        import torch

        uids = [u for u, d in decisions.items() if isinstance(d, dict)]
        if not uids:
            return None
        n = len(uids)
        rows = []
        for uid in uids:
            d = decisions[uid]
            cur = int(d.get("selected_rep") or d.get("rep_id") or 3)
            cap = _capacity_mbps(d)
            delivered = _delivered_mbps(d)
            rows.append(_user_feats(d, cap=cap, delivered=delivered, cur=cur, qmap=qmap, rates=rates, n=n))
        user = torch.tensor([rows], dtype=torch.float32)
        content_f = torch.tensor([_content_feats(content, rates, qmap)], dtype=torch.float32)
        glob = torch.zeros(1, 10)
        glob[0, 0] = n / 100.0
        glob[0, 1] = 1.0
        with torch.no_grad():
            out = net(user, content_f, glob)
        logits = out["rep_logits"][0].tolist()
        groups = out["group_logits"][0].argmax(dim=-1).tolist()
        return {str(uid): {"rep_logits": logits[i], "group": int(groups[i])} for i, uid in enumerate(uids)}
    except Exception:
        return None


def _neural_rep_scores(decisions: dict, content: str | None, rates: dict, qmap: dict) -> dict[str, list[float]] | None:
    return _neural_rep_scores_with(_load_model(), decisions, content, rates, qmap)


def score_g2(
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
    neural_bonus: float = 0.0,
) -> tuple[float | None, str]:
    if cand == anchor:
        return neural_bonus, "KEEP_ANCHOR"
    if qmap[cand]["q"] + 1e-12 < qmap[anchor]["q"]:
        return None, "QUALITY_GAIN_TOO_SMALL"
    margin = _env_float("TON_G2_UPGRADE_MARGIN", 1.05)
    if device + 1e-9 < _device_need(cand):
        if _device_contract_soft():
            pass
        else:
            # Canonical label: this is the hard per-rep device-capability
            # check, NOT the relay BaseGuard reserve. Raw token kept for
            # log compatibility with command112/127 forensics.
            return None, "DEVICE_CAPABILITY_INFEASIBLE"
    br_c = rates.get(cand, 1.0)
    residual = capacity - rates.get(anchor, 0.0) * _env_float("TON_G2_ANCHOR_RESERVE", 1.05)
    if _is_opt4() and cand != anchor:
        # Native-9 user path is a full-stream replacement, not incremental/k and
        # not "keep paying the anchor plus the candidate" (that double-counts).
        # Group-level second-stream bounding happens in apply_g2_projection coalesce.
        mbytes = float(br_c)
        if capacity + 1e-9 < mbytes * margin:
            return None, "FULL_STREAM_MARGINAL_COST"
    else:
        mbytes = marginal_shared_bytes(anchor, cand, rates, group_k)
        if residual + 1e-9 < mbytes * margin:
            return None, "NO_RESIDUAL_BUDGET"
        if capacity + 1e-9 < br_c * margin:
            return None, "NO_RESIDUAL_BUDGET"
    dq = qmap[cand]["q"] - qmap[anchor]["q"]
    cross = qmap[cand]["base"] != qmap[cur]["base"]
    hyst = _env_float("TON_G2_HYST_SAME", 0.06) if not cross else _env_float("TON_G2_HYST_CROSS", 0.18)
    if cand != cur and dq < hyst and cand != anchor:
        return None, "HYSTERESIS"
    switch = _env_float("TON_G2_SWITCH_SAME", 0.10) if not cross else _env_float("TON_G2_SWITCH_CROSS", 0.32)
    completion = _env_float("TON_G2_COMPLETION", 0.45) * min(1.0, max(0.0, residual) / max(br_c, 0.5))
    # delivered is health cue only — never capacity
    health = min(1.0, max(0.0, delivered) / max(0.5, rates.get(anchor, 0.8)))
    completion *= 0.5 + 0.5 * health
    cong = _env_float("TON_G2_CONGESTION", 0.50) * util * (mbytes / 4.0)
    fair = _env_float("TON_G2_DEFICIT_GAIN", 0.50) * max(0.0, deficit)
    device_soft = 0.0
    if _device_contract_soft():
        shortfall = max(0.0, _device_need(cand) - device)
        device_soft = _env_float("TON_G2_DEVICE_SOFT_PENALTY", 0.35) * shortfall
    numer = _env_float("TON_G2_WQ", 1.0) * dq + completion + fair + 0.05 * device + neural_bonus - device_soft
    denom = 1e-3 + _env_float("TON_G2_WB", 1.0) * mbytes + switch + cong
    return numer / denom, "OK"


def apply_native9rep_policy_g2(decisions: dict, *, content: str | None = None, util: float = 0.0) -> dict:
    if not _env_on("TON_NATIVE9REP_MD2G"):
        return {"applied": False, "version": _g2_version()}
    n = max(1, len(decisions))
    rates = load_content_bitrates(content)
    qmap = _qmap_for_scoring(load_quality_map())
    graph = load_pareto_graph()
    neural = _neural_rep_scores(decisions, content, rates, qmap)
    student_neural = None
    if _is_teacher_diag():
        student_neural = _neural_rep_scores_with(_load_student_diag(), decisions, content, rates, qmap)

    gcounts: dict[Any, int] = {}
    for d in decisions.values():
        if not isinstance(d, dict):
            continue
        gid = d.get("md2g_group_id", d.get("grouping_id", 0))
        gcounts[gid] = gcounts.get(gid, 0) + 1

    quals = []
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
        gid = d.get("md2g_group_id", d.get("grouping_id", 0))
        # slow grouping: keep existing FoV group. G2-v2 never lets the neural head rewrite groups.
        if gid is None and neural and str(uid) in neural and _g2_version() not in ("G2_V2", "G2V2"):
            gid = neural[str(uid)]["group"]
            d["md2g_group_id"] = gid
        quals.append(qmap.get(cur, {}).get("q", 1.0))
        deficit = 0.0
        meta[uid] = {
            "cur": cur, "device": device, "cap": cap, "delivered": delivered,
            "gid": gid, "group_k": gcounts.get(gid, 1), "deficit": 0.0, "last": d.get("ton_last_playable"),
        }
    qmean = sum(quals) / max(1, len(quals))
    for uid, m in meta.items():
        m["deficit"] = max(0.0, qmean - qmap.get(m["cur"], {}).get("q", qmean))
        if m["device"] < 0.5:
            m["deficit"] += 0.2

    order = sorted(meta.keys(), key=lambda u: (-meta[u]["deficit"], meta[u]["device"]))
    group_residual: dict[Any, float] = {}
    group_anchor: dict[Any, int] = {}
    if _g2_version() in ("G2_V2", "G2V2"):
        by_g: dict[Any, list] = {}
        for uid, m in meta.items():
            by_g.setdefault(m["gid"], []).append(uid)
        for gid, uids in by_g.items():
            weakest = min(uids, key=lambda u: (meta[u]["device"], meta[u]["cap"]))
            mw = meta[weakest]
            group_anchor[gid] = choose_anchor_g2(
                device=mw["device"], capacity=mw["cap"], rates=rates, qmap=qmap, graph=graph,
                last_playable=int(mw["last"]) if mw["last"] is not None else mw["cur"],
                weak=True,
            )
    changed = 0
    for uid in order:
        d = decisions[uid]
        m = meta[uid]
        weak = m["deficit"] > 0.15 or m["device"] < 0.5
        if _g2_version() in ("G2_V2", "G2V2") and m["gid"] in group_anchor:
            anc = group_anchor[m["gid"]]
        else:
            anc = choose_anchor_g2(
                device=m["device"], capacity=m["cap"], rates=rates, qmap=qmap, graph=graph,
                last_playable=int(m["last"]) if m["last"] is not None else m["cur"], weak=weak,
            )
        if m["gid"] not in group_residual:
            group_residual[m["gid"]] = max(0.0, m["cap"] - rates.get(anc, 0.0) * 1.05)
        logits = (neural or {}).get(str(uid), {}).get("rep_logits") or [0.0] * 9
        # softmax-ish bonus only among later-feasible cands; compute after scoring
        best, best_s = anc, -1e18
        reject = []
        for cand in range(1, 10):
            bonus = 0.15 * float(logits[cand - 1]) if neural else 0.0
            s, reason = score_g2(
                anchor=anc, cand=cand, cur=m["cur"], qmap=qmap, rates=rates,
                device=m["device"], capacity=max(m["cap"], group_residual.get(m["gid"], 0.0) + rates.get(anc, 0.0)),
                delivered=m["delivered"], group_k=m["group_k"], util=util, deficit=m["deficit"],
                neural_bonus=bonus,
            )
            if s is None:
                rec = {"cand": cand, "reason": reason}
                if reason == "DEVICE_CAPABILITY_INFEASIBLE":
                    rec["raw_reason"] = "BASEGUARD_RESERVE"
                    rec["canonical_reason"] = "DEVICE_CAPABILITY_INFEASIBLE"
                reject.append(rec)
                continue
            if s > best_s:
                best_s, best = s, cand
        if not _feasible_g2(best, device=m["device"], tp=m["cap"], rates=rates, margin=1.02):
            best = anc if _feasible_g2(anc, device=m["device"], tp=m["cap"], rates=rates, margin=1.02) else 3
        extra = marginal_shared_bytes(anc, best, rates, m["group_k"])
        group_residual[m["gid"]] = max(0.0, group_residual.get(m["gid"], 0.0) - extra)
        b, e = rep_to_base_enh(best)
        d["base_version"] = b
        d["enhanced_level"] = e
        d["enh_level"] = e
        d["pull_enhanced"] = e > 0
        d["selected_rep"] = best
        d["rep_id"] = best
        d["ton_native9rep_policy"] = (
            "g2_v2_group_anchor_native9rep" if _g2_version() in ("G2_V2", "G2V2")
            else "g2_native9rep_two_timescale"
        )
        d["ton_native9rep_anchor"] = anc
        # H3: SELECT/rendered alone must never become last_playable under opt0.
        if _is_opt0():
            ok_play, prov = _playback_confirmed_playable(d, best)
            d["ton_last_playable_provenance"] = prov
            if ok_play:
                d["ton_last_playable"] = best
            # else: keep prior ton_last_playable (continuity must not eat future state)
            d["ton_native9rep_policy"] = "g2_opt0_eval_qs_align"
            d["ton_g2_opt0"] = True
        else:
            d["ton_last_playable"] = best
        d["ton_g2_capacity_mbps"] = m["cap"]
        d["ton_g2_delivered_mbps"] = m["delivered"]
        d["ton_g2_neural"] = bool(neural)
        d["ton_g2_group_anchor"] = anc
        if _is_teacher_diag():
            t_logits = list(logits)
            s_logits = (student_neural or {}).get(str(uid), {}).get("rep_logits") or [0.0] * 9
            t_top = _topk_reps(t_logits, 3)
            s_top = _topk_reps(s_logits, 3)
            gain_reject = [x for x in reject if int(x.get("cand") or 0) in (1, 2, 4, 5, 6, 7)]
            feasible_set = [c for c in range(1, 10) if all(x.get("cand") != c for x in reject)]
            d["ton_g2_teacher_top1"] = t_top[0] if t_top else None
            d["ton_g2_teacher_top3"] = t_top
            d["ton_g2_student_top1"] = s_top[0] if s_top else None
            d["ton_g2_student_top3"] = s_top
            d["ton_g2_feasible_set"] = feasible_set
            d["ton_g2_gain_reject"] = gain_reject
            _append_teacher_diag(
                {
                    "uid": str(uid),
                    "teacher_top1": t_top[0] if t_top else None,
                    "teacher_top3": t_top,
                    "student_top1": s_top[0] if s_top else None,
                    "student_top3": s_top,
                    "feasible_set": feasible_set,
                    "gain_rep_rejects": gain_reject,
                    "selected_rep": int(best),
                    "anchor": int(anc),
                    "rendered_or_playable": d.get("ton_last_playable") or d.get("active_rep"),
                    "canonical_Qs": float(qmap.get(best, {}).get("q", 0.0)),
                    "capacity_mbps": m["cap"],
                    "device": m["device"],
                }
            )
        changed += 1
    if _is_opt4() or _is_opt5() or _is_opt6() or _is_opt7():
        by_g = {}
        for uid, d in decisions.items():
            if isinstance(d, dict):
                by_g.setdefault(d.get("md2g_group_id"), []).append(uid)
        for gid, uids in by_g.items():
            reps = [int(decisions[u].get("selected_rep") or 3) for u in uids]
            cnt = Counter(reps)
            # Keep a low common anchor (most frequent non-gain or Rep3) plus at most one shared gain-rep.
            anc = 3 if 3 in cnt else (min((r for r in cnt if r not in (1, 2, 4, 5, 6, 7)), default=3))
            gain_cnt = [(r, c) for r, c in cnt.items() if r in (1, 2, 4, 5, 6, 7)]
            shared = None
            if gain_cnt:
                r, c = max(gain_cnt, key=lambda x: (x[1], qmap.get(x[0], {}).get("q", 0.0)))
                # opt4 required c>=2, which smashed singleton oracle-positive
                # upgrades back to Rep3. opt5 keeps one group-common gain-rep.
                if c >= 2 or _is_opt5() or _is_opt6() or _is_opt7():
                    shared = r
            for u in uids:
                d = decisions[u]
                rid = int(d.get("selected_rep") or anc)
                target = shared if (shared is not None and rid in (1, 2, 4, 5, 6, 7)) else anc
                if rid in (1, 2, 4, 5, 6, 7) and shared is None:
                    target = anc
                if (_is_opt5() or _is_opt6() or _is_opt7()) and shared is not None and rid == anc:
                    # completion-first: whole group rides the one shared gain stream
                    # when it is canonical-Qs positive vs Rep3.
                    if float(qmap.get(shared, {}).get("q", 0.0)) > float(qmap.get(3, {}).get("q", 0.0)):
                        target = shared
                if target != rid:
                    b, e = rep_to_base_enh(target)
                    d["base_version"] = b
                    d["enhanced_level"] = e
                    d["enh_level"] = e
                    d["pull_enhanced"] = e > 0
                    d["selected_rep"] = target
                    d["rep_id"] = target
                    d["ton_g2_opt4_coalesce"] = True
    if _g2_version() in ("G2_V2", "G2V2") and group_anchor:
        # Coalesce private upgrades: keep group_anchor + at most one shared refinement.
        by_g = {}
        for uid, d in decisions.items():
            if isinstance(d, dict):
                by_g.setdefault(d.get("md2g_group_id"), []).append(uid)
        for gid, uids in by_g.items():
            anc = int(group_anchor.get(gid, 3))
            reps = [int(decisions[u].get("selected_rep") or anc) for u in uids]
            cnt = Counter(reps)
            non_anc = [(r, c) for r, c in cnt.items() if r != anc]
            shared = None
            if non_anc:
                shared = max(non_anc, key=lambda x: (x[1], qmap.get(x[0], {}).get("q", 0.0)))[0]
            for u in uids:
                d = decisions[u]
                rid = int(d.get("selected_rep") or anc)
                target = rid
                if shared is None:
                    target = anc
                elif rid != anc and rid != shared:
                    mu = meta[u]
                    target = shared if feasible(shared, device=mu["device"], tp=mu["cap"], rates=rates, margin=1.02) else anc
                if target != rid:
                    b, e = rep_to_base_enh(target)
                    d["base_version"] = b
                    d["enhanced_level"] = e
                    d["enh_level"] = e
                    d["pull_enhanced"] = e > 0
                    d["selected_rep"] = target
                    d["rep_id"] = target
                    d["ton_g2v2_coalesced"] = True
    return {
        "applied": True,
        "n_users": changed,
        "version": _g2_version(),
        "neural": bool(neural),
        "model_err": _MODEL_ERR,
        "scale_users": n,
        "group_anchor": {str(k): int(v) for k, v in group_anchor.items()},
    }
