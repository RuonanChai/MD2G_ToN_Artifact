#!/usr/bin/env python3
"""H10 transition-commit unit + fidelity preflight. No Mininet."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
REPO = TON.parents[1]
import sys

sys.path.insert(0, str(TON / "scripts"))
from command142_h10_policy import (  # noqa: E402
    contract_from_env,
    remaining_unamortized_cost_s,
    transition_commit,
)


class TestH10(unittest.TestCase):
    def setUp(self):
        blob = json.loads((REPO / "state" / "COMMAND142_H10_MECHANISM_CONTRACT.json").read_text())
        self.c = contract_from_env(blob["env"])
        self.assertAlmostEqual(self.c.completion_lat_s, 1.02)
        self.assertAlmostEqual(self.c.amortize_s, self.c.completion_lat_s)
        self.assertAlmostEqual(self.c.emergency_buffer_s, 1.0)
        self.assertNotIn("MD2G_H9_EXIT_CONFIRM_TICKS", blob["env"])
        self.assertNotIn("MD2G_LAYERED_STICKY_ENH", blob["env"])
        self.assertNotIn("MD2G_H10_AMORTIZE_SEC", blob["env"])
        self.assertTrue(blob.get("no_independent_amortize_horizon"))

    def test_not_n_tick_exit_hold(self):
        """After completion amortized, a single E0 proposal exits. H9 required two zeros."""
        c = self.c
        a, s, p, ps = transition_commit(0, 0.0, None, 0.0, 10.0, 1, 4.0, c)
        self.assertEqual(a, 1)
        a2, s2, p2, _ = transition_commit(a, s, p, ps, 10.0 + c.completion_lat_s + 0.01, 0, 4.0, c)
        self.assertEqual(a2, 0)
        self.assertIsNone(p2)

    def test_refuses_reverse_before_completion_amortized(self):
        c = self.c
        a, s, p, ps = transition_commit(0, 0.0, None, 0.0, 10.0, 1, 4.0, c)
        self.assertEqual(a, 1)
        a2, s2, p2, _ = transition_commit(a, s, p, ps, 10.5, 0, 4.0, c)
        self.assertEqual(a2, 1)
        self.assertEqual(p2, 0)
        self.assertGreater(remaining_unamortized_cost_s(0.5, c), 0.0)

    def test_pending_flicker_cancels_without_apply(self):
        c = self.c
        a, s, p, ps = transition_commit(0, 0.0, None, 0.0, 10.0, 1, 4.0, c)
        a, s, p, ps = transition_commit(a, s, p, ps, 10.4, 0, 4.0, c)
        self.assertEqual(a, 1)
        self.assertEqual(p, 0)
        a3, _, p3, _ = transition_commit(a, s, p, ps, 10.5, 1, 4.0, c)
        self.assertEqual(a3, 1)
        self.assertIsNone(p3)

    def test_symmetric_reenter_refused_until_e0_amortized(self):
        """H9 raised enters after confirmed exit. H10 amortizes E0 before re-enter."""
        c = self.c
        a, s, p, ps = transition_commit(0, 0.0, None, 0.0, 10.0, 1, 4.0, c)
        a, s, p, ps = transition_commit(a, s, p, ps, 10.0 + c.completion_lat_s + 0.01, 0, 4.0, c)
        self.assertEqual(a, 0)
        a2, _, p2, _ = transition_commit(a, s, p, ps, s + 0.3, 1, 4.0, c)
        self.assertEqual(a2, 0)
        self.assertEqual(p2, 1)

    def test_safety_exits_immediately(self):
        c = self.c
        a, s, _, _ = transition_commit(1, 10.0, None, 10.0, 10.2, 1, 0.5, c)
        self.assertEqual(a, 0)

    def test_up_requires_enter_buffer(self):
        c = self.c
        a, _, p, _ = transition_commit(0, 0.0, None, 0.0, 5.0, 1, 1.01, c)
        self.assertEqual(a, 0)
        self.assertEqual(p, 1)

    def test_playability_down_covers_remaining_cost(self):
        c = self.c
        a, s, p, ps = transition_commit(0, 0.0, None, 0.0, 10.0, 1, 4.0, c)
        a2, _, _, _ = transition_commit(a, s, p, ps, 10.3, 0, 1.01, c)
        self.assertEqual(a2, 0)

    def test_one_applied_writer_identity(self):
        c = self.c
        a, s, p, ps = 0, 0.0, None, 0.0
        for t, prop in [(1.0, 1), (1.5, 0), (2.0, 1), (3.5, 1)]:
            a, s, p, ps = transition_commit(a, s, p, ps, t, prop, 4.0, c)
        self.assertIn(a, (0, 1, 2))

    def test_not_hidden_two_second_hold(self):
        c = self.c
        self.assertLess(c.completion_lat_s, 2.0)
        a, s, p, ps = transition_commit(0, 0.0, None, 0.0, 10.0, 1, 4.0, c)
        a2, _, p2, _ = transition_commit(a, s, p, ps, 11.03, 0, 4.0, c)
        self.assertEqual(a2, 0)
        self.assertIsNone(p2)


if __name__ == "__main__":
    unittest.main()
