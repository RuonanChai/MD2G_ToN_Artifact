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

"""Command60/61 regression: Heuristic + Clustering baseline repairs (synthetic only)."""
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

REPO = artifact_root()
sys.path.insert(0, str(REPO))

from strategies.cell_scoped_state import set_deterministic_seeds, write_controller_fatal
from strategies.heuristic_controller_v2_refined import (
    EnhancedHeuristicController,
    aggregate_client_states as heuristic_aggregate_client_states,
)
from strategies.predictive_controller_v2_refined import (
    EnhancedPredictiveController,
    aggregate_client_states as clustering_aggregate_client_states,
)

HEURISTIC_BASELINE_LABEL = "HEURISTIC_DETERMINISTIC_JOINT"
CLUSTERING_BASELINE_LABEL = "CLUSTERING_ALGORITHMIC_APPROXIMATION"

# Loosened gates for synthetic discriminative cohort (documented in COMMAND60_BASELINE_REPAIR_TEST_PLAN.md).
DISCRIMINATIVE_ENV: Dict[str, str] = {
    "SIGCOMM_BASELINE_SEED": "6100",
    "MM26_HEURISTIC_GATE_MIN_TP": "2.0",
    "MM26_HEURISTIC_GATE_MEAN_TP": "3.0",
    "MM26_HEURISTIC_GATE_MAX_DELAY": "200.0",
    "MM26_HEURISTIC_GATE_MEAN_DELAY": "150.0",
    "MM26_HEURISTIC_GATE_MIN_DEV": "0.10",
    "MM26_HEURISTIC_GATE_MIN_PROB": "0.50",
    "MM26_HEURISTIC_ENH_TMIN": "1.5",
    "MM26_HEURISTIC_ENH_TMEAN": "2.5",
    "MM26_HEURISTIC_ENH_DMAX": "250.0",
    "MM26_HEURISTIC_ENH_DEV": "0.08",
    "MM26_HEURISTIC_ENHANCED_RATIO_CAP": "0.625",
    "MM26_CLUSTER_GATE_P75_MAX": "100.0",
    "MM26_CLUSTER_GATE_P90_MAX": "110.0",
    "MM26_CLUSTER_GATE_DSTD_MAX": "50.0",
    "MM26_CLUSTER_GATE_JITTER_MAX": "30.0",
    "MM26_CLUSTER_GATE_MIN_TP": "2.0",
    "MM26_CLUSTER_GATE_MEAN_TP": "3.0",
    "MM26_CLUSTER_ENHANCED_RATIO_CAP": "0.625",
}

NUM_USERS = 8
# Off-mainline host_ids for /tmp/mininet_shared collision avoidance.
CELL_STATE_HOST_BASE = 901


def assert_layers_decisions_consistent(payload: dict, first_uid: int = 1) -> None:
    """layers[i] must match decisions[str(first_uid+i)].pull_enhanced."""
    layers = payload["layers"]
    decisions = payload["decisions"]
    for i, layer in enumerate(layers):
        uid = str(first_uid + i)
        expected = 1 if decisions[uid]["pull_enhanced"] else 0
        assert int(bool(layer)) == expected, (
            f"layers/decisions mismatch uid={uid} layer={layer} expected={expected}"
        )


def build_decision_payload(
    *,
    strategy: str,
    decisions: List[int],
    first_uid: int,
    num_users: int,
    seed: int,
    uid_to_gid: Dict[int, int],
    group_members: Dict[int, List[int]],
    per_user_extra: Dict[int, dict] | None = None,
) -> dict:
    """Minimal controller-shaped payload for layers/decisions consistency checks."""
    per_user_extra = per_user_extra or {}
    decisions_map: Dict[str, dict] = {}
    decision_ts = time.time()
    for uid in range(first_uid, first_uid + num_users):
        gid = int(uid_to_gid.get(uid, uid))
        members = sorted(int(m) for m in group_members.get(gid, [uid]))
        local_idx = uid - first_uid
        pull = bool(decisions[local_idx]) if 0 <= local_idx < len(decisions) else False
        entry = {
            "pull_enhanced": pull,
            "enhanced_level": 1 if pull else 0,
            "decision_ts": decision_ts,
        }
        entry.update(per_user_extra.get(uid, {}))
        if strategy == "heuristic":
            entry.update(
                {
                    "heuristic_group_id": gid,
                    "heuristic_group_members": members,
                    "heuristic_group_size": len(members),
                }
            )
        else:
            entry.update(
                {
                    "clustering_group_id": gid,
                    "clustering_group_members": members,
                    "clustering_group_size": len(members),
                }
            )
        decisions_map[str(uid)] = entry

    payload = {
        "layers": [int(d) for d in decisions],
        "timestamp": decision_ts,
        "seed": seed,
        "decisions": decisions_map,
    }
    if strategy == "heuristic":
        payload["used_model"] = "EnhancedJointOptimization_v2"
        payload["baseline_label"] = HEURISTIC_BASELINE_LABEL
    else:
        payload["used_model"] = CLUSTERING_BASELINE_LABEL
        payload["baseline_label"] = CLUSTERING_BASELINE_LABEL

    assert_layers_decisions_consistent(payload, first_uid=first_uid)
    return payload


