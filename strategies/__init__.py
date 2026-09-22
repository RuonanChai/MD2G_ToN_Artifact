# strategies/__init__.py
"""Strategy package. Lazy-import torch-dependent submodules."""

from __future__ import annotations

__all__ = [
    "StrategyBase",
]


def __getattr__(name: str):
    """Lazy attribute access for optional / heavy strategies."""
    if name == "StrategyBase":
        from .strategy_base import StrategyBase
        return StrategyBase
    if name == "MD2G_PPO_Strategy":
        from .md2g_ppo_strategy import MD2G_PPO_Strategy
        return MD2G_PPO_Strategy
    if name == "RollingDRLStrategy":
        from .rolling_drl_strategy import RollingDRLStrategy
        return RollingDRLStrategy
    if name == "TwoStageHeuristicStrategy":
        from .two_stage_heuristic_strategy import TwoStageHeuristicStrategy
        return TwoStageHeuristicStrategy
    if name == "PredictiveClusteringStrategy":
        from .predictive_clustering_strategy import PredictiveClusteringStrategy
        return PredictiveClusteringStrategy
    if name == "run_enhanced_heuristic_controller":
        from .heuristic_controller_v2_refined import run_enhanced_heuristic_controller
        return run_enhanced_heuristic_controller
    if name == "run_enhanced_predictive_controller":
        from .predictive_controller_v2_refined import run_enhanced_predictive_controller
        return run_enhanced_predictive_controller
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
