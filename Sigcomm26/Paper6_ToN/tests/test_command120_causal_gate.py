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

import pytest

TON = ton_root()
sys.path.insert(0, str(TON / "scripts"))

from command120_causal_gate import evaluate, paired_rows  # noqa: E402
from command120_probe_canonical import (  # noqa: E402
    exact_cell_key,
    register_canonical_valid,
    scientific_n,
    skip_if_canonical_valid,
)

NORMAL = ("4g", "default_mix", "wifi_dominant")
STRESS = ("stress_lm_8mbps", "stress_lm_12mbps")
SEEDS = (81, 82)


def _cell(arm, net, seed, **kw):
    rec = {
        "arm": arm,
        "network": net,
        "seed": seed,
        "content": "redandblack",
        "users": 20,
        "valid": True,
        "sample_role": "canonical",
        "stall_s": 1.00,
        "time_to_playable_s": 0.20,
        "weak_Rq": 0.30,
        "U_native9": 0.40,
        "Ro_native9": 0.80,
        "metric_source": "command116_Ro_native9_offline",
        "U_used_in_gate": "U_native9",
        "ttp_definition_id": "command120_ttp_v1",
        "ttp_definition_consistent": True,
        "secondary_open_fraction": 0.0,
        "active_streams_gt1_fraction": 0.0,
        "secondary_bytes": 0.0,
        "active_streams": 1.0,
        "p_streams_gt1": 0.0,
    }
    rec.update(kw)
    return rec


def _four(net, seed, *, oi_stall, gated_stall, oi_wrq=0.18, gated_wrq=0.29, oi_streams=2.2, gated_streams=1.8):
    def sec(nstream):
        alive = nstream > 1.05
        return dict(
            secondary_open_fraction=0.40 if alive else 0.0,
            active_streams_gt1_fraction=0.40 if alive else 0.0,
            p_streams_gt1=0.40 if alive else 0.0,
            secondary_bytes=5_000_000.0 if alive else 0.0,
        )
    return [
        _cell("COMMON_ONLY", net, seed, stall_s=1.00, weak_Rq=0.30, U_native9=0.40, active_streams=1.0, **sec(1.0)),
        _cell(
            "OPEN_IMMEDIATE", net, seed,
            stall_s=oi_stall, time_to_playable_s=0.80 if oi_stall > 1.2 else 0.20,
            weak_Rq=oi_wrq, U_native9=0.32 if oi_wrq < 0.25 else 0.40,
            active_streams=oi_streams, **sec(oi_streams),
        ),
        _cell(
            "OPEN_AFTER_COMMON_PLAYABLE", net, seed,
            stall_s=gated_stall, time_to_playable_s=0.25,
            weak_Rq=gated_wrq, U_native9=0.39,
            active_streams=gated_streams, **sec(gated_streams),
        ),
        _cell(
            "BUFFER_GUARDED_OPEN", net, seed,
            stall_s=max(0.2, gated_stall - 0.05), time_to_playable_s=0.22,
            weak_Rq=gated_wrq + 0.01, U_native9=0.40,
            active_streams=gated_streams, **sec(gated_streams),
        ),
    ]


def _matrix(builder):
    rows = []
    for net in list(NORMAL) + list(STRESS):
        for seed in SEEDS:
            rows.extend(builder(net, seed))
    return rows


def test_exact_key_common_only_4g_seed81():
    assert exact_cell_key("redandblack", "4g", 20, "COMMON_ONLY", 81) == (
        "redandblack/4g/users_20/probe_common_only/seed_81"
    )


