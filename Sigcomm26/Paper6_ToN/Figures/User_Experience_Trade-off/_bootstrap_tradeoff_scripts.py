#!/usr/bin/env python3
"""Generate per-network Rb–U trade-off scripts (scatter; existing filenames)."""
from __future__ import annotations

from pathlib import Path

TEMPLATE = '''#!/usr/bin/env python3
"""NOT Fig.4-family. Tier-B Rb vs U trade-off scatter ({net_label})."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_style import plot_rb_u_tradeoff  # noqa: E402

NETWORK = "{net_key}"
OUT = Path(__file__).resolve().parent / "TierB_Rb_vs_U_{net_title}.pdf"


def main() -> int:
    plot_rb_u_tradeoff(NETWORK, OUT)
    print(f"Wrote {{OUT}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

NETS = [
    ("4g", "4G", "4G"),
    ("5g", "5G", "5G"),
    ("wifi", "WiFi", "Wi-Fi"),
    ("fiber_optic", "Fiber_Optic", "Fiber Optic"),
    ("default_mix", "Default_Mix", "Default Mix"),
]


def main() -> int:
    out_dir = Path(__file__).resolve().parent
    for net_key, net_title, net_label in NETS:
        name = f"plot_tradeoff_{net_key}.py"
        (out_dir / name).write_text(
            TEMPLATE.format(net_key=net_key, net_title=net_title, net_label=net_label)
        )
        print(f"Wrote {out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
