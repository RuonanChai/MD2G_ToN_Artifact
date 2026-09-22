#!/usr/bin/env python3
"""Instrumentation V2 contract schema PASS (not runtime-validated)."""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]


def main() -> int:
    c = json.loads((OUT / "contracts/MD2G_INSTRUMENTATION_V2.json").read_text())
    s = json.loads((OUT / "state/MD2G_INSTRUMENTATION_V2_STATUS.json").read_text())
    assert len(c["required_direct_records"]) >= 10
    assert c.get("scientific_status") == "INSTRUMENTATION_V2_CONTRACT_SCHEMA_PASS"
    assert c.get("final_scientific_freeze") is False
    assert s.get("INSTRUMENTATION_V2_RUNTIME_VALIDATED") is False
    assert s.get("token") == "INSTRUMENTATION_V2_CONTRACT_SCHEMA_PASS"
    assert (OUT / "state/INSTRUMENTATION_V2_RUNTIME_VALIDATED").read_text().strip().lower() == "false"
    print("PASS test_md2g_instrumentation_v2 (schema PASS / not runtime validated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
