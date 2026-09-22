#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OUT / "instrumentation"))
from md2g_instr_v1 import InstrEvent, InstrSink, synthetic_byte_flow  # noqa: E402


def fail(m):
    print("FAIL:", m, file=sys.stderr)
    raise SystemExit(1)


def main():
    c = json.loads((OUT / "contracts/MD2G_INSTRUMENTATION_V1.json").read_text())
    for ch in (
        "source_publisher_bytes",
        "rendered_useful_bytes",
        "stale_bytes",
        "duplicate_bytes",
        "cancellation_latency",
    ):
        if ch not in c["channels"]:
            fail(f"missing channel {ch}")
    flow = synthetic_byte_flow(2, 1000)
    if flow["fanout_ratio"] != 2.0:
        fail("synthetic unicast fanout expected 2")
    # sink roundtrip
    p = OUT / "audits/instr_synth_test.ndjson"
    if p.exists():
        p.unlink()
    sink = InstrSink(p)
    sink.emit(
        InstrEvent(
            run_id="synth",
            cell_id="c0",
            user_id="u1",
            rep_id="3",
            strategy="md2g",
            channel="rendered_useful_bytes",
            value=1000,
            unit="bytes",
        )
    )
    sink.close()
    line = json.loads(p.read_text().splitlines()[0])
    assert line["channel"] == "rendered_useful_bytes"
    print("PASS: MD2G_INSTRUMENTATION_V1 synthetic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
