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

"""Sole production supervisor for command152. Survives SSH. One Mininet."""
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
sys.path.insert(0, str(TON / "scripts"))
from command137_proc import dash_live, moq_live  # noqa: E402
sys.path.insert(0, str(TON / "lib"))
from command147_io import dump_dual, dump_status, ts  # noqa: E402

EVENTS = TON / "logs" / "command152_events.ndjson"
CURRENT = REPO / "state" / "CURRENT.json"
HOURLY = REPO / "status" / "COMMAND152_HOURLY_REPORT.md"
TERMINALS = [
    "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_A",
    "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B",
    "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_C",
    "CORRECT_COMPONENT_CONTRACT_NOT_SUPPORTED",
    "COMMAND152_SCIENTIFIC_CONTRACT_BLOCKED",
    "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
]


def exists(name: str) -> bool:
    return (REPO / "state" / f"{name}.json").is_file()


def event(kind: str, **kw) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": ts(), "kind": kind, **kw}
    with EVENTS.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)


def save_cur(st: dict) -> None:
    st["ts"] = ts()
    st["token"] = "COMMAND153_CURRENT"
    st["authority"] = "command153_anti_regression_autonomous_to_final_evidence.txt"
    st["exactly_one_executor"] = "tmux:command152_orch"
    st["watch"] = "tmux:command152_watch"
    st["loot_network_holdout_sealed"] = True
    st["v2_consumed"] = False
    if st.get("next_action") in (
        "COMMAND148_CANARY_CELL",
        "COMMAND148_MAIN_DEV_CELL",
        "COMMAND153_CONTINUE_APPLICABLE_PHASE",
    ) and st.get("phase") not in ("COMMAND152_WAIT_CELL",):
        st["last_real_progress_at"] = ts()
        st["last_event_kind"] = str(st.get("next_action") or "PROGRESS")
    text = json.dumps(st, indent=2) + "\n"
    CURRENT.write_text(text)
    (TON / "state" / "CURRENT.json").write_text(text)
    dump_dual("COMMAND152_STATE.json", st)


def env_launch() -> dict:
    e = os.environ.copy()
    e["COMMAND152_LAUNCH"] = "1"
    e["PYTHONUNBUFFERED"] = "1"
    return e


def run_py(script: str, extra_env: dict | None = None) -> int:
    env = env_launch()
    if extra_env:
        env.update(extra_env)
    return subprocess.run([str(PY), "-u", str(TON / "scripts" / script)], cwd=str(REPO), env=env).returncode


def hourly(st: dict) -> None:
    q24 = {}
    p24 = REPO / "state" / "COMMAND151_24CELL_QUEUE.json"
    if p24.is_file():
        q24 = json.loads(p24.read_text())
    cq = {}
    cqp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
    if cqp.is_file():
        cq = json.loads(cqp.read_text())
    done = list(cq.get("completed") or [])
    last5 = done[-5:]
    n_done = len(done)
    n_inv = len(cq.get("invalid") or [])
    n_left = max(0, 120 - n_done)
    eta_min = n_left * 4
    lines = [
        f"# COMMAND152 hourly {ts()}",
        "",
        f"- phase: `{st.get('phase')}`",
        f"- next_action: `{st.get('next_action')}`",
        f"- post_rb_24cell: `{q24.get('status')}` last=`{q24.get('last_key')}`",
        f"- canary: `{cq.get('status')}` last=`{cq.get('last_key')}`",
        f"- main_dev: `{json.loads((REPO / 'state' / 'COMMAND148_MAINDEV_QUEUE.json').read_text()).get('status') if (REPO / 'state' / 'COMMAND148_MAINDEV_QUEUE.json').is_file() else 'absent'}`",
        f"- last_five_valid: `{last5}`",
        f"- valid={n_done} invalid_attempts={n_inv} reruns={sum((cq.get('attempts') or {}).values()) if isinstance(cq.get('attempts'), dict) else 0}",
        f"- eta_canary_min_approx: {eta_min} (4min/cell remaining={n_left})",
        f"- completeness: {exists('COMMAND152_FINAL_METRIC_COMPLETENESS_PASS')}",
        f"- known_failures_ledger: {exists('COMMAND153_KNOWN_FAILURES_AND_FIXES')}",
        f"- metric_confirm: {exists('COMMAND153_FINAL_METRIC_CONTRACT_CONFIRM')}",
        f"- epoch_freeze: {exists('COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE')}",
        f"- post_rb_release: {exists('COMMAND151_POST_RB_RELEASE')}",
        f"- moq_live: {moq_live()}",
        f"- loot_sealed: true",
        f"- v2_consumed: false",
        f"- why_continue: consult known-failure ledger; rbv1 120 then DEV/scaling/holdout; no tuning",
        f"- one_executor: tmux:command152_orch",
        "",
    ]
    dump_status("COMMAND152_HOURLY_REPORT.md", "\n".join(lines))
    HOURLY.parent.mkdir(parents=True, exist_ok=True)
    HOURLY.write_text("\n".join(lines))
    subprocess.run(
        [str(PY), "-u", str(TON / "scripts" / "command152_reports.py"), "--level2"],
        cwd=str(REPO),
        env=env_launch(),
        check=False,
    )


