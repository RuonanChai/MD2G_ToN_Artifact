#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Common strategy interface for MD2G_PPO, RollingDRL, TwoStageHeuristic, and PredictiveClustering."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import numpy as np


class StrategyBase(ABC):
    """All strategies implement compute_actions."""

    def __init__(self, max_users: int):
        self.max_users = max_users

    @abstractmethod
    def compute_actions(self, state: Dict[str, Any]) -> List[int]:
        """Return one action per user: 0 = base, 1 = enhanced."""
        pass

    def get_strategy_name(self) -> str:
        """Return the strategy class name."""
        return self.__class__.__name__
