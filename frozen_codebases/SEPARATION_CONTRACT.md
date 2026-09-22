# CODE SEPARATION CONTRACT (binding)

Created: 2026-08-15T09:20:42.438822+00:00

## Two titled trees

| Title | Path | Authority |
|------|------|-----------|
| MM26 | `./frozen_codebases/MD2G_MM26_CameraReady_Final` | MM26 camera-ready (Cast + cmd68/69/70) |
| ToN  | `./frozen_codebases/MD2G_ToN_Native9rep` | ToN native-9rep / Paper6_ToN |

## Rules

1. **Never** merge policy/controller changes across these two trees.
2. Live monorepo may still temporarily wire ToN → MM26 host via env flags; that is
   **technical debt**. New work must edit only the matching titled tree, then sync
   deliberately one way.
3. Paper claims must cite the matching tree + freeze docs, not a mixed hash.
4. Deleting either tree requires a new dated freeze; do not overwrite in place silently.

## Pointers in monorepo

- This file: `frozen_codebases/SEPARATION_CONTRACT.md`
- MM26 publish source of truth remains `MM26/_publish/MD2G_Cast` until replaced.
- ToN live science remains under `Sigcomm26/Paper6_ToN/` until migration completes.
