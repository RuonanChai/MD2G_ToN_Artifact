# FIGURE_VISUAL_REDESIGN_V4_AUDIT

Authority: frozen COMMAND153 evidence only. No re-runs. Filenames, directories,
scientific values, aggregations, and claims unchanged.

Terminal: `TON_FINAL_FIGURE_VISUAL_REDESIGN_V4_READY`

Contact sheet: `Figures/FIGURE_VISUAL_REDESIGN_V4_CONTACT_SHEET.pdf`

Invariant check: `SCIENTIFIC_INVARIANT_CHECKS_PASS` (`verify_visual_redesign_invariants.py`)

---

## V4 policy

- KEEP chart families that already match their scientific question (polish only).
- REDESIGN only four figures whose V3 grammar was redundant, sparse, or weaker.
- Deliberate visual rhythm for the main manuscript; not maximizing chart-type variety.

---

## Classification legend

| Tag | Meaning |
|---|---|
| `MAIN_TEXT` | Recommended in the primary manuscript figures |
| `APPENDIX` | Keep on disk; place in appendix / supporting material |
| `SUPPORTING_ONLY` | Valid evidence figure; not a primary claim vehicle |

---

## Per-figure audit

| File | Chart type (V4) | Action | Placement |
|---|---|---|---|
| `QoE/QoE_By_Strategy.pdf` | ECDF | KEEP + polish | **MAIN_TEXT** |
| `Buffer Level/System_Utility_By_Users_scheme1.pdf` | multi-line scaling | KEEP + polish | **MAIN_TEXT** (central concurrency) |
| `QoE/QoE_By_Content_DeltaU.pdf` | content×load connected effect strip | **REDESIGN** | **MAIN_TEXT** (robustness left) |
| `QoE/QoE_By_Network.pdf` | diverging heatmap (color only, no hatch) | KEEP + polish | **MAIN_TEXT** (robustness right) |
| `QoE/Loot_Holdout_DeltaU_By_Users.pdf` | zero-centered connected-dot | KEEP + polish | **MAIN_TEXT** (holdout left) |
| `QoE/Mechanism_Decomposition_Loot.pdf` | single-panel signed stacked contributions | **REDESIGN** | **MAIN_TEXT** (holdout/mechanism right) |
| `QoE/MoQ_Shared_vs_Unicast.pdf` | horizontal dumbbell | KEEP + polish | **MAIN_TEXT** (architecture left) |
| `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf` | two-row method dot strip | **REDESIGN** | **MAIN_TEXT** (architecture right) |
| `Throughput/System_Throughput_Bar_4G.pdf` | multi-line scaling | KEEP | **MAIN_TEXT** (throughput 1×3) |
| `Throughput/System_Throughput_Bar_5G.pdf` | multi-line scaling | KEEP | **MAIN_TEXT** (throughput 1×3) |
| `Throughput/System_Throughput_Bar_Default_Mix.pdf` | multi-line scaling | KEEP | **MAIN_TEXT** (throughput 1×3) |
| `Buffer Level/System_Utility_By_Users_MainDev.pdf` | 3-panel horizontal ranked bars | **REDESIGN** | **APPENDIX** |
| `QoE/Weak_User_Rq_Loot.pdf` | 3-panel ECDF | KEEP + polish | **APPENDIX** (unless space) |
| `Throughput/System_Throughput_Bar_Wifi.pdf` | multi-line scaling | KEEP | **APPENDIX** |
| `Throughput/System_Throughput_Bar_Fiber_Optic.pdf` | multi-line scaling | KEEP | **APPENDIX** |
| `Throughput/System_Throughput_Bar_5G_Dominant.pdf` | multi-line scaling | KEEP | **APPENDIX** |
| `Throughput/System_Throughput_Bar_Wifi_Dominant.pdf` | multi-line scaling | KEEP | **APPENDIX** |
| `User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf` | trade-off scatter | KEEP | **SUPPORTING_ONLY** / Appendix (at most one in Discussion) |
| `User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf` | trade-off scatter | KEEP | **SUPPORTING_ONLY** |
| `User_Experience_Trade-off/TierB_Rb_vs_U_WiFi.pdf` | trade-off scatter | KEEP | **SUPPORTING_ONLY** |
| `User_Experience_Trade-off/TierB_Rb_vs_U_Fiber_Optic.pdf` | trade-off scatter | KEEP | **SUPPORTING_ONLY** |
| `User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf` | trade-off scatter | KEEP | **SUPPORTING_ONLY** |

Stall / TTFB / false Buffer-Level continuity figures remain fail-closed supporting
artifacts from prior audits; not redesign targets here. Do not delete.

Scheme aliases of the central scaling line (`System_Utility_By_Users_scheme*.pdf`,
`Buffer_Level_By_Users_scheme1.pdf`) remain byte-identical copies for filename
compatibility; treat scheme1 as the manuscript pointer.

---

## Recommended main-text figure map

1. **Overall ECDF** — `QoE_By_Strategy.pdf`
2. **Concurrency scaling** — `System_Utility_By_Users_scheme1.pdf`
3. **Robustness Figure*** — left `QoE_By_Content_DeltaU.pdf` + right `QoE_By_Network.pdf`
4. **Holdout / mechanism Figure*** — left `Loot_Holdout_DeltaU_By_Users.pdf` + right `Mechanism_Decomposition_Loot.pdf`
5. **Architecture Figure*** — left `MoQ_Shared_vs_Unicast.pdf` + right `H2_Cross_Stack_DASH.pdf`
6. **Throughput Figure*** (1×3) — `System_Throughput_Bar_{4G,5G,Default_Mix}.pdf`

---

## Redesign scientific QA (checked)

| Check | Result |
|---|---|
| Filenames unchanged | PASS |
| Values unchanged vs pack / invariants | PASS |
| Content×load uses true matched means (21/cell; no interpolation) | PASS |
| Heatmap 7×3 true network×load means; no hatch; no cell text/stars | PASS |
| Loot u20 mean ΔU clearly negative (~−0.160) | PASS |
| MD2G low-load weakness not visually hidden | PASS |
| u40 not marked significant (scaling keeps all five loads; no stars) | PASS |
| Loot decomposition Ro/Rq/Rb sum = observed ΔU within 1e-3 | PASS (`Rq` dominates loss and gain) |
| H2: no connecting line between only two measured loads | PASS |
| All PDFs vector | PASS |
| Readable at one-/two-column inclusion sizes | PASS (contact sheet sizes logged) |

---

## Style notes (V4)

- Strategy palette frozen (MD2G `#0072B2`, Heuristic `#E69F00`, Clustering `#009E73`, Rule `#CC79A7`, …).
- Load encoding on content strip: sequential blues `#9ECAE1` / `#4292C6` / `#08519C` + o/s/D markers.
- Mechanism colors: Ro `#009E73`, Rq `#0072B2`, Rb `#D55E00`, total diamond `#333333`.
- No error bars, annotations, numeric point labels, W/T/L, significance stars, or gray backgrounds.
- Precision statistics remain in manuscript tables/prose only.
