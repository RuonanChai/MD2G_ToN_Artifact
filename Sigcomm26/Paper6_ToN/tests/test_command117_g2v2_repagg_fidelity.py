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
"""Fail-closed command117 md2g_g2_v2_repagg fidelity / cost-accounting tests."""
import json
import os
import sys
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))

from command114_cell_runner import CLI, strategy_env  # noqa: E402
from command114_common import BR_MAP, METRIC_CONTRACT, MODEL_DIR, STATE, sha256_file  # noqa: E402
from ton_native9rep_md2g_policy_g2_repagg import (  # noqa: E402
    apply_native9rep_policy_g2_repagg,
    full_stream_open_cost,
    replace_stream_delta_cost,
)
from ton_ro_native9 import ro_native9_interval  # noqa: E402


def _env_repagg():
    os.environ["TON_NATIVE9REP_MD2G"] = "1"
    os.environ["TON_MD2G_CANDIDATE"] = "G2_V2_REPAGG"
    os.environ["TON_G2_USE_NEURAL"] = "0"
    os.environ.pop("TON_G2_GROUPING", None)
    os.environ.pop("TON_NATIVE9REP_RO", None)
    os.environ["TON_CONTENT_ID"] = "redandblack"


def _user(uid, *, gid, device, cap, rep=3, buf=5.0):
    return {
        "user_id": uid,
        "md2g_group_id": gid,
        "grouping_id": gid,
        "device_score": device,
        "access_capacity_mbps": cap,
        "throughput_mbps": cap,
        "selected_rep": rep,
        "rep_id": rep,
        "base_version": 3,
        "enhanced_level": 0,
        "buffer_level_sec": buf,
        "stall_sec": 0.0,
    }


def test_identity_and_dispatch_order():
    src = (TON / "lib" / "ton_native9rep_md2g_policy.py").read_text()
    assert src.find("G2_V2_REPAGG") < src.find('cand.startswith("G2")')
    assert CLI["md2g_g2_v2_repagg"] == "md2g"
    e = strategy_env("md2g_g2_v2_repagg", "redandblack", 20, 51)
    assert e["TON_MD2G_CANDIDATE"] == "G2_V2_REPAGG"
    assert e.get("TON_G2_GROUPING") in (None, "")
    assert e.get("TON_NATIVE9REP_RO") in (None, "", "0")
    assert e["TON_G2_USE_NEURAL"] == "1"
    student = Path(e["TON_G2_STUDENT_PATH"])
    assert student.is_file()
    e_v2 = strategy_env("md2g_g2_v2", "redandblack", 20, 51)
    assert e_v2["TON_MD2G_CANDIDATE"] == "G2_V2"
    e_g2 = strategy_env("md2g_g2", "redandblack", 20, 51)
    assert e_g2["TON_MD2G_CANDIDATE"] == "G2"


def test_student_sha_present():
    p = MODEL_DIR / "g2_student_v1.pt"
    assert p.is_file()
    assert sha256_file(p)


def test_a_second_full_stream_charges_full_bytes():
    rates = {3: 0.87, 8: 1.43, 5: 6.42}
    cost = full_stream_open_cost({3}, 8, rates)
    assert abs(cost - 1.43) < 1e-12, cost
    cost5 = full_stream_open_cost({3}, 5, rates)
    assert abs(cost5 - 6.42) < 1e-12
    # already active → 0
    assert full_stream_open_cost({3, 8}, 8, rates) == 0.0


def test_b_replace_charges_delta_only():
    rates = {3: 0.87, 8: 1.43}
    d = replace_stream_delta_cost(3, 8, rates)
    assert abs(d - (1.43 - 0.87)) < 1e-12, d


def test_c_same_rep_one_shared_stream():
    r = ro_native9_interval(
        selected_reps=[8, 8], group_ids=[1, 1], bitrates={8: 1.43},
    )
    assert r["n_shared_streams"] == 1
    assert abs(r["B_shared_equiv"] - 1.43) < 1e-12


