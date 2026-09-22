# Buffer Level folder — metric honesty

## True Sigcomm Buffer Level family (buffer_level_sec vs users/strategy)

**FAIL CLOSED.** Audited VALID `client_*_perf.csv` on canary (122/122) and MAINDEV sample
(265 cells with perf): `buffer_level_sec` is identically 0.0. No truthful buffer-occupancy
figure can be regenerated from frozen raw evidence.

See also: stall/TTFB audits — the same perf instrumentation left several client fields as
unimplemented placeholders.

## What *is* in this folder

Grouped-bar **System Utility \(U\)** plots that **reuse the Buffer-Level-By-Users chart
grammar** (scheme1 colors, figsize, fonts) for the ToN Tier-B concurrency crossover:

- `System_Utility_By_Users_scheme1.pdf` (alias `Buffer_Level_By_Users_scheme1.pdf`)
- `System_Utility_By_Strategy_scheme*.pdf`
- `System_Utility_By_Users_MainDev.pdf`

These are **not** buffer-occupancy figures. Captions must say System Utility \(U\).
