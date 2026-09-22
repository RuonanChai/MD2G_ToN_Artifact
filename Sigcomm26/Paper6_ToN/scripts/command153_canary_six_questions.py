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

"""Write mechanical six-question + E020 audit. Safe to run while a cell is live (reads CELL_DONE only)."""
import json
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command153_canary_six_questions import write_reports  # noqa: E402


def main() -> int:
    final = "--final" in sys.argv
    n_boot = 10000
    if "--n-boot" in sys.argv:
        i = sys.argv.index("--n-boot")
        n_boot = int(sys.argv[i + 1])
    body = write_reports(final=final, n_boot=n_boot)
    e = body.get("E020") or {}
    print(
        json.dumps(
            {
                "pass": True,
                "status": body.get("status"),
                "n_completed": body.get("n_completed_queue"),
                "n_matched": body.get("n_matched_same_substrate_blocks"),
                "delta_U_mean": ((body.get("Q1_matched_delta_U_vs_strongest_same_substrate") or {}).get("delta_U") or {}).get("mean"),
                "crossover": ((body.get("Q2_u20_vs_u60_crossover") or {}).get("high_concurrency_crossover_still_holds_under_real_Rb")),
                "ld_u60_special": ((body.get("Q3_content_direction") or {}).get("rb_u60_advantage_is_content_special_case")),
                "e020_waiting": e.get("mininet_waiting_assertion_count_post_E020"),
                "e020_pressure_missing": e.get("pressure_samples_missing_post_E020"),
                "e020_validity_missing": e.get("CELL_VALIDITY_missing_post_E020"),
                "e020_closed": e.get("closed"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
