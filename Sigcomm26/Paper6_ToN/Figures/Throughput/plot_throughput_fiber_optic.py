#!/usr/bin/env python3
"""Shared-root TX throughput vs users (Fiber_Optic). Filename retains Bar for identity."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_style import plot_throughput_network  # noqa: E402

NETWORK = "fiber_optic"
OUT = Path(__file__).resolve().parent / "System_Throughput_Bar_Fiber_Optic.pdf"


def main() -> int:
    plot_throughput_network(NETWORK, OUT)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
