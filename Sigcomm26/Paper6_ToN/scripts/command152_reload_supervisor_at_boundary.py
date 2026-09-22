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

"""Reload command152_orch at a dead cell boundary only. Never a second Mininet. Never mn -c."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))
from command137_proc import moq_live  # noqa: E402
from command147_io import ts  # noqa: E402

PY = str(REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3")
MARKER = REPO / "state" / "COMMAND152_ORCH_RELOADED.json"
LOG = TON / "logs" / "command152_orch_reload.log"
LAUNCH = (
    f"cd {REPO} && {PY} -u {TON}/scripts/command152_production_supervisor.py "
    f"2>&1 | tee -a {TON}/logs/command152_orch.log"
)


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{ts()} {msg}"
    print(line, flush=True)
    LOG.open("a").write(line + "\n")


def pids(pattern: str) -> list[int]:
    out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
    ids = []
    for ln in (out.stdout or "").split():
        try:
            ids.append(int(ln))
        except ValueError:
            pass
    return ids


def scientific_children_live() -> bool:
    for pat in (
        "command148_canary_cell.py",
        "command148_canary120.py",
        "command147_24cell_fidelity_smoke.py",
        "command148_main_dev.py",
        "command153_continue.py",
    ):
        if pids(pat):
            return True
    return False


def main() -> int:
    if MARKER.is_file():
        log("already_reloaded")
        return 0
    log("wait_dead_boundary")
    while True:
        if moq_live() or scientific_children_live():
            time.sleep(3)
            continue
        sup = pids("command152_production_supervisor.py")
        if not sup:
            log("no_supervisor_recreate_tmux")
            subprocess.run(
                ["tmux", "has-session", "-t", "command152_orch"],
                check=False,
            )
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", "command152_orch", LAUNCH],
                check=False,
            )
            if not pids("command152_production_supervisor.py"):
                subprocess.run(["tmux", "respawn-pane", "-t", "command152_orch", "-k", LAUNCH], check=False)
            MARKER.write_text('{"ts": "%s", "token": "COMMAND152_ORCH_RELOADED", "mode": "recreate"}\n' % ts())
            log("recreated")
            return 0
        # Re-check immediately before signal: a cell must not have started.
        time.sleep(1)
        if moq_live() or scientific_children_live():
            continue
        for pid in sup:
            if pid == os.getpid():
                continue
            log(f"SIGTERM supervisor {pid}")
            os.kill(pid, signal.SIGTERM)
        time.sleep(2)
        if pids("command152_production_supervisor.py"):
            log("supervisor_still_alive_abort")
            return 3
        rc = subprocess.run(["tmux", "has-session", "-t", "command152_orch"]).returncode
        if rc == 0:
            subprocess.run(["tmux", "respawn-pane", "-t", "command152_orch", "-k", LAUNCH], check=False)
        else:
            subprocess.run(["tmux", "new-session", "-d", "-s", "command152_orch", LAUNCH], check=False)
        time.sleep(2)
        if not pids("command152_production_supervisor.py"):
            log("reload_failed_no_supervisor")
            return 4
        MARKER.write_text('{"ts": "%s", "token": "COMMAND152_ORCH_RELOADED", "mode": "respawn"}\n' % ts())
        log("reloaded")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
