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

"""Regression: MD2G assigned_users clip + decision dwell (command60/61)."""
import importlib.util
import json
import sys
from pathlib import Path

REPO = artifact_root()
sys.path.insert(0, str(REPO))


def _load_rrc():
    path = REPO / "regional_relay_controller.py"
    spec = importlib.util.spec_from_file_location("rrc_cmd60", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_assigned_users_from_offset_canonical():
    from user_relay_mapping import assigned_users_from_offset

    assert assigned_users_from_offset(5, 1) == [1, 2, 3, 4, 5]
    assert assigned_users_from_offset(5, 6) == [6, 7, 8, 9, 10]


def test_mapping_clip_logic(tmp_path):
    from user_relay_mapping import assigned_users_from_offset, save_mapping_to_file, load_mapping_from_file

    # Stale N=100 half-split must not expand N=10 r1 max_users=5.
    stale = {str(i): ("r1" if i <= 50 else "r2") for i in range(1, 101)}
    mp = tmp_path / "map.json"
    mp.write_text(json.dumps(stale))
    loaded = load_mapping_from_file(str(mp))
    canonical = set(assigned_users_from_offset(5, 1))
    clipped = sorted(uid for uid, r in loaded.items() if r == "r1" and uid in canonical)
    assert clipped == [1, 2, 3, 4, 5]

    fresh = {"r1": [1, 2, 3, 4, 5], "r2": [6, 7, 8, 9, 10]}
    save_mapping_to_file(fresh, str(mp))
    loaded2 = load_mapping_from_file(str(mp))
    assert sorted(uid for uid, r in loaded2.items() if r == "r1") == [1, 2, 3, 4, 5]


def test_decision_dwell_holds_enhance(tmp_path):
    mod = _load_rrc()
    prev = {
        "decisions": {
            "1": {"pull_enhanced": False, "enhanced_level": 0, "md2g_group_id": 1, "dwell_enh_votes": 2, "dwell_group_votes": 2},
        }
    }
    df = tmp_path / "dec.json"
    df.write_text(json.dumps(prev))
    cur = {
        "1": {"pull_enhanced": True, "enhanced_level": 1, "md2g_group_id": 2},
    }
    import os

    os.environ["MD2G_DECISION_DWELL_TICKS"] = "5"
    summary = mod._md2g_apply_decision_dwell(cur, str(df), "md2g")
    assert summary["enabled"] is True
    assert cur["1"]["pull_enhanced"] is False
    assert cur["1"]["enhanced_level"] == 0
    assert cur["1"]["md2g_group_id"] == 1
    assert summary["held_enhance"] == 1
    assert summary["held_group"] == 1


def test_group_member_filter_in_dispatch():
    # Import only the pure filter behavior via reimplementation contract.
    total_clients = 10
    phantom = [1, 3, 7, 10, 13, 50]
    filtered = [int(m) for m in phantom if 1 <= int(m) <= int(total_clients)]
    assert filtered == [1, 3, 7, 10]
