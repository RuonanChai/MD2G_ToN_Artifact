# FIGURE VISUAL REDESIGN V2 AUDIT

Token: `TON_FINAL_FIGURE_VISUAL_REDESIGN_V2_READY`

This is a **visual / statistical-presentation** redesign of already-frozen final PDFs.
No experiment was rerun. No cell, matched block, seed, U/Rq/Ro/Rb definition, weight,
bootstrap, W/T/L, epoch, or manuscript claim was changed.
Every scientific PDF was overwritten **in place** at the same filename.

Diagnostic only (not a paper figure): `Figures/FIGURE_VISUAL_REDESIGN_V2_CONTACT_SHEET.pdf`
(22 pages, each page = the figure at native paper size, not enlarged).

Evidence epoch: `C152_RBV1_88cabc20eb5d` (COMMAND153 frozen package).
Source directory: `final/COMMAND153_FIGURE_SOURCE_DATA/`.
Bootstrap (only where the figure shows CI): seed **153**, `n_boot=10000`, percentile 95% CI of the mean.
Sample SD remains sample SD wherever the previous figure used SD.

Independent review: **MAIN_TEXT_VISUAL_PASS** (9/9 main-text figures).
Scientific invariant script: `verify_visual_redesign_invariants.py` → `SCIENTIFIC_INVARIANT_CHECKS_PASS`.

Font: Liberation Sans (Arial unavailable), embedded Type 42. Mathtext forced to the same family.
No DejaVu in regenerated PDFs.

LaTeX authority for display width: `Figures/FIGURE_INCLUDE_SUGGESTION.tex` (manuscript prose not edited).
Assumed IEEEtran journal: `\columnwidth ≈ 3.40 in`, `\textwidth ≈ 7.16 in`.

`effective_font_pt = source_font_pt × LaTeX_display_width / PDF_natural_width`.
PDFs are generated at the include width, so the scale factor is **1.00** and
axis/tick/legend source sizes (10 / 9.5 / 9 pt) are the final sizes.

---

## Visual identity (all figures)

| Role | Color | Marker | Line |
|---|---|---|---|
| MD2G | `#0E606B` | `o` | solid, 1.45 pt |
| Heuristic | `#1597A5` | `s` | dashed, 1.25 pt |
| Clustering | `#C4A35A` | `^` | dash-dot, 1.25 pt |
| Rule | `#C16A6A` | `D` | dotted, 1.25 pt |
| MoQ Unicast | `#8A8A8A` | `v` hollow | — |
| GROOT (DASH) | `#5E7A62` | `P` hollow | — |
| Rolling (DASH) | `#8B5A5A` | `X` hollow | — |
| Strongest same-substrate | `#5A5A5A` | `s` | dashed |

Spines: top/right off. Grid alpha ≈ 0.14. Marker ≈ 5 pt. CI/SD line ≈ 1.0 pt. Capsize 2.2 pt.

---

## Per-file ledger

### 1. `QoE/QoE_By_Strategy.pdf`

| | |
|---|---|
| Old grammar | box + mean (V1) |
| New grammar | **ECDF**, one curve per strategy, every cell, no pre-aggregation |
| Source | `dev.json` U; 189 cells / strategy |
| Uncertainty | none (full empirical distribution) |
| Placement | single-column `\columnwidth` |
| Natural PDF | **3.40 × 2.55 in** |
| LaTeX display | 3.40 in |
| Effective font | axis 10 pt, tick 9.5 pt, legend 9 pt (×1.00) |
| Axes | x ∈ [−0.02, 1.02] (U); y ∈ [−0.02, 1.04] (ECDF) |
| Invariants | strategy means still match pack G (MD2G 0.675, Clustering 0.649, Rule 0.641, Heuristic 0.559) |

### 2. `Buffer Level/System_Utility_By_Users_scheme1.pdf`

