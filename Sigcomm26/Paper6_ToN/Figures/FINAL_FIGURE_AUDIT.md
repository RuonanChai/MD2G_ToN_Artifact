# FINAL_FIGURE_AUDIT — ToN vs Sigcomm figure families

**Authority:** frozen COMMAND153/155 evidence package + VALID raw artifacts under
`Sigcomm26/Paper6_ToN/artifacts/` (canary + MAINDEV audited; summaries in
`final/COMMAND153_FIGURE_SOURCE_DATA/`).

**Style authority:** `paper_figures/Sigcomm/` (fonts, colors, folder grammar).

**Policy:** Match figure **family** when evidence supports it; otherwise fail-closed.
Never invent TTFB/continuity curves from zero placeholders. Never reintroduce “zero stall”.

---

## A. Raw-evidence audit (mandatory targets)

| Target family | Required raw evidence | Audit result | Decision |
|---|---|---|---|
| Fig.4-style trade-off (interval vs QoE) | Non-zero `delay_ms` / arrival interval + QoE | canary delay_ms nonzero **0/122**; MAINDEV sample **0/265** | **FAIL CLOSED** |
| Fig.5-style TTFB CDF | Non-zero `ttfb_*_ms` or first-byte timing | canary **0/122**; MAINDEV sample **0/265**; receipts have no TTFB field | **FAIL CLOSED** |
| Fig.7-style continuity/recovery timeseries | Evolving `stall_total_sec` (or equivalent timeline) | stall series ok **0** (canary + MAINDEV sample); `stall_last` scalar only | **FAIL CLOSED** |
| True Buffer Level | Non-zero `buffer_level_sec` | **0** nonzero in audited samples | **FAIL CLOSED** |

Audit JSON dumps:
- `TTFB/EVIDENCE_GAP_TTFB.json`
- `Stall Time/EVIDENCE_GAP_CONTINUITY_TIMESERIES.json`
- `User_Experience_Trade-off/EVIDENCE_GAP_FIG4_TRADEOFF.json`
- `Buffer Level/README_METRIC_HONESTY.md`

---

## B. Final paper figure map (recommended ordering)

| Fig # | Role | PDF path | Source data | Visual family (redesign) | Notes |
|------:|------|----------|-------------|--------------------------|-------|
| 1 | Topology / system (existing manuscript assets) | *(manuscript Figures/Topo_*)* | N/A | diagram — **unchanged** | Outside this rebuild |
| 2 | Overall U by strategy | `QoE/QoE_By_Strategy.pdf` | `dev.json` U | **box + mean** (was bar) | 189 cells/strategy; overlapping regimes |
| 3 | **Concurrency crossover (central Tier-B)** | `Buffer Level/System_Utility_By_Users_scheme1.pdf` | `scaling.json` U by users | **multi-line point-range** (was bar); metric = U | Alias `Buffer_Level_By_Users_scheme1.pdf`; u40 = estimated transition, CI includes 0 |
| 4 | MAINDEV U by users | `Buffer Level/System_Utility_By_Users_MainDev.pdf` | `dev.json` | **slope / point-range** (was bar) | u20/60/100 corroborates scaling |
| 5 | Network × load robustness (ΔU) | `QoE/QoE_By_Network.pdf` | `matched_blocks.json` | **diverging heatmap** (was bar) | 4G u60/u100 CI includes 0 (no outline) |
| 6 | Content robustness (ΔU) | `QoE/QoE_By_Content_DeltaU.pdf` | `matched_blocks.json` | **horizontal forest** | bootstrap 95% CI; manuscript content order |
| 7 | Unseen-content matched ΔU | `QoE/Loot_Holdout_DeltaU_By_Users.pdf` | `loot.json` matched | **line + CI** (was bar) | u20 loss W/T/L 0/0/21 remains visible |
| 8 | Utility decomposition | `QoE/Mechanism_Decomposition_Loot.pdf` | `loot.json` | **signed stacked contribution** | not an ablation; high-load gain is Rq-driven |
| 9 | Shared MoQ vs unicast | `QoE/MoQ_Shared_vs_Unicast.pdf` | `PRIMARY_STATS` | **dumbbell U/Rq/Ro/Rb** | unicast Ro=0 by construction |
| 10 | Weak-user Rq | `QoE/Weak_User_Rq_Loot.pdf` | `loot.json` | **paired lines** (was bar) | vs strongest same-substrate |
| 11–17 | Throughput by network | `Throughput/System_Throughput_Bar_*.pdf` | shared-root TX bytes | **multi-line scaling** (filename keeps Bar) | lower TX ≠ efficiency |
| 18 | H2 DASH secondary | `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf` | DASH CELL_DONE U | **two-point line** | cross-stack diagnostic only |
| 19–23 | Tier-B Rb–U scatters | `User_Experience_Trade-off/TierB_Rb_vs_U_*.pdf` | `dev.json` Rb,U | **trade-off scatter** (polished) | not Fig.4 axes; load = marker size |
| S1–S3 | Supporting stall_last bars | `Stall Time/Stall_Time_By_*.pdf` | `stall_last` | **bar — unchanged** | supporting decode-gap; not in U |

### Explicitly not generated (see SKIPPED_FIGURES.md)

| Old target | Status |
|---|---|
| Fig.4 fluidity–QoE (interval vs QoE) | SKIPPED — evidence gap |
| Fig.5 TTFB CDF 1×3 | SKIPPED — evidence gap |
| Fig.7/8 Continuity vs Recovery timeseries | SKIPPED — evidence gap |
| True Buffer occupancy curves | SKIPPED — evidence gap |

---

## C. Style validation

| Property | Source lock | Applied |
|---|---|---|
| Folder layout | Sigcomm QoE/TTFB/Buffer/Stall/Throughput/Trade-off | Yes (TTFB present with fail-closed only) |
| Font | DejaVu Sans | Yes |
| QoE bar colors (strategy-by-strategy bars that remain) | `#FBF0C3/#54686F/#E57B7F/#9E3150/#87BBA4` | Yes (unchanged stall / strategy-U bars) |
| Same-substrate identity (lines/boxes/heat) | `#0E606B/#1597A5/#FFC24B/#F66F69` + markers/linestyles | Yes |
| figsize / spines | two-column; top/right spines off on data axes | Yes (heatmap keeps cell box) |
| One py → one primary PDF | Yes (schemes are intentional variants) | Yes |

---

## D. Scientific validation checklist

- [x] No pre-Rb / INVALID / obsolete DASH-PC numbers
- [x] No fabricated TTFB CDF
- [x] No fabricated stall timeseries / “zero stall” claim
- [x] Universal win not implied (holdout u20 losses plotted)
- [x] Same-substrate primary; H2 secondary
- [x] FoV/A1–A5 not plotted as validation
- [x] Visual redesign 2026-08-31: filenames unchanged; chart family follows the scientific question; bootstrap CI used only on content forest, heatmap outlines, and holdout ΔU (seed 153 / n_boot 10000); remaining error bars stay sample SD
- [x] See `FIGURE_VISUAL_REDESIGN_AUDIT.md`

---

## E. New experiment required?

**No.** Gaps are instrumentation/retention limits in already-frozen VALID cells
(`ttfb_*`, `delay_ms`, `buffer_level_sec`, `stall_total_sec` placeholders). Filling them
would require a **new instrumentation contract + re-run**, which is outside this
figure-finalization goal and would change evidence epoch.
