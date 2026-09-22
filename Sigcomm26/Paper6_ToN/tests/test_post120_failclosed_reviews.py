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

"""Fail-closed classify must see DEV/scaling/loot queues, not only canary/24cell."""
import unittest
from pathlib import Path

TON = ton_root()
CLS = TON / "scripts" / "command153_classify_and_repair.py"
DEV = TON / "scripts" / "command148_main_dev.py"
CONT = TON / "scripts" / "command153_continue.py"
EV = TON / "scripts" / "command153_evidence.py"


class TestPost120FailClosedAndReviews(unittest.TestCase):
    def test_classify_scans_maindev_scaling_loot(self):
        txt = CLS.read_text()
        self.assertIn("COMMAND148_MAINDEV_QUEUE.json", txt)
        self.assertIn("COMMAND153_SCALING_QUEUE.json", txt)
        self.assertIn("COMMAND153_LOOT_QUEUE.json", txt)

    def test_maindev_does_not_blind_retry_failed(self):
        txt = DEV.read_text()
        self.assertIn("maindev_fail_closed", txt)
        self.assertIn("command153_classify_and_repair.py", txt)
        self.assertIn("n_try >= 3 and auth is None", txt)
        self.assertIn("n_try >= 3 and auth is None", CONT.read_text())

    def test_evidence_requires_six_reviews(self):
        txt = EV.read_text()
        self.assertIn("COMMAND153_SIX_REVIEWS.md", txt)
        self.assertIn("command153_final_reviews.py", txt)
        self.assertIn("injected_fail_closed", CONT.read_text())
        self.assertIn("COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED", CONT.read_text())
        self.assertIn("command153_final_reviews.py", EV.read_text().split("HASH_FILES", 1)[1].split("def exists", 1)[0])
        self.assertIn("command153_classify_and_repair.py", EV.read_text().split("HASH_FILES", 1)[1].split("def exists", 1)[0])

    def test_six_reviews_na_not_validation_and_scaling_split(self):
        txt = (TON / "scripts" / "command153_final_reviews.py").read_text()
        self.assertIn("NOT_APPLICABLE is never experimental validation", txt)
        self.assertIn("90 DEV reuse", txt)
        self.assertIn("h2_n >= 48", txt)
        self.assertIn("scale_n >= 150", txt)
        self.assertIn("COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE.json", txt)
        ev = EV.read_text()
        self.assertIn('"h2_n"', ev)
        self.assertIn("na_not_experimental_validation", ev)


if __name__ == "__main__":
    unittest.main()
