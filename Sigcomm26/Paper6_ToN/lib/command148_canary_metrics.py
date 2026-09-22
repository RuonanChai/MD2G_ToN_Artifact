from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Paper-facing metrics from a corrected-contract nested cell."""
import json
import statistics
from collections import Counter
from pathlib import Path

from command148_rb_lineage import rb_lineage
from command151_physical_pressure import summarize_cell
from command151_stall_supporting import STATUS as STALL_STATUS
from command151_stall_supporting import stall_seconds_from_receipts
from component_actuation_plan import TRACKS, closure
from ton_ro_component import paper_u, ro_component

REPO = artifact_root()
STATES = [f"Rep{i}" for i in range(1, 10)]
DUMP_COMPLETE_BYTES = 64


def _qnorm(content: str) -> dict:
    body = json.loads((REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json").read_text())
    return dict((body.get("Q_norm") or {}).get(content) or {})


def _rates(content: str) -> dict[str, float]:
    body = json.loads((REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
    return {t: float(body["contents"][content][t]["steady_state_payload_mbps"]) for t in TRACKS}


def _occ(counter: Counter, n: int) -> dict[str, float]:
    denom = max(int(n), 1)
    return {st: float(counter.get(st, 0)) / denom for st in STATES}


def _last_plan(cell: Path) -> dict:
    cur = cell / "COMPONENT_ACTUATION_PLAN_CURRENT.json"
    if cur.is_file():
        try:
            return json.loads(cur.read_text())
        except Exception:
            return {}
    jl = cell / "COMPONENT_ACTUATION_PLAN.jsonl"
    if not jl.is_file():
        return {}
    last = {}
    for ln in jl.read_text(errors="ignore").splitlines():
        if ln.strip():
            try:
                last = json.loads(ln)
            except Exception:
                continue
    return last


def composition_delivery_stats(cell: Path, spec: dict) -> dict:
    """Target vs decoded occupancy, receiver-set sizes, completion. Not a quality rank."""
    users = int(spec.get("users") or 0)
    content = str(spec.get("content") or "")
    qn = _qnorm(content)
    plan = _last_plan(cell)
    receivers = dict(plan.get("component_receivers") or {})
    targets_plan = dict(plan.get("user_target_states") or {})
    target_states: list[str] = []
    decoded_states: list[str] = []
    last_by_uid: dict[str, dict] = {}
    for i in range(1, users + 1):
        uid = f"u{i}"
        rp = cell / f"client_h{i}_COMPONENT_RECEIPT.jsonl"
        last = {}
        if rp.is_file():
            rows = [json.loads(x) for x in rp.read_text(errors="ignore").splitlines() if x.strip()]
            if rows:
                last = rows[-1]
        last_by_uid[uid] = last
        tgt = str(last.get("target_state") or targets_plan.get(uid) or "Rep1")
        raw_dec = last.get("decoded_state")
        target_states.append(tgt)
        if raw_dec not in (None, "", "null", "None"):
            decoded_states.append(str(raw_dec))
    n = max(len(target_states), 1)
    recv_size = {}
    completion = {}
    for c in TRACKS:
        rlist = list(receivers.get(c) or [])
        if not rlist:
            rlist = [uid for uid, last in last_by_uid.items() if c in set(closure(str(last.get("target_state") or targets_plan.get(uid) or "Rep1")))]
        recv_size[c] = len(rlist)
        n_ok = 0
        for uid in rlist:
            last = last_by_uid.get(uid) or {}
            dumps = last.get("dump_bytes") or {}
            try:
                bv = float(dumps.get(c) or 0)
            except (TypeError, ValueError):
                bv = 0.0
            if bv > DUMP_COMPLETE_BYTES:
                n_ok += 1
        completion[c] = {
            "n_receivers": len(rlist),
            "n_complete_dump_gt_64": n_ok,
            "fraction": (float(n_ok) / len(rlist)) if rlist else None,
        }
    return {
        "Q_norm_frozen": {st: float(qn.get(st) or 0.0) for st in STATES},
        "quality_ranked_by_rep_id": False,
        "target_state_occupancy": _occ(Counter(target_states), n),
        "actual_decoded_state_occupancy": _occ(Counter(decoded_states), n),
        "receiver_set_size": recv_size,
        "component_completion_fraction": completion,
        "n_users_in_occupancy": len(target_states),
    }


def cell_metrics(cell: Path, spec: dict) -> dict:
    content = spec["content"]
    qn = _qnorm(content)
    rates = _rates(content)
    users = int(spec["users"])
    rqs = []
    rxs = []
    stalls = []
    decoded = []
    user_comps: dict[str, set[str]] = {}
    payload = {t: 0 for t in TRACKS}
    for i in range(1, users + 1):
        rp = cell / f"client_h{i}_COMPONENT_RECEIPT.jsonl"
        if not rp.is_file():
            rqs.append(0.0)
            stalls.append(0.0)
            continue
        rows = [json.loads(x) for x in rp.read_text(errors="ignore").splitlines() if x.strip()]
        if not rows:
            rqs.append(0.0)
            stalls.append(0.0)
            continue
        last = rows[-1]
        raw_dec = last.get("decoded_state")
        if raw_dec in (None, "", "null", "None"):
            st = None
            rqs.append(0.0)
        else:
            st = str(raw_dec)
            rqs.append(float(qn.get(st) or 0.0))
        if st:
            decoded.append(st)
        dumps = last.get("dump_bytes") or {}
        user_comps[f"u{i}"] = set(closure(st)) if st else {t for t in TRACKS if int(dumps.get(t) or 0) > DUMP_COMPLETE_BYTES}
        for t in TRACKS:
            payload[t] = max(payload[t], int(dumps.get(t) or 0))
        stall_s, _status = stall_seconds_from_receipts(rows)
        stalls.append(float(stall_s))
        perf = cell / f"client_h{i}_perf.csv"
        if perf.is_file():
            lines = [ln for ln in perf.read_text().splitlines()[1:] if ln.strip()]
            if lines:
                parts = lines[-1].split(",")
                try:
                    rxs.append(float(parts[15]))
                except Exception:
                    rxs.append(0.0)
    b_uni = 0
    for comps in user_comps.values():
        for c in comps:
            b_uni += int(payload.get(c, 0))
    active = [t for t in TRACKS if payload.get(t, 0) > 64]
    if spec.get("strategy") == "MOQ_UNICAST_COMPONENT":
        b_shared = b_uni
        ro = 0.0
    else:
        b_shared = sum(int(payload[t]) for t in active)
        ro = ro_component(b_shared, b_uni)
    rq = statistics.mean(rqs) if rqs else 0.0
    weak = sorted(rqs)[0] if rqs else 0.0
    stall = statistics.mean(stalls) if stalls else 0.0
    press = summarize_cell(cell)
    frozen_p = (REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_CONTRACT_FROZEN.json").is_file()
    if press and press.get("Rb") is not None:
        rb = float(press["Rb"])
        rb0_proj = False
    elif frozen_p:
        rb = None
        rb0_proj = False
    else:
        rb = 0.0
        rb0_proj = True
    u = None if rb is None else paper_u(ro, rq, rb)
    extra = composition_delivery_stats(cell, spec)
    occupancy = extra["actual_decoded_state_occupancy"]
    out = {
        "key": spec["key"],
        "content": content,
        "network": spec["network"],
        "users": users,
        "seed": spec["seed"],
        "strategy": spec["strategy"],
        "U": u,
        "Ro_component": ro,
        "Rq": rq,
        "Rb": rb,
        "weak_user_Rq": weak,
        "stall_last": stall,
        "n_decoded": len(decoded),
        "component_occupancy": occupancy,
        "target_state_occupancy": extra["target_state_occupancy"],
        "actual_decoded_state_occupancy": extra["actual_decoded_state_occupancy"],
        "receiver_set_size": extra["receiver_set_size"],
        "component_completion_fraction": extra["component_completion_fraction"],
        "Q_norm_frozen": extra["Q_norm_frozen"],
        "quality_ranked_by_rep_id": False,
        "active_components": active,
        "upgrade_fraction": sum(float(occupancy.get(st) or 0.0) for st in STATES if st != "Rep1"),
        "B_shared": b_shared,
        "B_unicast": b_uni,
        "mean_rx": statistics.mean(rxs) if rxs else 0.0,
        "rates_mbps_ref": rates,
        "paper_U_is_Rb0_projection": rb0_proj,
        "Rb_semantics": "physical_bottleneck_pressure_p95_util",
        "Rb_source": "r0-eth1_tx_kernel_bytes" if press else "missing_or_pre_instrumentation_placeholder",
        "bandwidth_efficiency_evidence": ["Ro_component", "B_shared", "B_unicast", "mean_rx"],
        "physical_pressure": press,
        "stall_last_status": STALL_STATUS,
    }
    out["rb_lineage"] = rb_lineage(cell, out)
    return out
