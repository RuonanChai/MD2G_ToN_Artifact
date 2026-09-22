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

"""Read-only Rb=0 audit over VALID canary cells. Does not retune or stop the orch."""
import json
import sys
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
from command147_io import dump_dual, ts  # noqa: E402
from command148_rb_lineage import rb_lineage  # noqa: E402

ART = TON / "artifacts" / "command148_canary120"
QUEUE = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
if QUEUE.is_file():
    try:
        _q = json.loads(QUEUE.read_text())
        if str(_q.get("epoch") or "") == "post_physical_pressure_rbv1" or _q.get("art"):
            ART = Path(_q["art"]) if _q.get("art") else TON / "artifacts" / "command148_canary120_rbv1"
    except Exception:
        pass
if (REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_RELEASE.json").is_file():
    ART = TON / "artifacts" / "command148_canary120_rbv1"


def main() -> int:
    done = []
    if QUEUE.is_file():
        done = list(json.loads(QUEUE.read_text()).get("completed") or [])
    rows = []
    n_fail = 0
    classes = {}
    bsh = []
    for key in done:
        cell = ART / key
        if not (cell / "CELL_DONE.json").is_file():
            continue
        metrics = {}
        mp = cell / "CELL_METRICS.json"
        if mp.is_file():
            try:
                loaded = json.loads(mp.read_text())
            except Exception:
                loaded = None
            if isinstance(loaded, dict):
                metrics = loaded
        lin = rb_lineage(cell, metrics)
        classes[lin["class"]] = classes.get(lin["class"], 0) + 1
        if not lin["pass"]:
            n_fail += 1
        if metrics.get("B_shared") is not None:
            bsh.append(int(metrics["B_shared"]))
        rows.append(
            {
                "key": key,
                "class": lin["class"],
                "pass": lin["pass"],
                "U": metrics.get("U"),
                "Ro": metrics.get("Ro_component"),
                "Rq": metrics.get("Rq"),
                "Rb": metrics.get("Rb"),
                "B_shared": metrics.get("B_shared"),
                "B_unicast": metrics.get("B_unicast"),
                "dump_sum": lin["last_dump_bytes_sum"],
                "rx_sum": lin["last_rx_bytes_sum"],
                "perf_Rb": lin["perf_reward_R_b_unique"],
                "perf_stall": lin["perf_stall_total_sec_unique"],
            }
        )
    all_placeholder = bool(rows) and all(
        r["class"] == "RB_RESERVED_PHYSICAL_PRESSURE_PLACEHOLDER_ZERO" for r in rows
    )
    all_computed = bool(rows) and all(r["class"] == "RB_PHYSICAL_PRESSURE_COMPUTED" for r in rows)
    all_rb0 = bool(rows) and all(float(r.get("Rb") or 0) == 0.0 for r in rows if r.get("Rb") is not None)
    traffic_varies = (max(bsh) - min(bsh) > 1_000_000) if len(bsh) >= 2 else False
    post_rb = (REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_RELEASE.json").is_file()
    if all_computed:
        verdict = "RB_PHYSICAL_PRESSURE_COMPUTED_POST_RB; NOT_SITUATION_B_VOLUME_COST; do_not_claim_bandwidth_via_Rb"
        situation = "A_COMPUTED"
        paper_rb0 = False
    elif all_placeholder:
        verdict = (
            "NOT_SITUATION_B_VOLUME_COST; "
            "NOT_MEASURED_UNDER_BUDGET; "
            "RB_RESERVED_PLACEHOLDER_ZERO_WITH_PHYSICAL_BYTE_LINEAGE"
        )
        situation = "A_UNIMPLEMENTED"
        paper_rb0 = True
    else:
        verdict = "MIXED_OR_PARTIAL_RB_LINEAGE; continue_canary_no_retune"
        situation = "A_MIXED"
        paper_rb0 = False
    body = {
        "ts": ts(),
        "token": "COMMAND148_RB_ZERO_AUDIT",
        "n_valid": len(rows),
        "n_fail": n_fail,
        "all_placeholder_zero": all_placeholder,
        "all_physical_pressure_computed": all_computed,
        "all_metrics_Rb_zero": all_rb0,
        "physical_bytes_present_and_varying": bool(rows) and all(r["dump_sum"] > 64 or r["rx_sum"] > 64 for r in rows) and traffic_varies,
        "B_shared_min": min(bsh) if bsh else None,
        "B_shared_max": max(bsh) if bsh else None,
        "classes": classes,
        "situation": situation,
        "verdict": verdict,
        "paper_U_is_Rb0_projection": paper_rb0,
        "post_rb_epoch": post_rb,
        "do_not_claim_bandwidth_via_Rb": True,
        "bandwidth_evidence": ["Ro_component", "B_shared_component", "B_unicast_component", "dump_bytes", "eth0_rx_bytes"],
        "continue_canary": True,
        "strategy_retune": False,
        "rows": rows,
        "loot_sealed": True,
    }
    dump_dual("COMMAND148_RB_ZERO_AUDIT.json", body)
    md = [
        "# command148 Rb=0 audit",
        "",
        f"- ts: `{body['ts']}`",
        f"- n_valid: `{len(rows)}`",
        f"- verdict: `{body['verdict']}`",
        f"- situation: `{body['situation']}` (frozen Rb is pressure, not volume)",
        f"- all Rb=0: `{all_rb0}`",
        f"- physical bytes present and B_shared varies: `{body['physical_bytes_present_and_varying']}` ({body['B_shared_min']} … {body['B_shared_max']})",
        f"- paper U is U|Rb=0 projection: `{str(paper_rb0).lower()}`",
        "- do not claim bandwidth efficiency from Rb; use Ro_component / B_shared / B_unicast",
        "- stall_last=0 is the same nested-client placeholder class (not this audit's pass/fail)",
        "- no strategy retune; canary continues",
        "",
        "| key | U | Ro | Rq | Rb | B_shared | dump_sum | class |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        md.append(
            f"| `{r['key']}` | {float(r.get('U') or 0):.4f} | {float(r.get('Ro') or 0):.4f} | "
            f"{float(r.get('Rq') or 0):.4f} | {float(r.get('Rb') or 0):.4f} | {r.get('B_shared')} | "
            f"{r.get('dump_sum')} | `{r['class']}` |"
        )
    text = "\n".join(md) + "\n"
    for root in (REPO / "reviews" / "command148", TON / "reviews" / "command148"):
        root.mkdir(parents=True, exist_ok=True)
        (root / "RB_ZERO_AUDIT.md").write_text(text)
    print(
        json.dumps(
            {
                "pass": n_fail == 0 and (all_placeholder or all_computed),
                "n_valid": len(rows),
                "n_fail": n_fail,
                "classes": classes,
                "paper_U_is_Rb0_projection": paper_rb0,
            }
        )
    )
    return 0 if n_fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
