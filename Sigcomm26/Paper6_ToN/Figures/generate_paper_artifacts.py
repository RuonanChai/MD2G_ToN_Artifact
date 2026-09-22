#!/usr/bin/env python3
"""Emit FINAL_LATEX_NUMBERS.tex, claim matrix, and recursive figure manifest."""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from _fig_evidence import (
    FIG,
    SAME_STRATEGIES,
    load_cross_stack_dash_u,
    load_primary_stats,
    load_rows,
    matched_blocks_delta_by_users,
    matched_delta_by_users,
    mean_std,
    require_frozen_evidence,
)

ROUND_U = 3


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fmt_u(x: float) -> str:
    return f"{x:.{ROUND_U}f}"


def iter_plot_scripts() -> list[Path]:
    out = []
    for p in sorted(FIG.rglob("plot_*.py")):
        if p.name.startswith("_"):
            continue
        out.append(p)
    return out


def pdf_for_script(py: Path) -> Path | None:
    d = py.parent
    stem = py.stem
    if stem.startswith("plot_qoe_by_strategy"):
        return d / "QoE_By_Strategy.pdf"
    if stem.startswith("plot_qoe_by_network"):
        return d / "QoE_By_Network.pdf"
    if stem.startswith("plot_buffer_level_by_users"):
        return d / "Buffer_Level_By_Users_scheme1.pdf"
    if stem.startswith("plot_buffer_level_by_strategy"):
        return d / "Buffer_Level_By_Strategy_scheme1.pdf"
    # default: any pdf in same dir modified after script or matching prefix
    candidates = sorted(d.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def main() -> int:
    require_frozen_evidence()
    stats = load_primary_stats()
    mb_by_u = matched_blocks_delta_by_users()
    loot_by_u = matched_delta_by_users(load_rows("loot.json"))
    scale_delta = matched_delta_by_users(load_rows("scaling.json"))

    lines = [
        "% AUTO-GENERATED from frozen COMMAND153 final evidence — do not hand-edit",
        f"% ts={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "\\newcommand{\\MetricUWeightRo}{0.25}",
        "\\newcommand{\\MetricUWeightRq}{0.60}",
        "\\newcommand{\\MetricUWeightRb}{0.15}",
        f"\\newcommand{{\\MainDevMeanDeltaU}}{{{fmt_u(float(stats['mean_delta_U_vs_strongest_same']))}}}",
        f"\\newcommand{{\\MainDevMDTwoGU}}{{{fmt_u(float(stats['dev_by_strategy']['MD2G_COMPONENT']['U']))}}}",
        f"\\newcommand{{\\LootMDTwoGU}}{{{fmt_u(float(stats['loot_by_strategy']['MD2G_COMPONENT']['U']))}}}",
    ]
    for users in (20, 60, 100):
        lines.append(f"\\newcommand{{\\MainDevDeltaUu{users}}}{{{fmt_u(mean_std(mb_by_u[users])[0])}}}")
        lines.append(f"\\newcommand{{\\LootDeltaUu{users}}}{{{fmt_u(mean_std(loot_by_u[users])[0])}}}")
    for users in (10, 20, 40, 60, 100):
        lines.append(f"\\newcommand{{\\ScalingDeltaUu{users}}}{{{fmt_u(mean_std(scale_delta[users])[0])}}}")
    lines.append(f"\\newcommand{{\\EpochId}}{{C152\\_RBV1}}")
    (FIG / "FINAL_LATEX_NUMBERS.tex").write_text("\n".join(lines) + "\n")

    claims = [
        {
            "claim_id": "C004",
            "exact_claim": "Concurrency crossover: low u10/u20 unfavorable, u40 transition, u60/u100 favorable.",
            "status": "supported",
            "source_artifact": "final/COMMAND153_FIGURE_SOURCE_DATA/scaling.json",
            "figure_table": "Buffer Level/Buffer_Level_By_Users_scheme1.pdf",
            "exact_final_value": ", ".join(f"u{u} {fmt_u(mean_std(scale_delta[u])[0])}" for u in (10, 20, 40, 60, 100)),
        },
        {
            "claim_id": "C003",
            "exact_claim": "MD2G robust benefit at u>=60 on unseen Loot holdout.",
            "status": "limited",
            "source_artifact": "final/COMMAND153_FIGURE_SOURCE_DATA/loot.json",
            "figure_table": "QoE/Loot_Holdout_DeltaU_By_Users.pdf",
            "exact_final_value": f"u60 {fmt_u(mean_std(loot_by_u[60])[0])}, u100 {fmt_u(mean_std(loot_by_u[100])[0])}",
        },
    ]
    (FIG / "FINAL_CLAIM_EVIDENCE_MATRIX.json").write_text(
        json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "claims": claims}, indent=2) + "\n"
    )

    manifest = {"ts": datetime.now(timezone.utc).isoformat(), "figures": []}
    md = ["# FINAL figure manifest (Sigcomm folder layout)", ""]
    for py in iter_plot_scripts():
        pdfs = sorted(py.parent.glob("*.pdf"))
        pdf = pdfs[0] if len(pdfs) == 1 else next((p for p in pdfs if "scheme1" in p.name or p.stem.startswith(py.stem.replace("plot_", "").title())), pdfs[0] if pdfs else None)
        rel = py.relative_to(FIG)
        entry = {
            "folder": str(py.parent.relative_to(FIG)),
            "python_source": str(rel),
            "pdf": str(pdf.relative_to(FIG)) if pdf else None,
            "sha256_python": sha256_file(py),
            "sha256_pdf": sha256_file(pdf) if pdf and pdf.is_file() else None,
        }
        manifest["figures"].append(entry)
        md.append(f"- `{rel}` → `{entry['pdf']}`")
    (FIG / "FINAL_FIGURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (FIG / "FINAL_FIGURE_MANIFEST.md").write_text("\n".join(md) + "\n")
    print("Artifacts updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
