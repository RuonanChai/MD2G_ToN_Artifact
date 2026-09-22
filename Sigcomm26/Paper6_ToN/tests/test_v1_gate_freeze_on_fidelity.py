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

"""command153: V1 gate must freeze DEV after 120 even if MD2G loses U."""
import unittest
from pathlib import Path

TON = ton_root()
GATE = TON / "scripts" / "command148_canary_v1_gate.py"
ORCH = TON / "scripts" / "command152_production_supervisor.py"


class TestV1GateFreezesOnFidelity(unittest.TestCase):
    def test_gate_freezes_when_fidelity_even_if_not_v1(self):
        txt = GATE.read_text()
        self.assertIn("if not fidelity:", txt)
        self.assertIn("COMMAND148_DEV_CANDIDATE_FREEZE", txt)
        self.assertIn("losing U/low Rq does not block DEV", txt)
        self.assertNotIn("freezeable = bool(fidelity and student_ok", txt)

    def test_orch_canary_not_stopped_by_claim_limited_alone(self):
        txt = ORCH.read_text()
        self.assertIn("not exists(\"COMMAND148_DEV_CANDIDATE_FREEZE\")", txt)
        self.assertIn("not exists(\"COMMAND148_MAINDEV_COMPLETE\")", txt)
        # CLAIM_LIMITED must not be conjoined with the canary-continue gate.
        canary_gate = txt.split("COMMAND148_CANARY120_RBV1", 1)[0]
        self.assertNotIn(
            "and not exists(\"COMMAND148_COMPONENT_CONTROLLER_CLAIM_LIMITED\")",
            canary_gate,
        )


if __name__ == "__main__":
    unittest.main()
