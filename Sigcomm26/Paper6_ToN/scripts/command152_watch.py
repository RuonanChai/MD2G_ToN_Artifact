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

"""Read-only command152 watcher. Never launches Mininet. Never mn -c."""
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
LOG = TON / "logs" / "command152_watch.log"
HOURLY_SCRIPT = TON / "scripts" / "command155_hourly_report.py"
HOURLY_INTERVAL_S = 3600


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def maybe_hourly_report(last_run: float) -> float:
    now = time.time()
    if now - last_run < HOURLY_INTERVAL_S:
        return last_run
    if HOURLY_SCRIPT.is_file():
        subprocess.run([str(PY), "-u", str(HOURLY_SCRIPT)], cwd=str(REPO), check=False)
    return now


def main() -> int:
    last_hourly = 0.0
    while True:
        cur = {}
        p = REPO / "state" / "CURRENT.json"
        if p.exists():
            try:
                cur = json.loads(p.read_text())
            except Exception:
                cur = {}
        q = {}
        qp = REPO / "state" / "COMMAND151_24CELL_QUEUE.json"
        if qp.exists():
            try:
                q = json.loads(qp.read_text())
            except Exception:
                q = {}
        cq = {}
        cqp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
        if cqp.exists():
            try:
                cq = json.loads(cqp.read_text())
            except Exception:
                cq = {}
        dq = {}
        dqp = REPO / "state" / "COMMAND148_MAINDEV_QUEUE.json"
        if dqp.exists():
            try:
                dq = json.loads(dqp.read_text())
            except Exception:
                dq = {}
        hq = {}
        hqp = REPO / "state" / "COMMAND153_CROSS_STACK_DASH_QUEUE.json"
        if hqp.exists():
            try:
                hq = json.loads(hqp.read_text())
            except Exception:
                hq = {}
        sq = {}
        sqp = REPO / "state" / "COMMAND153_SCALING_QUEUE.json"
        if sqp.exists():
            try:
                sq = json.loads(sqp.read_text())
            except Exception:
                sq = {}
        lq = {}
        lqp = REPO / "state" / "COMMAND153_LOOT_QUEUE.json"
        if lqp.exists():
            try:
                lq = json.loads(lqp.read_text())
            except Exception:
                lq = {}
        terms = [
            "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_A",
            "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B",
            "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_C",
            "CORRECT_COMPONENT_CONTRACT_NOT_SUPPORTED",
            "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
        ]
        term = next((t for t in terms if (REPO / "state" / f"{t}.json").is_file()), None)
        lock = {}
        lp = REPO / "state" / "SCIENTIFIC_EXECUTOR.lock"
        if lp.is_file():
            try:
                lock = json.loads(lp.read_text())
            except Exception:
                lock = {}
        lock_alive = False
        try:
            pid = int(lock.get("pid") or 0)
            lock_alive = pid > 0 and Path(f"/proc/{pid}").exists()
        except (TypeError, ValueError):
            lock_alive = False
        orch = subprocess.run(
            ["tmux", "has-session", "-t", "command152_orch"],
            capture_output=True,
        ).returncode == 0
        leftover = (REPO / "state" / "COMMAND153_UNSUPERVISED_LIVE.json").is_file()
        line = (
            f"[{ts()}] next={cur.get('next_action')} phase={cur.get('phase')} "
            f"post_rb={q.get('status')} canary={cq.get('status')} "
            f"maindev={dq.get('status')} maindev_last={dq.get('last_key')} maindev_failed={dq.get('failed')} "
            f"h2={hq.get('status')} scale={sq.get('status')} loot={lq.get('status')} "
            f"lock={lock.get('cell_key')} lock_alive={lock_alive} orch={orch} leftover={leftover} "
            f"executor={cur.get('exactly_one_executor')} loot_sealed={cur.get('loot_network_holdout_sealed')} "
            f"terminal={term}"
        )
        print(line, flush=True)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.open("a").write(line + "\n")
        last_hourly = maybe_hourly_report(last_hourly)
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
