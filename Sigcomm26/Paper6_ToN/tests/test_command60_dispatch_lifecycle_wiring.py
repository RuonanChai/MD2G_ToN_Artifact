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

"""Command60/61: dispatch ↔ rep_lifecycle_v2 wiring (no Mininet)."""
import ast
import sys
from pathlib import Path

import pytest

REPO = artifact_root()
sys.path.insert(0, str(REPO))

from strategies.rep_lifecycle_v2 import plan_transition  # noqa: E402

DISPATCH = REPO / "dispatch_strategy_enhanced_unified_Sigcomm.py"


@pytest.mark.parametrize(
    "rendered,bv,el,expected_target,need_switch",
    [
        (None, 1, 0, 1, True),
        (3, 3, 0, 3, False),
        (3, 3, 1, 8, True),
        (8, 3, 1, 8, False),
        (5, 1, 2, 5, False),
        (4, 1, 2, 5, True),
    ],
)
def test_plan_transition(rendered, bv, el, expected_target, need_switch) -> None:
    target, switch = plan_transition(rendered, bv, el)
    assert target == expected_target
    assert switch is need_switch


def test_dispatch_imports_rep_lifecycle_and_env_gate() -> None:
    src = DISPATCH.read_text(encoding="utf-8")
    assert "from strategies.rep_lifecycle_v2 import" in src
    assert "RepLifecycle" in src
    assert "SIGCOMM_REP_LIFECYCLE_V2" in src
    assert "plan_transition" in src
    assert "rep_to_broadcast" in src
    assert "_rep_lc_maintain" in src
    assert "rep_lifecycle_h" in src


def test_dispatch_ast_references_rep_lifecycle() -> None:
    tree = ast.parse(DISPATCH.read_text(encoding="utf-8"), filename=str(DISPATCH))
    names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    assert "RepLifecycle" in names
    assert "plan_transition" in names
