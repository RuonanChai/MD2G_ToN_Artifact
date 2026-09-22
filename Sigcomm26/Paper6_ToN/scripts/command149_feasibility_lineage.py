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

"""COMMAND149 Phase 1 lineage from code + completed canary plans. Read-only vs live cell."""
import ast
import json
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import REPO, dump_analysis, dump_status, ts  # noqa: E402
from command149_marginal_cost import cumulative_prefix_mbps, delta_r_mbps, missing_components  # noqa: E402
from component_actuation_plan import closure  # noqa: E402

ART = TON / "artifacts" / "command148_canary120"
STRATS = [
    "MD2G_COMPONENT",
    "HV3_COMPONENT",
    "CLUSTERING_COMPONENT",
    "RULE_COMPONENT",
    "MOQ_UNICAST_COMPONENT",
]


def _src(path: Path) -> str:
    return path.read_text() if path.is_file() else ""


def code_proof() -> dict:
    pol = TON / "lib" / "command148_component_policy.py"
    tr = TON / "scripts" / "command148_train_teacher_student.py"
    plan = TON / "lib" / "component_actuation_plan.py"
    pol_s, tr_s, plan_s = _src(pol), _src(tr), _src(plan)
    old_cumul_live = "state_rate_mbps(content, st) * 1.05" in pol_s
    # after repair the live projector should import project_down
    repaired_live = "from command149_marginal_cost import" in pol_s and "project_down(" in pol_s
    old_cumul_train = "state_rate(content, st) * 1.05" in tr_s
    repaired_train = "missing_rate(content, st, active)" in tr_s
    plan_missing = "open_c = [c for c in required if c not in active]" in plan_s
    return {
        "pre_repair_live_projector_used_full_prefix": True,
        "pre_repair_evidence": "command148_component_policy._project_feasible compared access to state_rate_mbps=sum(closure)*1.05; 1.05*(b0+db1)≈61.27 was the live MD2G Rep2 admission threshold, not diagnostic wording.",
        "pre_repair_training_used_full_prefix": True,
        "pre_repair_training_evidence": "command148_train_teacher_student.expert_state skipped states unless access >= state_rate(content,st)*1.05 with state_rate=sum(closure).",
        "actuation_plan_already_missing_set": plan_missing,
        "actuation_plan_note": "build_plan.open_components = C(targets)\\A_g. Publisher open/close and Ro use missing-set. Admission/target projection did not.",
        "baseline_no_physical_projector_pre_repair": True,
        "baseline_evidence": "HV3/CLUSTERING/RULE/UNICAST returned time-based Rep targets with no access/DeltaR gate; nested planner opened requested missing publishers unconditionally.",
        "post_repair_live_uses_project_down": repaired_live,
        "post_repair_train_uses_missing_rate": repaired_train,
        "old_literal_still_in_live_projector": old_cumul_live,
        "old_literal_still_in_trainer": old_cumul_train,
        "frozen_margin": 1.05,
        "rep2_cumulative_threshold_mbps": cumulative_prefix_mbps("redandblack", "Rep2") * 1.05,
        "rep2_missing_db1_threshold_mbps": delta_r_mbps("redandblack", "Rep2", ["b0"]) * 1.05,
    }


