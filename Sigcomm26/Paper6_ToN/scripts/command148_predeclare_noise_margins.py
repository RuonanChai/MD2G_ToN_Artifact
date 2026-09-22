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

"""Predeclare canary baseline-noise margins before MD2G aggregate interpretation."""
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import dump_dual, ts  # noqa: E402


def main() -> int:
    body = {
        "ts": ts(),
        "token": "COMMAND148_CANARY_NOISE_MARGINS_PREDECLARED",
        "predeclared_before_md2g_aggregate": True,
        "paired_U_noise_abs": 0.03,
        "competitive_if_mean_delta_U_ge": -0.03,
        "advantage_if_mean_delta_U_ge": 0.03,
        "catastrophic_Rq_drop_vs_best_same_substrate": 0.15,
        "catastrophic_stall_increase": 0.25,
        "catastrophic_weak_user_Rq_drop": 0.15,
        "all_lowest_collapse_if_upgrade_fraction_lt": 0.05,
        "pathological_explosion_if_mean_active_components_gt": 5,
        "same_substrate": ["HV3_COMPONENT", "CLUSTERING_COMPONENT", "RULE_COMPONENT"],
        "cross_stack_note": "MOQ_UNICAST_COMPONENT is same-transport unicast control; GROOT/Rolling remain DASH appendix",
        "loot_sealed": True,
        "note": "Frozen before first matched five-strategy canary block is interpreted.",
    }
    dump_dual("COMMAND148_CANARY_NOISE_MARGINS_PREDECLARED.json", body)
    print(body["token"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
