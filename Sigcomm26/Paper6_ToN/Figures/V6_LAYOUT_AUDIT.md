# V6_LAYOUT_AUDIT

Authority: Figure Layout Auditor (ToN V6 camera-ready).  
Scope: all `TierB_Rb_vs_U_*.pdf`, MAIN_TEXT panels in `V6_MAIN_TEXT_CURATION.md`, and `V6_PAPER_PREVIEW.pdf`.  
Method: `pdfinfo` / `pdftotext` / `pdftohtml -xml` / `mutool draw -F txt` + 200 dpi `pdftoppm` visual review. **No redesign.**  
Re-audit after layout repairs: **2026-08-31T15:40:05Z** (source PDFs dated 10:36–10:37).

```
FIGURE_LAYOUT_PASS=true
```

---

## Terminal verdict

| Token | Value |
|---|---|
| `FIGURE_LAYOUT_PASS` | **true** |
| Blocking families | **none** (hard clips / hard overlaps cleared) |

Prior blocking defects on Rb–U (Rule + y-label MediaBox clip; Users↔data; Default Mix↔star) and MAIN B(a) Content ΔU (`100 use` truncation) are **fixed**. Soft notes remain (small Better arrow; Heur./Clust. abbreviations; preview Fig.6 still repeats strategy legend ×3; outer whitespace still tight).

---

## Prior failures — re-check

| Prior failure | Evidence after repair | Result |
|---|---|---|
| Rule + ylabel clipped | All five Rb–U: `pdftotext`/`mutool` show `Rule` + `System utility U`. `pdftohtml`: Rule `left=218` `right=244` ≤ page `246`; ylabel fragments `left=11` (≥0; prior was `left=-9`). Raster: both fully readable. | **FIXED** |
| Users legend overlapping data | Visual on 4G / 5G / Default Mix / WiFi / Fiber: Users box clear of markers/lines. | **FIXED** |
| Default Mix label on red star | `Default Mix` at `top≈37` upper-right; largest MD2G star readable; no text-on-marker collision. | **FIXED** |
| Content legend truncated `100 use` | `QoE_By_Content_DeltaU.pdf`: legend `Users` / `20` / `60` / `100` complete; no `use` fragment / no `100 use`. | **FIXED** |

Pass gate (hard clips/overlaps only): **met**. Better arrow may stay small. Abbreviated `Heur.` / `Clust.` OK because `Rule` is present.

---

## Smoking-gun MediaBox (post-repair)

`pdftohtml -xml` on all `TierB_Rb_vs_U_*.pdf` (page **246×280**; PDF pts ≈ **164.16×187.2**):

| Element | XML position | Issue |
|---|---|---|
| Legend `Rule` | `left=218`, `width=26` → right `244` | **Inside** page |
| Y-label fragments (`S`…` U`) | `left=11`, `width≈0` | Rotated-text pdftohtml artifact only; **on-page** (pdftotext + raster confirm full string) |
| Strategy labels | `MD2G`, `Heur.`, `Clust.`, `Rule` | Complete |
| `Better` | in-page UL | OK (small, allowed) |
| Profile labels | `4G` / `5G` / `Default Mix` / `Wi-Fi` / `Fiber Optic` | In-page; Default Mix clear of star |

`QoE_By_Content_DeltaU.pdf` (page **361×264**; PDF ≈ **241.2×176.4**): legend `100` full; soft `Red-and-Black` `left≈-1` and x-label near bottom — **not** hard truncation of `100 use`.

---

## Checklist summary

| # | Check | Rb–U family | MAIN A–E | Preview |
|---|---|---|---|---|
| 1 | Better arrow size small | **PASS** (allowed small) | N/A | **PASS** |
| 2 | Arrow / data collision | **PASS** | N/A | **PASS** |
| 3 | Arrow / legend collision | **PASS** | N/A | **PASS** |
| 4 | Legend / data collision | **PASS** (Users clear) | **PASS** | **PASS** |
| 5 | Clipped text (hard) | **PASS** (Rule + y-label inside) | **PASS** (Content ΔU `100` full) | **PASS** (inherits fixed sources) |
| 6 | Clipped star markers (data) | **PASS** | N/A | **PASS** |
| 7 | User-size legend overlap | **PASS** | N/A | **PASS** |
| 8 | Duplicate legends | PASS per single PDF | PASS | **WARN** Fig.6: strategy legend ×3 (soft; not a hard clip) |
| 9 | Network/profile identity | **PASS** | **PASS** where required | **PASS** |
| 10 | Outer whitespace 12–22% (max 30%) | WARN (~1–2%; ≤30%, no clip) | WARN (tight but no clip) | Page margins OK |
| 11 | Panel balance | PASS / soft WARN | **PASS** | Fig.5/6 1×3 OK |
| 12 | Readability | **PASS** | **PASS** | **PASS** for hard text |

