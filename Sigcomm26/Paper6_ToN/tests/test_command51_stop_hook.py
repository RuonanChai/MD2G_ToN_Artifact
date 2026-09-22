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

"""Regression: command51 stop hook rejects premature submission-ready."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = artifact_root()
HOOK = REPO / ".cursor/hooks/sigcomm_submission_stop_hook.py"
STATE = REPO / "Sigcomm26/Paper6_ToN/state"
PY = os.environ.get("SIGCOMM_PYTHON") or sys.executable


def run_hook():
    p = subprocess.run(
        [PY, str(HOOK)],
        input=json.dumps({"status": "completed", "loop_count": 0}),
        text=True,
        capture_output=True,
    )
    return p.returncode, json.loads(p.stdout or "{}")


def main():
    # With submission false / no final gate → must follow up
    old = (STATE / "SIGCOMM_SUBMISSION_READY").read_text() if (STATE / "SIGCOMM_SUBMISSION_READY").exists() else "false\n"
    (STATE / "SIGCOMM_SUBMISSION_READY").write_text("false\n")
    try:
        rc, out = run_hook()
        assert rc == 0
        assert "followup_message" in out
        assert "REJECTED_PREMATURE_STOP" in out["followup_message"] or "STOP_HOOK" in out["followup_message"]
    finally:
        (STATE / "SIGCOMM_SUBMISSION_READY").write_text(old)
    print("COMMAND51_STOP_HOOK_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
