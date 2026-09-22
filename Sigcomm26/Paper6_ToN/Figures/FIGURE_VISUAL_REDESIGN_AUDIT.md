# FIGURE_VISUAL_REDESIGN_AUDIT

Token: `TON_FINAL_FIGURE_VISUAL_REDESIGN_READY`

This is a **visual grammar** redesign of already-frozen final PDFs.
No experiment was rerun. No cell, match, U-weight, epoch, or manuscript claim was changed.
Every paper PDF was overwritten **in place** at the same filename.

Diagnostic only (not a paper figure): `Figures/FIGURE_VISUAL_REDESIGN_CONTACT_SHEET.pdf`.

Evidence epoch: `C152_RBV1_88cabc20eb5d` (COMMAND153 frozen package).
Source directory: `final/COMMAND153_FIGURE_SOURCE_DATA/`.
Bootstrap (only where the redesign explicitly requests CI): seed **153**, `n_boot=10000`, percentile 95% CI of the mean.

---

## 1. Changed paper PDFs

### A. `QoE/QoE_By_Strategy.pdf`

| | |
|---|---|
| Old family | grouped bar (mean ± sample SD) |
| New family | compact **box + mean-point** |
| Why | The scientific question is the **distribution** of U, not four category means. Boxes show overlapping operating regimes. |
| Source | `dev.json`, 189 MAINDEV cells per same-substrate strategy |
| Uncertainty | box = Q1–Q3; center line = median; whiskers = 1.5 IQR; white diamond = mean; low-alpha jittered cells. **Not** a significance test. |
| Derived view | none (raw cell U) |
| Values unchanged | strategy means match `G_maindev.strategy_means` (MD2G 0.675, Clustering 0.649, Rule 0.641, Heuristic 0.559) |

### B. `Buffer Level/System_Utility_By_Users_scheme1.pdf`

| | |
|---|---|
| Old family | grouped bars over user counts |
| New family | **multi-line point-range** |
| Why | User count is an **ordered physical scale**. Lines expose the mean-sign crossover near 40. |
| Source | `scaling.json` (150 keys = 90 DEV reuse + 60 new) |
| Uncertainty | **sample SD** (same semantics as the previous bars) |
| Derived view | optional dotted marker at x=40 labeled “estimated transition region”; **not** a significance claim. Pack: u40 ΔU CI includes 0. |
| Values unchanged | MD2G scaling means match pack `H_scaling.matched_by_users` |
| Alias | `Buffer_Level_By_Users_scheme1.pdf` remains a byte-identical alias. `System_Utility_By_Users_scheme2–5.pdf` remain filename-preserving copies of scheme1. |

### C. `Buffer Level/System_Utility_By_Users_MainDev.pdf`

| | |
|---|---|
| Old family | grouped bars |
| New family | **slope / point-range** at u20/60/100 |
| Why | Corroborates B on the three MAINDEV loads without duplicating a five-point bar chart. |
| Source | `dev.json` |
| Uncertainty | sample SD |
| Values unchanged | same strategy means as the previous MAINDEV bars |

### D. `QoE/QoE_By_Content_DeltaU.pdf`

| | |
|---|---|
| Old family | grouped bars |
| New family | **horizontal forest / dot-whisker** |
| Why | Content is an **effect-size vs zero** question. |
| Source | `matched_blocks.json`, n=63 per content, order Red-and-Black / Longdress / Soldier |
| Uncertainty | **bootstrap 95% CI** (redesigned from sample SD by request; same frozen blocks) |
| Derived view | CI recomputed from matched ΔU lists; means/CIs match pack `G_maindev.matched_by_content` |
| Values unchanged | RB 0.036 CI excludes 0; Longdress 0.010 and Soldier 0.001 CIs include 0 |

### E. `QoE/QoE_By_Network.pdf`

