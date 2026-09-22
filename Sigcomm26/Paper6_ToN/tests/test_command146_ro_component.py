#!/usr/bin/env python3
"""Invariance tests for Ro_component (no Mininet)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from ton_ro_component import b_shared, b_unicast, marginal_bytes, paper_u, ro_component  # noqa: E402

PAY = {"b0": 100, "db1": 40, "db2": 50, "e1": 30, "e2": 20}


def main() -> int:
    # 1. renaming Rep IDs cannot change Ro
    u1 = {"u0": ["b0", "db1"], "u1": ["b0", "db1", "e1"]}
    u2 = {"alice": ["b0", "db1"], "bob": ["b0", "db1", "e1"]}
    shared = ["b0", "db1", "e1"]
    r1 = ro_component(b_shared(shared, PAY), b_unicast(u1, PAY))
    r2 = ro_component(b_shared(shared, PAY), b_unicast(u2, PAY))
    assert r1 == r2

    # 2. two users sharing prerequisites: one shared prerequisite cost
    bu = b_unicast({"u0": ["b0"], "u1": ["b0"]}, PAY)
    bs = b_shared(["b0"], PAY)
    assert bu == 200 and bs == 100
    assert abs(ro_component(bs, bu) - 0.5) < 1e-9

    # 3. upgrade by already-active component: zero incremental shared cost
    assert marginal_bytes(["b0", "db1"], ["b0", "db1", "e1"], PAY) == 0

    # 4. missing component adds exactly that component
    assert marginal_bytes(["b0", "e1"], ["b0"], PAY) == 30

    # 5. full unicast Ro≈0
    users = {f"u{i}": ["b0", "e1"] for i in range(3)}
    bu = b_unicast(users, PAY)
    bs_uni = bu  # counted per user
    assert ro_component(bs_uni, bu) == 0.0

    # 6. perfect sharing: one copy of union
    bs = b_shared(["b0", "e1"], PAY)
    assert ro_component(bs, bu) > 0.5

    # paper weights
    u = paper_u(0.4, 0.8, 0.2)
    assert abs(u - (0.25 * 0.4 + 0.60 * 0.8 - 0.15 * 0.2)) < 1e-12
    print("PASS command146 Ro_component invariance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
