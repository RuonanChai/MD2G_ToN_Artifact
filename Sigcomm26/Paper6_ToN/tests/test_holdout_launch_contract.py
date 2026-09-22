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

"""Regression tests for HOLDOUT_LAUNCH_CONTRACT_V2."""
import json
import os
import subprocess
import sys
from pathlib import Path

OUT = ton_root()
PY = os.environ.get("SIGCOMM_PYTHON") or str(
    Path("python3")
)
GUARD = OUT / "scripts/holdout_launch_guard.py"
STATE = OUT / "state"


def run_guard(net, u, s, t):
    return subprocess.run([PY, str(GUARD), net, str(u), s, str(t)], capture_output=True, text=True)


def main():
    # Contract file
    c = json.loads((OUT / "contracts/HOLDOUT_LAUNCH_CONTRACT_V2.json").read_text())
    assert "HOLDOUT_RELEASE_APPROVED=true" in str(c["required_all"])

    # Unsafe: contaminated cell always denied
    r = run_guard("default_mix", 10, "md2g", 0)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "contaminated" in (r.stderr + r.stdout).lower() or "DENIED" in (r.stderr + r.stdout)

    # Unsafe: untouched holdout without freeze/release denied
    r = run_guard("default_mix", 10, "rolling", 0)
    assert r.returncode != 0
    assert "DENIED" in (r.stderr + r.stdout)

    old_c = (STATE / "CONTINUE_MATRIX").read_text() if (STATE / "CONTINUE_MATRIX").exists() else "false\n"
    (STATE / "CONTINUE_MATRIX").write_text("true\n")
    try:
        r = run_guard("4g", 10, "md2g", 0)
        assert r.returncode != 0
    finally:
        (STATE / "CONTINUE_MATRIX").write_text(old_c)

    print("HOLDOUT_LAUNCH_CONTRACT_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
