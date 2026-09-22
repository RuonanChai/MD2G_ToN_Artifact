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

"""One-step command153 continuation after main DEV. Never a second Mininet."""
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))
from command137_proc import dash_live, moq_live  # noqa: E402
from command147_io import dump_dual, handle_unsupervised_live_wait, token, ts  # noqa: E402
from command153_raw_dump_retention import launch_free_space_ok  # noqa: E402

PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
STRATS = [
    "MD2G_COMPONENT",
    "HV3_COMPONENT",
    "CLUSTERING_COMPONENT",
    "RULE_COMPONENT",
    "MOQ_UNICAST_COMPONENT",
]
DEV_ART = TON / "artifacts" / "command148_maindev"
SCALE_ART = TON / "artifacts" / "command153_scaling"
LOOT_ART = TON / "artifacts" / "command153_loot_holdout"


def exists(name: str) -> bool:
    return (REPO / "state" / f"{name}.json").is_file()


def _fail_closed(reason: str, extra: dict | None = None) -> int:
    body = {"reason": reason, "kill_live_cell": False}
    if extra:
        body.update(extra)
    token("COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED", body)
    print(json.dumps({"pass": False, **body}))
    return 3


def _queue_completed(qname: str) -> int:
    qp = REPO / "state" / qname
    if not qp.is_file():
        return 0
    try:
        return len(json.loads(qp.read_text()).get("completed") or [])
    except Exception:
        return 0


def _live() -> bool:
    return bool(moq_live() or dash_live())


def _launch(spec: dict, art: Path, qname: str, n: int) -> int:
    disk = launch_free_space_ok(REPO)
    if disk.get("pause_next_launch"):
        phase1 = TON / "scripts" / "command155_phase1_disk_reclaim.py"
        if phase1.is_file():
            subprocess.run([str(PY), "-u", str(phase1)], cwd=str(REPO), check=False)
            disk = launch_free_space_ok(REPO)
        dump_dual(
            "COMMAND153_DISK_PAUSE_NEXT_LAUNCH.json",
            {
                "ts": ts(),
                "token": "COMMAND153_DISK_PAUSE_NEXT_LAUNCH",
                "next_key": spec.get("key"),
                "queue": qname,
                "disk": disk,
                "kill_live_cell": False,
            },
        )
        print(json.dumps({"pass": False, "reason": "disk_pause_next_launch", "disk": disk}))
        return 5
    env = os.environ.copy()
    env["COMMAND148_SPEC_JSON"] = json.dumps(spec)
    env["COMMAND148_ART_ROOT"] = str(art)
    env["COMMAND153_QUEUE_NAME"] = qname
    env["COMMAND152_LAUNCH"] = env.get("COMMAND152_LAUNCH") or "1"
    env["COMMAND148_STAGE"] = spec.get("stage") or "injected"
    env["COMMAND148_QUEUE_N"] = str(n)
    qp = REPO / "state" / qname
    if qp.is_file():
        q = json.loads(qp.read_text())
    else:
        q = {"completed": [], "failed": None, "attempts": {}, "invalid": [], "n": n}
        dump_dual(qname, q)
    fail = q.get("failed") or {}
    if fail:
        subprocess.run([str(PY), "-u", str(TON / "scripts" / "command153_classify_and_repair.py")], cwd=str(REPO), check=False)
        sys.path.insert(0, str(TON / "scripts"))
        from command148_canary_cell import consume_exact_key, exact_key_authorized  # noqa: E402

        fk = str(fail.get("key") or spec["key"])
        n_try = int((q.get("attempts") or {}).get(fk) or 0)
        auth = exact_key_authorized(fk)
        if n_try >= 3 and auth is None:
            token(
                "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
                {"reason": "injected_fail_closed", "failed": fk, "queue": qname, "attempts": n_try, "kill_live_cell": False},
            )
            print(json.dumps({"pass": False, "reason": "injected_fail_closed", "failed": fk, "attempts": n_try, "ledger": True}))
            return 3
        if auth is not None:
            consume_exact_key(auth)
        q["failed"] = None
        dump_dual(qname, q)
        if fk != spec["key"]:
            spec = dict(spec)
            spec["key"] = fk
            env["COMMAND148_SPEC_JSON"] = json.dumps(spec)
    return subprocess.run([str(PY), "-u", str(TON / "scripts" / "command148_canary_cell.py")], cwd=str(REPO), env=env).returncode


