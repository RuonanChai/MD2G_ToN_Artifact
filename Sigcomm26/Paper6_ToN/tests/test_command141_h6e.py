#!/usr/bin/env python3
"""H6-E is H6-D with only completion_p 0.7→1.0."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
REPO = TON.parents[1]
sys.path.insert(0, str(TON / "scripts"))
from command141_h6_policy import candidate_from_env, completion_likely  # noqa: E402


class TestH6E(unittest.TestCase):
    def test_only_completion_p_differs_from_h6d(self):
        blob = json.loads((REPO / "state" / "COMMAND141_H6_CANDIDATES.json").read_text())
        by = {c["id"]: c for c in blob["candidates"]}
        d, e = by["H6-D_BALANCED_ENTERBUF_1S"]["env"], by["H6-E_COMPLETION_P_1"]["env"]
        self.assertEqual(e["MD2G_H6_COMPLETION_P"], "1.0")
        self.assertEqual(d["MD2G_H6_COMPLETION_P"], "0.7")
        for k in set(d) | set(e):
            if k == "MD2G_H6_COMPLETION_P":
                continue
            self.assertEqual(d.get(k), e.get(k), k)

    def test_observed_h6d_p50_opens_e_not_d(self):
        blob = json.loads((REPO / "state" / "COMMAND141_H6_CANDIDATES.json").read_text())
        by = {c["id"]: c for c in blob["candidates"]}
        d = candidate_from_env(by["H6-D_BALANCED_ENTERBUF_1S"]["env"])
        e = candidate_from_env(by["H6-E_COMPLETION_P_1"]["env"])
        self.assertFalse(completion_likely(1.05, d))
        self.assertTrue(completion_likely(1.05, e))
        self.assertFalse(completion_likely(1.00, e))


if __name__ == "__main__":
    unittest.main()
