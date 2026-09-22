# FINAL_FIG34_REFINEMENT_AUDIT

Layout-only. Data, metrics, captions, filenames, and LaTeX labels unchanged.

FIG3_STATUS=PASS
FIG4_STATUS=PASS
FONT_STATUS=PASS
PDF_RENDER_STATUS=PASS
SEMANTIC_PRESERVATION=PASS

## This round (Fig.1/2 line weight, full names, ticks, no clip)

- Fig.1/2 stroke equalized at 1.20 pt (MD2G not thickened).
- Legend uses full names: MD2G / Heuristic / Clustering / Rule (`pdftotext`).
- Fig.1 y-ticks 0.0, 0.2, 0.4, 0.6, 0.8, 1.0; Fig.2 y-ticks 0.5, 0.6, 0.7, 0.8.
- ECDF xmax/ymax padded; Fig.3 legend markers reduced so they are not cropped.
- Fig.4 y-labels restored to full network names (Fiber Optic, Default Mix, Wi-Fi Dominant, 5G Dominant).
- Native width 1.658 in (= 0.495 ACM columnwidth). Pair 1 height 1.70 in; pair 2 (Fig.3/4) height 1.28 in so the heatmap is not a tall strip.
- Fig.3: 20/60/100 on one horizontal line; marker diameter 3.5 pt via plot(markersize). Right xlim padded so Red&Black u=100 is unclipped. x = true ΔU.
- Fig.4: top horizontal colorbar; pair-2 left margin 0.44.
- Preview minipages `0.495\columnwidth` with `0.01\columnwidth` gap.
- `PAIR_HEIGHT_ALIGNMENT_PASS`
- `SCIENTIFIC_INVARIANT_CHECKS_PASS`
- ACM preview: 2 pages. One 1.19 pt overfull is preview body hyphenation, not a figure box.
