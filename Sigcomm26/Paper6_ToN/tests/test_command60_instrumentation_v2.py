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

"""Command60/61: Instrumentation V2 synthetic reconcile + overhead bound."""
import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO = artifact_root()
sys.path.insert(0, str(REPO))

from strategies.instrumentation_v2 import (  # noqa: E402
    DEFAULT_OVERHEAD_BOUND_FRAC,
    REQUIRED_DIRECT_RECORDS,
    InstrumentationV2,
    instrumentation_v2_enabled,
    synthetic_byte_accounting,
)

OUT = Path(__file__).resolve().parents[1]
CONTRACT = OUT / "contracts" / "MD2G_INSTRUMENTATION_V2.json"


def test_contract_required_keys_match_module() -> None:
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert c["required_direct_records"] == list(REQUIRED_DIRECT_RECORDS)
    assert c["implementation_status"] == "CODE_WIRED_SYNTHETIC_PASS_PENDING_RUNTIME_VALIDATE"
    assert c.get("final_scientific_freeze") is False


def test_env_gate_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGCOMM_INSTRUMENTATION_V2", raising=False)
    assert instrumentation_v2_enabled() is True
    monkeypatch.setenv("SIGCOMM_INSTRUMENTATION_V2", "0")
    assert instrumentation_v2_enabled() is False
    assert InstrumentationV2.enabled() is False


def test_synthetic_reconcile_and_required_keys() -> None:
    instr = synthetic_byte_accounting()
    rec = instr.reconcile_bytes()
    assert rec["ok"] is True
    assert rec["client_payload_bytes"] == 10_000
    assert rec["accounted_bytes"] == 10_000
    seen = set(instr.required_keys_seen())
    assert seen == set(REQUIRED_DIRECT_RECORDS)


def test_reconcile_fail_when_mismatch() -> None:
    instr = InstrumentationV2(cell="bad", user="u0")
    instr.record_client_payload_bytes(5000)
    instr.record_useful_rendered_bytes(1000)
    rec = instr.reconcile_bytes()
    assert rec["ok"] is False
    assert rec["delta_bytes"] == 4000


def test_write_jsonl_and_flush_cell() -> None:
    instr = synthetic_byte_accounting()
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "instr.jsonl"
        n = instr.write_jsonl(path)
        assert n == len(REQUIRED_DIRECT_RECORDS)
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == len(REQUIRED_DIRECT_RECORDS)
        fields = {json.loads(line)["field"] for line in lines}
        assert fields == set(REQUIRED_DIRECT_RECORDS)
        instr.record_client_payload_bytes(10_000)
        flushed = instr.flush_cell(path)
        assert flushed == 2  # one pending + summary trailer
        all_lines = path.read_text(encoding="utf-8").strip().splitlines()
        summary = json.loads(all_lines[-1])
        assert summary["field"] == "_cell_summary"
        assert summary["reconcile_bytes"]["ok"] is True


@pytest.mark.parametrize("n_events", [256, 1024])
def test_overhead_bound_preregistered(n_events: int) -> None:
    frac = InstrumentationV2.measure_record_overhead_fraction(n_events)
    assert frac < DEFAULT_OVERHEAD_BOUND_FRAC, (
        f"instrumentation overhead fraction {frac:.4f} >= bound {DEFAULT_OVERHEAD_BOUND_FRAC}"
    )


def test_dispatch_wiring_symbols_present() -> None:
    dispatch = REPO / "dispatch_strategy_enhanced_unified_Sigcomm.py"
    src = dispatch.read_text(encoding="utf-8")
    assert "from strategies.instrumentation_v2 import" in src
    assert "InstrumentationV2" in src
    assert "SIGCOMM_INSTRUMENTATION_V2" in src
    assert "instrumentation_v2_h" in src
