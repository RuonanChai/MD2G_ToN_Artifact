#!/usr/bin/env python3
"""COMPLETE OPT1_SMOKE must never be re-entered; one transition to DISTILL_OR_RETRAIN_DIAG."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "scripts"))

import command126_edges as edges  # noqa: E402
import command127_common as c127  # noqa: E402
from command126_edges import execute_edge  # noqa: E402
from command127_common import next_after_opt1_complete  # noqa: E402


def _isolate():
    tmp = Path(tempfile.mkdtemp(prefix="c127_opt1_complete_"))
    edges.LOCK = tmp / "COMMAND126_EDGE.lock"
    edges.STATE = tmp
    edges.ANALYSIS = tmp
    edges.owner_exists = lambda: False
    c127.STATE = tmp
    c127.ANALYSIS = tmp
    (tmp / "COMMAND126_OPT1_SMOKE.json").write_text(
        json.dumps(
            {
                "status": "COMPLETE",
                "acceptance": "FAIL_COLLAPSE_TO_REP3",
                "next_step": "DISTILL_OR_RETRAIN_BRANCH",
                "strategy": "md2g_g2_opt1",
                "n": 4,
            },
            indent=2,
        )
        + "\n"
    )
    return tmp


def test_next_action_never_reenters_opt1():
    assert (
        next_after_opt1_complete(
            "FAIL_COLLAPSE_TO_REP3",
            distill_consumed=False,
            teacher_complete=False,
        )
        == "DISTILL_OR_RETRAIN_DIAG"
    )
    assert (
        next_after_opt1_complete(
            "FAIL_COLLAPSE_TO_REP3",
            distill_consumed=True,
            teacher_complete=False,
        )
        == "TEACHER_DIAG"
    )
    assert (
        next_after_opt1_complete(
            "FAIL_COLLAPSE_TO_REP3",
            distill_consumed=True,
            teacher_complete=True,
        )
        in ("CLASSIFY_THEN_OPT2", "OPT2_SMOKE", "OPT2_ACCEPT", "FREEZE_OR_NEXT")
    )
    assert "OPT1_SMOKE" not in (
        next_after_opt1_complete("FAIL_COLLAPSE_TO_REP3", distill_consumed=True, teacher_complete=True),
    )


def test_complete_opt1_is_consumed_zero_new_cells():
    _isolate()
    launches = []

    def boom():
        launches.append("launched")
        return {"rc": 0}

    # Production path: no launch_fn → consume COMPLETE, do not call runner.
    r = execute_edge("OPT1_SMOKE")
    assert r["status"] == "CONSUMED_COMPLETE"
    assert r["next"] == "DISTILL_OR_RETRAIN_DIAG"
    assert r["new_opt1_cells"] == 0
    # Even if a launch_fn is supplied after isolation, consume still wins when
    # launch_fn is None. Prove launch_fn is unused on the consume path.
    assert launches == []
    r2 = execute_edge("OPT1_SMOKE", launch_fn=boom)
    # launch_fn bypasses consume (legacy unit-test hook); production never passes it.
    assert r2["status"] == "LAUNCHED"
    assert launches == ["launched"]


def test_exactly_one_transition_to_distill_diag():
    tmp = _isolate()
    first = execute_edge("DISTILL_OR_RETRAIN_DIAG")
    assert first["status"] == "TRANSITIONED"
    assert first["next"] == "TEACHER_DIAG"
    assert first["new_opt1_cells"] == 0
    marker = tmp / "COMMAND127_DISTILL_OR_RETRAIN_DIAG.json"
    assert marker.is_file()
    body = json.loads(marker.read_text())
    assert body["consumed"] is True
    second = execute_edge("DISTILL_OR_RETRAIN_DIAG")
    assert second["status"] == "CONSUMED_COMPLETE"
    assert second["next"] == "TEACHER_DIAG"
    assert second["new_opt1_cells"] == 0
    # Still no OPT1 relaunch.
    third = execute_edge("OPT1_SMOKE")
    assert third["status"] == "CONSUMED_COMPLETE"
    assert third["new_opt1_cells"] == 0
    assert third["next"] == "TEACHER_DIAG"


if __name__ == "__main__":
    tests = [
        test_next_action_never_reenters_opt1,
        test_complete_opt1_is_consumed_zero_new_cells,
        test_exactly_one_transition_to_distill_diag,
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print("PASS test_command127_opt1_complete_no_reenter")
