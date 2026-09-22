#!/usr/bin/env python3
"""Cell-scoped client-state paths + deterministic seeding (command60/61)."""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import List, Optional

import numpy as np


def cell_state_dir() -> Path:
    """Prefer SIGCOMM_CELL_STATE_DIR; else /tmp/{SIGCOMM_CELL_TMP}client_state; else legacy."""
    env = os.environ.get("SIGCOMM_CELL_STATE_DIR", "").strip()
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    tmp = os.environ.get("SIGCOMM_CELL_TMP", "").strip()
    if tmp:
        p = Path(f"/tmp/{tmp}client_state")
        p.mkdir(parents=True, exist_ok=True)
        return p
    p = Path("/tmp/mininet_shared")
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_search_dirs() -> List[Path]:
    """Ordered search roots for client_h*_state.json (scoped first)."""
    dirs: List[Path] = []
    primary = cell_state_dir()
    dirs.append(primary)
    legacy = Path("/tmp/mininet_shared")
    if legacy.resolve() != primary.resolve():
        dirs.append(legacy)
    return dirs


def set_deterministic_seeds(seed: Optional[int] = None) -> int:
    if seed is None:
        seed = int(os.environ.get("SIGCOMM_BASELINE_SEED", os.environ.get("PYTHONHASHSEED", "61")))
    seed = int(seed) & 0x7FFFFFFF
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except Exception:
        pass
    return seed


def write_controller_fatal(decision_file: str, strategy: str, err: BaseException, tb: str) -> Path:
    """Fail-closed marker next to decision file; cell validity should treat as invalid."""
    base = Path(decision_file).resolve().parent if decision_file else Path("/tmp")
    # Prefer cell log path via env
    log_root = os.environ.get("SIGCOMM_CELL_LOG_PATH", "").strip()
    out_dir = Path(log_root) if log_root else base
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"CONTROLLER_FATAL_{strategy}.json"
    payload = {
        "ts": time.time(),
        "strategy": strategy,
        "error": str(err),
        "traceback": tb,
        "fail_closed": True,
        "invalidate_cell": True,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)
    # Also stamp a generic name for validity scanners
    generic = out_dir / "CONTROLLER_FATAL.json"
    tmp2 = generic.with_suffix(".tmp")
    tmp2.write_text(json.dumps(payload, indent=2))
    tmp2.replace(generic)
    return path


def append_action_audit(decision_file: str, record: dict) -> None:
    log_root = os.environ.get("SIGCOMM_CELL_LOG_PATH", "").strip()
    out_dir = Path(log_root) if log_root else Path(decision_file).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "controller_action_audit.jsonl"
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
