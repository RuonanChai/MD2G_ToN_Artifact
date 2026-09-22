from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Shared IO for command147 tightening artifacts."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dump_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def dump_dual(name: str, obj: dict) -> None:
    dump_json(REPO / "state" / name, obj)
    dump_json(TON / "state" / name, obj)


def dump_analysis(name: str, obj: dict) -> None:
    dump_json(REPO / "analysis" / name, obj)
    dump_json(TON / "analysis" / name, obj)


def dump_status(name: str, text: str) -> None:
    for root in (REPO / "status", TON / "status"):
        root.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text if text.endswith("\n") else text + "\n")


def token(name: str, extra: dict | None = None) -> None:
    body = {"ts": ts(), "token": name}
    if extra:
        body.update(extra)
    dump_dual(f"{name}.json", body)


def handle_unsupervised_live_wait(*, stale_s: float = 180.0) -> int | None:
    """None = not unsupervised leftover. 0 = wait within grace. 3 = CONTRACT_BLOCKED written.

    Never kills a process. Healthy cells hold SCIENTIFIC_EXECUTOR.lock.
    """
    from command137_proc import dash_live, moq_live, unsupervised_live  # noqa: PLC0415

    leftover_name = "COMMAND153_UNSUPERVISED_LIVE.json"
    leftover_p = REPO / "state" / leftover_name
    if not (moq_live() or dash_live()) or not unsupervised_live():
        for root in (REPO / "state", TON / "state"):
            p = root / leftover_name
            if p.is_file():
                try:
                    p.unlink()
                except OSError:
                    pass
        return None
    first = None
    if leftover_p.is_file():
        try:
            first = json.loads(leftover_p.read_text()).get("first_ts")
        except Exception:
            first = None
    now = ts()
    if not first:
        dump_dual(
            leftover_name,
            {"ts": now, "first_ts": now, "kill_live_cell": False, "token": "COMMAND153_UNSUPERVISED_LIVE"},
        )
        return 0
    try:
        t0 = datetime.fromisoformat(str(first).replace("Z", "+00:00"))
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - t0).total_seconds()
    except Exception:
        age = 0.0
    if age >= float(stale_s):
        token(
            "COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED",
            {
                "reason": "unsupervised_live_after_lock_dead",
                "age_s": age,
                "kill_live_cell": False,
            },
        )
        return 3
    return 0


def canary_rbv1_art() -> Path:
    """Post-Rb scientific canary root. Pre-Rb command148_canary120 is diagnostic only."""
    rbv1 = TON / "artifacts" / "command148_canary120_rbv1"
    legacy = TON / "artifacts" / "command148_canary120"
    if (REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_RELEASE.json").is_file():
        return rbv1
    qp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
    if qp.is_file():
        try:
            q = json.loads(qp.read_text())
        except Exception:
            q = {}
        if str(q.get("epoch") or "") == "post_physical_pressure_rbv1":
            raw = q.get("art")
            return Path(raw) if raw else rbv1
    return legacy
