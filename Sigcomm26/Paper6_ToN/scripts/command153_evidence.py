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

"""Build command153 final evidence package from canonical rbv1/DEV/scaling/holdout only."""
import csv
import json
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
from command147_io import dump_dual, sha256_file, token, ts  # noqa: E402

STRATS = [
    "MD2G_COMPONENT",
    "HV3_COMPONENT",
    "CLUSTERING_COMPONENT",
    "RULE_COMPONENT",
    "MOQ_UNICAST_COMPONENT",
]
SAME = ["HV3_COMPONENT", "CLUSTERING_COMPONENT", "RULE_COMPONENT"]
FINAL = TON / "final"
FIG = FINAL / "COMMAND153_FIGURE_SOURCE_DATA"
HASH_FILES = [
    TON / "lib" / "command148_canary_audit.py",
    TON / "lib" / "command148_canary_metrics.py",
    TON / "lib" / "command148_component_policy.py",
    TON / "lib" / "command147_nested_client.py",
    TON / "lib" / "command147_io.py",
    TON / "lib" / "command151_physical_pressure.py",
    TON / "scripts" / "command148_canary_cell.py",
    TON / "scripts" / "command137_proc.py",
    TON / "scripts" / "command148_canary_v1_gate.py",
    TON / "scripts" / "command148_main_dev.py",
    TON / "scripts" / "command152_production_supervisor.py",
    TON / "scripts" / "command153_continue.py",
    TON / "scripts" / "command153_cross_stack_dash.py",
    TON / "scripts" / "command153_evidence.py",
    TON / "scripts" / "command153_final_reviews.py",
    TON / "scripts" / "command153_classify_and_repair.py",
    REPO / "DASH" / "rolling_dash_experiment.py",
    REPO / "moq_sub_with_latency.py",
    REPO / "moq_cluster_Sigcomm.py",
]


def exists(name: str) -> bool:
    return (REPO / "state" / f"{name}.json").is_file()


def _queue_keys(qname: str) -> list[str]:
    qp = REPO / "state" / qname
    if not qp.is_file():
        return []
    try:
        return [str(k) for k in (json.loads(qp.read_text()).get("completed") or [])]
    except Exception:
        return []


def _cell_row(cell: Path) -> dict | None:
    if not cell.is_dir() or "_INVALID" in cell.name or "_attempt" in cell.name:
        return None
    if not (cell / "CELL_DONE.json").is_file():
        return None
    mp = cell / "CELL_METRICS.json"
    if not mp.is_file():
        return None
    raw = mp.read_text().strip()
    if raw in ("", "null"):
        return None
    try:
        m = json.loads(raw)
    except Exception:
        return None
    if not isinstance(m, dict) or m.get("U") is None:
        return None
    if m.get("paper_U_is_Rb0_projection"):
        return None
    m["key"] = m.get("key") or cell.name
    m["cell_dir"] = str(cell)
    try:
        done = json.loads((cell / "CELL_DONE.json").read_text())
        if done.get("epoch_id") and not m.get("epoch_id"):
            m["epoch_id"] = done.get("epoch_id")
    except Exception:
        pass
    return m


def _load_rows_for_keys(art: Path, keys: list[str]) -> list[dict]:
    out = []
    for key in keys:
        row = _cell_row(art / key)
        if row is not None:
            out.append(row)
    return out


def _load_rows(art: Path, prefix: str) -> list[dict]:
    """Diagnostic-only iterator. Final stats must use queue keys."""
    out = []
    if not art.is_dir():
        return out
    for cell in sorted(art.iterdir()):
        if not cell.is_dir() or not cell.name.startswith(prefix):
            continue
        row = _cell_row(cell)
        if row is not None:
            out.append(row)
    return out


def _mean(xs: list[float]) -> float | None:
    return statistics.mean(xs) if xs else None


def _blk(r: dict) -> str:
    return f"{r.get('content')}_{r.get('network')}_u{r.get('users')}_s{r.get('seed')}"