def tick() -> int:
    st = {}
    if CURRENT.is_file():
        try:
            st = json.loads(CURRENT.read_text())
        except Exception:
            st = {}
    st["authority"] = "command153_anti_regression_autonomous_to_final_evidence.txt"
    hourly(st)
    dump_status("COMMAND153_HOURLY_REPORT.md", (REPO / "status" / "COMMAND152_HOURLY_REPORT.md").read_text() if (REPO / "status" / "COMMAND152_HOURLY_REPORT.md").is_file() else "")
    for term in TERMINALS:
        if exists(term):
            st["terminal_state"] = term
            st["next_action"] = "STOP"
            save_cur(st)
            event("TERMINAL_PRESENT", token=term)
            return 0
    if moq_live() or dash_live():
        st["next_action"] = "WAIT_LIVE_CELL_BOUNDARY"
        st["phase"] = "COMMAND152_WAIT_CELL"
        save_cur(st)
        event("WAIT_LIVE_CELL")
        return 30
    if not exists("COMMAND153_KNOWN_FAILURES_AND_FIXES"):
        st["phase"] = "COMMAND153_LEDGER"
        st["next_action"] = "WRITE_KNOWN_FAILURES_LEDGER"
        save_cur(st)
        event("LEDGER_START")
        rc = run_py("command153_ledger.py")
        event("LEDGER_DONE", rc=rc)
        return 5 if rc == 0 else 20
    if not exists("COMMAND152_FINAL_METRIC_COMPLETENESS_PASS"):
        st["phase"] = "COMMAND152_METRIC_COMPLETENESS"
        st["next_action"] = "COMMAND152_METRIC_COMPLETENESS"
        save_cur(st)
        event("COMPLETENESS_START")
        rc = run_py("command152_metric_completeness.py")
        event("COMPLETENESS_DONE", rc=rc)
        return 5 if rc == 0 else 20
    if not exists("COMMAND153_FINAL_METRIC_CONTRACT_CONFIRM"):
        st["phase"] = "COMMAND153_METRIC_CONFIRM"
        st["next_action"] = "COMMAND153_METRIC_CONFIRM"
        save_cur(st)
        event("METRIC_CONFIRM_START")
        rc = run_py("command153_metric_confirm.py")
        event("METRIC_CONFIRM_DONE", rc=rc)
        return 5 if rc == 0 else 20
    if not exists("COMMAND151_24CELL_POST_RB_FIDELITY_PASS"):
        st["phase"] = "COMMAND151_POST_RB_24CELL"
        st["next_action"] = "COMMAND151_24CELL_POST_RB"
        save_cur(st)
        q24 = {}
        p24 = REPO / "state" / "COMMAND151_24CELL_QUEUE.json"
        if p24.is_file():
            q24 = json.loads(p24.read_text())
        failed_key = str(((q24.get("failed") or {}) or {}).get("key") or "")
        rerun_p = REPO / "state" / "COMMAND153_EXACT_KEY_RERUN.json"
        match = False
        if failed_key and rerun_p.is_file():
            try:
                body = json.loads(rerun_p.read_text())
            except Exception:
                body = {}
            same = str(body.get("affected_key") or "") == failed_key
            status = str(body.get("status") or "").upper()
            n_app = int(body.get("n_applied") or 0)
            # AUTHORIZED tokens may launch once. CONSUMED or already-applied
            # E013/legacy tokens must re-enter classify (no blind retry).
            if same and status == "AUTHORIZED":
                match = True
            elif same and status == "CONSUMED":
                match = False
            elif same and not status and n_app < 1:
                match = True
            else:
                match = False
        if failed_key and not match:
            event("LEDGER_CONSULT_BEFORE_REPAIR", key=failed_key)
            rc = run_py("command153_classify_and_repair.py")
            event("CLASSIFY_DONE", rc=rc, key=failed_key)
            return 20
        event("POST_RB_24CELL_START")
        rc = run_py("command147_24cell_fidelity_smoke.py", {"COMMAND151_POST_RB_SMOKE": "1", "COMMAND151_REQUIRE_PRESSURE": "1"})
        event("POST_RB_24CELL_DONE", rc=rc)
        return 8 if rc == 0 else 20
    if not exists("COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE"):
        st["phase"] = "COMMAND152_EPOCH_FREEZE"
        st["next_action"] = "COMMAND152_EPOCH_FREEZE"
        save_cur(st)
        event("EPOCH_FREEZE_START")
        rc = run_py("command152_epoch_freeze.py")
        event("EPOCH_FREEZE_DONE", rc=rc)
        return 5
    if not exists("COMMAND151_PHYSICAL_PRESSURE_RELEASE") or not exists("COMMAND151_POST_RB_RELEASE"):
        st["phase"] = "COMMAND151_POST_RB_RELEASE"
        st["next_action"] = "COMMAND151_AFTER_BOUNDARY_RELEASE"
        save_cur(st)
        event("RELEASE_START")
        rc = run_py("command151_after_boundary.py")
        event("RELEASE_DONE", rc=rc)
        return 8
    if (
        exists("COMMAND151_PHYSICAL_PRESSURE_RELEASE")
        and exists("COMMAND151_POST_RB_RELEASE")
        and not exists("COMMAND148_DEV_CANDIDATE_FREEZE")
        and not exists("COMMAND152_CANARY_V1_PROMOTED")
    ):
        st["phase"] = "COMMAND148_CANARY120_RBV1"
        st["next_action"] = "COMMAND148_CANARY_CELL"
        save_cur(st)
        event("CANARY_CELL_START")
        rc = run_py("command148_canary120.py")
        event("CANARY_CELL_DONE", rc=rc)
        if rc not in (0,) and not moq_live():
            cq = {}
            cqp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
            if cqp.is_file():
                cq = json.loads(cqp.read_text())
            failed_key = str(((cq.get("failed") or {}) or {}).get("key") or "")
            if failed_key:
                event("LEDGER_CONSULT_BEFORE_CANARY_REPAIR", key=failed_key)
                run_py("command153_classify_and_repair.py")
            return 20
        cq = {}
        cqp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
        if cqp.is_file():
            cq = json.loads(cqp.read_text())
        if len(cq.get("completed") or []) >= 120 and not exists("COMMAND148_DEV_CANDIDATE_FREEZE"):
            event("V1_GATE_START")
            rcg = run_py("command148_canary_v1_gate.py")
            event("V1_GATE_DONE", rc=rcg)
            return 8
        return 8
    if exists("COMMAND148_CANARY120_COMPLETE") and not exists("COMMAND148_DEV_CANDIDATE_FREEZE"):
        st["phase"] = "COMMAND148_CANARY_V1_GATE"
        st["next_action"] = "COMMAND148_CANARY_V1_GATE"
        save_cur(st)
        event("V1_GATE_START")
        rc = run_py("command148_canary_v1_gate.py")
        event("V1_GATE_DONE", rc=rc)
        return 8
    if exists("COMMAND148_DEV_CANDIDATE_FREEZE") and not exists("COMMAND148_MAINDEV_COMPLETE") and not exists("COMMAND148_FINAL_DEV_FROZEN") and not exists("COMMAND153_FINAL_DEV_FROZEN"):
        st["phase"] = "COMMAND148_MAIN_DEV"
        st["next_action"] = "COMMAND148_MAIN_DEV_CELL"
        save_cur(st)
        event("MAIN_DEV_START")
        rc = run_py("command148_main_dev.py")
        event("MAIN_DEV_DONE", rc=rc)
        if rc not in (0,) and not moq_live() and not dash_live():
            mq = {}
            mqp = REPO / "state" / "COMMAND148_MAINDEV_QUEUE.json"
            if mqp.is_file():
                mq = json.loads(mqp.read_text())
            failed_key = str(((mq.get("failed") or {}) or {}).get("key") or "")
            if failed_key:
                event("LEDGER_CONSULT_BEFORE_MAINDEV_REPAIR", key=failed_key)
                run_py("command153_classify_and_repair.py")
            return 20
        return 8
    if exists("COMMAND148_MAINDEV_COMPLETE") or exists("COMMAND153_FINAL_DEV_FROZEN"):
        terms = [
            "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_A",
            "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B",
            "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_C",
            "CORRECT_COMPONENT_CONTRACT_NOT_SUPPORTED",
            "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
        ]
        if not any(exists(t) for t in terms):
            st["phase"] = "COMMAND153_CONTINUE"
            st["next_action"] = "COMMAND153_CONTINUE_APPLICABLE_PHASE"
            save_cur(st)
            event("CONTINUE_START")
            rc = run_py("command153_continue.py")
            event("CONTINUE_DONE", rc=rc)
            return 8 if rc == 0 else 20
    st["phase"] = "COMMAND153_POST_CANARY"
    st["next_action"] = "COMMAND153_CONTINUE_APPLICABLE_PHASE"
    save_cur(st)
    event("POST_CANARY_CONTINUE")
    return 60


def main() -> int:
    dump_dual(
        "COMMAND153_ACTIVE.json",
        {
            "ts": ts(),
            "token": "COMMAND153_ACTIVE",
            "exactly_one_executor": "tmux:command152_orch",
            "watch": "tmux:command152_watch",
            "command148_orch": "subordinate_no_independent_launch",
            "consult_known_failures_before_repair": True,
            "loot_sealed": True,
        },
    )
    dump_dual(
        "COMMAND152_ACTIVE.json",
        {
            "ts": ts(),
            "token": "COMMAND152_ACTIVE",
            "exactly_one_executor": "tmux:command152_orch",
            "watch": "tmux:command152_watch",
            "command148_orch": "subordinate_no_independent_launch",
            "loot_sealed": True,
            "command153_layer": True,
        },
    )
    event("ORCH_START")
    while True:
        try:
            sleep_s = tick()
        except Exception as e:
            event("TICK_ERROR", error=str(e))
            sleep_s = 20
        time.sleep(max(int(sleep_s or 20), 5))


if __name__ == "__main__":
    raise SystemExit(main())