---

## Rb–U specific confirmation

| Requirement | Result |
|---|---|
| Red MD2G star visible | **PASS** |
| Better points upper-left | **PASS** |
| Better secondary to data | **PASS** (small gray italic OK) |
| Network profile explicitly identifiable | **PASS** |
| User-count encoding understandable | **PASS** (Users 20/60/100; placement clear) |
| Arrow+label ≪ 8% axes area | **PASS** |

### Per-file Rb–U

| File | Stars | Better UL | Profile | Users↔data | Strat legend clip | Y-label clip | Notes |
|---|---|---|---|---|---|---|---|
| `TierB_Rb_vs_U_4G.pdf` | PASS | PASS | 4G | **PASS** | **PASS** Rule | **PASS** | Heur./Clust. abbr. OK |
| `TierB_Rb_vs_U_5G.pdf` | PASS | PASS | 5G | **PASS** | **PASS** Rule | **PASS** | |
| `TierB_Rb_vs_U_Default_Mix.pdf` | PASS | PASS | Default Mix | **PASS** | **PASS** Rule | **PASS** | Profile clear of star |
| `TierB_Rb_vs_U_WiFi.pdf` | PASS | PASS | Wi-Fi | **PASS** | **PASS** Rule | **PASS** | |
| `TierB_Rb_vs_U_Fiber_Optic.pdf` | PASS | PASS | Fiber Optic | **PASS** | **PASS** Rule | **PASS** | |

Discussion triad (4G / 5G / Default Mix) is layout-ready for hard-clip criteria.

---

## MAIN_TEXT (V6_MAIN_TEXT_CURATION A–E)

| Figure | Path | Layout | Notes |
|---|---|---|---|
| A(a) | `QoE/QoE_By_Strategy.pdf` | **PASS** | Unchanged prior PASS |
| A(b) | `Buffer Level/System_Utility_By_Users_scheme1.pdf` | **PASS** | |
| B(a) | `QoE/QoE_By_Content_DeltaU.pdf` | **PASS** | Legend `Users` + `20`/`60`/`100`; prior `100 use` gone |
| B(b) | `QoE/QoE_By_Network.pdf` | **PASS** | |
| C(a) | `QoE/Loot_Holdout_DeltaU_By_Users.pdf` | **PASS** | |
| C(b) | `QoE/Mechanism_Decomposition_Loot.pdf` | **PASS** | |
| D(a) | `QoE/MoQ_Shared_vs_Unicast.pdf` | **PASS** | |
| D(b) | `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf` | **PASS** | |
| E(a–c) | `Throughput/System_Throughput_Bar_{4G,5G,Default_Mix}.pdf` | **PASS** | |

---

## V6_PAPER_PREVIEW.pdf

Present (3 pages, letter). Typography preview only.

| Region | Layout |
|---|---|
| Fig.1–5 (MAIN A–E) | Readable; Fig.2(a) inherits fixed Content ΔU legend |
| Fig.6 Discussion Rb–U 1×3 | Hard clips cleared (`Rule` + `System utility U` on each panel). Soft: strategy legend still duplicated ×3; optional shared-legend cleanup remains non-blocking |

---

## Non-blocking notes

1. Outer whitespace often ≪12% preferred band; acceptable while ≤30% and no hard clip.
2. Better arrow remains small by design.
3. Preview Fig.6 may later use one shared strategy legend (cosmetic).
4. pdftohtml `width≈0` on rotated y-label is **not** treated as a clip when `left≥0` and pdftotext/raster show the full string.

---

## Pass gate (this re-audit)

`FIGURE_LAYOUT_PASS=true` because:

- every Rb–U PDF keeps `Rule` and full y-label **inside** MediaBox / readable on-page;
- no Users/profile hard collisions on Discussion triad (or Fiber/WiFi);
- Content ΔU legend no longer truncates to `100 use`;
- hard clips/overlaps from the prior audit are gone.

```
FIGURE_LAYOUT_PASS=true
```
