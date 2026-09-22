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

"""COMMAND149 post-pause: preserve pre-repair canary, retrain, recertify, reset 0/120, release.

Run only when no scientific cell is live and INTEGRITY_HOLD is set.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

TON = ton_root()
REPO = artifact_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import dump_dual, sha256_file, token, ts  # noqa: E402

PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"
ART = TON / "artifacts" / "command148_canary120"
PRE = TON / "artifacts" / "command148_canary120_PRE_MARGINAL_COST_TRAINING_CONTRACT"
MODEL_DIR = TON / "models" / "command148_component"
PRE_MODEL = TON / "models" / "command148_component_PRE_MARGINAL_COST_TRAINING_CONTRACT"


def live_canary() -> bool:
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            cmd = (p / "cmdline").read_bytes().replace(b"\x00", b" ").decode()
        except Exception:
            continue
        if "command148_canary_cell.py" in cmd:
            return True
    return False


def run_script(name: str) -> int:
    return subprocess.run([str(PY), "-u", str(TON / "scripts" / name)], cwd=str(REPO)).returncode


def main() -> int:
    hold = REPO / "state" / "COMMAND149_CANARY_INTEGRITY_HOLD.json"
    if not hold.is_file():
        print(json.dumps({"pass": False, "reason": "no_hold"}))
        return 2
    if live_canary():
        print(json.dumps({"pass": False, "reason": "live_cell", "wait": True}))
        return 0
    q = json.loads((REPO / "state" / "COMMAND148_CANARY120_QUEUE.json").read_text())
    PRE_MODEL.mkdir(parents=True, exist_ok=True)
    for fn in ("teacher_component_v1.pt", "student_component_v1.pt"):
        src = MODEL_DIR / fn
        dst = PRE_MODEL / fn
        if src.is_file() and not dst.is_file():
            shutil.copy2(src, dst)
    if ART.is_dir() and not PRE.exists():
        ART.rename(PRE)
    ART.mkdir(parents=True, exist_ok=True)
    if not (REPO / "state" / "COMMAND148_CANARY120_PRE_MARGINAL_COST_TRAINING_CONTRACT.json").is_file():
        dump_dual(
            "COMMAND148_CANARY120_PRE_MARGINAL_COST_TRAINING_CONTRACT.json",
            {
                "ts": ts(),
                "label": "PRE_MARGINAL_COST_TRAINING_CONTRACT",
                "not_final_science": True,
                "completed": list(q.get("completed") or []),
                "status_at_preserve": q.get("status"),
                "invalid": q.get("invalid") or [],
                "loot_sealed": True,
            },
        )
    dump_dual(
        "COMMAND148_CANARY120_QUEUE.json",
        {
            "ts": ts(),
            "n": 120,
            "completed": [],
            "failed": None,
            "attempts": {},
            "invalid": [],
            "status": "0/120",
            "loot_sealed": True,
            "post_command149_repair": True,
            "pre_repair_archive": str(PRE),
        },
    )
    print(json.dumps({"phase": "retrain_start", "ts": ts()}), flush=True)
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["COMMAND149_REUSE_TEACHER"] = "1"
    rc = subprocess.run(
        [str(PY), "-u", str(TON / "scripts" / "command148_train_teacher_student.py")],
        cwd=str(REPO),
        env=env,
    ).returncode
    if rc != 0:
        print(json.dumps({"pass": False, "reason": "retrain_failed", "rc": rc}))
        return rc
    tpath = MODEL_DIR / "teacher_component_v1.pt"
    spath = MODEL_DIR / "student_component_v1.pt"
    dump_dual(
        "COMMAND149_POST_REPAIR_MODEL_HASHES.json",
        {
            "ts": ts(),
            "teacher_sha256": sha256_file(tpath),
            "student_sha256": sha256_file(spath),
            "physics": "missing_component_DeltaR",
            "margin": 1.05,
            "pre_repair_models": str(PRE_MODEL),
        },
    )
    print(json.dumps({"phase": "recert_p3p4p5", "ts": ts()}), flush=True)
    recert_rc = {}
    for name in (
        "command147_capacity_offline_cert.py",
        "command147_capacity_estimator_cert.py",
        "command147_capacity_live_estimator_cert.py",
        "command147_actuation_live_cert.py",
        "command147_live_metric_cert.py",
    ):
        recert_rc[name] = run_script(name)
        print(json.dumps({"recert": name, "rc": recert_rc[name]}), flush=True)
    ut = subprocess.run(
        [str(PY), "-m", "unittest", "Sigcomm26.Paper6_ToN.tests.test_command149_marginal_cost", "-v"],
        cwd=str(REPO),
    )
    recert_rc["unittest_command149"] = ut.returncode
    ok = all(int(v) == 0 for v in recert_rc.values())
    dump_dual(
        "COMMAND149_P3P4P5_RECERT.json",
        {"ts": ts(), "rcs": recert_rc, "pass": ok, "canary_path": "command148_component_policy+command149_marginal_cost"},
    )
    if not ok:
        print(json.dumps({"pass": False, "reason": "recert_failed", "rcs": recert_rc}))
        return 3
    token(
        "COMMAND149_TRAINING_RUNTIME_MARGINAL_COST_REPAIRED_AND_RECERTIFIED",
        {
            "student_sha256": sha256_file(spath),
            "teacher_sha256": sha256_file(tpath),
            "pre_repair_not_final": True,
            "canary_restart": "0/120",
        },
    )
    dump_dual(
        "COMMAND149_CANARY_RELEASE.json",
        {
            "ts": ts(),
            "token": "COMMAND149_TRAINING_RUNTIME_MARGINAL_COST_REPAIRED_AND_RECERTIFIED",
            "resume": "command148_canary_0_120_post_repair",
            "mix_pre_post_forbidden": True,
            "loot_sealed": True,
            "v2_not_started": True,
            "policy_not_tuned": True,
            "margin_unchanged": 1.05,
        },
    )
    print(json.dumps({"pass": True, "released": True, "rcs": recert_rc}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
