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

"""command153 E018: live canary reporters must not read pre-Rb art after release."""
import unittest
from pathlib import Path

TON = ton_root()
REPO = artifact_root()
sys_path_inserted = False


class TestCanaryRbv1Art(unittest.TestCase):
    def test_helper_prefers_rbv1_after_release(self):
        import sys

        sys.path.insert(0, str(TON / "lib"))
        from command147_io import canary_rbv1_art  # noqa: E402

        rel = REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_RELEASE.json"
        self.assertTrue(rel.is_file())
        art = canary_rbv1_art()
        self.assertTrue(str(art).endswith("command148_canary120_rbv1"))

    def test_five_cell_and_block_review_call_helper(self):
        five = (TON / "scripts" / "command148_five_cell_report.py").read_text()
        blk = (TON / "scripts" / "command148_canary_block_review.py").read_text()
        self.assertIn("canary_rbv1_art()", five)
        self.assertIn("pre_rb_excluded", five)
        self.assertIn("paper_U_is_Rb0_projection", five)
        self.assertIn("canary_rbv1_art()", blk)
        self.assertIn("pre_rb_excluded", blk)
        self.assertNotIn(
            'ART = TON / "artifacts" / "command148_canary120"\nREV',
            five,
        )


if __name__ == "__main__":
    unittest.main()
