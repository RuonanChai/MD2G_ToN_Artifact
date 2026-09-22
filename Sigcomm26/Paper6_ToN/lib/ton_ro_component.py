#!/usr/bin/env python3
"""Ro_component accounting. Do not reuse command116 per-representation B_shared."""
from __future__ import annotations

from typing import Iterable, Mapping


def clip01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


def paper_u(ro: float, rq: float, rb: float) -> float:
    return clip01(0.25 * ro + 0.60 * rq - 0.15 * rb)


def b_unicast(user_components: Mapping[str, Iterable[str]], payload_bytes: Mapping[str, int]) -> int:
    total = 0
    for comps in user_components.values():
        for c in comps:
            total += int(payload_bytes.get(c, 0))
    return total


def b_shared(active_once: Iterable[str], payload_bytes: Mapping[str, int]) -> int:
    return sum(int(payload_bytes.get(c, 0)) for c in set(active_once))


def ro_component(b_shared_v: int, b_unicast_v: int) -> float:
    if b_unicast_v <= 0:
        return 0.0
    return clip01(1.0 - (b_shared_v / b_unicast_v))


def marginal_components(candidate: Iterable[str], active: Iterable[str]) -> list[str]:
    a = set(active)
    return [c for c in candidate if c not in a]


def marginal_bytes(candidate: Iterable[str], active: Iterable[str], payload_bytes: Mapping[str, int]) -> int:
    return sum(int(payload_bytes.get(c, 0)) for c in marginal_components(candidate, active))
