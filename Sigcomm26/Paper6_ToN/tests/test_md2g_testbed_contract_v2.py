#!/usr/bin/env python3
"""Regression: Testbed V2 contract schema PASS (pre-repair draft; not final freeze)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
CTR = OUT / "contracts"
STATE = OUT / "state"


def main() -> int:
    cpath = CTR / "MD2G_TESTBED_CONTRACT_V2.json"
    fpath = STATE / "MD2G_TESTBED_FREEZE_V2.json"
    assert cpath.exists(), "missing V2 contract"
    assert fpath.exists(), "missing V2 freeze status"
    c = json.loads(cpath.read_text())
    f = json.loads(fpath.read_text())
    assert c.get("name") == "MD2G_TESTBED_CONTRACT_V2"
    assert c.get("scientific_python_sources_frozen") is True
    assert c.get("topology_rules", {}).get("no_metric_uplift_mode") is True
    assert len(c.get("hashed_sources") or {}) >= 5
    assert c.get("scientific_status") == "TESTBED_V2_CONTRACT_SCHEMA_PASS"
    assert c.get("final_scientific_freeze") is False
    assert c.get("pre_repair_draft") is True
    assert c.get("pre_repair_draft_sha256")
    assert f.get("token") == "TESTBED_V2_CONTRACT_SCHEMA_PASS"
    assert f.get("final_scientific_freeze") is False
    assert f.get("TESTBED_V2_FINAL_FREEZE") is False
    assert f.get("FINAL_SCIENTIFIC_CELL_LAUNCH_ALLOWED") is False
    assert f.get("SIGCOMM_SUBMISSION_READY") is False
    assert (STATE / "TESTBED_V2_FINAL_FREEZE").read_text().strip().lower() == "false"
    assert (STATE / "FINAL_SCIENTIFIC_CELL_LAUNCH_ALLOWED").read_text().strip().lower() == "false"
    print("PASS test_md2g_testbed_contract_v2 (schema PASS / not final freeze)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
