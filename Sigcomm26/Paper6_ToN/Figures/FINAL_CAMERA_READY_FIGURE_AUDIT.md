# FINAL_CAMERA_READY_FIGURE_AUDIT

**Terminal token:** `TON_FINAL_CAMERA_READY_FIGURES_PASS`  
**Preview:** `Figures/FINAL_CAMERA_READY_FIGURE_PREVIEW.pdf`  
**Map:** `Figures/FINAL_MAIN_TEXT_FIGURE_MAP.md`  
**Date:** 2026-08-31

Scientific figure **design is frozen**. This audit covers only explicit blocker repairs + independent six-auditor certification.

---

## Blocker repair status

| # | Blocker | Repair | Status |
|---|---|---|---|
| 1 | Mechanism legend clips “Observed ΔU” | 2×2 legend, fontsize 9.5, extra top margin | **PASS** |
| 2 | Unicast Ro=0 hollow △ clipped | `xlim(-0.08, 1.04)`, ticks 0…1, value remains **exactly 0** | **PASS** |
| 3 | Rb–U Fiber/Default Mix profile labels on stars | Deterministic slot placer (prefer UL; fallback LR); Users legend top row | **PASS** |
| 4 | Overlapping trade-off markers | Open red star (`facecolor=none`, edge `#D7191C`, lw≈1.4) when MD2G≈baseline | **PASS** |
| 5 | Better arrow too prominent | lw 0.7, mutation_scale 6.5, font 10, color `#666/#777` | **PASS** |
| 6 | Throughput MAIN needs shared legend 1×3 | `Throughput/System_Throughput_MainText_1x3.pdf` (4G/5G/Default Mix) | **PASS** |

Optional Discussion Rb–U uses `TierB_Rb_vs_U_Discussion_1x3.pdf` with one shared strategy legend (strategies UL, Users UR).

---

## Six independent auditor gates

| Auditor | File | Token |
|---|---|---|
| 1 Scientific semantics | `_audit_child_1_scientific_semantics.md` | `SCIENTIFIC_SEMANTICS_PASS` |
| 2 Top-conference visual | `_audit_child_2_top_conference_visual.md` | `TOP_CONFERENCE_VISUAL_PASS` |
| 3 Collision / clipping | `_audit_child_3_collision_clipping.md` | `COLLISION_FREE_PASS` |
| 4 Effective 10pt | `_audit_child_4_effective_10pt.md` | `EFFECTIVE_10PT_PASS` |
| 5 Evidence curation | `_audit_child_5_evidence_curation.md` | `EVIDENCE_CURATION_PASS` |
| 6 Camera-ready chair | `_audit_child_6_camera_ready_chair.md` | `CAMERA_READY_FIGURE_CHAIR_PASS` |

All six tokens present. No waiver.

---

## Effective 10pt (after inclusion)

Method: IEEEtran 10pt twocolumn preview; PyMuPDF LiberationSans spans (matplotlib figure text); native inclusion widths ≈ 3.35 in / full textwidth for 1×3.

| Role | Effective range | Contract |
|---|---|---|
| Axis labels | 9.5–10.5 | PASS |
| Tick / legend | ≥9.0–10.5 | PASS |
| Panel / profile | 9.5–10.5 | PASS |
| Better | ≈10 | PASS |
| Important figure text floor | ≥9.0 | PASS (math single-letter subscripts o/q/b excluded) |

Machine measure: `audit_final_camera_ready_10pt.py` → `EFFECTIVE_10PT_PASS` (preview figure min ≈ 9.27 pt).

---

## Main-text composition

See `FINAL_MAIN_TEXT_FIGURE_MAP.md`.

- A: ECDF + scheme1 scaling  
- B: Content ΔU + Network heatmap (all 7 networks)  
- C: Loot ΔU + Mechanism  
- D: Shared vs Unicast + H2 DASH  
- E: Throughput **shared-legend** 1×3 (4G / 5G / Default Mix)  
- Optional Discussion: Rb–U **shared-legend** 1×3 (operating-point only)

Throughput coverage triad is structural (constrained / high-cap / heterogeneous), not MD2G-gain ranked. Remaining throughput slices stay Appendix.

---

## Invariants

`verify_visual_redesign_invariants.py` → `SCIENTIFIC_INVARIANT_CHECKS_PASS` (values / aggregation unchanged).

---

## FAIL-CLOSED checklist

- [x] SCIENTIFIC_SEMANTICS_PASS  
- [x] TOP_CONFERENCE_VISUAL_PASS  
- [x] COLLISION_FREE_PASS  
- [x] EFFECTIVE_10PT_PASS  
- [x] EVIDENCE_CURATION_PASS  
- [x] CAMERA_READY_FIGURE_CHAIR_PASS  

**TON_FINAL_CAMERA_READY_FIGURES_PASS**
