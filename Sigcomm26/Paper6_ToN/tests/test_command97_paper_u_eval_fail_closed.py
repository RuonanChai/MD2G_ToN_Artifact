#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed: paper-facing MoQ utility must not trace to λq=0.625 / λb=0.125."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
SCRIPTS = TON / "scripts"
sys.path.insert(0, str(SCRIPTS))

from command96_canonical_score import canonical_score  # noqa: E402
from command97_paper_u_eval import PAPER_METRIC, paper_u_eval  # noqa: E402

CORE = TON / "artifacts" / "command94_core"
ANALYSIS = TON / "analysis"
STATE = TON / "state"
MOQ = {"c28", "hv3", "clustering"}


class TestCommand97PaperUEval(unittest.TestCase):
    def test_paper_u_formula(self):
        # Known sample: Ro=1, Rq=0.776, Rb=0.5
        u = paper_u_eval(1.0, 0.776, 0.5)
        self.assertAlmostEqual(u, 0.25 * 1.0 + 0.60 * 0.776 - 0.15 * 0.5, places=12)
        # Must NOT equal runtime 0.625/0.125 combination
        runtime = max(0.0, 0.25 * 1.0 + 0.625 * 0.776 - 0.125 * 0.5)
        self.assertNotAlmostEqual(u, runtime, places=6)

    def test_canonical_moq_cells_use_paper_metric(self):
        n = 0
        for p in CORE.glob("**/CELL_DONE.json"):
            d = json.loads(p.read_text())
            if not d.get("valid"):
                continue
            strat = str(d.get("strategy") or "")
            if strat not in MOQ:
                continue
            sc = canonical_score(d, p.parent)
            n += 1
            self.assertTrue(sc.get("ok") is not False, msg=str(p))
            self.assertIsNotNone(sc.get("U"), msg=str(p))
            self.assertEqual(sc.get("metric"), PAPER_METRIC, msg=str(p))
            self.assertEqual(sc.get("lambdas"), {"Ro": 0.25, "Rq": 0.60, "Rb": 0.15}, msg=str(p))
            # Forbidden runtime lambdas must not appear as paper lambdas
            self.assertNotEqual(sc.get("lambdas", {}).get("Rq"), 0.625)
            self.assertNotEqual(sc.get("lambdas", {}).get("Rb"), 0.125)
            # runtime provenance may exist but must be labeled non-paper
            if "runtime_reward_final_label" in sc:
                self.assertIn("non_paper", sc["runtime_reward_final_label"])
            # CELL_DONE score_paper must match canonical U
            if d.get("score_paper") and d["score_paper"].get("U") is not None:
                self.assertAlmostEqual(float(sc["U"]), float(d["score_paper"]["U"]), places=9)
            # raw score.U if present is provenance only
            if isinstance(d.get("score"), dict) and d["score"].get("non_paper_non_canonical"):
                self.assertTrue(True)
            paper = p.parent / "PAPER_U_EVAL.json"
            self.assertTrue(paper.exists(), msg=f"missing {paper}")
            blob = json.loads(paper.read_text())
            self.assertEqual((blob.get("score") or {}).get("metric"), PAPER_METRIC)
            # Fail if paper score claims forbidden lambdas
            lam = (blob.get("score") or {}).get("lambdas") or {}
            self.assertNotEqual(lam.get("Rq"), 0.625)
            self.assertNotEqual(lam.get("Rb"), 0.125)
        self.assertGreater(n, 0, "no MoQ cells found")

    def test_paper_facing_block_summaries_use_canonical(self):
        blocks = ANALYSIS / "command96_blocks"
        if not blocks.exists():
            self.skipTest("no block summaries yet")
        for p in blocks.glob("*.json"):
            d = json.loads(p.read_text())
            # After refresh, paper_utility_metric should be present; if U_mean exists for MoQ strats
            # require lineage field when command97 refresh has run.
            lineage = d.get("paper_utility_lineage")
            if lineage is None:
                # Fail-closed once COMMAND97_U_IDENTITY_PASS exists
                if (STATE / "COMMAND97_U_IDENTITY_PASS").exists():
                    self.fail(f"{p.name} missing paper_utility_lineage after U_IDENTITY_PASS")
                continue
            self.assertEqual(lineage.get("moq"), PAPER_METRIC)
            self.assertEqual(lineage.get("dash"), "command96_dash_v1")
            text = p.read_text()
            # Hard reject paper summary that embeds runtime lambda as paper weights
            if '"paper_lambdas"' in text:
                self.assertNotIn('"Rq": 0.625', text)
                self.assertNotIn('"Rb": 0.125', text)

    def test_ledger_coverage(self):
        led = ANALYSIS / "COMMAND97_PAPER_U_LEDGER.json"
        self.assertTrue(led.exists())
        d = json.loads(led.read_text())
        self.assertEqual(d.get("n_identity_fail"), 0)
        keys = set(d.get("one_to_one_keys") or [])
        # Every valid MoQ CELL_DONE must be in ledger
        for p in CORE.glob("**/CELL_DONE.json"):
            j = json.loads(p.read_text())
            if not j.get("valid") or j.get("strategy") not in MOQ:
                continue
            key = f"{j['content']}/{j['net']}/users_{j['users']}/{j['strategy']}/seed_{j['seed']}"
            self.assertIn(key, keys, msg=f"missing ledger key {key}")


if __name__ == "__main__":
    unittest.main()
