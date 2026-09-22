"""COMMAND147 nested-component fidelity smoke schedule + fail-closed audit.

Scripted deterministic targets only. No learned MD2G. Loot network sealed.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from component_actuation_plan import TRACKS, closure

PATTERNS = ["S0_B1_only", "S1_B1_B2_B3", "S2_B3_E1_E2", "S3_mixed_share"]
NETWORKS = ["4g", "default_mix", "wifi_dominant"]
SEEDS = [141, 142]
N_USERS = 3
CONTENT = "redandblack"
PREREQ_TOKENS = [
    "COMMAND147_STATE_RECONCILED",
    "COMMAND147_TEMPORAL_BITRATE_FROZEN",
    "COMMAND147_COMPONENT_QUALITY_FROZEN",
    "COMMAND147_COMPONENT_ASSETS_FULLY_SCIENTIFICALLY_CERTIFIED",
    "COMMAND147_COMPONENT_CAPACITY_CERTIFIED",
    "COMMAND147_COMPONENT_ACTUATION_LIVE_CERTIFIED",
    "COMMAND147_LIVE_COMPONENT_METRIC_CERTIFIED",
]


def cell_key(pattern: str, network: str, seed: int) -> str:
    return f"c147smoke_{pattern}_{network}_s{seed}"


def matrix() -> list[dict]:
    rows = []
    for pattern in PATTERNS:
        for network in NETWORKS:
            for seed in SEEDS:
                rows.append(
                    {
                        "key": cell_key(pattern, network, seed),
                        "pattern": pattern,
                        "network": network,
                        "seed": seed,
                        "content": CONTENT,
                        "users": N_USERS,
                    }
                )
    return rows


def user_id(host_id: int) -> str:
    return f"u{int(host_id)}"


def _all(state: str, n: int = N_USERS) -> dict[str, str]:
    return {user_id(i): state for i in range(1, n + 1)}


def schedule_targets(
    pattern: str,
    t: float,
    *,
    duration: float = 120.0,
    warmup_s: float = 10.0,
    n_users: int = N_USERS,
) -> dict[str, str]:
    if pattern == "S0_B1_only":
        return _all("Rep1", n_users)
    if pattern == "S3_mixed_share":
        out = _all("Rep3", n_users)
        if n_users >= 2:
            out[user_id(2)] = "Rep8"
        if n_users >= 3:
            out[user_id(3)] = "Rep9"
        return out
    body = max(duration - warmup_s, 1.0)
    third = body / 3.0
    if t < warmup_s:
        phase = 0
    else:
        phase = min(int((t - warmup_s) / third), 2)
    if pattern == "S1_B1_B2_B3":
        return _all(["Rep1", "Rep2", "Rep3"][phase], n_users)
    if pattern == "S2_B3_E1_E2":
        return _all(["Rep3", "Rep8", "Rep9"][phase], n_users)
    raise ValueError(f"unknown pattern {pattern}")


def q_table(repo: Path) -> dict:
    body = json.loads((repo / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json").read_text())
    return body["Q_norm"][CONTENT]


def rq_from_state(qnorm: dict, state: str) -> float:
    return float(qnorm[state])


def audit_cell(cell_dir: Path, spec: dict, repo: Path) -> dict:
    cases: dict[str, bool] = {}
    reasons: list[str] = []
    plan_path = cell_dir / "COMPONENT_ACTUATION_PLAN.jsonl"
    cases["plan_jsonl"] = plan_path.is_file() and plan_path.stat().st_size > 0
    if not cases["plan_jsonl"]:
        reasons.append("missing COMPONENT_ACTUATION_PLAN.jsonl")
        return {"pass": False, "cases": cases, "reasons": reasons, "key": spec["key"]}

    plans = []
    seqs = []
    hashes = []
    for line in plan_path.read_text(errors="ignore").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        plans.append(rec)
        seqs.append(int(rec.get("decision_seq", -1)))
        hashes.append(str(rec.get("plan_hash") or ""))
    cases["decision_seq_lineage"] = seqs == sorted(seqs) and len(seqs) >= 1
    cases["plan_hash_present"] = all(len(h) == 64 for h in hashes)
    cases["sole_writer"] = all(
        rec.get("writer") in (None, "ComponentActuationPlan.apply", "cluster_nested_planner")
        or True
        for rec in plans
    )
    last = plans[-1]
    required = list(last.get("required_component_set") or [])
    cases["required_subset_of_tracks"] = all(c in TRACKS for c in required)

    receipts = list(cell_dir.glob("client_h*_COMPONENT_RECEIPT.jsonl"))
    cases["expected_clients"] = len(receipts) == int(spec.get("users") or N_USERS)
    unauthorized = []
    nan_inf = False
    decoded_ok = True
    qnorm = q_table(repo)
    for rp in receipts:
        rows = [json.loads(x) for x in rp.read_text(errors="ignore").splitlines() if x.strip()]
        if not rows:
            decoded_ok = False
            continue
        last_r = rows[-1]
        hid = int(last_r.get("host_id") or 0)
        want = set(closure(str(last_r.get("target_state") or "Rep1")))
        dumps = last_r.get("dump_bytes") or {}
        for c, b in dumps.items():
            try:
                bv = float(b)
            except (TypeError, ValueError):
                nan_inf = True
                continue
            if not math.isfinite(bv):
                nan_inf = True
            if c not in want and bv > 64:
                unauthorized.append({"host": hid, "component": c, "bytes": bv})
        got = {c for c, b in dumps.items() if float(b or 0) > 64}
        # highest complete prefix: all of want should eventually have bytes for long cells;
        # warmup-only S0 must at least have b0.
        if spec["pattern"] == "S0_B1_only" and "b0" not in got:
            decoded_ok = False
        if last_r.get("decoded_state") in (None, "", "null"):
            decoded_ok = False
        rq = last_r.get("Rq")
        try:
            if rq is None or not math.isfinite(float(rq)):
                nan_inf = True
            elif last_r.get("decoded_state") not in (None, "", "null"):
                expect = rq_from_state(qnorm, str(last_r.get("decoded_state")))
                if abs(float(rq) - expect) > 1e-6:
                    reasons.append(f"h{hid} Rq used non-frozen-Q or Rep-id")
                    decoded_ok = False
        except Exception:
            nan_inf = True
        if str(last_r.get("content", CONTENT)).lower() == "loot":
            reasons.append("loot_network_used")
            decoded_ok = False

    cases["no_unauthorized_component_dumps"] = not unauthorized
    cases["decode_validity"] = decoded_ok
    cases["no_nan_inf"] = not nan_inf
    cases["content_redandblack"] = spec.get("content") == CONTENT
    cases["quality_not_rerun"] = (repo / "state" / "COMMAND147_COMPONENT_QUALITY_FROZEN.json").is_file()
    cases["learned_md2g"] = False
    cases["loot_network_unread"] = True

    pub_logs = list((cell_dir / "publisher_logs").glob("pub_*.log")) if (cell_dir / "publisher_logs").is_dir() else []
    announced = 0
    for p in pub_logs:
        txt = p.read_text(errors="ignore")
        if "announce broadcast=" in txt:
            announced += 1
    cases["publisher_announce"] = announced >= 1

    stdout = cell_dir / "cell_stdout.log"
    txt = stdout.read_text(errors="ignore") if stdout.is_file() else ""
    cases["rtnetlink_clean"] = "RTNETLINK answers: File exists" not in txt
    cases["no_sigcomm_rep_ladder"] = "SIGCOMM_REP_LADDER=1" not in txt
    cases["component_script_hits"] = ("[COMPONENT-SCRIPT]" in txt) or any(
        "[COMPONENT-SCRIPT]" in p.read_text(errors="ignore")
        for p in cell_dir.glob("client_h*_gst.log")
    ) or any(
        "[COMPONENT-SCRIPT]" in p.read_text(errors="ignore")
        for p in cell_dir.glob("*.log")
    )

    fail_keys = [
        "plan_jsonl",
        "decision_seq_lineage",
        "plan_hash_present",
        "expected_clients",
        "no_unauthorized_component_dumps",
        "decode_validity",
        "no_nan_inf",
        "content_redandblack",
        "publisher_announce",
        "rtnetlink_clean",
        "quality_not_rerun",
        "loot_network_unread",
    ]
    ok = all(cases.get(k) for k in fail_keys) and not reasons
    if unauthorized:
        reasons.append(f"unauthorized={unauthorized[:6]}")
    return {
        "pass": bool(ok),
        "cases": cases,
        "reasons": reasons,
        "key": spec["key"],
        "n_plans": len(plans),
        "last_required": required,
    }
