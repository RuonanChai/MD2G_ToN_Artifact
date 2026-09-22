#!/usr/bin/env python3
"""PHASE 5 optional: controller latency at 20/60/100 users. No Mininet.

Does not overwrite the frozen 60-user breakdown JSON/PDF.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TON = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON))
from _common import RESULTS, write_csv, write_json  # noqa: E402
from controller_latency_breakdown import N_ITERS, _load_rec, summarize  # noqa: E402

OUT = RESULTS / "controller_latency"
USERS = (20, 60, 100)


def resize(xs: list, n: int) -> list:
    if not xs:
        return [0.0] * n
    if len(xs) >= n:
        return list(xs[:n])
    out = list(xs)
    while len(out) < n:
        out.append(xs[len(out) % len(xs)])
    return out


def main() -> int:
    import torch
    from command148_component_policy import TRACKS, _load_student
    from command148_mcg import mcg_select
    from command149_marginal_cost import project_down
    from component_actuation_plan import build_plan

    rec = _load_rec()
    content = rec["content"]
    access0 = [float(x) for x in rec["access_mbps"]]
    device0 = [float(x) for x in rec["device"]]
    active = list(rec.get("active_components") or [])
    t = float(rec.get("t") or 40.0)
    model = _load_student()
    model.eval()

    rows = []
    for n_users in USERS:
        access = resize(access0, n_users)
        device = resize(device0, n_users)

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

        md2g_total = []
        mcg_total = []
        for _ in range(N_ITERS):
            t0 = time.perf_counter()
            user, cfeat, gfeat = tensors()
            with torch.no_grad():
                out = model(user, cfeat, gfeat)
            pred = out["rep_logits"].argmax(-1)[0] + 1
            targets = {}
            for i in range(1, n_users + 1):
                rec_i = project_down(
                    f"Rep{int(pred[i - 1].item())}", access[i - 1], device[i - 1], content, active
                )
                targets[f"u{i}"] = rec_i["applied"]
            plan = build_plan(
                decision_seq=1,
                group="g0",
                user_target_states=targets,
                currently_active=active,
                reason="latency_scale",
            ).finalize()
            _ = plan.plan_hash
            md2g_total.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            sel = mcg_select(access, device, content, already_active=active)
            mtargets = {f"u{i}": sel["states"][i - 1] for i in range(1, n_users + 1)}
            mplan = build_plan(
                decision_seq=1,
                group="g0",
                user_target_states=mtargets,
                currently_active=active,
                reason="latency_scale_mcg",
            ).finalize()
            _ = mplan.plan_hash
            mcg_total.append((time.perf_counter() - t0) * 1000)

        s_md = summarize(md2g_total)
        s_mcg = summarize(mcg_total)
        rows.append({"scheduler": "MD2G-Cast student", "users": n_users, **s_md})
        rows.append({"scheduler": "MCG greedy", "users": n_users, **s_mcg})

    write_csv(OUT / "latency_scaling_20_60_100.csv", rows)
    write_json(
        OUT / "latency_scaling_20_60_100.json",
        {
            "n_iters": N_ITERS,
            "note": "Does not replace frozen 60-user breakdown. No Mininet.",
            "sidecar": rec.get("_sidecar"),
            "rows": rows,
        },
    )
    print(f"Wrote {OUT / 'latency_scaling_20_60_100.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
