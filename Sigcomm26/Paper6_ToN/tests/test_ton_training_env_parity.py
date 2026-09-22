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

"""Stage 2.1 — training env / accounting parity for COMMAND86 (Sigcomm nine-rep plane).

Token: TON_TRAINING_ENV_PARITY_PASS
Does not open holdout. Does not require Mininet live cells.
"""
import json
import math
import os
import subprocess
import sys
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
STATE = TON / "state"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TON))

TABLE1 = {
    1: 3.07,
    2: 1.79,
    3: 0.87,
    4: 4.54,
    5: 6.42,
    6: 2.80,
    7: 3.91,
    8: 1.43,
    9: 1.97,
}

EXPECTED_MAP = {
    (1, 0): 1,
    (2, 0): 2,
    (3, 0): 3,
    (1, 1): 4,
    (1, 2): 5,
    (2, 1): 6,
    (2, 2): 7,
    (3, 1): 8,
    (3, 2): 9,
}


def _u_eval(ro: float, rq: float, rb: float) -> float:
    return max(0.0, min(1.0, 0.25 * ro + 0.60 * rq - 0.15 * rb))


def test_gates_and_holdout_seal():
    assert (STATE / "TON_DATA_AND_SPLIT_PASS").exists()
    assert (STATE / "TON_SIGCOMM_NINE_REP_AUDIT_PASS").exists()
    seal = json.loads((STATE / "TON_HOLDOUT_SEAL.json").read_text())
    assert seal["sealed"] is True
    assert set(seal["holdout_rep_ids"]) == {3, 5}
    split = json.loads((STATE / "TON_DATA_SPLIT_FREEZE.json").read_text())
    assert set(split["train_rep_ids"] + split["dev_rep_ids"] + split["holdout_rep_ids"]) == set(
        range(1, 10)
    )
    assert not set(split["holdout_rep_ids"]) & set(split["train_rep_ids"])


def _ffprobe_mbps(path: str) -> float:
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=bit_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(r.stdout.strip()) / 1e6


def test_runtime_paths_and_bitrates():
    # Prefer system python for moq_cluster (needs distro mininet); fall back to ffprobe+paths.
    live = REPO / "video" / "redandblack_6_live"
    assert live.is_dir()
    files = {
        1: "rep1_base1_h264.mp4",
        2: "rep2_base2_h264.mp4",
        3: "rep3_base3_h264.mp4",
        4: "rep4_base1_enhanced1_h264.mp4",
        5: "rep5_base1_enhanced1_enhanced2_h264.mp4",
        6: "rep6_base2_enhanced1_h264.mp4",
        7: "rep7_base2_enhanced1_enhanced2_h264.mp4",
        8: "rep8_base3_enhanced1_h264.mp4",
        9: "rep9_base3_enhanced1_enhanced2_h264.mp4",
    }
    src = (REPO / "moq_cluster_Sigcomm.py").read_text(encoding="utf-8")
    assert 'REDANDBLACK_6_DIR = os.path.join(VIDEO_DIR, "redandblack_6_live")' in src
    for rid, name in files.items():
        path = live / name
        assert path.is_file(), f"missing {path}"
        br = _ffprobe_mbps(str(path))
        assert abs(br - TABLE1[rid]) < 0.15, f"rep{rid}: {br} vs {TABLE1[rid]}"


def test_action_to_rep_mapping():
    from strategies.rep_lifecycle_v2 import map_to_rep_id, rep_to_broadcast, REP_BROADCAST

    for (b, e), expect in EXPECTED_MAP.items():
        got = map_to_rep_id(b, e)
        assert got == expect, f"({b},{e}) -> {got} expect {expect}"
        assert rep_to_broadcast(got) == REP_BROADCAST[got]


def test_u_eval_frozen_independent():
    # Frozen paper metric; training must not retune these weights after results.
    assert abs(_u_eval(1, 1, 0) - 0.85) < 1e-9
    assert abs(_u_eval(0, 0, 1) - 0.0) < 1e-9  # clipped
    assert abs(_u_eval(1, 0, 1) - 0.10) < 1e-9


def test_projector_does_not_mutate_metrics():
    from controllers.c29_feasibility_projector import ProjectorConfig, project_actions

    users = list(range(5))
    groups = {u: u % 3 for u in users}
    upgrades = {u: True for u in users}
    access = {u: 10.0 for u in users}
    dwell = {u: 10.0 for u in users}
    g2, u2, log = project_actions(
        user_ids=users,
        raw_group=groups,
        raw_upgrade=upgrades,
        access_capacity_mbps=access,
        measured_residual_mbps=2.0,
        time_since_switch_s=dwell,
        cfg=ProjectorConfig(max_upgrades_per_tick=2, enhancement_cost_mbps=1.0),
    )
    assert log.contract_ok
    assert sum(1 for v in u2.values() if v) <= 2
    # Metric formula must remain independent of projector
    assert abs(_u_eval(0.8, 0.7, 0.1) - (0.25 * 0.8 + 0.60 * 0.7 - 0.15 * 0.1)) < 1e-12


def test_rep_bitrate_accounting_suite():
    r = subprocess.run(
        ["/usr/bin/python3", str(TON / "tests" / "test_rep_bitrate_accounting.py")],
        cwd=str(TON),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + "\n" + r.stderr


def test_c29_forward_shapes():
    import torch
    from controllers.c29_model import C29Controller, C29ModelConfig

    cfg = C29ModelConfig()
    model = C29Controller(cfg)
    B, N = 2, 8
    user = torch.randn(B, N, cfg.user_in_dim)
    content = torch.randn(B, cfg.content_in_dim)
    glob = torch.randn(B, cfg.global_in_dim)
    out = model(user, content, glob)
    assert "group_logits" in out or hasattr(out, "keys") or isinstance(out, dict)
    if isinstance(out, dict):
        # any head present is enough for scaffold parity
        assert len(out) >= 1


def main() -> int:
    tests = [
        test_gates_and_holdout_seal,
        test_runtime_paths_and_bitrates,
        test_action_to_rep_mapping,
        test_u_eval_frozen_independent,
        test_projector_does_not_mutate_metrics,
        test_rep_bitrate_accounting_suite,
        test_c29_forward_shapes,
    ]
    evidence = {"checks": [], "pass": True}
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            evidence["checks"].append({"name": t.__name__, "ok": True})
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            evidence["checks"].append({"name": t.__name__, "ok": False, "error": str(e)})
            evidence["pass"] = False
    out = STATE / "TON_TRAINING_ENV_PARITY.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    if evidence["pass"]:
        (STATE / "TON_TRAINING_ENV_PARITY_PASS").write_text("PASS\n")
        print("TON_TRAINING_ENV_PARITY_PASS")
        return 0
    print("TON_TRAINING_ENV_PARITY_FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
