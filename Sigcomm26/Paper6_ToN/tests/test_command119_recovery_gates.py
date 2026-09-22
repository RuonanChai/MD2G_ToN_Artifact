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

"""Regression: command119 recovery artifacts exist and do not authorize G2-v3 by default."""
import json
from pathlib import Path

TON = ton_root()


def test_classification_not_fundamental():
    d = json.loads((TON / "analysis/COMMAND119_M2_BLOCK_CLASSIFICATION.json").read_text())
    assert d["continue_recovery"] is True
    assert "FUNDAMENTAL_NO_HEADROOM" in d["summary_classes_absent"]
    assert d["g2v3_authorized"] is False


def test_headroom_gate_was_predeclared():
    d = json.loads((TON / "state/COMMAND119_PLAYABILITY_HEADROOM_GATE.json").read_text())
    assert d["predeclared_before_aggregate_replay"] is True
    assert d["thresholds_from_prior_DEV_only"]["predicted_delta_U_vs_repagg_min"] == 0.02


def test_no_g2v3_token_without_recovered_gate():
    assert not (TON / "state/COMMAND119_G2V3_AUTHORIZED").exists()
    g = json.loads((TON / "state/COMMAND119_RECOVERED_M2_GATE.json").read_text())
    assert g["authorized"] is False
    h = json.loads((TON / "state/COMMAND119_PLAYABILITY_HEADROOM_GATE.json").read_text())
    assert h["predeclared_before_aggregate_replay"] is True
    assert h["result"] == "FAIL"


def test_salvage_not_whole_target_unsupported():
    s = json.loads((TON / "analysis/COMMAND119_CLAIM_SALVAGE.json").read_text())
    assert s["TARGET_CLAIM_NOT_SCIENTIFICALLY_SUPPORTED"] is False
    assert s["all_three_agree_defensible_contribution"] is True
    assert not (TON / "state/TARGET_CLAIM_NOT_SCIENTIFICALLY_SUPPORTED").exists()
    d = json.loads((TON / "analysis/COMMAND119_COMPLETION_MECHANISM_DIFF.json").read_text())
    assert d["classification"] == "MECHANISM_ONLY_DECLARED_BUT_NOT_INSTANTIATED"