def test_skip_canonical_does_not_increase_n(tmp_path, monkeypatch):
    import command120_probe_canonical as pc
    monkeypatch.setattr(pc, "REGISTRY", tmp_path / "reg.json")
    monkeypatch.setattr(pc, "log", lambda *a, **k: None)
    d = tmp_path / "cell"
    d.mkdir()
    key = exact_cell_key("redandblack", "4g", 20, "COMMON_ONLY", 81)
    done = {
        "ts": "t0", "valid": True, "arm": "COMMON_ONLY", "network": "4g", "seed": 81,
        "cell_key": key,
    }
    (d / "CELL_DONE.json").write_text(json.dumps(done))
    a = skip_if_canonical_valid(key, d)
    b = skip_if_canonical_valid(key, d)
    assert a["skipped_canonical"] is True
    assert b["scientific_n_delta"] == 0
    assert scientific_n() == 1
    d2 = tmp_path / "cell_rerun"
    d2.mkdir()
    (d2 / "CELL_DONE.json").write_text(json.dumps(done))
    register_canonical_valid(key, d2, done)
    assert scientific_n() == 1
    assert (d2 / "DUPLICATE_RECOVERY_EVIDENCE.json").exists()


def test_duplicate_row_does_not_create_eleventh_matched_key():
    rows = _matrix(lambda net, seed: _four(net, seed, oi_stall=2.0, gated_stall=1.05))
    dup = dict(rows[1])
    dup["sample_role"] = "duplicate_recovery_evidence"
    rows.append(dup)
    assert len(paired_rows(rows)) == 10
    gate = evaluate(rows, n_duplicates_ignored=1)
    assert gate["n_matched_keys"] == 10


def test_incomplete_is_not_fail():
    rows = _four("4g", 81, oi_stall=2.0, gated_stall=1.0)
    gate = evaluate(rows)
    assert gate["verdict"] == "INCOMPLETE"
    assert gate["training"] == "BLOCKED"
    assert gate["incomplete"] is True


def test_strong_pass_normal_and_stress():
    rows = _matrix(lambda net, seed: _four(net, seed, oi_stall=2.2, gated_stall=1.0, oi_wrq=0.16, gated_wrq=0.30))
    gate = evaluate(rows)
    assert gate["n_matched_keys"] == 10
    assert gate["verdict"] == "STRONG_PASS"
    assert gate["training"] == "AUTHORIZED_GEN3_TRAINING"
    assert gate["training_authorized"] is True
    h1 = gate["contrasts"]["H1"]["pooled"]["metrics"]["stall_s"]
    assert h1["mean_delta"] > 0
    assert "W" in h1["WTL"]
    assert gate["contrasts"]["H1"]["normal"]["n_keys"] == 6
    assert gate["contrasts"]["H1"]["stress"]["n_keys"] == 4


def test_conditional_pass_stress_only():
    def builder(net, seed):
        if net in STRESS:
            return _four(
                net, seed, oi_stall=2.5, gated_stall=1.05,
                oi_wrq=0.14, gated_wrq=0.28, oi_streams=2.1, gated_streams=1.7,
            )
        return _four(
            net, seed, oi_stall=0.95, gated_stall=0.96,
            oi_wrq=0.30, gated_wrq=0.30, oi_streams=1.0, gated_streams=1.0,
        )
    gate = evaluate(_matrix(builder))
    assert gate["n_matched_keys"] == 10
    assert gate["verdict"] == "CONDITIONAL_PASS"
    assert gate["training"] == "AUTHORIZED_GEN3_TRAINING"
    assert gate["training_authorized"] is True
    assert "stress" in gate["paper_claim_limit"].lower()
    assert gate["predicates"]["h1_harm_stress"] is True
    md = __import__("command120_causal_gate", fromlist=["render_md"]).render_md(gate)
    assert "## NORMAL" in md and "## STRESS" in md
    assert "## SECONDARY_STREAM_PRESERVATION" in md


