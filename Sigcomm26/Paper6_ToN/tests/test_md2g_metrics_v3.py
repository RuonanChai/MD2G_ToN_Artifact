#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
CTR = OUT / "contracts"
STATE = OUT / "state"


def fail(m):
    print("FAIL:", m, file=sys.stderr)
    raise SystemExit(1)


def main():
    m = json.loads((CTR / "MD2G_METRIC_CONTRACT_V3.json").read_text())
    f = json.loads((STATE / "MD2G_METRIC_FREEZE_V3.json").read_text())
    if not f.get("frozen"):
        fail("metric not frozen")
    if m.get("contract_sha256") != f.get("contract_sha256"):
        fail("sha mismatch")
    if m["objective_qoe"].get("not_mos") is not True:
        fail("must declare not MOS")
    if "0.7×RX useful-byte efficiency" not in m["system_utility"]["exclude_until_direct_instrumentation"]:
        fail("must exclude 0.7×RX")
    if m["system_utility"]["headline_formula"].find("QoE_abs") < 0:
        fail("headline must be QoE-based without proxy efficiency")
    assert "startup_TTFB" in m["delay"]
    assert "steady_state_delivery_interval" in m["delay"]
    assert m["failure_denominator"]["rule"].startswith("all launched")
    print("PASS: MD2G_METRIC_CONTRACT_V3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
