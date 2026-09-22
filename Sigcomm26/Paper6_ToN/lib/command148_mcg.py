from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Marginal Completion Greedy (MCG) same-substrate baseline.

Same nested components, quality map, and feasibility projector as the other
MoQ controllers. score(c) = Σ_u ΔQ / extra shared rate(c). Greedy admit the
highest-scoring component. Undecoded users have Q=0 (not Q(Rep1)). FoV unused.
"""
import json
from pathlib import Path

from command149_marginal_cost import FROZEN_SAFETY_MARGIN
from component_actuation_plan import TRACKS, closure

COMPONENTS = ("b0", "db1", "db2", "e1", "e2")
PRE: dict[str, tuple[str, ...]] = {
    "b0": (),
    "db1": ("b0",),
    "db2": ("b0", "db1"),
    "e1": ("b0",),
    "e2": ("b0", "e1"),
}
STATES = [f"Rep{i}" for i in range(1, 10)]
REPO = artifact_root()


def _qnorm(content: str) -> dict[str, float]:
    p = Path(
        __import__("os").environ.get("COMMAND147_QUALITY_CONTRACT")
        or str(REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json")
    )
    return {k: float(v) for k, v in (json.loads(p.read_text()).get("Q_norm") or {}).get(content).items()}


def _rates(content: str) -> dict[str, float]:
    body = json.loads((REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
    return {t: float(body["contents"][content][t]["steady_state_payload_mbps"]) for t in TRACKS}


def state_of(decoded_set: set[str]) -> str | None:
    """Highest Rep whose closure is ⊆ decoded. Undecoded (no b0) is None, not Rep1."""
    if "b0" not in decoded_set:
        return None
    best, n = "Rep1", 1
    for st in STATES:
        cset = set(closure(st))
        if cset <= decoded_set and len(cset) >= n:
            best, n = st, len(cset)
    return best


def q_of(decoded_set: set[str], qmap: dict[str, float]) -> float:
    st = state_of(decoded_set)
    if st is None:
        return 0.0
    return float(qmap[st])


def mcg_select(
    access: list[float],
    device: list[float],
    content: str,
    *,
    decoded_sets: list[set[str]] | None = None,
    already_active: list[str] | None = None,
) -> dict:
    qmap = _qnorm(content)
    rates = _rates(content)
    n = len(access)
    decoded = [set(s) for s in (decoded_sets or [set() for _ in range(n)])]
    if len(decoded) < n:
        decoded.extend(set() for _ in range(n - len(decoded)))
    admitted: list[str] = [c for c in COMPONENTS if c in set(already_active or [])]
    scores: list[dict] = []

    def user_q(i: int) -> float:
        return q_of(decoded[i], qmap)

    def can_use(i: int, comp: str) -> bool:
        if float(device[i]) + 1e-9 < (0.15 if comp != "b0" else 0.0):
            return False
        trial = set(decoded[i]) | {comp}
        st = state_of(trial)
        if st is None:
            return False
        missing = [c for c in closure(st) if c not in decoded[i]]
        dlt = sum(rates[c] for c in missing)
        return float(access[i]) + 1e-9 >= dlt * FROZEN_SAFETY_MARGIN

    while True:
        best_c, best_s = None, 0.0
        for comp in COMPONENTS:
            if comp in admitted:
                continue
            if any(p not in admitted for p in PRE[comp]):
                continue
            extra = float(rates[comp])
            dq = 0.0
            n_gain = 0
            for i in range(n):
                if not can_use(i, comp):
                    continue
                q0 = user_q(i)
                trial = set(decoded[i]) | {comp}
                q1 = q_of(trial, qmap)
                gain = q1 - q0
                if gain > 1e-12:
                    dq += gain
                    n_gain += 1
            if n_gain <= 0:
                continue
            score = dq / max(extra, 1e-9)
            if score > best_s:
                best_s, best_c = score, comp
        if best_c is None:
            break
        admitted.append(best_c)
        scores.append({"component": best_c, "score": best_s})
        for i in range(n):
            if can_use(i, best_c):
                decoded[i].add(best_c)

    states = [state_of(decoded[i]) or "Rep1" for i in range(n)]
    return {
        "states": states,
        "active": list(admitted),
        "scores": scores,
        "fov_used": False,
        "physics": "missing_component_DeltaR",
        "margin": FROZEN_SAFETY_MARGIN,
        "n_users": n,
    }
