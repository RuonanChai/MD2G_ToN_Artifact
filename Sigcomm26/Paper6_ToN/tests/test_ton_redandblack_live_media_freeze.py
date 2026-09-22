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

"""Regression for TON_REDANDBLACK_LIVE_MEDIA_FREEZE (command87 Phase A)."""
import json
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
STATE = TON / "state"
REPO = TON.parents[1]  # Sigcomm26 -> wrong; parents[1]=Sigcomm26, need repo
REPO = artifact_root()


def test_freeze_exists_and_pass_token():
    assert (STATE / "TON_REDANDBLACK_LIVE_MEDIA_PASS").exists()
    freeze = json.loads((STATE / "TON_REDANDBLACK_LIVE_MEDIA_FREEZE.json").read_text())
    assert freeze["TON_RUNTIME_MEDIA"] == "redandblack_6_live"
    assert freeze["TON_BITRATE_REFERENCE_ONLY"] == "redandblack_6"
    assert freeze["true_content_count"] == 1
    assert freeze["n_reps"] == 9
    assert freeze["identity_class"] == "FULL_INDEPENDENT_REPS_SAME_CONTENT"
    assert freeze["representation_switch"].startswith("REPLACES")


def test_all_reps_present_and_bitrate():
    freeze = json.loads((STATE / "TON_REDANDBLACK_LIVE_MEDIA_FREEZE.json").read_text())
    assert len(freeze["reps"]) == 9
    for r in freeze["reps"]:
        assert Path(r["absolute_path"]).is_file()
        assert r["duration_s"] >= 119.0
        assert r["bitrate_delta_pct"] < 0.5
        assert "redandblack_6_live" in r["absolute_path"]
        assert "redandblack_6/" not in r["absolute_path"].replace("redandblack_6_live", "")


def test_runtime_code_points_at_live():
    src = (REPO / "moq_cluster_Sigcomm.py").read_text(encoding="utf-8")
    assert 'REDANDBLACK_6_DIR = os.path.join(VIDEO_DIR, "redandblack_6_live")' in src


def test_rep_diagnostic_not_content_split():
    diag = json.loads((STATE / "TON_REPRESENTATION_DIAGNOSTIC_SPLIT.json").read_text())
    assert "NOT_CONTENT" in diag["identity_class"]
    recon = json.loads((STATE / "COMMAND87_RECONCILIATION.json").read_text())
    assert recon["TON_CONTENT_GENERALIZATION_CLAIM_ALLOWED"] is False
    assert recon["C29_FINAL_FREEZE_PASS"] is False


def test_live_split_disjoint():
    split = json.loads((STATE / "TON_LIVE_TRAIN_DEV_SPLIT.json").read_text())
    tr = set(split["LIVE_TRAIN"]["bandwidth_trace_ids"])
    dv = set(split["LIVE_DEV"]["bandwidth_trace_ids"])
    assert not (tr & dv)
    assert not (
        set(split["LIVE_TRAIN"]["fov_participant_ids"])
        & set(split["LIVE_DEV"]["fov_participant_ids"])
    )
    assert not (set(split["LIVE_TRAIN"]["seeds"]) & set(split["LIVE_DEV"]["seeds"]))
    assert (STATE / "TON_LIVE_SPLIT_PASS").exists()


if __name__ == "__main__":
    for t in [
        test_freeze_exists_and_pass_token,
        test_all_reps_present_and_bitrate,
        test_runtime_code_points_at_live,
        test_rep_diagnostic_not_content_split,
        test_live_split_disjoint,
    ]:
        t()
        print(f"PASS {t.__name__}")
    print("PASS test_ton_redandblack_live_media_freeze")
