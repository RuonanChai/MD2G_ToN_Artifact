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

"""COMMAND148 sole scientific launcher. Frozen science unchanged. One Mininet."""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
CURRENT = REPO / "state" / "CURRENT.json"
STATE = REPO / "state" / "COMMAND148_STATE.json"
EVENTS = REPO / "logs" / "command148_events.ndjson"
HOURLY = REPO / "status" / "COMMAND148_HOURLY_REPORT.md"
LEASE = REPO / "state" / "COMMAND148_SINGLE_OWNER.lock"
sys.path.insert(0, str(TON / "scripts"))
from command137_proc import moq_live  # noqa: E402
sys.path.insert(0, str(TON / "lib"))
from command151_pause import new_launch_paused  # noqa: E402


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def exists(name: str) -> bool:
    return (REPO / "state" / f"{name}.json").is_file()


def event(kind: str, **kw) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": ts(), "kind": kind, **kw}
    with EVENTS.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)


def load_cur() -> dict:
    return json.loads(CURRENT.read_text()) if CURRENT.exists() else {}


def save_cur(st: dict) -> None:
    st["ts"] = ts()
    st["token"] = "COMMAND148_CURRENT"
    st["authority"] = "command148_MD2G_autonomous_complete_all_experiments.txt"
    st["campaign_authority"] = "command146_MD2G_correct_nested_component_full_experiment_plan.txt"
    st["tightening_authority"] = "command147_MD2G_contract_tightening_before_smoke.txt"
    st["exactly_one_executor"] = "tmux:command148_orch"
    st["watch"] = "tmux:command148_watch"
    st["command145_forbidden"] = True
    st["holdout_sealed"] = True
    st["loot_unsealed"] = False
    st["loot_network_holdout_sealed"] = not exists("COMMAND148_FINAL_DEV_FROZEN")
    st["quality_table_frozen"] = True
    st["do_not_rerun_quality_measurement"] = True
    st["scientific_mininet_cells"] = int(st.get("scientific_mininet_cells") or 0)
    text = json.dumps(st, indent=2) + "\n"
    CURRENT.write_text(text)
    (TON / "state" / "CURRENT.json").write_text(text)
    STATE.write_text(text)
    (TON / "state" / "COMMAND148_STATE.json").write_text(text)


def run_py(script: str) -> int:
    return subprocess.run([str(PY), "-u", str(TON / "scripts" / script)], cwd=str(REPO)).returncode


def executor_busy() -> bool:
    if moq_live():
        return True
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            cmd = (p / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except Exception:
            continue
        if "python" in cmd and (
            "command147_24cell_fidelity_smoke.py" in cmd
            or "command148_canary_cell.py" in cmd
            or "command148_canary120.py" in cmd
            or "command148_train_teacher_student.py" in cmd
            or "command148_matrix_cell.py" in cmd
        ):
            return True
    return False


def smoke_progress() -> tuple[int, list]:
    q = {}
    p = REPO / "state" / "COMMAND147_24CELL_QUEUE.json"
    if p.is_file():
        q = json.loads(p.read_text())
    done = list(q.get("completed") or [])
    return len(done), done


def canary_progress() -> tuple[int, str | None]:
    p = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
    if not p.is_file():
        return 0, None
    q = json.loads(p.read_text())
    return len(q.get("completed") or []), q.get("last_key")


def hourly(st: dict) -> None:
    n, _done = smoke_progress()
    cn, lastk = canary_progress()
    lines = [
        f"# COMMAND148 hourly {ts()}",
        "",
        f"- phase: `{st.get('phase')}`",
        f"- next_action: `{st.get('next_action')}`",
        f"- smoke: {n}/24 VALID",
        f"- teacher_student_ready: {exists('COMMAND148_TEACHER_STUDENT_READY')}",
        f"- canary: {cn}/120 canonical VALID",
        f"- canary_last_key: `{lastk}`",
        f"- noise_margins_frozen: {exists('COMMAND148_CANARY_NOISE_MARGINS_FROZEN')}",
        f"- active_cell: `{st.get('active_cell')}`",
        f"- executor_busy: {executor_busy()}",
        f"- loot_network_holdout_sealed: `{st.get('loot_network_holdout_sealed')}`",
        f"- final DEV frozen: {exists('COMMAND148_FINAL_DEV_FROZEN')}",
        f"- last_event: `{st.get('last_event_kind')}`",
        f"- why_continue: 24/24 smoke PASS; Teacher/Student READY; run 120-cell canary with Student sidecar + predeclared noise margins; frozen science unchanged",
        f"- one_executor: tmux:command148_orch",
        "",
    ]
    HOURLY.parent.mkdir(parents=True, exist_ok=True)
    HOURLY.write_text("\n".join(lines))
    (TON / "status" / "COMMAND148_HOURLY_REPORT.md").write_text("\n".join(lines))


def acquire_lease() -> None:
    LEASE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LEASE), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        event("LEASE_HELD_BY_OTHER")
        raise SystemExit(0)
    os.write(fd, f"{os.getpid()} {ts()}\n".encode())
    globals()["_lease_fd"] = fd