| | |
|---|---|
| Old grammar | multi-line + SD errorbar whiskers (V1) |
| New grammar | **scaling line + sample-SD translucent ribbon**; marker at every measured load; no interpolation beyond {10,20,40,60,100} |
| Source | `scaling.json` U |
| Uncertainty | **sample SD** ribbon (not CI) |
| Placement | double-column `0.92\textwidth` |
| Natural PDF | **6.59 × 2.85 in** |
| LaTeX display | 6.59 in |
| Effective font | 10 / 9.5 / 9 pt (×1.00) |
| Axes | x = {10,20,40,60,100}; y = data-driven pad of mean±SD (~0.50–0.85) |
| Notes | dotted x=40 + “estimated transition”; **not** marked significant (u40 CI includes 0) |
| Aliases | `scheme2–5.pdf` and `Buffer_Level_By_Users_scheme1.pdf` are byte-identical copies (filenames preserved) |

### 3. `Buffer Level/System_Utility_By_Users_MainDev.pdf`

| | |
|---|---|
| Old grammar | scaling line u20/60/100 (V1) |
| New grammar | **Cleveland dot-and-whisker small multiples**; 3×1 vertical (single-column); methods as rows |
| Source | `dev.json` U by users |
| Uncertainty | **sample SD** horizontal whisker |
| Placement | single-column `\columnwidth` |
| Natural PDF | **3.40 × 5.15 in** |
| LaTeX display | 3.40 in |
| Effective font | 10 / 9.5 pt; panel labels 10 pt bold (×1.00) |
| Axes | x ∈ [0.32, 0.98] shared; y = {MD2G, Heuristic, Clustering, Rule} |

### 4. `QoE/QoE_By_Content_DeltaU.pdf`

| | |
|---|---|
| Old grammar | forest (V1) |
| New grammar | compact **forest**; no cell shading; no significance stars |
| Source | `matched_blocks.json` ΔU; n=63 per content |
| Uncertainty | **bootstrap 95% CI** (seed 153, n_boot=10000) |
| Placement | single-column |
| Natural PDF | **3.40 × 2.15 in** |
| LaTeX display | 3.40 in |
| Effective font | 10 / 9.5 pt (×1.00) |
| Axes | x ∈ [−0.12, 0.20]; y = Red-and-Black / Longdress / Soldier |
| Frozen values | Rb 0.036 / Ld 0.010 / Soldier 0.001 with pack CIs unchanged |

### 5. `QoE/QoE_By_Network.pdf`

| | |
|---|---|
| Old grammar | diverging heatmap (V1) |
| New grammar | **network-conditioned dodged dot-whisker**; loads 20/60/100 by marker shape |
| Source | `matched_blocks.json`; 7 nets × 3 loads × n=9 |
| Uncertainty | **bootstrap 95% CI** |
| Placement | single-column (dodge, not 1×3; manuscript already single-column) |
| Natural PDF | **3.40 × 4.15 in** |
| LaTeX display | 3.40 in |
| Effective font | 10 / 9.5 / 9 pt (×1.00) |
| Axes | x ∈ [−0.24, 0.20]; y = 7 network profiles (manuscript order) |
| Notes | no thick-border significance encoding; 4G u60 CI still includes 0 visually |

### 6. `QoE/Loot_Holdout_DeltaU_By_Users.pdf`

| | |
|---|---|
| Old grammar | connected zero-crossing line + CI (V1) |
| New grammar | **diverging lollipop**; stem from 0; **no connecting line**; filled iff CI excludes 0 |
| Source | `loot.json` matched ΔU |
| Uncertainty | **bootstrap 95% CI** |
| Placement | single-column |
| Natural PDF | **3.40 × 2.85 in** |
| LaTeX display | 3.40 in |
| Effective font | 10 / 9.5 pt; W/T/L as second tick line ≥8.5 pt (×1.00) |
| Axes | x = {20,60,100}; y ∈ [−0.22, 0.17] |
| Frozen | u20 = −0.160 WTL 0/0/21; u60 = +0.083 21/0/0; u100 = +0.111 21/0/0; all CIs exclude 0 |

### 7. `QoE/Mechanism_Decomposition_Loot.pdf`

