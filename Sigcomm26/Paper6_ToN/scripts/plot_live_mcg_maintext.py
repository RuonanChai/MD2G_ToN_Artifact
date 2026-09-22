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

"""Fair live MCG main-text 1×3. Authoritative cells only. No offline MCG. No Rolling."""
import csv
import hashlib
import json
import math
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
FIG = TON / "Figures"
sys.path.insert(0, str(FIG))
from _fig_v3 import apply_v3, style_ax  # noqa: E402

DEV_JSON = TON / "final" / "COMMAND153_FIGURE_SOURCE_DATA" / "dev.json"
ART = TON / "artifacts" / "ton_live_mcg"
FAIR = TON / "results" / "live_mcg_baseline" / "fairness_check.json"
OUT_PDF = FIG / "QoE" / "Live_MCG_Fair_Mechanism_1x3.pdf"
OUT_DIR = TON / "results" / "live_mcg_maintext"
SUMMARY = OUT_DIR / "live_mcg_maintext_summary.csv"
PROV = OUT_DIR / "live_mcg_maintext_provenance.json"
OFFLINE_MCG = TON / "results" / "mcg_baseline"

USERS = (20, 60, 100)
NETS = ("4g", "wifi", "fiber_optic")
SEEDS = (151, 152, 153)
CONTENT = "redandblack"
STRATS = (
    ("MD2G-Cast", "MD2G_COMPONENT", "#0072B2", "-", "o"),
    ("MCG", "MCG_COMPONENT", "#666666", "-", "D"),
    ("Heuristic", "HV3_COMPONENT", "#D89000", "--", "s"),
    ("Clustering", "CLUSTERING_COMPONENT", "#009E73", "-.", "^"),
    ("Rule", "RULE_COMPONENT", "#CC79A7", ":", "v"),
)
U_WEIGHTS = (0.25, 0.60, 0.15)
NATIVE_W, NATIVE_H = 7.00, 2.20
COMMON_LW = 1.35
COMMON_MS = 4.6
SOURCE_FONT = 9.5
INCLUDE_FRAC = 0.97


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def completion_scalar(metrics: dict) -> float:
    cf = metrics.get("component_completion_fraction") or {}
    nums = dens = 0
    if isinstance(cf, dict):
        for rec in cf.values():
            if not isinstance(rec, dict):
                continue
            dens += int(rec.get("n_receivers") or 0)
            nums += int(rec.get("n_complete_dump_gt_64") or 0)
    if dens <= 0:
        raise SystemExit("COMPLETION_DENOM_ZERO")
    return nums / dens


def bootstrap_ci(vals: list[float], seed: int = 153) -> tuple[float, float]:
    n = len(vals)
    rng = random.Random(seed)
    means = []
    for _ in range(2000):
        s = [vals[rng.randrange(n)] for _ in range(n)]
        means.append(sum(s) / n)
    means.sort()
    return means[int(0.025 * 2000)], means[int(0.975 * 2000) - 1]


def load_frozen_slice() -> dict[tuple, dict]:
    rows = json.loads(DEV_JSON.read_text())
    out = {}
    for r in rows:
        if r.get("content") != CONTENT:
            continue
        if r.get("network") not in NETS:
            continue
        if int(r.get("users") or 0) not in USERS:
            continue
        if int(r.get("seed") or 0) not in SEEDS:
            continue
        s = r.get("strategy")
        if s not in ("MD2G_COMPONENT", "HV3_COMPONENT", "CLUSTERING_COMPONENT", "RULE_COMPONENT"):
            continue
        key = (s, r["network"], int(r["users"]), int(r["seed"]))
        out[key] = r
    want = 4 * 3 * 3 * 3
    if len(out) != want:
        raise SystemExit(f"FROZEN_SLICE_INCOMPLETE n={len(out)} want={want}")
    return out


