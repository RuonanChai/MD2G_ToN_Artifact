#!/usr/bin/env python3
"""Metric V4 contract schema PASS (pre-repair draft; not final freeze)."""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]


def main() -> int:
    c = json.loads((OUT / "contracts/MD2G_METRIC_CONTRACT_V4.json").read_text())
    f = json.loads((OUT / "state/MD2G_METRIC_FREEZE_V4.json").read_text())
    assert c["headline_qoe"]["forbid_final_rep_only"] is True
    assert c["headline_u_sys"]["forbid_fixed_strategy_class_credits"] is True
    assert c.get("scientific_status") == "METRIC_V4_CONTRACT_SCHEMA_PASS"
    assert c.get("final_scientific_freeze") is False
    assert c.get("pre_repair_draft_sha256")
    assert f.get("token") == "METRIC_V4_CONTRACT_SCHEMA_PASS"
    assert f.get("METRIC_V4_FINAL_FREEZE") is False
    assert f.get("FINAL_SCIENTIFIC_CELL_LAUNCH_ALLOWED") is False
    assert (OUT / "state/METRIC_V4_FINAL_FREEZE").read_text().strip().lower() == "false"
    print("PASS test_md2g_metrics_v4 (schema PASS / not final freeze)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
