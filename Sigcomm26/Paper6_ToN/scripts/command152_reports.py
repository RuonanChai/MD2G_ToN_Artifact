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

"""command152 Level-1/2/3 reports. Never ranks from a single cell. Does not retune."""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
from command147_io import ts  # noqa: E402

ART_DEFAULT = TON / "artifacts" / "command148_canary120_rbv1"
OUT = TON / "reports" / "command152"
REV = TON / "reviews" / "command152"
STRATS = [
    "MD2G_COMPONENT",
    "HV3_COMPONENT",
    "CLUSTERING_COMPONENT",
    "RULE_COMPONENT",
    "MOQ_UNICAST_COMPONENT",
]
SAME = ["HV3_COMPONENT", "CLUSTERING_COMPONENT", "RULE_COMPONENT"]


def _art() -> Path:
    qp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
    if qp.is_file():
        q = json.loads(qp.read_text())
        raw = q.get("art")
        if raw:
            return Path(raw)
        if str(q.get("epoch") or "") == "post_physical_pressure_rbv1":
            return ART_DEFAULT
    return ART_DEFAULT


def _rows() -> list[dict]:
    qp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
    if not qp.is_file():
        return []
    q = json.loads(qp.read_text())
    art = _art()
    out = []
    for key in q.get("completed") or []:
        cell = art / key
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


def _mean(xs: list[float]) -> float | None:
    return statistics.mean(xs) if xs else None


def _blk(r: dict) -> str:
    return f"{r.get('content')}_{r.get('network')}_u{r.get('users')}_s{r.get('seed')}"