def load_live_mcg() -> dict[tuple, dict]:
    if not FAIR.is_file():
        raise SystemExit("MISSING_FAIRNESS_CHECK")
    fair = json.loads(FAIR.read_text())
    if fair.get("pass") is not True or int(fair.get("n_mcg_valid") or 0) != 27:
        raise SystemExit(f"FAIRNESS_NOT_PASS {fair}")
    if list(fair.get("seeds") or []) != list(SEEDS):
        raise SystemExit("SEED_MISMATCH")
    if list(fair.get("networks") or []) != list(NETS):
        raise SystemExit("NET_MISMATCH")
    if list(fair.get("u_weights") or []) != list(U_WEIGHTS):
        raise SystemExit("U_WEIGHT_MISMATCH")
    out = {}
    for net in NETS:
        for users in USERS:
            for seed in SEEDS:
                key = f"c148mcg_{CONTENT}_{net}_u{users}_MCG_COMPONENT_s{seed}"
                cell = ART / key
                done_p = cell / "CELL_DONE.json"
                met_p = cell / "CELL_METRICS.json"
                mcg_p = cell / "COMMAND148_MCG_DECISION.jsonl"
                stu = cell / "COMMAND148_STUDENT_INFERENCE.jsonl"
                if not done_p.is_file() or not met_p.is_file():
                    raise SystemExit(f"MISSING_LIVE_CELL {key}")
                done = json.loads(done_p.read_text())
                met = json.loads(met_p.read_text())
                if done.get("valid") is not True or (done.get("audit") or {}).get("pass") is not True:
                    raise SystemExit(f"CELL_NOT_VALID {key}")
                if met.get("strategy") != "MCG_COMPONENT":
                    raise SystemExit(f"WRONG_STRATEGY {key}")
                if not mcg_p.is_file() or mcg_p.stat().st_size <= 0:
                    raise SystemExit(f"NO_MCG_DECISION {key}")
                if stu.is_file() and stu.stat().st_size > 0:
                    raise SystemExit(f"MCG_USED_STUDENT {key}")
                if "component_completion_fraction" not in met:
                    raise SystemExit(f"NO_COMPLETION_FIELD {key}")
                out[("MCG_COMPONENT", net, users, seed)] = {
                    "U": float(met["U"]),
                    "Rq": float(met["Rq"]),
                    "Ro_component": float(met["Ro_component"]),
                    "Rb": float(met["Rb"]),
                    "decoded_completion": completion_scalar(met),
                    "key": key,
                    "source": str(met_p),
                }
    if len(out) != 27:
        raise SystemExit(f"LIVE_MCG_INCOMPLETE n={len(out)}")
    return out


def refuse_offline() -> None:
    # Must not read plotted values from the stale offline pack.
    if not OFFLINE_MCG.is_dir():
        return
    # Presence is fine; using it as source is not. Guard by never opening those CSVs.


def collect_series(frozen: dict, mcg: dict) -> dict:
    buckets: dict[tuple[str, int, str], list[float]] = {}
    for label, code, *_rest in STRATS:
        for users in USERS:
            for metric in ("U", "Rq", "decoded_completion"):
                vals = []
                for net in NETS:
                    for seed in SEEDS:
                        if code == "MCG_COMPONENT":
                            rec = mcg[(code, net, users, seed)]
                        else:
                            rec = frozen[(code, net, users, seed)]
                        if metric == "decoded_completion":
                            if code == "MCG_COMPONENT":
                                vals.append(float(rec["decoded_completion"]))
                            else:
                                vals.append(completion_scalar(rec))
                        elif metric == "Rq":
                            vals.append(float(rec["Rq"]))
                        else:
                            vals.append(float(rec["U"]))
                if len(vals) != 9:
                    raise SystemExit(f"BLOCK_COUNT {label} u={users} {metric} n={len(vals)}")
                buckets[(label, users, metric)] = vals
    return buckets


def summarize(buckets: dict) -> list[dict]:
    rows = []
    for label, _code, *_r in STRATS:
        for users in USERS:
            rec = {"strategy": label, "users": users, "n": 9, "fair_same_substrate": True}
            for metric in ("U", "Rq", "decoded_completion"):
                vals = buckets[(label, users, metric)]
                lo, hi = bootstrap_ci(vals)
                rec[f"{metric}_mean"] = sum(vals) / len(vals)
                rec[f"{metric}_ci95_lo"] = lo
                rec[f"{metric}_ci95_hi"] = hi
            rows.append(rec)
    return rows