| | |
|---|---|
| Old family | strategy-mean bars flattened over network |
| New family | **zero-centered diverging heatmap** (network × users) |
| Why | The result is organized by **concurrency × network**, not by a single favorable network. |
| Source | `matched_blocks.json`; 7 networks × {20,60,100}; n=9 matched blocks/cell |
| Uncertainty | cell value = mean matched ΔU; **outline iff bootstrap 95% CI excludes 0**. No stars. |
| Color | `RdBu`, symmetric `±max|cell|` (vmax = 0.1921) |
| Network order | 4G, 5G, Wi-Fi, Fiber Optic, Default Mix, Wi-Fi Dominant, 5G Dominant (fixed; not sorted by MD2G) |
| 4G not hidden | u20 −0.104 (CI excludes 0); u60 +0.013 and u100 +0.048 **CI includes 0** (no outline) |

### F. `QoE/Loot_Holdout_DeltaU_By_Users.pdf`

| | |
|---|---|
| Old family | grouped bars |
| New family | **line + point-range** around y=0 |
| Why | Matched effect that **crosses zero** with ordered concurrency. |
| Source | `loot.json` matched same-substrate blocks, n=21 per load, seeds 91/92/93 |
| Uncertainty | bootstrap 95% CI; W/T/L noise ±0.03 |
| Values unchanged | u20 −0.160 W/T/L **0/0/21**; u60 +0.083 **21/0/0**; u100 +0.111 **21/0/0** |
| Visual | low-concurrency loss is below zero and labeled; not shaded away |

### G. `QoE/Mechanism_Decomposition_Loot.pdf`

| | |
|---|---|
| Old family | independent grouped metric bars |
| New family | **signed diverging stacked contribution** + observed ΔU overlay |
| Why | The three weighted terms **sum to ΔU**. Independent bars hid that identity. |
| Source | `loot.json` matched blocks; `0.25 ΔRo + 0.60 ΔRq − 0.15 ΔRb` |
| Uncertainty | none (algebraic means). Overlay totals = pack ΔU −0.160 / +0.083 / +0.111 |
| Caption metadata | **utility decomposition**, not causal contribution / not an ablation |
| Scientific read | high-load gain is almost entirely Rq-driven |

### H. `QoE/MoQ_Shared_vs_Unicast.pdf`

| | |
|---|---|
| Old family | two U bars |
| New family | **horizontal dumbbell** across U, Rq, Ro, Rb |
| Why | Architecture difference lives in the four metrics, not only final U. |
| Source | `COMMAND153_PRIMARY_STATS.json` → `loot_by_strategy` |
| Uncertainty | none (frozen means) |
| Values unchanged | MD2G U 0.688, Rq 0.760, Ro 0.974, Rb 0.075; Unicast U 0.194, Rq 0.407, **Ro = 0**, Rb 0.334 |
| Note on figure | higher better for U/Rq/Ro; lower better for Rb; unicast Ro=0 by construction |

### I. `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf`

| | |
|---|---|
| Old family | grouped bars |
| New family | **two-point line / point-range** (u20, u60 only; no extrapolation) |
| Why | Two ordered loads; cross-stack diagnostic, not same-substrate fairness. |
| Source | `artifacts/command153_cross_stack_dash` CELL_DONE + matched MD2G from `dev.json` |
| Uncertainty | sample SD. MD2G is de-duplicated per (content, network, seed) so SD is not double-counted from GROOT+Rolling rows. **Means unchanged.** |
| Caption metadata | “cross-stack diagnostic” retained on the x-label |

### J. Throughput (filenames keep `Bar`)

Paths (unchanged names):

- `Throughput/System_Throughput_Bar_4G.pdf`
- `Throughput/System_Throughput_Bar_5G.pdf`
- `Throughput/System_Throughput_Bar_Default_Mix.pdf`

Also regenerated for filename consistency (same grammar): Wifi, Fiber_Optic, 5G_Dominant, Wifi_Dominant.

| | |
|---|---|
| Old family | grouped bars |
| New family | **multi-line system-load scaling** |
| Why | Throughput vs receiver count is an ordered scaling process. |
| Source | `dev.json` `physical_pressure.raw_protocol_inclusive_tx_bytes` → Mbps |
| Uncertainty | sample SD |
| Y scale | shared across MAINDEV networks (0 … 1.08× observed max) |
| Caption metadata | “Lower TX is not efficiency: it may reflect lower decoded service.” |

