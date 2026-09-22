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

"""Level-2 matched-block review for completed command147 smoke cells."""
import json
from collections import defaultdict
from pathlib import Path

REPO = artifact_root()
ART = REPO / "Sigcomm26" / "Paper6_ToN" / "artifacts" / "command147_24cell_smoke"
OUT = REPO / "reviews" / "command148"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    by = defaultdict(list)
    for d in sorted(ART.iterdir()):
        done = d / "CELL_DONE.json"
        if not done.is_file() or "_attempt1_" in d.name:
            continue
        body = json.loads(done.read_text())
        pattern = body.get("audit", {}).get("pattern") or body.get("pattern")
        by[pattern].append({"key": d.name, "pass": body.get("audit", {}).get("pass"), "rc": body.get("audit", {}).get("rc")})
    summary = {"blocks": {}, "direction": "fidelity_only_not_controller_ranking"}
    for pat, rows in by.items():
        summary["blocks"][pat] = {
            "n": len(rows),
            "all_pass": all(r.get("pass") for r in rows),
            "keys": [r["key"] for r in rows],
            "favorable_unfavorable": "N/A_fidelity_smoke",
        }
    (OUT / "SMOKE_LEVEL2_BLOCKS.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v["n"] for k, v in summary["blocks"].items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
