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

import unittest
from pathlib import Path

TON = ton_root()


class TestCommand153CorpusClaimAudit(unittest.TestCase):
    def test_na_surfaces_excluded_from_ton_conjunction(self):
        import sys

        sys.path.insert(0, str(TON / "lib"))
        from command153_corpus_claim_audit import (  # noqa: E402
            corpus_claim_verdict,
            report_surface,
            ton_conjunction_pass,
        )

        gpu = report_surface("GPU_provenance_PASS", n=0)
        rgb = report_surface("no_black_blue_solid_color_visual_failure", n=0)
        http = report_surface("valid_HTTP_206_range", n=0)
        self.assertEqual(gpu["status"], "N/A")
        self.assertEqual(gpu["contract_status"], "NOT_IN_CONTRACT")
        self.assertFalse(gpu["in_ton_conjunction"])
        self.assertEqual(rgb["status"], "N/A")
        self.assertEqual(http["status"], "N/A")
        checklist = {
            "validator_PASS": {"status": "PASS"},
            "DATA_SANITY_finite_U_Ro_Rq_Rb_Bshared_Bunicast": {"status": "PASS"},
            "paper_facing_metrics_complete_for_frozen_ToN_contract": {"status": "PASS"},
            "finite_throughput_latency_QoE_system_utility": {"status": "PASS_ON_CONTRACTED_U"},
            "GPU_provenance_PASS": gpu,
            "no_black_blue_solid_color_visual_failure": rgb,
            "valid_HTTP_206_range": http,
        }
        self.assertTrue(ton_conjunction_pass(checklist))
        v = corpus_claim_verdict(loot_sealed=True, maindev_n=144, loot_frozen=False, ton_conjunction_ok=True)
        self.assertEqual(v, "INCONCLUSIVE")
        v2 = corpus_claim_verdict(loot_sealed=True, maindev_n=945, loot_frozen=False, ton_conjunction_ok=True)
        self.assertEqual(v2, "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