def plot(rows: list[dict]) -> None:
    apply_v3()
    plt.rcParams.update(
        {
            "font.size": SOURCE_FONT,
            "axes.labelsize": SOURCE_FONT,
            "axes.titlesize": SOURCE_FONT,
            "xtick.labelsize": SOURCE_FONT,
            "ytick.labelsize": SOURCE_FONT,
            "legend.fontsize": SOURCE_FONT,
            "figure.titlesize": SOURCE_FONT,
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(NATIVE_W, NATIVE_H))
    fig.subplots_adjust(left=0.108, right=0.988, bottom=0.22, top=0.80, wspace=0.58)
    xs = np.array(USERS, dtype=float)
    panels = (
        ("U", "Utility U", (0.35, 0.90), axes[0]),
        ("Rq", "Quality Rq", (0.25, 1.02), axes[1]),
        ("decoded_completion", "Completion", (0.50, 1.02), axes[2]),
    )
    handles = []
    labels = []
    by = {(r["strategy"], int(r["users"])): r for r in rows}
    for metric, ylab, ylim, ax in panels:
        for label, _code, color, ls, mk in STRATS:
            ys = [by[(label, u)][f"{metric}_mean"] for u in USERS]
            ylo = [by[(label, u)][f"{metric}_mean"] - by[(label, u)][f"{metric}_ci95_lo"] for u in USERS]
            yhi = [by[(label, u)][f"{metric}_ci95_hi"] - by[(label, u)][f"{metric}_mean"] for u in USERS]
            line = ax.errorbar(
                xs,
                ys,
                yerr=np.vstack([ylo, yhi]),
                color=color,
                linestyle=ls,
                marker=mk,
                linewidth=COMMON_LW,
                markersize=COMMON_MS,
                capsize=2.2,
                elinewidth=0.8,
                alpha=1.0,
                label=label,
            )
            if metric == "U":
                handles.append(line)
                labels.append(label)
        ax.set_xticks(USERS)
        ax.set_xlim(12, 108)
        ax.set_ylim(*ylim)
        ax.set_xlabel("")
        ax.set_ylabel(ylab, labelpad=6)
        ax.set_title("")
        style_ax(ax)
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.94),
        ncol=5,
        frameon=False,
        columnspacing=1.55,
        handletextpad=0.40,
        handlelength=1.9,
    )
    fig.supxlabel("Receivers", fontsize=SOURCE_FONT, y=0.02)
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, format="pdf", bbox_inches=None, pad_inches=0.0)
    plt.close(fig)


