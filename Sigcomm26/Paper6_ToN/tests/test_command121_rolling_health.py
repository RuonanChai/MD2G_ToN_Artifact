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
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "scripts"))

from command121_rolling_health import (  # noqa: E402
    answers_16, classify_round, overlay_c6_authorized_hashes,
)


def _cell(arm, *, streams=1.0, sec=0.0, exercised=False, buf_ok=True, probe_conc=1):
    return {
        "cell_done_valid": True,
        "users": 20,
        "fov_sha256": "abc",
        "integrity_ok": True,
        "integrity_fail": [],
        "metrics": {
            "U_native9": 0.4, "Ro_native9": 0.8, "Rq": 0.3, "weak_Rq": 0.2,
            "stall_s": 0.5, "readiness_v1": 0.2, "B_shared": 100.0, "B_unicast": 120.0,
            "active_streams": streams, "secondary_open_fraction": sec,
            "active_streams_gt1_fraction": sec, "secondary_bytes": 1e6 if (sec or exercised) else 0.0,
            "served_ratio": 1.0,
        },
        "controller": {
            "treatment_exercised": exercised,
            "secondary_open_fraction": 0.4 if exercised else 0.0,
            "active_streams_gt1_fraction": 0.4 if exercised else 0.0,
            "post_warmup_reason_counts": {"P1_OPEN_IMMEDIATE": 10} if exercised else {"COMMON_ONLY": 10},
            "actuation_source": "probe_controller_audit.active_streams",
        },
        "playability": {
            "telemetry_present": True, "n_hosts_constant_buffer": 0,
            "n_forbidden_mean_buf_5": 0 if buf_ok else 3,
        },
        "probe_windows": {
            "max_concurrent_probes": probe_conc,
            "overlap_fraction": 0.0 if probe_conc <= 1 else 0.2,
            "interference_violations": (
                [] if probe_conc <= 1 else [f"probe_max_concurrent={probe_conc}>1"]
            ),
        },
    }


def test_intervention_not_exercised_is_integrity_pause():
    cells = {a: _cell(a, streams=1.0, sec=0.0, exercised=False) for a in (
        "COMMON_ONLY", "OPEN_IMMEDIATE", "OPEN_AFTER_COMMON_PLAYABLE", "BUFFER_GUARDED_OPEN"
    )}
    rnd = classify_round("4g", 81, cells, {}, {"file_sha256": {}})
    assert rnd["verdict"] == "INTEGRITY_FAIL_PAUSE"
    assert "INTERVENTION_NOT_EXERCISED" in rnd["integrity_fail"]


def test_controller_audit_not_playability_streams():
    """Client jsonl stream-pair length must not decide OPEN_IMMEDIATE actuation."""
    cells = {a: _cell(a, streams=1.0, sec=0.0, exercised=(a == "OPEN_IMMEDIATE")) for a in (
        "COMMON_ONLY", "OPEN_IMMEDIATE", "OPEN_AFTER_COMMON_PLAYABLE", "BUFFER_GUARDED_OPEN"
    )}
    rnd = classify_round("4g", 81, cells, {}, {"file_sha256": {}})
    assert "INTERVENTION_NOT_EXERCISED" not in (rnd.get("integrity_fail") or [])
    assert rnd["OPEN_IMMEDIATE_treatment_exercised"] is True
    assert rnd["verdict"] in ("HEALTHY_CONTINUE", "VALID_UNFAVORABLE_CONTINUE")


def test_probe_overlap_is_implementation_anomaly():
    cells = {a: _cell(a, exercised=(a == "OPEN_IMMEDIATE"), probe_conc=2) for a in (
        "COMMON_ONLY", "OPEN_IMMEDIATE", "OPEN_AFTER_COMMON_PLAYABLE", "BUFFER_GUARDED_OPEN"
    )}
    rnd = classify_round("4g", 81, cells, {}, {"file_sha256": {}})
    assert rnd["verdict"] == "IMPLEMENTATION_ANOMALY_PAUSE"
    assert any("probe_max_concurrent" in x or "probe_overlap" in x for x in rnd["implementation_anomaly"])


def test_incomplete_wait():
    cells = {"COMMON_ONLY": _cell("COMMON_ONLY"), "OPEN_IMMEDIATE": None,
             "OPEN_AFTER_COMMON_PLAYABLE": None, "BUFFER_GUARDED_OPEN": None}
    rnd = classify_round("wifi_dominant", 81, cells, {}, {"file_sha256": {}})
    assert rnd["verdict"] == "INCOMPLETE_WAIT"


