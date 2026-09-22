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

"""command147 T0–T7 ComponentActuationPlan lineage (in-process physical model)."""
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from component_actuation_plan import ComponentRuntime, build_plan, closure  # noqa: E402


def test_t0_b1_only():
    rt = ComponentRuntime()
    p = build_plan(decision_seq=0, group="g0", user_target_states={"u1": "Rep1"}, currently_active=[], reason="T0")
    rt.apply(p, ["u1"])
    assert p.open_components == ["b0"]
    assert rt.publishers["b0"] and not rt.publishers["db1"]
    assert rt.payload_bytes["b0"] > 0
    assert rt.payload_bytes["db1"] == 0
    assert rt.decoded["u1"] == "Rep1"


def test_t1_b1_to_b2_db1_only():
    rt = ComponentRuntime()
    rt.apply(build_plan(decision_seq=0, group="g0", user_target_states={"u1": "Rep1"}, currently_active=[], reason="T0"), ["u1"])
    p = build_plan(decision_seq=1, group="g0", user_target_states={"u1": "Rep2"}, currently_active=rt.active, reason="T1")
    assert p.open_components == ["db1"]
    assert p.close_components == []
    b0_before = rt.payload_bytes["b0"]
    rt.apply(p, ["u1"])
    assert rt.payload_bytes["db1"] > 0
    assert rt.payload_bytes["b0"] > b0_before
    assert rt.decoded["u1"] == "Rep2"


def test_t2_b2_to_b3_db2_only():
    rt = ComponentRuntime()
    rt.apply(build_plan(decision_seq=0, group="g0", user_target_states={"u1": "Rep2"}, currently_active=[], reason="T1"), ["u1"])
    p = build_plan(decision_seq=2, group="g0", user_target_states={"u1": "Rep3"}, currently_active=rt.active, reason="T2")
    assert p.open_components == ["db2"]
    rt.apply(p, ["u1"])
    assert rt.decoded["u1"] == "Rep3"


def test_t3_b3_to_e1_only():
    rt = ComponentRuntime()
    rt.apply(build_plan(decision_seq=0, group="g0", user_target_states={"u1": "Rep3"}, currently_active=[], reason="pre"), ["u1"])
    p = build_plan(decision_seq=3, group="g0", user_target_states={"u1": "Rep8"}, currently_active=rt.active, reason="T3")
    assert p.open_components == ["e1"]
    rt.apply(p, ["u1"])
    assert rt.decoded["u1"] == "Rep8"


def test_t4_e1_to_e2_only():
    rt = ComponentRuntime()
    rt.apply(build_plan(decision_seq=0, group="g0", user_target_states={"u1": "Rep8"}, currently_active=[], reason="pre"), ["u1"])
    p = build_plan(decision_seq=4, group="g0", user_target_states={"u1": "Rep9"}, currently_active=rt.active, reason="T4")
    assert p.open_components == ["e2"]
    rt.apply(p, ["u1"])
    assert rt.decoded["u1"] == "Rep9"


def test_t5_mixed_share_e1_e2():
    rt = ComponentRuntime()
    targets = {"u1": "Rep3", "u2": "Rep8", "u3": "Rep9"}
    p = build_plan(decision_seq=5, group="g0", user_target_states=targets, currently_active=[], reason="T5")
    assert set(p.required_component_set) == {"b0", "db1", "db2", "e1", "e2"}
    assert p.component_receivers["e1"] == ["u2", "u3"]
    assert p.component_receivers["e2"] == ["u3"]
    assert "u1" not in p.component_receivers["e1"]
    rt.apply(p, ["u1", "u2", "u3"])
    assert all(rt.payload_bytes[c] == rt.payload_per_tick[c] for c in p.required_component_set)
    assert rt.client_receipt["u1"]["e1"] == 0
    assert rt.client_receipt["u2"]["e1"] > 0
    assert rt.decoded["u1"] == "Rep3"
    assert rt.decoded["u2"] == "Rep8"
    assert rt.decoded["u3"] == "Rep9"


def test_e1_shared_once_not_delivered_to_rep3():
    rt = ComponentRuntime()
    targets = {"u1": "Rep3", "u2": "Rep8"}
    p = build_plan(decision_seq=0, group="g0", user_target_states=targets, currently_active=[], reason="mix")
    assert "e1" in p.required_component_set
    assert p.component_receivers["e1"] == ["u2"]
    rt.apply(p, ["u1", "u2"])
    assert rt.publishers["e1"]
    assert rt.payload_bytes["e1"] > 0
    assert rt.client_receipt["u1"]["e1"] == 0
    assert rt.client_receipt["u2"]["e1"] > 0
    p2 = build_plan(
        decision_seq=1,
        group="g0",
        user_target_states={"u1": "Rep3", "u2": "Rep3"},
        currently_active=rt.active,
        reason="drop_e1",
    )
    assert p2.close_components == ["e1"]
    assert p2.component_receivers["e1"] == []
    rt.apply(p2, ["u1", "u2"])
    assert not rt.publishers["e1"]
    assert rt.decoded["u1"] == "Rep3"
    assert rt.decoded["u2"] == "Rep3"


def test_t6_hold_zero_unauthorized():
    rt = ComponentRuntime()
    p = build_plan(decision_seq=6, group="g0", user_target_states={"u1": "Rep3"}, currently_active=[], reason="T6")
    rt.apply(p, ["u1"])
    rt.hold()
    assert rt.payload_bytes["e1"] == 0
    assert rt.unauthorized_bytes["e1"] == 0
    assert not rt.publishers["e1"]


def test_t7_close_e2_keep_prereq():
    rt = ComponentRuntime()
    rt.apply(build_plan(decision_seq=0, group="g0", user_target_states={"u1": "Rep9"}, currently_active=[], reason="pre"), ["u1"])
    p = build_plan(decision_seq=7, group="g0", user_target_states={"u1": "Rep8"}, currently_active=rt.active, reason="T7")
    assert p.close_components == ["e2"]
    assert "b0" in p.required_component_set and "e1" in p.required_component_set
    rt.apply(p, ["u1"])
    assert not rt.publishers["e2"]
    assert rt.publishers["e1"]
    assert rt.decoded["u1"] == "Rep8"


def test_already_active_e1_zero_open():
    rt = ComponentRuntime()
    rt.apply(build_plan(decision_seq=0, group="g0", user_target_states={"u1": "Rep8"}, currently_active=[], reason="pre"), ["u1"])
    p = build_plan(
        decision_seq=8,
        group="g0",
        user_target_states={"u1": "Rep8", "u2": "Rep8"},
        currently_active=rt.active,
        reason="share_e1",
    )
    assert p.open_components == []
    assert closure("Rep8") == ["b0", "db1", "db2", "e1"]
    assert p.component_receivers["e1"] == ["u1", "u2"]


def test_wanted_components_respects_receiver_set():
    from command147_nested_client import wanted_components

    rec = {"b0": ["u1", "u2"], "db1": ["u1", "u2"], "db2": ["u1", "u2"], "e1": ["u2"], "e2": []}
    assert wanted_components("u1", "Rep3", rec) == ["b0", "db1", "db2"]
    assert "e1" not in wanted_components("u1", "Rep8", rec)
    assert wanted_components("u2", "Rep8", rec) == ["b0", "db1", "db2", "e1"]
