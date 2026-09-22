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

"""H2 CROSS_STACK_DASH_BASELINES. After 945 DEV, before FINAL_DEV_FROZEN. One Mininet."""
import csv
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

TON = ton_root()
REPO = artifact_root()
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))
from command137_proc import dash_live, moq_live  # noqa: E402
from command147_io import dump_dual, handle_unsupervised_live_wait, sha256_file, token, ts  # noqa: E402
from command152_executor_lock import release, try_acquire  # noqa: E402
from command153_raw_dump_retention import launch_free_space_ok  # noqa: E402

PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
RUNNER = TON / "scripts" / "run_authentic_unicast_baseline_cell.py"
ART = TON / "artifacts" / "command153_cross_stack_dash"
QNAME = "COMMAND153_CROSS_STACK_DASH_QUEUE.json"
CONTENTS = ["redandblack", "longdress"]
NETS = ["4g", "default_mix", "wifi_dominant"]
USERS = [20, 60]
SEEDS = [151, 152]
STRATS = ["groot", "rolling"]
MEDIA_ROOT = REPO / "media" / "ton_dash_reference_ladder_v1"


def dash_media_init(content: str) -> Path:
    return MEDIA_ROOT / content / "dash_live" / "dash" / "rep1" / "rep1_init.mp4"


def media_ready() -> tuple[bool, list[str]]:
    missing = [str(dash_media_init(c)) for c in CONTENTS if not dash_media_init(c).is_file()]
    return (not missing), missing


def matrix() -> list[dict]:
    rows = []
    for content in CONTENTS:
        for net in NETS:
            for users in USERS:
                for seed in SEEDS:
                    for strat in STRATS:
                        key = f"c153dash_{content}_{net}_u{users}_{strat}_s{seed}"
                        rows.append(
                            {
                                "key": key,
                                "content": content,
                                "network": net,
                                "users": users,
                                "seed": seed,
                                "strategy": f"{strat}_dash",
                                "dash_strategy": strat,
                            }
                        )
    return rows


def write_manifest() -> dict | None:
    rows = matrix()
    assert len(rows) == 48
    keys = [r["key"] for r in rows]
    for name in ("COMMAND153_CROSS_STACK_DASH_MANIFEST.json", "CROSS_STACK_DASH_MANIFEST.json"):
        existing_p = REPO / "state" / name
        if not existing_p.is_file():
            continue
        try:
            prev = json.loads(existing_p.read_text())
        except Exception:
            continue
        frozen_keys = list(prev.get("keys") or [])
        if not frozen_keys:
            continue
        if frozen_keys != keys or int(prev.get("n") or 0) != 48:
            token(
                "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
                {
                    "reason": "h2_matrix_diverged_from_frozen_manifest",
                    "manifest": name,
                    "kill_live_cell": False,
                },
            )
            return None
        return prev
    body = {
        "ts": ts(),
        "token": "CROSS_STACK_DASH_MANIFEST",
        "frozen_before_any_command153_dash_outcome": True,
        "execute_after": "COMMAND148_MAINDEV_COMPLETE",
        "execute_before": ["COMMAND153_FINAL_DEV_FROZEN", "Loot unseal"],
        "n": 48,
        "contents": CONTENTS,
        "networks": NETS,
        "users": USERS,
        "seeds": SEEDS,
        "strategies": ["GROOT_DASH", "ROLLING_DASH"],
        "keys": keys,
        "media": str(MEDIA_ROOT),
        "media_semantics": "standalone DASH reference ladder, not nested b0/db1/db2/e1/e2",
        "classification": "CROSS_STACK_SYSTEM_COMPARISON",
        "not_same_substrate": True,
        "do_not_use_as_primary_md2g_vs_baseline": True,
        "primary_same_substrate_remains": [
            "HV3_COMPONENT",
            "CLUSTERING_COMPONENT",
            "RULE_COMPONENT",
        ],
        "canonical_U_commensurate_with_nested_Q_norm": False,
        "report_native_dash_metrics_separately": True,
        "independent_unicast_Ro": 0,
        "authentic_http_unicast_only": True,
        "never_retrofit_component_grouping_or_md2g_control": True,
        "rb_command151_physical_pressure": True,
        "sole_launcher": "tmux:command152_orch",
        "runner_sha256": sha256_file(RUNNER) if RUNNER.is_file() else None,
        "loot_sealed": True,
    }
    dump_dual("CROSS_STACK_DASH_MANIFEST.json", body)
    dump_dual("COMMAND153_CROSS_STACK_DASH_MANIFEST.json", body)
    return body


