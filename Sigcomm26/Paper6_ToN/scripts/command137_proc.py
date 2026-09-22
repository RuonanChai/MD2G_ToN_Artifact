from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Process ownership helpers. Watch scripts that mention moq_cluster are not a live cell."""
from pathlib import Path


def _cmdlines() -> list[str]:
    rows = []
    for pid in Path("/proc").iterdir():
        if not pid.name.isdigit():
            continue
        try:
            rows.append((pid / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore"))
        except Exception:
            continue
    return rows


def moq_live() -> bool:
    for cmd in _cmdlines():
        parts = cmd.split()
        if not parts:
            continue
        if not any(p.endswith("moq_cluster_Sigcomm.py") or p.endswith("moq_cluster_NOSSDAV.py") for p in parts):
            continue
        if any("python" in p for p in parts[:4]):
            return True
    return False


def dash_live() -> bool:
    for cmd in _cmdlines():
        parts = cmd.split()
        if not parts:
            continue
        if not any(
            p.endswith("rolling_dash_experiment.py")
            or p.endswith("groot_dash_experiment.py")
            or p.endswith("command139_dash_companion_canary.py")
            or p.endswith("run_authentic_unicast_baseline_cell.py")
            for p in parts
        ):
            continue
        if any("python" in p for p in parts[:4]):
            return True
    return False


def transport_encode_live() -> bool:
    for cmd in _cmdlines():
        parts = cmd.split()
        if any(p.endswith("command137_transport_encode.py") for p in parts) and any("python" in p for p in parts[:4]):
            return True
    return False


def scientific_lock_pid_alive() -> bool:
    p = Path("str(artifact_root())/state/SCIENTIFIC_EXECUTOR.lock")
    if not p.is_file():
        return False
    try:
        import json

        pid = int((json.loads(p.read_text()) or {}).get("pid") or 0)
    except Exception:
        return False
    return pid > 1 and Path("/proc", str(pid)).exists()


def unsupervised_live() -> bool:
    """MoQ/DASH process exists but the scientific executor lock pid is dead."""
    return (moq_live() or dash_live()) and not scientific_lock_pid_alive()
