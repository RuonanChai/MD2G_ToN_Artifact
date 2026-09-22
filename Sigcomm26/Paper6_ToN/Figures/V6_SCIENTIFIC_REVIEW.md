# V6_SCIENTIFIC_REVIEW

Authority: Systems Methodology Reviewer (skeptical SIGCOMM / NSDI / ToN).  
Scope: MAIN_TEXT paper-order figures per `V6_MAIN_TEXT_CURATION.md` (A–E + optional Discussion Rb–U), grounded in `V6_FIGURE_SEMANTIC_MAP.md`, `V6_SCIENCE_FREEZE.json`, and `final/PAPER_REWRITE_INPUT_PACK` facts.  
Constraint: COMMAND153 frozen evidence only; no scientific re-runs; no value changes.

**SYSTEMS_METHODOLOGY_REVIEW_PASS = true**

---

## Verdict

| Token | Value |
|---|---|
| `SYSTEMS_METHODOLOGY_REVIEW_PASS` | **true** |
| Binding placement | `V6_MAIN_TEXT_CURATION.md` (supersedes V5 / semantic-map MAIN placement of lone Default-Mix Rb–U) |
| Evidence freeze | `V6_SCIENCE_FREEZE.json` hashes / U weights unchanged |

The prescribed A–E pack does **not** systematically hide low-concurrency losses, does **not** treat u40 as a proven threshold in the figure set, keeps the seven-network heatmap order fixed, leaves 4G and Loot u20 weakness inspectable, names mechanism as **decomposition**, demotes Rb–U to operating-point Discussion, and separates MoQ-Unicast / DASH from same-substrate controller ranking. Fail-closed TTFB / true buffer / CPU / FoV plots stay out of the paper-order set.

PASS is **conditional on caption/text discipline** listed in § Must-fix caption caveats. A caption that violates those items is a manuscript defect even though the figure *selection* passes.

---

## Checklist (paper-order)

### 1. No figure hides u20 underperformance — PASS

| MAIN panel | u20 visibility |
|---|---|
| A(a) `QoE_By_Strategy.pdf` | Pooled ECDF (all loads). Does **not** alone tell the concurrency story; must not be captioned as universal win. |
| A(b) scaling U vs users | Absolute \(U\) curves; MD2G trails at low concurrency on the scaling slice (pack: u10/u20 mean ΔU negative). |
| B(a) content ΔU | Explicit load markers 20/60/100; frozen means u20 negative on all three DEV contents (−0.106 / −0.157 / −0.147). |
| B(b) network heatmap | Column u=20 present; **all seven** nets mean ΔU &lt; 0 at u20. |
| C(a) Loot ΔU | u20 mean **−0.160214**, W/T/L **0/0/21**, CI excludes 0; zero line drawn. |
| C(b) mechanism stack | u20 panel retained; Rq contribution negative at low load (decomposition shows *why* ΔU is negative). |

No MAIN panel drops the u=20 column or reorders loads to show only wins. Pooled A(a) is acceptable **only** because B/C carry the load-conditioned claim.

### 2. u40 not visually presented as proven threshold — PASS (caption-bound)

- Scaling figure (`System_Utility_By_Users_scheme1.pdf`) includes loads 10/20/**40**/60/100 as a scale axis for mean \(U\), with **no** annotated “threshold,” crossover marker, or significance band on u40.
- Pack fact: first positive *mean* ΔU at u=40, but **u40 CI includes 0** → **estimated transition**, not a sharp proven threshold.
- Heatmap / Loot / mechanism MAIN panels use only 20/60/100 — they do not elevate u40.

**Must not** caption A(b) as “MD2G wins beyond 40 users” or “proven operating threshold at 40.”

### 3. Heatmap keeps all seven networks in fixed order — PASS

Script `QoE/plot_qoe_by_network.py` uses `HEATMAP_NET_ORDER` from `_fig_evidence.py`:

`4g → 5g → wifi → fiber_optic → default_mix → wifi_dominant → 5g_dominant`

