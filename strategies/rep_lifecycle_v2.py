#!/usr/bin/env python3
"""FULL_INDEPENDENT_REPS atomic lifecycle (command60/61).

Pure mapping + state machine — no Mininet/MoQ wiring.
"""
from __future__ import annotations

import os
import time
from typing import Callable, Dict, Mapping, Optional

# Rep1–3: base-only; Rep4–9: full independently decodable composite MP4s.
REP_BROADCAST: Dict[int, str] = {
    1: "base1",
    2: "base2",
    3: "base3",
    4: "base1_enhanced1",
    5: "base1_enhanced2",
    6: "base2_enhanced1",
    7: "base2_enhanced2",
    8: "base3_enhanced1",
    9: "base3_enhanced2",
}

_BROADCAST_TO_REP: Dict[str, int] = {name: rid for rid, name in REP_BROADCAST.items()}


def map_to_rep_id(base_version: int, enh_level: int) -> int:
    """Map base version + enhanced level → Rep ID (1–9 ladder)."""
    bv = int(base_version)
    el = int(enh_level)
    if el <= 0:
        if bv not in (1, 2, 3):
            raise ValueError(f"invalid base_version for base-only rep: {bv}")
        return bv
    if el == 1:
        return {1: 4, 2: 6, 3: 8}[bv]
    if el >= 2:
        return {1: 5, 2: 7, 3: 9}[bv]
    raise ValueError(f"invalid enhanced level: {el}")


def rep_to_broadcast(rep_id: int) -> str:
    """Rep ID → MoQ broadcast name."""
    rid = int(rep_id)
    try:
        return REP_BROADCAST[rid]
    except KeyError as exc:
        raise ValueError(f"invalid rep_id: {rep_id}") from exc


def broadcast_to_rep(name: str) -> int:
    """MoQ broadcast name → Rep ID."""
    key = str(name)
    try:
        return _BROADCAST_TO_REP[key]
    except KeyError as exc:
        raise ValueError(f"unknown broadcast name: {name!r}") from exc


def plan_transition(
    current_rendered: Optional[int],
    base_version: int,
    enh_level: int,
) -> tuple[int, bool]:
    """Return ``(target_rep, need_switch)`` for controller enh_level on fixed base."""
    target = map_to_rep_id(base_version, enh_level)
    if current_rendered is None:
        return target, True
    return target, int(current_rendered) != target


def _max_overlap_s() -> float:
    return float(os.environ.get("SIGCOMM_REP_MAX_OVERLAP_S", "3.0"))


