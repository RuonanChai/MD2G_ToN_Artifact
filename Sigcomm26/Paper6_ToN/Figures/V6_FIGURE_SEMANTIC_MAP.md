# V6_FIGURE_SEMANTIC_MAP

Authority: COMMAND153 frozen figure source data + V5 audit placement.
Generated as Figure Semantic Auditor output. No scientific re-runs.

**FIGURE_SEMANTIC_MAPPING_PASS = true**

Companion JSON: `Figures/V6_FIGURE_SEMANTIC_MAP.json`

Paper-pack reference: `Sigcomm26/Paper6_ToN/final/PAPER_REWRITE_INPUT_PACK.json`  
Source rows: `final/COMMAND153_FIGURE_SOURCE_DATA/{dev,loot,scaling,matched_blocks,cross_stack_dash}.json`

Canonical U: `clip(0.25*Ro_component + 0.60*Rq - 0.15*Rb, 0, 1)`

---

## Scientific caveats (global)

### Rb–U operating-point caveat (binding)

`TierB_Rb_vs_U_*.pdf` plots mean **Rb** vs mean **U** at loads 20/60/100.
Because **U already includes −0.15·Rb**, this family is an **OPERATING-POINT VISUALIZATION only**,
**not** independent causal-mechanism evidence that “lower Rb causes higher U.”
Primary mechanism evidence remains the **Ro / Rq / Rb decomposition**
(`Mechanism_Decomposition_Loot.pdf` and matched Δ contributions).

### Same-substrate vs cross-stack

- Same-substrate primary: MD2G vs Heuristic (HV3) / Clustering / Rule.
- MoQ Unicast is delivery-mode comparison only.
- GROOT / Rolling are cross-stack DASH/HTTP unicast; not mixed into strongest same-substrate.

---

## Access-profile agreement (critical)

Identity must agree across **filename**, **script `NETWORK=`**, and **`dev.json` filter `network=`**.
Do not infer from plot appearance.

### TierB_Rb_vs_U

| filename | filename_profile | script NETWORK | data network filter | agree |
|---|---|---|---|---|
| TierB_Rb_vs_U_4G.pdf | 4G | `4g` | `4g` | true |
| TierB_Rb_vs_U_5G.pdf | 5G | `5g` | `5g` | true |
| TierB_Rb_vs_U_WiFi.pdf | WiFi | `wifi` | `wifi` | true |
| TierB_Rb_vs_U_Fiber_Optic.pdf | Fiber_Optic | `fiber_optic` | `fiber_optic` | true |
| TierB_Rb_vs_U_Default_Mix.pdf | Default_Mix | `default_mix` | `default_mix` | true |

Loader: `_fig_style.plot_rb_u_tradeoff(network)` → `load_rows("dev.json")` with `r["network"] == network`.

### System_Throughput_Bar

| filename | filename_profile | script NETWORK | data network filter | agree |
|---|---|---|---|---|
| System_Throughput_Bar_4G.pdf | 4G | `4g` | `4g` | true |
| System_Throughput_Bar_5G.pdf | 5G | `5g` | `5g` | true |
| System_Throughput_Bar_Default_Mix.pdf | Default_Mix | `default_mix` | `default_mix` | true |
| System_Throughput_Bar_Wifi.pdf | Wifi | `wifi` | `wifi` | true |
| System_Throughput_Bar_Fiber_Optic.pdf | Fiber_Optic | `fiber_optic` | `fiber_optic` | true |
| System_Throughput_Bar_5G_Dominant.pdf | 5G_Dominant | `5g_dominant` | `5g_dominant` | true |
| System_Throughput_Bar_Wifi_Dominant.pdf | Wifi_Dominant | `wifi_dominant` | `wifi_dominant` | true |

Loader: `_fig_style.plot_throughput_network(network)` → `load_rows("dev.json")` with `r["network"] == network`.

---

## Per-figure semantic map (V5 final paper PDFs)

Placement baseline: `FIGURE_VISUAL_REDESIGN_V5_AUDIT.md`.

### 1. `QoE/QoE_By_Strategy.pdf`

| Field | Value |
|---|---|
| scientific_question | How does MAINDEV per-cell system utility U distribute across same-substrate strategies? |
| source_artifact | `dev.json` |
| contents | redandblack, longdress, soldier |
| network_access_profile | all MAINDEV nets (4g, 5g, wifi, fiber_optic, default_mix, wifi_dominant, 5g_dominant) |
| user_scales | 20, 60, 100 (pooled) |
| strategies | MD2G, Heuristic, Clustering, Rule |
| x_axis | System utility U (ECDF support) |
| y_axis | Empirical CDF |
| higher_preferable | x: higher U better; y: CDF shape (right-shift better) |
| placement | **MAIN_TEXT** |

### 2. `Buffer Level/System_Utility_By_Users_scheme1.pdf`

