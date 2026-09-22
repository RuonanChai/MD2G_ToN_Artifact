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

"""120-cell corrected-contract canary. One cell per invocation. No Loot network."""
import json
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import REPO, dump_dual, ts  # noqa: E402
from command151_pause import new_launch_paused  # noqa: E402

STRATS = [
    "MD2G_COMPONENT",
    "HV3_COMPONENT",
    "CLUSTERING_COMPONENT",
    "RULE_COMPONENT",
    "MOQ_UNICAST_COMPONENT",
]
CONTENTS = ["redandblack", "longdress"]
NETS = ["4g", "default_mix", "wifi_dominant"]
USERS = [20, 60]
SEEDS = [151, 152]
QUEUE = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"


def matrix() -> list[dict]:
    rows = []
    for content in CONTENTS:
        for net in NETS:
            for users in USERS:
                for seed in SEEDS:
                    for strat in STRATS:
                        key = f"c148can_{content}_{net}_u{users}_{strat}_s{seed}"
                        rows.append(
                            {
                                "key": key,
                                "content": content,
                                "network": net,
                                "users": users,
                                "seed": seed,
                                "strategy": strat,
                            }
                        )
    return rows


def main() -> int:
    paused, token = new_launch_paused()
    if paused:
        if (REPO / "state" / "COMMAND152_ACTIVE.json").is_file():
            print(json.dumps({"pass": True, "paused": token, "wait": True, "subordinate_to_command152": True}))
            return 0
        import subprocess

        py = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
        after = TON / "scripts" / "command151_after_boundary.py"
        print(
            json.dumps(
                {
                    "pass": True,
                    "paused": token,
                    "wait": True,
                    "no_new_cell": True,
                    "kill_live_cell": False,
                }
            )
        )
        if after.is_file():
            return subprocess.run([str(py), "-u", str(after)], cwd=str(REPO)).returncode
        return 0
    if not (REPO / "state" / "COMMAND148_TEACHER_STUDENT_READY.json").is_file():
        print(json.dumps({"pass": False, "reason": "teacher_not_ready"}))
        return 2
    rows = matrix()
    assert len(rows) == 120
    q = json.loads(QUEUE.read_text()) if QUEUE.is_file() else {"completed": [], "failed": None}
    body = {
        "ts": ts(),
        "n": 120,
        "completed": q.get("completed") or [],
        "failed": q.get("failed"),
        "attempts": q.get("attempts") or {},
        "invalid": q.get("invalid") or [],
        "status": f"{len(q.get('completed') or [])}/120",
        "loot_sealed": True,
    }
    for k in ("epoch", "art", "do_not_mix_pre_rb", "epoch_id", "last_key"):
        if q.get(k) is not None:
            body[k] = q[k]
    dump_dual("COMMAND148_CANARY120_QUEUE.json", body)
    # Hand off to one-cell runner when present.
    cell = TON / "scripts" / "command148_canary_cell.py"
    if cell.is_file():
        import subprocess

        py = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
        return subprocess.run([str(py), "-u", str(cell)], cwd=str(REPO)).returncode
    print(json.dumps({"pass": False, "reason": "canary_cell_runner_missing", "n": 120}))
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
