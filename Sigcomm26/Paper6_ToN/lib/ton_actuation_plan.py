#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""command123: sole physical ActuationPlan authority for native-rep subscriptions.

PPO/native proposal and causal-arm policy may only *propose*. After
``finalize_actuation_plan``, this module is the only scientific-runtime writer of
``selected_rep`` / ``pull_enhanced`` / ``base_version`` / ``enhanced_level``.
Dispatch must apply the plan's user targets and close any other representation.
Does not change H1/H2, arm thresholds, paper_U, or command116 metrics.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from ton_native9rep_md2g_policy import rep_to_base_enh

_LOCK = threading.Lock()
_SEQ = 0
_LAST_PLAN_HASH: str | None = None
# Runtime fail-closed: any independent selected_rep mutation after apply is a contract break.
_SOLE_WRITER = "ton_actuation_plan.apply_actuation_plan"


@dataclass
class ActuationPlan:
    decision_seq: int
    ts: float
    arm: str
    group_id: str
    common_rep: int
    desired_secondary_reps: list[int]
    desired_active_streams: list[int]
    protected_users: list[Any]
    reason: str
    source_policy_proposal: dict
    feasibility_snapshot: dict
    buffer_playability_snapshot_hash: str
    plan_hash: str
    user_targets: dict = field(default_factory=dict)
    startup_hold: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def next_decision_seq() -> int:
    global _SEQ
    with _LOCK:
        _SEQ += 1
        return _SEQ


def snapshot_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _plan_hash_body(body: dict) -> str:
    skip = {"plan_hash", "ts"}
    payload = {k: v for k, v in body.items() if k not in skip}
    return snapshot_hash(payload)


def stamp_rep_fields(d: dict, rid: int) -> None:
    """THE only allowed mutation of physical native-representation fields."""
    base, enh = rep_to_base_enh(int(rid))
    d["selected_rep"] = int(rid)
    d["rep_id"] = int(rid)
    d["base_version"] = int(base)
    d["enhanced_level"] = int(enh)
    d["enh_level"] = int(enh)
    d["pull_enhanced"] = bool(enh > 0)
    d["actuation_writer"] = _SOLE_WRITER


def build_group_plan(
    *,
    arm: str,
    group_id: Any,
    common_rep: int,
    secondary: int | None,
    reason: str,
    user_targets: dict,
    protected_users: list,
    source_policy_proposal: dict,
    feasibility_snapshot: dict,
    buffer_playability_snapshot: dict,
    startup_hold: bool = False,
    decision_seq: int | None = None,
) -> ActuationPlan:
    streams = {int(common_rep)}
    secs: list[int] = []
    if secondary is not None:
        streams.add(int(secondary))
        secs.append(int(secondary))
    seq = int(decision_seq) if decision_seq is not None else next_decision_seq()
    body = {
        "decision_seq": seq,
        "arm": str(arm),
        "group_id": str(group_id),
        "common_rep": int(common_rep),
        "desired_secondary_reps": sorted(secs),
        "desired_active_streams": sorted(streams),
        "protected_users": [str(u) for u in protected_users],
        "reason": str(reason),
        "source_policy_proposal": source_policy_proposal,
        "feasibility_snapshot": feasibility_snapshot,
        "buffer_playability_snapshot_hash": snapshot_hash(buffer_playability_snapshot),
        "user_targets": {str(k): int(v) for k, v in user_targets.items()},
        "startup_hold": bool(startup_hold),
    }
    plan = ActuationPlan(
        ts=time.time(),
        plan_hash="",
        **body,
    )
    plan.plan_hash = _plan_hash_body(plan.to_dict())
    return plan


def apply_actuation_plan(decisions: dict, plans: list[ActuationPlan]) -> dict:
    """Sole scientific-runtime writer of the sender-visible native stream set."""
    global _LAST_PLAN_HASH
    applied_users = []
    for plan in plans:
        for uid, rid in (plan.user_targets or {}).items():
            d = None
            if uid in decisions:
                d = decisions[uid]
            else:
                try:
                    d = decisions.get(int(uid))
                except (TypeError, ValueError):
                    d = None
                if d is None:
                    d = decisions.get(str(uid))
            if not isinstance(d, dict):
                continue
            stamp_rep_fields(d, int(rid))
            d["actuation_decision_seq"] = int(plan.decision_seq)
            d["actuation_plan_hash"] = plan.plan_hash
            d["actuation_arm"] = plan.arm
            d["actuation_reason"] = plan.reason
            d["ton_active_stream_set"] = list(plan.desired_active_streams)
            d["ton_common_rep"] = int(plan.common_rep)
            d["ton_gen3_probe_arm"] = plan.arm
            d["ton_gen3_probe_reason"] = plan.reason
            applied_users.append(str(uid))
        _LAST_PLAN_HASH = plan.plan_hash
    return {
        "writer": _SOLE_WRITER,
        "n_users": len(applied_users),
        "n_plans": len(plans),
        "plan_hashes": [p.plan_hash for p in plans],
        "decision_seqs": [p.decision_seq for p in plans],
    }


def assert_plan_is_physical_authority(d: dict) -> None:
    """Fail closed if a later writer overwrote the plan without a new ActuationPlan."""
    if not isinstance(d, dict):
        return
    if d.get("actuation_writer") not in (None, _SOLE_WRITER):
        raise RuntimeError(
            f"ACTUATION_MULTIPLE_WRITERS: {d.get('actuation_writer')!r} mutated physical reps"
        )


def probe_arm_active() -> bool:
    return bool((os.environ.get("TON_GEN3_PROBE_ARM") or "").strip())


def emergency_safety_plan(
    *,
    arm: str,
    group_id: Any,
    common_rep: int,
    user_targets: dict,
    reason: str,
    source_policy_proposal: dict,
    feasibility_snapshot: dict,
    buffer_playability_snapshot: dict,
    protected_users: list | None = None,
) -> ActuationPlan:
    """Any emergency fallback MUST be a new explicit ActuationPlan, never a hidden mutation."""
    return build_group_plan(
        arm=arm,
        group_id=group_id,
        common_rep=int(common_rep),
        secondary=None,
        reason=str(reason),
        user_targets=user_targets,
        protected_users=list(protected_users or []),
        source_policy_proposal=source_policy_proposal,
        feasibility_snapshot=feasibility_snapshot,
        buffer_playability_snapshot=buffer_playability_snapshot,
        startup_hold=False,
    )