| Field | Value |
|---|---|
| scientific_question | How does mean U scale with concurrency on the frozen scaling slice? |
| source_artifact | `scaling.json` |
| contents | redandblack only |
| network_access_profile | default_mix + wifi_dominant (scaling contract) |
| user_scales | 10, 20, 40, 60, 100 |
| strategies | MD2G, Heuristic, Clustering, Rule |
| x_axis | Number of users |
| y_axis | Mean system utility U |
| higher_preferable | y: higher better; x: scale axis (not preference) |
| placement | **MAIN_TEXT** |

### 3. `Buffer Level/System_Utility_By_Users_MainDev.pdf`

| Field | Value |
|---|---|
| scientific_question | At MAINDEV loads 20/60/100, how are the four same-substrate policies ranked by mean U? |
| source_artifact | `dev.json` |
| contents | redandblack, longdress, soldier |
| network_access_profile | all MAINDEV nets (pooled per load) |
| user_scales | 20, 60, 100 (panels) |
| strategies | MD2G, Heuristic, Clustering, Rule |
| x_axis | Mean system utility U |
| y_axis | Strategy (ranked bars) |
| higher_preferable | x: higher better |
| placement | **APPENDIX** |

### 4. `QoE/QoE_By_Content_DeltaU.pdf`

| Field | Value |
|---|---|
| scientific_question | Does each DEV content preserve the low→high load matched ΔU pattern? |
| source_artifact | `matched_blocks.json` |
| contents | redandblack, longdress, soldier |
| network_access_profile | all 7 MAINDEV nets (21 blocks = 7 nets × 3 seeds per content×load) |
| user_scales | 20, 60, 100 (marker encoding) |
| strategies | ΔU = MD2G − max(HV3, Clustering, Rule) |
| x_axis | Matched ΔU |
| y_axis | Content |
| higher_preferable | x: higher ΔU better for MD2G; y: category |
| placement | **MAIN_TEXT** |

### 5. `QoE/QoE_By_Network.pdf`

| Field | Value |
|---|---|
| scientific_question | How does matched ΔU vary across access profiles × load? |
| source_artifact | `matched_blocks.json` |
| contents | redandblack, longdress, soldier (pooled per net×users) |
| network_access_profile | heatmap rows: 4g, 5g, wifi, fiber_optic, default_mix, wifi_dominant, 5g_dominant |
| user_scales | 20, 60, 100 (columns) |
| strategies | matched ΔU vs strongest same-substrate |
| x_axis | Number of users |
| y_axis | Network / access profile |
| color | Matched ΔU (diverging; positive = MD2G ahead) |
| higher_preferable | color/ΔU: higher better for MD2G |
| placement | **MAIN_TEXT** |

### 6. `QoE/Loot_Holdout_DeltaU_By_Users.pdf`

| Field | Value |
|---|---|
| scientific_question | On unseen Loot, how does matched ΔU change with user scale? |
| source_artifact | `loot.json` (via `matched_delta_by_users`) |
| contents | loot |
| network_access_profile | all 7 MAINDEV nets (pooled per users) |
| user_scales | 20, 60, 100 |
| strategies | MD2G vs max(HV3, Clustering, Rule) |
| x_axis | Number of users (Loot holdout) |
| y_axis | Matched ΔU |
| higher_preferable | y: higher better for MD2G |
| placement | **MAIN_TEXT** |

### 7. `QoE/Mechanism_Decomposition_Loot.pdf`

| Field | Value |
|---|---|
| scientific_question | Which U components (0.25ΔRo, 0.60ΔRq, −0.15ΔRb) explain Loot matched ΔU by load? |
| source_artifact | `loot.json` (via `match_same_substrate_blocks`) |
| contents | loot |
| network_access_profile | all 7 nets (21 matched blocks per load) |
| user_scales | 20, 60, 100 |
| strategies | MD2G vs strongest same-substrate |
| x_axis | Number of users (Loot holdout) |
| y_axis | Utility contribution (signed stack) + observed ΔU diamond |
| higher_preferable | positive contribution / higher observed ΔU better for MD2G |
| placement | **MAIN_TEXT** |
| note | This is the primary mechanism figure; prefer over Rb–U scatter for causal claims. |

### 8. `QoE/MoQ_Shared_vs_Unicast.pdf`

| Field | Value |
|---|---|
| scientific_question | On Loot, how do shared MoQ MD2G means compare to MoQ Unicast on U/Rq/Ro/Rb? |
| source_artifact | `COMMAND153_PRIMARY_STATS.json` → `loot_by_strategy` |
| contents | loot (holdout aggregate) |
| network_access_profile | all Loot nets (stats aggregate) |
| user_scales | pooled holdout aggregate |
| strategies | MD2G_COMPONENT vs MOQ_UNICAST_COMPONENT |
| x_axis | Loot holdout mean (metric value in [0,1]) |
| y_axis | Metric (U, Rq, Ro, Rb) |
| higher_preferable | U/Rq/Ro: higher better; Rb: lower better |
| placement | **MAIN_TEXT** |

### 9. `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf`