| | |
|---|---|
| Old grammar | signed stacked bars (V1) |
| New grammar | **waterfall** small multiples (1×3): +0.25ΔRo, +0.60ΔRq, −0.15ΔRb, diamond = observed ΔU |
| Source | `loot.json` matched blocks |
| Uncertainty | none (algebraic decomposition, **not** an ablation) |
| Placement | double-column `0.92\textwidth` |
| Natural PDF | **6.59 × 2.55 in** |
| LaTeX display | 6.59 in |
| Effective font | 10 / 9.5 / 9 pt (×1.00) |
| Axes | shared y covering ≈[−0.18, 0.13]; x = Ro, Rq, Rb, ΔU |
| Invariants | components sum to observed ΔU: u20 −0.160; u60 +0.083; u100 +0.111 |
| Notes | Ro bars are visually tiny because frozen |c_Ro| < 0.001; that is data, not a scale trick. No u40 annotation (that belongs on the scaling figure). |

### 8. `QoE/MoQ_Shared_vs_Unicast.pdf`

| | |
|---|---|
| Old grammar | horizontal dumbbell (V1) |
| New grammar | compact **horizontal dumbbell**; direct numeric labels |
| Source | `COMMAND153_PRIMARY_STATS.json` `loot_by_strategy` |
| Uncertainty | frozen means (no SD/CI on this figure previously or now) |
| Placement | single-column `0.85\columnwidth` |
| Natural PDF | **2.89 × 2.05 in** |
| LaTeX display | 2.89 in |
| Effective font | 10 / 9.5 / 8.5 pt labels (×1.00) |
| Axes | x ∈ [−0.06, 1.08]; rows U, Rq, Ro, Rb |
| Invariants | unicast Ro = **0** exactly |

### 9. `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf`

| | |
|---|---|
| Old grammar | two-point connected strategy lines (V1) |
| New grammar | **two Cleveland panels** (a) 20 (b) 60; rows MD2G / GROOT / Rolling; no 20↔60 trajectory |
| Source | DASH `CELL_DONE` + MAINDEV MD2G U; MD2G de-duplicated on (content, network, seed) |
| Uncertainty | **sample SD** |
| Placement | single-column |
| Natural PDF | **3.40 × 3.85 in** |
| LaTeX display | 3.40 in |
| Effective font | 10 / 9.5 pt (×1.00) |
| Axes | shared x = data-driven pad of mean±SD; DASH markers hollow |
| Status | cross-stack diagnostic, not same-substrate ranking |

### 10. `Throughput/System_Throughput_Bar_{4G,5G,Default_Mix,Wifi,Fiber_Optic,5G_Dominant,Wifi_Dominant}.pdf`

| | |
|---|---|
| Old grammar | scaling line + giant SD caps (V1); filename already kept “Bar” |
| New grammar | **throughput-vs-users scaling curve + sample-SD ribbon** |
| Source | `dev.json` shared-root TX Mbps |
| Uncertainty | **sample SD** ribbon |
| Placement | appendix; suggested `\columnwidth` |
| Natural PDF | **3.40 × 2.70 in** each |
| LaTeX display | 3.40 in |
| Effective font | 10 / 9.5 / 9 pt (×1.00) |
| Axes | x = {20,60,100}; y data-driven (4G/5G/Default Mix share ≈[45, 142] Mbps); Fiber/Wifi/dominant use their own pad, not a wasted common 0-floor |
| Notes | footnote “Lower TX is not efficiency.” Filename still contains `Bar`. |

### 11. `QoE/Weak_User_Rq_Loot.pdf`

| | |
|---|---|
| Old grammar | mean±SD point-range with huge whiskers + connecting line (V1; rejected) |
| New grammar | **ECDF small multiples** 3×1; MD2G vs strongest same-substrate; every matched observation |
| Source | `loot.json` `weak_user_Rq` via matched blocks |
| Uncertainty | none (full sample ECDF replaces mean±SD) |
| Placement | supporting / suggested single-column |
| Natural PDF | **3.40 × 5.20 in** |
| LaTeX display | 3.40 in |
| Effective font | 10 / 9.5 pt; panel labels 10 pt bold (×1.00) |
| Axes | all panels x ∈ [−0.02, 1.02], y ∈ [−0.04, 1.06]; legend once (panel a) |