def test_fail_indistinguishable_without_treatment_is_integrity_not_scientific_fail():
    rows = _matrix(
        lambda net, seed: _four(
            net, seed, oi_stall=1.00, gated_stall=1.00,
            oi_wrq=0.30, gated_wrq=0.30, oi_streams=1.0, gated_streams=1.0,
        )
    )
    gate = evaluate(rows)
    assert gate["verdict"] == "GATE_INTEGRITY_FAIL"
    assert gate["token"] == "COMMAND120_INTERVENTION_NOT_EXERCISED"
    assert gate["training_authorized"] is False
    assert gate["training"] == "BLOCKED_RELEASE_CHECKS"


def test_fail_collapse_to_common_only():
    rows = _matrix(lambda net, seed: _four(net, seed, oi_stall=2.2, gated_stall=1.0, oi_streams=2.2, gated_streams=1.0))
    gate = evaluate(rows)
    assert gate["verdict"] == "FAIL"
    assert gate["training_authorized"] is False
    assert gate["instantiation"]["buffer_guarded_streams_alive_keys"] == 0


def test_legacy_u_blocks_training_even_if_science_would_pass():
    rows = _matrix(lambda net, seed: _four(net, seed, oi_stall=2.2, gated_stall=1.0, oi_wrq=0.16, gated_wrq=0.30))
    for r in rows:
        r["U_used_in_gate"] = "U_legacy_diagnostic"
        r["metric_source"] = "runtime_twotrack"
    gate = evaluate(rows)
    assert gate["verdict"] == "GATE_INTEGRITY_FAIL"
    assert gate["training_authorized"] is False
    assert gate["training"] == "BLOCKED_RELEASE_CHECKS"


def test_h2_stall_gain_without_secondary_is_fail_not_pass():
    rows = _matrix(lambda net, seed: _four(net, seed, oi_stall=2.2, gated_stall=1.0, oi_streams=2.2, gated_streams=1.0))
    gate = evaluate(rows)
    assert gate["verdict"] == "FAIL"
    assert gate["predicates"]["h2_fake_success"] is True
    assert gate["second_family_budget"] == 1


def test_prefix_quarantine_excluded_from_paired_gate():
    rows = _matrix(lambda net, seed: _four(net, seed, oi_stall=2.2, gated_stall=1.0, oi_wrq=0.16, gated_wrq=0.30))
    for r in rows:
        r["sample_role"] = "PRE_CAPACITY_ESTIMATOR_FIX_TREATMENT_NOT_EXERCISED"
        r["valid_for_causal_gate"] = False
    assert paired_rows(rows) == []
    gate = evaluate(rows)
    assert gate["verdict"] == "INCOMPLETE"
    assert gate["training_authorized"] is False


def test_prefix_retarget_allows_repaired_canonical(tmp_path, monkeypatch):
    import command120_probe_canonical as pc
    from command120_common import PREFIX_ROLE
    monkeypatch.setattr(pc, "REGISTRY", tmp_path / "reg.json")
    monkeypatch.setattr(pc, "log", lambda *a, **k: None)
    key = exact_cell_key("redandblack", "4g", 20, "OPEN_IMMEDIATE", 81)
    old = tmp_path / "prefix"
    new = tmp_path / "c122"
    old.mkdir(); new.mkdir()
    done_p = {
        "ts": "t0", "valid": True, "arm": "OPEN_IMMEDIATE", "network": "4g", "seed": 81,
        "cell_key": key, "sample_role": PREFIX_ROLE, "command122_prefix": True,
    }
    (old / "CELL_DONE.json").write_text(json.dumps(done_p))
    pc.register_canonical_valid(key, old, done_p)
    assert scientific_n() == 0
    done_n = dict(done_p)
    done_n["sample_role"] = "canonical"
    done_n.pop("command122_prefix", None)
    (new / "CELL_DONE.json").write_text(json.dumps(done_n))
    rec = pc.register_canonical_valid(key, new, done_n)
    assert rec["sample_role"] == "canonical"
    assert rec.get("retargeted_from_prefix")
    assert scientific_n() == 1
    assert not (new / "DUPLICATE_RECOVERY_EVIDENCE.json").exists()
