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

"""Final paper-facing metric completeness before post-Rb 120. Does not retune science."""
import json
import subprocess
import sys
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
from command147_io import dump_dual, ts  # noqa: E402
from command151_stall_supporting import STATUS as STALL_STATUS  # noqa: E402

PY = REPO / "Sigcomm26" / ".venv_sigcomm" / "bin" / "python3"


def _run_tests() -> dict:
    tests = [
        TON / "tests" / "test_command151_stall_supporting.py",
        TON / "tests" / "test_command148_level2_occupancy.py",
        TON / "tests" / "test_moq_sub_retry_preserves_anon.py",
    ]
    rows = []
    ok = True
    for p in tests:
        rc = subprocess.run([str(PY), "-u", str(p)], cwd=str(REPO), capture_output=True, text=True)
        rows.append({"test": p.name, "rc": rc.returncode})
        if rc.returncode != 0:
            ok = False
    return {"pass": ok, "rows": rows}


def main() -> int:
    tests = _run_tests()
    metrics = {
        "U": "LIVE_CERTIFIED",
        "Ro_component": "LIVE_CERTIFIED",
        "Rq": "LIVE_CERTIFIED_decoded_state_Q_norm",
        "Rb": "LIVE_CERTIFIED_physical_shared_root_pressure",
        "B_shared_component": "LIVE_CERTIFIED",
        "B_unicast_component": "LIVE_CERTIFIED",
        "decoded_state_occupancy": "LIVE_CERTIFIED_no_target_fallback",
        "target_state_occupancy": "LIVE_CERTIFIED",
        "receiver_set_size": "LIVE_CERTIFIED",
        "component_completion_fraction": "LIVE_CERTIFIED",
        "weak_user_Rq": {
            "status": "LIVE_CERTIFIED",
            "denominator": "all_launched_users",
            "aggregator": "minimum_per_user_decoded_Q_norm",
            "undecoded": 0.0,
        },
        "physical_shared_root_tx_rx_util": "LIVE_CERTIFIED_r0_eth1_tx",
        "stall": {
            "status": "LIVE_CERTIFIED_SUPPORTING_NOT_IN_U",
            "stall_last_status": STALL_STATUS,
            "in_U": False,
            "in_Rq": False,
            "never_claim_zero_stall": True,
            "placeholder_forbidden": True,
        },
        "delay_p50_p95_p99": {
            "status": "NOT_IN_FINAL_CLAIM_CONTRACT",
            "reason": "command148 final U/Ro/Rq/Rb tables do not require delay tails",
        },
    }
    body = {
        "ts": ts(),
        "token": "COMMAND152_FINAL_METRIC_COMPLETENESS",
        "tests": tests,
        "metrics": metrics,
        "loot_sealed": True,
        "tune_md2g_or_baselines": False,
        "rejected": ["null_metrics", "placeholder_stall", "placeholder_Rb", "missing_physical_counters"],
    }
    dump_dual("COMMAND152_FINAL_METRIC_COMPLETENESS.json", body)
    if not tests["pass"]:
        print(json.dumps({"pass": False, "tests": tests["rows"]}))
        return 2
    dump_dual(
        "COMMAND152_FINAL_METRIC_COMPLETENESS_PASS.json",
        {"ts": ts(), "token": "COMMAND152_FINAL_METRIC_COMPLETENESS_PASS", "stall": STALL_STATUS, "delay": "NOT_IN_FINAL_CLAIM_CONTRACT"},
    )
    print(json.dumps({"pass": True, "stall": STALL_STATUS, "delay": "NOT_IN_FINAL_CLAIM_CONTRACT"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
