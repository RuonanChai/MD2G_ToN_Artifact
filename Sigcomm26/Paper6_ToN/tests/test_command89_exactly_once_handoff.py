#!/usr/bin/env python3
"""command89 exactly-once handoff guards (no live process mutation)."""
from __future__ import annotations

import ast
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
STATE = TON / "state"
SCRIPTS = TON / "scripts"


def test_watchdog_has_no_popen():
    src = (SCRIPTS / "ton_command88_health_watchdog.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in ("Popen", "system"):
                raise AssertionError(f"forbidden call .{func.attr} at line {node.lineno}")
            if isinstance(func, ast.Name) and func.id == "Popen":
                raise AssertionError(f"forbidden Popen at line {node.lineno}")


def test_orch_does_not_popen_pipeline():
    src = (SCRIPTS / "command87_orchestrator.py").read_text(encoding="utf-8")
    assert "raise SystemExit(42)" in src
    assert "COMMAND88_LIVE_PIPELINE_LAUNCHED" not in src
    assert "command88_live_scientific_pipeline.py" in src
    # no Popen targeting the pipeline script
    assert "command88_live_scientific_pipeline.py\"]" not in src.replace(" ", "")


def test_supervisor_phase_aware_strings():
    src = (SCRIPTS / "ton_command88_supervisor.sh").read_text(encoding="utf-8")
    assert "CANARY_COMPLETE_HANDOFF_READY" in src
    assert "COMMAND89_TRANSITION_GUARD_PASS" in src
    assert "command88_live_scientific_pipeline.py" in src
    assert "stopping predecessor" in src or "do not restart orch" in src


def test_transition_guard_token_required():
    assert (STATE / "COMMAND89_TRANSITION_GUARD_PASS").exists()


def test_successor_instance_schema_placeholder():
    src = (SCRIPTS / "ton_command88_supervisor.sh").read_text(encoding="utf-8")
    assert "COMMAND89_SUCCESSOR_INSTANCE.json" in src
    assert "uuid" in src


if __name__ == "__main__":
    tests = [
        test_watchdog_has_no_popen,
        test_orch_does_not_popen_pipeline,
        test_supervisor_phase_aware_strings,
        test_transition_guard_token_required,
        test_successor_instance_schema_placeholder,
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print("PASS test_command89_exactly_once_handoff")
    (STATE / "COMMAND89_TRANSITION_GUARD_PASS").write_text("PASS\n")
    print("COMMAND89_TRANSITION_GUARD_PASS")
