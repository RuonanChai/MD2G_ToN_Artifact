#!/usr/bin/env python3
"""H5 Rb gain without physical-byte/subscribe explanation must fail closed."""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "scripts"))
from command140_h5_mechanism import audit, paper_u, reconcile  # noqa: E402

HDR = [
    "timestamp", "user_id", "network_type", "device_score", "base_version",
    "enhanced_level", "subscription_type", "ttfb_base_ms", "ttfb_enh1_ms",
    "ttfb_enh2_ms", "ttfb_enh3_ms", "delay_ms", "stall_count", "stall_count_inc",
    "stall_total_sec", "rx_bytes", "buffer_level_sec", "rep_id", "qoe",
    "reward_R_o", "reward_R_q", "reward_R_b", "reward_final", "grouping_id",
    "grouping_efficiency", "load_balance_jfi", "decision_step", "quality_level",
    "quality_score", "cpu_bottleneck_node_percent", "cpu_relay_process_percent",
    "cpu_controller_process_percent", "cpu_dash_server_process_percent",
    "cpu_system_percent", "retransmission_count", "payload_ttfb_ms",
    "media_covered_sec",
]


def _write_perf(path: Path, *, rb: float, rq: float, ro: float, rx_end: int, enh: str, stall: float, ttfb_e1: float = 0.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HDR)
        w.writeheader()
        for i in range(0, 50):
            row = {k: "0" for k in HDR}
            row.update(
                {
                    "timestamp": str(1000.0 + i),
                    "user_id": "1",
                    "base_version": "3",
                    "enhanced_level": enh,
                    "subscription_type": "B3" if enh == "0" else "B3E1",
                    "ttfb_enh1_ms": f"{ttfb_e1:.2f}",
                    "stall_total_sec": f"{stall:.3f}" if i == 49 else "0.000",
                    "rx_bytes": str(int(rx_end * i / 49.0)),
                    "rep_id": "3" if enh == "0" else "8",
                    "reward_R_o": f"{ro:.4f}",
                    "reward_R_q": f"{rq:.4f}",
                    "reward_R_b": f"{rb:.4f}",
                    "reward_final": f"{paper_u(ro, rq, rb):.4f}",
                    "grouping_id": "1",
                    "grouping_efficiency": f"{ro:.4f}",
                    "media_covered_sec": f"{max(0.0, i - 5):.3f}",
                }
            )
            w.writerow(row)


def _cell(root: Path, kind: str, content: str, seed: int, strat: str) -> Path:
    d = root / content / "4g" / "users_20" / strat / f"seed_{seed}"
    d.mkdir(parents=True, exist_ok=True)
    return d


