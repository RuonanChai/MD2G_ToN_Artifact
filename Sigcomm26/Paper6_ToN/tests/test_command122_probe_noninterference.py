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

# -*- coding: utf-8 -*-
"""Probe stagger/budget and command122 launch-gate fail-closed checks."""
import inspect
import json
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))

from command122_probe_noninterference import (  # noqa: E402
    load_tolerances,
    run_unit_sim,
)
from ton_playability_telemetry import (  # noqa: E402
    PROBE_MAX_CONCURRENT,
    ProbeAdmission,
    probe_slot_ok,
    try_acquire_probe,
)


def test_tolerances_predeclared_before_aggregates():
    tol, sha = load_tolerances()
    assert tol["predeclared_before_aggregate_results"] is True
    assert sha
    assert tol["links_mbps"] == [8.0, 12.0, 30.0, 40.0]
    assert tol["tolerances"]["max_concurrent_probes"] == 1
    assert PROBE_MAX_CONCURRENT == 1


def test_probe_slots_are_staggered():
    now = 0.0
    eligible = [i for i in range(20) if probe_slot_ok(i, now)]
    assert len(eligible) <= 2  # 20 clients / 10 slots


def test_global_budget_serializes():
    import tempfile
    p = Path(tempfile.mkdtemp()) / "b.json"
    adm = ProbeAdmission(path=p, max_concurrent=1)
    assert adm.try_acquire(0, 0.0) is True
    assert adm.try_acquire(10, 0.0) is False  # same slot, global budget 1


def test_burst_tick_skips_slot_after_schedule():
    """command120 dispatch interval=1.0s rotates a 0.50s slot by +2."""
    import tempfile
    p = Path(tempfile.mkdtemp()) / "b.json"
    adm = ProbeAdmission(path=p, max_concurrent=1)
    assert probe_slot_ok(0, 0.0) is True
    assert probe_slot_ok(0, 1.0) is False
    assert adm.try_acquire(0, 1.0, require_slot=True) is False
    assert adm.try_acquire(0, 1.0, require_slot=False) is True
    src = Path(
        "str(artifact_root())"
        "/dispatch_strategy_enhanced_unified_Sigcomm.py"
    ).read_text()
    assert "require_slot=False" in src
    assert "require_slot" in inspect.getsource(try_acquire_probe)


def test_schedule_ignores_probe_arm_env(monkeypatch):
    monkeypatch.setenv("TON_GEN3_PROBE_ARM", "OPEN_IMMEDIATE")
    assert "os.environ" not in inspect.getsource(probe_slot_ok)
    assert "os.environ" not in inspect.getsource(ProbeAdmission.try_acquire)
    assert probe_slot_ok(0, 0.0) is True


def test_scientific_schedule_meets_predeclared_tolerances():
    tol, _ = load_tolerances()
    unit = run_unit_sim(tol)
    assert unit["pass"], json.dumps(unit, indent=2)[:2000]
    # Unsync is diagnostic: may violate peak/overlap; must not be the pass schedule.
    peaks = [r["peak_aggregate_probe_mbps"] for r in unit["unsync_diagnostic_only"]]
    assert unit["pass_schedule"] != "unsynchronized 20-way burst"


def test_certified_token_is_not_sufficient_for_launch(tmp_path, monkeypatch):
    import command120_common as c

    monkeypatch.setattr(c, "STATE", tmp_path)
    (tmp_path / "COMMAND122_CAPACITY_ESTIMATOR_CERTIFIED").write_text("nope\n")
    (tmp_path / "COMMAND122_CAUSAL_TREATMENTS_ACTUATED").write_text("x\n")
    (tmp_path / "COMMAND122_CAUSAL_RELAUNCH_GATE.json").write_text('{"pass": true}\n')
    assert c.scientific_causal_launch_allowed() is False
    (tmp_path / "COMMAND122_CAUSAL_FEASIBILITY_ESTIMATOR").write_text("x\n")
    (tmp_path / "COMMAND122_PROBE_NONINTERFERENCE_PASS").write_text("x\n")
    (tmp_path / "COMMAND123_PHYSICAL_ACTUATION_PREFLIGHT_PASS").write_text("x\n")
    (tmp_path / "CELL_SCOPED_NETWORK_CLEANUP_PASS").write_text("x\n")
    (tmp_path / "COMMAND123_C6_RESTART_GATE.json").write_text('{"pass": true}\n')
    assert c.scientific_causal_launch_allowed() is True
    (tmp_path / "COMMAND122_PAUSE_NEW_LAUNCHES").write_text("pause\n")
    assert c.scientific_causal_launch_allowed() is False
