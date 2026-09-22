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

"""command40 §5: Rolling must not shadow sys with a local import."""
import ast
import re
import sys
from pathlib import Path

REPO = artifact_root()
CTRL = REPO / "regional_relay_controller.py"
MM26 = REPO / "MM26" / "regional_relay_controller.py"


def _rolling_region(src: str) -> str:
    # Slice around Rolling SC-DDQN load
    m = re.search(r"\[Rolling\].*Loading SC-DDQN(.*?)(?:elif |else:|def )", src, re.S)
    return m.group(0) if m else src


def test_no_local_import_sys_in_rolling_region():
    for path in (CTRL, MM26):
        src = path.read_text(encoding="utf-8")
        region = _rolling_region(src)
        # Strip comments before checking for a real local import
        code_only = "\n".join(
            ln for ln in region.splitlines()
            if not ln.lstrip().startswith("
        )
        assert not re.search(r"^\s*import\s+sys\b", code_only, re.M), (
            f"local import sys still in Rolling region of {path}"
        )
        assert re.search(r"^import sys\b", src, re.M), f"module-level import sys missing in {path}"


def test_note_comment_present():
    src = CTRL.read_text(encoding="utf-8")
    assert "do NOT `import sys`" in src or "do NOT import sys" in src or "NOTE(command40)" in src


def test_ast_parse_controllers():
    for path in (CTRL, MM26):
        ast.parse(path.read_text(encoding="utf-8"))


def test_rolling_arg_construction_contract():
    """Source must pass --strategy rolling into controller cmd without bare except swallow."""
    moq = (REPO / "moq_cluster_Sigcomm.py").read_text(encoding="utf-8")
    assert "--strategy {strategy}" in moq or "--strategy rolling" in moq
    # Failure path must SystemExit / nonzero, not silent pass
    assert "SystemExit(2)" in moq


if __name__ == "__main__":
    test_no_local_import_sys_in_rolling_region()
    test_note_comment_present()
    test_ast_parse_controllers()
    test_rolling_arg_construction_contract()
    print("OK test_rolling_launch")
