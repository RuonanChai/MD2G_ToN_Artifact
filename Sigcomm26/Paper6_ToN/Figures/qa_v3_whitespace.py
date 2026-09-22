#!/usr/bin/env python3
"""V3 whitespace + annotation QA for regenerated final PDFs."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

FIG = Path(__file__).resolve().parent
FORBIDDEN = [
    "better",
    "estimated transition",
    "Lower TX is not efficiency",
    "W/T/L",
    "higher is better",
    "lower is better",
]

PDFS = [
    "QoE/QoE_By_Strategy.pdf",
    "Buffer Level/System_Utility_By_Users_scheme1.pdf",
    "Buffer Level/System_Utility_By_Users_MainDev.pdf",
    "QoE/QoE_By_Content_DeltaU.pdf",
    "QoE/QoE_By_Network.pdf",
    "QoE/Loot_Holdout_DeltaU_By_Users.pdf",
    "QoE/Mechanism_Decomposition_Loot.pdf",
    "QoE/MoQ_Shared_vs_Unicast.pdf",
    "User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf",
    "QoE/Weak_User_Rq_Loot.pdf",
    "Throughput/System_Throughput_Bar_4G.pdf",
    "Throughput/System_Throughput_Bar_5G.pdf",
    "Throughput/System_Throughput_Bar_Default_Mix.pdf",
    "Throughput/System_Throughput_Bar_Wifi.pdf",
    "Throughput/System_Throughput_Bar_Fiber_Optic.pdf",
    "Throughput/System_Throughput_Bar_5G_Dominant.pdf",
    "Throughput/System_Throughput_Bar_Wifi_Dominant.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_WiFi.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_Fiber_Optic.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf",
]


def whitespace_frac(pdf: Path) -> float:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "p"
        subprocess.check_call(["pdftoppm", "-png", "-r", "150", str(pdf), str(out)], stdout=subprocess.DEVNULL)
        pngs = sorted(Path(td).glob("*.png"))
        if not pngs:
            raise SystemExit(f"NO_PNG {pdf}")
        arr = np.asarray(Image.open(pngs[0]).convert("RGB"))
    ink = np.any(arr < 250, axis=2)
    if not ink.any():
        return 1.0
    rows = np.where(ink.any(axis=1))[0]
    cols = np.where(ink.any(axis=0))[0]
    h, w = ink.shape
    bbox = (rows[-1] - rows[0] + 1) * (cols[-1] - cols[0] + 1)
    return 1.0 - (bbox / float(h * w))


def pdf_text(pdf: Path) -> str:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # type: ignore
    doc = fitz.open(pdf)
    return "\n".join(page.get_text() for page in doc)


def main() -> int:
    fails = []
    rows = []
    for rel in PDFS:
        p = FIG / rel
        ws = whitespace_frac(p)
        text = pdf_text(p)
        bad = [s for s in FORBIDDEN if s.lower() in text.lower()]
        fonts = subprocess.check_output(["pdffonts", str(p)], text=True)
        vector_ok = "Type 3" not in fonts
        print(f"{rel:56s}  ws={100*ws:5.1f}%  vector={vector_ok}  bad={bad or '-'}")
        rows.append((rel, ws, vector_ok, bad))
        if ws > 0.30:
            fails.append(f"WHITESPACE {rel} {100*ws:.1f}%")
        if bad:
            fails.append(f"ANNOTATION {rel} {bad}")
        if not vector_ok:
            fails.append(f"NOT_VECTOR {rel}")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("V3_WHITESPACE_AND_ANNOTATION_QA_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