def score_cell(cell: Path, expected: int) -> dict:
    per = []
    for p in sorted(list(cell.glob("client_h*_perf.csv")) + list(cell.glob("dash_h*_perf.csv"))):
        rows = list(csv.DictReader(p.open()))
        if not rows:
            continue
        t0 = float(rows[0]["timestamp"])
        use = [r for r in rows if float(r["timestamp"]) - t0 >= 30.0] or rows
        ro, rq, rb = [], [], []
        for r in use:
            try:
                ro.append(float(r["reward_R_o"]))
                rq.append(float(r["reward_R_q"]))
                rb.append(float(r["reward_R_b"]))
            except Exception:
                pass
        if ro:
            per.append(
                {
                    "Ro": statistics.mean(ro),
                    "Rq": statistics.mean(rq),
                    "Rb": statistics.mean(rb),
                }
            )
    return {"ok": len(per) >= max(1, expected // 2), "n": len(per), "native_user_rows": per[:3]}


def main() -> int:
    leftover = handle_unsupervised_live_wait()
    if leftover == 3:
        print(json.dumps({"pass": False, "reason": "unsupervised_live_after_lock_dead", "kill_live_cell": False}))
        return 3
    if leftover == 0:
        print(json.dumps({"pass": True, "wait": True, "reason": "unsupervised_live_grace", "kill_live_cell": False}))
        return 0
    if moq_live() or dash_live():
        print(json.dumps({"pass": True, "wait": True, "reason": "live_cell_untouched"}))
        return 0
    if (REPO / "state" / "COMMAND152_ACTIVE.json").is_file() and os.environ.get(
        "COMMAND152_LAUNCH", ""
    ).strip().lower() not in ("1", "true", "yes"):
        print(json.dumps({"pass": True, "wait": True, "reason": "command152_owns_launches"}))
        return 0
    if not (REPO / "state" / "COMMAND148_MAINDEV_COMPLETE.json").is_file():
        print(json.dumps({"pass": True, "wait": True, "reason": "main_dev_incomplete", "manifest_frozen": True}))
        return 0
    man = write_manifest()
    if man is None:
        print(json.dumps({"pass": False, "reason": "h2_matrix_diverged_from_frozen_manifest"}))
        return 3
    if not (REPO / "state" / "COMMAND139_DASH_REFERENCE_LADDER_GATE.json").is_file():
        token(
            "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
            {"reason": "dash_reference_ladder_gate_missing", "kill_live_cell": False},
        )
        print(json.dumps({"pass": False, "reason": "dash_reference_ladder_gate_missing"}))
        return 2
    ok_media, missing_media = media_ready()
    if not ok_media:
        token(
            "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
            {"reason": "dash_media_init_missing", "missing": missing_media, "kill_live_cell": False},
        )
        print(json.dumps({"pass": False, "reason": "dash_media_init_missing", "missing": missing_media}))
        return 2
    rows = matrix()
    qp = REPO / "state" / QNAME
    q = json.loads(qp.read_text()) if qp.is_file() else {"completed": [], "failed": None, "n": 48, "attempts": {}}
    q["n"] = 48
    done = set(q.get("completed") or [])
    ART.mkdir(parents=True, exist_ok=True)
    pending = next((r for r in rows if r["key"] not in done), None)
    if pending is None:
        dump_dual(
            "COMMAND153_CROSS_STACK_DASH_COMPLETE.json",
            {
                "ts": ts(),
                "token": "COMMAND153_CROSS_STACK_DASH_COMPLETE",
                "n": 48,
                "not_primary_same_substrate": True,
                "loot_sealed": True,
            },
        )
        print(json.dumps({"pass": True, "phase": "h2_complete", "n": 48, "done_unique": len(done)}))
        return 0
    if pending["content"] == "loot":
        token(
            "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
            {"reason": "h2_loot_key_before_final_dev_frozen", "key": pending["key"], "kill_live_cell": False},
        )
        print(json.dumps({"pass": False, "reason": "h2_loot_key_before_final_dev_frozen", "key": pending["key"]}))
        return 3
    # Cell-boundary disk gate only — never interrupt live for yellow disk.
    disk = launch_free_space_ok(REPO)
    if disk.get("pause_next_launch"):
        dump_dual(
            "COMMAND153_DISK_PAUSE_NEXT_LAUNCH.json",
            {
                "ts": ts(),
                "token": "COMMAND153_DISK_PAUSE_NEXT_LAUNCH",
                "next_key": pending["key"],
                "phase": "h2_cross_stack_dash",
                "disk": disk,
                "kill_live_cell": False,
            },
        )
        print(json.dumps({"pass": False, "reason": "disk_pause_next_launch", "disk": disk}))
        return 5
    fail = q.get("failed") or {}
    attempts = dict(q.get("attempts") or {})
    n_try = int(attempts.get(pending["key"]) or 0)
    if fail:
        subprocess.run(
            [str(PY), "-u", str(TON / "scripts" / "command153_classify_and_repair.py")],
            cwd=str(REPO),
            check=False,
        )
        from command148_canary_cell import consume_exact_key, exact_key_authorized  # noqa: PLC0415

        fk = str(fail.get("key") or pending["key"])
        auth = exact_key_authorized(fk)
        # Same budget as nested canary: two identical execution retries (3 attempts),
        # then fail-closed unless command153 exact-key is AUTHORIZED.
        if n_try >= 3 and auth is None:
            token(
                "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
                {"reason": "h2_fail_closed", "failed": fk, "attempts": n_try, "kill_live_cell": False},
            )
            print(json.dumps({"pass": False, "reason": "h2_fail_closed", "failed": fk, "attempts": n_try, "ledger": True}))
            return 3
        if auth is not None:
            consume_exact_key(auth)
        q["failed"] = None
        dump_dual(QNAME, q)
    lock_fd = try_acquire(pending["key"], "command153_cross_stack_dash")
    if lock_fd is None:
        print(json.dumps({"pass": True, "wait": True, "reason": "executor_lock_held"}))
        return 0
    proc = None
    try:
        attempts[pending["key"]] = n_try + 1
        q["attempts"] = attempts
        dump_dual(QNAME, q)
        cell = ART / pending["key"]
        cell.mkdir(parents=True, exist_ok=True)
        for stale in (
            "PHYSICAL_PRESSURE_TIMESERIES.jsonl",
            "PHYSICAL_PRESSURE_SUMMARY.json",
            "CELL_DONE.json",
        ):
            sp = cell / stale
            if sp.is_file():
                sp.unlink()
        live = MEDIA_ROOT / pending["content"] / "dash_live"
        env = os.environ.copy()
        env.update(
            {
                "SIGCOMM_DASH_LIVE_DIR": str(live),
                "SIGCOMM_AUTHENTIC_UNICAST": "1",
                "DASH_STRATEGY": pending["dash_strategy"],
                "TON_CONTENT_ID": pending["content"],
                "MM26_CONTENT_ID": pending["content"],
                "SIGCOMM_BASELINE_SEED": str(pending["seed"]),
                "MM26_SEED": str(pending["seed"]),
                "COMMAND151_REQUIRE_PRESSURE": "1",
                "COMMAND152_LAUNCH": env.get("COMMAND152_LAUNCH") or "1",
                "PYTHONUNBUFFERED": "1",
            }
        )
        if pending["network"] == "4g":
            env["COMMAND137_RATE_FEASIBILITY_RAW_4G"] = "1"
            env["COMMAND139_DASH_MATCHED_RAW_4G"] = "1"
        cmd = [
            str(PY),
            "-u",
            str(RUNNER),
            "--strategy",
            pending["dash_strategy"],
            "--clients",
            str(pending["users"]),
            "--network_type",
            pending["network"],
            "--log_path",
            str(cell),
            "--duration",
            "120",
            "--interval",
            "1.0",
        ]
        with (cell / "cell_stdout.log").open("w") as out:
            proc = subprocess.run(cmd, cwd=str(REPO), env=env, stdout=out, stderr=subprocess.STDOUT)
    finally:
        release(lock_fd)
    if proc is None:
        rec = {
            "ts": ts(),
            **pending,
            "rc": None,
            "valid": False,
            "class": "INVALID_EXECUTION",
        }
        q["failed"] = rec
        q["status"] = "FAIL_CLOSED"
        dump_dual(QNAME, q)
        print(json.dumps({"pass": False, "key": pending["key"], "class": "INVALID_EXECUTION", "reason": "h2_proc_unbound"}))
        return 4
    proof = {}
    if (cell / "UNICAST_AUTHENTICITY_PROOF.json").is_file():
        proof = json.loads((cell / "UNICAST_AUTHENTICITY_PROOF.json").read_text())
    valid_cell = False
    if (cell / "CELL_VALIDITY.json").is_file():
        valid_cell = bool(json.loads((cell / "CELL_VALIDITY.json").read_text()).get("valid"))
    sc = score_cell(cell, int(pending["users"]))
    n_press = 0
    ts_p = cell / "PHYSICAL_PRESSURE_TIMESERIES.jsonl"
    if ts_p.is_file():
        try:
            n_press = sum(1 for ln in ts_p.read_text().splitlines() if ln.strip())
        except Exception:
            n_press = 0
    rec = {
        "ts": ts(),
        **pending,
        "rc": proc.returncode,
        "score": sc,
        "physical_pressure_samples": n_press,
        "valid": bool(valid_cell and proof.get("independent_http_sessions") and n_press >= 2),
        "classification": "CROSS_STACK",
        "canonical_U_not_primary": True,
        "media": "dash_reference_ladder_v1",
    }
    (cell / "CELL_DONE.json").write_text(json.dumps(rec, indent=2) + "\n")
    if not rec["valid"]:
        q["failed"] = rec
        q["status"] = "FAIL_CLOSED"
        dump_dual(QNAME, q)
        print(json.dumps({"pass": False, "key": pending["key"], "class": "INVALID_EXECUTION_OR_FIDELITY"}))
        return 4
    done.add(pending["key"])
    q["completed"] = list(done)
    q["failed"] = None
    q["last_key"] = pending["key"]
    q["status"] = f"{len(done)}/48"
    q["ts"] = ts()
    dump_dual(QNAME, q)
    print(json.dumps({"pass": True, "key": pending["key"], "progress": q["status"]}))
    if len(done) >= 48:
        dump_dual(
            "COMMAND153_CROSS_STACK_DASH_COMPLETE.json",
            {
                "ts": ts(),
                "token": "COMMAND153_CROSS_STACK_DASH_COMPLETE",
                "n": 48,
                "not_primary_same_substrate": True,
                "loot_sealed": True,
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
