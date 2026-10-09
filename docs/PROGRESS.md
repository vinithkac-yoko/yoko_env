# Progress

## Phase 0: scaffold (done, awaiting Kasi's approval)

Done:
- Spec and Addendum 1 saved; contradictions folded into `BUILD_SPEC.md` (tagged **[A1]**).
- `uv` workspace, 8 package skeletons, `yoko` CLI (`serve` works; others print their phase).
- Import-linter layering plus the "no model SDK outside agent" contract.
- FastAPI app: `/api/health`, `/api/build` (git sha, Seamly2D pin, formats, fixtures hash), `/api/fixtures` (bearer `STUDIO_TOKEN`; 503 if unset), serves the built studio.
- Studio: Vite + React + TS + Tailwind status page with a fixtures list.
- Fixtures committed with a hash manifest that a test enforces: basic set, measurement file, example plan sheet, DC008 tech pack.
- ADRs 0001 to 0010, `COVERAGE.md` (draft), `FILE_HEALTH.md`, `ARCHITECTURE.md`.
- CI workflow and Dockerfile.

Not done, on purpose:
- Railway deploy: needs you to create the project (Phase 0 variable: `STUDIO_TOKEN`).
- `JUNIOR_SWEAT_TEE_compressed.pdf` and `Bottom_spec.pdf`: they did not arrive with the addendum either. Examples only; nothing depends on them.
- Playwright smoke test for the studio: added in Phase 10 with the real screens; Phase 0 has a vitest unit test and a manual Chromium check.
- Oracle image and GitHub Actions job: Phase 2.

## Decisions from Kasi, 2026-10-09

- Create `main` from the session branch: approved, but the push was refused in the session. Kasi creates it (see chat); Railway can deploy the session branch meanwhile (`docs/DEPLOY.md`).
- ADR 0009 seed ranges and levels: approved. Held-out pairings still open.
- Size coverage for multi-size checks: header sizes 34 to 42 (UK 6 to 14): approved.
- Landmark vocabulary goes to the pattern makers as a **sheet** (Phase 3).
- Phase 1 plan: approved.
- `alltools_pattern.sm2d` as the parity fixture: approved. Also run Seamly2D's other test patterns through the pinned Seamly2D, upgrade them and test them (Phase 2, in CI; see below).

## Seamly2D's own test patterns (Phase 2)

Source: `src/test/CollectionTest/share` in the Seamly2D repo (about 40 files, mostly old formats; Addendum 1 §17). No link needed: the repo is cloned read-only in the session.
Plan: a GitHub Actions job builds the pinned Seamly2D (Qt 6.11, as its own CI does), opens and re-saves each file to upgrade it to format 0.7.5, and commits the upgraded copies with oracle outputs to `fixtures/external/seamly2d/`. Open question for Phase 2: whether the Seamly2D binary can open and save headlessly. Its command line is export-oriented (basename, destination, measurement file, format, gradation) and has a `--test` option; if it cannot save, a small harness over its converter library is the fallback.

## Environment variables by phase

| Phase | Variables |
| --- | --- |
| 0 | `STUDIO_TOKEN` |
| 1 to 5 | none new |
| 6 | `DATABASE_URL` (session snapshots), `BUCKET_*` |
| 7 | `ANTHROPIC_API_KEY` |
| 7 (later) | `OPENAI_COMPAT_BASE_URL`, `OPENAI_COMPAT_API_KEY` |

## Phase 1 plan (engine core), for review before I code

Scope: formulas, points, lines, arcs, curves, evaluation, validation, fork / undo / hash, plus provenance fields, readers for formats 0.6.8 to 0.7.5 and the landmark sidecar loader.

1. **Formula language.** Port Seamly2D's grammar (`src/libs/qmuparser`) exactly: operators, ternary, built-in functions, measurement and variable names (with `#`), geometry references (`Line_A_B`, `AngleLine_A_B`, `Spl_...`, `Arc_...`, `CurrentLength`, `CurrentSeamAllowance`). Parse once to an AST, no `eval`, record dependency edges. Tests cite the source file each rule comes from.
2. **Object model and graph.** Ordered operations, stable labels plus internal UUIDs, `dependents` and `dependencies`, incremental re-evaluation (target under 5 ms for one edit on 500 objects).
3. **Geometry for the object types in the basic set first** (the 15 types in `COVERAGE.md` marked phase 1), checked against hand-computed values; the oracle comes in Phase 2.
4. **Validation** after every mutation, with typed errors.
5. **Session:** `apply` (atomic), `undo`, `fork` (copy-on-write), `snapshot`, `state_hash`, `diff`.
6. **Reader** for 0.6.8 (our file) first, then 0.6.9 to 0.7.5 deltas, using the pinned source's converter as the spec.
7. **Checkpoint:** the basic set evaluates and renders with every object Seamly2D draws, in one style.

Open questions for Phase 1 are in the chat summary.
