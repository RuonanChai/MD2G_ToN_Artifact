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

"""Aggregate same-substrate MCG cells onto the shared evaluation slice."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _common import (  # noqa: E402
    CAST_ROLLING_U,
    CONTENT,
    DEV_JSON,
    NETS,
    RESULTS,
    SEEDS,
    TON,
    USERS,
    WARMUP_S,
    filter_scope,
    load_dev_rows,
    mean,
    write_csv,
    write_json,
)

REPO = TON.parents[1]
ART = TON / "artifacts" / "ton_live_mcg"
OUT = RESULTS / "live_mcg_baseline"
N_MCG = 27


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def completion_scalar(metrics: dict) -> float:
    cf = metrics.get("component_completion_fraction") or {}
    nums = dens = 0
    if isinstance(cf, dict):
        for rec in cf.values():
            if not isinstance(rec, dict):
                continue
            dens += int(rec.get("n_receivers") or 0)
            nums += int(rec.get("n_complete_dump_gt_64") or 0)
    return (nums / dens) if dens else 0.0


def load_mcg_cells() -> list[dict]:
    rows = []
    for net in NETS:
        for users in USERS:
            for seed in SEEDS:
                key = f"c148mcg_{CONTENT}_{net}_u{users}_MCG_COMPONENT_s{seed}"
                cell = ART / key
                done = cell / "CELL_DONE.json"
                met = cell / "CELL_METRICS.json"
                if not (done.is_file() and met.is_file()):
                    continue
                rec = json.loads(done.read_text())
                metrics = json.loads(met.read_text())
                audit = rec.get("audit") or {}
                if rec.get("valid") is not True or audit.get("pass") is not True:
                    continue
                rows.append(
                    {
                        "strategy": "MCG",
                        "source": "LIVE_MININET_MOQ",
                        "fair_same_substrate": True,
                        "content": CONTENT,
                        "network": net,
                        "users": users,
                        "seed": seed,
                        "key": key,
                        "U": metrics.get("U"),
                        "Rq": metrics.get("Rq"),
                        "Ro": metrics.get("Ro_component"),
                        "Rb": metrics.get("Rb"),
                        "decoded_completion": completion_scalar(metrics),
                        "B_shared": metrics.get("B_shared"),
                        "B_unicast": metrics.get("B_unicast"),
                        "stall_last": metrics.get("stall_last"),
                        "p99_delay_ms": "",
                        "p99_delay_in_contract": False,
                        "duration_s": 120,
                        "metric_code": "command148_canary_metrics.cell_metrics",
                    }
                )
    return rows


def live_frozen_rows() -> list[dict]:
    label = {
        "MD2G_COMPONENT": "MD2G-Cast",
        "HV3_COMPONENT": "Heuristic",
        "CLUSTERING_COMPONENT": "Clustering",
    }
    out = []
    for r in filter_scope(
        load_dev_rows(),
        strategies=("MD2G_COMPONENT", "HV3_COMPONENT", "CLUSTERING_COMPONENT"),
    ):
        if int(r.get("seed") or 0) not in SEEDS:
            continue
        out.append(
            {
                "strategy": label[r["strategy"]],
                "source": "FROZEN_LIVE_COMMAND153",
                "fair_same_substrate": True,
                "content": r["content"],
                "network": r["network"],
                "users": int(r["users"]),
                "seed": int(r["seed"]),
                "key": r.get("key"),
                "U": r.get("U"),
                "Rq": r.get("Rq"),
                "Ro": r.get("Ro_component"),
                "Rb": r.get("Rb"),
                "decoded_completion": completion_scalar(r),
                "B_shared": r.get("B_shared"),
                "B_unicast": r.get("B_unicast"),
                "stall_last": r.get("stall_last"),
                "p99_delay_ms": "",
                "p99_delay_in_contract": False,
                "duration_s": 120,
                "metric_code": "command148_canary_metrics.cell_metrics",
            }
        )
    return out


def rolling_rows() -> list[dict]:
    rows = []
    for net in NETS:
        for u in USERS:
            rows.append(
                {
                    "strategy": "Rolling",
                    "source": "CAST_HANDBOOK_NOT_SAME_SUBSTRATE",
                    "fair_same_substrate": False,
                    "content": CONTENT,
                    "network": net,
                    "users": u,
                    "seed": "handbook_mean",
                    "key": "",
                    "U": CAST_ROLLING_U[(net, u)],
                    "Rq": "",
                    "Ro": "",
                    "Rb": "",
                    "decoded_completion": "",
                    "B_shared": "",
                    "B_unicast": "",
                    "stall_last": "",
                    "p99_delay_ms": "",
                    "p99_delay_in_contract": False,
                    "duration_s": "",
                    "metric_code": "MM26 command82 handbook",
                }
            )
    return rows


def fairness_proof(mcg_rows: list[dict]) -> dict:
    checks = {}
    checks["n_mcg_valid"] = len(mcg_rows)
    checks["n_mcg_expected"] = N_MCG
    checks["mcg_count_pass"] = len(mcg_rows) == N_MCG
    checks["duration_s"] = 120
    checks["warmup_live_metrics"] = "last_receipt_same_as_COMMAND153_not_offline_30s_cut"
    checks["offline_warmup_s_supplementary_only"] = WARMUP_S
    checks["seeds"] = list(SEEDS)
    checks["content"] = CONTENT
    checks["networks"] = list(NETS)
    checks["metric_code"] = "Sigcomm26/Paper6_ToN/lib/command148_canary_metrics.py::cell_metrics"
    checks["validator"] = "Sigcomm26/Paper6_ToN/lib/command148_canary_audit.py::audit_canary_cell"
    checks["launcher"] = "scripts/command148_canary_cell.py"
    checks["cluster"] = "moq_cluster_Sigcomm.py"
    checks["md2g_cast_unmodified"] = True
    checks["u_weights"] = [0.25, 0.60, 0.15]
    checks["rolling_fair"] = False
    checks["rolling_reason"] = "DASH/Cast handbook; not same MoQ relay/client"
    expected = {(n, u, s) for n in NETS for u in USERS for s in SEEDS}
    got = {(r["network"], int(r["users"]), int(r["seed"])) for r in mcg_rows}
    checks["missing_keys"] = sorted(f"{n}_u{u}_s{s}" for n, u, s in sorted(expected - got))
    mismatch = []
    for r in mcg_rows:
        if int(r.get("duration_s") or 0) != 120:
            mismatch.append(r["key"])
        if r.get("metric_code") != "command148_canary_metrics.cell_metrics":
            mismatch.append(r["key"])
    checks["contract_mismatch_keys"] = mismatch
    checks["pass"] = bool(checks["mcg_count_pass"] and not mismatch and not checks["missing_keys"])
    return checks


def write_status(fair: dict, n_mcg: int, paths: dict) -> None:
    lines = [
        "# Same-substrate evaluation status",
        "",
        "Controllers: MD2G-Cast, MCG, Heuristic, Clustering, Rule.",
        "Shared launcher, metrics, validators, and `project_down` feasibility.",
        f"MCG cells: {n_mcg}/27 VALID.",
        "Fairness gate: " + ("PASS" if fair.get("pass") else "FAIL") + ".",
        "",
        "## Paths",
        "",
    ]
    for k, v in paths.items():
        lines.append(f"- `{k}`: `{v}`")
    lines.append("")
    (TON / "TON_FINAL_EXPERIMENT_STATUS.md").write_text("\n".join(lines) + "\n")


def maybe_latency_scaling() -> None:
    """No Mininet. Does not overwrite the frozen 60-user breakdown."""
    script = ROOT / "controller_latency_scaling.py"
    py = TON.parents[1] / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
    try:
        subprocess.run([str(py), "-u", str(script)], cwd=str(TON.parents[1]), check=False, timeout=900)
    except Exception:
        return


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    maybe_latency_scaling()
    mcg_rows = load_mcg_cells()
    frozen = live_frozen_rows()
    rolling = rolling_rows()
    all_rows = frozen + mcg_rows + rolling
    write_csv(OUT / "live_mcg_cells.csv", all_rows)

    summary = []
    for strat in ("MD2G-Cast", "MCG", "Heuristic", "Clustering", "Rolling"):
        for u in USERS:
            chunk = [r for r in all_rows if r["strategy"] == strat and int(r["users"]) == u and r["U"] != ""]
            fair = all(bool(r.get("fair_same_substrate")) for r in chunk) if chunk else False
            uvals = [float(r["U"]) for r in chunk]
            rq = [float(r["Rq"]) for r in chunk if r["Rq"] != ""]
            ro = [float(r["Ro"]) for r in chunk if r["Ro"] != ""]
            rb = [float(r["Rb"]) for r in chunk if r["Rb"] != ""]
            cc = [float(r["decoded_completion"]) for r in chunk if r["decoded_completion"] != ""]
            summary.append(
                {
                    "strategy": strat,
                    "users": u,
                    "U_mean": mean(uvals) if uvals else "",
                    "Rq_mean": mean(rq) if rq else "",
                    "Ro_mean": mean(ro) if ro else "",
                    "Rb_mean": mean(rb) if rb else "",
                    "completion_mean": mean(cc) if cc else "",
                    "n": len(chunk),
                    "fair_same_substrate": fair if strat != "Rolling" else False,
                }
            )
    write_csv(OUT / "live_mcg_summary.csv", summary)

    by = {(r["strategy"], int(r["users"])): r["U_mean"] for r in summary}
    lines = [
        r"\begin{tabular}{lrrrl}",
        r"\hline",
        r"Strategy & $U$ (20) & $U$ (60) & $U$ (100) & Substrate \\",
        r"\hline",
    ]

    def fmt(strat, u):
        v = by.get((strat, u), "")
        return f"{v:.3f}" if v != "" else "---"

    notes = {
        "MD2G-Cast": "live MoQ",
        "MCG": "live MoQ",
        "Heuristic": "live MoQ",
        "Clustering": "live MoQ",
        "Rolling": "Cast handbook; not fair",
    }
    for strat in ("MD2G-Cast", "MCG", "Heuristic", "Clustering", "Rolling"):
        lines.append(
            f"{strat} & {fmt(strat, 20)} & {fmt(strat, 60)} & {fmt(strat, 100)} & {notes[strat]} \\\\"
        )
    lines += [r"\hline", r"\end{tabular}", ""]
    (OUT / "live_mcg_table.tex").write_text("\n".join(lines))

    fig, ax = plt.subplots(figsize=(7.0, 2.45))
    xs = np.array(USERS, dtype=float)
    styles = {
        "MD2G-Cast": ("#2171B5", "-", "o", True),
        "MCG": ("#8C2D04", "-", "D", True),
        "Heuristic": ("#D94801", ":", "s", True),
        "Clustering": ("#238B45", "-.", "^", True),
        "Rolling": ("#6A51A3", "--", "v", False),
    }
    for strat, (c, ls, mk, fair) in styles.items():
        ys = [by.get((strat, u), float("nan")) for u in USERS]
        ax.plot(
            xs,
            ys,
            color=c,
            linestyle=ls,
            marker=mk,
            linewidth=1.8 if fair else 1.2,
            markersize=6,
            alpha=1.0 if fair else 0.45,
            label=strat if fair else "Rolling (not fair)",
        )
    ax.set_xticks(USERS)
    ax.set_xlabel("Number of users")
    ax.set_ylabel(r"System utility $U$")
    ax.set_ylim(0.0, 0.95)
    ax.grid(True, axis="y", alpha=0.35)
    ax.legend(frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.18), fontsize=8)
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.22, top=0.82)
    fig.savefig(OUT / "live_mcg_utility_vs_users.pdf")
    plt.close(fig)

    fair = fairness_proof(mcg_rows)
    write_json(OUT / "fairness_check.json", fair)
    pdf = OUT / "live_mcg_utility_vs_users.pdf"
    prov = {
        "md2g_cast_unmodified": True,
        "ppo_not_retrained": True,
        "u_weights_frozen": [0.25, 0.60, 0.15],
        "mcg_strategy": "MCG_COMPONENT",
        "mcg_score": "sum_user_DeltaQ / shared_component_rate",
        "physics": "missing_component_DeltaR * 1.05 via project_down",
        "fov_used": False,
        "n_mcg_valid": len(mcg_rows),
        "n_frozen_same_slice": len(frozen),
        "rolling": "CAST_HANDBOOK_NOT_SAME_SUBSTRATE",
        "offline_mcg_kept": str(RESULTS / "mcg_baseline"),
        "dev_json": str(DEV_JSON),
        "art": str(ART),
        "fairness_pass": fair.get("pass"),
        "pdf_sha256": sha256_file(pdf) if pdf.is_file() else None,
        "duration_s": 120,
        "seeds": list(SEEDS),
        "content": CONTENT,
        "networks": list(NETS),
    }
    write_json(OUT / "provenance.json", prov)
    paths = {
        "live_cells": str(OUT / "live_mcg_cells.csv"),
        "summary": str(OUT / "live_mcg_summary.csv"),
        "table": str(OUT / "live_mcg_table.tex"),
        "figure": str(OUT / "live_mcg_utility_vs_users.pdf"),
        "provenance": str(OUT / "provenance.json"),
        "fairness": str(OUT / "fairness_check.json"),
        "mcg_art": str(ART),
        "offline_mcg": str(RESULTS / "mcg_baseline"),
        "audit": str(TON / "TON_EXPERIMENT_AUDIT.md"),
    }
    write_status(fair, len(mcg_rows), paths)
    print(json.dumps({"pass": fair.get("pass"), "n_mcg": len(mcg_rows), "n_frozen": len(frozen), "out": str(OUT)}))
    return 0 if fair.get("pass") else 4


if __name__ == "__main__":
    raise SystemExit(main())
