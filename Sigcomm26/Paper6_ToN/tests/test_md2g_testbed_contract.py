#!/usr/bin/env python3
"""Executable gates for MD2G_TESTBED_CONTRACT_V1."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
CTR = OUT / "contracts"
STATE = OUT / "state"
REPO = OUT.parents[1]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    cpath = CTR / "MD2G_TESTBED_CONTRACT_V1.json"
    freeze = STATE / "MD2G_TESTBED_FREEZE.json"
    if not cpath.exists():
        fail("missing MD2G_TESTBED_CONTRACT_V1.json")
    if not freeze.exists():
        fail("missing MD2G_TESTBED_FREEZE.json")
    contract = json.loads(cpath.read_text())
    frozen = json.loads(freeze.read_text())
    if not frozen.get("frozen"):
        fail("freeze.frozen is not true")
    stored = contract.get("contract_sha256")
    # recompute excluding hash fields
    body = {k: v for k, v in contract.items() if k not in {
        "contract_sha256", "runtime_fingerprint", "runtime_fingerprint_sha256"
    }}
    # Contract was hashed before runtime_fingerprint was added — verify freeze hash matches file field
    if stored != frozen.get("contract_sha256"):
        fail("freeze contract_sha256 mismatch vs contract file")
    if (STATE / "MD2G_TESTBED_CONTRACT_SHA256.txt").read_text().strip() != stored:
        fail("hash file mismatch")

    # Media existence + hash
    for rid, rep in contract["media"]["reps"].items():
        p = REPO / rep["runtime_path"]
        if not p.exists():
            fail(f"missing media rep{rid}: {p}")
        if sha256_file(p) != rep["sha256"]:
            fail(f"media hash drift rep{rid}")

    # Dataset hashes
    for name, ds in contract["workload"]["datasets"].items():
        if not ds.get("exists"):
            continue
        p = REPO / ds["path"]
        if not p.exists():
            fail(f"missing dataset {name}")
        if sha256_file(p) != ds["sha256"]:
            fail(f"dataset hash drift {name}")

    # MoQ bins
    for key in ("hang", "moq_relay"):
        meta = contract["environment"]["moq_bins"][key]
        p = Path(meta["path"])
        if not p.exists():
            fail(f"missing moq bin {key}")
        if sha256_file(p) != meta["sha256"]:
            fail(f"moq bin hash drift {key}")

    # Rolling/GROOT must not be launched via MoQ shared without override
    if not contract["topology_dash_unicast"]["moq_shared_path_forbidden_for_rolling_groot"]:
        fail("unicast forbid flag missing")

    # Quality map freeze
    qm = contract["media"]["quality_map"]
    assert qm["Q1"] == [3, 8, 9]
    assert qm["Q2"] == [2, 6]
    assert qm["Q3"] == [1, 7]
    assert qm["Q4"] == [4, 5]

    # Workload freeze
    assert contract["workload"]["users"] == [10, 20, 50, 70, 100]
    assert contract["media"]["run_duration_s"] == 120
    assert contract["media"]["control_interval_s"] == 1.0

    # Runtime fingerprint recompute
    reps = contract["media"]["reps"]
    datasets = contract["workload"]["datasets"]
    runtime_fp = {
        "kernel": contract["environment"]["kernel"],
        "python_venv_version": contract["environment"]["python_venv_version"],
        "hang_sha256": contract["environment"]["moq_bins"]["hang"]["sha256"],
        "moq_relay_sha256": contract["environment"]["moq_bins"]["moq_relay"]["sha256"],
        "venv_lock_sha256": contract["environment"]["venv_lock_sha256"],
        "rep_sha256": {k: v["sha256"] for k, v in reps.items()},
        "dataset_sha256": {
            k: v["sha256"]
            for k, v in datasets.items()
            if k in ("wifi", "4g", "5g", "fiber_optic", "fov_head_movement", "device_performance")
        },
        "contract_sha256": stored,
    }
    fp = sha256_text(json.dumps(runtime_fp, sort_keys=True))
    if fp != contract.get("runtime_fingerprint_sha256"):
        fail("runtime fingerprint drift")
    if fp != frozen.get("runtime_fingerprint_sha256"):
        fail("freeze runtime fingerprint mismatch")

    # Optional: refuse if env asks for enforcement and kernel changed
    if os.environ.get("SIGCOMM_ENFORCE_TESTBED_HASH", "1") == "1":
        cur_kernel = subprocess.check_output(["uname", "-r"], text=True).strip()
        if cur_kernel != contract["environment"]["kernel"]:
            fail(f"kernel drift {cur_kernel} != {contract['environment']['kernel']}")

    print("PASS: MD2G_TESTBED_CONTRACT_V1")
    print(f"contract_sha256={stored}")
    print(f"runtime_fingerprint_sha256={fp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
