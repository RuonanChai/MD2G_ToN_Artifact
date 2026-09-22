from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Exactly-one scientific Mininet executor lock. Never kill a live cell to take it."""
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO = artifact_root()
LOCK = REPO / "state" / "SCIENTIFIC_EXECUTOR.lock"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def try_acquire(cell_key: str, owner: str) -> int | None:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCK), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    body = {"pid": os.getpid(), "cell_key": cell_key, "owner": owner, "ts": ts()}
    os.ftruncate(fd, 0)
    os.write(fd, (json.dumps(body) + "\n").encode())
    os.fsync(fd)
    return fd


def release(fd: int | None) -> None:
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass
