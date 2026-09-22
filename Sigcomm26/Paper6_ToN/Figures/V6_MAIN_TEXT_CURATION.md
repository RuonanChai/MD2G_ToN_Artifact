# V6_MAIN_TEXT_CURATION

Authority: Top-Conference Figure Curator (SIGCOMM / NSDI / ToN standard).  
Inputs: `V6_FIGURE_SEMANTIC_MAP.{md,json}`, `FIGURE_VISUAL_REDESIGN_V5_AUDIT.md`, `V6_SCIENCE_FREEZE.json` (brief).  
Constraint: COMMAND153 frozen evidence only; no scientific re-runs; no value changes.

**TOP_CONFERENCE_CURATION_PASS = true**

---

## Verdict

| Token | Value |
|---|---|
| `TOP_CONFERENCE_CURATION_PASS` | **true** |
| `RB_U_DECISION` | **INCLUDE_OPTIONAL_DISCUSSION_1x3** (panels: 4G / 5G / Default Mix) |
| `RB_U_IN_MAIN_A_E` | **false** (demotes V5 single-panel Default Mix from MAIN_TEXT) |

### Pass reasons

1. **Narrative arc A→E is conference-grade.** Overall distribution + scaling → content/network robustness → holdout + primary mechanism → architecture (shared MoQ vs unicast; cross-stack DASH) → representative physical load. One claim per figure family; no duplicate story.
2. **Primary mechanism is correctly placed.** Causal Ro/Rq/Rb story sits in FIGURE C(b) (`Mechanism_Decomposition_Loot.pdf`), not in Rb–U scatters (semantic map: `OPERATING_POINT_VISUALIZATION_ONLY`; U already includes −0.15·Rb).
3. **Access-profile identity is clean.** Semantic map reports all TierB and Throughput filename / `NETWORK=` / `dev.json` filter agreements = true.
4. **Representative load triad is structural, not outcome-picked.** FIGURE E and optional Rb–U Discussion use the same coverage set: constrained homogeneous (`4g`), high-capacity homogeneous (`5g`), heterogeneous (`default_mix`) — identical to V5 throughput MAIN_TEXT selection and V5’s written note that Default Mix was *not* chosen by largest MD2G win.
5. **Science freeze intact.** Placement curation only; hashes / U weights / source rows unchanged (`V6_SCIENCE_FREEZE.json`).
6. **V5 visual QA already PASS** on every curated PDF (clip / legend / vector); curator does not reopen visual redesign.

### Explicit supersession of V5 Rb–U placement

V5 put `TierB_Rb_vs_U_Default_Mix.pdf` alone in MAIN_TEXT as “optional representative.”  
**Curator rejects single-profile MAIN_TEXT Rb–U** (even if Default Mix was not win-ranked): a lone mixed panel still reads as selective operating-point marketing next to a full mechanism figure.  
**Replace with:** at most one Discussion figure that *combines* the three existing PDFs as panels — or omit Rb–U from the paper body entirely. Curator chooses **include Discussion 1×3** (see § Rb–U decision).

---

## Prescribed MAIN TEXT visual structure

External (not in Figures/ semantic set): topology / system diagram.

### FIGURE A — Overall + scaling

| Panel | Path | Role |
|---|---|---|
| (a) | `QoE/QoE_By_Strategy.pdf` | MAINDEV same-substrate U ECDF |
| (b) | `Buffer Level/System_Utility_By_Users_scheme1.pdf` | Frozen scaling-slice mean U vs users |

### FIGURE B — Robustness

| Panel | Path | Role |
|---|---|---|
| (a) | `QoE/QoE_By_Content_DeltaU.pdf` | Matched ΔU by DEV content × load |
| (b) | `QoE/QoE_By_Network.pdf` | Matched ΔU heatmap: access profile × load |

### FIGURE C — Holdout + mechanism

| Panel | Path | Role |
|---|---|---|
| (a) | `QoE/Loot_Holdout_DeltaU_By_Users.pdf` | Unseen Loot matched ΔU vs users |
| (b) | `QoE/Mechanism_Decomposition_Loot.pdf` | **Primary** 0.25ΔRo / 0.60ΔRq / −0.15ΔRb stack |

### FIGURE D — Architecture

| Panel | Path | Role |
|---|---|---|
| (a) | `QoE/MoQ_Shared_vs_Unicast.pdf` | Shared MoQ MD2G vs MoQ Unicast (Loot aggregate) |
| (b) | `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf` | Cross-stack only: MD2G MoQ vs GROOT/Rolling |

Caption discipline: D(b) must not be mixed into same-substrate ranking claims.

### FIGURE E — Representative physical network load (LaTeX 1×3)

| Panel | Path | Access class |
|---|---|---|
| (a) | `Throughput/System_Throughput_Bar_4G.pdf` | Constrained homogeneous (`4g`) |
| (b) | `Throughput/System_Throughput_Bar_5G.pdf` | High-capacity homogeneous (`5g`) |
| (c) | `Throughput/System_Throughput_Bar_Default_Mix.pdf` | Heterogeneous (`default_mix`) |

Metric honesty: shared-root protocol-inclusive TX (Mbps); **not** Ro; **not** “bandwidth saved.”

---

## OPTIONAL Discussion — Rb–U (at most one figure)

### `RB_U_DECISION = INCLUDE_OPTIONAL_DISCUSSION_1x3`

**One** Discussion figure (e.g. Figure F / Discussion Fig.*), LaTeX 1×3, combining existing PDFs as panels — do **not** invent a new plot or pick a fourth/fifth profile for a larger MD2G win:

| Panel | Path | Coverage role |
|---|---|---|
| (a) | `User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf` | Constrained homogeneous |
| (b) | `User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf` | High-capacity homogeneous |
| (c) | `User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf` | Heterogeneous |

**Mandatory caption / text caveats:**

- Claim class = **OPERATING_POINT_VISUALIZATION_ONLY**.
- \(U\) already includes \(-0.15 R_b\); this figure is **not** independent causal proof that “lower Rb causes higher U.”
- Point readers to FIGURE C(b) for mechanism.
- Do not caption as Sigcomm Fig.4-style “Fluidity–QoE” (`User_Experience_Trade-off/README_FIGURE_FAMILY.md`).

**Not included in Discussion panels:** `TierB_Rb_vs_U_WiFi.pdf`, `TierB_Rb_vs_U_Fiber_Optic.pdf` → remain `SUPPORTING_ONLY` / appendix repository (full family available; not paper-body cherry-picks).

**If page budget forces a cut:** drop the entire Discussion Rb–U figure first (keep A–E). Do **not** fall back to Default Mix alone in MAIN_TEXT.

---

## APPENDIX

| Item | Paths / notes |
|---|---|
| MainDev ranking bars | `Buffer Level/System_Utility_By_Users_MainDev.pdf` |
| Weak-user Rq | `QoE/Weak_User_Rq_Loot.pdf` |
| Remaining throughput | `Throughput/System_Throughput_Bar_{Wifi,Fiber_Optic,5G_Dominant,Wifi_Dominant}.pdf` |
| Stall diagnostics | `Stall Time/*` scalar / audit plots only; **never** reclaim SIGCOMM “zero stall” (`STALL_VS_SIGCOMM_PAPER.md`, `SKIPPED_FIGURES.md`). Continuity timeseries / Fig.4 fluidity remain fail-closed. |
| Remaining Rb–U | `TierB_Rb_vs_U_{WiFi,Fiber_Optic}.pdf` (and any non-panel copies); optional mirror of Discussion 1×3 if Discussion omitted |

---

## Full placement table (every semantic-map figure)

| filename | placement | note |
|---|---|---|
| `QoE/QoE_By_Strategy.pdf` | **MAIN_TEXT** | FIGURE A(a) |
| `Buffer Level/System_Utility_By_Users_scheme1.pdf` | **MAIN_TEXT** | FIGURE A(b) |
| `Buffer Level/System_Utility_By_Users_MainDev.pdf` | **APPENDIX** | |
| `QoE/QoE_By_Content_DeltaU.pdf` | **MAIN_TEXT** | FIGURE B(a) |
| `QoE/QoE_By_Network.pdf` | **MAIN_TEXT** | FIGURE B(b) |
| `QoE/Loot_Holdout_DeltaU_By_Users.pdf` | **MAIN_TEXT** | FIGURE C(a) |
| `QoE/Mechanism_Decomposition_Loot.pdf` | **MAIN_TEXT** | FIGURE C(b); PRIMARY_MECHANISM |
| `QoE/MoQ_Shared_vs_Unicast.pdf` | **MAIN_TEXT** | FIGURE D(a) |
| `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf` | **MAIN_TEXT** | FIGURE D(b); cross-stack only |
| `QoE/Weak_User_Rq_Loot.pdf` | **APPENDIX** | |
| `Throughput/System_Throughput_Bar_4G.pdf` | **MAIN_TEXT** | FIGURE E(a) |
| `Throughput/System_Throughput_Bar_5G.pdf` | **MAIN_TEXT** | FIGURE E(b) |
| `Throughput/System_Throughput_Bar_Default_Mix.pdf` | **MAIN_TEXT** | FIGURE E(c) |
| `Throughput/System_Throughput_Bar_Wifi.pdf` | **APPENDIX** | |
| `Throughput/System_Throughput_Bar_Fiber_Optic.pdf` | **APPENDIX** | |
| `Throughput/System_Throughput_Bar_5G_Dominant.pdf` | **APPENDIX** | |
| `Throughput/System_Throughput_Bar_Wifi_Dominant.pdf` | **APPENDIX** | |
| `User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf` | **DISCUSSION** (panel a of optional 1×3) | else SUPPORTING_ONLY if Discussion cut |
| `User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf` | **DISCUSSION** (panel b) | else SUPPORTING_ONLY if Discussion cut |
| `User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf` | **DISCUSSION** (panel c) | **not** lone MAIN_TEXT (supersedes V5) |
| `User_Experience_Trade-off/TierB_Rb_vs_U_WiFi.pdf` | **SUPPORTING_ONLY** | |
| `User_Experience_Trade-off/TierB_Rb_vs_U_Fiber_Optic.pdf` | **SUPPORTING_ONLY** | |

Out of MAIN/APPENDIX paper body (fail-closed / duplicate / contact sheets): TTFB audits, Fig.4 fluidity, continuity timeseries, true buffer_level, scheme2–5 byte aliases, contact sheets — see `SKIPPED_FIGURES.md` / semantic map “Out of scope.”

---

## Anti-cherry-pick rationale

### Throughput FIGURE E triad

| Check | Evidence |
|---|---|
| Structural coverage, not max-ΔU | Constrained / high-capacity / heterogeneous — matches access-regime diversity needed for physical-load claims |
| Same triad as V5 MAIN_TEXT throughput | V5 audit already froze 4G / 5G / Default Mix for paper-order; remaining four profiles → appendix |
| Profile agreement | Semantic map: filename ↔ script ↔ `dev.json` all `agree: true` |
| Not a QoE win selector | Throughput is capacity/pressure context; semantic map marks `higher_preferable` null for TX axis |

### Rb–U Discussion triad (same three profiles)

| Check | Evidence |
|---|---|
| Prefer combine-three over pick-one-win | Curator forbids Default Mix alone in MAIN_TEXT; requires 4G+5G+Default Mix if shown |
| Not largest-MD2G-win selection | V5: “Representative Rb–U … Default Mix (central mixed access), **not selected by largest MD2G win**.” Extending to 4G+5G completes coverage rather than searching Fiber/WiFi for prettier stars |
| Symmetric to FIGURE E | Same three `network_key`s as physical-load main panels → selection rule is shared and predeclared |
| Causal honesty | Semantic map binding caveat + PRIMARY_MECHANISM = `Mechanism_Decomposition_Loot.pdf` |
| Leftover profiles stay supporting | WiFi / Fiber remain SUPPORTING_ONLY so authors cannot later promote a better-looking singleton |

### What would have failed anti-cherry-pick

- MAIN_TEXT Rb–U = only Fiber or only WiFi after inspecting outcomes.
- MAIN_TEXT Rb–U = Default Mix alone while omitting constrained/high-cap companions.
- Captioning Rb–U as causal “lower stall/pressure ⇒ higher U” without pointing to C(b).
- Mixing GROOT/Rolling into same-substrate ranking figures.

---

## Count summary

| Bucket | n (semantic-map set of 22) |
|---|---|
| MAIN_TEXT (A–E panels) | 11 |
| DISCUSSION (optional Rb–U 1×3) | 3 |
| APPENDIX | 6 (MainDev + Weak_User_Rq + 4 throughput) |
| SUPPORTING_ONLY (residual Rb–U) | 2 (WiFi, Fiber) |
| **Total** | **22** |

If Discussion Rb–U is cut for space: DISCUSSION 3 → SUPPORTING_ONLY; MAIN_TEXT count unchanged at 11.

---

## Terminal tokens (return to orchestrator)

```
TOP_CONFERENCE_CURATION_PASS=true
RB_U_DECISION=INCLUDE_OPTIONAL_DISCUSSION_1x3
RB_U_PANELS=4G+5G+Default_Mix
RB_U_IN_MAIN_A_E=false
```