def validate_pdf() -> dict:
    info = subprocess.check_output(["pdfinfo", str(OUT_PDF)], text=True)
    pages = fonts = None
    w_pt = h_pt = None
    for ln in info.splitlines():
        if ln.startswith("Pages:"):
            pages = int(ln.split(":")[1])
        if ln.startswith("Page size"):
            parts = ln.split(":")[1].strip().split()
            w_pt, h_pt = float(parts[0]), float(parts[2])
    font_txt = subprocess.check_output(["pdffonts", str(OUT_PDF)], text=True)
    if "Type 3" in font_txt:
        raise SystemExit("TYPE3_FONT")
    if "Liberation" not in font_txt and "Arial" not in font_txt and "Helvetica" not in font_txt and "Nimbus" not in font_txt and "DejaVu" not in font_txt:
        # fonttype 42 embeds TrueType; name may be LiberationSans
        if "TrueType" not in font_txt and "Type 1" not in font_txt:
            raise SystemExit(f"NO_VECTOR_FONT {font_txt}")
    w_in, h_in = w_pt / 72.0, h_pt / 72.0
    if pages != 1:
        raise SystemExit(f"NOT_ONE_PAGE {pages}")
    if abs(w_in - NATIVE_W) / NATIVE_W > 0.015:
        raise SystemExit(f"SIZE_MISMATCH {w_in:.3f}x{h_in:.3f}")
    if not (2.15 - 1e-6 <= h_in <= 2.25 + 1e-6):
        raise SystemExit(f"HEIGHT_NOT_FLAT {h_in:.3f}")
    import pymupdf

    page = pymupdf.open(OUT_PDF)[0]
    pr = page.rect
    sizes = []
    texts = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            for span in line.get("spans") or []:
                text = (span.get("text") or "").strip()
                if not text:
                    continue
                texts.append(text)
                sz = float(span.get("size") or 0)
                sizes.append(sz)
                x0, y0, x1, y1 = span["bbox"]
                if x0 < pr.x0 - 0.4 or y0 < pr.y0 - 0.4 or x1 > pr.x1 + 0.4 or y1 > pr.y1 + 0.4:
                    raise SystemExit(f"CLIPPED_SPAN {text!r} bbox={span['bbox']}")
    joined = " ".join(texts)
    if "(a)" in joined or "(b)" in joined or "(c)" in joined:
        raise SystemExit(f"PANEL_LABELS_PRESENT {texts}")
    if "Rule" not in texts:
        raise SystemExit("RULE_MISSING_FROM_LEGEND")
    raw = OUT_PDF.read_bytes()
    if b"Rolling" in raw:
        raise SystemExit("ROLLING_IN_PDF")
    if b"offline" in raw.lower():
        raise SystemExit("OFFLINE_IN_PDF")
    if b"#8C2D04" in raw or b"8C2D04" in raw:
        raise SystemExit("MCG_OLD_BROWN_PRESENT")
    return {
        "pages": pages,
        "width_in": w_in,
        "height_in": h_in,
        "width_pt": w_pt,
        "height_pt": h_pt,
        "source_font_min": min(sizes) if sizes else None,
        "source_font_max": max(sizes) if sizes else None,
        "source_texts": texts,
        "pdffonts": font_txt,
        "intended_include": r"figure* width=0.97\textwidth",
        "sha256": sha256_file(OUT_PDF),
    }


def patch_provenance(pdf: dict, inclusion: dict) -> None:
    if not PROV.is_file():
        raise SystemExit("MISSING_PROVENANCE")
    body = json.loads(PROV.read_text())
    body["generated_pdf"] = str(OUT_PDF)
    body["generated_pdf_sha256"] = pdf["sha256"]
    body["pdfinfo"] = {
        "pages": pdf["pages"],
        "width_in": pdf["width_in"],
        "height_in": pdf["height_in"],
        "width_pt": pdf["width_pt"],
        "height_pt": pdf["height_pt"],
    }
    body["font_contract"] = pdf["intended_include"]
    body["strategies_included"] = [s[0] for s in STRATS]
    body["n_frozen_same_slice"] = 108
    body["presentation_revision"] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source_font_min": pdf["source_font_min"],
        "source_font_max": pdf["source_font_max"],
        "manuscript_textwidth_pt": inclusion["textwidth_pt"],
        "inclusion_width": "0.97\\textwidth",
        "inclusion_scale": inclusion["scale"],
        "effective_font_min": inclusion["eff_min"],
        "effective_font_max": inclusion["eff_max"],
        "compiled_pdf": inclusion.get("compiled_pdf"),
    }
    PROV.write_text(json.dumps(body, indent=2) + "\n")


def main() -> int:
    refuse_offline()
    frozen = load_frozen_slice()
    mcg = load_live_mcg()
    buckets = collect_series(frozen, mcg)
    rows = summarize(buckets)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with SUMMARY.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    plot(rows)
    pdf = validate_pdf()
    inclusion = {"textwidth_pt": None, "scale": None, "eff_min": None, "eff_max": None}
    patch_provenance(pdf, inclusion)
    print(json.dumps({"pass": True, "pdf": str(OUT_PDF), "sha256": pdf["sha256"], "size_in": [pdf["width_in"], pdf["height_in"]], "source_font": [pdf["source_font_min"], pdf["source_font_max"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