def _by_strategy(rows: list[dict]) -> dict:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("strategy") or "")].append(r)
    out = {}
    for s, rs in by.items():
        out[s] = {
            "n": len(rs),
            "U": _mean([float(x["U"]) for x in rs]),
            "Rq": _mean([float(x.get("Rq") or 0) for x in rs]),
            "Ro_component": _mean([float(x.get("Ro_component") or 0) for x in rs]),
            "Rb": _mean([float(x.get("Rb") or 0) for x in rs]),
            "weak_user_Rq": _mean([float(x.get("weak_user_Rq") or 0) for x in rs]),
        }
    return out


def _matched(rows: list[dict]) -> list[dict]:
    blocks: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        blocks[_blk(r)][str(r.get("strategy") or "")] = r
    out = []
    for blk, recs in sorted(blocks.items()):
        if not all(s in recs for s in STRATS):
            continue
        md = recs["MD2G_COMPONENT"]
        same = [recs[s] for s in SAME]
        best = max(same, key=lambda x: float(x["U"]))
        out.append(
            {
                "block": blk,
                "content": md.get("content"),
                "network": md.get("network"),
                "users": md.get("users"),
                "seed": md.get("seed"),
                "MD2G_U": md["U"],
                "MD2G_Rq": md.get("Rq"),
                "MD2G_Ro": md.get("Ro_component"),
                "MD2G_Rb": md.get("Rb"),
                "MD2G_weak_user_Rq": md.get("weak_user_Rq"),
                "strongest_same": best.get("strategy"),
                "strongest_same_U": best["U"],
                "delta_U": float(md["U"]) - float(best["U"]),
                "unicast_U": recs["MOQ_UNICAST_COMPONENT"]["U"],
            }
        )
    return out


def _tier(matched: list[dict], loot_matched: list[dict] | None = None) -> str:
    """command148 A/B/C. Noise band from frozen canary margins (±0.03)."""
    if not matched:
        return "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_C"
    noise = 0.03
    p = REPO / "state" / "COMMAND148_CANARY_NOISE_MARGINS_PREDECLARED.json"
    if p.is_file():
        try:
            noise = float(json.loads(p.read_text()).get("paired_U_noise_abs") or 0.03)
        except Exception:
            noise = 0.03
    deltas = [float(x["delta_U"]) for x in matched]
    mu = statistics.mean(deltas)
    wins = sum(1 for d in deltas if d > noise)
    losses = sum(1 for d in deltas if d < -noise)
    high = [x for x in matched if int(x.get("users") or 0) >= 60]
    low = [x for x in matched if int(x.get("users") or 0) <= 20]
    high_mu = statistics.mean([float(x["delta_U"]) for x in high]) if high else None
    low_mu = statistics.mean([float(x["delta_U"]) for x in low]) if low else None
    loot_mu = None
    if loot_matched:
        loot_mu = statistics.mean([float(x["delta_U"]) for x in loot_matched])
    robust_a = (
        mu > noise
        and wins >= max(1, int(0.7 * len(matched)))
        and (low_mu is None or low_mu >= -noise)
    )
    if robust_a and (loot_mu is None or loot_mu >= -noise):
        return "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_A"
    crossover_b = high_mu is not None and high_mu > noise and (low_mu is None or low_mu < 0)
    competitive_b = mu >= -noise and wins > losses
    if crossover_b or competitive_b:
        return "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B"
    return "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_C"


