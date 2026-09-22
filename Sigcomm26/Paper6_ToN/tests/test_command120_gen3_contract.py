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
"""Gen3 contract invariants: disjoint seeds/traces, loot sealed, G2 closed."""
import json
from pathlib import Path

TON = ton_root()
STATE = TON / "state"


def test_g0_tokens_exist():
    assert (STATE / "COMMAND120_GEN2_CLOSED").exists()
    assert (STATE / "COMMAND120_GENERATION3_CONTRACT_FROZEN").exists()
    assert (STATE / "COMMAND120_GEN2_CLOSURE.json").exists()
    assert (STATE / "COMMAND120_GENERATION3_CONTRACT.json").exists()


def test_holdout_unread_proof():
    d = json.loads((STATE / "COMMAND120_GEN2_CLOSURE.json").read_text())
    proof = d["holdout_never_inspected"]
    assert proof["pass"] is True
    assert proof["opened_soldier_or_loot_performance"] is False
    assert d["do_not_authorize_md2g_g2_v3"] is True


def test_disjoint_seeds_and_contents():
    c = json.loads((STATE / "COMMAND120_GENERATION3_CONTRACT.json").read_text())
    dev_s = set(c["DEV"]["seeds"])
    hol_s = set(c["FINAL_HOLDOUT"]["seeds"])
    assert dev_s == {81, 82, 83}
    assert hol_s == {91, 92, 93}
    assert not (dev_s & hol_s)
    assert "soldier" in c["DEV"]["contents"]
    assert "loot" in c["FINAL_HOLDOUT"]["contents"]
    assert "loot" not in c["DEV"]["contents"]
    assert 71 not in dev_s and 71 not in hol_s


def test_disjoint_trace_windows():
    c = json.loads((STATE / "COMMAND120_GENERATION3_CONTRACT.json").read_text())
    for key, part in c["trace_partitions"].items():
        assert part["dev_row_end"] == part["holdout_row_start"]
        assert part["dev_row_start"] < part["dev_row_end"]
        assert part["holdout_row_start"] < part["holdout_row_end"]
        assert part["disjoint"] is True
        assert c["DEV"]["fov_trace_ids"] or key != "fov_head_movement"


def test_hypotheses_predeclared_without_results():
    h = json.loads((STATE / "COMMAND120_PLAYABILITY_CAUSAL_HYPOTHESES.json").read_text())
    assert h["results_present"] is False
    assert "H1" in h and "H2" in h
    assert h["command119_replay"] == "not used"


def test_paper_u_frozen():
    c = json.loads((STATE / "COMMAND120_GENERATION3_CONTRACT.json").read_text())
    assert "0.25*Ro_native9" in c["paper_U"]
    assert "0.60*Rq" in c["paper_U"]
    assert "0.15*Rb" in c["paper_U"]
