from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Corrected-contract canary target policies. Frozen Q; ComponentActuationPlan applies."""
import json
import os
from pathlib import Path

from command147_nested_runtime import user_id
from command149_marginal_cost import active_from_plan, project_down, user_active_unicast
from component_actuation_plan import TRACKS, closure

STRATS = [
    "MD2G_COMPONENT",
    "HV3_COMPONENT",
    "CLUSTERING_COMPONENT",
    "RULE_COMPONENT",
    "MOQ_UNICAST_COMPONENT",
    "MCG_COMPONENT",
]
STATES = [f"Rep{i}" for i in range(1, 10)]
_STUDENT = None
_STUDENT_ERR = None


def _repo() -> Path:
    return artifact_root()


def _holdout_released() -> bool:
    return (_repo() / "state" / "COMMAND153_FINAL_DEV_FROZEN.json").is_file()


def _content() -> str:
    c = (os.environ.get("TON_CONTENT_ID") or "redandblack").strip().lower()
    if c == "loot" and not _holdout_released():
        raise RuntimeError("loot_network_sealed")
    return c


def _qnorm(content: str) -> dict:
    p = Path(
        os.environ.get("COMMAND147_QUALITY_CONTRACT")
        or str(_repo() / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json")
    )
    return dict((json.loads(p.read_text()).get("Q_norm") or {}).get(content) or {})


def _rates(content: str) -> dict[str, float]:
    body = json.loads((_repo() / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
    return {
        t: float(body["contents"][content][t]["steady_state_payload_mbps"])
        for t in TRACKS
    }


def state_rate_mbps(content: str, state: str) -> float:
    """Diagnostic full-prefix rate. Not admission. Use command149_marginal_cost.delta_r_mbps."""
    r = _rates(content)
    return sum(r[c] for c in closure(state))


def _read_live_access(log_path: Path | None, n_users: int) -> tuple[list[float], list[float]]:
    """Throughput from client perf.csv rx deltas. Never Mininet configured-BW."""
    access = [0.0] * n_users
    device = [[0.22, 0.55, 0.88][i % 3] for i in range(n_users)]
    if log_path is None:
        return access, device
    for i in range(1, n_users + 1):
        p = log_path / f"client_h{i}_perf.csv"
        if not p.is_file():
            continue
        try:
            lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
        except Exception:
            continue
        if len(lines) < 3:
            continue

        def _rx(row: str) -> float:
            parts = row.split(",")
            try:
                return float(parts[15])
            except Exception:
                return 0.0

        def _ts(row: str) -> float:
            try:
                return float(row.split(",")[0])
            except Exception:
                return 0.0

        a, b = lines[-2], lines[-1]
        dt = max(_ts(b) - _ts(a), 0.5)
        access[i - 1] = max(0.0, (_rx(b) - _rx(a)) * 8.0 / dt / 1e6)
        try:
            device[i - 1] = float(b.split(",")[3])
        except Exception:
            pass
    return access, device


def _student_path() -> Path:
    env = (os.environ.get("COMMAND148_STUDENT_PATH") or "").strip()
    if env:
        return Path(env)
    return _repo() / "Sigcomm26" / "Paper6_ToN" / "models" / "command148_component" / "student_component_v1.pt"


def _load_student():
    global _STUDENT, _STUDENT_ERR
    if _STUDENT is not None:
        return _STUDENT
    if _STUDENT_ERR is not None:
        raise RuntimeError(_STUDENT_ERR)
    path = _student_path()
    if not path.is_file():
        _STUDENT_ERR = f"student_missing:{path}"
        raise RuntimeError(_STUDENT_ERR)
    import sys

    ton = _repo() / "Sigcomm26" / "Paper6_ToN"
    if str(ton) not in sys.path:
        sys.path.insert(0, str(ton))
    if str(ton / "lib") not in sys.path:
        sys.path.insert(0, str(ton / "lib"))
    import torch
    from controllers.g2_native9rep_model import build_student

    model = build_student()
    blob = torch.load(str(path), map_location="cpu", weights_only=False)
    sd = blob["state_dict"] if isinstance(blob, dict) and "state_dict" in blob else blob
    model.load_state_dict(sd)
    model.eval()
    _STUDENT = model
    return _STUDENT


def _project_feasible(
    rep_id: int,
    access: float,
    device: float,
    content: str,
    active: list[str] | None = None,
) -> str:
    rec = project_down(f"Rep{int(rep_id)}", access, device, content, active or [])
    return str(rec["applied"])


def _write_infer(rec: dict, log_path: str | None = None) -> None:
    cell = (os.environ.get("COMMAND148_CELL_DIR") or log_path or "").strip()
    if not cell:
        return
    p = Path(cell) / "COMMAND148_STUDENT_INFERENCE.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def _write_mcg(rec: dict, log_path: str | None = None) -> None:
    cell = (os.environ.get("COMMAND148_CELL_DIR") or log_path or "").strip()
    if not cell:
        return
    p = Path(cell) / "COMMAND148_MCG_DECISION.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def _read_decoded_sets(log_path: Path | None, n_users: int) -> list[set[str]]:
    """Current decoded components from last receipts. Empty at t=0."""
    out: list[set[str]] = [set() for _ in range(n_users)]
    if log_path is None:
        return out
    for i in range(1, n_users + 1):
        rp = Path(log_path) / f"client_h{i}_COMPONENT_RECEIPT.jsonl"
        if not rp.is_file():
            continue
        try:
            rows = [json.loads(x) for x in rp.read_text(errors="ignore").splitlines() if x.strip()]
        except Exception:
            continue
        if not rows:
            continue
        last = rows[-1]
        st = last.get("decoded_state")
        if st not in (None, "", "null", "None"):
            out[i - 1] = set(closure(str(st)))
            continue
        dumps = last.get("dump_bytes") or {}
        got = set()
        for c, b in dumps.items():
            try:
                if c in TRACKS and float(b) > 64:
                    got.add(c)
            except (TypeError, ValueError):
                continue
        out[i - 1] = got
    return out


def md2g_student_targets(
    t: float,
    n_users: int,
    duration: float = 120.0,
    *,
    log_path: str | None = None,
    content: str | None = None,
) -> dict[str, str]:
    import torch

    content = (content or _content()).strip().lower()
    if content == "loot" and not _holdout_released():
        raise RuntimeError("loot_network_sealed")
    cell = Path(os.environ.get("COMMAND148_CELL_DIR") or log_path or "")
    access, device = _read_live_access(cell if str(cell) else None, n_users)
    active = active_from_plan(cell if str(cell) else None)
    model = _load_student()
    user = torch.zeros(1, n_users, 16)
    for i in range(n_users):
        user[0, i, 0] = access[i] / 120.0
        user[0, i, 1] = device[i]
        user[0, i, 2] = min(1.0, t / max(duration, 1.0))
    cfeat = torch.zeros(1, 12)
    cfeat[0, 0] = 0.0 if content == "redandblack" else 1.0
    gfeat = torch.zeros(1, 10)
    gfeat[0, 0] = n_users / 100.0
    for j, tr in enumerate(TRACKS):
        gfeat[0, 1 + j] = 1.0 if tr in set(active) else 0.0
    with torch.no_grad():
        pred = model(user, cfeat, gfeat)["rep_logits"].argmax(-1)[0] + 1
    out = {}
    feas = []
    for i in range(1, n_users + 1):
        raw = int(pred[i - 1].item())
        rec = project_down(f"Rep{raw}", access[i - 1], device[i - 1], content, active)
        out[user_id(i)] = rec["applied"]
        feas.append(rec)
    _write_infer(
        {
            "t": float(t),
            "content": content,
            "n_users": n_users,
            "targets": out,
            "raw_rep": [int(pred[i].item()) for i in range(n_users)],
            "access_mbps": access,
            "device": device,
            "active_components": active,
            "physics": "missing_component_DeltaR",
            "feasibility": feas,
            "learned_md2g": True,
        },
        log_path=str(cell) if str(cell) else log_path,
    )
    return out


def mcg_component_targets(
    t: float,
    n_users: int,
    duration: float = 120.0,
    *,
    log_path: str | None = None,
    content: str | None = None,
) -> dict[str, str]:
    """Live MCG. Same state/action interface as MD2G; does not call the student."""
    from command148_mcg import mcg_select

    content = (content or _content()).strip().lower()
    if content == "loot" and not _holdout_released():
        raise RuntimeError("loot_network_sealed")
    cell = Path(os.environ.get("COMMAND148_CELL_DIR") or log_path or "")
    cell_p = cell if str(cell) else None
    access, device = _read_live_access(cell_p, n_users)
    active = active_from_plan(cell_p)
    decoded = _read_decoded_sets(cell_p, n_users)
    sel = mcg_select(
        access,
        device,
        content,
        decoded_sets=decoded,
        already_active=active,
    )
    raw = {user_id(i): sel["states"][i - 1] for i in range(1, n_users + 1)}
    out = _apply_shared_physics(raw, strategy="MCG_COMPONENT", n_users=n_users, content=content, log_path=log_path)
    _write_mcg(
        {
            "t": float(t),
            "content": content,
            "n_users": n_users,
            "duration": float(duration),
            "targets": out,
            "raw_states": raw,
            "greedy_active": sel.get("active"),
            "scores": sel.get("scores"),
            "access_mbps": access,
            "device": device,
            "active_components": active,
            "decoded_seed": [sorted(s) for s in decoded],
            "physics": "missing_component_DeltaR",
            "fov_used": False,
            "learned_md2g": False,
            "scheduler": "MCG_COMPONENT",
        },
        log_path=str(cell) if str(cell) else log_path,
    )
    return out


def rule_targets(t: float, n_users: int, duration: float = 120.0) -> dict[str, str]:
    out = {}
    for i in range(1, n_users + 1):
        bucket = (i - 1) % 3
        if t < 20:
            out[user_id(i)] = "Rep1"
        elif bucket == 0:
            out[user_id(i)] = "Rep3" if t < 70 else "Rep8"
        elif bucket == 1:
            out[user_id(i)] = "Rep2" if t < 50 else "Rep6"
        else:
            out[user_id(i)] = "Rep9" if t >= 80 else "Rep3"
    return out


def _raw_policy_targets(strategy: str, t: float, n_users: int, duration: float) -> dict[str, str]:
    s = strategy.upper()
    if s in ("RULE_COMPONENT", "MOQ_UNICAST_COMPONENT"):
        return rule_targets(t, n_users, duration)
    if s == "HV3_COMPONENT":
        out = {}
        for i in range(1, n_users + 1):
            if t < 25:
                out[user_id(i)] = "Rep1"
            elif t < 70:
                out[user_id(i)] = "Rep2"
            else:
                out[user_id(i)] = "Rep3"
        return out
    if s == "CLUSTERING_COMPONENT":
        out = {}
        mid = max(1, n_users // 2)
        for i in range(1, n_users + 1):
            if i <= mid:
                out[user_id(i)] = "Rep3" if t < 40 else "Rep8"
            else:
                out[user_id(i)] = "Rep2" if t < 40 else "Rep6"
        return out
    raise ValueError(f"unknown strategy {strategy}")


def _apply_shared_physics(
    raw: dict[str, str],
    *,
    strategy: str,
    n_users: int,
    content: str,
    log_path: str | None,
) -> dict[str, str]:
    cell = Path(os.environ.get("COMMAND148_CELL_DIR") or log_path or "")
    access, device = _read_live_access(cell if str(cell) else None, n_users)
    group_active = active_from_plan(cell if str(cell) else None)
    unicast = strategy.upper() == "MOQ_UNICAST_COMPONENT"
    pub_keys = None
    plan_p = cell / "COMPONENT_ACTUATION_PLAN_CURRENT.json" if str(cell) else None
    if unicast and plan_p is not None and plan_p.is_file():
        try:
            pub_keys = list(json.loads(plan_p.read_text()).get("physical_publisher_keys") or [])
        except Exception:
            pub_keys = None
    out = {}
    for i in range(1, n_users + 1):
        uid = user_id(i)
        ag = user_active_unicast(uid, pub_keys) if unicast else group_active
        rec = project_down(raw[uid], access[i - 1], device[i - 1], content, ag)
        out[uid] = rec["applied"]
    return out


def schedule_strategy_targets(
    strategy: str,
    t: float,
    n_users: int,
    duration: float = 120.0,
    log_path: str | None = None,
    content: str | None = None,
    **_kw,
) -> dict[str, str]:
    s = strategy.upper()
    content = (content or _content()).strip().lower()
    if content == "loot" and not _holdout_released():
        raise RuntimeError("loot_network_sealed")
    if s == "MD2G_COMPONENT":
        return md2g_student_targets(t, n_users, duration, log_path=log_path, content=content)
    if s == "MCG_COMPONENT":
        return mcg_component_targets(t, n_users, duration, log_path=log_path, content=content)
    raw = _raw_policy_targets(s, t, n_users, duration)
    return _apply_shared_physics(raw, strategy=s, n_users=n_users, content=content, log_path=log_path)


def physical_publisher_keys(targets: dict[str, str], unicast: bool) -> list[tuple[str, str]]:
    """Return (publisher_key, video_component). Unicast uses independent copies."""
    if not unicast:
        seen: list[tuple[str, str]] = []
        got = set()
        for st in targets.values():
            for c in closure(st):
                if c not in got:
                    got.add(c)
                    seen.append((c, c))
        return seen
    keys: list[tuple[str, str]] = []
    got = set()
    for uid, st in targets.items():
        hid = str(uid).replace("u", "")
        for c in closure(st):
            k = f"u{hid}_{c}"
            if k not in got:
                got.add(k)
                keys.append((k, c))
    return keys


def video_component_of_pub(key: str) -> str:
    if key in TRACKS:
        return key
    if "_" in key:
        c = key.rsplit("_", 1)[-1]
        if c in TRACKS:
            return c
    raise ValueError(f"not a component publisher key: {key}")