### 12. `User_Experience_Trade-off/TierB_Rb_vs_U_{4G,5G,WiFi,Fiber_Optic,Default_Mix}.pdf`

| | |
|---|---|
| Old grammar | per-cell scatter, load = marker size (V1) |
| New grammar | **Pareto trajectory**: one mean (Rb, U) per (strategy, load); connect only sequential loads of the same method; small load labels on MD2G; “better” arrow (low Rb, high U) |
| Source | `dev.json` Rb, U |
| Uncertainty | none (means of measured cells; no invented frontier, hull, or regression) |
| Placement | appendix; suggested `\columnwidth` |
| Natural PDF | **3.40 × 2.55 in** each |
| LaTeX display | 3.40 in |
| Effective font | 10 / 9.5 / 8.5 pt (×1.00) |
| Axes | family-common Rb ∈ [0.047, 0.140], U ∈ [0.402, 0.819] |

### 13. Not redesigned

Topology diagrams, `Stall_Time_By_*.pdf` bars, fail-closed TTFB/continuity/buffer-occupancy families.

---

## Font / export QA

For every regenerated scientific PDF:

- `pdfinfo` page size matches the target natural width (3.40 / 6.59 / 2.89 in).
- `pdffonts` shows only embedded Liberation Sans (and Bold where panel labels are bold).
- Rasterized at 300 dpi (`pdftoppm`) for clipping / legend / tick inspection.
- `savefig(..., bbox_inches=None)` so LaTeX does not shrink a 6.5 in canvas.

---

## Scientific invariant checks

`python verify_visual_redesign_invariants.py` → `SCIENTIFIC_INVARIANT_CHECKS_PASS`

- A: 189 cells/strategy; means match pack G
- B: scaling MD2G means match pack H (tol 5e-4)
- D: content means + bootstrap CI match pack
- E: 7×3 matched cells, n=9 each
- F: Loot means / CI / WTL match pack I
- G: Loot 0.25ΔRo + 0.60ΔRq − 0.15ΔRb sums to observed ΔU
- H: unicast Ro = 0; MD2G U frozen
- U weights still (0.25, 0.60, 0.15)
- SAMPLE SD was not replaced by CI; bootstrap 95% CI was not replaced by SD

---

## Independent reviewer (8-point rubric)

Reviewer: [V2 figure rubric](3d906e92-5092-461e-8776-509c3c53cf74)

| Figure | Q1 type | Q2 <5s | Q3 uncertainty | Q4 ~10pt | Q5 axis | Q6 gray | Q7 restrained | Q8 question-driven | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| QoE_By_Strategy | YES | YES | N/A (ECDF) | YES | YES | YES | YES | YES | PASS |
| scheme1 | YES | YES | SD ribbon | YES | YES | YES | YES | YES | PASS |
| MainDev | YES | YES | SD whisker | YES | YES | YES | YES | YES | PASS |
| Content ΔU | YES | YES | bootstrap CI | YES | YES | YES | YES | YES | PASS |
| Network | YES | YES | bootstrap CI | YES | YES | YES | YES | YES | PASS |
| Loot ΔU | YES | YES | bootstrap CI | YES | YES | YES | YES | YES | PASS |
| Mechanism | YES | YES | algebraic | YES | YES | YES | YES | YES | PASS |
| Shared vs Unicast | YES | YES | frozen means | YES | YES | YES | YES | YES | PASS |
| H2 DASH | YES | YES | sample SD | YES | YES | YES | YES | YES | PASS |

**MAIN_TEXT_VISUAL_PASS**

Residual polish (not FAIL): waterfall Ro bars are nearly invisible because |0.25ΔRo| < 0.001; Loot ylabel now names the CI.

---

## What was not done

- No filename changes.
- No manuscript prose / include-size edits.
- No holdout unsealing, no metric retune, no experiment rerun.
- Contact sheet is diagnostic only.