def test_c6_telemetry_hash_not_pre40_drift_pause():
    pre40 = "acde28c106d2dc61a1d90b5ae27941932614c4ecad47e783cf55950a82328389"
    c6 = "c8e9381a174f5333674c45084ddf04feb1433381bbc5e499b959ba4e4e02d51c"
    baseline = overlay_c6_authorized_hashes({"file_sha256": {"ton_playability_telemetry": pre40}})
    assert baseline["file_sha256"]["ton_playability_telemetry"] == c6
    cells = {a: _cell(a, exercised=(a == "OPEN_IMMEDIATE")) for a in (
        "COMMON_ONLY", "OPEN_IMMEDIATE", "OPEN_AFTER_COMMON_PLAYABLE", "BUFFER_GUARDED_OPEN"
    )}
    rnd = classify_round("4g", 81, cells, {"ton_playability_telemetry": c6}, baseline)
    assert not any(str(x).startswith("hash_drift") for x in (rnd.get("integrity_fail") or []))
    assert rnd["verdict"] in ("HEALTHY_CONTINUE", "VALID_UNFAVORABLE_CONTINUE")


def test_answers_flag_waste_when_no_secondary():
    rounds = [classify_round("4g", 81, {
        a: _cell(a, exercised=False) for a in (
            "COMMON_ONLY", "OPEN_IMMEDIATE", "OPEN_AFTER_COMMON_PLAYABLE", "BUFFER_GUARDED_OPEN"
        )
    }, {}, {"file_sha256": {}})]
    ans = answers_16(rounds, 16)
    assert ans["2_OPEN_IMMEDIATE_opens_secondary"] is False
    assert ans["6_remaining_cells_wasteful_due_to_runtime_defect"] is True
    assert ans["1_interventions_behave_differently"] is False


def test_open_without_physical_payload_is_integrity_pause():
    cells = {a: _cell(a, exercised=(a == "OPEN_IMMEDIATE"), sec=0.0) for a in (
        "COMMON_ONLY", "OPEN_IMMEDIATE", "OPEN_AFTER_COMMON_PLAYABLE", "BUFFER_GUARDED_OPEN"
    )}
    cells["OPEN_IMMEDIATE"]["metrics"]["secondary_bytes"] = 0.0
    rnd = classify_round("4g", 81, cells, {}, {"file_sha256": {}})
    assert rnd["verdict"] == "INTEGRITY_FAIL_PAUSE"
    assert "OPEN_WITHOUT_PHYSICAL_PAYLOAD" in rnd["integrity_fail"]


def test_hold_leak_is_integrity_pause():
    cells = {a: _cell(a, exercised=(a == "OPEN_IMMEDIATE"), sec=0.4 if a == "OPEN_IMMEDIATE" else 0.0) for a in (
        "COMMON_ONLY", "OPEN_IMMEDIATE", "OPEN_AFTER_COMMON_PLAYABLE", "BUFFER_GUARDED_OPEN"
    )}
    cells["BUFFER_GUARDED_OPEN"]["metrics"]["secondary_bytes"] = 9e6
    cells["BUFFER_GUARDED_OPEN"]["controller"]["secondary_open_fraction"] = 0.0
    cells["BUFFER_GUARDED_OPEN"]["controller"]["treatment_exercised"] = False
    rnd = classify_round("4g", 81, cells, {}, {"file_sha256": {}})
    assert rnd["verdict"] == "INTEGRITY_FAIL_PAUSE"
    assert any("HOLD_LEAKED_UNAUTHORIZED_PAYLOAD" in x for x in rnd["integrity_fail"])


def test_level1_single_cell_is_not_science():
    from command121_three_level import level1_verdict
    l1 = level1_verdict({
        "exact_key": "redandblack/4g/users_20/probe_common_only/seed_81",
        "arm": "COMMON_ONLY",
        "integrity_fail": [],
        "level1_anomalies": [],
        "metrics": {"U_native9": 0.2, "stall_s": 5.0},
    })
    assert l1["verdict"] == "CELL_SANITY_PASS"
    assert l1["scientific_interpretation"] == "NOT_APPLICABLE_SINGLE_CELL"
    assert l1["do_not_tune"] is True
    assert l1["not_final_causal_gate"] is True


def test_level1_open_without_payload_pauses_before_next_cell():
    from command121_three_level import level1_verdict
    l1 = level1_verdict({
        "arm": "OPEN_IMMEDIATE",
        "integrity_fail": ["OPEN_WITHOUT_PHYSICAL_PAYLOAD"],
        "level1_anomalies": [],
    })
    assert l1["verdict"] == "INTEGRITY_FAIL_PAUSE"