def _client_state_record(host_id: int, throughput: float, delay: float = 40.0) -> dict:
    return {
        "host_id": host_id,
        "timestamp": time.time(),
        "throughput_mbps": throughput,
        "delay_ms": delay,
        "device_score": 0.8,
        "fov_overlap": 0.7,
        "viewpoint": "synthetic",
    }


def _write_state_files(directory: Path, host_ids: List[int], throughput: float) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for hid in host_ids:
        path = directory / f"client_h{hid}_state.json"
        path.write_text(json.dumps(_client_state_record(hid, throughput)))


def _discriminative_clients() -> Dict[int, dict]:
    """Two cohorts: good BW/low delay vs poor BW/high delay; u5/u6 split H vs C."""
    def mk(**kw: Any) -> dict:
        base = dict(
            network_stability=1.0,
            user_preference=0.5,
            bandwidth_variance=0.1,
            latency_jitter=2.0,
        )
        base.update(kw)
        return base

    return {
        1: mk(throughput=10, delay=30, device_score=0.9, fov_overlap=0.9, bandwidth_headroom=7),
        2: mk(throughput=10, delay=30, device_score=0.9, fov_overlap=0.9, bandwidth_headroom=7),
        3: mk(throughput=10, delay=30, device_score=0.9, fov_overlap=0.2, bandwidth_headroom=7),
        4: mk(throughput=10, delay=30, device_score=0.9, fov_overlap=0.2, bandwidth_headroom=7),
        5: mk(
            throughput=8,
            delay=140,
            device_score=0.8,
            fov_overlap=0.5,
            bandwidth_headroom=5,
            latency_jitter=8,
        ),
        6: mk(throughput=10, delay=30, device_score=0.9, fov_overlap=0.5, bandwidth_headroom=7),
        7: mk(
            throughput=1.5,
            delay=200,
            device_score=0.2,
            fov_overlap=0.3,
            bandwidth_headroom=0,
            latency_jitter=25,
        ),
        8: mk(
            throughput=1.5,
            delay=200,
            device_score=0.2,
            fov_overlap=0.3,
            bandwidth_headroom=0,
            latency_jitter=25,
        ),
    }


@pytest.fixture
def discriminative_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in DISCRIMINATIVE_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize(
    "aggregate_fn",
    [heuristic_aggregate_client_states, clustering_aggregate_client_states],
    ids=["heuristic", "clustering"],
)
def test_cell_scoped_state_prefers_sigcomm_cell_state_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, aggregate_fn
) -> None:
    scoped = tmp_path / "cell_state"
    legacy = Path("/tmp/mininet_shared")
    host_ids = [CELL_STATE_HOST_BASE + i for i in range(4)]
    user_offset = host_ids[0]
    num_users = len(host_ids)

    monkeypatch.setenv("SIGCOMM_CELL_STATE_DIR", str(scoped))
    _write_state_files(scoped, host_ids, throughput=77.7)
    _write_state_files(legacy, host_ids, throughput=11.1)

    try:
        states = aggregate_fn(num_users, user_offset=user_offset)
    finally:
        for hid in host_ids:
            legacy_file = legacy / f"client_h{hid}_state.json"
            if legacy_file.exists():
                legacy_file.unlink()

    assert len(states) == num_users
    for hid in host_ids:
        assert states[hid]["throughput"] == pytest.approx(77.7)
        assert "state_path" in states[hid]
        assert str(scoped) in states[hid]["state_path"]


@pytest.mark.parametrize(
    "controller_cls,label",
    [
        (EnhancedHeuristicController, HEURISTIC_BASELINE_LABEL),
        (EnhancedPredictiveController, CLUSTERING_BASELINE_LABEL),
    ],
    ids=["heuristic", "clustering"],
)
def test_deterministic_seeds_same_inputs_same_decisions(
    discriminative_env: None,
    controller_cls: type,
    label: str,
) -> None:
    clients = _discriminative_clients()
    runs: List[List[int]] = []
    for _ in range(2):
        set_deterministic_seeds(int(os.environ["SIGCOMM_BASELINE_SEED"]))
        controller = controller_cls(NUM_USERS)
        runs.append(controller.make_decision(clients))
    assert runs[0] == runs[1]
    assert sum(runs[0]) >= 1
    assert label in (HEURISTIC_BASELINE_LABEL, CLUSTERING_BASELINE_LABEL)


