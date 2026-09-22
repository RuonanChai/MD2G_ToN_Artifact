#!/usr/bin/env python3
"""V5 contact sheets: ALL figures + PAPER_ORDER main-text only."""
from __future__ import annotations

import subprocess
from pathlib import Path

from pypdf import PdfReader, PdfWriter

FIG = Path(__file__).resolve().parent
OUT_ALL = FIG / "FIGURE_VISUAL_REDESIGN_V5_CONTACT_SHEET_ALL.pdf"
OUT_PAPER = FIG / "FIGURE_VISUAL_REDESIGN_V5_CONTACT_SHEET_PAPER_ORDER.pdf"

ALL_FILES = [
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

# Manuscript visual order (no MainDev; throughput only 1×3 trio; one Rb–U)
PAPER_ORDER = [
    "QoE/QoE_By_Strategy.pdf",
    "Buffer Level/System_Utility_By_Users_scheme1.pdf",
    "QoE/QoE_By_Content_DeltaU.pdf",
    "QoE/QoE_By_Network.pdf",
    "QoE/Loot_Holdout_DeltaU_By_Users.pdf",
    "QoE/Mechanism_Decomposition_Loot.pdf",
    "QoE/MoQ_Shared_vs_Unicast.pdf",
    "User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf",
    "Throughput/System_Throughput_Bar_4G.pdf",
    "Throughput/System_Throughput_Bar_5G.pdf",
    "Throughput/System_Throughput_Bar_Default_Mix.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf",
]


def page_size_in(path: Path) -> tuple[float, float]:
    info = subprocess.check_output(["pdfinfo", str(path)], text=True)
    for ln in info.splitlines():
        if ln.startswith("Page size"):
            parts = ln.split(":")[1].strip().split()
            return float(parts[0]) / 72.0, float(parts[2]) / 72.0
    raise SystemExit(f"NO_PAGE_SIZE {path}")


def write_sheet(files: list[str], out: Path, title: str) -> None:
    writer = PdfWriter()
    print(title)
    for rel in files:
        path = FIG / rel
        if not path.is_file():
            raise SystemExit(f"MISSING {rel}")
        w, h = page_size_in(path)
        print(f"  {rel:56s}  {w:.2f}x{h:.2f} in")
        reader = PdfReader(str(path))
        writer.add_page(reader.pages[0])
        writer.add_outline_item(rel, len(writer.pages) - 1)
    writer.write(str(out))
    print(f"Wrote {out} pages={len(writer.pages)}")


def main() -> int:
    write_sheet(ALL_FILES, OUT_ALL, "V5 ALL contact sheet")
    write_sheet(PAPER_ORDER, OUT_PAPER, "V5 PAPER_ORDER contact sheet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
