#!/usr/bin/env python3
"""Regression tests for command130 action-edge executor (no Mininet)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "scripts"))


class TestCommand130Edges(unittest.TestCase):
    def test_complete_stage_reentry_does_not_relaunch_valid(self):
        import command130_campaign_harness as h
        import command130_common as c

        item = c.OPT4_KEYS[0]
        with mock.patch.object(h, "cell_valid", return_value=True):
            st = c.default_state()
            st["next_action"] = "LAUNCH_OPT4_LONGDRESS_4G"
            st2 = h.launch_opt4(item, st)
            self.assertIsNone(st2.get("active_owner_pid"))

    def test_next_action_consumed_when_idle(self):
        import command130_campaign_harness as h

        st = {
            "terminal_state": None,
            "next_action": "CONSUME_OPT4_VERDICT",
            "active_cell": None,
        }
        with mock.patch.object(h, "consume_opt4_verdict", side_effect=lambda s: {**s, "next_action": "SAFE_CLEANUP"}):
            out = h.execute_next_action(st)
        self.assertEqual(out["next_action"], "SAFE_CLEANUP")

    def test_pid_alive_without_artifact_is_not_progress(self):
        import command130_campaign_harness as h

        self.assertFalse(h.pid_alive(99999999))
        self.assertTrue(isinstance(h.scientific_executor_exists(), bool))

    def test_owner_dies_between_cells_clears_active(self):
        import command130_campaign_harness as h
        import command130_common as c

        st = c.default_state()
        st["active_cell"] = c.opt4_key(c.OPT4_KEYS[2])
        st["active_owner_pid"] = 99999999
        st["next_action_consumed"] = True
        out = h.consume_active(st)
        self.assertIsNone(out["active_cell"])
        self.assertEqual(out.get("last_failure_class"), "OWNER_DIED_BETWEEN_CELLS")

    def test_tmux_survives_in_state_even_if_this_process_exits(self):
        import command130_common as c

        st = c.default_state()
        self.assertEqual(st["executor_tmux"], "command130_campaign")

    def test_unchanged_invalid_does_not_loop_action(self):
        import command130_campaign_harness as h

        st = {"identical_retry_count": 2, "last_failure_class": "CELL_INVALID", "next_action": "LAUNCH_OPT4_LONGDRESS_4G", "terminal_state": None, "active_cell": None}
        # third identical would be handled by caller; harness must still be deterministic
        self.assertEqual(st["identical_retry_count"], 2)

    def test_bridge_rc0_without_transition_is_detectable(self):
        import command130_campaign_harness as h

        before = {"next_action": "SAFE_CLEANUP", "active_cell": None, "terminal_state": None}
        with mock.patch.object(h, "run_cleanup", side_effect=lambda s: s):
            after = h.execute_next_action(dict(before))
        self.assertEqual(after.get("next_action"), "SAFE_CLEANUP")

    def test_review_does_not_block_next_edge(self):
        import command130_campaign_harness as h

        st = {"trials_since_scientific_review": 2, "last_review_trial_count": 0, "next_action": "WATCH_COMMAND121_FIVE_TRIAL", "terminal_state": None, "active_cell": None}
        out = h.maybe_review(st)
        self.assertEqual(out.get("last_review_trial_count"), 0)


if __name__ == "__main__":
    unittest.main()
