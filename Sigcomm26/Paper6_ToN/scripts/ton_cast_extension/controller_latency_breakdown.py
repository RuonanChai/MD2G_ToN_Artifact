#!/usr/bin/env python3
"""TASK 3: Controller pipeline latency breakdown. No full-scale Mininet.

Stages match the frozen student path in command148_component_policy.md2g_student_targets:
state collection, feature prep, student inference, grouping logits, action projection, plan write.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
TON = ROOT.parents[1]
REPO = TON.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON))
from _common import RESULTS, write_csv, write_json  # noqa: E402

OUT = RESULTS / "controller_latency"
N_ITERS = 1000
def _find_sidecar() -> Path:
    maindev = TON / "artifacts" / "command148_maindev"
    preferred = [
        maindev / "c148dev_redandblack_4g_u60_MD2G_COMPONENT_s153" / "COMMAND148_STUDENT_INFERENCE.jsonl",
        maindev / "c148dev_redandblack_wifi_u60_MD2G_COMPONENT_s151" / "COMMAND148_STUDENT_INFERENCE.jsonl",
    ]
    for p in preferred:
        if p.is_file():
            return p
    for p in sorted(maindev.glob("c148dev_redandblack_*_u60_MD2G_COMPONENT_s*/COMMAND148_STUDENT_INFERENCE.jsonl")):
        if "INVALID" not in str(p):
            return p
    raise SystemExit("NO_SIDECAR")


def _load_rec() -> dict:
    sidecar = _find_sidecar()
    for ln in sidecar.read_text(errors="ignore").splitlines():
        rec = json.loads(ln)
        acc = rec.get("access_mbps") or []
        if acc and float(sum(acc)) / len(acc) > 1.0:
            rec["_sidecar"] = str(sidecar)
            return rec
    raise SystemExit(f"NO_SIDECAR_TICK {sidecar}")


def pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100.0
    lo = int(np.floor(k))
    hi = int(np.ceil(k))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - k) + xs[hi] * (k - lo)


def summarize(xs):
    return {
        "mean_ms": statistics.mean(xs),
        "median_ms": statistics.median(xs),
        "p95_ms": pct(xs, 95),
        "p99_ms": pct(xs, 99),
        "n": len(xs),
    }


def main() -> int:
    import torch
    from command149_marginal_cost import project_down
    from command148_component_policy import TRACKS, _load_student
    from component_actuation_plan import build_plan

    rec = _load_rec()
    n_users = int(rec["n_users"])
    content = rec["content"]
    access = [float(x) for x in rec["access_mbps"]]
    device = [float(x) for x in rec["device"]]
    active = list(rec.get("active_components") or [])
    t = float(rec.get("t") or 40.0)
    model = _load_student()
    model.eval()

    def tensors():
        user = torch.zeros(1, n_users, 16)
        for i in range(n_users):
            user[0, i, 0] = access[i] / 120.0
            user[0, i, 1] = device[i]
            user[0, i, 2] = min(1.0, t / 120.0)
        cfeat = torch.zeros(1, 12)
        cfeat[0, 0] = 0.0 if content == "redandblack" else 1.0
        gfeat = torch.zeros(1, 10)
        gfeat[0, 0] = n_users / 100.0
        for j, tr in enumerate(TRACKS):
            gfeat[0, 1 + j] = 1.0 if tr in set(active) else 0.0
        return user, cfeat, gfeat

    with torch.no_grad():
        model(*tensors())

    stages = {
        "state_collection": [],
        "feature_preprocessing": [],
        "student_policy_inference": [],
        "grouping_decision": [],
        "action_generation": [],
        "relay_update": [],
    }
    for _ in range(N_ITERS):
        t0 = time.perf_counter()
        acc = list(access)
        dev = list(device)
        stages["state_collection"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        user, cfeat, gfeat = tensors()
        stages["feature_preprocessing"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        with torch.no_grad():
            out = model(user, cfeat, gfeat)
        stages["student_policy_inference"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        _g = out["group_logits"].argmax(-1)
        pred = out["rep_logits"].argmax(-1)[0] + 1
        stages["grouping_decision"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        targets = {}
        for i in range(1, n_users + 1):
            rec_i = project_down(f"Rep{int(pred[i - 1].item())}", acc[i - 1], dev[i - 1], content, active)
            targets[f"u{i}"] = rec_i["applied"]
        stages["action_generation"].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        plan = build_plan(
            decision_seq=1,
            group="g0",
            user_target_states=targets,
            currently_active=active,
            reason="latency_bench",
        ).finalize()
        _ = plan.plan_hash
        stages["relay_update"].append((time.perf_counter() - t0) * 1000)

    rows = []
    total = None
    for name, xs in stages.items():
        s = summarize(xs)
        s["stage"] = name
        rows.append(s)
    tot_xs = [sum(v[i] for v in stages.values()) for i in range(N_ITERS)]
    total = summarize(tot_xs)
    total["stage"] = "total_pipeline"
    rows.append(total)
    write_csv(OUT / "controller_latency_breakdown.csv", rows)
    write_json(OUT / "controller_latency_breakdown.json", {"n_iters": N_ITERS, "n_users": n_users, "sidecar": rec.get("_sidecar"), "stages": rows})

    tex = [
        r"\begin{tabular}{lrrrr}",
        r"\hline",
        r"Stage & Mean (ms) & Median & P95 & P99 \\",
        r"\hline",
    ]
    labels = {
        "state_collection": "State collection",
        "feature_preprocessing": "Feature preprocessing",
        "student_policy_inference": "Student policy inference",
        "grouping_decision": "Grouping decision",
        "action_generation": "Action generation",
        "relay_update": "Relay update",
        "total_pipeline": r"\textbf{Total}",
    }
    for s in rows:
        tex.append(
            f"{labels[s['stage']]} & {s['mean_ms']:.3f} & {s['median_ms']:.3f} & {s['p95_ms']:.3f} & {s['p99_ms']:.3f} \\\\"
        )
    tex += [r"\hline", r"\end{tabular}", ""]
    (OUT / "controller_latency_breakdown.tex").write_text("\n".join(tex))

    fig, ax = plt.subplots(figsize=(7.0, 2.45))
    names = [r["stage"] for r in rows if r["stage"] != "total_pipeline"]
    means = [next(r["mean_ms"] for r in rows if r["stage"] == n) for n in names]
    ax.barh(range(len(names)), means, color="
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(["State collection", "Feature prep", "Student inference", "Grouping", "Action gen", "Relay update"])
    ax.invert_yaxis()
    ax.set_xlabel("Mean latency (ms), 1000 iterations, 60 users")
    ax.grid(True, axis="x", alpha=0.3)
    fig.subplots_adjust(left=0.28, right=0.98, bottom=0.22, top=0.96)
    fig.savefig(OUT / "controller_latency_breakdown.pdf")
    plt.close(fig)
    print(f"Wrote {OUT} total_mean_ms={total['mean_ms']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
