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
import json
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "scripts"))

from command120_event_ttp_sanity import (  # noqa: E402
    INSUFFICIENT,
    classify_sanity,
    event_ttp_cell,
    event_ttp_host,
)
from command120_40_40_dossier import (  # noqa: E402
    branch,
    event_block,
    render_md,
    release_check,
)
from command120_causal_gate import evaluate  # noqa: E402
from test_command120_causal_gate import _matrix, _four  # noqa: E402


def test_campaign_style_jsonl_is_insufficient_lineage(tmp_path: Path):
    p = tmp_path / "playability_h1.jsonl"
    rows = [
        {
            "t": 100.0 + i,
            "playable_ahead_sec": 0.0 if i < 3 else 1.2,
            "stall_active": i < 2,
            "time_to_playable_s": 1.0 if i < 3 else 0.0,
            "active_rep": 3,
            "group_id": 1,
            "active_group_rep_streams": [[1, 3]],
        }
        for i in range(8)
    ]
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    rec = event_ttp_cell(tmp_path)
    assert rec["event_ttp_s"] is None
    assert rec["lineage"] == INSUFFICIENT


def test_matching_identity_joins():
    rows = [
        {"stream_open_ts": 10.0, "opened_rep": 5, "opened_object_id": "g1o2", "opened_group_id": 1},
        {"first_playable_ts": 12.5, "playable_rep": 5, "playable_object_id": "g1o2", "playable_group_id": 1},
    ]
    rec = event_ttp_host(rows)
    assert rec["lineage"] == "joined"
    assert abs(rec["event_ttp_s"] - 2.5) < 1e-9


def test_mismatched_object_is_insufficient():
    rows = [
        {"stream_open_ts": 10.0, "opened_rep": 5, "opened_object_id": "g1o2", "opened_group_id": 1},
        {"first_playable_ts": 12.5, "playable_rep": 5, "playable_object_id": "g1o9", "playable_group_id": 1},
    ]
    rec = event_ttp_host(rows)
    assert rec["event_ttp_s"] is None
    assert rec["lineage"] == INSUFFICIENT


def test_timestamps_without_identity_are_insufficient():
    rows = [
        {"stream_open_ts": 10.0},
        {"first_playable_ts": 12.5},
        {"t": 10.0, "playable_ahead_sec": 1.2, "active_group_rep_streams": [[1, 3]]},
    ]
    rec = event_ttp_host(rows)
    assert rec["lineage"] == INSUFFICIENT


def test_classify_zero_joined_is_insufficient():
    s = classify_sanity(0, 40, [])
    assert s["verdict"] == INSUFFICIENT


def test_event_ttp_does_not_change_gate_verdict():
    rows = _matrix(lambda net, seed: _four(net, seed, oi_stall=2.2, gated_stall=1.0, oi_wrq=0.16, gated_wrq=0.30))
    gate = evaluate(rows)
    before = gate["verdict"]
    s = classify_sanity(0, 40, [])
    assert s["verdict"] == INSUFFICIENT
    assert evaluate(rows)["verdict"] == before


def test_dossier_has_eight_sections_and_insufficient_event_ttp():
    rows = _matrix(lambda net, seed: _four(net, seed, oi_stall=2.2, gated_stall=1.0, oi_wrq=0.16, gated_wrq=0.30))
    gate = evaluate(rows)
    ev = {
        "n_cells_with_event_ttp": 0,
        "n_cells_inspected": 40,
        "sanity": {"verdict": INSUFFICIENT, "note": "no join"},
        "paired_event_deltas": [],
    }
    blk = event_block(ev, gate)
    assert blk["verdict"] == INSUFFICIENT
    assert blk["used_by_causal_gate"] is False
    rel = release_check(gate)
    body = {
        "ts": "t",
        "item_1_gate_json": "GATE",
        "item_2_probe_table_md": "TABLE",
        "verdict": gate["verdict"],
        "token": gate["token"],
        "training": gate["training"],
        "training_authorized": gate["training_authorized"],
        "paper_claim_limit": gate.get("paper_claim_limit"),
        "next_action": gate.get("next_action"),
        "NORMAL": {"H1": {}, "H2a": {}, "H2b": {}},
        "STRESS": {"H1": {}, "H2a": {}, "H2b": {}},
        "four_arm_absolute": {"NORMAL": {}, "STRESS": {}, "pooled": {}},
        "treatment_strength": {"NORMAL": {}, "STRESS": {}},
        "event_ttp_sanity": blk,
        "release_check": rel,
        "branch": branch(gate, {**rel, "matrix_integrity_all_pass": True}),
        "event_ttp_does_not_affect_causal_gate": True,
    }
    md = render_md(body)
    for heading in (
        "## 1. COMMAND120_PLAYABILITY_CAUSAL_GATE.json",
        "## 2. COMMAND120_CAUSAL_PROBE_TABLE.md",
        "## 3. NORMAL",
        "## 4. STRESS",
        "## 5. ",
        "## 6. treatment-strength",
        "## 7. event-TTP sanity",
        "## 8. release-check",
    ):
        assert heading in md
    assert "INSUFFICIENT_EVENT_LINEAGE" in md
    assert body["event_ttp_does_not_affect_causal_gate"] is True
    assert body["branch"]["decision"] in (
        "ENTER_GEN3_TEACHER_STUDENT",
        "CONDITIONAL_TRAINING_STRESS_MECHANISM_ONLY",
        "LAST_SECOND_FAMILY_PROBE",
        "REPAIR_EVIDENCE_NO_SECOND_FAMILY",
        "WAIT_MATRIX",
    )


def test_integrity_fail_does_not_spend_second_family():
    b = branch(
        {"verdict": "GATE_INTEGRITY_FAIL", "training_authorized": False},
        {"matrix_integrity_all_pass": False},
    )
    assert b["train"] is False
    assert b["decision"] == "REPAIR_EVIDENCE_NO_SECOND_FAMILY"
