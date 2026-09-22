#!/usr/bin/env python3
"""MCG same-substrate controller replay on frozen decision traces.

Does not modify MD2G-Cast / PPO. Does not launch Mininet.
Uses the same access/device traces the frozen student saw, plus frozen Q and
missing-component ΔR. MCG is labeled OFFLINE_TRACE_REPLAY.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _common import (  # noqa: E402
    CAST_ROLLING_U,
    CONTENT,
    MAINDEV,
    NETS,
    RESULTS,
    SEEDS,
    STRAT_LABEL,
    USERS,
    WARMUP_S,
    clip01,
    filter_scope,
    frozen_q,
    frozen_rates,
    load_dev_rows,
    mean,
    pct,
    prereq,
    closures,
    utility,
    write_csv,
    write_json,
)

OUT = RESULTS / "mcg_baseline"
MARGIN = 1.05
COMPONENTS = ("b0", "db1", "db2", "e1", "e2")
CELL_RE = re.compile(
    r"c148dev_(?P<content>[^_]+)_(?P<net>.+)_u(?P<users>\d+)_MD2G_COMPONENT_s(?P<seed>\d+)$"
)


def _state_of(decoded_set: set[str], clos: dict[str, list[str]]) -> str:
    best, n = "Rep1", -1
    for st, cset in clos.items():
        if set(cset) <= decoded_set and len(cset) >= n:
            best, n = st, len(cset)
    return best


def mcg_tick(access: list[float], device: list[float], content: str) -> dict:
    """Greedy: score(component)=Σ ΔQ / extra shared rate. Shared publish once."""
    qmap = frozen_q(content)
    rates = frozen_rates(content)
    clos = closures()
    pre = prereq()
    n = len(access)
    decoded = [set() for _ in range(n)]
    active: list[str] = []
    delay_ms = [0.0] * n

    def user_q(i: int) -> float:
        return float(qmap[_state_of(decoded[i], clos)])

    def can_use(i: int, comp: str) -> bool:
        if float(device[i]) + 1e-9 < (0.15 if comp != "b0" else 0.0):
            return False
        trial = set(decoded[i]) | {comp}
        st = _state_of(trial, clos)
        missing = [c for c in clos[st] if c not in decoded[i]]
        dlt = sum(rates[c] for c in missing)
        return float(access[i]) + 1e-9 >= dlt * MARGIN

    while True:
        best_c, best_s = None, 0.0
        for comp in COMPONENTS:
            if comp in active:
                continue
            if any(p not in active for p in pre[comp]):
                continue
            dq = 0.0
            n_gain = 0
            for i in range(n):
                if not can_use(i, comp):
                    continue
                q0 = user_q(i)
                trial = set(decoded[i]) | {comp}
                q1 = float(qmap[_state_of(trial, clos)])
                gain = q1 - q0
                if gain > 1e-12:
                    dq += gain
                    n_gain += 1
            if n_gain <= 0:
                continue
            score = dq / max(rates[comp], 1e-9)
            if score > best_s:
                best_s, best_c = score, comp
        if best_c is None:
            break
        active.append(best_c)
        for i in range(n):
            if not can_use(i, best_c):
                continue
            missing = [best_c] if best_c not in decoded[i] else []
            if missing:
                delay_ms[i] += 1000.0 * rates[best_c] / max(float(access[i]), 1e-6)
            decoded[i].add(best_c)

    states = [_state_of(decoded[i], clos) for i in range(n)]
    rq = mean(float(qmap[s]) for s in states)
    b_uni = sum(sum(rates[c] for c in clos[s]) for s in states)
    b_sh = sum(rates[c] for c in active)
    ro = clip01(1.0 - (b_sh / b_uni if b_uni > 0 else 1.0))
    requested = sum(1 for s in states for _ in clos[s])
    completed = sum(len(d) for d in decoded)
    completion = completed / requested if requested else 0.0
    return {
        "states": states,
        "active": list(active),
        "Rq": rq,
        "Ro": ro,
        "completion": completion,
        "reuse_ratio": ro,
        "B_shared_mbps": b_sh,
        "B_unicast_mbps": b_uni,
        "delay_ms": delay_ms,
        "p99_delay_ms": pct(delay_ms, 99),
        "n_users": n,
    }


def iter_md2g_cells():
    for d in sorted(MAINDEV.iterdir()):
        if not d.is_dir() or "INVALID" in d.name:
            continue
        m = CELL_RE.match(d.name)
        if not m:
            continue
        if m.group("content") != CONTENT:
            continue
        net = m.group("net")
        if net not in NETS:
            continue
        users = int(m.group("users"))
        seed = int(m.group("seed"))
        if users not in USERS or seed not in SEEDS:
            continue
        inf = d / "COMMAND148_STUDENT_INFERENCE.jsonl"
        if inf.is_file():
            yield d, net, users, seed, inf


def replay_cell(inf: Path, content: str) -> dict | None:
    ticks = []
    for ln in inf.read_text(errors="ignore").splitlines():
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        acc = [float(x) for x in (rec.get("access_mbps") or [])]
        if not acc or float(rec.get("t") or 0) < WARMUP_S:
            continue
        if mean(acc) < 1.0:
            continue
        dev = [float(x) for x in (rec.get("device") or [0.5] * len(acc))]
        if len(dev) < len(acc):
            dev = (dev + [0.5] * len(acc))[: len(acc)]
        ticks.append(mcg_tick(acc, dev, content))
    if not ticks:
        return None
    delays = [d for t in ticks for d in t["delay_ms"]]
    return {
        "Rq": mean(t["Rq"] for t in ticks),
        "Ro": mean(t["Ro"] for t in ticks),
        "completion": mean(t["completion"] for t in ticks),
        "B_shared_mbps": mean(t["B_shared_mbps"] for t in ticks),
        "B_unicast_mbps": mean(t["B_unicast_mbps"] for t in ticks),
        "p99_delay_ms_offline": pct(delays, 99),
        "n_ticks": len(ticks),
    }


def live_index(rows):
    idx = {}
    for r in filter_scope(rows, strategies=("MD2G_COMPONENT", "HV3_COMPONENT", "CLUSTERING_COMPONENT", "MOQ_UNICAST_COMPONENT")):
        idx[(r["strategy"], r["network"], int(r["users"]), int(r["seed"]))] = r
    return idx


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    live = live_index(load_dev_rows())
    mcg_rows = []
    for _d, net, users, seed, inf in iter_md2g_cells():
        m = replay_cell(inf, CONTENT)
        if m is None:
            continue
        rb_live = float(live.get(("MD2G_COMPONENT", net, users, seed), {}).get("Rb") or 0.0)
        u_rb0 = utility(m["Ro"], m["Rq"], 0.0)
        u_matched_rb = utility(m["Ro"], m["Rq"], rb_live)
        mcg_rows.append(
            {
                "strategy": "MCG",
                "source": "OFFLINE_TRACE_REPLAY",
                "content": CONTENT,
                "network": net,
                "users": users,
                "seed": seed,
                "U_Rb0": u_rb0,
                "U": u_matched_rb,
                "Rq": m["Rq"],
                "Ro": m["Ro"],
                "Rb_matched_live_md2g": rb_live,
                "decoded_completion": m["completion"],
                "bandwidth_mbps_shared": m["B_shared_mbps"],
                "p99_delay_ms": m["p99_delay_ms_offline"],
                "n_ticks": m["n_ticks"],
            }
        )
    live_rows = []
    for (strat, net, users, seed), r in live.items():
        live_rows.append(
            {
                "strategy": STRAT_LABEL[strat],
                "source": "FROZEN_LIVE_COMMAND153",
                "content": CONTENT,
                "network": net,
                "users": users,
                "seed": seed,
                "U_Rb0": utility(r["Ro_component"], r["Rq"], 0.0),
                "U": r["U"],
                "Rq": r["Rq"],
                "Ro": r["Ro_component"],
                "Rb_matched_live_md2g": r["Rb"],
                "decoded_completion": r["Rq"],
                "bandwidth_mbps_shared": float(r.get("B_shared") or 0) * 8 / 120e6,
                "p99_delay_ms": "",
                "n_ticks": "",
            }
        )
    rolling_rows = []
    for net in NETS:
        for u in USERS:
            rolling_rows.append(
                {
                    "strategy": "Rolling",
                    "source": "CAST_COMMAND82_HANDBOOK",
                    "content": CONTENT,
                    "network": net,
                    "users": u,
                    "seed": "handbook_mean",
                    "U_Rb0": "",
                    "U": CAST_ROLLING_U[(net, u)],
                    "Rq": "",
                    "Ro": "",
                    "Rb_matched_live_md2g": "",
                    "decoded_completion": "",
                    "bandwidth_mbps_shared": "",
                    "p99_delay_ms": "",
                    "n_ticks": "",
                }
            )
    all_rows = live_rows + mcg_rows + rolling_rows
    write_csv(OUT / "mcg_vs_baselines_cells.csv", all_rows)
    # Seed-mean table for LaTeX / figure
    summary = []
    for strat in ("MD2G-Cast", "MCG", "Heuristic", "Clustering", "Rolling"):
        for u in USERS:
            vals = [float(r["U"]) for r in all_rows if r["strategy"] == strat and int(r["users"]) == u and r["U"] != ""]
            summary.append(
                {
                    "strategy": strat,
                    "users": u,
                    "U_mean": mean(vals) if vals else "",
                    "n": len(vals),
                }
            )
    write_csv(OUT / "mcg_utility_by_users.csv", summary)
    lines = [
        r"\begin{tabular}{lrrr}",
        r"\hline",
        r"Strategy & $U$ (20) & $U$ (60) & $U$ (100) \\",
        r"\hline",
    ]
    by = {(r["strategy"], int(r["users"])): r["U_mean"] for r in summary}
    for strat in ("MD2G-Cast", "MCG", "Heuristic", "Clustering", "Rolling"):
        def fmt(u):
            v = by.get((strat, u), "")
            return f"{v:.3f}" if v != "" else "---"
        note = r"\textit{offline}" if strat == "MCG" else (r"\textit{Cast handbook}" if strat == "Rolling" else "live")
        lines.append(f"{strat} ({note}) & {fmt(20)} & {fmt(60)} & {fmt(100)} \\\\")
    lines += [r"\hline", r"\end{tabular}", ""]
    (OUT / "mcg_baseline_table.tex").write_text("\n".join(lines))

    fig, ax = plt.subplots(figsize=(7.0, 2.35))
    xs = np.array(USERS, dtype=float)
    styles = {
        "MD2G-Cast": ("#2171B5", "-", "o"),
        "MCG": ("#8C2D04", "--", "D"),
        "Heuristic": ("#D94801", ":", "s"),
        "Clustering": ("#238B45", "-.", "^"),
        "Rolling": ("#6A51A3", "--", "v"),
    }
    for strat, (c, ls, mk) in styles.items():
        ys = [by.get((strat, u), float("nan")) for u in USERS]
        ax.plot(xs, ys, color=c, linestyle=ls, marker=mk, linewidth=1.8, markersize=6, label=strat)
    ax.set_xticks(USERS)
    ax.set_xlabel("Number of users")
    ax.set_ylabel(r"System utility $U$")
    ax.set_ylim(0.0, 0.95)
    ax.grid(True, axis="y", alpha=0.35)
    ax.legend(frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.18), fontsize=8)
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.22, top=0.82)
    fig.savefig(OUT / "utility_vs_users_mcg.pdf")
    plt.close(fig)
    write_json(
        OUT / "MCG_PROVENANCE.json",
        {
            "method": "OFFLINE_TRACE_REPLAY",
            "not_live_mininet": True,
            "md2g_cast_unmodified": True,
            "ppo_not_retrained": True,
            "score": "sum_user_DeltaQ / shared_component_rate",
            "physics": "missing_component_DeltaR * 1.05",
            "U_for_MCG": "clip(0.25 Ro_mcg + 0.60 Rq_mcg - 0.15 Rb_live_matched_MD2G)",
            "n_mcg_cells": len(mcg_rows),
            "rolling_source": "MM26 Camera Ready PAPER_FULL_MATRIX_METRICS_HANDBOOK.md command82",
        },
    )
    print(f"Wrote {OUT} n_mcg={len(mcg_rows)} n_live={len(live_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
