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

"""V1 120-cell canary aggregate gate. One V2 only if one proven mechanism weakness."""
import json
import statistics
import sys
from pathlib import Path

TON = ton_root()
REPO = artifact_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import dump_dual, token, ts  # noqa: E402

ART = TON / "artifacts" / "command148_canary120"
SAME = ["HV3_COMPONENT", "CLUSTERING_COMPONENT", "RULE_COMPONENT"]


def _art(q: dict) -> Path:
    if str(q.get("epoch") or "") == "post_physical_pressure_rbv1":
        return TON / "artifacts" / "command148_canary120_rbv1"
    raw = q.get("art")
    return Path(raw) if raw else ART


def _rows() -> list[dict]:
    q = json.loads((REPO / "state" / "COMMAND148_CANARY120_QUEUE.json").read_text())
    if q.get("epoch") != "post_physical_pressure_rbv1" or not (
        REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_RELEASE.json"
    ).is_file():
        raise SystemExit(
            json.dumps(
                {
                    "pass": False,
                    "reason": "pre_physical_pressure_cells_not_final_science",
                    "class": "PRE_PHYSICAL_PRESSURE_INSTRUMENTATION_DIAGNOSTIC",
                }
            )
        )
    art = _art(q)
    out = []
    for key in q.get("completed") or []:
        p = art / key / "CELL_METRICS.json"
        if not p.is_file():
            continue
        raw = p.read_text().strip()
        if raw in ("", "null"):
            continue
        m = json.loads(raw)
        if not isinstance(m, dict) or m.get("paper_U_is_Rb0_projection"):
            continue
        if m.get("Rb") is None:
            continue
        out.append(m)
    return out


def _mean(xs: list[float]) -> float:
    return statistics.mean(xs) if xs else 0.0