Comment in code: *Manuscript heatmap row order (not sorted by MD2G performance)*. Matches pack `networks_maindev`. Semantic map lists the same row order. Do **not** resort rows by ΔU for camera-ready.

### 4. 4G weakness remains visible — PASS

- Heatmap retains **4G** as first row; recomputed means ≈ (−0.105, +0.013, +0.049) — high-concurrency gains fragile vs other nets (pack: u60/u100 CIs include 0 on 4g).
- FIGURE E(a) keeps `System_Throughput_Bar_4G.pdf` in the representative physical-load triad (constrained homogeneous), not dropped for a prettier profile.
- Optional Discussion Rb–U includes 4G panel if shown.

### 5. Loot u20 remains negative — PASS

Frozen matched Loot (via `matched_delta_by_users`):

| users | n | mean ΔU | W/T/L |
|---:|---:|---:|---|
| 20 | 21 | **−0.160214** | **0/0/21** |
| 60 | 21 | +0.083108 | 21/0/0 |
| 100 | 21 | +0.111350 | 21/0/0 |

C(a) and C(b) both include u20. Every network: u20 all losses. Do not pool loads into a single Loot bar that washes out the negative.

### 6. Mechanism plot called decomposition, not ablation — PASS

- Filename / script: `Mechanism_Decomposition_Loot.pdf` / `plot_mechanism_decomposition_loot.py`.
- Semantics: algebraic stack \(0.25\Delta R_o + 0.60\Delta R_q + (-0.15\Delta R_b)\) vs observed ΔU — **measured decomposition**, not FoV/device/completion ablations (pack: A1–A5/A7 **NOT_APPLICABLE**).
- Curator role: FIGURE C(b) = **PRIMARY_MECHANISM**.

Caption must say **decomposition** / component contributions — never “ablation study.”

### 7. Rb–U described as operating-point / supporting — PASS

- Science freeze / semantic map: \(U=\mathrm{clip}(0.25 R_o + 0.60 R_q - 0.15 R_b, 0, 1)\) already penalizes Rb.
- Claim class: **OPERATING_POINT_VISUALIZATION_ONLY**; not independent causal proof that “lower Rb ⇒ higher U.”
- Curation: `RB_U_IN_MAIN_A_E=false`; at most optional Discussion 1×3 (4G / 5G / Default Mix) with mandatory caveats; WiFi/Fiber remain SUPPORTING_ONLY.
- Supersedes V5 lone Default-Mix MAIN Rb–U (and semantic-map row that still listed Default Mix as MAIN_TEXT).

### 8. Throughput not “lower always better” — PASS (caption-bound)

Semantic map: shared-root protocol-inclusive TX Mbps; `higher_preferable` **context-dependent**; **not** Ro; **not** “bandwidth saved.” Pack §69: lower TX can mean under-delivery. FIGURE E triad is physical-pressure context, not a QoE win selector.

### 9. MoQ-Unicast not same-substrate controller — PASS

- Same-substrate set in evidence helpers: MD2G / HV3 / Clustering / Rule only (`SAME_STRATEGIES`).
- D(a) is a **separate** shared-vs-unicast architecture panel (Loot aggregate); unicast Ro=0 enforced in plot script.
- Semantic map / pack: delivery-mode comparison — **not** controller skill within shared MoQ.

### 10. DASH remains cross-stack secondary — PASS (caption-bound)

- D(b) `H2_Cross_Stack_DASH.pdf` only; GROOT/Rolling never enter strongest same-substrate max.
- Curator: “Caption discipline: D(b) must not be mixed into same-substrate ranking claims.”
- Allowed wording: secondary cross-stack system gap; does **not** isolate MD2G controller within MoQ.
- Note: rewrite pack once listed H2 as APPENDIX; curation places it in MAIN as architecture secondary — acceptable **iff** captions stay secondary.

### 11. No unsupported TTFB / buffer / CPU / FoV figures return — PASS

Out of MAIN/APPENDIX body per curation + semantic map “Out of scope” / `SKIPPED_FIGURES`:

