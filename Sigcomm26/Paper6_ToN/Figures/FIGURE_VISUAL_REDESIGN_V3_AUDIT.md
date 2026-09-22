# FIGURE VISUAL REDESIGN V3 AUDIT

Token: `TON_FINAL_FIGURE_VISUAL_REDESIGN_V3_READY`

Visual-only redesign of frozen COMMAND153 final PDFs.
No experiment rerun. No cell, match, seed, U/Rq/Ro/Rb, weight, bootstrap,
W/T/L, epoch, or manuscript claim changed. Filenames unchanged.

Diagnostic only: `Figures/FIGURE_VISUAL_REDESIGN_V3_CONTACT_SHEET.pdf`.

Evidence epoch: `C152_RBV1_88cabc20eb5d`.
Source: `final/COMMAND153_FIGURE_SOURCE_DATA/`.
CI and W/T/L remain in frozen tables; **figures no longer draw them**.

`verify_visual_redesign_invariants.py` → `SCIENTIFIC_INVARIANT_CHECKS_PASS`.
`qa_v3_whitespace.py` → `V3_WHITESPACE_AND_ANNOTATION_QA_PASS`.

Palette: MD2G `#0072B2`, Heuristic `#E69F00`, Clustering `#009E73`,
Rule `#CC79A7`, Unicast `#7A7A7A`, GROOT `#56B4E9`, Rolling `#D55E00`.
Font: embedded Liberation Sans. `bbox_inches=tight`, `pad_inches=0.02`.
No error bars, no SD/CI bands, no in-plot callouts.

---

## Per-file ledger

Outer whitespace = 1 − (non-white content bbox / canvas). All ≤ 30%.

### `QoE/QoE_By_Strategy.pdf`

| | |
|---|---|
| Question | How do U distributions differ across strategies? |
| V2 type | ECDF with markers on 0–1 x |
| V3 type | landscape ECDF, x on data support |
| Source | `dev.json` U, 189 cells/strategy |
| Values | unchanged (means match pack G) |
| Whitespace | 6.4% |
| Vector | yes |
| Size | 3.16 × 2.29 in after tight crop |

### `Buffer Level/System_Utility_By_Users_scheme1.pdf` (+ scheme2–5 aliases)

| | |
|---|---|
| Question | How does mean U evolve with concurrency; where does MD2G separate? |
| V2 type | line + sample-SD ribbon + “estimated transition” |
| V3 type | lines+markers; no band; no u40 annotation |
| Source | `scaling.json` |
| Values | unchanged (pack H) |
| Whitespace | 4.2% |
| Vector | yes |
| Size | 6.01 × 2.52 in |
| Notes | scheme2–5 and `Buffer_Level_By_Users_scheme1.pdf` are byte copies |

### `Buffer Level/System_Utility_By_Users_MainDev.pdf`

| | |
|---|---|
| Question | Relative position of each controller at MAINDEV 20/60/100 |
| V2 type | vertical Cleveland + SD whiskers |
| V3 type | 1×3 **horizontal** dots; no whisker; no connector |
| Source | `dev.json` |
| Values | unchanged |
| Whitespace | 2.5% |
| Vector | yes |
| Size | 6.11 × 2.35 in |

### `QoE/QoE_By_Content_DeltaU.pdf`

| | |
|---|---|
| Question | Which DEV contents have positive or near-zero aggregate ΔU? |
| V2 type | forest + bootstrap CI |
| V3 type | diverging lollipop; mean only; manuscript order |
| Source | `matched_blocks.json` n=63/content |
| Values | Rb 0.036 / Ld 0.010 / Soldier 0.001 unchanged; CI kept in tables |
| Whitespace | 4.9% |
| Vector | yes |
| Size | 3.54 × 1.95 in |

### `QoE/QoE_By_Network.pdf`

| | |
|---|---|
| Question | How does ΔU interact with network × concurrency? |
| V2 type | dodged dot-whisker + CI |
| V3 type | diverging heatmap, zero-centered, no cell text |
| Source | `matched_blocks.json` 7×3, n=9 |
| Values | cell means unchanged; 4G u60 near zero remains visible as near-white |
| Whitespace | 4.9% |
| Vector | yes |
| Size | 3.95 × 2.25 in |
| Scale | zmin/zmax = ±0.192 (max \|cell mean\|) |
| Notes | negative cells use `///` hatch so sign remains readable in grayscale; not a significance outline |