def scaling_matrix() -> list[dict]:
    rows = []
    for net in ("default_mix", "wifi_dominant"):
        for users in (10, 20, 40, 60, 100):
            for seed in (151, 152, 153):
                for strat in STRATS:
                    rows.append(
                        {
                            "key": f"c153scale_redandblack_{net}_u{users}_{strat}_s{seed}",
                            "content": "redandblack",
                            "network": net,
                            "users": users,
                            "seed": seed,
                            "strategy": strat,
                            "stage": "scaling",
                        }
                    )
    return rows


def loot_matrix() -> list[dict]:
    rows = []
    nets = ["4g", "5g", "wifi", "fiber_optic", "default_mix", "wifi_dominant", "5g_dominant"]
    for net in nets:
        for users in (20, 60, 100):
            for seed in (91, 92, 93):
                for strat in STRATS:
                    rows.append(
                        {
                            "key": f"c153loot_{net}_u{users}_{strat}_s{seed}",
                            "content": "loot",
                            "network": net,
                            "users": users,
                            "seed": seed,
                            "strategy": strat,
                            "stage": "loot_holdout",
                        }
                    )
    return rows


def _reuse_dev(spec: dict) -> Path | None:
    if spec["users"] not in (20, 60, 100) or spec["seed"] not in (151, 152, 153):
        return None
    k = f"c148dev_{spec['content']}_{spec['network']}_u{spec['users']}_{spec['strategy']}_s{spec['seed']}"
    p = DEV_ART / k
    if (p / "CELL_DONE.json").is_file() and (p / "CELL_METRICS.json").is_file():
        return p
    return None


def step_scaling() -> int:
    qname = "COMMAND153_SCALING_QUEUE.json"
    qp = REPO / "state" / qname
    q = json.loads(qp.read_text()) if qp.is_file() else {"completed": [], "reused": [], "failed": None, "n": 150}
    SCALE_ART.mkdir(parents=True, exist_ok=True)
    done = set(q.get("completed") or [])
    reused = list(q.get("reused") or [])
    for spec in scaling_matrix():
        if spec["key"] in done:
            continue
        twin = _reuse_dev(spec)
        if twin is not None:
            dest = SCALE_ART / spec["key"]
            dest.mkdir(parents=True, exist_ok=True)
            for name in ("CELL_DONE.json", "CELL_METRICS.json", "CELL_AUDIT.json", "CELL_VALIDITY.json"):
                src = twin / name
                if src.is_file():
                    (dest / name).write_text(src.read_text())
            rec = json.loads((dest / "CELL_DONE.json").read_text())
            rec["reused_from"] = twin.name
            rec["key"] = spec["key"]
            (dest / "CELL_DONE.json").write_text(json.dumps(rec, indent=2) + "\n")
            done.add(spec["key"])
            reused.append(spec["key"])
            q["completed"] = list(done)
            q["reused"] = reused
            q["status"] = f"{len(done)}/{len(scaling_matrix())}"
            q["ts"] = ts()
            dump_dual(qname, q)
            continue
        return _launch(spec, SCALE_ART, qname, len(scaling_matrix()))
    expected = [s["key"] for s in scaling_matrix()]
    if any(k not in done for k in expected):
        return _fail_closed("scaling_incomplete", {"n": sum(1 for k in expected if k in done), "expected": len(expected)})
    dump_dual("COMMAND153_SCALING_COMPLETE.json", {"ts": ts(), "token": "COMMAND153_SCALING_COMPLETE", "n": len(expected)})
    print(json.dumps({"pass": True, "phase": "scaling_complete", "n": len(done)}))
    return 0


