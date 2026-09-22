#!/usr/bin/env python3
"""NOT Fig.4-family. Tier-B Rb vs U trade-off scatter (4G)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_style import plot_rb_u_tradeoff  # noqa: E402

NETWORK = "4g"
OUT = Path(__file__).resolve().parent / "TierB_Rb_vs_U_4G.pdf"


def main() -> int:
    plot_rb_u_tradeoff(NETWORK, OUT)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
