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

"""Command60/61 regression: FULL_INDEPENDENT_REPS atomic lifecycle (synthetic)."""
import itertools
import os
import sys
from pathlib import Path

import pytest

REPO = artifact_root()
sys.path.insert(0, str(REPO))

from strategies.rep_lifecycle_v2 import (  # noqa: E402
    REP_BROADCAST,
    RepLifecycle,
    broadcast_to_rep,
    map_to_rep_id,
    rep_to_broadcast,
)


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# --- mapping ---


def test_all_nine_mappings_bidirectional() -> None:
    assert len(REP_BROADCAST) == 9
    for rep_id, name in REP_BROADCAST.items():
        assert rep_to_broadcast(rep_id) == name
        assert broadcast_to_rep(name) == rep_id

    assert map_to_rep_id(1, 0) == 1
    assert map_to_rep_id(2, 0) == 2
    assert map_to_rep_id(3, 0) == 3
    assert map_to_rep_id(1, 1) == 4
    assert map_to_rep_id(1, 2) == 5
    assert map_to_rep_id(2, 1) == 6
    assert map_to_rep_id(2, 2) == 7
    assert map_to_rep_id(3, 1) == 8
    assert map_to_rep_id(3, 2) == 9

    for rep_id in range(1, 10):
        bv = min(rep_id, 3) if rep_id <= 3 else {4: 1, 5: 1, 6: 2, 7: 2, 8: 3, 9: 3}[rep_id]
        el = 0 if rep_id <= 3 else (1 if rep_id in (4, 6, 8) else 2)
        assert map_to_rep_id(bv, el) == rep_id
        assert rep_to_broadcast(rep_id) == REP_BROADCAST[rep_id]


# --- base3 → rep8: temporary overlap, never steady dual ---


def test_transition_base3_to_rep8_atomic_no_steady_dual() -> None:
    clk = FakeClock()
    lc = RepLifecycle(clock=clk)
    lc.seed_rendered(3)

    lc.request_target(8)
    assert lc.intended_rep == 8
    assert lc.decision_epoch == 1

    lc.begin_subscribe(8)
    assert lc.subscribed_rep == 8
    assert lc.overlap_start is not None
    assert lc.simultaneous_active_count() == 2  # temporary overlap OK

    lc.on_first_valid_object(8)
    assert lc.rendered_rep == 8
    assert lc.delivered_rep == 8
    assert lc.active_subs[3]["status"] == "pending_cancel"
    assert lc.cancel_request_ts is not None
    # still two subs until cancel ack
    assert lc.simultaneous_active_count() == 2

    lc.ack_cancel(3)
    assert 3 not in lc.active_subs
    assert lc.simultaneous_active_count() == 1
    assert lc.overlap_end is not None
    assert lc.steady_single_subscription()


# --- cancel without ack keeps pending ---


def test_cancel_without_ack_keeps_pending() -> None:
    clk = FakeClock()
    lc = RepLifecycle(clock=clk)
    lc.seed_rendered(1)

    lc.request_target(4)
    lc.begin_subscribe(4)
    lc.on_first_valid_object(4)

    assert lc.active_subs[1]["status"] == "pending_cancel"
    assert lc._pending_cancel == 1
    assert lc.simultaneous_active_count() == 2
    assert not lc.steady_single_subscription()

    snap = lc.snapshot()
    assert snap["pending_cancel"] == 1
    assert snap["simultaneous_active_count"] == 2


# --- pairwise transitions per base family ---

BASE_FAMILIES = {
    1: (1, 4, 5),
    2: (2, 6, 7),
    3: (3, 8, 9),
}


def _run_transition(from_rep: int, to_rep: int) -> RepLifecycle:
    clk = FakeClock()
    lc = RepLifecycle(clock=clk)
    lc.seed_rendered(from_rep)
    lc.request_target(to_rep)
    lc.begin_subscribe(to_rep)
    lc.on_first_valid_object(to_rep)
    lc.ack_cancel(from_rep)
    return lc


@pytest.mark.parametrize(
    "base_version,reps",
    [(bv, reps) for bv, reps in BASE_FAMILIES.items()],
)
def test_pairwise_transitions_same_base_family(base_version: int, reps: tuple[int, ...]) -> None:
    for a, b in itertools.permutations(reps, 2):
        lc = _run_transition(a, b)
        assert lc.rendered_rep == b, f"base{bv}: {a}->{b} rendered"
        assert lc.simultaneous_active_count() == 1, f"base{bv}: {a}->{b} steady dual forbidden"
        assert rep_to_broadcast(b) == REP_BROADCAST[b]
        assert lc.steady_single_subscription()


# --- overlap violation ---


def test_overlap_violation_when_exceed_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGCOMM_REP_MAX_OVERLAP_S", "3.0")
    clk = FakeClock()
    lc = RepLifecycle(clock=clk)
    lc.seed_rendered(3)

    lc.request_target(8)
    lc.begin_subscribe(8)
    lc.on_first_valid_object(8)

    clk.advance(4.0)  # exceed 3.0 s without cancel ack
    snap = lc.snapshot()
    assert snap["overlap_violation"] is True
    assert lc.overlap_violation is True


def test_overlap_within_max_no_violation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGCOMM_REP_MAX_OVERLAP_S", "3.0")
    clk = FakeClock()
    lc = RepLifecycle(clock=clk)
    lc.seed_rendered(3)

    lc.request_target(8)
    lc.begin_subscribe(8)
    lc.on_first_valid_object(8)
    clk.advance(1.0)
    lc.ack_cancel(3)

    assert lc.overlap_violation is False
    assert lc.snapshot()["overlap_violation"] is False


def test_invalid_rep_raises() -> None:
    with pytest.raises(ValueError):
        rep_to_broadcast(10)
    with pytest.raises(ValueError):
        broadcast_to_rep("base99")