ABLATION_VARIANTS = {
    "A0_full": {"status": "APPLICABLE_REUSE_DEV_MD2G", "live": True},
    "A1_no_fov_group_overlap": {
        "status": "NOT_APPLICABLE",
        "reason": "final nested controller has no live FoV overlap knob; do not fabricate",
    },
    "A2_no_device": {"status": "NOT_APPLICABLE", "reason": "device scores are diagnostic defaults; no isolated live toggle certified"},
    "A3_no_component_headroom": {"status": "NOT_APPLICABLE", "reason": "project_down is shared physics, not a separable live ablation flag"},
    "A4_no_completion_playability": {"status": "NOT_APPLICABLE", "reason": "no live completion-gate disable certified post-freeze"},
    "A5_fixed_grouping": {"status": "NOT_APPLICABLE", "reason": "planner already uses a single group g0"},
    "A6_rule_only": {"status": "APPLICABLE_REUSE_DEV_RULE", "live": True},
    "A7_naive_cumulative_cost": {
        "status": "NOT_APPLICABLE",
        "reason": "command149 missing-component cost is frozen; do not rerun wrong-contract cumulative prefix",
    },
}


def write_ablation_manifest() -> dict:
    """Freeze-once before any ablation result. Never rewrite variants after freeze."""
    existing_p = REPO / "state" / "COMMAND153_ABLATION_MANIFEST.json"
    if existing_p.is_file():
        try:
            prev = json.loads(existing_p.read_text())
        except Exception:
            prev = {}
        if prev.get("variants"):
            return prev
    body = {
        "ts": ts(),
        "token": "COMMAND153_ABLATION_MANIFEST",
        "frozen_before_first_ablation_result": True,
        "frozen_before_ablation_complete": True,
        "variants": ABLATION_VARIANTS,
        "loot_sealed": True,
        "do_not_fabricate": True,
        "n_applicable_live": 2,
        "n_not_applicable": 6,
        "no_288_live_matrix": True,
    }
    dump_dual("COMMAND153_ABLATION_MANIFEST.json", body)
    return body


def write_fov_not_applicable() -> dict:
    """Freeze-once before any FoV result. COMPLETE is a later pipeline token."""
    existing_p = REPO / "state" / "COMMAND153_FOV_NOT_APPLICABLE.json"
    if existing_p.is_file():
        try:
            prev = json.loads(existing_p.read_text())
        except Exception:
            prev = {}
        if prev.get("token") == "COMMAND153_FOV_NOT_APPLICABLE":
            return prev
    body = {
        "ts": ts(),
        "token": "COMMAND153_FOV_NOT_APPLICABLE",
        "frozen_before_first_fov_result": True,
        "reason": "no live overlap 20/40/60/80 knob in frozen nested controller; 96-cell FoV matrix would fabricate a mechanism",
        "do_not_fabricate": True,
        "loot_sealed": True,
    }
    dump_dual("COMMAND153_FOV_NOT_APPLICABLE.json", body)
    return body


def _dev_strategy_keys(strategy: str) -> list[str]:
    qp = REPO / "state" / "COMMAND148_MAINDEV_QUEUE.json"
    if not qp.is_file():
        return []
    try:
        done = [str(k) for k in (json.loads(qp.read_text()).get("completed") or [])]
    except Exception:
        return []
    needle = f"_{strategy}_s"
    return [k for k in done if needle in k]


