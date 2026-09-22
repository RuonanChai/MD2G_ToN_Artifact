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

"""COMMAND153 raw dump retention — contract-driven; never interrupts a live cell."""
import hashlib
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
CONTRACT = REPO / "state" / "COMMAND153_RAW_DUMP_RETENTION_CONTRACT.json"

# Derived evidence that must exist before VALID dump unlink (names or globs).
REQUIRED_FILES = (
    "CELL_VALIDITY.json",
    "CELL_METRICS.json",
    "CELL_DONE.json",
    "CELL_AUDIT.json",
    "PHYSICAL_PRESSURE_TIMESERIES.jsonl",
)
REQUIRED_METRIC_KEYS = (
    "target_state_occupancy",
    "actual_decoded_state_occupancy",
    "component_completion_fraction",
    "B_shared",
    "B_unicast",
    "Rb",
    "Ro_component",
    "Rq",
    "U",
)
REQUIRED_GLOBS = (
    "client_*_COMPONENT_RECEIPT.jsonl",
    "client_*_perf.csv",
)


def load_contract() -> dict[str, Any]:
    if not CONTRACT.is_file():
        raise FileNotFoundError(f"missing retention contract: {CONTRACT}")
    return json.loads(CONTRACT.read_text())


def atomic_write_json(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def free_bytes(path: Path | None = None) -> int:
    usage = shutil.disk_usage(str(path or REPO))
    return int(usage.free)


def is_invalid_or_failed_attempt_dir(cell: Path) -> bool:
    name = cell.name.lower()
    return any(
        tok in name
        for tok in ("_invalid", "invalid_", "_attempt", "fail_closed", "failed")
    )


def sentinel_keys(contract: dict[str, Any] | None = None) -> set[str]:
    c = contract or load_contract()
    return set(c.get("valid_raw_dump_sentinel_keys") or [])


def derived_evidence_ready(cell: Path) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for name in REQUIRED_FILES:
        if not (cell / name).is_file():
            missing.append(name)
    metrics_path = cell / "CELL_METRICS.json"
    if metrics_path.is_file():
        try:
            metrics = json.loads(metrics_path.read_text())
        except Exception:
            metrics = {}
            missing.append("CELL_METRICS.json:unreadable")
        if isinstance(metrics, dict):
            for k in REQUIRED_METRIC_KEYS:
                if k not in metrics:
                    missing.append(f"CELL_METRICS.{k}")
    for pattern in REQUIRED_GLOBS:
        if not list(cell.glob(pattern)):
            missing.append(pattern)
    return (not missing), missing


def inventory_dumps(cell: Path) -> list[dict[str, Any]]:
    """SHA256 every dump before VALID delete. Parallelize to keep cell-boundary short."""
    paths = sorted(cell.glob("dump_*.bin"))
    if not paths:
        return []
    empty_sha = hashlib.sha256(b"").hexdigest()

    def _one(dump: Path) -> dict[str, Any]:
        st = dump.stat()
        nbytes = int(st.st_size)
        # Empty dumps are common after CLOSE; constant digest avoids needless IO.
        if nbytes == 0:
            return {"name": dump.name, "bytes": 0, "sha256": empty_sha}
        return {"name": dump.name, "bytes": nbytes, "sha256": sha256_file(dump)}

    workers = min(8, max(1, len(paths)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, paths))


def may_delete_valid_dumps(cell: Path, cell_key: str | None = None) -> dict[str, Any]:
    """Gate for VALID-only dump unlink. Never call on INVALID/attempt dirs."""
    contract = load_contract()
    key = cell_key or cell.name
    out: dict[str, Any] = {
        "cell_key": key,
        "allow_delete": False,
        "reason": None,
        "dumps": [],
        "sentinel": key in sentinel_keys(contract),
    }
    if is_invalid_or_failed_attempt_dir(cell):
        out["reason"] = "INVALID_OR_ATTEMPT_DUMPS_PERMANENT"
        return out
    if out["sentinel"]:
        out["reason"] = "SENTINEL_KEEP_RAW_DUMPS"
        out["dumps"] = [
            {"name": p.name, "bytes": p.stat().st_size, "sha256": None}
            for p in sorted(cell.glob("dump_*.bin"))
        ]
        return out
    ready, missing = derived_evidence_ready(cell)
    if not ready:
        out["reason"] = "DERIVED_EVIDENCE_INCOMPLETE"
        out["missing"] = missing
        return out
    dumps = inventory_dumps(cell)
    out["dumps"] = dumps
    if not dumps:
        out["allow_delete"] = True
        out["reason"] = "NO_DUMPS"
        return out
    out["allow_delete"] = True
    out["reason"] = "VALID_HASHED_DERIVED_COMPLETE"
    return out


def reclaim_valid_dumps_if_allowed(cell: Path, cell_key: str | None = None, epoch_id: str | None = None) -> dict[str, Any]:
    gate = may_delete_valid_dumps(cell, cell_key=cell_key)
    manifest = {
        "ts_unix": __import__("time").time(),
        "token": "COMMAND153_RAW_DUMP_MANIFEST",
        "cell_key": gate["cell_key"],
        "epoch_id": epoch_id,
        "gate": gate,
        "contract_token": "COMMAND153_RAW_DUMP_RETENTION_CONTRACT",
        "deleted": [],
        "retained": [],
    }
    if not gate.get("allow_delete"):
        for d in cell.glob("dump_*.bin"):
            manifest["retained"].append({"name": d.name, "bytes": d.stat().st_size})
        atomic_write_json(cell / "RAW_DUMP_RETENTION.json", manifest)
        return manifest
    for row in gate.get("dumps") or []:
        path = cell / str(row["name"])
        if path.is_file():
            path.unlink()
            manifest["deleted"].append(row)
    atomic_write_json(cell / "RAW_DUMP_MANIFEST.json", {
        "ts_unix": manifest["ts_unix"],
        "cell_key": gate["cell_key"],
        "epoch_id": epoch_id,
        "dumps": gate.get("dumps") or [],
        "policy": "VALID_raw_payload_to_hash_plus_derived_then_delete",
        "contract_token": "COMMAND153_RAW_DUMP_RETENTION_CONTRACT",
    })
    atomic_write_json(cell / "RAW_DUMP_RETENTION.json", manifest)
    return manifest


def launch_free_space_ok(path: Path | None = None) -> dict[str, Any]:
    """Cell-boundary only. Never use this to kill a live cell."""
    contract = load_contract()
    floor = int(contract.get("min_free_bytes_before_next_launch") or (40 * 1024**3))
    free = free_bytes(path)
    return {
        "ok": free >= floor,
        "free_bytes": free,
        "min_free_bytes_before_next_launch": floor,
        "pause_next_launch": free < floor,
        "never_interrupt_live_cell": True,
        "cleanup_allowed": list(contract.get("cleanup_allowed_when_below_floor") or []),
        "cleanup_forbidden": list(contract.get("cleanup_forbidden") or []),
    }


def assert_not_cleaning_invalid(cell: Path) -> None:
    if is_invalid_or_failed_attempt_dir(cell):
        raise RuntimeError(f"retention contract forbids dump cleanup under INVALID/attempt: {cell}")
