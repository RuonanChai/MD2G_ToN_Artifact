#!/usr/bin/env python3
"""Run same-substrate analysis scripts in order."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = Path("python3")
SCRIPTS = [
    "mcg_baseline.py",
    "utility_weight_sensitivity.py",
    "controller_latency_breakdown.py",
    "completion_aware_analysis.py",
    "cross_content_generalization.py",
]


def main() -> int:
    for name in SCRIPTS:
        cmd = [str(PY), str(ROOT / name)]
        print("+", " ".join(cmd), flush=True)
        r = subprocess.run(cmd, cwd=str(ROOT))
        if r.returncode != 0:
            return r.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
