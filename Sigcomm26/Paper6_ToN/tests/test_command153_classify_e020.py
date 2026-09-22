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

"""E020: teardown r0.cmd waiting assert + missing CELL_VALIDITY is Class A exact-key."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "scripts"))
sys.path.insert(0, str(TON / "lib"))
from command153_classify_and_repair import classify_cell  # noqa: E402

CLUSTER = Path("str(artifact_root())/moq_cluster_Sigcomm.py")


class TestE020TeardownValidityGap(unittest.TestCase):
    def test_cluster_joins_pressure_thread_and_uses_host_cmd_safe(self):
        txt = CLUSTER.read_text()
        self.assertIn("def host_cmd_safe(", txt)
        self.assertIn("_press_thread.join", txt)
        self.assertIn("host_cmd_safe(r0, f\"cat /tmp/{TMP_PREFIX}r0.log 2>&1\")", txt)
        self.assertIn("if not _NESTED_COMPONENTS:", txt)
        self.assertIn("skip 2-track base/enhanced pgrep", txt)

    def test_classify_maps_waiting_assert_missing_validity_to_e020(self):
        with tempfile.TemporaryDirectory() as td:
            cell = Path(td)
            (cell / "CELL_AUDIT.json").write_text(
                json.dumps({"audit": {"reasons": ["cluster_CELL_VALIDITY.valid!=true"]}}) + "\n"
            )
            (cell / "cell_stdout.log").write_text(
                "运行实验 120 秒（等待数据流传输和perf.csv记录）...\n"
                "[COMPONENT-PLAN] seq=0 open=['b0']\n"
                "Traceback (most recent call last):\n"
                "    r0_log = r0.cmd(f\"cat /tmp/{TMP_PREFIX}r0.log 2>&1\")\n"
                "    assert self.shell and not self.waiting\n"
                "AssertionError\n"
            )
            rec = classify_cell("c148can_longdress_default_mix_u60_RULE_COMPONENT_s151", cell)
            self.assertEqual(rec["class"], "A_RUNTIME_INSTRUMENTATION_DEFECT")
            self.assertEqual(rec["failure_id"], "E020_TEARDOWN_R0_CMD_WAITING_SKIPS_CELL_VALIDITY")
            self.assertTrue(rec["reuse_certified_fix"])

    def test_does_not_reauthorize_consumed_same_key_failure(self):
        from command153_classify_and_repair import _already_consumed_exact_key
        import command153_classify_and_repair as mod

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state" / "COMMAND153_EXACT_KEY_RERUN.json"
            p.parent.mkdir(parents=True)
            p.write_text(
                json.dumps(
                    {
                        "status": "CONSUMED",
                        "affected_key": "c153dash_redandblack_4g_u20_groot_s151",
                        "failure_id": "E021_DASH_H2_MISSING_COMMAND151_PRESSURE",
                        "n_applied": 1,
                    }
                )
                + "\n"
            )
            old = mod.REPO
            try:
                mod.REPO = Path(td)
                self.assertTrue(
                    _already_consumed_exact_key(
                        "c153dash_redandblack_4g_u20_groot_s151",
                        "E021_DASH_H2_MISSING_COMMAND151_PRESSURE",
                    )
                )
                self.assertFalse(
                    _already_consumed_exact_key(
                        "c153dash_redandblack_4g_u20_groot_s151",
                        "E020_TEARDOWN_R0_CMD_WAITING_SKIPS_CELL_VALIDITY",
                    )
                )
            finally:
                mod.REPO = old


if __name__ == "__main__":
    unittest.main()
