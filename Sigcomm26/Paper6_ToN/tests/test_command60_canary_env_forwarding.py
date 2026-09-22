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

"""Command60: canary campaign env forwarding into Mininet namespaces (no Mininet)."""
from pathlib import Path

REPO = artifact_root()
MOQ_CLUSTER = REPO / "moq_cluster_Sigcomm.py"
DISPATCH = REPO / "dispatch_strategy_enhanced_unified_Sigcomm.py"
CANARY = REPO / "Sigcomm26/Paper6_ToN/scripts/command60_run_prescience_canaries.py"


def test_moq_cluster_forwards_sigcomm_rep_lifecycle_in_env_vars() -> None:
    src = MOQ_CLUSTER.read_text(encoding="utf-8")
    assert "def sigcomm_campaign_env_dict" in src
    assert "SIGCOMM_REP_LIFECYCLE_V2" in src
    assert "sigcomm_campaign_env_prefix()" in src
    assert "f'{_campaign_env}'" in src or "f\"{_campaign_env}\"" in src
    idx = src.index("def gen_dispatch_cmd")
    env_vars_block = src[idx : idx + 2500]
    assert "SIGCOMM_REP_LIFECYCLE_V2" in env_vars_block or "_campaign_env" in env_vars_block


def test_moq_cluster_forwards_mm26_and_controller_env() -> None:
    src = MOQ_CLUSTER.read_text(encoding="utf-8")
    assert 'key.startswith("MM26_")' in src
    assert "_campaign_env}{SIGCOMM_PYTHON}" in src.replace(" ", "")


def test_dispatch_reads_sigcomm_initial_probe_s() -> None:
    src = DISPATCH.read_text(encoding="utf-8")
    assert "SIGCOMM_INITIAL_PROBE_S" in src
    assert "_initial_probe_duration_s" in src
    assert "SIGCOMM_BUFFER_PROTECTION_S" in src
    assert "_buffer_protection_threshold_s" in src
    assert "payload_ttfb_ms is None" in src
    assert "media_covered_sec" in src


def test_canary_script_sets_probe_and_buffer_env() -> None:
    src = CANARY.read_text(encoding="utf-8")
    assert 'default=90' in src.replace(" ", "")
    assert "SIGCOMM_INITIAL_PROBE_S" in src
    assert "SIGCOMM_BUFFER_PROTECTION_S" in src
    assert "MM26_HEURISTIC_GATE_MIN_TP" in src