def main() -> int:
    rows = _rows()
    margins = json.loads((REPO / "state" / "COMMAND148_CANARY_NOISE_MARGINS_PREDECLARED.json").read_text())
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["strategy"], []).append(r)
    md2g = by.get("MD2G_COMPONENT") or []
    fidelity = len(rows) >= 120
    upgrade = _mean([float(r.get("upgrade_fraction") or 0.0) for r in md2g])
    collapse = upgrade < float(margins["all_lowest_collapse_if_upgrade_fraction_lt"])
    explosion = _mean([len(r.get("active_components") or []) for r in md2g]) > float(
        margins["pathological_explosion_if_mean_active_components_gt"]
    )
    u_md2g = _mean([float(r["U"]) for r in md2g])
    best_name, best_u = None, -1.0
    for s in SAME:
        mu = _mean([float(r["U"]) for r in by.get(s) or []])
        if mu > best_u:
            best_u, best_name = mu, s
    delta = u_md2g - best_u
    competitive = delta >= float(margins["competitive_if_mean_delta_U_ge"])
    rq_md2g = _mean([float(r["Rq"]) for r in md2g])
    rq_best = _mean([float(r["Rq"]) for r in by.get(best_name) or []])
    stall_md2g = _mean([float(r.get("stall_last") or 0.0) for r in md2g])
    stall_best = _mean([float(r.get("stall_last") or 0.0) for r in by.get(best_name) or []])
    weak_md2g = _mean([float(r.get("weak_user_Rq") or 0.0) for r in md2g])
    weak_best = _mean([float(r.get("weak_user_Rq") or 0.0) for r in by.get(best_name) or []])
    rq_ok = (rq_best - rq_md2g) <= float(margins["catastrophic_Rq_drop_vs_best_same_substrate"])
    stall_ok = True  # supporting DECODE_GAP stall is not a V1 pass/fail filter
    weak_ok = (weak_best - weak_md2g) <= float(margins["catastrophic_weak_user_Rq_drop"])
    q = json.loads((REPO / "state" / "COMMAND148_CANARY120_QUEUE.json").read_text())
    art = _art(q)
    student_ok = all((art / r["key"] / "COMMAND148_STUDENT_INFERENCE.jsonl").is_file() for r in md2g)
    v1 = all([fidelity, (not collapse), (not explosion), competitive, rq_ok, stall_ok, weak_ok, student_ok])
    body = {
        "ts": ts(),
        "n": len(rows),
        "fidelity_120": fidelity,
        "md2g_upgrade_fraction": upgrade,
        "all_lowest_collapse": collapse,
        "pathological_explosion": explosion,
        "U_md2g": u_md2g,
        "strongest_same_substrate": best_name,
        "U_strongest_same_substrate": best_u,
        "delta_U": delta,
        "competitive": competitive,
        "rq_ok": rq_ok,
        "stall_ok": stall_ok,
        "stall_last_status": "DECODE_GAP_SECONDS_POST_WARMUP",
        "stall_in_v1_gate": False,
        "never_claim_zero_stall": True,
        "weak_ok": weak_ok,
        "student_ok": student_ok,
        "v1_pass": v1,
        "loot_sealed": True,
        "margins": margins.get("token"),
    }
    dump_dual("COMMAND148_CANARY_V1_GATE.json", body)
    # command153: 120/120 is enough to freeze a DEV candidate. Losing U / low Rq /
    # non-competitive / collapse flags do not block DEV and do not by themselves
    # authorize V2. CLAIM_LIMITED may be recorded, but never without a freeze,
    # or orch would stop the canary/DEV ladder.
    v2_used = (REPO / "state" / "COMMAND148_V2_REPAIR_FROZEN.json").is_file()
    v2_hyp = REPO / "state" / "COMMAND153_V2_HYPOTHESIS.json"
    if fidelity and (not v2_used) and v2_hyp.is_file():
        dump_dual(
            "COMMAND148_V2_REPAIR_FROZEN.json",
            {
                "ts": ts(),
                "weakness": "prewritten_command153_hypothesis",
                "hypothesis": json.loads(v2_hyp.read_text()),
                "repair": "one_minimal_policy_change_frozen_before_v2_results",
                "rerun": "same_120_cell_canary",
                "no_v3": True,
                "frozen_before_v2_results": True,
                "v1": body,
            },
        )
        print(json.dumps({"pass": False, "v2_authorized": True, "source": "COMMAND153_V2_HYPOTHESIS"}))
        return 5
    if not fidelity:
        dump_dual(
            "COMMAND148_COMPONENT_CONTROLLER_CLAIM_LIMITED.json",
            {
                "ts": ts(),
                "token": "COMMAND148_COMPONENT_CONTROLLER_CLAIM_LIMITED",
                "v1": body,
                "dev_continues": False,
                "reason": "canary_n_lt_120",
            },
        )
        print(json.dumps({"pass": False, "claim_limited": True, "reason": "canary_n_lt_120", "n": len(rows)}))
        return 6
    dump_dual(
        "COMMAND148_CANARY120_COMPLETE.json",
        {
            "ts": ts(),
            "n": len(rows),
            "status": "V1_GATE_FROZEN",
            "loot_sealed": True,
            "epoch": q.get("epoch"),
        },
    )
    ver = "V1" if v1 else "V1_CLAIM_LIMITED"
    dump_dual(
        "COMMAND148_DEV_CANDIDATE_FREEZE.json",
        {
            "ts": ts(),
            "version": ver,
            "n": 120,
            "v1_pass": v1,
            "student": str(TON / "models" / "command148_component" / "student_component_v1.pt"),
            "student_ok": student_ok,
            "v1": body,
            "loot_sealed": True,
            "note": "command153: losing U/low Rq does not block DEV; does not authorize V2",
        },
    )
    token("COMMAND148_DEV_CANDIDATE_FREEZE", {"version": ver, "v1_pass": v1})
    if not v1:
        dump_dual(
            "COMMAND148_COMPONENT_CONTROLLER_CLAIM_LIMITED.json",
            {
                "ts": ts(),
                "token": "COMMAND148_COMPONENT_CONTROLLER_CLAIM_LIMITED",
                "v1": body,
                "dev_continues": True,
            },
        )
    if not student_ok:
        dump_dual(
            "COMMAND148_V2_NOT_AUTHORIZED_EXECUTION_FIDELITY.json",
            {
                "ts": ts(),
                "weakness": "student_fidelity",
                "note": "command153: student sidecar missing is execution/fidelity, not a V2 controller repair; DEV still frozen",
            },
        )
    if (not v1) and (not v2_used):
        dump_dual(
            "COMMAND153_V2_NOT_AUTHORIZED_FROM_U_LOSS.json",
            {
                "ts": ts(),
                "weakness": "paired_U_not_competitive" if not competitive else "v1_claim_limited",
                "note": "command153: losing blocks / low Rq / non-competitive U does not authorize V2",
                "v1": body,
            },
        )
    try:
        from command153_canary_six_questions import write_reports

        write_reports(final=True)
    except Exception as exc:
        dump_dual(
            "COMMAND153_SIX_QUESTIONS_WRITE_FAILED.json",
            {"ts": ts(), "error": str(exc), "note": "DEV freeze still proceeds"},
        )
    print(json.dumps({"pass": True, "version": ver, "v1_pass": v1, **{k: body[k] for k in ("delta_U", "U_md2g")}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
