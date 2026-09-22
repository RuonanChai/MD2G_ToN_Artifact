# FIGURE_VISUAL_REDESIGN_V5_AUDIT

Authority: frozen COMMAND153 evidence only. No re-runs. Filenames, directories,
scientific values, aggregations, and claims unchanged.

Terminal: `TON_FINAL_FIGURE_VISUAL_REDESIGN_V5_READY`

Contact sheets:
- `Figures/FIGURE_VISUAL_REDESIGN_V5_CONTACT_SHEET_ALL.pdf`
- `Figures/FIGURE_VISUAL_REDESIGN_V5_CONTACT_SHEET_PAPER_ORDER.pdf`

Invariant check: `SCIENTIFIC_INVARIANT_CHECKS_PASS`

---

## Paper-order (MAIN_TEXT)

1. Topology / system diagram (external)
2. `QoE_By_Strategy.pdf`
3. `System_Utility_By_Users_scheme1.pdf`
4. Robustness: `QoE_By_Content_DeltaU.pdf` + `QoE_By_Network.pdf`
5. Holdout/mechanism: `Loot_Holdout_DeltaU_By_Users.pdf` + `Mechanism_Decomposition_Loot.pdf`
6. Architecture: `MoQ_Shared_vs_Unicast.pdf` + `H2_Cross_Stack_DASH.pdf`
7. Throughput 1×3: 4G / 5G / Default Mix
8. Optional representative Rb–U: `TierB_Rb_vs_U_Default_Mix.pdf` (red-star MD2G + Better)

Excluded from main text: MainDev bars; remaining throughput; remaining Rb–U; Weak_User_Rq (appendix).

---

## Per-figure QA

| File | Role | Family | Placement | Values | Clip | Legend | Outside WS% | Vector |
|---|---|---|---|---|---|---|---|---|
| `QoE/QoE_By_Strategy.pdf` | overall U ECDF | ECDF | **MAIN_TEXT** | yes | PASS | PASS | 4.7 | PASS |
| `Buffer Level/System_Utility_By_Users_scheme1.pdf` | concurrency scaling | multi-line | **MAIN_TEXT** | yes | PASS | PASS | 3.7 | PASS |
| `Buffer Level/System_Utility_By_Users_MainDev.pdf` | MAINDEV ranking | ranked bars | **APPENDIX** | yes | PASS | PASS | 1.4 | PASS |
| `QoE/QoE_By_Content_DeltaU.pdf` | content×load ΔU | connected effect strip | **MAIN_TEXT** | yes | PASS | PASS | 3.6 | PASS |
| `QoE/QoE_By_Network.pdf` | network×load ΔU | diverging heatmap | **MAIN_TEXT** | yes | PASS | PASS | 3.2 | PASS |
| `QoE/Loot_Holdout_DeltaU_By_Users.pdf` | Loot holdout ΔU | connected-dot | **MAIN_TEXT** | yes | PASS | PASS | 1.3 | PASS |
| `QoE/Mechanism_Decomposition_Loot.pdf` | Loot ΔU decomposition | signed stacked | **MAIN_TEXT** | yes | PASS | PASS | 1.8 | PASS |
| `QoE/MoQ_Shared_vs_Unicast.pdf` | shared vs unicast | dumbbell | **MAIN_TEXT** | yes | PASS | PASS | 4.9 | PASS |
| `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf` | cross-stack DASH | method dot strip | **MAIN_TEXT** | yes | PASS | PASS | 3.9 | PASS |
| `QoE/Weak_User_Rq_Loot.pdf` | weak-user Rq | 3-panel ECDF | **APPENDIX** | yes | PASS | PASS | 3.1 | PASS |
| `Throughput/System_Throughput_Bar_4G.pdf` | throughput 4G | multi-line | **MAIN_TEXT** | yes | PASS | PASS | 3.9 | PASS |
| `Throughput/System_Throughput_Bar_5G.pdf` | throughput 5G | multi-line | **MAIN_TEXT** | yes | PASS | PASS | 3.9 | PASS |
| `Throughput/System_Throughput_Bar_Default_Mix.pdf` | throughput Default Mix | multi-line | **MAIN_TEXT** | yes | PASS | PASS | 3.9 | PASS |
| `Throughput/System_Throughput_Bar_Wifi.pdf` | throughput Wi-Fi | multi-line | **APPENDIX** | yes | PASS | PASS | 3.9 | PASS |
| `Throughput/System_Throughput_Bar_Fiber_Optic.pdf` | throughput Fiber | multi-line | **APPENDIX** | yes | PASS | PASS | 3.9 | PASS |
| `Throughput/System_Throughput_Bar_5G_Dominant.pdf` | throughput 5G Dom | multi-line | **APPENDIX** | yes | PASS | PASS | 3.9 | PASS |
| `Throughput/System_Throughput_Bar_Wifi_Dominant.pdf` | throughput Wi-Fi Dom | multi-line | **APPENDIX** | yes | PASS | PASS | 3.9 | PASS |
| `User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf` | Rb–U trade-off 4G | trade-off scatter | **SUPPORTING_ONLY** | yes | PASS | PASS | 5.0 | PASS |
| `User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf` | Rb–U trade-off 5G | trade-off scatter | **SUPPORTING_ONLY** | yes | PASS | PASS | 5.0 | PASS |
| `User_Experience_Trade-off/TierB_Rb_vs_U_WiFi.pdf` | Rb–U trade-off Wi-Fi | trade-off scatter | **SUPPORTING_ONLY** | yes | PASS | PASS | 5.0 | PASS |
| `User_Experience_Trade-off/TierB_Rb_vs_U_Fiber_Optic.pdf` | Rb–U trade-off Fiber | trade-off scatter | **SUPPORTING_ONLY** | yes | PASS | PASS | 5.0 | PASS |
| `User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf` | Rb–U trade-off Default Mix (representative) | trade-off scatter | **MAIN_TEXT** | yes | PASS | PASS | 5.0 | PASS |

---

## TierB Rb–U special checks

| File | Red star | Better↑← | Users legend | Strategy legend | No overlap |
|---|---|---|---|---|---|
| `User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf` | PASS | PASS | PASS | PASS | PASS |
| `User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf` | PASS | PASS | PASS | PASS | PASS |
| `User_Experience_Trade-off/TierB_Rb_vs_U_WiFi.pdf` | PASS | PASS | PASS | PASS | PASS |
| `User_Experience_Trade-off/TierB_Rb_vs_U_Fiber_Optic.pdf` | PASS | PASS | PASS | PASS | PASS |
| `User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf` | PASS | PASS | PASS | PASS | PASS |

---

## V5 deltas vs V4

- Mechanism: proxy legend (exactly four entries); bars use `_nolegend_`.
- Throughput: keep line family; MD2G LW≈2.0, baselines ≈1.6; smaller markers.
- MainDev: thinner bars, tighter spacing; APPENDIX only (not in PAPER_ORDER sheet).
- TierB Rb–U: landscape; red five-point MD2G star; Better arrow; fig-level strategy legend;
  corner-chosen user-size legend; trajectories; fixed canvas save (no legend crop).
- MD2G red star is trade-off-only (not global).

Representative Rb–U for main text: **Default Mix** (central mixed access profile),
not selected by largest MD2G win.

## Aggregate

QA_ISSUES: none

V5_VISUAL_QA_PASS