def write_cumulative(n: int | None = None) -> dict:
    rows = _rows()
    n = n if n is not None else len(rows)
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
    body = {
        "ts": ts(),
        "n_valid": len(rows),
        "by_strategy": means,
        "do_not_rank_from_single_cells": True,
        "loot_sealed": True,
        "pre_rb_excluded": True,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (TON / "reports" / "command152").mkdir(parents=True, exist_ok=True)
    (REPO / "reports" / "command152").mkdir(parents=True, exist_ok=True)
    name = f"CUMULATIVE_METRICS_{len(rows):03d}"
    text = json.dumps(body, indent=2) + "\n"
    (OUT / f"{name}.json").write_text(text)
    (REPO / "reports" / "command152" / f"{name}.json").write_text(text)
    md = [
        f"# COMMAND152 cumulative n={len(rows)}",
        "",
        f"- ts: `{body['ts']}`",
        "- pre-Rb diagnostic U excluded",
        "- do not rank from single cells",
        "",
        "| strategy | n | U | Rq | Ro | Rb | weak_Rq |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in STRATS:
        m = means.get(s) or {}
        if not m:
            md.append(f"| `{s}` | 0 | NA | NA | NA | NA | NA |")
            continue
        md.append(
            f"| `{s}` | {m['n']} | {m['U']:.4f} | {m['Rq']:.4f} | {m['Ro_component']:.4f} | "
            f"{m['Rb']:.4f} | {m['weak_user_Rq']:.4f} |"
        )
    md.append("")
    md_text = "\n".join(md)
    (OUT / f"{name}.md").write_text(md_text)
    (REPO / "reports" / "command152" / f"{name}.md").write_text(md_text)
    return body


def write_level2() -> dict:
    rows = _rows()
    blocks: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        blocks[_blk(r)][str(r.get("strategy") or "")] = r
    REV.mkdir(parents=True, exist_ok=True)
    (REPO / "reviews" / "command152").mkdir(parents=True, exist_ok=True)
    matched = []
    summaries = {}
    for blk, recs in sorted(blocks.items()):
        have = [s for s in STRATS if s in recs]
        is_matched = have == STRATS
        md2g = recs.get("MD2G_COMPONENT") or {}
        deltas = {}
        for s in SAME:
            b = recs.get(s) or {}
            if md2g.get("U") is None or b.get("U") is None:
                continue
            deltas[s] = {
                "delta_U": float(md2g["U"]) - float(b["U"]),
                "delta_Rq": float(md2g.get("Rq") or 0) - float(b.get("Rq") or 0),
                "delta_Ro": float(md2g.get("Ro_component") or 0) - float(b.get("Ro_component") or 0),
                "delta_Rb": float(md2g.get("Rb") or 0) - float(b.get("Rb") or 0),
                "delta_weak_user_Rq": float(md2g.get("weak_user_Rq") or 0) - float(b.get("weak_user_Rq") or 0),
            }
        body = {
            "ts": ts(),
            "block": blk,
            "matched": is_matched,
            "strategies_present": have,
            "MD2G": {k: md2g.get(k) for k in ("U", "Rq", "Ro_component", "Rb", "weak_user_Rq")},
            "deltas_vs_same_substrate": deltas,
            "MOQ_UNICAST_is_not_same_substrate": True,
            "do_not_rank_from_single_cells": True,
        }
        summaries[blk] = {"matched": is_matched, "deltas": deltas}
        if is_matched:
            matched.append(blk)
            text = json.dumps(body, indent=2) + "\n"
            (REV / f"LEVEL2_{blk}.json").write_text(text)
            (REPO / "reviews" / "command152" / f"LEVEL2_{blk}.json").write_text(text)
            lines = [
                f"# COMMAND152 Level-2 `{blk}`",
                "",
                f"- matched five strategies: `{is_matched}`",
                "- MOQ_UNICAST is diagnostic only",
                "",
                "| vs | dU | dRq | dRo | dRb | d_weak_Rq |",
                "|---|---|---|---|---|---|",
            ]
            for s, d in deltas.items():
                lines.append(
                    f"| `{s}` | {d['delta_U']:.4f} | {d['delta_Rq']:.4f} | {d['delta_Ro']:.4f} | "
                    f"{d['delta_Rb']:.4f} | {d['delta_weak_user_Rq']:.4f} |"
                )
            lines.append("")
            md = "\n".join(lines)
            (REV / f"LEVEL2_{blk}.md").write_text(md)
            (REPO / "reviews" / "command152" / f"LEVEL2_{blk}.md").write_text(md)
    write_level3(rows, blocks)
    return {"n_matched": len(matched), "matched": matched, "blocks": summaries}


def write_level3(rows: list[dict], blocks: dict[str, dict[str, dict]]) -> dict:
    high = []
    low = []
    by_net: dict[str, list[dict]] = defaultdict(list)
    for blk, recs in blocks.items():
        if set(recs) != set(STRATS):
            continue
        md = recs.get("MD2G_COMPONENT") or {}
        same_u = [recs[s]["U"] for s in SAME if s in recs and recs[s].get("U") is not None]
        if md.get("U") is None or not same_u:
            continue
        d = float(md["U"]) - max(float(x) for x in same_u)
        users = int(md.get("users") or 0)
        rec = {"block": blk, "delta_U_vs_strongest_same": d, "users": users, "network": md.get("network")}
        if users >= 60:
            high.append(rec)
        if users <= 20:
            low.append(rec)
        by_net[str(md.get("network") or "")].append(rec)
    high_gain = bool(high) and _mean([x["delta_U_vs_strongest_same"] for x in high]) is not None and (
        _mean([x["delta_U_vs_strongest_same"] for x in high]) or 0
    ) > 0
    low_weak = bool(low) and _mean([x["delta_U_vs_strongest_same"] for x in low]) is not None and (
        _mean([x["delta_U_vs_strongest_same"] for x in low]) or 0
    ) < 0
    klass = None
    if high_gain and low_weak:
        klass = "CONDITIONAL_SCALABILITY_ADVANTAGE"
    body = {
        "ts": ts(),
        "high_concurrency_users_ge_60": high,
        "low_concurrency_users_le_20": low,
        "by_network": {k: v for k, v in by_net.items()},
        "high_concurrency_gain_persists": high_gain,
        "low_concurrency_weakness_exists": low_weak,
        "class": klass,
        "insufficient_matched_blocks": not (high and low),
        "do_not_rank_from_single_cells": True,
        "loot_sealed": True,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "LEVEL3_CONDITION.json").write_text(json.dumps(body, indent=2) + "\n")
    (REPO / "reports" / "command152").mkdir(parents=True, exist_ok=True)
    (REPO / "reports" / "command152" / "LEVEL3_CONDITION.json").write_text(json.dumps(body, indent=2) + "\n")
    try:
        from command153_canary_six_questions import write_reports

        write_reports(final=False)
    except Exception as exc:
        body["six_questions_write_error"] = str(exc)
    return body


def main() -> int:
    args = sys.argv[1:]
    if "--level2" in args or not args:
        lvl2 = write_level2()
        print(json.dumps({"level2": {"n_matched": lvl2["n_matched"], "matched": lvl2["matched"]}}))
        if "--level2" in args and not any(a.isdigit() for a in args):
            return 0
    n = None
    for a in args:
        if a.isdigit():
            n = int(a)
    body = write_cumulative(n)
    print(json.dumps({"cumulative_n": body["n_valid"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
