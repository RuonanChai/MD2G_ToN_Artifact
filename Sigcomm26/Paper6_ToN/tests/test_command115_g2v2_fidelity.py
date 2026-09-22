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
"""Fail-closed G2-v2 grouping/runtime fidelity (command115 Phase 4)."""
import ast
import json
import os
import sys
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))

from command114_common import BR_MAP, MEDIA_MANIFEST, METRIC_CONTRACT  # noqa: E402


def test_g2v1_not_overwritten():
    src = (TON / "lib" / "ton_native9rep_md2g_policy_g2.py").read_text()
    assert "g2_native9rep_two_timescale" in src
    assert "g2_v2_group_anchor_native9rep" in src
    assert 'cand.startswith("G2")' in (TON / "lib" / "ton_native9rep_md2g_policy.py").read_text()


def test_g2v2_grouping_module_exists():
    from ton_g2v2_grouping import (
        dispatch_group_assignments,
        group_by_reuse_preserving_fov,
        grouping_mode,
    )
    os.environ["TON_MD2G_CANDIDATE"] = "G2_V2"
    os.environ["TON_G2_GROUPING"] = "REUSE_V2"
    assert grouping_mode() == "G2_V2"
    import numpy as np
    fs = np.array([0.1, 0.12, 0.9, 0.92, 0.11, 0.88])
    ds = np.linspace(0.2, 0.9, 6)
    bw = np.linspace(2, 40, 6)
    g = group_by_reuse_preserving_fov(ds, bw, fs, num_groups=3)
    assert len(set(int(x) for x in g.tolist())) >= 2
    os.environ["TON_MD2G_CANDIDATE"] = "G2"
    os.environ["TON_G2_GROUPING"] = "HV3"
    assert grouping_mode() == "HV3_DIAG"
    alt = dispatch_group_assignments(ds, bw, fs, num_groups=3)
    assert alt is not None


def test_controller_dispatches_grouping():
    src = (REPO / "MM26" / "regional_relay_controller.py").read_text()
    assert "dispatch_group_assignments" in src
    assert "TON_G2_GROUPING" in src


def test_native9_ro_gated():
    src = (REPO / "dispatch_strategy_enhanced_unified_Sigcomm.py").read_text()
    assert "calculate_native9_multicast_saving" in src
    assert "TON_NATIVE9REP_RO" in src
    tree = ast.parse(src)
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "calculate_native9_multicast_saving" in names
    assert "calculate_multicast_saving" in names


def test_cell_runner_identities():
    from command114_cell_runner import CLI, strategy_env

    assert CLI["md2g_g2_v2"] == "md2g"
    assert CLI["g2_diag_hv3group"] == "md2g"
    e2 = strategy_env("md2g_g2_v2", "redandblack", 20, 51)
    assert e2["TON_MD2G_CANDIDATE"] == "G2_V2"
    assert e2["TON_G2_GROUPING"] == "REUSE_V2"
    assert e2["TON_NATIVE9REP_RO"] == "1"
    assert e2["MM26_MD2G_TP_SIGNAL"] == "access_capacity"
    ed = strategy_env("g2_diag_hv3group", "redandblack", 20, 51)
    assert ed["TON_G2_GROUPING"] == "HV3"
    assert ed["TON_NATIVE9REP_RO"] == "0"
    assert ed["TON_MD2G_CANDIDATE"] == "G2"
    e1 = strategy_env("md2g_g2", "redandblack", 20, 51)
    assert e1["TON_MD2G_CANDIDATE"] == "G2"
    assert e1.get("TON_G2_GROUPING") in (None, "", "LEGACY_UTILITY")


def test_selected_rep_still_honored():
    src = (REPO / "dispatch_strategy_enhanced_unified_Sigcomm.py").read_text()
    assert "TON_NATIVE9REP honor" in src
    assert "selected_rep" in src


def test_hashes_unchanged():
    man = json.loads(MEDIA_MANIFEST.read_text())
    br = json.loads(BR_MAP.read_text())
    c = json.loads(METRIC_CONTRACT.read_text())
    assert man["contents"]["redandblack"]["n_unique_sha"] == 9
    assert "0.25" in c["paper_U_eval"]
    assert len(br["redandblack"]) == 9


def test_campaign_forwards_g2v2_env():
    os.environ["TON_MD2G_CANDIDATE"] = "G2_V2"
    os.environ["TON_G2_GROUPING"] = "REUSE_V2"
    os.environ["TON_NATIVE9REP_RO"] = "1"
    os.environ["TON_NATIVE9REP_MD2G"] = "1"
    from moq_cluster_Sigcomm import sigcomm_campaign_env_dict

    d = sigcomm_campaign_env_dict()
    assert d.get("TON_MD2G_CANDIDATE") == "G2_V2"
    assert d.get("TON_G2_GROUPING") == "REUSE_V2"
    assert d.get("TON_NATIVE9REP_RO") == "1"


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
    if failed:
        raise SystemExit(1)
    print("ALL_PASS", len(tests))