def main() -> int:
    if not exists("COMMAND153_LOOT_HOLDOUT_FROZEN"):
        print(json.dumps({"pass": False, "reason": "loot_not_frozen"}))
        return 2
    FINAL.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    canary = _load_rows_for_keys(
        TON / "artifacts" / "command148_canary120_rbv1",
        _queue_keys("COMMAND148_CANARY120_QUEUE.json"),
    )
    pre_rb = TON / "artifacts" / "command148_canary120"
    dev = _load_rows_for_keys(
        TON / "artifacts" / "command148_maindev",
        _queue_keys("COMMAND148_MAINDEV_QUEUE.json"),
    )
    scaling = _load_rows_for_keys(
        TON / "artifacts" / "command153_scaling",
        _queue_keys("COMMAND153_SCALING_QUEUE.json"),
    )
    loot = _load_rows_for_keys(
        TON / "artifacts" / "command153_loot_holdout",
        _queue_keys("COMMAND153_LOOT_QUEUE.json"),
    )
    if any(_load_rows(pre_rb, "c148can_")):
        # presence is diagnostic only; never mixed into primary stats
        pass
    matched = _matched(dev or canary)
    loot_matched = _matched(loot)
    epoch_id = None
    ep = REPO / "state" / "COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE.json"
    if ep.is_file():
        try:
            epb = json.loads(ep.read_text())
            epoch_id = epb.get("epoch_id") or epb.get("epoch")
        except Exception:
            epoch_id = None
    # Attach freeze epoch to rows that lack it (provenance); reject conflicting stamps.
    epoch_conflicts = []
    for row in canary + dev + scaling + loot:
        rid = row.get("epoch_id")
        if not rid and epoch_id:
            row["epoch_id"] = epoch_id
        elif rid and epoch_id and str(rid) != str(epoch_id):
            epoch_conflicts.append({"key": row.get("key"), "epoch_id": rid})
    if epoch_conflicts:
        token(
            "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
            {
                "reason": "mixed_epoch_in_canonical_rows",
                "expected_epoch_id": epoch_id,
                "n_conflicts": len(epoch_conflicts),
                "sample": epoch_conflicts[:8],
                "kill_live_cell": False,
            },
        )
        print(json.dumps({"pass": False, "reason": "mixed_epoch_in_canonical_rows", "n": len(epoch_conflicts)}))
        return 4
    primary = {
        "ts": ts(),
        "pre_rb_56": "DIAGNOSTIC_ONLY_NOT_FOR_FINAL_CLAIMS",
        "epoch_id": epoch_id,
        "canary_rbv1_n": len(canary),
        "dev_n": len(dev),
        "scaling_n": len(scaling),
        "h2_n": len(_queue_keys("COMMAND153_CROSS_STACK_DASH_QUEUE.json")),
        "loot_n": len(loot),
        "canary_by_strategy": _by_strategy(canary),
        "dev_by_strategy": _by_strategy(dev),
        "loot_by_strategy": _by_strategy(loot),
        "n_matched_dev_or_canary": len(matched),
        "mean_delta_U_vs_strongest_same": _mean([float(x["delta_U"]) for x in matched]),
        "never_claim_zero_stall": True,
        "delay": "NOT_IN_FINAL_CLAIM_CONTRACT",
        "rb_is_not_bandwidth_saving": True,
        "not_150_new_executions": True,
        "na_not_experimental_validation": True,
        "epoch_conflicts_n": 0,
    }
    (FINAL / "COMMAND153_PRIMARY_STATS.json").write_text(json.dumps(primary, indent=2) + "\n")
    dump_dual("COMMAND153_PRIMARY_STATS.json", primary)
    csv_p = FINAL / "COMMAND153_MATCHED_BLOCKS.csv"
    fields = [
        "block",
        "content",
        "network",
        "users",
        "seed",
        "MD2G_U",
        "MD2G_Rq",
        "MD2G_Ro",
        "MD2G_Rb",
        "MD2G_weak_user_Rq",
        "strongest_same",
        "strongest_same_U",
        "delta_U",
        "unicast_U",
    ]
    with csv_p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in matched:
            w.writerow({k: row.get(k) for k in fields})
    (FIG / "matched_blocks.json").write_text(json.dumps(matched, indent=2) + "\n")
    (FIG / "canary_rbv1.json").write_text(json.dumps(canary, indent=2, default=str) + "\n")
    (FIG / "dev.json").write_text(json.dumps(dev, indent=2, default=str) + "\n")
    (FIG / "scaling.json").write_text(json.dumps(scaling, indent=2, default=str) + "\n")
    (FIG / "loot.json").write_text(json.dumps(loot, indent=2, default=str) + "\n")
    hashes = {"ts": ts(), "files": {}}
    for p in HASH_FILES:
        if p.is_file():
            hashes["files"][str(p.relative_to(REPO))] = sha256_file(p)
    (FINAL / "COMMAND153_ALL_HASHES.json").write_text(json.dumps(hashes, indent=2) + "\n")
    dump_dual("COMMAND153_ALL_HASHES.json", hashes)
    ledger = {}
    if (REPO / "state" / "COMMAND153_KNOWN_FAILURES_AND_FIXES.json").is_file():
        ledger = json.loads((REPO / "state" / "COMMAND153_KNOWN_FAILURES_AND_FIXES.json").read_text())
    ledger_body = {"ts": ts(), "lessons": ledger.get("lessons") or [], "loot_frozen": True}
    dump_dual("COMMAND153_CANONICAL_LEDGER.json", ledger_body)
    (FINAL / "COMMAND153_CANONICAL_LEDGER.json").write_text(json.dumps(ledger_body, indent=2) + "\n")
    scale_stats = {
        "ts": ts(),
        "n": len(scaling),
        "logical_n": 150,
        "exact_dev_reuse_n_planned": 90,
        "newly_launched_n_planned": 60,
        "exact_dev_reuse_n": sum(1 for r in scaling if int(r.get("users") or 0) in (20, 60, 100)),
        "newly_launched_n": sum(1 for r in scaling if int(r.get("users") or 0) in (10, 40)),
        "not_150_new_executions": True,
        "by_users": {},
        "note": "150-key logical matrix: 90 exact DEV reuses (u20/60/100) + 60 newly launched (u10/40 only)",
    }
    by_u: dict[str, list[float]] = defaultdict(list)
    for r in scaling:
        by_u[str(r.get("users"))].append(float(r["U"]))
    scale_stats["by_users"] = {k: {"n": len(v), "U": _mean(v)} for k, v in by_u.items()}
    (FINAL / "COMMAND153_SCALING_STATS.json").write_text(json.dumps(scale_stats, indent=2) + "\n")
    abl = {}
    if (REPO / "state" / "COMMAND153_ABLATION_MANIFEST.json").is_file():
        abl = json.loads((REPO / "state" / "COMMAND153_ABLATION_MANIFEST.json").read_text())
    abl_complete = {}
    acp = REPO / "state" / "COMMAND153_ABLATION_COMPLETE.json"
    if acp.is_file():
        try:
            abl_complete = json.loads(acp.read_text())
        except Exception:
            abl_complete = {}
    compat = {}
    cpp = REPO / "state" / "COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE.json"
    if cpp.is_file():
        compat = json.loads(cpp.read_text())
        (FINAL / "COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE.json").write_text(json.dumps(compat, indent=2) + "\n")
    (FINAL / "COMMAND153_ABLATION_STATS.json").write_text(
        json.dumps(
            {
                "ts": ts(),
                "manifest": abl,
                "complete": {
                    "a0_reuse_dev_md2g_n": abl_complete.get("a0_reuse_dev_md2g_n"),
                    "a6_reuse_dev_rule_n": abl_complete.get("a6_reuse_dev_rule_n"),
                    "no_288_live_matrix": True,
                },
                "not_experimental_validation_for_na": True,
                "a1_a5_a7_not_applicable_not_validation": True,
                "a0_a6_reuse_dev_only": True,
                "paper_claim_compatibility": "COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE",
            },
            indent=2,
        )
        + "\n"
    )
    fov = {"ts": ts(), "status": "NOT_APPLICABLE", "reason": "no live overlap knob"}
    if (REPO / "state" / "COMMAND153_FOV_NOT_APPLICABLE.json").is_file():
        fov = json.loads((REPO / "state" / "COMMAND153_FOV_NOT_APPLICABLE.json").read_text())
    fov["not_experimental_validation"] = True
    fov["not_a_sensitivity_result"] = True
    fov["paper_claim_compatibility"] = "COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE"
    (FINAL / "COMMAND153_FOV_STATS.json").write_text(json.dumps(fov, indent=2) + "\n")
    oh = {}
    if (REPO / "state" / "COMMAND153_OVERHEAD_COMPLETE.json").is_file():
        oh = json.loads((REPO / "state" / "COMMAND153_OVERHEAD_COMPLETE.json").read_text())
    (FINAL / "COMMAND153_OVERHEAD_STATS.json").write_text(json.dumps(oh, indent=2) + "\n")
    hold = {
        "ts": ts(),
        "n": len(loot),
        "by_strategy": _by_strategy(loot),
        "unseen_windows": True,
        "no_post_holdout_tuning": True,
    }
    (FINAL / "COMMAND153_HOLDOUT_STATS.json").write_text(json.dumps(hold, indent=2) + "\n")
    h2_keys = _queue_keys("COMMAND153_CROSS_STACK_DASH_QUEUE.json")
    h2_art = TON / "artifacts" / "command153_cross_stack_dash"
    h2_rows = []
    for key in h2_keys:
        cell = h2_art / key
        done = {}
        if (cell / "CELL_DONE.json").is_file():
            try:
                done = json.loads((cell / "CELL_DONE.json").read_text())
            except Exception:
                done = {}
        rb = None
        sp = cell / "PHYSICAL_PRESSURE_SUMMARY.json"
        if sp.is_file():
            try:
                rb = json.loads(sp.read_text()).get("Rb")
            except Exception:
                rb = None
        h2_rows.append(
            {
                "key": key,
                "strategy": done.get("dash_strategy") or done.get("strategy"),
                "content": done.get("content"),
                "network": done.get("network"),
                "users": done.get("users"),
                "seed": done.get("seed"),
                "native_score_ok": (done.get("score") or {}).get("ok"),
                "physical_pressure_samples": done.get("physical_pressure_samples"),
                "Rb": rb,
                "canonical_U_not_primary": True,
            }
        )
    h2_stats = {
        "ts": ts(),
        "n": len(h2_rows),
        "not_same_substrate": True,
        "do_not_use_as_primary_md2g_vs_baseline": True,
        "independent_unicast_Ro": 0,
        "rows": h2_rows,
    }
    (FINAL / "COMMAND153_CROSS_STACK_DASH_STATS.json").write_text(json.dumps(h2_stats, indent=2) + "\n")
    (FIG / "cross_stack_dash.json").write_text(json.dumps(h2_stats, indent=2) + "\n")
    unfavorable = [x for x in matched if float(x["delta_U"]) < 0]
    (FINAL / "COMMAND153_LIMITATIONS_AND_UNFAVORABLE_RESULTS.md").write_text(
        "# COMMAND153 limitations and unfavorable results\n\n"
        "- Never claim zero stall.\n"
        "- Delay is NOT_IN_FINAL_CLAIM_CONTRACT.\n"
        "- Rb is physical bottleneck pressure, not bandwidth saving; use Ro/B_shared/B_unicast separately.\n"
        "- Pre-Rb 56/120 cells are DIAGNOSTIC_ONLY and excluded from final U/CI.\n"
        "- MOQ_UNICAST is a delivery-mode comparison, not same-substrate.\n"
        "- NOT_APPLICABLE (A1–A5/A7, FoV 20/40/60/80) is never experimental validation; command146 F8/F9 cannot be filled from NA tokens.\n"
        "- Scaling is a 150-key logical matrix: 90 exact DEV reuses + 60 newly launched cells, not 150 new executions.\n"
        f"- Unfavorable matched blocks (MD2G delta_U < 0): {len(unfavorable)} / {len(matched)}\n"
        + "".join(f"- `{x['block']}` delta_U={x['delta_U']:.4f} vs {x['strongest_same']}\n" for x in unfavorable[:40])
    )
    (FINAL / "COMMAND153_REPRODUCIBILITY_MANIFEST.md").write_text(
        "# COMMAND153 reproducibility\n\n"
        "- Executor: `tmux:command152_orch`\n"
        "- Watch: `tmux:command152_watch`\n"
        "- Canary art: `artifacts/command148_canary120_rbv1`\n"
        "- Epoch: post_physical_pressure_rbv1\n"
        "- Media: nested b0,db1,db2,e1,e2\n"
        f"- Runtime hashes: `final/COMMAND153_ALL_HASHES.json` n={len(hashes['files'])}\n"
        "- Loot holdout frozen before this package.\n"
    )
    src = TON / "final" / "COMMAND153_KNOWN_FAILURES_AND_FIXES.md"
    if not src.is_file():
        alt = REPO / "status" / "COMMAND153_KNOWN_FAILURES_AND_FIXES.md"
        if alt.is_file():
            src = alt
    if src.is_file():
        (FINAL / "COMMAND153_KNOWN_FAILURES_AND_FIXES.md").write_text(src.read_text())
    elif ledger.get("lessons"):
        # Fail-closed synthesis from frozen ledger JSON so the required artifact cannot be absent.
        lines = ["# COMMAND153 known failures and certified fixes", ""]
        for L in ledger.get("lessons") or []:
            lines += [
                f"## {L.get('failure_id')}",
                "",
                f"- status: `{L.get('status')}`",
                f"- symptom: {L.get('symptom')}",
                f"- root_cause: {L.get('root_cause')}",
                f"- repair: {L.get('repair')}",
                f"- recertification: {L.get('recertification')}",
                f"- do_not_repeat: {L.get('do_not_repeat')}",
                "",
            ]
        (FINAL / "COMMAND153_KNOWN_FAILURES_AND_FIXES.md").write_text("\n".join(lines) + "\n")
    limited = exists("COMMAND148_COMPONENT_CONTROLLER_CLAIM_LIMITED")
    term = _tier(matched, loot_matched)
    if limited and term == "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_A":
        term = "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B"
    claim = {
        "ts": ts(),
        "never_claim_zero_stall": True,
        "delay": "NOT_IN_FINAL_CLAIM_CONTRACT",
        "rb_is_not_bandwidth_saving": True,
        "pre_rb_56": "DIAGNOSTIC_ONLY_NOT_FOR_FINAL_CLAIMS",
        "terminal": term,
        "claims": [
            {
                "claim": "nested incremental component contract is the scientific media contract",
                "status": "SUPPORTED",
                "evidence": ["COMMAND147_COMPONENT_ASSETS_FULLY_SCIENTIFICALLY_CERTIFIED"],
                "regimes": "all command148/151/152/153 nested cells",
                "counterexamples": [],
            },
            {
                "claim": "MD2G strictly dominates all same-substrate baselines on every block",
                "status": "NOT_SUPPORTED" if unfavorable else "CONDITIONALLY_SUPPORTED",
                "evidence": ["final/COMMAND153_MATCHED_BLOCKS.csv", "final/COMMAND153_PRIMARY_STATS.json"],
                "regimes": "matched five-strategy blocks on DEV/canary",
                "counterexamples": [x["block"] for x in unfavorable[:20]],
            },
            {
                "claim": "component-aware shared delivery and Ro/B_shared/B_unicast accounting are valid",
                "status": "SUPPORTED" if canary or dev else "NOT_SUPPORTED",
                "evidence": ["final/COMMAND153_PRIMARY_STATS.json"],
                "regimes": "post-Rb rbv1 and DEV",
                "counterexamples": [],
            },
            {
                "claim": "A1–A5/A7 ablations and FoV 20/40/60/80 experimentally validate those mechanisms",
                "status": "NOT_APPLICABLE_NOT_VALIDATION",
                "evidence": [
                    "final/COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE.json",
                    "final/COMMAND153_ABLATION_STATS.json",
                    "final/COMMAND153_FOV_STATS.json",
                ],
                "regimes": "none; NA is contract/controller fact",
                "counterexamples": ["do not plot NA as F8/F9 results"],
            },
            {
                "claim": "scaling executed 150 new Mininet cells",
                "status": "NOT_SUPPORTED",
                "evidence": ["final/COMMAND153_SCALING_STATS.json"],
                "regimes": "150 logical keys = 90 DEV reuse + 60 new launches",
                "counterexamples": ["not_150_new_executions"],
            },
        ],
    }
    (FINAL / "COMMAND153_CLAIM_EVIDENCE_MATRIX.md").write_text(
        "# COMMAND153 claim-evidence matrix\n\n"
        + "\n".join(
            f"- `{c['status']}`: {c['claim']} evidence={c['evidence']} counterexamples={c.get('counterexamples')}"
            for c in claim["claims"]
        )
        + f"\n\nTerminal: `{term}`\n"
    )
    dump_dual("COMMAND153_CLAIM_EVIDENCE_MATRIX.json", claim)
    subprocess.run(
        [
            str(REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"),
            "-u",
            str(TON / "scripts" / "command153_final_reviews.py"),
        ],
        cwd=str(REPO),
        check=False,
    )
    if not (FINAL / "COMMAND153_SIX_REVIEWS.md").is_file():
        token(
            "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
            {"reason": "six_reviews_missing_after_final_reviews", "kill_live_cell": False},
        )
        print(json.dumps({"pass": False, "reason": "six_reviews_missing_after_final_reviews"}))
        return 4
    required = [
        FINAL / "COMMAND153_CANONICAL_LEDGER.json",
        FINAL / "COMMAND153_ALL_HASHES.json",
        FINAL / "COMMAND153_PRIMARY_STATS.json",
        FINAL / "COMMAND153_MATCHED_BLOCKS.csv",
        FINAL / "COMMAND153_SCALING_STATS.json",
        FINAL / "COMMAND153_ABLATION_STATS.json",
        FINAL / "COMMAND153_FOV_STATS.json",
        FINAL / "COMMAND153_OVERHEAD_STATS.json",
        FINAL / "COMMAND153_HOLDOUT_STATS.json",
        FINAL / "COMMAND153_CROSS_STACK_DASH_STATS.json",
        FINAL / "COMMAND153_REPRODUCIBILITY_MANIFEST.md",
        FINAL / "COMMAND153_LIMITATIONS_AND_UNFAVORABLE_RESULTS.md",
        FINAL / "COMMAND153_CLAIM_EVIDENCE_MATRIX.md",
        FINAL / "COMMAND153_SIX_REVIEWS.md",
        FINAL / "COMMAND153_KNOWN_FAILURES_AND_FIXES.md",
        FINAL / "COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE.json",
    ]
    missing = [str(p.name) for p in required if not p.is_file() or p.stat().st_size == 0]
    need_tokens = [
        "COMMAND148_MAINDEV_COMPLETE",
        "COMMAND153_CROSS_STACK_DASH_COMPLETE",
        "COMMAND153_SCALING_COMPLETE",
        "COMMAND153_FINAL_DEV_FROZEN",
        "COMMAND153_LOOT_HOLDOUT_FROZEN",
    ]
    missing_tokens = [t for t in need_tokens if not exists(t)]
    h2_n = 0
    h2p = REPO / "state" / "COMMAND153_CROSS_STACK_DASH_COMPLETE.json"
    if h2p.is_file():
        try:
            h2_n = int(json.loads(h2p.read_text()).get("n") or 0)
        except Exception:
            h2_n = 0
    if (
        missing
        or missing_tokens
        or len(loot) < 315
        or len(canary) < 120
        or len(dev) < 945
        or len(scaling) < 150
        or h2_n < 48
    ):
        print(
            json.dumps(
                {
                    "pass": False,
                    "reason": "evidence_incomplete",
                    "missing": missing,
                    "missing_tokens": missing_tokens,
                    "loot_n": len(loot),
                    "canary_n": len(canary),
                    "dev_n": len(dev),
                    "scaling_n": len(scaling),
                    "h2_n": h2_n,
                }
            )
        )
        token(
            "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
            {
                "reason": "evidence_incomplete",
                "missing": missing,
                "missing_tokens": missing_tokens,
                "loot_n": len(loot),
                "canary_n": len(canary),
                "dev_n": len(dev),
                "scaling_n": len(scaling),
                "h2_n": h2_n,
                "kill_live_cell": False,
            },
        )
        return 4
    token(term, {"evidence_package": True, "n_matched": len(matched)})
    dump_dual(
        "TON_COMPONENT_MD2G_EVIDENCE_PACKAGE_READY.json",
        {"ts": ts(), "token": "TON_COMPONENT_MD2G_EVIDENCE_PACKAGE_READY", "true": True, "terminal": term},
    )
    print(json.dumps({"pass": True, "phase": "terminal", "token": term, "n_matched": len(matched), "canary_n": len(canary), "loot_n": len(loot)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