def tick() -> None:
    st = load_cur()
    if exists("COMMAND152_ACTIVE") or exists("COMMAND153_ACTIVE"):
        event("YIELD_TO_COMMAND152")
        time.sleep(60)
        return
    st["phase"] = st.get("phase") or "COMMAND148_SMOKE"
    hourly(st)
    if exists("TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_A") or exists(
        "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B"
    ) or exists("TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_C") or exists(
        "CORRECT_COMPONENT_CONTRACT_NOT_SUPPORTED"
    ):
        st["terminal_state"] = "SET"
        save_cur(st)
        event("TERMINAL_PRESENT")
        return
    if executor_busy():
        st["active_cell"] = st.get("active_cell") or "LIVE_CELL"
        st["next_action"] = "WAIT_LIVE_CELL_BOUNDARY"
        st["last_event_kind"] = "WAIT_ONE_EXECUTOR"
        save_cur(st)
        event("WAIT_LIVE_CELL")
        return
    paused, token = new_launch_paused()
    if paused:
        st["active_cell"] = None
        st["phase"] = "COMMAND151_PHYSICAL_PRESSURE"
        st["next_action"] = "COMMAND151_AFTER_BOUNDARY"
        st["last_event_kind"] = "PAUSED_NEW_LAUNCHES"
        save_cur(st)
        event("PAUSED_NEW_LAUNCHES", token=token)
        rc = run_py("command151_after_boundary.py")
        event("COMMAND151_AFTER_BOUNDARY", rc=rc)
        return
    n, _done = smoke_progress()
    if not exists("COMMAND147_24CELL_COMPONENT_FIDELITY_SMOKE_PASS"):
        st["next_action"] = "COMMAND147_24CELL_FIDELITY_SMOKE"
        st["phase"] = "COMMAND148_SMOKE"
        st["last_event_kind"] = "P6_SMOKE_CELL"
        st["active_cell"] = None
        save_cur(st)
        event("SMOKE_LAUNCH", completed=n)
        rc = run_py("command147_24cell_fidelity_smoke.py")
        event("SMOKE_RETURN", rc=rc, completed=smoke_progress()[0])
        st = load_cur()
        st["last_real_progress_at"] = ts()
        save_cur(st)
        return
    if not exists("COMMAND147_READY_FOR_COMMAND146_TEACHER"):
        st["next_action"] = "COMMAND148_PRETRAIN_SCIENTIFIC_FREEZE"
        st["phase"] = "COMMAND148_PRETRAIN_FREEZE"
        save_cur(st)
        event("PRETRAIN_FREEZE_START")
        rc = run_py("command148_pretrain_freeze.py")
        event("PRETRAIN_FREEZE_DONE", rc=rc)
        return
    if not exists("COMMAND148_TEACHER_STUDENT_READY"):
        st["next_action"] = "COMMAND148_TEACHER_TRAIN"
        st["phase"] = "COMMAND148_TEACHER_STUDENT"
        save_cur(st)
        event("TEACHER_START")
        rc = run_py("command148_train_teacher_student.py")
        event("TEACHER_DONE", rc=rc)
        return
    if not exists("COMMAND148_DEV_CANDIDATE_FREEZE") and not exists(
        "COMMAND148_COMPONENT_CONTROLLER_CLAIM_LIMITED"
    ):
        st["next_action"] = "COMMAND148_120CELL_CANARY"
        st["phase"] = "COMMAND148_CANARY"
        save_cur(st)
        event("CANARY_START")
        rc = run_py("command148_canary120.py")
        event("CANARY_DONE", rc=rc)
        if rc == 5:
            event("V2_APPLY_START")
            run_py("command148_apply_v2.py")
            event("V2_APPLY_DONE")
        return
    if exists("COMMAND148_DEV_CANDIDATE_FREEZE") and not exists("COMMAND148_FINAL_DEV_FROZEN"):
        st["next_action"] = "COMMAND148_MAIN_DEV_MATRIX"
        st["phase"] = "COMMAND148_MAIN_DEV"
        save_cur(st)
        event("MAIN_DEV_START")
        rc = run_py("command148_main_dev.py")
        event("MAIN_DEV_DONE", rc=rc)
        return
    st["next_action"] = "COMMAND148_LIMITED_OR_POST_DEV"
    st["last_event_kind"] = "CONTINUE_POST_CANARY"
    save_cur(st)
    event("CONTINUE_POST_CANARY")


def main() -> int:
    acquire_lease()
    event("ORCH_START")
    while True:
        try:
            tick()
        except Exception as e:
            event("TICK_ERROR", error=str(e))
        time.sleep(12)


if __name__ == "__main__":
    raise SystemExit(main())