def step_ablation_manifest() -> int:
    man = write_ablation_manifest()
    a0 = _dev_strategy_keys("MD2G_COMPONENT")
    a6 = _dev_strategy_keys("RULE_COMPONENT")
    if len(a0) < 189 or len(a6) < 189:
        return _fail_closed(
            "ablation_dev_reuse_incomplete",
            {"n_a0": len(a0), "n_a6": len(a6), "expected_each": 189},
        )
    dump_dual(
        "COMMAND153_ABLATION_COMPLETE.json",
        {
            "ts": ts(),
            "token": "COMMAND153_ABLATION_COMPLETE",
            "manifest_only_not_applicable_majority": True,
            "manifest_frozen_before_complete": True,
            "n_applicable": 2,
            "not_experimental_validation_for_na": True,
            "a0_reuse_dev_md2g_n": len(a0),
            "a6_reuse_dev_rule_n": len(a6),
            "a0_reuse_from": "COMMAND148_MAINDEV_QUEUE MD2G_COMPONENT",
            "a6_reuse_from": "COMMAND148_MAINDEV_QUEUE RULE_COMPONENT",
            "no_288_live_matrix": True,
        },
    )
    print(json.dumps({"pass": True, "phase": "ablation_manifest", "n_applicable": 2, "n_a0": len(a0), "n_a6": len(a6), "frozen": bool(man.get("variants"))}))
    return 0


def step_fov() -> int:
    write_fov_not_applicable()
    dump_dual("COMMAND153_FOV_COMPLETE.json", {"ts": ts(), "token": "COMMAND153_FOV_COMPLETE", "status": "NOT_APPLICABLE"})
    print(json.dumps({"pass": True, "phase": "fov_not_applicable"}))
    return 0


def _student_infer_ms(art: Path, limit_per_file: int = 20) -> list[float]:
    lat: list[float] = []
    if not art.is_dir():
        return lat
    for inf in art.glob("*/COMMAND148_STUDENT_INFERENCE.jsonl"):
        for ln in inf.read_text(errors="ignore").splitlines()[:limit_per_file]:
            try:
                rec = json.loads(ln)
            except Exception:
                continue
            for k in ("dt_ms", "infer_ms", "latency_ms"):
                if rec.get(k) is not None:
                    try:
                        lat.append(float(rec[k]))
                    except (TypeError, ValueError):
                        pass
                    break
    return lat


def step_overhead() -> int:
    rbv1 = _student_infer_ms(TON / "artifacts" / "command148_canary120_rbv1")
    dev = _student_infer_ms(DEV_ART)
    lat = rbv1 + dev
    body = {
        "ts": ts(),
        "token": "COMMAND153_OVERHEAD_STATS",
        "student_infer_ms_n": len(lat),
        "student_infer_ms_mean": statistics.mean(lat) if lat else None,
        "student_infer_ms_n_rbv1": len(rbv1),
        "student_infer_ms_n_maindev": len(dev),
        "source": "rbv1 + main DEV student sidecars (u20/u60/u100 where present); no extra Mininet perturbation cell",
        "pressure_instrumentation": "r0-eth1 1s sampler already in every scientific cell",
        "loot_sealed": True,
    }
    dump_dual("COMMAND153_OVERHEAD_COMPLETE.json", body)
    (TON / "final").mkdir(parents=True, exist_ok=True)
    (TON / "final" / "COMMAND153_OVERHEAD_STATS.json").write_text(json.dumps(body, indent=2) + "\n")
    print(json.dumps({"pass": True, "phase": "overhead", "n": len(lat)}))
    return 0


def _parse_maindev_key(key: str) -> dict | None:
    # c148dev_{content}_{net}_u{users}_{STRAT}_s{seed}
    try:
        for content in ("longdress", "redandblack", "soldier"):
            prefix = f"c148dev_{content}_"
            if not key.startswith(prefix):
                continue
            rest = key[len(prefix) :]
            for net in ("fiber_optic", "default_mix", "wifi_dominant", "5g_dominant", "4g", "5g", "wifi"):
                npre = f"{net}_u"
                if not rest.startswith(npre):
                    continue
                rest2 = rest[len(npre) :]
                u_s, _, rem = rest2.partition("_")
                users = int(u_s)
                if "_s" not in rem:
                    return None
                strat, _, seed_s = rem.rpartition("_s")
                return {
                    "key": key,
                    "content": content,
                    "network": net,
                    "users": users,
                    "seed": int(seed_s),
                    "strategy": strat,
                    "stage": "sentinel_rerun_e027",
                }
    except Exception:
        return None
    return None