### K. `QoE/Weak_User_Rq_Loot.pdf` (already existed)

| | |
|---|---|
| Old family | grouped bars |
| New family | **paired lines**: MD2G vs strongest same-substrate weak-user Rq |
| Why | Ordered loads; comparator is the matched strongest baseline, not a named third strategy. |
| Source | `loot.json` matched blocks (`weak_user_Rq`) |
| Uncertainty | sample SD |

### L. `User_Experience_Trade-off/TierB_Rb_vs_U_*.pdf` (already existed)

`TierB_Rb_vs_U_{4G,5G,WiFi,Fiber_Optic,Default_Mix}.pdf`

| | |
|---|---|
| Old family | scatter |
| New family | **ACE/MAE-style trade-off scatter** (same family, polished) |
| Why | Two competing objectives (higher U, lower Rb). |
| Source | `dev.json` cell (Rb, U) |
| Encoding | strategy = color+marker; **load = marker size** (20/60/100); small “better” arrow toward upper-left |
| Not implied | causality; no Pareto overlay (not computed) |

---

## 2. Deliberately unchanged (and why)

| PDF / family | Why left as-is |
|---|---|
| Topology diagrams (`Topo_MD2G` / `Topo_DASH` in the manuscript tree) | Diagram family; not a data chart |
| `Stall Time/Stall_Time_By_{Strategy,Users,Network}.pdf` | Discrete supporting `stall_last` bars; n does not justify a new grammar |
| `Buffer Level/System_Utility_By_Strategy_scheme*.pdf` and `Buffer_Level_By_Strategy_scheme1.pdf` | Category micro-comparison; compact bars remain appropriate |
| TTFB / continuity timeseries / Fig.4 fluidity–QoE | **Fail-closed**. Instrumentation not in frozen evidence. Not resurrected. |
| Evaluation-matrix tables | Remain tables |
| Manuscript `.tex` claims | Explicitly out of scope |

---

## 3. Scientific invariant checks

Executed by `Figures/verify_visual_redesign_invariants.py` against `PAPER_REWRITE_INPUT_PACK.json` + frozen source JSON.

- 189 cells/strategy; MAINDEV strategy-mean U match pack
- Scaling MD2G means match `H_scaling` (tol 5e-4)
- Content means + bootstrap CIs match pack
- Heatmap 7×3 cells, n=9 each
- Holdout ΔU means, CIs, W/T/L match pack (0/0/21, 21/0/0, 21/0/0)
- Weighted Ro/Rq/Rb contributions sum to observed holdout ΔU
- Unicast Ro = 0; MD2G holdout U frozen
- U weights remain 0.25 / 0.60 / 0.15
- No TTFB, delay-QoE, buffer occupancy, CPU, or FoV figure created
- All original manifest filenames still exist; none renamed or deleted
- Paper PDFs are Matplotlib vector PDF 1.4 with embedded DejaVu (fonttype 42)

---

## 4. Reproducibility

```bash
MPLBACKEND=Agg Sigcomm26/.venv_sigcomm/bin/python \
  Sigcomm26/Paper6_ToN/Figures/regenerate_visual_redesign.py
```

Contact sheet (diagnostic):

```bash
MPLBACKEND=Agg Sigcomm26/.venv_sigcomm/bin/python \
  Sigcomm26/Paper6_ToN/Figures/make_visual_redesign_contact_sheet.py
```

---

## 5. Caption notes for the writer (no manuscript edit in this task)

- Error bars that remain SD must still be called **sample SD**, not CI.
- Content forest, network heatmap outlines, and holdout ΔU whiskers are **bootstrap 95% CI**.
- Mechanism figure is a **utility decomposition**, not an ablation.
- H2 is a **cross-stack diagnostic**.
- Throughput: lower TX is not efficiency.
- u40 is an **estimated transition**, not a statistically marked threshold.
