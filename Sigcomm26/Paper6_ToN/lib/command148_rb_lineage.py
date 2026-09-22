"""Rb=0 lineage. Pressure term, not volume. Does not retune strategies."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from command151_physical_pressure import SAMPLES, summarize_cell

TRACKS = ("b0", "db1", "db2", "e1", "e2")

RB_CONTRACT = (
    "normalized actual bottleneck/network pressure from physical link counters "
    "including protocol overhead under one frozen definition"
)
RB_NOT = "not normalized bytes transmitted; not 1-Bu/target; not a function of Ro_component"


def _unique_perf(cell: Path, field: str) -> list[float]:
    vals: set[float] = set()
    for pf in cell.glob("client_h*_perf.csv"):
        with pf.open(newline="") as f:
            for row in csv.DictReader(f):
                try:
                    vals.add(float(row.get(field) or 0.0))
                except (TypeError, ValueError):
                    continue
    return sorted(vals)


def _last_rx_sum(cell: Path) -> float:
    total = 0.0
    n = 0
    for pf in cell.glob("client_h*_perf.csv"):
        last = None
        with pf.open(newline="") as f:
            for row in csv.DictReader(f):
                last = row
        if last:
            try:
                total += float(last.get("rx_bytes") or 0.0)
                n += 1
            except (TypeError, ValueError):
                pass
    return total


def _last_dump_sum(cell: Path) -> int:
    total = 0
    for rp in cell.glob("client_h*_COMPONENT_RECEIPT.jsonl"):
        rows = [json.loads(x) for x in rp.read_text(errors="ignore").splitlines() if x.strip()]
        if not rows:
            continue
        dumps = rows[-1].get("dump_bytes") or {}
        for c in TRACKS:
            try:
                total += int(dumps.get(c) or 0)
            except (TypeError, ValueError):
                continue
    return total


def rb_lineage(cell: Path, metrics: dict | None = None) -> dict:
    """Classify Rb=0. Never fills Rb from B_shared/Ro. Does not change U."""
    perf_rb = _unique_perf(cell, "reward_R_b")
    perf_ro = _unique_perf(cell, "reward_R_o")
    perf_stall = _unique_perf(cell, "stall_total_sec")
    dump_sum = _last_dump_sum(cell)
    rx_sum = _last_rx_sum(cell)
    m = metrics or {}
    metrics_rb = m.get("Rb")
    metrics_ro = m.get("Ro_component")
    b_shared = m.get("B_shared")
    b_uni = m.get("B_unicast")
    press_file = (cell / SAMPLES).is_file() and (cell / SAMPLES).stat().st_size > 0
    press = summarize_cell(cell) if press_file else None
    traffic = dump_sum > 64 or rx_sum > 64 or float(b_shared or 0) > 64
    placeholder_client = perf_rb == [0.0] or perf_rb == []
    placeholder_agg = metrics_rb is None or (isinstance(metrics_rb, (int, float)) and float(metrics_rb) == 0.0)
    fabricated = (not placeholder_agg) and placeholder_client and not press_file
    dropped = (not placeholder_client) and placeholder_agg and not press_file
    conflated = False
    if metrics_rb is not None and metrics_ro is not None:
        try:
            rb_f = float(metrics_rb)
            ro_f = float(metrics_ro)
            if abs(rb_f - ro_f) < 1e-6 and 0.02 < ro_f < 0.98:
                conflated = True
            if abs(rb_f - (1.0 - ro_f)) < 1e-6 and 0.02 < ro_f < 0.98:
                conflated = True
        except (TypeError, ValueError):
            pass
    if fabricated:
        klass = "RB_AGGREGATOR_FABRICATED_WITHOUT_PRESSURE_COUNTERS"
        ok = False
    elif dropped:
        klass = "RB_CLIENT_NONZERO_AGGREGATOR_DROPPED"
        ok = False
    elif conflated:
        klass = "RB_CONFLATED_WITH_RO_OR_VOLUME"
        ok = False
    elif press_file:
        rb_ok = press is not None and press.get("Rb") is not None
        klass = "RB_PHYSICAL_PRESSURE_COMPUTED" if rb_ok else "RB_PRESSURE_SAMPLES_NONFINITE"
        ok = bool(rb_ok)
    elif placeholder_client and placeholder_agg and not traffic:
        klass = "RB_PLACEHOLDER_ZERO_NO_TRAFFIC"
        ok = False
    else:
        klass = "RB_RESERVED_PHYSICAL_PRESSURE_PLACEHOLDER_ZERO"
        ok = True
    return {
        "pass": ok,
        "class": klass,
        "contract_Rb": RB_CONTRACT,
        "not_Rb": RB_NOT,
        "situation": "A_UNIMPLEMENTED",
        "situation_note": (
            "Frozen Rb is bottleneck/network pressure (situation A), not volume cost (situation B). "
            "Client reward_R_b remains a placeholder; canonical Rb is P95 physical-utilization pressure "
            "from r0-eth1 kernel counters when PHYSICAL_PRESSURE_TIMESERIES.jsonl exists."
        ),
        "paper_U_is_Rb0_projection": klass == "RB_RESERVED_PHYSICAL_PRESSURE_PLACEHOLDER_ZERO",
        "physical_root_link_pressure_computed": bool(press_file),
        "perf_reward_R_b_unique": perf_rb,
        "perf_reward_R_o_unique": perf_ro,
        "perf_stall_total_sec_unique": perf_stall,
        "stall_last_also_client_placeholder": perf_stall == [0.0] or perf_stall == [],
        "last_dump_bytes_sum": dump_sum,
        "last_rx_bytes_sum": rx_sum,
        "metrics_Rb": metrics_rb,
        "metrics_Ro_component": metrics_ro,
        "B_shared": b_shared,
        "B_unicast": b_uni,
        "physical_traffic_present": traffic,
        "bandwidth_efficiency_evidence": ["Ro_component", "B_shared_component", "B_unicast_component", "dump_bytes", "eth0_rx_bytes"],
    }
