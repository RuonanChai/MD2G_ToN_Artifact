#!/usr/bin/env python3
"""Generate per-network Throughput plot scripts (line scaling; filenames keep Bar)."""
from __future__ import annotations

from pathlib import Path

TEMPLATE = '''#!/usr/bin/env python3
"""Shared-root TX throughput vs users ({net_title}). Filename retains Bar for identity."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_style import plot_throughput_network  # noqa: E402

NETWORK = "{net_key}"
OUT = Path(__file__).resolve().parent / "System_Throughput_Bar_{net_title}.pdf"


def main() -> int:
    plot_throughput_network(NETWORK, OUT)
    print(f"Wrote {{OUT}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

NETS = [
    ("4g", "4G"),
    ("5g", "5G"),
    ("wifi", "Wifi"),
    ("fiber_optic", "Fiber_Optic"),
    ("default_mix", "Default_Mix"),
    ("5g_dominant", "5G_Dominant"),
    ("wifi_dominant", "Wifi_Dominant"),
]


def main() -> int:
    out_dir = Path(__file__).resolve().parent
    for net_key, net_title in NETS:
        path = out_dir / f"plot_throughput_{net_key}.py"
        path.write_text(TEMPLATE.format(net_key=net_key, net_title=net_title))
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
