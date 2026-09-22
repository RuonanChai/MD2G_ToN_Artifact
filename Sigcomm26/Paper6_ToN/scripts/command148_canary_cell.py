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

"""One corrected-contract 120-cell canary trial. No Loot. One Mininet."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))
from command137_proc import dash_live, moq_live  # noqa: E402
from command147_io import dump_dual, handle_unsupervised_live_wait, ts  # noqa: E402
from command148_canary120 import QUEUE, matrix  # noqa: E402
from command148_canary_audit import audit_canary_cell  # noqa: E402
from command148_canary_metrics import cell_metrics  # noqa: E402
from command151_pause import new_launch_paused  # noqa: E402
from command152_executor_lock import release, try_acquire  # noqa: E402

PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
SUDO = REPO / "Sigcomm26" / ".sudo_password.local"
CLUSTER = REPO / "moq_cluster_Sigcomm.py"
ART = TON / "artifacts" / "command148_canary120"
if (REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_RELEASE.json").is_file():
    ART = TON / "artifacts" / "command148_canary120_rbv1"
STUDENT = TON / "models" / "command148_component" / "student_component_v1.pt"
MAX_IDENTICAL_RETRIES = 2


def load_q() -> dict:
    if QUEUE.is_file():
        return json.loads(QUEUE.read_text())
    return {"completed": [], "failed": None, "attempts": {}, "invalid": []}


def save_q(q: dict) -> None:
    q["ts"] = ts()
    dump_dual("COMMAND148_CANARY120_QUEUE.json", q)


def archive_attempt(cell: Path, key: str, klass: str, art: Path | None = None) -> Path:
    root = art or ART
    dest = root / f"{key}_{klass}_{int(time.time())}"
    if cell.exists():
        cell.rename(dest)
    return dest


def sanitize_wrong_treatment(q: dict) -> dict:
    done = list(q.get("completed") or [])
    keep = []
    invalid = list(q.get("invalid") or [])
    for key in done:
        spec = next((s for s in matrix() if s["key"] == key), None)
        cell = ART / key
        if spec and spec["strategy"] == "MD2G_COMPONENT":
            inf = cell / "COMMAND148_STUDENT_INFERENCE.jsonl"
            if not inf.is_file() or inf.stat().st_size == 0:
                if cell.is_dir():
                    dest = archive_attempt(cell, key, "INVALID_TREATMENT_MD2G_NOT_STUDENT")
                    invalid.append({"key": key, "class": "INVALID_TREATMENT_MD2G_NOT_STUDENT", "dest": str(dest)})
                continue
        if spec and spec["strategy"] == "MOQ_UNICAST_COMPONENT":
            pubs = list((cell / "publisher_logs").glob("pub_b0.log")) if cell.is_dir() else []
            if pubs:
                dest = archive_attempt(cell, key, "INVALID_SHARED_DELIVERY_IMPLEMENTATION")
                invalid.append({"key": key, "class": "INVALID_SHARED_DELIVERY_IMPLEMENTATION", "dest": str(dest)})
                continue
        if (cell / "CELL_DONE.json").is_file():
            keep.append(key)
    q["completed"] = keep
    q["invalid"] = invalid
    q["status"] = f"{len(keep)}/120"
    return q


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
        q["status"] = f"{len(done)}/{int(q.get('n') or 120)}"
        q["last_key"] = done[-1]
        save_q(q)
    return pending


def exact_key_authorized(key: str) -> dict | None:
    """One AUTHORIZED command153 exact-key token may clear a fail-closed canary key."""
    p = REPO / "state" / "COMMAND153_EXACT_KEY_RERUN.json"
    if not key or not p.is_file():
        return None
    try:
        body = json.loads(p.read_text())
    except Exception:
        return None
    if str(body.get("affected_key") or "") != key:
        return None
    if str(body.get("status") or "").upper() != "AUTHORIZED":
        return None
    if int(body.get("n_applied") or 0) > 3:
        return None
    return body


def consume_exact_key(body: dict) -> None:
    body = dict(body)
    body["n_applied"] = int(body.get("n_applied") or 0) + 1
    body["status"] = "CONSUMED"
    body["ts"] = ts()
    dump_dual("COMMAND153_EXACT_KEY_RERUN.json", body)


def maybe_five_report(n: int) -> None:
    if n > 0 and n % 5 == 0:
        subprocess.run(
            [str(PY), "-u", str(TON / "scripts" / "command148_five_cell_report.py"), str(n)],
            cwd=str(REPO),
            check=False,
        )
        c152 = TON / "scripts" / "command152_reports.py"
        if c152.is_file():
            subprocess.run([str(PY), "-u", str(c152), str(n)], cwd=str(REPO), check=False)
    subprocess.run(
        [str(PY), "-u", str(TON / "scripts" / "command148_canary_block_review.py")],
        cwd=str(REPO),
        check=False,
    )
    c152_lvl = TON / "scripts" / "command152_reports.py"
    if c152_lvl.is_file():
        subprocess.run([str(PY), "-u", str(c152_lvl), "--level2"], cwd=str(REPO), check=False)
    subprocess.run(
        [str(PY), "-u", str(TON / "scripts" / "command148_rb_zero_audit.py")],
        cwd=str(REPO),
        check=False,
    )


def _main_injected(spec_env: str) -> int:
    spec = json.loads(spec_env)
    art = Path(os.environ.get("COMMAND148_ART_ROOT") or str(ART))
    qname = os.environ.get("COMMAND153_QUEUE_NAME") or "COMMAND153_INJECTED_QUEUE.json"
    qp = REPO / "state" / qname
    q = json.loads(qp.read_text()) if qp.is_file() else {"completed": [], "failed": None, "attempts": {}, "invalid": []}
    if spec.get("content") == "loot" and not (REPO / "state" / "COMMAND153_FINAL_DEV_FROZEN.json").is_file():
        print(json.dumps({"pass": False, "reason": "loot_sealed"}))
        return 2
    attempts = dict(q.get("attempts") or {})
    n_try = int(attempts.get(spec["key"]) or 0)
    cell = art / spec["key"]
    if cell.exists() and not (cell / "CELL_DONE.json").is_file():
        archive_attempt(cell, spec["key"], f"attempt{n_try or 1}_incomplete", art=art)
        cell = art / spec["key"]
    cell.mkdir(parents=True, exist_ok=True)
    lock_fd = try_acquire(spec["key"], "command148_canary_cell")
    if lock_fd is None:
        print(json.dumps({"pass": True, "wait": True, "reason": "executor_lock_held"}))
        return 0

    def _save(body: dict) -> None:
        body["ts"] = ts()
        dump_dual(qname, body)

    try:
        return _run_canary_cell(q, spec, cell, attempts, n_try, art=art, save=_save, do_five_report=False)
    finally:
        release(lock_fd)


def main() -> int:
    paused, token = new_launch_paused()
    if paused:
        print(json.dumps({"pass": True, "paused": token, "wait": True, "no_new_cell": True, "kill_live_cell": False}))
        return 0
    if not (REPO / "state" / "COMMAND148_TEACHER_STUDENT_READY.json").is_file():
        print(json.dumps({"pass": False, "reason": "teacher_not_ready"}))
        return 2
    if not (REPO / "state" / "COMMAND148_CANARY_NOISE_MARGINS_PREDECLARED.json").is_file():
        subprocess.run([str(PY), "-u", str(TON / "scripts" / "command148_predeclare_noise_margins.py")], cwd=str(REPO))
    leftover = handle_unsupervised_live_wait()
    if leftover == 3:
        print(json.dumps({"pass": False, "reason": "unsupervised_live_after_lock_dead", "kill_live_cell": False}))
        return 3
    if leftover == 0:
        print(json.dumps({"pass": True, "wait": True, "reason": "unsupervised_live_grace", "kill_live_cell": False}))
        return 0
    if moq_live() or dash_live():
        print(json.dumps({"pass": False, "reason": "executor_already_live", "wait": True}))
        return 0
    if (REPO / "state" / "COMMAND152_ACTIVE.json").is_file() and os.environ.get(
        "COMMAND152_LAUNCH", ""
    ).strip().lower() not in ("1", "true", "yes"):
        print(json.dumps({"pass": True, "wait": True, "reason": "command152_owns_launches"}))
        return 0
    spec_env = os.environ.get("COMMAND148_SPEC_JSON", "").strip()
    if spec_env:
        # DEV/scaling/loot injected launches must not rewrite the rbv1 canary queue.
        return _main_injected(spec_env)
    q = sanitize_wrong_treatment(load_q())
    fail = q.get("failed")
    if fail:
        klass = str((fail.get("audit") or {}).get("class") or fail.get("class") or "")
        fk = str(fail.get("key") or "")
        n_att = int((q.get("attempts") or {}).get(fk) or 0)
        auth = exact_key_authorized(fk)
        retryable = "TREATMENT" in klass or (
            klass.startswith("INVALID_EXECUTION")
            and "FIDELITY" not in klass
            and n_att <= MAX_IDENTICAL_RETRIES
        )
        if auth is not None:
            consume_exact_key(auth)
            q["failed"] = None
            q["status"] = f"RETRY_AUTHORIZED_{fk}"
            save_q(q)
        elif retryable:
            q["failed"] = None
        elif n_att > MAX_IDENTICAL_RETRIES and klass.startswith("INVALID_EXECUTION"):
            save_q(q)
            print(json.dumps({"pass": False, "reason": "max_execution_retries", "failed": fail}))
            return 4
        else:
            save_q(q)
            classify = TON / "scripts" / "command153_classify_and_repair.py"
            if classify.is_file():
                subprocess.run([str(PY), "-u", str(classify)], cwd=str(REPO), check=False)
                auth2 = exact_key_authorized(fk)
                if auth2 is not None:
                    consume_exact_key(auth2)
                    q["failed"] = None
                    q["status"] = f"RETRY_AUTHORIZED_{fk}"
                    save_q(q)
                else:
                    print(json.dumps({"pass": False, "reason": "paused_previous_fail", "failed": fail, "ledger": True}))
                    return 3
            else:
                print(json.dumps({"pass": False, "reason": "paused_previous_fail", "failed": fail, "ledger": True}))
                return 3
    save_q(q)
    spec = next_spec(q)
    if spec is None:
        n = len(q.get("completed") or [])
        dump_dual(
            "COMMAND148_CANARY120_COMPLETE.json",
            {"ts": ts(), "n": n, "status": "PENDING_V1_AGGREGATE_GATE", "loot_sealed": True},
        )
        if n >= 120:
            return subprocess.run(
                [str(PY), "-u", str(TON / "scripts" / "command148_canary_v1_gate.py")],
                cwd=str(REPO),
            ).returncode
        print(json.dumps({"pass": True, "done": n, "pending": "incomplete_queue"}))
        return 0
    if spec["content"] == "loot" and not (REPO / "state" / "COMMAND153_FINAL_DEV_FROZEN.json").is_file():
        print(json.dumps({"pass": False, "reason": "loot_sealed"}))
        return 2
    attempts = dict(q.get("attempts") or {})
    n_try = int(attempts.get(spec["key"]) or 0)
    cell = ART / spec["key"]
    if cell.exists() and not (cell / "CELL_DONE.json").is_file():
        archive_attempt(cell, spec["key"], f"attempt{n_try or 1}_incomplete")
        cell = ART / spec["key"]
    cell.mkdir(parents=True, exist_ok=True)
    lock_fd = try_acquire(spec["key"], "command148_canary_cell")
    if lock_fd is None:
        print(json.dumps({"pass": True, "wait": True, "reason": "executor_lock_held"}))
        return 0
    try:
        return _run_canary_cell(q, spec, cell, attempts, n_try)
    finally:
        release(lock_fd)


def _run_canary_cell(
    q: dict,
    spec: dict,
    cell: Path,
    attempts: dict,
    n_try: int,
    *,
    art: Path | None = None,
    save=None,
    do_five_report: bool = True,
) -> int:
    art = art or ART
    save = save or save_q
    env = os.environ.copy()
    env.update(
        {
            "TON_NESTED_COMPONENTS": "1",
            "TON_TRUE_CONTENT_LAYERING": "0",
            "TON_CONTENT_ID": spec["content"],
            "MM26_CONTENT_ID": spec["content"],
            "COMMAND148_STRATEGY": spec["strategy"],
            "COMMAND148_NETWORK": spec["network"],
            "COMMAND148_CELL_DIR": str(cell),
            "COMMAND148_STUDENT_PATH": str(STUDENT),
            "COMMAND147_QUALITY_CONTRACT": str(REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json"),
            "SIGCOMM_BASELINE_SEED": str(spec["seed"]),
            "SIGCOMM_REP_LIFECYCLE_V2": "0",
            "TON_NATIVE9REP_MD2G": "0",
            "PYTHONUNBUFFERED": "1",
            "SKIP_PING_ALL": "1",
            "MM26_SKIP_PING_ALL": "1",
            "SIGCOMM_SKIP_PINGALL": "1",
            "PYTHONPATH": str(TON / "lib") + os.pathsep + str(TON) + os.pathsep + env.get("PYTHONPATH", ""),
        }
    )
    if spec["strategy"] == "MOQ_UNICAST_COMPONENT":
        env["COMMAND148_UNICAST"] = "1"
    env.pop("SIGCOMM_REP_LADDER", None)
    if (REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_RELEASE.json").is_file():
        env["COMMAND151_REQUIRE_PRESSURE"] = "1"
    cmd = [
        "sudo", "-S", "-E", str(PY), "-u", str(CLUSTER),
        "--clients", str(spec["users"]),
        "--strategy", "heuristic",
        "--network_type", spec["network"],
        "--log_path", str(cell),
        "--duration", "120",
        "--interval", "1.0",
    ]
    t0 = time.time()
    with SUDO.open("rb") as pw, (cell / "cell_stdout.log").open("w") as out:
        proc = subprocess.run(cmd, cwd=str(REPO), env=env, stdin=pw, stdout=out, stderr=subprocess.STDOUT)
    metrics = None
    try:
        metrics = cell_metrics(cell, spec)
    except Exception as e:
        (cell / "CELL_METRICS_ERROR.txt").write_text(str(e) + "\n")
        metrics = None
    if isinstance(metrics, dict):
        (cell / "CELL_METRICS.json").write_text(json.dumps(metrics, indent=2) + "\n")
    audit = audit_canary_cell(cell, spec, metrics)
    rec = {
        "ts": ts(),
        "key": spec["key"],
        "rc": proc.returncode,
        "elapsed_s": time.time() - t0,
        "audit": audit,
        **spec,
    }
    if isinstance(metrics, dict):
        rec["metrics"] = metrics
        (cell / "CELL_METRICS.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (cell / "CELL_AUDIT.json").write_text(json.dumps(rec, indent=2) + "\n")
    attempts[spec["key"]] = n_try + 1
    q["attempts"] = attempts
    if proc.returncode != 0 or not audit.get("pass"):
        klass = str(audit.get("class") or "INVALID_EXECUTION")
        dest = archive_attempt(cell, spec["key"], klass, art=art)
        rec["archived"] = str(dest)
        inv = list(q.get("invalid") or [])
        inv.append({"key": spec["key"], "class": klass, "dest": str(dest), "n_try": n_try + 1})
        q["invalid"] = inv
        execution = klass.startswith("INVALID_EXECUTION") and "FIDELITY" not in klass
        if execution and (n_try + 1) <= MAX_IDENTICAL_RETRIES:
            q["failed"] = None
            q["status"] = f"RETRY_{spec['key']}_{n_try + 1}"
            save(q)
            print(json.dumps({"pass": False, "retry": True, **rec}, default=str))
            return 0
        q["failed"] = rec
        q["status"] = "FAIL_CLOSED"
        save(q)
        fail_name = "COMMAND148_CANARY_FAIL_CLOSED.json" if do_five_report else "COMMAND153_INJECTED_FAIL_CLOSED.json"
        dump_dual(fail_name, rec)
        print(json.dumps({"pass": False, **rec}, default=str))
        return 4
    rec["valid"] = True
    # Provenance only: stamp frozen post-instrumentation epoch; does not change U/Q/Rb.
    ep = REPO / "state" / "COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE.json"
    if ep.is_file():
        try:
            epb = json.loads(ep.read_text())
            eid = epb.get("epoch_id") or epb.get("epoch")
            if eid:
                rec["epoch_id"] = eid
        except Exception:
            pass
    (cell / "CELL_DONE.json").write_text(json.dumps(rec, indent=2) + "\n")
    # Retention contract: INVALID dumps never deleted here; VALID may hash+delete
    # unless sentinel. Never interrupt a still-running cell (this runs post-VALID only).
    try:
        from command153_raw_dump_retention import reclaim_valid_dumps_if_allowed  # noqa: PLC0415

        reclaim_valid_dumps_if_allowed(cell, cell_key=spec["key"], epoch_id=rec.get("epoch_id"))
    except Exception as exc:
        (cell / "RAW_DUMP_RETENTION_ERROR.json").write_text(
            json.dumps({"pass": False, "error": str(exc), "kept_dumps": True}, indent=2) + "\n"
        )
    done = list(q.get("completed") or [])
    if spec["key"] not in done:
        done.append(spec["key"])
    q["completed"] = done
    q["failed"] = None
    if q.get("n") is None:
        env_n = os.environ.get("COMMAND148_QUEUE_N", "").strip()
        if env_n.isdigit():
            q["n"] = int(env_n)
        elif do_five_report:
            q["n"] = 120
    denom = int(q.get("n") or len(done))
    q["status"] = f"{len(done)}/{denom}"
    q["last_key"] = spec["key"]
    save(q)
    if do_five_report:
        maybe_five_report(len(done))
    print(json.dumps({"pass": True, "key": spec["key"], "progress": q["status"], "U": (metrics or {}).get("U")}))
    if do_five_report and len(done) >= 120:
        six_q = TON / "scripts" / "command153_canary_six_questions.py"
        if six_q.is_file():
            subprocess.run(
                [str(PY), "-u", str(six_q), "--final"],
                cwd=str(REPO),
                check=False,
            )
        return subprocess.run(
            [str(PY), "-u", str(TON / "scripts" / "command148_canary_v1_gate.py")],
            cwd=str(REPO),
        ).returncode
    if (not do_five_report) and os.environ.get("COMMAND148_STAGE") == "main_dev":
        dev_rep = TON / "scripts" / "command153_dev_reports.py"
        if dev_rep.is_file():
            subprocess.run([str(PY), "-u", str(dev_rep)], cwd=str(REPO), check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
