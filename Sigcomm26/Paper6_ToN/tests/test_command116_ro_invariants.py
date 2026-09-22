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
"""Fail-closed invariance tests for canonical Ro_native9. No strategy U inspection."""
import json
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))

from command114_common import BR_MAP, STATE, write_json, ts  # noqa: E402
from ton_ro_native9 import paper_u_native9, ro_native9_interval  # noqa: E402


def nearly(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol


def test_a_equal_group_equal_rep():
    br = {3: 0.87}
    r = ro_native9_interval(
        selected_reps=[3] * 20,
        group_ids=[0] * 10 + [1] * 10,
        bitrates=br,
    )
    assert nearly(r["Ro_native9"], 1.0 - 2.0 / 20.0, 1e-9), r
    assert r["n_shared_streams"] == 2


def test_b_bitrate_awareness():
    # Unequal fan-out: 19 share Rep3, 1 takes a heavier vs lighter full rep.
    g = [0] * 19 + [1]
    r5 = ro_native9_interval(
        selected_reps=[3] * 19 + [5], group_ids=g, bitrates={3: 0.87, 5: 6.42, 8: 1.43},
    )
    r8 = ro_native9_interval(
        selected_reps=[3] * 19 + [8], group_ids=g, bitrates={3: 0.87, 5: 6.42, 8: 1.43},
    )
    uni5, sh5 = 19 * 0.87 + 6.42, 0.87 + 6.42
    uni8, sh8 = 19 * 0.87 + 1.43, 0.87 + 1.43
    assert nearly(r5["Ro_native9"], 1.0 - sh5 / uni5, 1e-9)
    assert nearly(r8["Ro_native9"], 1.0 - sh8 / uni8, 1e-9)
    assert r5["B_shared_equiv"] > r8["B_shared_equiv"]
    assert r5["Ro_native9"] < r8["Ro_native9"]
    # two-track would treat both as enh unicast; native must not assign equal cost
    assert not nearly(r5["Ro_native9"], r8["Ro_native9"], 1e-6)


def test_c_rename_invariance():
    br_a = {3: 0.87, 8: 1.43}
    br_b = {30: 0.87, 80: 1.43}  # renamed labels, identical bytes
    g = [0] * 10 + [1] * 10
    r1 = ro_native9_interval(selected_reps=[3] * 10 + [8] * 10, group_ids=g, bitrates=br_a)
    r2 = ro_native9_interval(selected_reps=[30] * 10 + [80] * 10, group_ids=g, bitrates=br_b)
    assert nearly(r1["Ro_native9"], r2["Ro_native9"], 1e-12)
    assert nearly(r1["B_shared_equiv"], r2["B_shared_equiv"], 1e-12)


def test_d_multi_rep_once():
    # 10 users one group: 6 on Rep3, 4 on Rep8 → 2 shared streams
    r = ro_native9_interval(
        selected_reps=[3] * 6 + [8] * 4,
        group_ids=[0] * 10,
        bitrates={3: 0.87, 8: 1.43},
    )
    uni = 6 * 0.87 + 4 * 1.43
    shared = 0.87 + 1.43
    assert r["n_shared_streams"] == 2
    assert nearly(r["Ro_native9"], 1.0 - shared / uni, 1e-9)
    assert r["Ro_native9"] > 0.5


def test_e_user_drop_cannot_improve():
    br = {3: 0.87}
    full = ro_native9_interval(selected_reps=[3] * 20, group_ids=[0] * 10 + [1] * 10, bitrates=br)
    dropped = ro_native9_interval(
        selected_reps=[3] * 20,
        group_ids=[0] * 10 + [1] * 10,
        bitrates=br,
        served_mask=[True] * 2 + [False] * 18,
    )
    # 2 served, possibly 1 or 2 groups: Ro <= 0.5 < 0.90
    assert dropped["Ro_native9"] < full["Ro_native9"]
    u_full = paper_u_native9(full["Ro_native9"], 0.5, 0.2)
    u_drop = paper_u_native9(dropped["Ro_native9"], 0.5, 0.2)
    assert u_drop <= u_full + 1e-12


def test_f_weights_frozen():
    assert nearly(paper_u_native9(1.0, 1.0, 0.0), 0.85)
    assert nearly(paper_u_native9(0.0, 0.0, 1.0), 0.0)


def test_no_enh_mechanical_penalty():
    # 20 users, 2 groups, all Rep8 (would be enh=1 in two-track)
    r = ro_native9_interval(
        selected_reps=[8] * 20,
        group_ids=[0] * 10 + [1] * 10,
        bitrates={8: 1.43, 3: 0.87},
    )
    assert nearly(r["Ro_native9"], 0.90, 1e-9), r


def main() -> int:
    tests = [
        test_a_equal_group_equal_rep,
        test_b_bitrate_awareness,
        test_c_rename_invariance,
        test_d_multi_rep_once,
        test_e_user_drop_cannot_improve,
        test_f_weights_frozen,
        test_no_enh_mechanical_penalty,
    ]
    failed = []
    for fn in tests:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception as e:
            failed.append(fn.__name__)
            print("FAIL", fn.__name__, e)
    br = json.loads(BR_MAP.read_text())
    assert "redandblack" in br and len(br["redandblack"]) == 9
    payload = {
        "ts": ts(),
        "pass": not failed,
        "n_tests": len(tests),
        "failed": failed,
        "contract": str(STATE / "COMMAND116_TON_RO_SEMANTIC_CONTRACT.json"),
        "holdout_inspected": False,
        "strategy_aggregates_inspected": False,
        "physical_tolerance_predeclared": "[0.5, 40] client_payload_delta_bits / B_shared_equiv_bits",
    }
    write_json(STATE / "COMMAND116_RO_METRIC_VALIDATION.json", payload)
    if not failed:
        (STATE / "COMMAND116_RO_METRIC_VALIDATION").write_text(f"PASS\nts={payload['ts']}\n")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
