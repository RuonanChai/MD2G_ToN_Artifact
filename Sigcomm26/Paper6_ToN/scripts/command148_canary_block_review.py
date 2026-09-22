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

"""Level-2 matched five-strategy canary block. No V1 promotion. No strategy retune.

Reports target vs decoded occupancy, receiver-set size, and component completion.
Quality uses frozen non-monotonic Q_norm; never ranks quality by Rep ID.
Unauthorized component payload remains a fail-closed fidelity error (handled by cell audit).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
from command147_io import canary_rbv1_art, dump_dual, ts  # noqa: E402
from command148_canary_metrics import STATES, composition_delivery_stats  # noqa: E402
from component_actuation_plan import TRACKS  # noqa: E402

ART = canary_rbv1_art()
OUT = REPO / "reviews" / "command148"
TON_OUT = TON / "reviews" / "command148"
MARGINS = REPO / "state" / "COMMAND148_CANARY_NOISE_MARGINS.json"
STRATS = [
    "MD2G_COMPONENT",
    "HV3_COMPONENT",
    "CLUSTERING_COMPONENT",
    "RULE_COMPONENT",
    "MOQ_UNICAST_COMPONENT",
]
SAME_SUBSTRATE = ["MD2G_COMPONENT", "HV3_COMPONENT", "CLUSTERING_COMPONENT", "RULE_COMPONENT"]


def _spec_from_key(key: str, audit: dict) -> dict:
    return {
        "key": key,
        "content": audit.get("content"),
        "network": audit.get("network"),
        "users": audit.get("users"),
        "seed": audit.get("seed"),
        "strategy": audit.get("strategy"),
    }


def _enrich(cell: Path, audit: dict, metrics: dict) -> dict:
    spec = _spec_from_key(cell.name, audit)
    extra = composition_delivery_stats(cell, spec)
    out = dict(metrics)
    out.update(extra)
    out["strategy"] = spec["strategy"]
    out["key"] = spec["key"]
    out["U"] = metrics.get("U")
    out["Ro_component"] = metrics.get("Ro_component")
    out["Rq"] = metrics.get("Rq")
    out["Rb"] = metrics.get("Rb")
    out["weak_user_Rq"] = metrics.get("weak_user_Rq")
    out["stall_last"] = metrics.get("stall_last")
    return out


def _states_by_frozen_q(qn: dict) -> list[str]:
    return sorted(STATES, key=lambda st: (float(qn.get(st) or 0.0), st))


def _direction(rows: dict[str, dict]) -> dict:
    md2g = rows.get("MD2G_COMPONENT") or {}
    u_md = md2g.get("U")
    same = [rows[s]["U"] for s in SAME_SUBSTRATE if s in rows and rows[s].get("U") is not None and s != "MD2G_COMPONENT"]
    strongest = max(same) if same else None
    note = (
        "Direction uses canonical U (frozen Q_norm in Rq). "
        "Not a Rep-ID rank. Unfavorable MD2G is scientifically valid. "
        "Unauthorized payload is fail-closed, not a strategy score."
    )
    if u_md is None or strongest is None:
        return {"label": "ambiguous", "note": note, "md2g_U": u_md, "strongest_same_substrate_U": strongest}
    if u_md > strongest:
        lab = "favorable"
    elif u_md < strongest:
        lab = "unfavorable"
    else:
        lab = "ambiguous"
    return {
        "label": lab,
        "note": note,
        "md2g_U": u_md,
        "strongest_same_substrate_U": strongest,
        "delta_U": float(u_md) - float(strongest),
    }


def _md_block(blk: str, rec: dict) -> str:
    qn = rec.get("Q_norm_frozen") or {}
    order = _states_by_frozen_q(qn)
    lines = [
        f"# COMMAND148 Level-2 matched block `{blk}`",
        "",
        f"- ts: `{rec['ts']}`",
        f"- matched: `{rec['matched']}` (5 strategies)",
        "- quality: frozen non-monotonic Q_norm; **not** ranked by Rep ID",
        "- unauthorized component payload: fail-closed fidelity (cell audit), not a strategy score",
        "- Rb: physical bottleneck/network pressure (`paper_U_is_Rb0_projection=false` on rbv1). Bandwidth evidence is Ro_component / B_shared / B_unicast, not Rb.",
        f"- direction: `{rec['direction']['label']}`",
        f"- note: {rec['direction']['note']}",
        "",
        "## Frozen Q_norm (composition labels)",
        "",
        "| composition | Q_norm |",
        "|---|---|",
    ]
    for st in order:
        lines.append(f"| {st} | {float(qn.get(st) or 0.0):.6f} |")
    lines += ["", "## Per-strategy headline", "", "| strategy | U | Ro | Rq | Rb | weak_Rq |", "|---|---|---|---|---|---|"]
    for s in STRATS:
        r = rec["strategies"].get(s) or {}
        if not r:
            lines.append(f"| `{s}` | NA | NA | NA | NA | NA |")
            continue
        lines.append(
            f"| `{s}` | {float(r.get('U') or 0):.4f} | {float(r.get('Ro_component') or 0):.4f} | "
            f"{float(r.get('Rq') or 0):.4f} | {float(r.get('Rb') or 0):.4f} | {float(r.get('weak_user_Rq') or 0):.4f} |"
        )
    for s in STRATS:
        r = rec["strategies"].get(s) or {}
        if not r:
            continue
        lines += ["", f"## `{s}` occupancy / receivers / completion", ""]
        lines.append("| composition | Q_norm | target_occ | decoded_occ |")
        lines.append("|---|---|---|---|")
        tgt = r.get("target_state_occupancy") or {}
        dec = r.get("actual_decoded_state_occupancy") or {}
        for st in order:
            lines.append(
                f"| {st} | {float(qn.get(st) or 0.0):.6f} | {float(tgt.get(st) or 0.0):.4f} | {float(dec.get(st) or 0.0):.4f} |"
            )
        lines.append("")
        lines.append("| component | receiver_set_size | n_complete | completion_fraction |")
        lines.append("|---|---|---|---|")
        sizes = r.get("receiver_set_size") or {}
        comp = r.get("component_completion_fraction") or {}
        for c in TRACKS:
            cf = comp.get(c) or {}
            frac = cf.get("fraction")
            frac_s = "NA" if frac is None else f"{float(frac):.4f}"
            lines.append(f"| {c} | {int(sizes.get(c) or 0)} | {int(cf.get('n_complete_dump_gt_64') or 0)} | {frac_s} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    q = {}
    qp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
    if qp.is_file():
        q = json.loads(qp.read_text())
    done = list(q.get("completed") or [])
    blocks: dict[str, dict[str, dict]] = defaultdict(dict)
    qn_by_block: dict[str, dict] = {}
    for key in done:
        cell = ART / key
        audit_p = cell / "CELL_AUDIT.json"
        met_p = cell / "CELL_METRICS.json"
        if not audit_p.is_file() or not (cell / "CELL_DONE.json").is_file():
            continue
        audit = json.loads(audit_p.read_text())
        if not (audit.get("audit") or {}).get("pass"):
            continue
        metrics = json.loads(met_p.read_text()) if met_p.is_file() else {}
        if not isinstance(metrics, dict) or metrics.get("paper_U_is_Rb0_projection"):
            continue
        blk = f"{audit.get('content')}_{audit.get('network')}_u{audit.get('users')}_s{audit.get('seed')}"
        strat = str(audit.get("strategy") or metrics.get("strategy") or "")
        enriched = _enrich(cell, audit, metrics)
        blocks[blk][strat] = enriched
        qn_by_block[blk] = enriched.get("Q_norm_frozen") or qn_by_block.get(blk) or {}

    OUT.mkdir(parents=True, exist_ok=True)
    TON_OUT.mkdir(parents=True, exist_ok=True)
    matched = []
    summaries = {}
    for blk, rows in sorted(blocks.items()):
        have = [s for s in STRATS if s in rows]
        is_matched = have == STRATS
        rec = {
            "ts": ts(),
            "block": blk,
            "matched": is_matched,
            "strategies_present": have,
            "Q_norm_frozen": qn_by_block.get(blk) or {},
            "quality_ranked_by_rep_id": False,
            "unauthorized_payload": "fail_closed_fidelity_not_strategy_score",
            "Rb": "physical_pressure_computed_rbv1",
            "direction": _direction(rows) if is_matched else {"label": "incomplete_block", "note": "need all five VALID strategies"},
            "strategies": {s: rows[s] for s in have},
        }
        summaries[blk] = {
            "matched": is_matched,
            "strategies_present": have,
            "direction": rec["direction"]["label"],
            "md2g_U": (rows.get("MD2G_COMPONENT") or {}).get("U"),
        }
        if is_matched:
            matched.append(blk)
            (OUT / f"LEVEL2_{blk}.json").write_text(json.dumps(rec, indent=2) + "\n")
            (OUT / f"LEVEL2_{blk}.md").write_text(_md_block(blk, rec))
            (TON_OUT / f"LEVEL2_{blk}.json").write_text(json.dumps(rec, indent=2) + "\n")
            (TON_OUT / f"LEVEL2_{blk}.md").write_text(_md_block(blk, rec))

    body = {
        "ts": ts(),
        "completed": len(done),
        "matched_level2_blocks": matched,
        "n_matched": len(matched),
        "noise_margins": json.loads(MARGINS.read_text()).get("token") if MARGINS.is_file() else None,
        "md2g_aggregate_allowed": False,
        "quality_ranked_by_rep_id": False,
        "unauthorized_payload": "fail_closed_fidelity_not_strategy_score",
        "Rb": "physical_pressure_computed_rbv1",
        "art": str(ART),
        "pre_rb_excluded": True,
        "blocks": summaries,
        "loot_sealed": True,
    }
    (OUT / "CANARY_LEVEL2_BLOCKS.json").write_text(json.dumps(body, indent=2) + "\n")
    (TON_OUT / "CANARY_LEVEL2_BLOCKS.json").write_text(json.dumps(body, indent=2) + "\n")
    dump_dual("COMMAND148_CANARY_BLOCK_REVIEW.json", body)
    print(json.dumps({"pass": True, "completed": len(done), "n_matched": len(matched), "matched": matched}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