| Field | Value |
|---|---|
| scientific_question | At 20 and 60 users, how does MD2G MoQ U compare to authentic DASH GROOT/Rolling? |
| source_artifact | DASH cells via `load_cross_stack_dash_u()` + MD2G U from `dev.json`; summary also in `cross_stack_dash.json` |
| contents | redandblack, longdress |
| network_access_profile | wifi_dominant, default_mix, 4g (12 cells / method / load) |
| user_scales | 20, 60 |
| strategies | MD2G (MoQ) vs groot vs rolling |
| x_axis | Mean system utility U |
| y_axis | User load strip |
| higher_preferable | x: higher better |
| placement | **MAIN_TEXT** |
| note | Cross-stack only; not same-substrate ranking. |

### 10. `QoE/Weak_User_Rq_Loot.pdf`

| Field | Value |
|---|---|
| scientific_question | On Loot, how does weak-user Rq ECDF of MD2G compare to strongest same-substrate at each load? |
| source_artifact | `loot.json` (matched blocks) |
| contents | loot |
| network_access_profile | all 7 nets |
| user_scales | 20, 60, 100 (panels) |
| strategies | MD2G vs strongest same-substrate |
| x_axis | Weak-user Rq |
| y_axis | Empirical CDF |
| higher_preferable | x: higher Rq better (right-shift) |
| placement | **APPENDIX** |

### 11–17. Throughput family (`Throughput/System_Throughput_Bar_*.pdf`)

Common semantics:

| Field | Value |
|---|---|
| scientific_question | How does shared-root TX throughput (Mbps) scale with users under one fixed access profile? |
| source_artifact | `dev.json` filtered by `network` |
| contents | redandblack, longdress, soldier |
| user_scales | 20, 60, 100 |
| strategies | MD2G, Heuristic, Clustering, Rule |
| x_axis | Number of users |
| y_axis | Shared-root TX (Mbps) from `physical_pressure.raw_protocol_inclusive_tx_bytes` |
| higher_preferable | context-dependent (capacity use / pressure); **not** a QoE win metric by itself |
| metric_note | Protocol-inclusive TX rate; not Ro and not “bandwidth saved.” |

| filename | network | placement |
|---|---|---|
| System_Throughput_Bar_4G.pdf | `4g` | MAIN_TEXT |
| System_Throughput_Bar_5G.pdf | `5g` | MAIN_TEXT |
| System_Throughput_Bar_Default_Mix.pdf | `default_mix` | MAIN_TEXT |
| System_Throughput_Bar_Wifi.pdf | `wifi` | APPENDIX |
| System_Throughput_Bar_Fiber_Optic.pdf | `fiber_optic` | APPENDIX |
| System_Throughput_Bar_5G_Dominant.pdf | `5g_dominant` | APPENDIX |
| System_Throughput_Bar_Wifi_Dominant.pdf | `wifi_dominant` | APPENDIX |

### 18–22. TierB Rb–U family (`User_Experience_Trade-off/TierB_Rb_vs_U_*.pdf`)

Common semantics:

| Field | Value |
|---|---|
| scientific_question | Under one access profile, where do same-substrate strategies sit in (Rb, U) at loads 20/60/100? |
| source_artifact | `dev.json` filtered by `network` |
| contents | redandblack, longdress, soldier |
| user_scales | 20, 60, 100 (marker size + trajectory) |
| strategies | MD2G, Heuristic, Clustering, Rule |
| x_axis | Rb (bottleneck / physical pressure proxy; lower preferred) |
| y_axis | System utility U (higher preferred) |
| better_direction | toward lower-left? No — “Better” arrow is **lower Rb and higher U** (left and up) |
| claim_class | **OPERATING_POINT_VISUALIZATION_ONLY** (U already penalizes Rb) |
| primary_mechanism_figure | Mechanism_Decomposition_Loot.pdf |

| filename | network | placement |
|---|---|---|
| TierB_Rb_vs_U_Default_Mix.pdf | `default_mix` | MAIN_TEXT (representative) |
| TierB_Rb_vs_U_4G.pdf | `4g` | SUPPORTING_ONLY |
| TierB_Rb_vs_U_5G.pdf | `5g` | SUPPORTING_ONLY |
| TierB_Rb_vs_U_WiFi.pdf | `wifi` | SUPPORTING_ONLY |
| TierB_Rb_vs_U_Fiber_Optic.pdf | `fiber_optic` | SUPPORTING_ONLY |

---

## Out of scope for this map

- Fail-closed gap audits (`EVIDENCE_GAP_*.json`, TTFB CDF audit, Fig.4 fluidity audit).
- Stall Time PDFs (not in V5 paper-order final set for ToN component figures).
- Color-scheme alias PDFs (`*_scheme2.pdf` …) that duplicate scheme1 bytes.
- Contact sheets and legacy Buffer_Level_By_* aliases.

---

## Pass predicate

`FIGURE_SEMANTIC_MAPPING_PASS=true` iff:

1. All TierB profile agreements are true;
2. All Throughput profile agreements are true;
3. Every V5 final paper PDF above has a complete semantic record.

All three hold.