def step_sentinel_rerun() -> int:
    """E027: live-rerun dump-less reused retention sentinels before FINAL_DEV."""
    req_p = REPO / "state" / "COMMAND153_SENTINEL_RERUN_REQUIRED.json"
    if not req_p.is_file():
        dump_dual("COMMAND153_SENTINEL_RERUN_COMPLETE.json", {"ts": ts(), "token": "COMMAND153_SENTINEL_RERUN_COMPLETE", "n": 0, "skipped": True})
        return 0
    req = json.loads(req_p.read_text())
    keys = list(req.get("keys") or [])
    qname = "COMMAND153_SENTINEL_RERUN_QUEUE.json"
    qp = REPO / "state" / qname
    q = json.loads(qp.read_text()) if qp.is_file() else {"completed": [], "failed": None, "n": len(keys)}
    done = set(q.get("completed") or [])
    pending = []
    for key in keys:
        cell = DEV_ART / key
        dumps = list(cell.glob("dump_*.bin")) if cell.is_dir() else []
        if dumps:
            if key not in done:
                done.add(key)
            continue
        pending.append(key)
    q["completed"] = sorted(done)
    q["n"] = len(keys)
    q["pending"] = pending
    dump_dual(qname, q)
    if not pending:
        dump_dual(
            "COMMAND153_SENTINEL_RERUN_COMPLETE.json",
            {"ts": ts(), "token": "COMMAND153_SENTINEL_RERUN_COMPLETE", "n": len(keys), "keys": keys},
        )
        print(json.dumps({"pass": True, "phase": "sentinel_rerun_complete", "n": len(keys)}))
        return 0
    key = pending[0]
    spec = _parse_maindev_key(key)
    if spec is None:
        return _fail_closed("sentinel_rerun_unparseable_key", {"key": key})
    cell = DEV_ART / key
    # Archive dump-less reuse stub so canary_cell launches a fresh live cell.
    if cell.is_dir() and (cell / "CELL_DONE.json").is_file() and not list(cell.glob("dump_*.bin")):
        bak = DEV_ART / f"{key}.e027_reuse_stub_bak"
        if bak.exists():
            import shutil as _sh

            _sh.rmtree(bak, ignore_errors=True)
        cell.rename(bak)
    print(json.dumps({"pass": True, "phase": "sentinel_rerun_launch", "key": key, "remaining": len(pending)}))
    return _launch(spec, DEV_ART, qname, len(keys))


def step_final_dev_freeze() -> int:
    missing = [
        n
        for n in (
            "COMMAND148_MAINDEV_COMPLETE",
            "COMMAND153_CROSS_STACK_DASH_COMPLETE",
            "COMMAND153_SCALING_COMPLETE",
            "COMMAND153_ABLATION_COMPLETE",
            "COMMAND153_FOV_COMPLETE",
            "COMMAND153_OVERHEAD_COMPLETE",
        )
        if not exists(n)
    ]
    if (REPO / "state" / "COMMAND153_SENTINEL_RERUN_REQUIRED.json").is_file() and not exists(
        "COMMAND153_SENTINEL_RERUN_COMPLETE"
    ):
        missing.append("COMMAND153_SENTINEL_RERUN_COMPLETE")
    counts = {
        "maindev": _queue_completed("COMMAND148_MAINDEV_QUEUE.json"),
        "h2": _queue_completed("COMMAND153_CROSS_STACK_DASH_QUEUE.json"),
        "scaling": _queue_completed("COMMAND153_SCALING_QUEUE.json"),
    }
    if missing or counts["maindev"] < 945 or counts["h2"] < 48 or counts["scaling"] < 150:
        return _fail_closed(
            "h2_cross_stack_dash_required_before_final_dev_freeze",
            {"missing": missing, "counts": counts},
        )
    dump_dual(
        "COMMAND153_FINAL_DEV_FREEZE.json",
        {
            "ts": ts(),
            "token": "COMMAND153_FINAL_DEV_FREEZE",
            "no_further_policy_model_hyperparameter_changes": True,
            "loot_sealed_until_holdout": True,
            "maindev_n": counts["maindev"],
            "h2_n": counts["h2"],
            "scaling_n": counts["scaling"],
        },
    )
    token("COMMAND153_FINAL_DEV_FROZEN", {"loot_next": True})
    print(json.dumps({"pass": True, "phase": "final_dev_frozen"}))
    return 0


