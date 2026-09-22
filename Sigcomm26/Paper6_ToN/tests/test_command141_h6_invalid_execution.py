#!/usr/bin/env python3
"""Invalid H6-C CELL_DONE must not look done or switch to H6-B."""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "scripts"))
import command140_o1_run_next as o1  # noqa: E402


def _write_perf(d: Path, host: int, n_rows: int, t0: float = 1000.0, dt: float = 1.0) -> None:
    p = d / f"client_h{host}_perf.csv"
    fields = ["timestamp", "reward_R_o", "reward_R_q", "reward_R_b"]
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i in range(n_rows):
            w.writerow(
                {
                    "timestamp": f"{t0 + i * dt:.2f}",
                    "reward_R_o": "0.2",
                    "reward_R_q": "0.5",
                    "reward_R_b": "0.3",
                }
            )


class TestH6InvalidExecution(unittest.TestCase):
    def test_sparse_header_only_cell_is_not_execution_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "CELL_DONE.json").write_text(
                json.dumps({"rc": -15, "valid": False, "score": {"ok": True, "n": 10, "expected": 20, "U": 0.56}})
                + "\n"
            )
            for i in range(1, 11):
                _write_perf(d, i, 6)
            for i in range(11, 21):
                _write_perf(d, i, 0)
            self.assertFalse(o1.h6_execution_valid(d))

    def test_invalid_cell_done_is_not_already_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "CELL_DONE.json").write_text(json.dumps({"rc": -15, "score": {"ok": True, "n": 10, "expected": 20}}) + "\n")
            for i in range(1, 21):
                _write_perf(d, i, 0 if i > 10 else 6)
            self.assertFalse(o1.h6_execution_valid(d))
            self.assertNotEqual(
                "H6_ALREADY_DONE",
                "H6_ALREADY_DONE" if o1.h6_execution_valid(d) else "H6_INVALID_NEEDS_RERUN",
            )

    def test_sidecar_blocks_scientific_validity(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "CELL_DONE.json").write_text(json.dumps({"rc": 0, "score": {"ok": True, "n": 20, "expected": 20}}) + "\n")
            for i in range(1, 21):
                _write_perf(d, i, 100)
            self.assertTrue(o1.h6_execution_valid(d))
            (d / "UNAUTHORIZED_PREMATURE_LAUNCH.json").write_text("{}\n")
            self.assertFalse(o1.h6_execution_valid(d))

    def test_setup_stall_sidecar_blocks_scientific_validity(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "CELL_DONE.json").write_text(json.dumps({"rc": -15, "score": {"ok": False, "n": 0, "expected": 20}}) + "\n")
            (d / "SETUP_STALL.json").write_text("{}\n")
            self.assertFalse(o1.h6_execution_valid(d))

    def test_h6d_review_prefers_valid_rerun1_over_invalid_seed51(self):
        from command141_h6d_review import cell_dir, review_h6d_rb51

        primary = cell_dir("H6D", "redandblack", 51)
        rerun = cell_dir("H6D", "redandblack", 51, attempt="rerun1")
        self.assertFalse(o1.h6_execution_valid(primary))
        self.assertTrue(o1.h6_execution_valid(rerun))
        rev = review_h6d_rb51()
        self.assertEqual(rev["cell"], str(rerun))
        self.assertNotEqual(rev.get("verdict"), "NOT_INTERPRETED_INVALID_OR_MISSING")
        self.assertTrue(rev.get("interpret"))

    def test_full_duration_complete_cell_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "CELL_DONE.json").write_text(json.dumps({"rc": 0, "score": {"ok": True, "n": 20, "expected": 20}}) + "\n")
            for i in range(1, 21):
                _write_perf(d, i, 120)
            self.assertTrue(o1.h6_execution_valid(d))


if __name__ == "__main__":
    unittest.main()
