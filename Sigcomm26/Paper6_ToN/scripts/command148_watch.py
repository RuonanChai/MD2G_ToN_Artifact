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

"""Read-only command148 watcher. Never launches Mininet. Never mn -c."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
LOG = TON / "logs" / "command148_watch.log"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    while True:
        cur = {}
        p = REPO / "state" / "CURRENT.json"
        if p.exists():
            cur = json.loads(p.read_text())
        q = {}
        qp = REPO / "state" / "COMMAND147_24CELL_QUEUE.json"
        if qp.exists():
            q = json.loads(qp.read_text())
        cq = {}
        cqp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
        if cqp.exists():
            cq = json.loads(cqp.read_text())
        line = (
            f"[{ts()}] next={cur.get('next_action')} phase={cur.get('phase')} "
            f"smoke={q.get('status')} canary={cq.get('status')} last={cq.get('last_key')} "
            f"active={cur.get('active_cell')} loot_sealed={cur.get('loot_network_holdout_sealed')} "
            f"executor={cur.get('exactly_one_executor')}"
        )
        print(line, flush=True)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.open("a").write(line + "\n")
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
