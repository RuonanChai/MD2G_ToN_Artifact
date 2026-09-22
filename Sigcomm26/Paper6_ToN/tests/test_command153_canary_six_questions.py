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

"""Mechanical six-question W/T/L + E020 post-repair counters."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command153_canary_six_questions import (  # noqa: E402
    NOISE,
    advantage_source,
    bootstrap_mean_ci,
    build_report,
    completion_label,
    e020_audit_cells,
    paired_blocks,
    wtl,
)


def _row(content, net, users, seed, strat, U, Rq=0.5, Ro=0.8, Rb=0.1, weak=0.3, **extra):
    m = {
        "content": content,
        "network": net,
        "users": users,
        "seed": seed,
        "strategy": strat,
        "U": U,
        "Rq": Rq,
        "Ro_component": Ro,
        "Rb": Rb,
        "weak_user_Rq": weak,
        "Q_norm_frozen": {f"Rep{i}": i / 9.0 for i in range(1, 10)},
        "target_state_occupancy": {f"Rep{i}": 0.0 for i in range(1, 10)},
        "actual_decoded_state_occupancy": {f"Rep{i}": 0.0 for i in range(1, 10)},
        "component_completion_fraction": {
            "e1": {"fraction": 0.9},
            "e2": {"fraction": 0.9},
        },
    }
    m["target_state_occupancy"]["Rep9"] = 1.0
    m["actual_decoded_state_occupancy"]["Rep9"] = 0.8
    m.update(extra)
    return m


def _block(content, net, users, seed, md_u, hv, cl, ru, uni=0.14, **kw):
    recs = {
        "MD2G_COMPONENT": _row(content, net, users, seed, "MD2G_COMPONENT", md_u, **kw),
        "HV3_COMPONENT": _row(content, net, users, seed, "HV3_COMPONENT", hv, **kw),
        "CLUSTERING_COMPONENT": _row(content, net, users, seed, "CLUSTERING_COMPONENT", cl, **kw),
        "RULE_COMPONENT": _row(content, net, users, seed, "RULE_COMPONENT", ru, **kw),
        "MOQ_UNICAST_COMPONENT": _row(content, net, users, seed, "MOQ_UNICAST_COMPONENT", uni, **kw),
    }
    return recs


class TestSixQuestions(unittest.TestCase):
    def test_wtl_noise_band(self):
        self.assertEqual(wtl([0.10, 0.01, -0.10]), {"W": 1, "T": 1, "L": 1, "noise_abs": NOISE, "n": 3})

    def test_bootstrap_seed_frozen(self):
        a = bootstrap_mean_ci([0.1, -0.05, 0.2], n_boot=200, seed=153)
        b = bootstrap_mean_ci([0.1, -0.05, 0.2], n_boot=200, seed=153)
        self.assertEqual(a["ci95_lo"], b["ci95_lo"])
        self.assertEqual(a["ci95_hi"], b["ci95_hi"])
        self.assertAlmostEqual(a["mean"], (0.1 - 0.05 + 0.2) / 3)

    def test_matched_delta_vs_strongest_not_mean_rank(self):
        blocks = {
            "rb_4g_u60_s151": _block("redandblack", "4g", 60, 151, 0.70, 0.50, 0.55, 0.40),
            "rb_4g_u20_s151": _block("redandblack", "4g", 20, 151, 0.40, 0.55, 0.60, 0.50),
        }
        pairs = paired_blocks(blocks)
        self.assertEqual(len(pairs), 2)
        u60 = [p for p in pairs if p["users"] == 60][0]
        u20 = [p for p in pairs if p["users"] == 20][0]
        self.assertEqual(u60["strongest_same_substrate"], "CLUSTERING_COMPONENT")
        self.assertAlmostEqual(u60["delta_U"], 0.15)
        self.assertEqual(u20["strongest_same_substrate"], "CLUSTERING_COMPONENT")
        self.assertAlmostEqual(u20["delta_U"], -0.20)

    def test_crossover_and_ld_not_rb_special(self):
        blocks = {}
        for seed in (151, 152):
            blocks[f"rb_4g_u20_s{seed}"] = _block("redandblack", "4g", 20, seed, 0.40, 0.55, 0.50, 0.48)
            blocks[f"rb_4g_u60_s{seed}"] = _block("redandblack", "4g", 60, seed, 0.70, 0.50, 0.55, 0.52)
            blocks[f"ld_4g_u20_s{seed}"] = _block("longdress", "4g", 20, seed, 0.42, 0.56, 0.51, 0.49)
            blocks[f"ld_4g_u60_s{seed}"] = _block("longdress", "4g", 60, seed, 0.72, 0.51, 0.54, 0.50)
        pairs = paired_blocks(blocks)
        rows = [r for recs in blocks.values() for r in recs.values()]
        body = build_report(rows, pairs, {"n_post_E020_completed": 0}, n_completed=8, final=False, n_boot=50)
        self.assertTrue(body["Q2_u20_vs_u60_crossover"]["high_concurrency_crossover_still_holds_under_real_Rb"])
        self.assertTrue(body["Q3_content_direction"]["u60_direction_consistent"])
        self.assertFalse(body["Q3_content_direction"]["rb_u60_advantage_is_content_special_case"])
        self.assertTrue(body["MOQ_UNICAST_is_not_primary_algorithm_evidence"])

    def test_rb_u60_special_when_ld_does_not_win(self):
        blocks = {
            "rb_4g_u60_s151": _block("redandblack", "4g", 60, 151, 0.70, 0.50, 0.55, 0.50),
            "ld_4g_u60_s151": _block("longdress", "4g", 60, 151, 0.50, 0.55, 0.52, 0.51),
        }
        pairs = paired_blocks(blocks)
        rows = [r for recs in blocks.values() for r in recs.values()]
        body = build_report(rows, pairs, {"n_post_E020_completed": 0}, n_completed=2, final=False, n_boot=50)
        self.assertTrue(body["Q3_content_direction"]["rb_u60_advantage_is_content_special_case"])
        self.assertFalse(body["Q3_content_direction"]["u60_direction_consistent"])

    def test_advantage_rq_paying_rb(self):
        src = advantage_source(
            {
                "mean_delta_Rq": 0.20,
                "mean_delta_Ro": 0.01,
                "mean_delta_Rb": 0.10,
                "delta_U": {"mean": 0.10},
            }
        )
        self.assertEqual(src["label"], "Rq_GAIN_PAYING_HIGHER_Rb")
        self.assertGreater(src["contrib_to_delta_U"]["Rq"], src["contrib_to_delta_U"]["Ro"])

    def test_completion_labels(self):
        self.assertEqual(completion_label(0.20, 0.50), "SYSTEMATIC_OVER_AGGRESSIVE")
        self.assertEqual(completion_label(0.20, 0.95), "AMBITIOUS_BUT_MOSTLY_COMPLETED")
        self.assertEqual(completion_label(-0.08, 0.90), "CONSERVATIVE_OR_DECODE_ABOVE_TARGET")
        self.assertEqual(completion_label(0.01, 0.90), "NO_SYSTEMATIC_BIAS_DETECTED")

    def test_e020_counts_post_cutoff_only(self):
        with tempfile.TemporaryDirectory() as td:
            art = Path(td)
            pre = art / "pre"
            post_ok = art / "post_ok"
            post_bad = art / "post_bad"
            live = art / "live"
            for p in (pre, post_ok, post_bad, live):
                p.mkdir()
            (pre / "CELL_DONE.json").write_text(json.dumps({"ts": "2026-08-20T12:00:00+00:00"}) + "\n")
            (pre / "CELL_VALIDITY.json").write_text("{}\n")
            (pre / "PHYSICAL_PRESSURE_TIMESERIES.jsonl").write_text("{}\n{}\n")
            (pre / "CELL_METRICS.json").write_text(json.dumps({"physical_pressure": {"n_intervals": 100}}) + "\n")
            (post_ok / "CELL_DONE.json").write_text(json.dumps({"ts": "2026-08-20T13:44:00+00:00"}) + "\n")
            (post_ok / "CELL_VALIDITY.json").write_text("{}\n")
            (post_ok / "PHYSICAL_PRESSURE_TIMESERIES.jsonl").write_text("{}\n{}\n")
            (post_ok / "CELL_METRICS.json").write_text(json.dumps({"physical_pressure": {"n_intervals": 118}}) + "\n")
            (post_ok / "cell_stdout.log").write_text("ok\n")
            (post_bad / "CELL_DONE.json").write_text(json.dumps({"ts": "2026-08-20T13:50:00+00:00"}) + "\n")
            (post_bad / "cell_stdout.log").write_text("assert self.shell and not self.waiting\n")
            rec = e020_audit_cells(
                art,
                ["pre", "post_ok", "post_bad", "live"],
                cutoff=datetime(2026, 8, 20, 13, 40, 25, tzinfo=timezone.utc),
            )
            self.assertEqual(rec["mininet_waiting_assertion_count_post_E020"], 1)
            self.assertEqual(rec["pressure_samples_missing_post_E020"], 1)
            self.assertEqual(rec["CELL_VALIDITY_missing_post_E020"], 1)
            self.assertEqual(rec["n_post_E020_completed"], 2)
            self.assertEqual(rec["n_skipped_no_CELL_DONE_live_or_incomplete"], 1)


if __name__ == "__main__":
    unittest.main()