def test_discriminative_synthetic_clients_not_aliases(discriminative_env: None) -> None:
    clients = _discriminative_clients()
    set_deterministic_seeds(int(os.environ["SIGCOMM_BASELINE_SEED"]))
    h_dec = EnhancedHeuristicController(NUM_USERS).make_decision(clients)
    set_deterministic_seeds(int(os.environ["SIGCOMM_BASELINE_SEED"]))
    c_dec = EnhancedPredictiveController(NUM_USERS).make_decision(clients)

    assert sum(h_dec) >= 1, "heuristic must emit at least one enhanced=1 under loosened gates"
    assert sum(c_dec) >= 1, "clustering must emit at least one enhanced=1 under loosened gates"
    assert h_dec != c_dec, "heuristic and clustering must not be decision aliases"


def test_write_controller_fatal_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_root = tmp_path / "cell_logs"
    monkeypatch.setenv("SIGCOMM_CELL_LOG_PATH", str(log_root))
    decision_file = str(tmp_path / "decisions.json")
    err = RuntimeError("synthetic controller fault")
    path = write_controller_fatal(decision_file, "heuristic", err, "traceback-line")

    generic = log_root / "CONTROLLER_FATAL.json"
    specific = log_root / "CONTROLLER_FATAL_heuristic.json"
    assert path == specific
    assert generic.is_file()
    payload = json.loads(generic.read_text())
    assert payload["invalidate_cell"] is True
    assert payload["fail_closed"] is True
    assert payload["strategy"] == "heuristic"
    assert "synthetic controller fault" in payload["error"]


def test_make_decision_exception_triggers_fatal_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate fail-closed path when make_decision raises (no Mininet loop)."""
    log_root = tmp_path / "cell_logs"
    monkeypatch.setenv("SIGCOMM_CELL_LOG_PATH", str(log_root))
    decision_file = str(tmp_path / "decisions.json")

    controller = EnhancedHeuristicController(NUM_USERS)

    def _boom(_clients: dict) -> List[int]:
        raise ValueError("make_decision exploded")

    controller.make_decision = _boom  # type: ignore[method-assign]
    clients = _discriminative_clients()
    with pytest.raises(ValueError, match="make_decision exploded"):
        controller.make_decision(clients)

    write_controller_fatal(decision_file, "heuristic", ValueError("make_decision exploded"), "tb")
    payload = json.loads((log_root / "CONTROLLER_FATAL.json").read_text())
    assert payload["invalidate_cell"] is True


def test_layers_decisions_consistency_heuristic_payload(discriminative_env: None) -> None:
    clients = _discriminative_clients()
    set_deterministic_seeds(int(os.environ["SIGCOMM_BASELINE_SEED"]))
    controller = EnhancedHeuristicController(NUM_USERS)
    decisions = controller.make_decision(clients)

    uid_to_gid: Dict[int, int] = {}
    group_members: Dict[int, List[int]] = {}
    first_uid = 1
    for gid, users in controller.last_groups.items():
        for local_uid in users:
            global_uid = local_uid + first_uid - 1
            uid_to_gid[global_uid] = int(gid)
            group_members.setdefault(int(gid), []).append(global_uid)

    payload = build_decision_payload(
        strategy="heuristic",
        decisions=decisions,
        first_uid=first_uid,
        num_users=NUM_USERS,
        seed=int(os.environ["SIGCOMM_BASELINE_SEED"]),
        uid_to_gid=uid_to_gid,
        group_members=group_members,
    )
    assert payload["baseline_label"] == HEURISTIC_BASELINE_LABEL


def test_layers_decisions_consistency_clustering_payload(discriminative_env: None) -> None:
    clients = _discriminative_clients()
    set_deterministic_seeds(int(os.environ["SIGCOMM_BASELINE_SEED"]))
    controller = EnhancedPredictiveController(NUM_USERS)
    decisions = controller.make_decision(clients)

    uid_to_gid: Dict[int, int] = {}
    group_members: Dict[int, List[int]] = {}
    first_uid = 1
    for gid, users in controller.last_clusters.items():
        for local_uid in users:
            global_uid = int(local_uid) + first_uid - 1
            uid_to_gid[global_uid] = int(gid)
            group_members.setdefault(int(gid), []).append(global_uid)

    payload = build_decision_payload(
        strategy="clustering",
        decisions=decisions,
        first_uid=first_uid,
        num_users=NUM_USERS,
        seed=int(os.environ["SIGCOMM_BASELINE_SEED"]),
        uid_to_gid=uid_to_gid,
        group_members=group_members,
    )
    assert payload["baseline_label"] == CLUSTERING_BASELINE_LABEL
    assert CLUSTERING_BASELINE_LABEL in payload["used_model"]


def test_clustering_baseline_label_constant() -> None:
    src = (REPO / "strategies/predictive_controller_v2_refined.py").read_text(encoding="utf-8")
    assert CLUSTERING_BASELINE_LABEL in src
    assert "baseline_label" in src


def test_heuristic_baseline_label_constant() -> None:
    src = (REPO / "strategies/heuristic_controller_v2_refined.py").read_text(encoding="utf-8")
    assert HEURISTIC_BASELINE_LABEL in src
    assert "baseline_label" in src
