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

"""Same-substrate MCG evaluation harness. One Mininet. Shared command148 cell path."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))
from command137_proc import dash_live, moq_live  # noqa: E402
from command147_io import dump_dual, ts  # noqa: E402
from command153_raw_dump_retention import launch_free_space_ok  # noqa: E402

PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
ART = TON / "artifacts" / "ton_live_mcg"
QNAME = "COMMAND_TON_LIVE_MCG_QUEUE.json"
N = 27
NETS = ("4g", "wifi", "fiber_optic")
USERS = (20, 60, 100)
SEEDS = (151, 152, 153)
CONTENT = "redandblack"


def matrix() -> list[dict]:
    rows = []
    for net in NETS:
        for users in USERS:
            for seed in SEEDS:
                rows.append(
                    {
                        "key": f"c148mcg_{CONTENT}_{net}_u{users}_MCG_COMPONENT_s{seed}",
                        "content": CONTENT,
                        "network": net,
                        "users": users,
                        "seed": seed,
                        "strategy": "MCG_COMPONENT",
                        "stage": "ton_live_mcg",
                    }
                )
    assert len(rows) == N
    return rows


def load_q() -> dict:
    p = REPO / "state" / QNAME
    if p.is_file():
        return json.loads(p.read_text())
    return {"completed": [], "failed": None, "attempts": {}, "invalid": [], "n": N}


def save_q(q: dict) -> None:
    q["ts"] = ts()
    q["n"] = N
    dump_dual(QNAME, q)


def next_spec(q: dict) -> dict | None:
    done = list(q.get("completed") or [])
    dset = set(done)
    dirty = False
    pending = None
    for spec in matrix():
        if spec["key"] in dset:
            continue
        cell = ART / spec["key"]
        if (cell / "CELL_DONE.json").is_file() and (cell / "CELL_METRICS.json").is_file():
            done.append(spec["key"])
            dset.add(spec["key"])
            dirty = True
            continue
        pending = spec
        break
    if dirty:
        q["completed"] = done
        q["status"] = f"{len(done)}/{N}"
        save_q(q)
    return pending


def launch(spec: dict) -> int:
    disk = launch_free_space_ok(REPO)
    if disk.get("pause_next_launch"):
        dump_dual(
            "TON_LIVE_MCG_DISK_PAUSE.json",
            {"ts": ts(), "next_key": spec["key"], "disk": disk, "kill_live_cell": False},
        )
        print(json.dumps({"pass": False, "reason": "disk_pause_next_launch", "disk": disk}), flush=True)
        return 5
    ART.mkdir(parents=True, exist_ok=True)
    q = load_q()
    if q.get("n") is None:
        q["n"] = N
        save_q(q)
    env = os.environ.copy()
    env["COMMAND148_SPEC_JSON"] = json.dumps(spec)
    env["COMMAND148_ART_ROOT"] = str(ART)
    env["COMMAND153_QUEUE_NAME"] = QNAME
    env["COMMAND148_STAGE"] = "ton_live_mcg"
    env["COMMAND148_QUEUE_N"] = str(N)
    env["COMMAND152_LAUNCH"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    print(json.dumps({"event": "launch", "key": spec["key"], "ts": ts()}), flush=True)
    return subprocess.run(
        [str(PY), "-u", str(TON / "scripts" / "command148_canary_cell.py")],
        cwd=str(REPO),
        env=env,
    ).returncode


def maybe_aggregate(n_done: int) -> int:
    if n_done < N:
        return 0
    agg = TON / "scripts" / "ton_cast_extension" / "live_mcg_aggregate.py"
    return subprocess.run([str(PY), "-u", str(agg)], cwd=str(REPO)).returncode


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    (TON / "logs").mkdir(parents=True, exist_ok=True)
    dump_dual(
        "TON_LIVE_MCG_STATUS.json",
        {"ts": ts(), "status": "RUNNING", "art": str(ART), "n": N, "kill_live_cell": False},
    )
    while True:
        if moq_live() or dash_live():
            print(json.dumps({"wait": True, "reason": "executor_already_live", "ts": ts()}), flush=True)
            time.sleep(30)
            continue
        q = load_q()
        fail = q.get("failed")
        if fail:
            dump_dual(
                "TON_LIVE_MCG_BLOCKED.json",
                {"ts": ts(), "reason": "fail_closed", "failed": fail, "kill_live_cell": False},
            )
            print(json.dumps({"pass": False, "reason": "fail_closed", "failed": fail.get("key")}), flush=True)
            return 3
        spec = next_spec(q)
        if spec is None:
            n = len(load_q().get("completed") or [])
            dump_dual("TON_LIVE_MCG_STATUS.json", {"ts": ts(), "status": "AGGREGATING", "n_done": n})
            rc = maybe_aggregate(n)
            dump_dual(
                "TON_LIVE_MCG_STATUS.json",
                {"ts": ts(), "status": "COMPLETE" if rc == 0 and n >= N else "INCOMPLETE", "n_done": n, "agg_rc": rc},
            )
            print(json.dumps({"pass": rc == 0, "done": n, "n": N, "agg_rc": rc}), flush=True)
            return 0 if rc == 0 and n >= N else 4
        rc = launch(spec)
        q = load_q()
        dump_dual(
            "TON_LIVE_MCG_STATUS.json",
            {
                "ts": ts(),
                "status": "RUNNING",
                "last_key": spec["key"],
                "last_rc": rc,
                "n_done": len(q.get("completed") or []),
                "n": N,
            },
        )
        if rc not in (0,):
            # canary_cell 0 = success or retry-scheduled; non-zero = fail-closed / blocked
            time.sleep(2)
            q2 = load_q()
            if q2.get("failed"):
                continue
            if rc == 5:
                time.sleep(60)
                continue
            print(json.dumps({"pass": False, "reason": "launch_rc", "rc": rc, "key": spec["key"]}), flush=True)
            return rc
        time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