def step_loot() -> int:
    if not exists("COMMAND153_FINAL_DEV_FROZEN"):
        return _fail_closed("loot_sealed_until_final_dev_frozen")
    qname = "COMMAND153_LOOT_QUEUE.json"
    rows = loot_matrix()
    assert len(rows) == 315
    qp = REPO / "state" / qname
    q = json.loads(qp.read_text()) if qp.is_file() else {"completed": [], "failed": None, "n": 315}
    LOOT_ART.mkdir(parents=True, exist_ok=True)
    done = set(q.get("completed") or [])
    for spec in rows:
        if spec["key"] in done:
            continue
        return _launch(spec, LOOT_ART, qname, 315)
    expected = [s["key"] for s in rows]
    if any(k not in done for k in expected):
        return _fail_closed("loot_incomplete", {"n": sum(1 for k in expected if k in done), "expected": 315})
    dump_dual("COMMAND153_LOOT_HOLDOUT_FREEZE.json", {"ts": ts(), "token": "COMMAND153_LOOT_HOLDOUT_FREEZE", "n": 315})
    token("COMMAND153_LOOT_HOLDOUT_FROZEN", {"n": len(done)})
    print(json.dumps({"pass": True, "phase": "loot_complete", "n": len(done)}))
    return 0


def step_evidence_and_terminal() -> int:
    ev = TON / "scripts" / "command153_evidence.py"
    return subprocess.run([str(PY), "-u", str(ev)], cwd=str(REPO)).returncode


def main() -> int:
    leftover = handle_unsupervised_live_wait()
    if leftover == 3:
        print(json.dumps({"pass": False, "reason": "unsupervised_live_after_lock_dead", "kill_live_cell": False}))
        return 3
    if leftover == 0:
        print(json.dumps({"pass": True, "wait": True, "reason": "unsupervised_live_grace", "kill_live_cell": False}))
        return 0
    if _live():
        print(json.dumps({"pass": True, "wait": True, "reason": "live_cell_untouched"}))
        return 0
    if not exists("COMMAND148_MAINDEV_COMPLETE"):
        print(json.dumps({"pass": True, "wait": True, "reason": "canary_or_dev_in_progress"}))
        return 0
    if not exists("COMMAND153_CROSS_STACK_DASH_COMPLETE"):
        dash = TON / "scripts" / "command153_cross_stack_dash.py"
        env = os.environ.copy()
        env["COMMAND152_LAUNCH"] = env.get("COMMAND152_LAUNCH") or "1"
        return subprocess.run([str(PY), "-u", str(dash)], cwd=str(REPO), env=env).returncode
    if not exists("COMMAND153_SCALING_COMPLETE"):
        return step_scaling()
    if not exists("COMMAND153_ABLATION_COMPLETE"):
        return step_ablation_manifest()
    if not exists("COMMAND153_FOV_COMPLETE"):
        return step_fov()
    if not exists("COMMAND153_OVERHEAD_COMPLETE"):
        return step_overhead()
    if (REPO / "state" / "COMMAND153_SENTINEL_RERUN_REQUIRED.json").is_file() and not exists(
        "COMMAND153_SENTINEL_RERUN_COMPLETE"
    ):
        return step_sentinel_rerun()
    if not exists("COMMAND153_FINAL_DEV_FROZEN"):
        return step_final_dev_freeze()
    if not exists("COMMAND153_LOOT_HOLDOUT_FROZEN"):
        return step_loot()
    return step_evidence_and_terminal()


if __name__ == "__main__":
    raise SystemExit(main())