def test_level1_hold_leak_pauses():
    from command121_three_level import level1_verdict
    l1 = level1_verdict({
        "arm": "BUFFER_GUARDED_OPEN",
        "integrity_fail": ["HOLD_LEAKED_UNAUTHORIZED_PAYLOAD"],
        "level1_anomalies": [],
    })
    assert l1["verdict"] == "INTEGRITY_FAIL_PAUSE"


def test_level2_explanation_does_not_change_frozen_verdict():
    cells = {a: _cell(a, exercised=(a == "OPEN_IMMEDIATE"), sec=0.4 if a == "OPEN_IMMEDIATE" else 0.0) for a in (
        "COMMON_ONLY", "OPEN_IMMEDIATE", "OPEN_AFTER_COMMON_PLAYABLE", "BUFFER_GUARDED_OPEN"
    )}
    rnd = classify_round("4g", 81, cells, {}, {"file_sha256": {}})
    assert rnd["verdict"] in ("HEALTHY_CONTINUE", "VALID_UNFAVORABLE_CONTINUE")
    assert rnd["level2"]["frozen_verdict_unchanged"] == rnd["verdict"]
    assert rnd["level2"]["do_not_tune"] is True
    assert rnd["level2"]["not_final_causal_gate"] is True
    assert rnd["level2"]["interim_direction"] in ("favorable", "unfavorable", "ambiguous")


def test_hourly_report_labeled_not_final():
    from command121_three_level import render_hourly, rational_analysis
    body = {
        "ts": "t",
        "n_valid_canonical": 2,
        "n_complete_rounds": 0,
        "last_round_verdict": "INCOMPLETE_WAIT",
        "cumulative_integrity_fail_rounds": 0,
        "cumulative_implementation_anomaly_rounds": 0,
        "pause_new_launches": False,
        "safe_to_continue": True,
        "rounds": [],
    }
    l1 = {"exact_key": "k", "arm": "COMMON_ONLY", "verdict": "CELL_SANITY_PASS",
          "scientific_interpretation": "NOT_APPLICABLE_SINGLE_CELL",
          "integrity_fail": [], "implementation_anomaly": []}
    md = render_hourly(body, [l1], None)
    assert "NOT FINAL CAUSAL GATE" in md
    assert "2/40" in md
    assert "0/10" in md
    ra = rational_analysis(body, l1, None)
    assert ra["do_not_tune"] is True
    assert "CONTINUE" in ra["why_continue_or_pause"]


def test_1s_bin_back_to_back_is_not_true_overlap():
    from command121_rolling_health import l3_true_overlap_fraction
    t0 = 1000.4
    events = [
        {"host": "h1", "t": t0, "rx": 81920},
        {"host": "h2", "t": t0 + 0.51, "rx": 81920},  # same floor(t)=1000, dt>0.50
    ]
    rec = l3_true_overlap_fraction(events, t0, t0 + 115.0, hold_s=0.50)
    assert rec["max_concurrent"] == 1
    assert rec["overlap_fraction"] == 0.0
    assert rec["min_inter_host_dt_s"] >= 0.50


def test_true_simultaneous_overlap_still_counts():
    from command121_rolling_health import l3_true_overlap_fraction
    events = [
        {"host": "h1", "t": 0.0, "rx": 81920},
        {"host": "h2", "t": 0.10, "rx": 81920},
    ]
    rec = l3_true_overlap_fraction(events, 0.0, 100.0, hold_s=0.50)
    assert rec["max_concurrent"] == 2
    assert rec["overlap_fraction"] > 0.0
    assert rec["overlap_fraction"] < 0.10
    from command121_three_level import render_hourly, rational_analysis
    body = {
        "ts": "t",
        "n_valid_canonical": 2,
        "n_complete_rounds": 0,
        "last_round_verdict": "INCOMPLETE_WAIT",
        "cumulative_integrity_fail_rounds": 0,
        "cumulative_implementation_anomaly_rounds": 0,
        "pause_new_launches": False,
        "safe_to_continue": True,
        "rounds": [],
    }
    l1 = {"exact_key": "k", "arm": "COMMON_ONLY", "verdict": "CELL_SANITY_PASS",
          "scientific_interpretation": "NOT_APPLICABLE_SINGLE_CELL",
          "integrity_fail": [], "implementation_anomaly": []}
    md = render_hourly(body, [l1], None)
    assert "NOT FINAL CAUSAL GATE" in md
    assert "2/40" in md
    assert "0/10" in md
    ra = rational_analysis(body, l1, None)
    assert ra["do_not_tune"] is True
    assert "CONTINUE" in ra["why_continue_or_pause"]
