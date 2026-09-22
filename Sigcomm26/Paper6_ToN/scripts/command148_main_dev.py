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

"""945-cell main DEV matrix. Reuse exact matching canary cells. No Loot. No post-canary tuning."""
import json
import os
import subprocess
import sys
from pathlib import Path

TON = ton_root()
REPO = artifact_root()
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))
from command147_io import dump_dual, token, ts  # noqa: E402
from command153_raw_dump_retention import launch_free_space_ok, sentinel_keys  # noqa: E402

STRATS = [
    "MD2G_COMPONENT",
    "HV3_COMPONENT",
    "CLUSTERING_COMPONENT",
    "RULE_COMPONENT",
    "MOQ_UNICAST_COMPONENT",
]
CONTENTS = ["redandblack", "longdress", "soldier"]
NETS = ["4g", "5g", "wifi", "fiber_optic", "default_mix", "wifi_dominant", "5g_dominant"]
USERS = [20, 60, 100]
SEEDS = [151, 152, 153]
QUEUE = REPO / "state" / "COMMAND148_MAINDEV_QUEUE.json"
CANARY_ART = TON / "artifacts" / "command148_canary120"
if (REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_RELEASE.json").is_file():
    CANARY_ART = TON / "artifacts" / "command148_canary120_rbv1"
ART = TON / "artifacts" / "command148_maindev"
PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"


def matrix() -> list[dict]:
    rows = []
    for content in CONTENTS:
        for net in NETS:
            for users in USERS:
                for seed in SEEDS:
                    for strat in STRATS:
                        key = f"c148dev_{content}_{net}_u{users}_{strat}_s{seed}"
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


def canary_twin(spec: dict) -> Path | None:
    if spec["content"] not in ("redandblack", "longdress"):
        return None
    if spec["network"] not in ("4g", "default_mix", "wifi_dominant"):
        return None
    if spec["users"] not in (20, 60):
        return None
    if spec["seed"] not in (151, 152):
        return None
    k = f"c148can_{spec['content']}_{spec['network']}_u{spec['users']}_{spec['strategy']}_s{spec['seed']}"
    p = CANARY_ART / k
    if (p / "CELL_DONE.json").is_file() and (p / "CELL_METRICS.json").is_file():
        return p
    return None


def main() -> int:
    if not (REPO / "state" / "COMMAND148_DEV_CANDIDATE_FREEZE.json").is_file():
        print(json.dumps({"pass": False, "reason": "candidate_not_frozen"}))
        return 2
    if (os.environ.get("TON_CONTENT_ID") or "").lower() == "loot":
        print(json.dumps({"pass": False, "reason": "loot_sealed"}))
        return 2
    rows = matrix()
    assert len(rows) == 945
    q = json.loads(QUEUE.read_text()) if QUEUE.is_file() else {"completed": [], "failed": None, "reused": []}
    q["n"] = 945
    q["loot_sealed"] = True
    done_list = list(q.get("completed") or [])
    done = set(done_list)
    reused = list(q.get("reused") or [])
    ART.mkdir(parents=True, exist_ok=True)
    for spec in rows:
        if spec["key"] in done:
            continue
        twin = canary_twin(spec)
        # otherwise MAINDEV completes with SENTINEL_KEEP but zero recoverable raw dumps.
        if twin is not None and spec["key"] in sentinel_keys() and not list(twin.glob("dump_*.bin")):
            twin = None
        if twin is not None:
            dest = ART / spec["key"]
            dest.mkdir(parents=True, exist_ok=True)
            for name in ("CELL_DONE.json", "CELL_METRICS.json", "CELL_AUDIT.json", "CELL_VALIDITY.json"):
                src = twin / name
                if src.is_file():
                    (dest / name).write_text(src.read_text())
            # Prefer copying twin dumps when present (sentinel or future reuse with dumps).
            for dump in twin.glob("dump_*.bin"):
                target = dest / dump.name
                if not target.is_file():
                    target.write_bytes(dump.read_bytes())
            rec = json.loads((dest / "CELL_DONE.json").read_text())
            rec["reused_from"] = twin.name
            rec["key"] = spec["key"]
            (dest / "CELL_DONE.json").write_text(json.dumps(rec, indent=2) + "\n")
            done.add(spec["key"])
            done_list.append(spec["key"])
            reused.append(spec["key"])
            q["completed"] = done_list
            q["reused"] = reused
            q["n"] = 945
            q["status"] = f"{len(done_list)}/945"
            q["ts"] = ts()
            dump_dual("COMMAND148_MAINDEV_QUEUE.json", q)
            continue
        # Cell-boundary disk gate only: never kill/interrupt a live cell for yellow disk.
        disk = launch_free_space_ok(REPO)
        if disk.get("pause_next_launch"):
            dump_dual(
                "COMMAND153_DISK_PAUSE_NEXT_LAUNCH.json",
                {
                    "ts": ts(),
                    "token": "COMMAND153_DISK_PAUSE_NEXT_LAUNCH",
                    "next_key": spec["key"],
                    "disk": disk,
                    "kill_live_cell": False,
                    "cleanup_forbidden": disk.get("cleanup_forbidden"),
                },
            )
            print(json.dumps({"pass": False, "reason": "disk_pause_next_launch", "disk": disk}))
            return 5
        env = os.environ.copy()
        env["COMMAND148_STAGE"] = "main_dev"
        env["COMMAND148_SPEC_JSON"] = json.dumps(spec)
        env["COMMAND148_ART_ROOT"] = str(ART)
        env["COMMAND153_QUEUE_NAME"] = "COMMAND148_MAINDEV_QUEUE.json"
        env["COMMAND148_QUEUE_N"] = "945"
        env["COMMAND152_LAUNCH"] = os.environ.get("COMMAND152_LAUNCH") or "1"
        fail = q.get("failed") or {}
        if fail:
            subprocess.run(
                [str(PY), "-u", str(TON / "scripts" / "command153_classify_and_repair.py")],
                cwd=str(REPO),
                check=False,
            )
            from command148_canary_cell import consume_exact_key, exact_key_authorized  # noqa: PLC0415

            fk = str(fail.get("key") or spec["key"])
            n_try = int((q.get("attempts") or {}).get(fk) or 0)
            auth = exact_key_authorized(fk)
            if n_try >= 3 and auth is None:
                token(
                    "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
                    {"reason": "maindev_fail_closed", "failed": fk, "attempts": n_try, "kill_live_cell": False},
                )
                print(json.dumps({"pass": False, "reason": "maindev_fail_closed", "failed": fail.get("key"), "attempts": n_try, "ledger": True}))
                return 3
            if auth is not None:
                consume_exact_key(auth)
            q["failed"] = None
            dump_dual("COMMAND148_MAINDEV_QUEUE.json", q)
            if fk != spec["key"]:
                spec = next((s for s in rows if s["key"] == fk), spec)
                env["COMMAND148_SPEC_JSON"] = json.dumps(spec)
        rc = subprocess.run(
            [str(PY), "-u", str(TON / "scripts" / "command148_canary_cell.py")],
            cwd=str(REPO),
            env=env,
        ).returncode
        return rc
    dump_dual(
        "COMMAND148_MAINDEV_QUEUE.json",
        {"ts": ts(), "n": 945, "completed": done_list, "reused": reused, "status": f"{len(done)}/945", "loot_sealed": True},
    )
    expected = [s["key"] for s in rows]
    if any(k not in done for k in expected):
        print(json.dumps({"pass": False, "reason": "maindev_incomplete", "n": sum(1 for k in expected if k in done), "expected": 945}))
        return 2
    print(json.dumps({"pass": True, "done": len(expected)}))
    cont = TON / "scripts" / "command153_continue.py"
    if cont.is_file() and not (REPO / "state" / "COMMAND153_FINAL_DEV_FROZEN.json").is_file():
        dump_dual(
            "COMMAND148_MAINDEV_COMPLETE.json",
            {"ts": ts(), "token": "COMMAND148_MAINDEV_COMPLETE", "n": 945, "loot_sealed": True},
        )
        env = os.environ.copy()
        env["COMMAND152_LAUNCH"] = env.get("COMMAND152_LAUNCH") or "1"
        return subprocess.run([str(PY), "-u", str(cont)], cwd=str(REPO), env=env).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