### `QoE/Loot_Holdout_DeltaU_By_Users.pdf`

| | |
|---|---|
| Question | Does unseen Loot reproduce the load-dependent sign change? |
| V2 type | lollipop + CI + W/T/L ticks |
| V3 type | zero-centered connected-dot; no CI/WTL |
| Source | `loot.json` matched ΔU |
| Values | −0.160 / +0.083 / +0.111 unchanged; WTL 0/0/21, 21/0/0, 21/0/0 in tables |
| Whitespace | 3.0% |
| Vector | yes |
| Size | 3.18 × 2.06 in |

### `QoE/Mechanism_Decomposition_Loot.pdf`

| | |
|---|---|
| Question | What algebraically produces matched ΔU at each load? |
| V2 type | waterfall with Ro/Rq/Rb math labels + diamond |
| V3 type | 1×3 waterfall: Reuse / Quality / Pressure / Total |
| Source | `loot.json` matched blocks |
| Values | components still sum to observed ΔU |
| Whitespace | 3.5% |
| Vector | yes |
| Size | 6.07 × 2.72 in |
| Notes | labeled utility decomposition, not ablation |

### `QoE/MoQ_Shared_vs_Unicast.pdf`

| | |
|---|---|
| Question | How does shared delivery differ from unicast on U, Rq, Ro, Rb? |
| V2 type | dumbbell with numeric labels |
| V3 type | dumbbell, no numbers; unicast hollow |
| Source | `PRIMARY_STATS` loot_by_strategy |
| Values | unicast Ro = 0 unchanged |
| Whitespace | 6.3% |
| Vector | yes |
| Size | 2.94 × 2.21 in |

### `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf`

| | |
|---|---|
| Question | How do complete-system U values move from 20 to 60 users? |
| V2 type | two Cleveland panels + sample SD |
| V3 type | slopegraph 20–60; MD2G solid, DASH dashed/dotted + hollow/X |
| Source | DASH CELL_DONE + MAINDEV MD2G (de-duplicated) |
| Values | unchanged |
| Whitespace | 5.3% |
| Vector | yes |
| Size | 3.06 × 2.36 in |

### `QoE/Weak_User_Rq_Loot.pdf`

| | |
|---|---|
| Question | How does weak-user Rq distribution change with load? |
| V2 type | 3×1 vertical ECDF |
| V3 type | 1×3 **horizontal** ECDF; x on data support (~0–0.6) |
| Source | `loot.json` matched weak_user_Rq |
| Values | unchanged |
| Whitespace | 3.8% |
| Vector | yes |
| Size | 5.94 × 2.79 in |

### `Throughput/System_Throughput_Bar_*.pdf`

| | |
|---|---|
| Question | How does shared-root TX scale with users? |
| V2 type | line + SD ribbon + “Lower TX is not efficiency” |
| V3 type | lines+markers; no band; no footnote; filename still contains Bar |
| Source | `dev.json` shared-root TX Mbps |
| Values | means unchanged |
| Whitespace | 6.6% each |
| Vector | yes |
| Size | ~3.20 × 2.32 in |
| Axes | 4G/5G/Default Mix share comparable y; others own pad of means |

### `User_Experience_Trade-off/TierB_Rb_vs_U_*.pdf`

| | |
|---|---|
| Question | Utility–pressure operating point as load changes |
| V2 type | Pareto arrows + “better” + load text |
| V3 type | scatter + thin low-alpha trajectory; size = 20/60/100; size legend |
| Source | `dev.json` Rb, U means per (strategy, load) |
| Values | unchanged |
| Whitespace | 2.0% |
| Vector | yes |
| Size | ~3.06 × 2.52 in |
| Notes | no Pareto frontier, no arrows |

### Unchanged in concept

`Topo_MD2G.pdf`, `Topo_DASH.pdf`, evaluation design table, stall bars,
fail-closed TTFB/continuity/buffer families.

---

## QA checklist

- exact filename unchanged
- exact frozen data unchanged
- no error bar / uncertainty band
- no “better” / “estimated transition” / “Lower TX” / W/T/L / value labels
- outer whitespace ≤ 30% (max observed 6.6%)
- vector PDF, Liberation Sans embedded
- u40 not marked as statistically established
- 4G not hidden by favorable sorting (heatmap row order frozen)
- low-load negative Loot ΔU visible
- grayscale: linestyle + marker, not color alone

---

## Terminal

`TON_FINAL_FIGURE_VISUAL_REDESIGN_V3_READY`
