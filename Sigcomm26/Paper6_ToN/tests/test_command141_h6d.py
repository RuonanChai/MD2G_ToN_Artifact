#!/usr/bin/env python3
"""H6-D is H6-B with only enter_buffer 1.2→1.0."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
REPO = TON.parents[1]
sys.path.insert(0, str(TON / "scripts"))
from command141_h6_policy import candidate_from_env, completion_likely  # noqa: E402


class TestH6D(unittest.TestCase):
    def test_only_enter_buffer_differs_from_h6b(self):
        blob = json.loads((REPO / "state" / "COMMAND141_H6_CANDIDATES.json").read_text())
        by = {c["id"]: c for c in blob["candidates"]}
        b, d = by["H6-B_BALANCED"]["env"], by["H6-D_BALANCED_ENTERBUF_1S"]["env"]
        self.assertEqual(d["MD2G_H6_ENTER_BUFFER_SEC"], "1.0")
        self.assertEqual(b["MD2G_H6_ENTER_BUFFER_SEC"], "1.2")
        keys = set(b) | set(d)
        for k in keys:
            if k == "MD2G_H6_ENTER_BUFFER_SEC":
                continue
            self.assertEqual(b.get(k), d.get(k), k)

    def test_completion_likely_at_observed_buffer_is_audit_target(self):
        env = json.loads((REPO / "state" / "COMMAND141_H6_CANDIDATES.json").read_text())
        d = [c for c in env["candidates"] if c["id"] == "H6-D_BALANCED_ENTERBUF_1S"][0]
        cand = candidate_from_env(d["env"])
        self.assertTrue(completion_likely(1.50, cand))
        self.assertFalse(completion_likely(1.10, cand))


if __name__ == "__main__":
    unittest.main()
