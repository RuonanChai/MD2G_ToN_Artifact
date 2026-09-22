#!/usr/bin/env python3
"""Reproduce overnight OPT1_SMOKE stuck state; prove one-and-only-one launch."""
from __future__ import annotations

import sys
import tempfile
import threading
import time
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "scripts"))

import command126_edges as edges  # noqa: E402
from command126_edges import (  # noqa: E402
    EXECUTABLE,
    TRANSITION_STALL_S,
    execute_edge,
    maybe_execute_actionable_edge,
)


def _isolate_edge_lock():
    """Do not contend with a live scientific EDGE.lock."""
    tmp = Path(tempfile.mkdtemp(prefix="c126_edge_test_"))
    edges.LOCK = tmp / "COMMAND126_EDGE.lock"
    edges.STATE = tmp
    return tmp

# Exact overnight stuck reconstruction (not a scientific failure).
STUCK = {
    "phase": "RETRAIN",
    "subphase": "opt1_smoke",
    "active_cell_key": None,
    "next_action": "OPT1_SMOKE",
    "moq_live": False,
    "smoke_done": 4,
    "transition_idle_s": 8.6 * 3600,
}


def test_stuck_state_is_actionable():
    assert STUCK["phase"] == "RETRAIN"
    assert STUCK["subphase"] == "opt1_smoke"
    assert STUCK["active_cell_key"] is None
    assert STUCK["next_action"] == "OPT1_SMOKE"
    assert STUCK["next_action"] in EXECUTABLE
    assert STUCK["transition_idle_s"] > TRANSITION_STALL_S


def test_old_watch_status_only_would_not_launch():
    """Pre-repair watch only ran harness tick; harness never called execute_edge."""
    watch = (TON / "scripts" / "command126_watch.py").read_text(encoding="utf-8")
    harness = (TON / "scripts" / "command126_harness.py").read_text(encoding="utf-8")
    assert "execute_edge" in watch
    assert "maybe_execute_actionable_edge" in harness or "execute_edge" in harness
    assert "TRANSITION_STALL_S" in watch or "180" in watch


def test_one_and_only_one_launch_from_stuck_state():
    _isolate_edge_lock()
    launches = []
    started = threading.Event()
    release = threading.Event()

    def launch_fn():
        launches.append(threading.current_thread().name)
        started.set()
        assert release.wait(8), "release timeout"
        return {"rc": 0}

    results: list[dict | None] = [None, None]

    def t0():
        results[0] = maybe_execute_actionable_edge(STUCK, launch_fn=launch_fn, min_idle_s=TRANSITION_STALL_S)

    def t1():
        assert started.wait(4), "first launch did not start"
        results[1] = maybe_execute_actionable_edge(STUCK, launch_fn=launch_fn, min_idle_s=TRANSITION_STALL_S)

    a = threading.Thread(target=t0, name="edge-a")
    b = threading.Thread(target=t1, name="edge-b")
    a.start()
    b.start()
    assert started.wait(4), "first launch did not start"
    time.sleep(0.3)
    release.set()
    a.join(10)
    b.join(10)
    assert results[0] is not None and results[1] is not None
    statuses = {results[0]["status"], results[1]["status"]}
    assert "LAUNCHED" in statuses
    assert "DUPLICATE_REFUSED" in statuses
    assert len(launches) == 1
    launched = results[0] if results[0]["status"] == "LAUNCHED" else results[1]
    refused = results[0] if results[0]["status"] == "DUPLICATE_REFUSED" else results[1]
    assert launched["action"] == "OPT1_SMOKE"
    assert refused["reason"] in ("EDGE_LOCK", "OWNER_EXISTS")


def test_launch_failure_classified_not_idle():
    _isolate_edge_lock()
    def boom():
        raise RuntimeError("synthetic_launch_fail")

    r = execute_edge("OPT1_SMOKE", launch_fn=boom)
    assert r["status"] == "FAIL_CLASSIFIED"
    assert r["class"] == "LAUNCH_EXCEPTION"


def test_retrain_edge_preserves_existing_opt1_checkpoints():
    r = execute_edge("LAUNCH_OPT1_RETRAIN", launch_fn=lambda: {"rc": 0})
    assert r["status"] == "SKIP_RETRAIN_CHECKPOINT_PRESERVED"
    assert r["next"] == "OPT1_SMOKE"


if __name__ == "__main__":
    tests = [
        test_stuck_state_is_actionable,
        test_old_watch_status_only_would_not_launch,
        test_one_and_only_one_launch_from_stuck_state,
        test_launch_failure_classified_not_idle,
        test_retrain_edge_preserves_existing_opt1_checkpoints,
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print("PASS test_command126_opt1_smoke_edge")
