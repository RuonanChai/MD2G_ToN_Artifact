# ToN final paper figures — Sigcomm folder layout

Style authority: `paper_figures/Sigcomm/` (fonts/colors/layout locked).
Data authority: `final/COMMAND153_FIGURE_SOURCE_DATA/` + frozen COMMAND153 tokens.

## Folder map (mirrors Sigcomm)

| Folder | Scripts | Primary PDFs |
|--------|---------|--------------|
| **QoE/** | `plot_qoe_by_strategy.py`, `plot_qoe_by_network.py`, … | `QoE_By_Strategy.pdf`, `QoE_By_Network.pdf`, `Loot_Holdout_DeltaU_By_Users.pdf` |
| **Buffer Level/** | `plot_buffer_level_by_users.py` (crossover), `plot_buffer_level_by_strategy.py`, `plot_maindev_utility_by_users.py` | `Buffer_Level_By_Users_scheme1.pdf` (alias), `System_Utility_By_Users_scheme*.pdf` |
| **Stall Time/** | `plot_stall_time_by_{strategy,network,users}.py` | `Stall_Time_By_*.pdf` |
| **Throughput/** | `plot_throughput_{4g,5g,wifi,...}.py` | `System_Throughput_Bar_*.pdf` |
| **User_Experience_Trade-off/** | `plot_tradeoff_{network}.py`, `plot_h2_cross_stack_dash.py` | `User_Experience_Trade-off_*.pdf`, `H2_Cross_Stack_DASH.pdf` |

Skipped categories: see `SKIPPED_FIGURES.md` (TTFB, CPU usage, FoV — no frozen final evidence or NOT_APPLICABLE).

Shared loader: `_fig_evidence.py` (root of this tree).

## Run all

```bash
cd Sigcomm26/Paper6_ToN/Figures
PY=../.venv_sigcomm/bin/python3
find . -name 'plot_*.py' ! -path './_*' | sort | while read s; do $PY -u "$s"; done
$PY -u generate_paper_artifacts.py
```

Terminal: `PAPER_FINALIZATION_FIGURES_READY.json`
