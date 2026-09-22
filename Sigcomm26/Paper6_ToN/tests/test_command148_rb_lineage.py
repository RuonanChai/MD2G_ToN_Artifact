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

"""Rb placeholder lineage: pressure ≠ volume; zero with traffic is not a hide-bytes bug."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command148_rb_lineage import rb_lineage  # noqa: E402

PERF_H = (
    "timestamp,user_id,network_type,device_score,base_version,enhanced_level,subscription_type,"
    "ttfb_base_ms,ttfb_enh1_ms,ttfb_enh2_ms,ttfb_enh3_ms,delay_ms,"
    "stall_count,stall_count_inc,stall_total_sec,rx_bytes,"
    "buffer_level_sec,rep_id,qoe,reward_R_o,reward_R_q,reward_R_b,reward_final,"
    "grouping_id,grouping_efficiency,load_balance_jfi,decision_step,"
    "quality_level,quality_score,"
    "cpu_bottleneck_node_percent,cpu_relay_process_percent,cpu_controller_process_percent,"
    "cpu_dash_server_process_percent,cpu_system_percent,retransmission_count\n"
)


def _write_perf(cell: Path, hid: int, rb: float, rx: int) -> None:
    row = (
        f"1.0,{hid},4g,0.5,1,0,component,0,0,0,0,0,0,0,0.0,{rx},"
        f"0.0,2,0.5,0,0.5,{rb},0.5,0,0,1,0,0,0.5,0,0,0,0,0,0\n"
    )
    p = cell / f"client_h{hid}_perf.csv"
    p.write_text(PERF_H + row)


def _write_receipt(cell: Path, hid: int, dump: int) -> None:
    rec = {
        "host_id": hid,
        "target_state": "Rep2",
        "decoded_state": "Rep2",
        "dump_bytes": {"b0": dump, "db1": dump, "db2": 0, "e1": 0, "e2": 0},
        "Rq": 0.5,
        "content": "redandblack",
    }
    (cell / f"client_h{hid}_COMPONENT_RECEIPT.jsonl").write_text(json.dumps(rec) + "\n")


class TestRbLineage(unittest.TestCase):
    def test_placeholder_with_traffic_is_not_volume_bug(self):
        with tempfile.TemporaryDirectory() as td:
            cell = Path(td)
            _write_perf(cell, 1, 0.0, 9_000_000)
            _write_receipt(cell, 1, 100_000)
            got = rb_lineage(cell, {"Rb": 0.0, "Ro_component": 0.95, "B_shared": 155_000_000, "B_unicast": 3_000_000_000})
            self.assertTrue(got["pass"])
            self.assertEqual(got["class"], "RB_RESERVED_PHYSICAL_PRESSURE_PLACEHOLDER_ZERO")
            self.assertTrue(got["physical_traffic_present"])
            self.assertTrue(got["paper_U_is_Rb0_projection"])
            self.assertEqual(got["situation"], "A_UNIMPLEMENTED")

    def test_zero_without_traffic_fails(self):
        with tempfile.TemporaryDirectory() as td:
            cell = Path(td)
            _write_perf(cell, 1, 0.0, 0)
            _write_receipt(cell, 1, 0)
            got = rb_lineage(cell, {"Rb": 0.0, "Ro_component": 0.0, "B_shared": 0, "B_unicast": 0})
            self.assertFalse(got["pass"])
            self.assertEqual(got["class"], "RB_PLACEHOLDER_ZERO_NO_TRAFFIC")

    def test_pressure_timeseries_is_computed(self):
        with tempfile.TemporaryDirectory() as td:
            cell = Path(td)
            _write_perf(cell, 1, 0.0, 9_000_000)
            _write_receipt(cell, 1, 100_000)
            cap = 10e6
            rows = [{"t": float(i), "tx_bytes": int(i * 1.25e6), "rx_bytes": 0, "capacity_bps": cap} for i in range(8)]
            (cell / "PHYSICAL_PRESSURE_TIMESERIES.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            got = rb_lineage(cell, {"Rb": 0.99, "Ro_component": 0.4, "B_shared": 155_000_000, "B_unicast": 3_000_000_000})
            self.assertTrue(got["pass"])
            self.assertEqual(got["class"], "RB_PHYSICAL_PRESSURE_COMPUTED")
            self.assertTrue(got["physical_root_link_pressure_computed"])
            self.assertFalse(got["paper_U_is_Rb0_projection"])
        with tempfile.TemporaryDirectory() as td:
            cell = Path(td)
            _write_perf(cell, 1, 0.95, 9_000_000)
            _write_receipt(cell, 1, 100_000)
            got = rb_lineage(cell, {"Rb": 0.95, "Ro_component": 0.95, "B_shared": 155_000_000, "B_unicast": 3_000_000_000})
            self.assertFalse(got["pass"])
            self.assertEqual(got["class"], "RB_CONFLATED_WITH_RO_OR_VOLUME")


if __name__ == "__main__":
    unittest.main()