def sample_cell(key: str, n_plans: int = 8) -> dict:
    cell = ART / key
    out: dict = {"key": key, "exists": cell.is_dir()}
    mp = cell / "CELL_METRICS.json"
    if mp.is_file():
        m = json.loads(mp.read_text())
        out["metrics"] = {
            "strategy": m.get("strategy"),
            "U": m.get("U"),
            "Rq": m.get("Rq"),
            "occupancy": m.get("component_occupancy"),
            "active": m.get("active_components"),
        }
    plans = []
    pj = cell / "COMPONENT_ACTUATION_PLAN.jsonl"
    if pj.is_file():
        rows = [json.loads(x) for x in pj.read_text().splitlines() if x.strip()]
        pick = rows[:2] + rows[len(rows) // 2 : len(rows) // 2 + 1] + rows[-2:]
        for rec in pick[:n_plans]:
            targets = rec.get("user_target_states") or {}
            active = rec.get("currently_active_component_set") or []
            required = rec.get("required_component_set") or []
            proposed = next(iter(targets.values()), "Rep1")
            plans.append(
                {
                    "decision_seq": rec.get("decision_seq"),
                    "reason": rec.get("reason"),
                    "proposed_target_sample": proposed,
                    "C_target": list(closure(str(proposed))) if proposed else [],
                    "active": active,
                    "missing": [c for c in (required or []) if c not in set(active or [])],
                    "plan_open": rec.get("open_components"),
                    "plan_required": required,
                    "marginal_component_bytes": rec.get("marginal_component_bytes"),
                    "expected_DeltaR_if_proposed": delta_r_mbps("redandblack", str(proposed), active)
                    if proposed
                    else None,
                    "legacy_cumulative_if_proposed": cumulative_prefix_mbps("redandblack", str(proposed))
                    if proposed
                    else None,
                }
            )
        out["n_plans"] = len(rows)
    out["plan_samples"] = plans
    inf = cell / "COMMAND148_STUDENT_INFERENCE.jsonl"
    if inf.is_file():
        lines = [json.loads(x) for x in inf.read_text().splitlines() if x.strip()]
        raw = {r for rec in lines for r in rec.get("raw_rep") or []}
        tgt = {v for rec in lines for v in (rec.get("targets") or {}).values()}
        out["md2g_inference"] = {
            "n_ticks": len(lines),
            "raw_rep_set": sorted(raw),
            "applied_set": sorted(tgt),
            "physics_field": lines[-1].get("physics") if lines else None,
        }
    return out


def main() -> int:
    q = json.loads((REPO / "state" / "COMMAND148_CANARY120_QUEUE.json").read_text())
    completed = list(q.get("completed") or [])
    cells = {}
    for seed in (151, 152):
        for strat in STRATS:
            key = f"c148can_redandblack_4g_u20_{strat}_s{seed}"
            if (ART / key).is_dir():
                cells[key] = sample_cell(key)
    proof = code_proof()
    body = {
        "ts": ts(),
        "authority": "command149_runtime_marginal_cost_reconciliation.txt",
        "loot_sealed": True,
        "classification": "E",
        "classification_name": "MULTIPLE_CONTRACT_MISMATCH",
        "includes": ["B_MD2G_RUNTIME_CUMULATIVE_COST_BUG", "C_TRAINING_AND_RUNTIME_CUMULATIVE_COST_BUG", "D_BASELINE_FEASIBILITY_ASYMMETRY"],
        "not_A": "61.27 Mbps was the live MD2G projector threshold (full prefix * 1.05), not non-authoritative wording.",
        "code_proof": proof,
        "path": {
            "MD2G_COMPONENT": "Student logits → _project_feasible/project_down → targets → build_plan(A_g) → open missing publishers. Pre-repair projector used cumulative prefix; plan open used missing-set.",
            "HV3_COMPONENT": "time schedule Rep1/2/3 → (pre-repair: no physics) → build_plan → open missing. Post-repair: same project_down as MD2G.",
            "CLUSTERING_COMPONENT": "time/group schedule → same as HV3.",
            "RULE_COMPONENT": "time/bucket schedule → same as HV3.",
            "MOQ_UNICAST_COMPONENT": "same RULE targets; sharing topology independent copies only; component rates identical.",
        },
        "hand_computable": {
            "case1": {
                "A_g": ["b0"],
                "candidate": "Rep2",
                "missing": missing_components("Rep2", ["b0"]),
                "DeltaR_mbps": delta_r_mbps("redandblack", "Rep2", ["b0"]),
                "not_b0_plus_db1": cumulative_prefix_mbps("redandblack", "Rep2"),
            },
            "case2": {
                "A_g": ["b0", "db1", "db2"],
                "candidate": "Rep8",
                "missing": missing_components("Rep8", ["b0", "db1", "db2"]),
                "DeltaR_mbps": delta_r_mbps("redandblack", "Rep8", ["b0", "db1", "db2"]),
            },
            "case3": {
                "A_g": ["b0", "db1", "db2", "e1"],
                "candidate": "Rep8",
                "missing": missing_components("Rep8", ["b0", "db1", "db2", "e1"]),
                "DeltaR_mbps": delta_r_mbps("redandblack", "Rep8", ["b0", "db1", "db2", "e1"]),
            },
        },
        "completed_at_lineage": completed,
        "cells": cells,
        "live_hv3_u60_s152_not_killed": True,
        "canary_cells_are_pre_repair_not_final": True,
        "label": "PRE_MARGINAL_COST_TRAINING_CONTRACT",
    }
    dump_analysis("COMMAND149_RUNTIME_FEASIBILITY_LINEAGE.json", body)
    md = [
        "# COMMAND149 runtime feasibility lineage",
        "",
        f"- ts: `{body['ts']}`",
        f"- classification: **E / MULTIPLE_CONTRACT_MISMATCH** (B+C+D)",
        "- 61.27 Mbps was live MD2G **admission** (`1.05 * (b0+db1)`), not diagnostic wording.",
        "- Teacher/expert used the same cumulative prefix gate.",
        "- HV3/Clustering/Rule/Unicast had **no** equivalent physical projector.",
        "- ComponentActuationPlan open-set was already missing-component; admission was not.",
        "",
        "## Hand-computable",
        f"- Case1 A_g={{b0}} → B2 missing={body['hand_computable']['case1']['missing']} DeltaR={body['hand_computable']['case1']['DeltaR_mbps']:.4f} Mbps (not {body['hand_computable']['case1']['not_b0_plus_db1']:.4f}).",
        f"- Case2 A_g={{b0,db1,db2}} → B3+E1 missing={body['hand_computable']['case2']['missing']} DeltaR={body['hand_computable']['case2']['DeltaR_mbps']:.4f} Mbps.",
        f"- Case3 already-shared e1 → DeltaR={body['hand_computable']['case3']['DeltaR_mbps']:.4f}.",
        "",
        "Existing canary cells are `PRE_MARGINAL_COST_TRAINING_CONTRACT` / not final science. Loot sealed. No V2.",
        "",
    ]
    dump_status("COMMAND149_RUNTIME_FEASIBILITY_LINEAGE.md", "\n".join(md))
    (TON / "analysis" / "COMMAND149_RUNTIME_FEASIBILITY_LINEAGE.json").write_text(json.dumps(body, indent=2) + "\n")
    print(json.dumps({"classification": "E", "n_cells": len(cells), "repaired_live": proof["post_repair_live_uses_project_down"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
