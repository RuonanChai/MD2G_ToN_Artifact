# V6_CAMERA_READY_CHAIR

Authority: Camera-Ready Figure Chair (ToN V6).  
Independent verification of all figure gates under `Sigcomm26/Paper6_ToN/Figures/`.  
Date: 2026-08-31.

```
V6_CAMERA_READY_FIGURE_PASS=true
```

---

## Checklist

| # | Gate / evidence | Result |
|---|---|---|
| 1 | `V6_FIGURE_SEMANTIC_MAP.json` → `FIGURE_SEMANTIC_MAPPING_PASS=true` | **PASS** |
| 2 | `V6_MAIN_TEXT_CURATION.md` → `TOP_CONFERENCE_CURATION_PASS=true` | **PASS** |
| 3 | `V6_10PT_TYPOGRAPHY_AUDIT.json` → `EFFECTIVE_10PT_TYPOGRAPHY_PASS=true` | **PASS** |
| 4 | `V6_LAYOUT_AUDIT.md` → `FIGURE_LAYOUT_PASS=true` | **PASS** |
| 5 | `V6_SCIENTIFIC_REVIEW.md` → `SYSTEMS_METHODOLOGY_REVIEW_PASS=true` | **PASS** |
| 6 | `V6_SCIENCE_FREEZE.json` exists | **PASS** |
| 7 | `FIGURE_VISUAL_REDESIGN_V6_CONTACT_SHEET_PAPER_ORDER.pdf` exists | **PASS** |
| 8 | `FIGURE_VISUAL_REDESIGN_V6_CONTACT_SHEET_ALL.pdf` exists | **PASS** |
| 9 | Spot-check: TierB_Rb_vs_U filename↔profile (4g/5g/wifi/fiber_optic/default_mix) | **PASS** |
| 10 | Spot-check: `pdftotext` on `TierB_Rb_vs_U_4G.pdf` contains Rule, Better, 4G, System utility | **PASS** |

---

## Spot-check notes (Chair)

**Filename ↔ script NETWORK ↔ on-PDF profile**

| File | Script `NETWORK=` | pdftotext profile label |
|---|---|---|
| `TierB_Rb_vs_U_4G.pdf` | `4g` | `4G` |
| `TierB_Rb_vs_U_5G.pdf` | `5g` | `5G` |
| `TierB_Rb_vs_U_WiFi.pdf` | `wifi` | `Wi-Fi` |
| `TierB_Rb_vs_U_Fiber_Optic.pdf` | `fiber_optic` | `Fiber Optic` |
| `TierB_Rb_vs_U_Default_Mix.pdf` | `default_mix` | `Default Mix` |

Semantic-map `tierb_rb_u_profile_agreement`: all five `agree: true`.

**`pdftotext TierB_Rb_vs_U_4G.pdf`:** contains `Rule`, `Better`, `4G`, `System utility` (full axis string `System utility U`).

---

## Terminal token

```
V6_CAMERA_READY_FIGURE_PASS=true
```
