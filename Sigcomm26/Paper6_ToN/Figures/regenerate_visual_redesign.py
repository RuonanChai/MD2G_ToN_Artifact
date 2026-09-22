#!/usr/bin/env python3
"""Regenerate redesigned final PDFs at their existing filenames."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

FIG = Path(__file__).resolve().parent
SCRIPTS = [
    FIG / "Throughput" / "_bootstrap_throughput_scripts.py",
    FIG / "User_Experience_Trade-off" / "_bootstrap_tradeoff_scripts.py",
    FIG / "QoE" / "plot_qoe_by_strategy.py",
    FIG / "Buffer Level" / "plot_buffer_level_by_users.py",
    FIG / "Buffer Level" / "plot_maindev_utility_by_users.py",
    FIG / "QoE" / "plot_qoe_by_content_delta.py",
    FIG / "QoE" / "plot_qoe_by_network.py",
    FIG / "QoE" / "plot_loot_holdout_delta_u.py",
    FIG / "QoE" / "plot_mechanism_decomposition_loot.py",
    FIG / "QoE" / "plot_moq_shared_vs_unicast.py",
    FIG / "User_Experience_Trade-off" / "plot_h2_cross_stack_dash.py",
    FIG / "QoE" / "plot_weak_user_rq_loot.py",
    FIG / "Throughput" / "plot_throughput_4g.py",
    FIG / "Throughput" / "plot_throughput_5g.py",
    FIG / "Throughput" / "plot_throughput_default_mix.py",
    FIG / "Throughput" / "plot_throughput_wifi.py",
    FIG / "Throughput" / "plot_throughput_fiber_optic.py",
    FIG / "Throughput" / "plot_throughput_5g_dominant.py",
    FIG / "Throughput" / "plot_throughput_wifi_dominant.py",
    FIG / "User_Experience_Trade-off" / "plot_tradeoff_4g.py",
    FIG / "User_Experience_Trade-off" / "plot_tradeoff_5g.py",
    FIG / "User_Experience_Trade-off" / "plot_tradeoff_wifi.py",
    FIG / "User_Experience_Trade-off" / "plot_tradeoff_fiber_optic.py",
    FIG / "User_Experience_Trade-off" / "plot_tradeoff_default_mix.py",
]


def main() -> int:
    sys.path.insert(0, str(FIG))
    for i, p in enumerate(SCRIPTS):
        print(f"=== [{i+1}/{len(SCRIPTS)}] {p.relative_to(FIG)} ===", flush=True)
        try:
            runpy.run_path(str(p), run_name="__main__")
        except SystemExit as e:
            code = e.code
            if code not in (0, None):
                raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
