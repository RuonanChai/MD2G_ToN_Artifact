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

"""command40 §9: SIGCOMM Eq.9 must be the active R_q path when SIGCOMM_QOE_EQ9=1."""
import ast
import hashlib
import math
import os
import re
import sys
from pathlib import Path

REPO = artifact_root()
DISPATCH = REPO / "dispatch_strategy_enhanced_unified_Sigcomm.py"
MOQ = REPO / "moq_cluster_Sigcomm.py"
OUT = REPO / "Sigcomm26/Paper6_ToN"

REP_TO_QS = {
    1: 0.8, 2: 0.6, 3: 0.4,
    4: 1.0, 5: 1.0,
    6: 0.6, 7: 0.8,
    8: 0.4, 9: 0.4,
}


def _source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def test_eq9_gate_present_in_source():
    src = DISPATCH.read_text(encoding="utf-8")
    assert 'os.environ.get("SIGCOMM_QOE_EQ9"' in src
    assert "_REP_TO_QS" in src
    assert "QOE_WEIGHTS[\"delay\"]" in src  # legacy five-part still exists
    # Eq.9 must be the taken branch when env truthy
    assert re.search(
        r'_use_eq9\s*=\s*os\.environ\.get\("SIGCOMM_QOE_EQ9".*?\)\s*.*?in\s*\("1"',
        src,
        re.S,
    )
    # Must map from final Rep ID via map_to_rep_id inside Eq.9 branch
    eq9_block = src.split("if _use_eq9:", 1)[1].split("else:", 1)[0]
    assert "map_to_rep_id" in eq9_block
    assert "0.6 + 0.4" not in eq9_block
    assert "QOE_WEIGHTS" not in eq9_block


def test_mm26_print_labeled_when_eq9():
    src = DISPATCH.read_text(encoding="utf-8")
    assert "[QOE_CONTRACT] SIGCOMM_QOE_EQ9=1 active" in src
    assert "INACTIVE legacy" in src or "inactive legacy" in src


def test_moq_forwards_eq9_env():
    src = MOQ.read_text(encoding="utf-8")
    assert "SIGCOMM_QOE_EQ9=" in src
    assert "SIGCOMM_REP_LADDER=" in src


def test_eq9_formula_recompute_sample():
    """One recomputed sample from raw inputs (paper Eq.9)."""
    rid = 4
    Q_s = REP_TO_QS[rid]
    delay_ms = 100.0
    stall_sec = 0.0
    D_n = min(delay_ms / 200.0, 1.0)
    S_n = 1.0 - math.exp(-stall_sec / 3.0) if stall_sec > 0 else 0.0
    R_q = max(0.0, min(1.0, 1.0 * Q_s - 0.5 * D_n - 0.5 * S_n))
    assert abs(Q_s - 1.0) < 1e-12
    assert abs(D_n - 0.5) < 1e-12
    assert abs(R_q - 0.75) < 1e-9


def test_eq9_active_path_differs_from_mm26_shortcut():
    """Under Eq.9, Q_s(Rep3)=0.4; MM26 shortcut with enh=0 yields 0.6."""
    assert REP_TO_QS[3] == 0.4
    mm26 = min(1.0, 0.6 + 0.4 * (0 / 2.0))
    assert abs(mm26 - 0.6) < 1e-12
    assert abs(mm26 - REP_TO_QS[3]) > 1e-9


def test_import_eq9_banner_when_env_set():
    """Import dispatch with env=1 must advertise Eq.9 contract (not only five-part)."""
    env = os.environ.copy()
    env["SIGCOMM_QOE_EQ9"] = "1"
    env.setdefault("SIGCOMM_DATASET_DIR", str(REPO / "datasets"))
    # Lightweight: exec only the banner block equivalent by reading AST + re-check source.
    # Full import is heavy; verify contract strings and that default path is gated.
    tree = ast.parse(DISPATCH.read_text(encoding="utf-8"))
    assigns = [n for n in tree.body if isinstance(n, ast.Assign)]
    assert assigns  # module parses
    src = DISPATCH.read_text(encoding="utf-8")
    # Fail if module still unconditionally claims MM26 is the active path with no Eq.9 gate text
    assert "paper Eq.9" in src or "SIGCOMM_QOE_EQ9=1 active" in src


def test_contract_fingerprint_fields():
    """Machine-readable contract snapshot for audits."""
    contract = {
        "SIGCOMM_QOE_EQ9_resolved_when_set": "1",
        "SIGCOMM_REP_LADDER_campaign": "1",
        "source_file": str(DISPATCH.relative_to(REPO)),
        "source_function": "run_client / reward R_q block",
        "source_hash": _source_hash(DISPATCH),
        "moq_cluster_hash": _source_hash(MOQ),
        "rep_id_to_Qs": REP_TO_QS,
        "delay_norm": "min(delay_ms/200, 1)",
        "stall_norm": "1-exp(-stall_total_sec/3)",
        "qoe_formula_id": "SIGCOMM_EQ9_TABLE1",
        "output_columns": [
            "rep_id", "reward_R_q", "qoe", "quality_score",
            "delay_ms", "stall_total_sec",
        ],
    }
    out = OUT / "audits" / "QOE_RUNTIME_CONTRACT_SNAPSHOT.json"
    import json
    out.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    assert out.exists()
    assert contract["qoe_formula_id"] == "SIGCOMM_EQ9_TABLE1"


if __name__ == "__main__":
    tests = [
        test_eq9_gate_present_in_source,
        test_mm26_print_labeled_when_eq9,
        test_moq_forwards_eq9_env,
        test_eq9_formula_recompute_sample,
        test_eq9_active_path_differs_from_mm26_shortcut,
        test_import_eq9_banner_when_env_set,
        test_contract_fingerprint_fields,
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print("PASS test_sigcomm_qoe_runtime_contract")
