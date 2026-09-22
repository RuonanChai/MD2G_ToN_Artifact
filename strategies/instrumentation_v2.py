#!/usr/bin/env python3
"""Direct instrumentation V2 recording helpers (command60/61).

Pure accounting + jsonl sink — no Mininet/MoQ wiring in this module.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

try:
    import psutil

    _PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment,misc]
    _PSUTIL_AVAILABLE = False

PathLike = Union[str, Path]

DEFAULT_RECONCILE_TOLERANCE_FRAC = 0.01
DEFAULT_OVERHEAD_BOUND_FRAC = 0.05
REQUIRED_DIRECT_RECORDS = (
    "source_egress",
    "root_ingress_egress",
    "leaf_ingress_egress",
    "client_payload_bytes",
    "protocol_control_overhead",
    "stale_bytes",
    "duplicate_representation_bytes",
    "unused_enhancement_bytes",
    "useful_rendered_bytes",
    "subscription_cancel_timestamps",
    "simultaneous_active_reps",
    "controller_inference_queue_latency",
    "relay_queue_latency",
    "cpu_memory",
)


def instrumentation_v2_enabled() -> bool:
    """Env gate; default ON (disabled only when SIGCOMM_INSTRUMENTATION_V2=0)."""
    return os.environ.get("SIGCOMM_INSTRUMENTATION_V2", "1") != "0"


class InstrumentationV2:
    """Direct byte/latency/cpu records per MD2G_INSTRUMENTATION_V2 contract."""

    _BYTE_FIELDS = (
        "client_payload_bytes",
        "protocol_control_overhead",
        "stale_bytes",
        "duplicate_representation_bytes",
        "unused_enhancement_bytes",
        "useful_rendered_bytes",
    )

    def __init__(
        self,
        *,
        cell: str,
        user: Union[str, int],
        rep: Optional[int] = None,
        epoch: int = 0,
        clock: Optional[Callable[[], float]] = None,
        reconcile_tolerance_frac: float = DEFAULT_RECONCILE_TOLERANCE_FRAC,
    ) -> None:
        self.cell = str(cell)
        self.user = str(user)
        self.rep = rep
        self.epoch = int(epoch)
        self._clock = clock or time.monotonic
        self.reconcile_tolerance_frac = float(reconcile_tolerance_frac)
        self._pending: List[Dict[str, Any]] = []
        self._byte_totals: Dict[str, int] = {k: 0 for k in self._BYTE_FIELDS}
        self._record_counts: Dict[str, int] = {k: 0 for k in REQUIRED_DIRECT_RECORDS}
        self._overhead_ns_acc = 0

    # --- env ---

    @classmethod
    def enabled(cls) -> bool:
        return instrumentation_v2_enabled()

    # --- internal ---

    def _emit(
        self,
        field: str,
        value: Any,
        *,
        rep: Optional[int] = None,
        epoch: Optional[int] = None,
        unit: str = "",
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        t0 = time.perf_counter_ns()
        rec: Dict[str, Any] = {
            "cell": self.cell,
            "user": self.user,
            "rep": self.rep if rep is None else rep,
            "epoch": self.epoch if epoch is None else int(epoch),
            "field": field,
            "value": value,
            "unit": unit,
            "ts_mono": self._clock(),
        }
        if meta:
            rec["meta"] = meta
        self._pending.append(rec)
        self._record_counts[field] = self._record_counts.get(field, 0) + 1
        self._overhead_ns_acc += time.perf_counter_ns() - t0

    def _record_bytes(
        self,
        field: str,
        nbytes: int,
        *,
        rep: Optional[int] = None,
        epoch: Optional[int] = None,
        cumulative: bool = True,
    ) -> None:
        n = max(0, int(nbytes))
        if cumulative:
            self._byte_totals[field] = n
        else:
            self._byte_totals[field] = self._byte_totals.get(field, 0) + n
        self._emit(field, n, rep=rep, epoch=epoch, unit="bytes")

    # --- required direct record methods ---

    def record_source_egress(
        self, ingress: int, egress: int, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._emit(
            "source_egress",
            {"ingress": int(ingress), "egress": int(egress)},
            rep=rep,
            epoch=epoch,
            unit="bytes",
        )

    def record_root_ingress_egress(
        self, ingress: int, egress: int, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._emit(
            "root_ingress_egress",
            {"ingress": int(ingress), "egress": int(egress)},
            rep=rep,
            epoch=epoch,
            unit="bytes",
        )

    def record_leaf_ingress_egress(
        self, ingress: int, egress: int, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._emit(
            "leaf_ingress_egress",
            {"ingress": int(ingress), "egress": int(egress)},
            rep=rep,
            epoch=epoch,
            unit="bytes",
        )

    def record_client_payload_bytes(
        self, nbytes: int, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._record_bytes("client_payload_bytes", nbytes, rep=rep, epoch=epoch)

    def record_protocol_control_overhead(
        self, nbytes: int, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._record_bytes("protocol_control_overhead", nbytes, rep=rep, epoch=epoch)

    def record_stale_bytes(
        self, nbytes: int, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._record_bytes("stale_bytes", nbytes, rep=rep, epoch=epoch)

    def record_duplicate_representation_bytes(
        self, nbytes: int, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._record_bytes("duplicate_representation_bytes", nbytes, rep=rep, epoch=epoch)

    def record_unused_enhancement_bytes(
        self, nbytes: int, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._record_bytes("unused_enhancement_bytes", nbytes, rep=rep, epoch=epoch)

    def record_useful_rendered_bytes(
        self, nbytes: int, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._record_bytes("useful_rendered_bytes", nbytes, rep=rep, epoch=epoch)

    def record_subscription_cancel_timestamps(
        self,
        subscribe_ts: float,
        cancel_ts: Optional[float] = None,
        *,
        rep: Optional[int] = None,
        epoch: Optional[int] = None,
    ) -> None:
        self._emit(
            "subscription_cancel_timestamps",
            {"subscribe_ts": float(subscribe_ts), "cancel_ts": cancel_ts},
            rep=rep,
            epoch=epoch,
            unit="monotonic_s",
        )

    def record_simultaneous_active_reps(
        self, count: int, *, epoch: Optional[int] = None
    ) -> None:
        self._emit(
            "simultaneous_active_reps",
            int(count),
            epoch=epoch,
            unit="count",
        )

    def record_controller_inference_queue_latency(
        self, latency_s: float, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._emit(
            "controller_inference_queue_latency",
            float(latency_s),
            rep=rep,
            epoch=epoch,
            unit="seconds",
        )

    def record_relay_queue_latency(
        self, latency_s: float, *, rep: Optional[int] = None, epoch: Optional[int] = None
    ) -> None:
        self._emit(
            "relay_queue_latency",
            float(latency_s),
            rep=rep,
            epoch=epoch,
            unit="seconds",
        )

    def record_cpu_memory(
        self, snapshot: Optional[Dict[str, Any]] = None, *, epoch: Optional[int] = None
    ) -> None:
        snap = snapshot if snapshot is not None else self.overhead_snapshot()
        self._emit("cpu_memory", snap, epoch=epoch, unit="snapshot")

    # --- reconcile / overhead ---

    def reconcile_bytes(self, *, tolerance_frac: Optional[float] = None) -> Dict[str, Any]:
        """Check useful + stale + duplicate + unused + control ≈ client_payload."""
        tol = self.reconcile_tolerance_frac if tolerance_frac is None else float(tolerance_frac)
        payload = int(self._byte_totals.get("client_payload_bytes", 0))
        useful = int(self._byte_totals.get("useful_rendered_bytes", 0))
        stale = int(self._byte_totals.get("stale_bytes", 0))
        duplicate = int(self._byte_totals.get("duplicate_representation_bytes", 0))
        unused = int(self._byte_totals.get("unused_enhancement_bytes", 0))
        control = int(self._byte_totals.get("protocol_control_overhead", 0))
        accounted = useful + stale + duplicate + unused + control
        delta = abs(payload - accounted)
        abs_tol = max(1, int(payload * tol))
        ok = payload == 0 or delta <= abs_tol
        return {
            "ok": ok,
            "client_payload_bytes": payload,
            "accounted_bytes": accounted,
            "delta_bytes": delta,
            "tolerance_bytes": abs_tol,
            "components": {
                "useful_rendered_bytes": useful,
                "stale_bytes": stale,
                "duplicate_representation_bytes": duplicate,
                "unused_enhancement_bytes": unused,
                "protocol_control_overhead": control,
            },
        }

    @staticmethod
    def overhead_snapshot() -> Dict[str, Any]:
        """CPU/memory snapshot via psutil when available."""
        out: Dict[str, Any] = {"ts_mono": time.monotonic(), "psutil_available": _PSUTIL_AVAILABLE}
        if not _PSUTIL_AVAILABLE or psutil is None:
            return out
        try:
            out["cpu_percent"] = float(psutil.cpu_percent(interval=None))
            proc = psutil.Process()
            mem = proc.memory_info()
            out["memory_rss_bytes"] = int(mem.rss)
            out["memory_rss_mb"] = round(mem.rss / (1024 * 1024), 3)
        except Exception as exc:
            out["error"] = str(exc)
        return out

    @staticmethod
    def measure_record_overhead_fraction(n_events: int = 1000) -> float:
        """Synthetic overhead: instrumentation delta / total client tick time.

        Uses a heavy simulated client tick so recording noise cannot dominate.
        Returns the *median* of three warmed-up trials for stability.
        """
        n = max(1, int(n_events))

        def _simulated_client_tick(i: int) -> int:
            # Mimics per-iteration dump-size aggregation work in dispatch.
            total = 0
            for j in range(20000):
                total += (i + j) * 8192 % 997
            return total

        def _one_trial() -> float:
            instr = InstrumentationV2(cell="overhead_synth", user="u0")
            # Warm-up (discard)
            for i in range(8):
                _simulated_client_tick(i)
                instr.record_client_payload_bytes(i, rep=1, epoch=0)

            t0 = time.perf_counter()
            for i in range(n):
                _simulated_client_tick(i)
            baseline_s = time.perf_counter() - t0

            t0 = time.perf_counter()
            for i in range(n):
                payload = _simulated_client_tick(i)
                instr.record_client_payload_bytes(payload, rep=1, epoch=0)
                instr.record_simultaneous_active_reps(1, epoch=0)
            total_s = time.perf_counter() - t0
            if total_s <= 0:
                return 0.0
            return max(0.0, total_s - baseline_s) / total_s

        trials = sorted(_one_trial() for _ in range(3))
        return trials[1]  # median

    def required_keys_seen(self) -> List[str]:
        return [k for k in REQUIRED_DIRECT_RECORDS if self._record_counts.get(k, 0) > 0]

    # --- persistence ---

    def write_jsonl(self, path: PathLike, *, append: bool = True) -> int:
        """Flush pending records to jsonl; return number of lines written."""
        if not self._pending:
            return 0
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        n = len(self._pending)
        with open(p, mode, encoding="utf-8") as fh:
            for rec in self._pending:
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
        self._pending.clear()
        return n

    def flush_cell(self, path: PathLike) -> int:
        """Write pending records plus reconcile summary trailer."""
        n = self.write_jsonl(path, append=True)
        summary = {
            "cell": self.cell,
            "user": self.user,
            "field": "_cell_summary",
            "ts_mono": self._clock(),
            "reconcile_bytes": self.reconcile_bytes(),
            "required_keys_seen": self.required_keys_seen(),
            "record_counts": dict(self._record_counts),
        }
        p = Path(path)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, sort_keys=True) + "\n")
            fh.flush()
        return n + 1


def synthetic_byte_accounting(
    *,
    client_payload: int = 10_000,
    useful: int = 7_000,
    stale: int = 1_000,
    duplicate: int = 500,
    unused: int = 1_000,
    control: int = 500,
) -> InstrumentationV2:
    """Deterministic fixture for unit tests (reconcile PASS)."""
    instr = InstrumentationV2(cell="synth_cell", user="u1", rep=3, epoch=1)
    instr.record_source_egress(useful, useful)
    instr.record_root_ingress_egress(useful, useful)
    instr.record_leaf_ingress_egress(useful, useful)
    instr.record_client_payload_bytes(client_payload)
    instr.record_useful_rendered_bytes(useful)
    instr.record_stale_bytes(stale)
    instr.record_duplicate_representation_bytes(duplicate)
    instr.record_unused_enhancement_bytes(unused)
    instr.record_protocol_control_overhead(control)
    instr.record_subscription_cancel_timestamps(1000.0, 1003.2, rep=3)
    instr.record_simultaneous_active_reps(2)
    instr.record_controller_inference_queue_latency(0.012, rep=3)
    instr.record_relay_queue_latency(0.004, rep=3)
    instr.record_cpu_memory({"cpu_percent": 1.0, "memory_rss_mb": 42.0})
    return instr