class RepLifecycle:
    """Atomic FULL_INDEPENDENT_REPS subscription lifecycle audit state."""

    def __init__(self, *, clock: Optional[Callable[[], float]] = None) -> None:
        self._clock = clock or time.monotonic

        self.intended_rep: Optional[int] = None
        self.admitted_rep: Optional[int] = None
        self.subscribed_rep: Optional[int] = None
        self.delivered_rep: Optional[int] = None
        self.rendered_rep: Optional[int] = None

        self.decision_epoch: int = 0
        self.subscription_epoch: int = 0

        self.overlap_start: Optional[float] = None
        self.overlap_end: Optional[float] = None
        self.cancel_request_ts: Optional[float] = None
        self.cancel_ack_ts: Optional[float] = None

        self.stale_bytes: int = 0
        self.duplicate_bytes: int = 0

        # rep_id -> {"since": float, "status": str}
        self.active_subs: Dict[int, Dict[str, object]] = {}

        self.overlap_violation: bool = False
        self._pending_cancel: Optional[int] = None

    @property
    def max_overlap_s(self) -> float:
        return _max_overlap_s()

    def request_target(self, rep_id: int) -> None:
        """Controller decision: target Rep for next steady state."""
        rid = int(rep_id)
        rep_to_broadcast(rid)  # validate
        self.decision_epoch += 1
        self.intended_rep = rid

    def begin_subscribe(self, rep_id: int) -> None:
        """Start subscription to exactly one broadcast name for *rep_id*."""
        rid = int(rep_id)
        rep_to_broadcast(rid)
        self.subscription_epoch += 1
        self.subscribed_rep = rid
        self.admitted_rep = rid

        now = self._clock()
        if self._has_overlap_candidate(excluding=rid):
            if self.overlap_start is None:
                self.overlap_start = now

        self.active_subs[rid] = {"since": now, "status": "subscribed"}
        self._evaluate_overlap_violation(now)

    def on_first_valid_object(self, rep_id: int) -> None:
        """First decodable object on *rep_id*; promote atomically if intended."""
        rid = int(rep_id)
        rep_to_broadcast(rid)
        self.delivered_rep = rid

        entry = self.active_subs.get(rid)
        if entry is not None:
            entry["status"] = "delivered"

        if self.intended_rep == rid:
            self._promote(rid)

    def ack_cancel(self, old_rep: int) -> None:
        """Acknowledge cancellation of a superseded Rep subscription."""
        old = int(old_rep)
        if old not in self.active_subs:
            return

        now = self._clock()
        self.cancel_ack_ts = now
        del self.active_subs[old]

        if self._pending_cancel == old:
            self._pending_cancel = None

        if self.overlap_start is not None and self.simultaneous_active_count() <= 1:
            self.overlap_end = now
            self._evaluate_overlap_violation(now)
            self.overlap_start = None

    def simultaneous_active_count(self) -> int:
        """Count Reps with an outstanding subscription (incl. pending cancel)."""
        return len(self.active_subs)

    def steady_single_subscription(self) -> bool:
        """True when at most one active sub and no pending cancel overlap."""
        return self.simultaneous_active_count() <= 1 and self._pending_cancel is None

    def snapshot(self) -> dict:
        """JSONL-serializable audit record."""
        now = self._clock()
        self._evaluate_overlap_violation(now)
        return {
            "intended_rep": self.intended_rep,
            "admitted_rep": self.admitted_rep,
            "subscribed_rep": self.subscribed_rep,
            "delivered_rep": self.delivered_rep,
            "rendered_rep": self.rendered_rep,
            "decision_epoch": self.decision_epoch,
            "subscription_epoch": self.subscription_epoch,
            "overlap_start": self.overlap_start,
            "overlap_end": self.overlap_end,
            "cancel_request_ts": self.cancel_request_ts,
            "cancel_ack_ts": self.cancel_ack_ts,
            "stale_bytes": self.stale_bytes,
            "duplicate_bytes": self.duplicate_bytes,
            "active_subs": {str(k): dict(v) for k, v in self.active_subs.items()},
            "pending_cancel": self._pending_cancel,
            "simultaneous_active_count": self.simultaneous_active_count(),
            "overlap_violation": self.overlap_violation,
            "max_overlap_s": self.max_overlap_s,
        }

    def _promote(self, rep_id: int) -> None:
        old = self.rendered_rep
        now = self._clock()
        self.rendered_rep = rep_id
        self.admitted_rep = rep_id
        self.subscribed_rep = rep_id

        if rep_id in self.active_subs:
            self.active_subs[rep_id]["status"] = "active"

        if old is not None and old != rep_id and old in self.active_subs:
            self.active_subs[old]["status"] = "pending_cancel"
            self._pending_cancel = old
            self.cancel_request_ts = now

        self._evaluate_overlap_violation(now)

    def _has_overlap_candidate(self, *, excluding: int) -> bool:
        if self.rendered_rep is not None and self.rendered_rep != excluding:
            return True
        for rid in self.active_subs:
            if rid != excluding:
                return True
        return False

    def _evaluate_overlap_violation(self, now: Optional[float] = None) -> None:
        if self.overlap_violation:
            return
        if self.overlap_start is None:
            return
        ts = now if now is not None else self._clock()
        end = self.overlap_end if self.overlap_end is not None else ts
        if end - self.overlap_start > self.max_overlap_s:
            self.overlap_violation = True

    def seed_rendered(self, rep_id: int) -> None:
        """Test/dispatch helper: establish initial steady rendered Rep."""
        rid = int(rep_id)
        rep_to_broadcast(rid)
        now = self._clock()
        self.rendered_rep = rid
        self.intended_rep = rid
        self.admitted_rep = rid
        self.subscribed_rep = rid
        self.delivered_rep = rid
        self.active_subs = {rid: {"since": now, "status": "active"}}
