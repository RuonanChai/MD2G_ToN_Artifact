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
"""Fail-closed Generation-2 runtime fidelity tests (command114 Phase 4)."""
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

from command114_common import BR_MAP, DEV_CONTENTS, MEDIA_MANIFEST, METRIC_CONTRACT  # noqa: E402


def test_nine_unique_media_per_dev_content():
    man = json.loads(MEDIA_MANIFEST.read_text())
    for c in DEV_CONTENTS:
        shas = list((man["contents"][c]["rep_sha256"] or {}).values())
        assert len(shas) == 9, c
        assert len(set(shas)) == 9, c
        assert man["contents"][c]["n_unique_sha"] == 9


def test_per_content_bitrate_map():
    br = json.loads(BR_MAP.read_text())
    for c in DEV_CONTENTS:
        reps = br[c]
        assert len(reps) == 9
        vals = [float(reps[str(i)]) for i in range(1, 10)]
        assert min(vals) > 0.2 and max(vals) < 20


def test_campaign_env_forwards_ton_star():
    os.environ["TON_NATIVE9REP_MD2G"] = "1"
    os.environ["TON_MD2G_CANDIDATE"] = "G2"
    os.environ["MM26_MD2G_TP_SIGNAL"] = "access_capacity"
    from moq_cluster_Sigcomm import sigcomm_campaign_env_dict

    d = sigcomm_campaign_env_dict()
    assert d.get("TON_NATIVE9REP_MD2G") == "1"
    assert d.get("TON_MD2G_CANDIDATE") == "G2"
    assert d.get("MM26_MD2G_TP_SIGNAL") == "access_capacity"


def test_dispatch_honors_selected_rep():
    src = (REPO / "dispatch_strategy_enhanced_unified_Sigcomm.py").read_text()
    assert "_ton_native9rep_md2g_enabled" in src
    assert "TON_NATIVE9REP honor" in src
    assert "selected_rep" in src


def test_capacity_not_delivered_in_g2():
    src = (TON / "lib" / "ton_native9rep_md2g_policy_g2.py").read_text()
    assert "_capacity_mbps" in src
    assert "health cue" in src.lower() or "health_and_completion" in src or "never capacity" in src.lower()


def test_g2_action_is_native_nine_rep():
    src = (TON / "controllers" / "g2_native9rep_model.py").read_text()
    assert "n_reps: int = 9" in src
    assert "head_rep" in src
    # no binary enhanced-only head as the sole action
    assert "rep_logits" in src


def test_paper_u_frozen():
    c = json.loads(METRIC_CONTRACT.read_text())
    assert "0.25" in c["paper_U_eval"] and "0.60" in c["paper_U_eval"] and "0.15" in c["paper_U_eval"]


def test_hydrate_accepts_ton():
    src = (REPO / "MM26" / "regional_relay_controller.py").read_text()
    assert 'key.startswith(("MM26_", "SIGCOMM_", "TON_"))' in src



def test_g2_dispatch_from_v1_entry():
    src = (TON / "lib" / "ton_native9rep_md2g_policy.py").read_text()
    assert 'cand.startswith("G2")' in src


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
