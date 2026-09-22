from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""E015: crf23 evidence can never satisfy crf28; any hash mismatch forces a fresh run."""
import importlib.util
import json
from pathlib import Path

REPO = artifact_root()
MOD = REPO / "Sigcomm26" / "Paper6_ToN" / "scripts" / "command137_provenance.py"


def _load():
    spec = importlib.util.spec_from_file_location("c137_prov", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _base(**kw):
    body = {
        "content": "redandblack",
        "network": "4g",
        "users": 1,
        "seed": 0,
        "strategy_or_sentinel_mode": "COMMAND137_B3_ONLY_RAW_CLEANED_NO_FLOOR",
        "transport_profile_id": "h264_yuv420_crf28",
        "transport_media_manifest_sha": "man28",
        "physical_b3_sha": "b328",
        "point_membership_sha": "mem",
        "trace_sha": "trace",
        "trace_contract_sha": "tcon",
        "publisher_sha": "pub",
        "dispatch_sha": "disp",
        "subscriber_sha": "sub",
        "lifecycle_sha": "life",
        "metric_hash": "met",
        "feature_contract_hash": "feat",
    }
    body.update(kw)
    return body


def test_crf23_cell_never_satisfies_crf28():
    m = _load()
    crf23 = _base(transport_profile_id="h264_yuv420_crf23", physical_b3_sha="b323", transport_media_manifest_sha="man23")
    crf28 = _base()
    gate = m.reuse_gate(crf23, crf28)
    assert gate["decision"] == m.REUSE_FORBIDDEN
    assert "transport_profile_id" in gate["mismatches"]
    assert "physical_b3_sha" in gate["mismatches"]
    assert "transport_media_manifest_sha" in gate["mismatches"]


def test_profile_or_media_hash_mismatch_always_fresh():
    m = _load()
    req = _base()
    for key, val in (
        ("transport_profile_id", "h264_yuv420_crf32"),
        ("transport_media_manifest_sha", "other_man"),
        ("physical_b3_sha", "other_b3"),
        ("point_membership_sha", "other_mem"),
        ("trace_sha", "other_trace"),
        ("trace_contract_sha", "other_tcon"),
        ("publisher_sha", "other_pub"),
        ("dispatch_sha", "other_disp"),
        ("subscriber_sha", "other_sub"),
        ("lifecycle_sha", "other_life"),
        ("metric_hash", "other_met"),
        ("feature_contract_hash", "other_feat"),
        ("content", "longdress"),
        ("network", "default_mix"),
        ("users", 20),
        ("seed", 51),
        ("strategy_or_sentinel_mode", "heuristic_canary"),
    ):
        got = m.reuse_gate(_base(**{key: val}), req)
        assert got["decision"] == m.REUSE_FORBIDDEN, key
        assert key in got["mismatches"], key


def test_exact_match_allows_reuse():
    m = _load()
    req = _base()
    gate = m.reuse_gate(dict(req), req)
    assert gate["decision"] == m.REUSE_ALLOW
    assert gate["mismatches"] == []


def test_missing_existing_is_forbidden():
    m = _load()
    gate = m.reuse_gate(None, _base())
    assert gate["decision"] == m.REUSE_FORBIDDEN


def _write_echo_set(cell, req, *, profile=None, b3=None, sha=None, stdout_ok=True):
    cell.mkdir(parents=True, exist_ok=True)
    sha = sha if sha is not None else req["run_contract_sha256"]
    profile = profile if profile is not None else req["transport_profile_id"]
    b3 = b3 if b3 is not None else req["physical_b3_sha"]
    echo = {"run_contract_sha256": sha, "transport_profile_id": profile, "b3_sha256": b3}
    (cell / "RUN_CONTRACT_ECHO_PUBLISHER.json").write_text(json.dumps(echo) + "\n")
    (cell / "client_h1_run_contract.json").write_text(json.dumps(echo) + "\n")
    (cell / "CELL_DONE.json").write_text(
        json.dumps(
            {
                "run_contract_sha256": sha,
                "transport_profile_id": profile,
                "physical_b3_sha": b3,
            }
        )
        + "\n"
    )
    text = f"COMMAND137_RUN_CONTRACT sha={sha} profile={profile} b3={b3}\n" if stdout_ok else "检查实验结果\n"
    (cell / "cell_stdout.log").write_text(text)


def test_validate_echoes_pass_when_identities_agree(tmp_path):
    m = _load()
    req = _base()
    req["run_contract_sha256"] = m.contract_sha(req)
    cell = tmp_path / "cell"
    _write_echo_set(cell, req)
    body = m.validate_echoes(cell, req)
    assert body["status"] == "PASS"
    assert body["fail_closed"] is True
    assert body["blocks"] == []


def test_validate_echoes_fail_closed_on_profile_or_media_hash_mismatch(tmp_path):
    m = _load()
    req = _base()
    req["run_contract_sha256"] = m.contract_sha(req)
    cell = tmp_path / "crf23_echoes"
    _write_echo_set(cell, req, profile="h264_yuv420_crf23", b3="b323")
    body = m.validate_echoes(cell, req)
    assert body["status"] == "FAIL"
    assert body["fail_closed"] is True
    assert "publisher_profile" in body["blocks"]
    assert "publisher_b3" in body["blocks"]
    assert "cell_done_profile" in body["blocks"]
    assert "cell_done_b3" in body["blocks"]


def test_crf23_stdout_phrase_cannot_satisfy_crf28_validator(tmp_path):
    m = _load()
    req = _base()
    req["run_contract_sha256"] = m.contract_sha(req)
    cell = tmp_path / "phrase_only"
    _write_echo_set(cell, req, stdout_ok=False)
    body = m.validate_echoes(cell, req)
    assert body["status"] == "FAIL"
    assert "publisher_log_missing_contract_sha" in body["blocks"]
    assert "publisher_log_missing_profile" in body["blocks"]