- TTFB CDF audits (audited zeros)
- Fig.4 fluidity / continuity timeseries (fail-closed)
- True `buffer_level` (folder name “Buffer Level” hosts **utility** aliases only)
- CPU, FoV sweeps / NA ablations

Stall scalar plots appendix-only; never reclaim SIGCOMM “zero stall.”

---

## Residual risks (do not flip PASS → FAIL if captions hold)

1. **A(a) pooled ECDF** can be misread as dominance if B/C are under-cited in text.
2. **Semantic map still labels** `TierB_Rb_vs_U_Default_Mix.pdf` as MAIN_TEXT — authors must follow **curation**, not the stale placement cell.
3. **Large DASH U gap** in MAIN D(b) invites overclaim; keep “cross-stack secondary” in the caption first sentence.
4. **Directory name** `Buffer Level/` for utility PDFs is legacy naming; captions must say system utility \(U\), not playback buffer seconds.

---

## Must-fix caption caveats

Bind these into LaTeX captions / surrounding prose before camera-ready:

1. **A(a):** Same-substrate MAINDEV \(U\) distribution pooled over loads/nets; concurrency-dependent matched ΔU is in B/C — **not** a claim of universal MD2G dominance.
2. **A(b):** Mean \(U\) vs concurrency on the frozen scaling slice; any mention of ~40 users is an **estimated mean-sign transition** (u40 CI includes 0), **not** a proven threshold.
3. **B(b):** Matched ΔU heatmap; rows in fixed contract order (not performance-sorted); **4G** high-concurrency gains remain small / CI-fragile — do not imply uniform access robustness.
4. **C(a):** Unseen Loot matched ΔU; **u20 remains negative** (0 wins / 21 losses); do not pool loads into one summary that conceals this.
5. **C(b):** Title/caption = **mechanism decomposition** (weighted ΔRo / ΔRq / ΔRb contributions), **not** ablation; primary mechanism figure.
6. **D(a):** Shared MoQ component delivery vs MoQ Unicast — **architecture / delivery mode**, not same-substrate controller ranking.
7. **D(b):** **Cross-stack secondary** (MoQ vs authentic DASH/HTTP); gap does not isolate the MD2G controller; never fold GROOT/Rolling into strongest same-substrate baseline.
8. **E(a–c):** Shared-root **protocol-inclusive TX (Mbps)** = physical load/pressure context; **not** \(R_o\); **not** “bandwidth saved”; **lower TX is not always better**.
9. **Optional Discussion Rb–U (if kept):** **OPERATING-POINT VISUALIZATION ONLY**; \(U\) already includes \(-0.15 R_b\); not independent causal evidence that lower Rb causes higher \(U\); point readers to C(b).

---

## Gate predicate

`SYSTEMS_METHODOLOGY_REVIEW_PASS=true` iff all of:

1. MAIN A–E retain explicit u20 / Loot-negative / seven-net heatmap / 4G visibility as above;
2. Mechanism figure is decomposition (not ablation) and is primary vs Rb–U;
3. Rb–U is not lone MAIN causal evidence (`RB_U_IN_MAIN_A_E=false`);
4. MoQ-Unicast and DASH stay outside same-substrate ranking figures;
5. Throughput / Rb–U semantics reject “lower always better” / false causal Rb→U;
6. Unsupported TTFB / true buffer / CPU / FoV plots are not restored to paper-order;
7. Must-fix caption caveats are acknowledged as binding for manuscript (selection alone is insufficient for camera-ready claims).

All seven hold under the curated pack.

---

## Terminal tokens (return to orchestrator)

```
SYSTEMS_METHODOLOGY_REVIEW_PASS=true
MUST_FIX_CAPTIONS=A(a)_no_universal_dominance;A(b)_u40_estimated_transition_not_threshold;B(b)_fixed_order_and_4G_fragility;C(a)_loot_u20_negative;C(b)_decomposition_not_ablation;D(a)_delivery_not_controller;D(b)_cross_stack_secondary;E_tx_not_efficiency;RbU_operating_point_only
```
