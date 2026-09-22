#!/usr/bin/env python3
"""Diagnostic V2 contact sheet: each page is the figure at native paper size."""
from __future__ import annotations

import subprocess
from pathlib import Path

from pypdf import PdfReader, PdfWriter

FIG = Path(__file__).resolve().parent
OUT = FIG / "FIGURE_VISUAL_REDESIGN_V2_CONTACT_SHEET.pdf"

FILES = [
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


def page_size_in(path: Path) -> tuple[float, float]:
    info = subprocess.check_output(["pdfinfo", str(path)], text=True)
    for ln in info.splitlines():
        if ln.startswith("Page size"):
            # "Page size:       244.8 x 183.6 pts"
            parts = ln.split(":")[1].strip().split()
            w, h = float(parts[0]), float(parts[2])
            return w / 72.0, h / 72.0
    raise SystemExit(f"NO_PAGE_SIZE {path}")


def main() -> int:
    writer = PdfWriter()
    print("V2 contact sheet (native page sizes, not enlarged)")
    for rel in FILES:
        path = FIG / rel
        if not path.is_file():
            raise SystemExit(f"MISSING {path}")
        w, h = page_size_in(path)
        fonts = subprocess.check_output(["pdffonts", str(path)], text=True)
        bad = [ln for ln in fonts.splitlines()[2:] if ln.strip() and "Liberation" not in ln]
        print(f"  {rel:56s}  {w:.2f}x{h:.2f} in  fonts_ok={not bad}")
        reader = PdfReader(str(path))
        page = reader.pages[0]
        page.annotations = None
        writer.add_page(page)
        writer.add_outline_item(rel, len(writer.pages) - 1)
    writer.write(str(OUT))
    print(f"Wrote {OUT} pages={len(writer.pages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
