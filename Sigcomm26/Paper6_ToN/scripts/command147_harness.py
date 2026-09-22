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

"""COMMAND147 durable tightening harness. No Teacher. No scientific Mininet until READY."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
if not PY.exists():
    PY = Path("/usr/bin/python3")
CURRENT = REPO / "state" / "CURRENT.json"
STATE = REPO / "state" / "COMMAND147_STATE.json"
EVENTS = REPO / "logs" / "command147_events.ndjson"

TOKENS = [
    "COMMAND147_STATE_RECONCILED",
    "COMMAND147_TEMPORAL_BITRATE_FROZEN",
    "COMMAND147_COMPONENT_QUALITY_FROZEN",
    "COMMAND147_COMPONENT_ASSETS_FULLY_SCIENTIFICALLY_CERTIFIED",
    "COMMAND147_COMPONENT_CAPACITY_CERTIFIED",
    "COMMAND147_COMPONENT_ACTUATION_LIVE_CERTIFIED",
    "COMMAND147_LIVE_COMPONENT_METRIC_CERTIFIED",
    "COMMAND147_24CELL_COMPONENT_FIDELITY_SMOKE_PASS",
]


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
    st["token"] = "COMMAND147_CURRENT"
    st["authority"] = "command147_MD2G_contract_tightening_before_smoke.txt"
    st["campaign_authority"] = "command146_MD2G_correct_nested_component_full_experiment_plan.txt"
    st["tightening_authority"] = "command147_MD2G_contract_tightening_before_smoke.txt"
    st["command145_forbidden"] = True
    st["holdout_sealed"] = True
    st["loot_unsealed"] = False
    st["loot_network_holdout_sealed"] = True
    st["MD2G_DEV_OPTIMIZATION_ALLOWED"] = False
    st["exactly_one_executor"] = "tmux:command137_harness"
    st["watch"] = "tmux:command137_watch"
    st["phase"] = "COMMAND146_POST_MEDIA_CONTRACT_TIGHTENING"
    st["all_media_generated"] = True
    st["structural_component_assets_certified"] = True
    st["scientific_mininet_cells"] = 0
    st["COMMAND147_READY_FOR_COMMAND146_TEACHER"] = exists("COMMAND147_READY_FOR_COMMAND146_TEACHER")
    st["quality_table_frozen"] = exists("COMMAND147_COMPONENT_QUALITY_FROZEN")
    st["temporal_bitrate_contract_frozen"] = exists("COMMAND147_TEMPORAL_BITRATE_FROZEN")
    st["capacity_component_certified"] = exists("COMMAND147_COMPONENT_CAPACITY_CERTIFIED")
    st["component_actuation_live_certified"] = exists("COMMAND147_COMPONENT_ACTUATION_LIVE_CERTIFIED")
    st["live_component_metric_certified"] = exists("COMMAND147_LIVE_COMPONENT_METRIC_CERTIFIED")
    text = json.dumps(st, indent=2) + "\n"
    tmp = CURRENT.with_suffix(".tmp")
    tmp.write_text(text)
    tmp.replace(CURRENT)
    (TON / "state" / "CURRENT.json").write_text(text)
    STATE.write_text(text)
    (TON / "state" / "COMMAND147_STATE.json").write_text(text)
    (TON / "state" / "CURRENT.json").write_text(text)


def run_py(script: str) -> int:
    return subprocess.run([str(PY), "-u", str(TON / "scripts" / script)], cwd=str(REPO)).returncode


def main() -> int:
    st = load_cur()
    st.setdefault("round_id", "C147")
    st["active_cell"] = None
    st["terminal_state"] = None
    if (REPO / "state" / "COMMAND148_AGENTS_AUTHORITY.json").is_file():
        event("YIELD_TO_COMMAND148", note="command148 is sole Mininet launcher")
        return 0
    if not exists("COMMAND147_STATE_RECONCILED"):
        event("P0_MISSING")
        st["next_action"] = "COMMAND147_STATE_RECONCILE"
        save_cur(st)
        return 2
    if not exists("COMMAND147_TEMPORAL_BITRATE_FROZEN"):
        st["next_action"] = "COMMAND147_TEMPORAL_BITRATE_TRUTH"
        st["last_real_progress_at"] = ts()
        st["last_event_kind"] = "P1_TEMPORAL"
        save_cur(st)
        event("P1_START")
        rc = run_py("command147_temporal_bitrate_audit.py")
        event("P1_DONE", rc=rc)
        st = load_cur()
        st["temporal_bitrate_contract_frozen"] = exists("COMMAND147_TEMPORAL_BITRATE_FROZEN")
        st["next_action"] = (
            "COMMAND147_COMPONENT_QUALITY_TRUTH" if rc == 0 else "COMMAND147_TEMPORAL_BITRATE_TRUTH"
        )
        st["last_real_progress_at"] = ts()
        save_cur(st)
        return rc
    if not exists("COMMAND147_COMPONENT_QUALITY_FROZEN"):
        st["next_action"] = "COMMAND147_COMPONENT_QUALITY_TRUTH"
        st["last_real_progress_at"] = ts()
        st["last_event_kind"] = "P2_QUALITY"
        save_cur(st)
        event("P2_START")
        rc = run_py("command147_measure_component_quality.py")
        event("P2_DONE", rc=rc)
        st = load_cur()
        st["quality_table_frozen"] = exists("COMMAND147_COMPONENT_QUALITY_FROZEN")
        st["next_action"] = (
            "COMMAND147_COMPONENT_CAPACITY_RECERT" if rc == 0 else "COMMAND147_COMPONENT_QUALITY_TRUTH"
        )
        st["last_real_progress_at"] = ts()
        save_cur(st)
        return rc
    if not exists("COMMAND147_COMPONENT_CAPACITY_OFFLINE_PASS"):
        st["next_action"] = "COMMAND147_COMPONENT_CAPACITY_RECERT"
        st["last_event_kind"] = "P3_CAPACITY_OFFLINE"
        st["last_real_progress_at"] = ts()
        save_cur(st)
        event("P3_OFFLINE_START", note="DeltaR from frozen rates; live estimator not yet; no scientific Mininet")
        rc = run_py("command147_capacity_offline_cert.py")
        event("P3_OFFLINE_DONE", rc=rc)
        st = load_cur()
        st["capacity_component_certified"] = False
        st["next_action"] = (
            "COMMAND147_COMPONENT_CAPACITY_LIVE_ESTIMATOR"
            if exists("COMMAND147_COMPONENT_CAPACITY_OFFLINE_PASS")
            else "COMMAND147_COMPONENT_CAPACITY_RECERT"
        )
        st["last_real_progress_at"] = ts()
        save_cur(st)
        return rc
    if not exists("COMMAND147_COMPONENT_CAPACITY_CERTIFIED"):
        st["next_action"] = "COMMAND147_COMPONENT_CAPACITY_LIVE_ESTIMATOR"
        st["last_event_kind"] = "P3_LIVE_ESTIMATOR"
        st["capacity_component_certified"] = False
        st["quality_table_frozen"] = True
        st["last_real_progress_at"] = ts()
        save_cur(st)
        event("P3_LIVE_START", note="quality frozen; do not remeasure; live estimator recert; no Teacher/smoke")
        rc = run_py("command147_capacity_live_estimator_cert.py")
        event("P3_LIVE_DONE", rc=rc)
        st = load_cur()
        st["capacity_component_certified"] = exists("COMMAND147_COMPONENT_CAPACITY_CERTIFIED")
        st["next_action"] = (
            "COMMAND147_COMPONENT_ACTUATION_LIVE"
            if exists("COMMAND147_COMPONENT_CAPACITY_CERTIFIED")
            else "COMMAND147_COMPONENT_CAPACITY_LIVE_ESTIMATOR"
        )
        st["last_real_progress_at"] = ts()
        save_cur(st)
        return rc
    if not exists("COMMAND147_COMPONENT_ACTUATION_LIVE_CERTIFIED"):
        st["next_action"] = "COMMAND147_COMPONENT_ACTUATION_LIVE"
        st["last_event_kind"] = "P4_ACTUATION_LIVE"
        st["last_real_progress_at"] = ts()
        save_cur(st)
        event("P4_START")
        rc = run_py("command147_actuation_live_cert.py")
        event("P4_DONE", rc=rc)
        st = load_cur()
        st["component_actuation_live_certified"] = exists("COMMAND147_COMPONENT_ACTUATION_LIVE_CERTIFIED")
        st["next_action"] = (
            "COMMAND147_LIVE_COMPONENT_METRIC"
            if exists("COMMAND147_COMPONENT_ACTUATION_LIVE_CERTIFIED")
            else "COMMAND147_COMPONENT_ACTUATION_LIVE"
        )
        st["last_real_progress_at"] = ts()
        save_cur(st)
        return rc
    if not exists("COMMAND147_LIVE_COMPONENT_METRIC_CERTIFIED"):
        st["next_action"] = "COMMAND147_LIVE_COMPONENT_METRIC"
        st["last_event_kind"] = "P5_LIVE_METRIC"
        st["last_real_progress_at"] = ts()
        save_cur(st)
        event("P5_START")
        rc = run_py("command147_live_metric_cert.py")
        event("P5_DONE", rc=rc)
        st = load_cur()
        st["live_component_metric_certified"] = exists("COMMAND147_LIVE_COMPONENT_METRIC_CERTIFIED")
        st["next_action"] = (
            "COMMAND147_24CELL_FIDELITY_SMOKE"
            if exists("COMMAND147_LIVE_COMPONENT_METRIC_CERTIFIED")
            else "COMMAND147_LIVE_COMPONENT_METRIC"
        )
        st["last_real_progress_at"] = ts()
        save_cur(st)
        return rc
    if not exists("COMMAND147_24CELL_COMPONENT_FIDELITY_SMOKE_PASS"):
        st["next_action"] = "COMMAND147_24CELL_FIDELITY_SMOKE"
        st["last_event_kind"] = "P6_24CELL_SMOKE"
        st["quality_table_frozen"] = True
        st["last_real_progress_at"] = ts()
        save_cur(st)
        event("P6_CELL_START", note="fidelity smoke only; no Teacher; no quality rerun")
        rc = run_py("command147_24cell_fidelity_smoke.py")
        event("P6_CELL_DONE", rc=rc)
        st = load_cur()
        st["next_action"] = (
            "COMMAND147_PRETRAIN_SCIENTIFIC_FREEZE"
            if exists("COMMAND147_24CELL_COMPONENT_FIDELITY_SMOKE_PASS")
            else "COMMAND147_24CELL_FIDELITY_SMOKE"
        )
        st["last_real_progress_at"] = ts()
        save_cur(st)
        return rc
    missing = [t for t in TOKENS if not exists(t)]
    st["next_action"] = "COMMAND147_" + (missing[0].split("COMMAND147_")[-1] if missing else "READY")
    st["missing_tokens"] = missing
    st["last_real_progress_at"] = ts()
    save_cur(st)
    event("WAITING_NEXT_TOKEN", missing=missing)
    # Do not launch smoke/Teacher/scientific Mininet here.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
