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

"""DEV 945 paper-facing reports. Does not touch the rbv1 120 canary queue."""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
from command147_io import ts  # noqa: E402

ART = TON / "artifacts" / "command148_maindev"
OUT = TON / "reports" / "command153_dev"
REV = TON / "reviews" / "command153_dev"
STRATS = [
    "MD2G_COMPONENT",
    "HV3_COMPONENT",
    "CLUSTERING_COMPONENT",
    "RULE_COMPONENT",
    "MOQ_UNICAST_COMPONENT",
]
SAME = ["HV3_COMPONENT", "CLUSTERING_COMPONENT", "RULE_COMPONENT"]
QUEUE = REPO / "state" / "COMMAND148_MAINDEV_QUEUE.json"


def _mean(xs: list[float]) -> float | None:
    return statistics.mean(xs) if xs else None


def _rows() -> list[dict]:
    if not QUEUE.is_file():
        return []
    q = json.loads(QUEUE.read_text())
    out = []
    for key in q.get("completed") or []:
        cell = ART / key
        if not (cell / "CELL_DONE.json").is_file():
            continue
        mp = cell / "CELL_METRICS.json"
        if not mp.is_file():
            continue
        raw = mp.read_text().strip()
        if raw in ("", "null"):
            continue
        m = json.loads(raw)
        if not isinstance(m, dict) or m.get("U") is None:
            continue
        if m.get("paper_U_is_Rb0_projection"):
            continue
        m["key"] = key
        out.append(m)
    return out


def _blk(r: dict) -> str:
    return f"{r.get('content')}_{r.get('network')}_u{r.get('users')}_s{r.get('seed')}"


def write_reports() -> dict:
    rows = _rows()
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[str(r.get("strategy") or "")].append(r)
    means = {}
    for s, rs in by.items():
        means[s] = {
            "n": len(rs),
            "U": _mean([float(x["U"]) for x in rs]),
            "Rq": _mean([float(x.get("Rq") or 0) for x in rs]),
            "Ro_component": _mean([float(x.get("Ro_component") or 0) for x in rs]),
            "Rb": _mean([float(x.get("Rb") or 0) for x in rs]),
            "weak_user_Rq": _mean([float(x.get("weak_user_Rq") or 0) for x in rs]),
        }
    OUT.mkdir(parents=True, exist_ok=True)
    REV.mkdir(parents=True, exist_ok=True)
    body = {"ts": ts(), "n_valid": len(rows), "by_strategy": means, "loot_sealed": True, "not_canary_120": True}
    (OUT / "CUMULATIVE_METRICS.json").write_text(json.dumps(body, indent=2) + "\n")
    blocks: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        blocks[_blk(r)][str(r.get("strategy") or "")] = r
    n_matched = 0
    for blk, recs in sorted(blocks.items()):
        if not all(s in recs and recs[s].get("U") is not None for s in STRATS):
            continue
        n_matched += 1
        md = recs["MD2G_COMPONENT"]
        deltas = {}
        for s in SAME:
            b = recs[s]
            deltas[s] = float(md["U"]) - float(b["U"])
        strongest = max(SAME, key=lambda s: float(recs[s]["U"]))
        rec = {
            "ts": ts(),
            "block": blk,
            "matched": True,
            "MD2G_U": md["U"],
            "strongest_same": strongest,
            "delta_U_vs_strongest": float(md["U"]) - float(recs[strongest]["U"]),
            "deltas": deltas,
            "MOQ_UNICAST_not_same_substrate": True,
        }
        (REV / f"LEVEL2_{blk}.json").write_text(json.dumps(rec, indent=2) + "\n")
    summary = {"ts": ts(), "n_valid": len(rows), "n_matched": n_matched, "loot_sealed": True}
    (OUT / "LEVEL2_SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    s = write_reports()
    print(json.dumps({"pass": True, **s}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