class TestH5Mechanism(unittest.TestCase):
    def test_rb_drop_without_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            h5r, canr = tmp / "h5", tmp / "can"
            can = _cell(canr, "can", "redandblack", 51, "md2g_layered_final_dev")
            hv = _cell(canr, "hv", "redandblack", 51, "hv3_layered")
            h5 = _cell(h5r, "h5", "redandblack", 51, "md2g_layered_final_dev")
            _write_perf(can / "client_h1_perf.csv", rb=0.57, rq=0.69, ro=0.85, rx_end=5_000_000, enh="0", stall=1.2)
            _write_perf(hv / "client_h1_perf.csv", rb=0.57, rq=0.69, ro=0.85, rx_end=5_000_000, enh="0", stall=1.2)
            _write_perf(h5 / "client_h1_perf.csv", rb=0.40, rq=0.68, ro=0.86, rx_end=5_000_000, enh="0", stall=1.5)
            u_can = paper_u(0.85, 0.69, 0.57)
            u_h5 = paper_u(0.86, 0.68, 0.40)
            (can / "CELL_DONE.json").write_text(json.dumps({"valid": True, "score": {"U": u_can}}))
            (hv / "CELL_DONE.json").write_text(json.dumps({"valid": True, "score": {"U": u_can}}))
            (h5 / "CELL_DONE.json").write_text(json.dumps({"valid": True, "score": {"U": u_h5}}))
            rec = reconcile("redandblack", 51, h5_root=h5r, can_root=canr)
            self.assertTrue(rec["fail_closed_rb_without_bytes"])
            self.assertEqual(rec["verdict"], "FAIL_CLOSED_RB_WITHOUT_BYTES")
            self.assertFalse(rec["byte_explained"])

    def test_rb_drop_with_enh_bytes_is_mixed_not_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            h5r, canr = tmp / "h5", tmp / "can"
            can = _cell(canr, "can", "redandblack", 51, "md2g_layered_final_dev")
            hv = _cell(canr, "hv", "redandblack", 51, "hv3_layered")
            h5 = _cell(h5r, "h5", "redandblack", 51, "md2g_layered_final_dev")
            _write_perf(can / "client_h1_perf.csv", rb=0.57, rq=0.69, ro=0.85, rx_end=5_000_000, enh="0", stall=1.2)
            _write_perf(hv / "client_h1_perf.csv", rb=0.57, rq=0.69, ro=0.85, rx_end=5_000_000, enh="0", stall=1.2)
            _write_perf(
                h5 / "client_h1_perf.csv",
                rb=0.40, rq=0.685, ro=0.864, rx_end=11_000_000, enh="1", stall=1.5, ttfb_e1=40.0,
            )
            (h5 / "client_h1_gst_enh1.log").write_text(
                "INFO moq_sub: 开始订阅 broadcast=base3_enh1_only track=video0\n"
                "INFO moq_lite::lite::subscriber: subscribe started id=1 broadcast=base3_enh1_only track=video0\n"
            )
            u_can = paper_u(0.85, 0.69, 0.57)
            u_h5 = paper_u(0.864, 0.685, 0.40)
            (can / "CELL_DONE.json").write_text(json.dumps({"valid": True, "score": {"U": u_can}}))
            (hv / "CELL_DONE.json").write_text(json.dumps({"valid": True, "score": {"U": u_can}}))
            (h5 / "CELL_DONE.json").write_text(json.dumps({"valid": True, "score": {"U": u_h5}}))
            rec = reconcile("redandblack", 51, h5_root=h5r, can_root=canr)
            self.assertFalse(rec["fail_closed_rb_without_bytes"])
            self.assertTrue(rec["byte_explained"])
            self.assertTrue(rec["promising"])
            self.assertEqual(rec["verdict"], "PROMISING_BUT_MECHANISM_MIXED")

    def test_seed52_blocked_until_both_seed51_promising(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            h5r, canr = tmp / "h5", tmp / "can"
            for content in ("redandblack", "longdress"):
                can = _cell(canr, "can", content, 51, "md2g_layered_final_dev")
                hv = _cell(canr, "hv", content, 51, "hv3_layered")
                h5 = _cell(h5r, "h5", content, 51, "md2g_layered_final_dev")
                _write_perf(can / "client_h1_perf.csv", rb=0.57, rq=0.69, ro=0.85, rx_end=5_000_000, enh="0", stall=1.2)
                _write_perf(hv / "client_h1_perf.csv", rb=0.57, rq=0.69, ro=0.85, rx_end=5_000_000, enh="0", stall=1.2)
                _write_perf(h5 / "client_h1_perf.csv", rb=0.57, rq=0.69, ro=0.85, rx_end=5_000_000, enh="0", stall=1.2)
                u = paper_u(0.85, 0.69, 0.57)
                (can / "CELL_DONE.json").write_text(json.dumps({"valid": True, "score": {"U": u}}))
                (hv / "CELL_DONE.json").write_text(json.dumps({"valid": True, "score": {"U": u}}))
                (h5 / "CELL_DONE.json").write_text(json.dumps({"valid": True, "score": {"U": u}}))
            body = audit(h5_root=h5r, can_root=canr, write=False)
            self.assertFalse(body["allow_seed52"])
            self.assertFalse(body["seed51_both_promising"])


if __name__ == "__main__":
    unittest.main()
