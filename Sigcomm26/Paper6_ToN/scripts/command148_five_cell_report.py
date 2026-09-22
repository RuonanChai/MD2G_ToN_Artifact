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

"""Cumulative paper-facing metrics after every 5 newly promoted canonical VALID cells."""
import json
import statistics
import sys
from pathlib import Path

TON = ton_root()
REPO = artifact_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import canary_rbv1_art, dump_dual, ts  # noqa: E402

ART = canary_rbv1_art()
REV = TON / "reviews" / "command148"


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    q = json.loads((REPO / "state" / "COMMAND148_CANARY120_QUEUE.json").read_text())
    done = list(q.get("completed") or [])
    rows = []
    for key in done:
        mp = ART / key / "CELL_METRICS.json"
        if not mp.is_file():
            continue
        raw = mp.read_text().strip()
        if raw in ("", "null"):
            continue
        try:
            m = json.loads(raw)
        except Exception:
            continue
        if not isinstance(m, dict) or m.get("U") is None:
            continue
        if m.get("paper_U_is_Rb0_projection"):
            continue
        rows.append(m)
    by_s: dict[str, list[float]] = {}
    for r in rows:
        by_s.setdefault(r["strategy"], []).append(float(r["U"]))
    means = {k: statistics.mean(v) for k, v in by_s.items() if v}
    body = {
        "ts": ts(),
        "n_valid": len(done),
        "n_with_metrics": len(rows),
        "mean_U_by_strategy": means,
        "rows": rows,
        "loot_sealed": True,
        "art": str(ART),
        "pre_rb_excluded": True,
    }
    out = REV / f"CUMULATIVE_METRICS_{len(done):03d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=2) + "\n")
    dump_dual("COMMAND148_CUMULATIVE_METRICS_LATEST.json", {k: body[k] for k in body if k != "rows"})
    md = [
        f"# COMMAND148 cumulative paper-facing metrics n={len(done)}",
        "",
        f"- ts: `{body['ts']}`",
        f"- VALID cells: {len(done)}",
        "- mean U by strategy:",
    ]
    for k, v in sorted(means.items()):
        md.append(f"  - `{k}`: {v:.4f}")
    md.append("- Loot network holdout remains sealed.")
    md.append("")
    (REV / f"CUMULATIVE_METRICS_{len(done):03d}.md").write_text("\n".join(md))
    print(json.dumps({"n": len(done), "means": means}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