def test_d_rename_invariance():
    r1 = ro_native9_interval(selected_reps=[3, 8], group_ids=[0, 0], bitrates={3: 0.87, 8: 1.43})
    r2 = ro_native9_interval(selected_reps=[30, 80], group_ids=[0, 0], bitrates={30: 0.87, 80: 1.43})
    assert abs(r1["Ro_native9"] - r2["Ro_native9"]) < 1e-12
    assert abs(r1["B_shared_equiv"] - r2["B_shared_equiv"]) < 1e-12


def test_e_weak_user_protection_rejects_harmful_upgrade():
    _env_repagg()
    os.environ["TON_G2_REPAGG_MAX_EXTRA"] = "1"
    os.environ["TON_G2_REPAGG_WEAK_DEVICE"] = "0.50"
    from ton_native9rep_md2g_policy_g2_repagg import _LAST
    _LAST.clear()
    decisions = {
        "w": _user("w", gid=1, device=0.05, cap=30.0, rep=3, buf=6.0),
        "s": _user("s", gid=1, device=0.95, cap=40.0, rep=5, buf=6.0),
    }
    out = apply_native9rep_policy_g2_repagg(decisions, content="redandblack", util=0.2)
    assert out["applied"]
    weak_rep = int(decisions["w"]["selected_rep"])
    # weak user must remain on a feasible anchor, not a high-device-only stream
    from ton_native9rep_md2g_policy_v2 import _device_need
    assert 0.05 + 1e-9 >= _device_need(weak_rep)
    assert weak_rep in (3, 8, 9, 2)
    assert decisions["w"].get("ton_g2_neural_proposal") is not None
    assert decisions["w"].get("ton_g2_projected_rep") == weak_rep


def test_f_all_clients_remain_served():
    _env_repagg()
    from ton_native9rep_md2g_policy_g2_repagg import _LAST
    _LAST.clear()
    decisions = {str(i): _user(str(i), gid=1 if i <= 10 else 2, device=0.2 + 0.05 * i, cap=25.0) for i in range(1, 21)}
    out = apply_native9rep_policy_g2_repagg(decisions, content="redandblack")
    assert out["n_users"] == 20
    for d in decisions.values():
        rid = int(d["selected_rep"])
        assert 1 <= rid <= 9
        assert d["ton_native9rep_policy"] == "g2_v2_repagg_projection"


def test_grouping_not_rewritten():
    _env_repagg()
    from ton_native9rep_md2g_policy_g2_repagg import _LAST
    _LAST.clear()
    decisions = {
        "a": _user("a", gid=7, device=0.8, cap=30.0),
        "b": _user("b", gid=7, device=0.7, cap=30.0),
    }
    apply_native9rep_policy_g2_repagg(decisions, content="redandblack")
    assert decisions["a"]["md2g_group_id"] == 7
    assert decisions["b"]["grouping_id"] == 7


def test_no_strategy_specific_ro_and_weights_frozen():
    e = strategy_env("md2g_g2_v2_repagg", "redandblack", 20, 51)
    assert e.get("TON_NATIVE9REP_RO") in (None, "", "0")
    c = json.loads(METRIC_CONTRACT.read_text())
    assert "0.25" in c["paper_U_eval"] and "0.60" in c["paper_U_eval"] and "0.15" in c["paper_U_eval"]
    br = json.loads(BR_MAP.read_text())["redandblack"]
    assert len(br) == 9


def test_entry_dispatch_repagg():
    _env_repagg()
    from ton_native9rep_md2g_policy import apply_native9rep_policy
    from ton_native9rep_md2g_policy_g2_repagg import _LAST
    _LAST.clear()
    decisions = {"a": _user("a", gid=1, device=0.6, cap=20.0)}
    out = apply_native9rep_policy(decisions, content="redandblack")
    assert out.get("version") == "G2_V2_REPAGG"
    assert decisions["a"]["ton_native9rep_policy"] == "g2_v2_repagg_projection"


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = []
    for fn in tests:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception as e:
            failed.append(fn.__name__)
            print("FAIL", fn.__name__, e)
            traceback.print_exc()
    sys.exit(1 if failed else 0)
