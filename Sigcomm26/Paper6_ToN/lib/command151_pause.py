from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Pause new command148 launches. Does not kill a live Mininet cell."""
from pathlib import Path

REPO = artifact_root()
HOLD = REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_HOLD.json"
RELEASE = REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_RELEASE.json"
HOLD149 = REPO / "state" / "COMMAND149_CANARY_INTEGRITY_HOLD.json"
REL149 = REPO / "state" / "COMMAND149_CANARY_RELEASE.json"
TOKEN = "PAUSED_COMMAND151_PHYSICAL_PRESSURE_INSTRUMENTATION"


def new_launch_paused() -> tuple[bool, str | None]:
    if HOLD.is_file() and not RELEASE.is_file():
        return True, TOKEN
    if HOLD149.is_file() and not REL149.is_file():
        return True, "COMMAND149_CANARY_INTEGRITY_HOLD"
    return False, None
