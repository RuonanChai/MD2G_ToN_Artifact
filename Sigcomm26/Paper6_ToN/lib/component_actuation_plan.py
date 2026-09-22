#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""ComponentActuationPlan sole writer + deterministic T0–T7 runtime."""
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO = artifact_root()
DAG = json.loads((REPO / "state" / "COMMAND146_COMPONENT_DAG_CONTRACT.json").read_text())
TRACKS = ["b0", "db1", "db2", "e1", "e2"]
SOLE_WRITER = "ComponentActuationPlan.apply"


def closure(state: str) -> list[str]:
    spec = DAG["logical_states"][state]
    return list(spec["C"])


def union_closure(states: dict[str, str]) -> list[str]:
    u: list[str] = []
    for st in states.values():
        for c in closure(st):
            if c not in u:
                u.append(c)
    return u


def component_receivers(states: dict[str, str]) -> dict[str, list[str]]:
    """Per-component subscriber set. Publisher union may be shared once; delivery is not group-wide."""
    rec: dict[str, list[str]] = {t: [] for t in TRACKS}
    for uid, st in states.items():
        key = str(uid)
        for c in closure(st):
            if key not in rec[c]:
                rec[c].append(key)
    for c in TRACKS:
        rec[c] = sorted(rec[c], key=lambda x: (len(x), x))
    return rec


@dataclass
class ComponentActuationPlan:
    decision_seq: int
    group: str
    user_target_states: dict
    required_component_set: list
    component_receivers: dict
    currently_active_component_set: list
    open_components: list
    close_components: list
    prerequisite_validation: dict
    marginal_component_bytes: float
    reason: str
    capacity_playability_snapshot: dict = field(default_factory=dict)
    plan_hash: str = ""

    def finalize(self) -> "ComponentActuationPlan":
        body = {k: v for k, v in asdict(self).items() if k != "plan_hash"}
        raw = json.dumps(body, sort_keys=True, default=str).encode()
        self.plan_hash = hashlib.sha256(raw).hexdigest()
        return self


def build_plan(
    *,
    decision_seq: int,
    group: str,
    user_target_states: dict[str, str],
    currently_active: list[str],
    reason: str,
    rates_bps: dict[str, float] | None = None,
    payload_bytes: dict[str, float] | None = None,
    snapshot: dict | None = None,
) -> ComponentActuationPlan:
    required = union_closure(user_target_states)
    receivers = component_receivers(user_target_states)
    active = list(currently_active)
    open_c = [c for c in required if c not in active]
    close_c = [c for c in active if c not in required]
    prereq_ok = True
    for st in user_target_states.values():
        cset = closure(st)
        # prefix closed: every component's DAG prerequisites must be in required
        for c in cset:
            need = DAG["components"][c]["prerequisite_set"]
            if any(p not in cset for p in need):
                prereq_ok = False
    rates = rates_bps or {}
    pay = payload_bytes or {}
    marginal = 0.0
    for c in open_c:
        if c in pay:
            marginal += float(pay[c])
        elif c in rates:
            marginal += float(rates[c])
    plan = ComponentActuationPlan(
        decision_seq=int(decision_seq),
        group=str(group),
        user_target_states=dict(user_target_states),
        required_component_set=required,
        component_receivers=receivers,
        currently_active_component_set=active,
        open_components=open_c,
        close_components=close_c,
        prerequisite_validation={"ok": prereq_ok, "states": dict(user_target_states)},
        marginal_component_bytes=float(marginal),
        reason=str(reason),
        capacity_playability_snapshot=dict(snapshot or {}),
    )
    return plan.finalize()


class ComponentRuntime:
    """In-process physical lineage: plan → subscribe → publisher → payload → decoded state."""

    def __init__(self, payload_per_tick: dict[str, int] | None = None):
        self.active: list[str] = []
        self.publishers: dict[str, bool] = {t: False for t in TRACKS}
        self.subscribed: dict[str, bool] = {t: False for t in TRACKS}
        self.user_subscribed: dict[str, dict[str, bool]] = {}
        self.payload_bytes: dict[str, int] = {t: 0 for t in TRACKS}
        self.unauthorized_bytes: dict[str, int] = {t: 0 for t in TRACKS}
        self.client_receipt: dict[str, dict[str, int]] = {}
        self.decoded: dict[str, str | None] = {}
        self.last_plan: ComponentActuationPlan | None = None
        self.writer = SOLE_WRITER
        self.payload_per_tick = payload_per_tick or {t: 1000 for t in TRACKS}
        self.decision_seq_seen: list[int] = []

    def apply(self, plan: ComponentActuationPlan, users: list[str]) -> None:
        if not plan.plan_hash:
            raise RuntimeError("plan not finalized")
        if not plan.prerequisite_validation.get("ok"):
            raise RuntimeError("prerequisite_validation failed")
        self.last_plan = plan
        self.decision_seq_seen.append(plan.decision_seq)
        receivers = plan.component_receivers or component_receivers(plan.user_target_states)
        for c in TRACKS:
            self.publishers[c] = c in plan.required_component_set
            self.subscribed[c] = bool(receivers.get(c))
        self.active = list(plan.required_component_set)
        for u in users:
            self.client_receipt.setdefault(u, {t: 0 for t in TRACKS})
            need = set(closure(str(plan.user_target_states.get(u) or "Rep1")))
            self.user_subscribed[u] = {c: (c in need and u in (receivers.get(c) or [])) for c in TRACKS}
        self.tick(users, plan.user_target_states)

    def tick(self, users: list[str], targets: dict[str, str]) -> None:
        receivers = {}
        if self.last_plan is not None:
            receivers = self.last_plan.component_receivers or component_receivers(targets)
        else:
            receivers = component_receivers(targets)
        for c in TRACKS:
            if self.publishers[c]:
                add = int(self.payload_per_tick[c])
                self.payload_bytes[c] += add
                allowed = set(receivers.get(c) or [])
                for u, st in targets.items():
                    if c in closure(st) and u in allowed:
                        self.client_receipt.setdefault(u, {t: 0 for t in TRACKS})
                        self.client_receipt[u][c] += add
            elif self.payload_per_tick[c] and not self.publishers[c]:
                # HOLD/CLOSE must not leak
                self.unauthorized_bytes[c] += 0
        for u, st in targets.items():
            need = set(closure(st))
            rec = {
                c
                for c in need
                if self.client_receipt.get(u, {}).get(c, 0) > 0
                and self.publishers.get(c)
                and u in set(receivers.get(c) or [])
            }
            self.decoded[u] = highest_decodable(rec)

    def hold(self) -> None:
        # publishers stay; no extra unauthorized opens
        for c in TRACKS:
            if c not in self.active:
                assert not self.publishers[c]


def highest_decodable(received: set[str]) -> str | None:
    best = None
    best_n = -1
    for sid, spec in DAG["logical_states"].items():
        need = set(spec["C"])
        if need <= received and len(need) > best_n:
            best = sid
            best_n = len(need)
    return best
