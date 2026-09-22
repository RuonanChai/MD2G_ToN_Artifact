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

"""COMMAND147 P6: one nested-component fidelity smoke cell per invocation.

24 cells = 4 patterns × 3 networks × 2 seeds. Scripted ComponentActuationPlan only.
No learned MD2G. No Loot network. No quality remeasurement.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))
from command137_proc import moq_live  # noqa: E402
from command147_io import dump_dual, token, ts  # noqa: E402
from command147_nested_runtime import (  # noqa: E402
    CONTENT,
    N_USERS,
    PREREQ_TOKENS,
    audit_cell,
    matrix,
)
from command148_canary_audit import finite_headlines  # noqa: E402
from command148_canary_metrics import cell_metrics  # noqa: E402
from command152_executor_lock import release, try_acquire  # noqa: E402

PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
SUDO = REPO / "Sigcomm26" / ".sudo_password.local"
CLUSTER = REPO / "moq_cluster_Sigcomm.py"
ART = TON / "artifacts" / "command147_24cell_smoke"
QUEUE = REPO / "state" / "COMMAND147_24CELL_QUEUE.json"
if os.environ.get("COMMAND151_POST_RB_SMOKE", "").strip().lower() in ("1", "true", "yes"):
    ART = TON / "artifacts" / "command151_24cell_post_rb"
    QUEUE = REPO / "state" / "COMMAND151_24CELL_QUEUE.json"


def load_queue() -> dict:
    if QUEUE.is_file():
        return json.loads(QUEUE.read_text())
    return {
        "token": "COMMAND147_24CELL_QUEUE",
        "completed": [],
        "failed": None,
        "status": "QUEUED",
    }


def save_queue(body: dict) -> None:
    body["ts"] = ts()
    QUEUE.write_text(json.dumps(body, indent=2) + "\n")
    shutil.copy2(QUEUE, TON / "state" / QUEUE.name)


def prereqs_ok() -> list[str]:
    missing = [t for t in PREREQ_TOKENS if not (REPO / "state" / f"{t}.json").is_file()]
    return missing


def env_for(spec: dict, cell_dir: Path) -> dict:
    e = os.environ.copy()
    e.update(
        {
            "TON_NESTED_COMPONENTS": "1",
            "TON_TRUE_CONTENT_LAYERING": "0",
            "TON_FULLREP_STRESS": "0",
            "TON_CONTENT_ID": CONTENT,
            "MM26_CONTENT_ID": CONTENT,
            "COMMAND147_SMOKE_PATTERN": spec["pattern"],
            "COMMAND147_SMOKE_NETWORK": spec["network"],
            "COMMAND147_QUALITY_CONTRACT": str(REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json"),
            "COMMAND146_COMPONENT_DAG": str(REPO / "state" / "COMMAND146_COMPONENT_DAG_CONTRACT.json"),
            "SIGCOMM_BASELINE_SEED": str(spec["seed"]),
            "SIGCOMM_INITIAL_PROBE_S": "3",
            "SIGCOMM_REP_LIFECYCLE_V2": "0",
            "SIGCOMM_NATIVE9REP_DECISION": "0",
            "TON_NATIVE9REP_MD2G": "0",
            "PYTHONUNBUFFERED": "1",
            "SKIP_PING_ALL": "1",
            "MM26_SKIP_PING_ALL": "1",
            "COMMAND151_REQUIRE_PRESSURE": "1" if os.environ.get("COMMAND151_POST_RB_SMOKE") else "0",
            "SIGCOMM_SKIP_PINGALL": "1",
            "PYTHONPATH": str(TON / "lib") + os.pathsep + e.get("PYTHONPATH", ""),
        }
    )
    e.pop("SIGCOMM_REP_LADDER", None)
    e.pop("TON_BITRATE_FAIL_CLOSED", None)
    e.pop("MM26_ADAPTIVE_ADMISSION", None)
    return e


def next_spec(q: dict) -> dict | None:
    done = set(q.get("completed") or [])
    for spec in matrix():
        if spec["key"] in done:
            continue
        if (ART / spec["key"] / "CELL_DONE.json").is_file():
            continue
        return spec
    return None


def main() -> int:
    if not (REPO / "state" / "COMMAND147_COMPONENT_QUALITY_FROZEN.json").is_file():
        print(json.dumps({"pass": False, "reason": "quality_not_frozen"}))
        return 2
    missing = prereqs_ok()
    if missing:
        print(json.dumps({"pass": False, "reason": "prereq_missing", "missing": missing}))
        return 2
    if moq_live():
        print(json.dumps({"pass": False, "reason": "moq_already_live", "wait": True}))
        return 0
    if (REPO / "state" / "COMMAND152_ACTIVE.json").is_file() and os.environ.get(
        "COMMAND152_LAUNCH", ""
    ).strip().lower() not in ("1", "true", "yes"):
        print(json.dumps({"pass": True, "wait": True, "reason": "command152_owns_launches"}))
        return 0
    q = load_queue()
    repair_paths = [
        REPO / "state" / "COMMAND153_EXACT_KEY_RERUN.json",
        REPO / "state" / "COMMAND152_EXACT_KEY_RERUN.json",
        REPO / "state" / "COMMAND147_P6_PERF_CSV_REPAIR.json",
    ]
    repair = None
    if q.get("failed"):
        fk = str((q.get("failed") or {}).get("key") or "")
        for p in repair_paths:
            if not p.is_file():
                continue
            try:
                affected = str(json.loads(p.read_text()).get("affected_key") or "")
            except Exception:
                affected = ""
            if affected != fk:
                continue
            try:
                st = str(json.loads(p.read_text()).get("status") or "").upper()
            except Exception:
                st = ""
            if st == "CONSUMED":
                continue
            repair = p
            break
        if repair is None:
            print(json.dumps({"pass": False, "reason": "paused_previous_fail", "failed": q["failed"]}))
            return 3
    if q.get("failed") and repair is not None:
        fk = str((q.get("failed") or {}).get("key") or "")
        affected = ""
        try:
            affected = str(json.loads(repair.read_text()).get("affected_key") or "")
        except Exception:
            affected = ""
        if affected and fk != affected:
            print(json.dumps({"pass": False, "reason": "paused_unrelated_fail", "failed": q["failed"]}))
            return 3
        preserve_as = ""
        try:
            preserve_as = str(json.loads(repair.read_text()).get("preserve_as") or "")
        except Exception:
            preserve_as = ""
        old = ART / fk
        if old.is_dir() and not (old / "CELL_DONE.json").is_file():
            dest = ART / (preserve_as or f"{fk}_attempt1_missing_perf_csv")
            if dest.exists():
                dest = ART / f"{dest.name}_{int(time.time())}"
            old.rename(dest)
        q["failed"] = None
        q["status"] = "RETRY_AFTER_PERF_CSV_REPAIR"
        q["repair"] = str(repair)
        try:
            rb = json.loads(repair.read_text())
            n_app = int(rb.get("n_applied") or 0) + 1
            if n_app > 3:
                print(json.dumps({"pass": False, "reason": "max_exact_key_repairs", "key": fk, "n_applied": n_app}))
                return 4
            rb["n_applied"] = n_app
            rb["status"] = "CONSUMED"
            repair.write_text(json.dumps(rb, indent=2) + "\n")
            try:
                dump_dual(repair.name, rb)
            except Exception:
                pass
        except Exception:
            pass
        save_queue(q)
    if q.get("failed"):
        print(json.dumps({"pass": False, "reason": "paused_previous_fail", "failed": q["failed"]}))
        return 3
    spec = next_spec(q)
    if spec is None:
        n = len(matrix())
        post = bool(os.environ.get("COMMAND151_POST_RB_SMOKE"))
        if post:
            cmp_py = TON / "scripts" / "command151_24cell_delivery_compare.py"
            rc = subprocess.run([str(PY), "-u", str(cmp_py)], cwd=str(REPO)).returncode
            if rc != 0:
                print(json.dumps({"pass": False, "reason": "delivery_compare_failed", "rc": rc}))
                return 4
            token(
                "COMMAND151_24CELL_POST_RB_FIDELITY_PASS",
                {"n": n, "learned_md2g": False, "loot_network_holdout_sealed": True, "post_rb": True},
            )
        else:
            token(
                "COMMAND147_24CELL_COMPONENT_FIDELITY_SMOKE_PASS",
                {"n": n, "learned_md2g": False, "loot_network_holdout_sealed": True},
            )
        q["status"] = "PASS_24_24"
        q["completed"] = [s["key"] for s in matrix()]
        save_queue(q)
        print(json.dumps({"pass": True, "done": n}))
        return 0
    if not SUDO.is_file():
        print(json.dumps({"pass": False, "reason": "HARD_INFRASTRUCTURE_BLOCK missing sudo"}))
        return 2
    lock_fd = try_acquire(spec["key"], "command147_24cell_fidelity_smoke")
    if lock_fd is None:
        print(json.dumps({"pass": True, "wait": True, "reason": "executor_lock_held"}))
        return 0
    try:
        return _run_cell(q, spec)
    finally:
        release(lock_fd)


def _run_cell(q: dict, spec: dict) -> int:
    cell_dir = ART / spec["key"]
    cell_dir.mkdir(parents=True, exist_ok=True)
    duration = 120
    cmd = [
        "sudo",
        "-S",
        "-E",
        str(PY),
        "-u",
        str(CLUSTER),
        "--clients",
        str(N_USERS),
        "--strategy",
        "heuristic",
        "--network_type",
        spec["network"],
        "--log_path",
        str(cell_dir),
        "--duration",
        str(duration),
        "--interval",
        "1.0",
    ]
    t0 = time.time()
    with SUDO.open("rb") as pw, (cell_dir / "cell_stdout.log").open("w") as out:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            env=env_for(spec, cell_dir),
            stdin=pw,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
    audit = audit_cell(cell_dir, spec, REPO)
    audit["rc"] = proc.returncode
    audit["elapsed_s"] = time.time() - t0
    audit["pattern"] = spec["pattern"]
    audit["network"] = spec["network"]
    audit["seed"] = spec["seed"]
    if os.environ.get("COMMAND151_POST_RB_SMOKE"):
        sp = cell_dir / "PHYSICAL_PRESSURE_TIMESERIES.jsonl"
        audit.setdefault("cases", {})["physical_pressure_timeseries"] = sp.is_file() and sp.stat().st_size > 0
        if not audit["cases"]["physical_pressure_timeseries"]:
            audit["pass"] = False
            audit.setdefault("reasons", []).append("missing PHYSICAL_PRESSURE_TIMESERIES.jsonl")
        mspec = dict(spec)
        mspec["strategy"] = "HV3_COMPONENT"
        try:
            metrics = cell_metrics(cell_dir, mspec)
        except Exception as e:
            metrics = None
            audit["pass"] = False
            audit.setdefault("reasons", []).append(f"metrics_error={e}")
        ok_h, bad = finite_headlines(metrics)
        audit["cases"]["finite_headlines"] = ok_h
        if not ok_h:
            audit["pass"] = False
            audit["class"] = "INVALID_HEADLINE_NONFINITE"
            audit.setdefault("reasons", []).extend(bad)
        if isinstance(metrics, dict):
            (cell_dir / "CELL_METRICS.json").write_text(json.dumps(metrics, indent=2) + "\n")
            audit["Rb"] = metrics.get("Rb")
            audit["Ro_component"] = metrics.get("Ro_component")
            audit["stall_last_status"] = metrics.get("stall_last_status")
    (cell_dir / "CELL_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n")
    if proc.returncode != 0 or not audit.get("pass"):
        q["failed"] = {"key": spec["key"], "audit": audit}
        q["status"] = "FAIL_CLOSED"
        save_queue(q)
        dump_dual(
            "COMMAND151_24CELL_FAIL_CLOSED.json" if os.environ.get("COMMAND151_POST_RB_SMOKE") else "COMMAND147_24CELL_FAIL_CLOSED.json",
            {"ts": ts(), "key": spec["key"], "audit": audit},
        )
        print(json.dumps({"pass": False, "key": spec["key"], "audit": audit}, default=str))
        return 4
    (cell_dir / "CELL_DONE.json").write_text(
        json.dumps({"ts": ts(), "key": spec["key"], "audit": audit}, indent=2) + "\n"
    )
    done = list(q.get("completed") or [])
    if spec["key"] not in done:
        done.append(spec["key"])
    q["completed"] = done
    q["status"] = f"{len(done)}/24"
    q["last_key"] = spec["key"]
    save_queue(q)
    print(json.dumps({"pass": True, "key": spec["key"], "progress": q["status"]}))
    if len(done) >= 24:
        if os.environ.get("COMMAND151_POST_RB_SMOKE"):
            cmp_py = TON / "scripts" / "command151_24cell_delivery_compare.py"
            rc = subprocess.run([str(PY), "-u", str(cmp_py)], cwd=str(REPO)).returncode
            if rc != 0:
                print(json.dumps({"pass": False, "reason": "delivery_compare_failed", "rc": rc}))
                return 4
            token(
                "COMMAND151_24CELL_POST_RB_FIDELITY_PASS",
                {"n": 24, "learned_md2g": False, "loot_network_holdout_sealed": True, "post_rb": True},
            )
        else:
            token(
                "COMMAND147_24CELL_COMPONENT_FIDELITY_SMOKE_PASS",
                {"n": 24, "learned_md2g": False, "loot_network_holdout_sealed": True},
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
