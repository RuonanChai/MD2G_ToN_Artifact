#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Regression: holdout-blind development paired effect can satisfy freeze gate."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

OUT = ton_root()
sys.path.insert(0, str(OUT / "scripts"))

import md2g_dev_paired_effect as pe  # noqa: E402
import command49_try_freeze as freeze  # noqa: E402


class TestDevPairedEffect(unittest.TestCase):
    def test_development_paired_records_and_supports_family(self):
        paired = pe.evaluate("CAND_TEST_PAIRED", canary_dir=None)
        self.assertTrue(paired["paired_effect_recorded"])
        self.assertTrue(paired["holdout_blind"])
        self.assertFalse(paired["used_contaminated_holdout"])
        self.assertGreaterEqual(paired["development_baseline"]["n_pairs"], 20)
        self.assertGreaterEqual(paired["val_win_tie_rate"], 0.50)
        self.assertTrue(paired["baseline_supports_md2g_family"])
        # Must not touch replacement holdout roots
        art = paired["development_baseline"]["artifact_root"]
        self.assertNotIn("holdout_replacement", art)
        self.assertEqual(paired["development_baseline"]["networks"], ["5g", "wifi"])

    def test_try_freeze_requires_pass_development_paired(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cand = "CAND_FAKE_FREEZE"
            cdir = root / "candidates" / cand
            cdir.mkdir(parents=True)
            snap = {
                "candidate_id": cand,
                "canary_status": "PASS",
                "paired_effect_recorded": True,
                "validation_status": "PASS_DEVELOPMENT_PAIRED",
                "val_win_tie_rate": 0.9,
                "baseline_supports_md2g_family": True,
                "holdout_blind": True,
                "used_contaminated_holdout": False,
            }
            (cdir / "eval_snapshot.json").write_text(json.dumps(snap) + "\n")
            dec_dir = OUT / "agents" / "decisions" / cand
            # Use isolated temp state via mocks
            state = root / "state"
            state.mkdir()
            agents = root / "agents"
            (agents / "decisions" / cand).mkdir(parents=True)
            (agents / "decisions" / cand / "MAIN_DECISION.json").write_text(
                json.dumps({"candidate_id": cand, "all_pass": True}) + "\n"
            )
            (state / "MD2G_DESIGN_SEARCH_ARTIFACT_ROOT.txt").write_text(str(root) + "\n")
            aud = root / "audits"
            aud.mkdir()
            with mock.patch.object(freeze, "STATE", state), mock.patch.object(freeze, "AGENTS", agents), mock.patch.object(
                freeze, "AUD", aud
            ):
                rc = freeze.main()
                self.assertEqual(rc, 0)
                self.assertTrue((state / "MD2G_FINAL_DESIGN_FREEZE.json").exists())
                tok = json.loads((state / "MD2G_FINAL_DESIGN_FREEZE.json").read_text())["token"]
                self.assertEqual(tok, "MD2G_FINAL_DESIGN_FROZEN")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
