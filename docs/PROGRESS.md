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

## CI oracle workflow: added (Kasi said yes, 2026-10-10)

`.github/workflows/oracle.yml` builds the pinned Seamly2D with Qt 6.11.1, dumps the basic set, and checks the engine, the committed oracle file and the real-Qt vectors against it. It was written without being able to run it here (no Qt 6.11 download from the session), so its first run on GitHub is its test; fixing it is my job if it fails.

## Seamly2D's own test patterns (Phase 2)

Source: `src/test/CollectionTest/share` in the Seamly2D repo (about 40 files, mostly old formats; Addendum 1 §17). No link needed: the repo is cloned read-only in the session.
Plan: a GitHub Actions job builds the pinned Seamly2D (Qt 6.11, as its own CI does), opens and re-saves each file to upgrade it to format 0.7.5, and commits the upgraded copies with oracle outputs to `fixtures/external/seamly2d/`. Open question for Phase 2: whether the Seamly2D binary can open and save headlessly. Its command line is export-oriented (basename, destination, measurement file, format, gradation) and has a `--test` option; if it cannot save, a small harness over its converter library is the fallback.

## Phase 1 log

- **Slice 1, formula language: done** (2026-10-09). `yoko_engine.formula`: tokenizer, parser to an immutable AST, evaluator, 35 built-in functions, dependency extraction, error codes with hints, size caps. Ported from Seamly2D's `qmuparser`; every rule cites its source file. 131 tests including: every formula in the basic set parses, the file's own variables evaluate at base size, and property tests (the parser only ever raises `FormulaError`). Quirks copied and deliberate differences: `docs/formula-differences.md`.
- **Slice 2, model, reader, first point kinds: done** (2026-10-09). `yoko_engine.model` (immutable pattern, objects keep every attribute), `yoko_engine.geometry` (Qt `QLineF` port: y-down, angles counter-clockwise on screen), `yoko_engine.evaluator` (single, endLine, alongLine, normal, bisector, intersectXY, lineIntersectAxis, line; `Line_`/`AngleLine_` variables; `CurrentLength`), `yoko_io.seamly` (0.6.8 patterns and multisize tables, defusedxml). The real basic set reads in 16 ms and evaluates in 15 ms; 197 of its points compute. Not yet computed: arcs, curves, `pointOfContact`, `trueDarts`, `curveIntersectAxis`, `flippingByLine` (52 objects; they block ~230 downstream objects). ADR 0011 records the pixel-scale kernel decision.
- **Oracle, running locally: done** (2026-10-09). Seamly2D `v2026.10.5.154` builds on this machine against Ubuntu's Qt 6.4 with four small compatibility patches (`docker/oracle/qt64-compat.patch`; Qt 6.5+ APIs), plus our dump hook (`docker/oracle/yoko-oracle-dump.patch`: with `YOKO_ORACLE_DUMP=out.json` it writes every point, curve, arc and variable Seamly2D computed). `docker/oracle/build-local.sh` rebuilds it; `scripts/oracle_dump.sh` runs it headless (offscreen, `--test`). The GitHub Actions oracle job (Phase 2) will build with Qt 6.11.1 and apply only the dump patch; `download.qt.io` is not reachable from this session, so the local build is for development.
- **Bit-exact agreement with Seamly2D.** `tests/test_qt_vectors.py`: our `QLineF` port equals real Qt on 4000 random lines for length, angle, angleTo, setAngle, setLength, unitVector, normalVector and intersects (found by differential testing: Qt's length is glibc `hypot`, `setLength` is `p1 + d / length * len`, `setAngle` uses `qDegreesToRadians`). `tests/test_oracle_basic_set.py`: all 197 points and 747 variables the engine computes equal Seamly2D's, exactly (0 deviation, not just under 0.01 mm). The test has a ratchet (`MIN_POINTS`, `MIN_VARIABLES`) that only goes up as more of the language is implemented.
- **Slice 3, the rest of the basic set's language: done** (2026-10-09). Arcs, cubic Beziers and Bezier paths (flattened lengths by Seamly2D's own subdivision; paths re-derive each segment's handles like `VSpline`), `pointOfContact`, `trueDarts`, `curveIntersectAxis` (with the curve split it performs, for Beziers, paths and arcs), `flippingByLine` for points, and a `QTransform` port. **The whole basic set now evaluates with zero issues and matches Seamly2D exactly: all 302 calculation points and all 1573 variables, bit for bit** (the other 145 points Seamly2D holds are piece nodes, Phase 3). Differential tests against real Qt: `QLineF` (4000 cases), `QTransform` flip (2000), `QPainterPath::length` (400), all exact.
- Findings worth knowing: `VSpline` does not store control points, it re-derives them from an angle and a handle length (changes the last bit, visible in path lengths); Qt's `length()` is glibc `hypot`; `curveIntersectAxis` silently fails when its base point is exactly the scene origin (0, 0); `AngleLine_` values are floored to 5 decimals.
- **Slice 4, validation, session, provenance, landmarks, render: done** (2026-10-09).
  - Incremental evaluator: per-object records (points, curves, symbols, what each reads), early cutoff when an object's outputs do not change, forward-reference guards. A random-edit test checks incremental == full evaluation. Numbers from `scripts/bench_engine.py` (96-object pattern): a late edit about 1.1 ms, an early edit about 4.9 ms, a fork about 0.1 ms. Both are under the 5 ms target.
  - `validation.py`: typed issues after every mutation, in linear time.
  - `PatternSession`: `apply` (all-or-nothing; an action is rejected only if it introduces new error-level issues), `undo`, cheap `fork`, `snapshot`, `state_hash`, `diff`, `dependents` / `dependencies`.
  - Provenance on every action (who, why, which step), exported with `sidecar()`.
  - Landmark sidecar: `Landmarks` plus a YAML loader in `yoko_io.landmarks`. The vocabulary itself comes from the pattern makers (Phase 3 sheet); the loader invents none.
  - `yoko_io.render.render_svg`: draws everything Seamly2D draws, one style, all groups on (ADR 0003). `lineType="none"` draws no line.
  - Studio and server: `/api/library/base` and `/api/library/base/render.svg` (token-protected); the studio shows the locked "Aldrich 6th Ed Basic Pattern" with its summary and drawing.
- **Phase 1 checkpoint reached:** the basic set evaluates (302 points, 37 curves, 17 variables from 425 objects, 0 issues, identical to Seamly2D) and renders with all lines visible.
- Not done on purpose: rotate / move / mirror-by-axis operation tools (Phase 3); Playwright smoke test (Phase 10).

## Phase 2 log (IO: lossless files, upgrades, oracle in CI)

- **Lossless writer: done** (2026-10-10). `yoko_io.xmlwrite` copies Qt's `QXmlStreamWriter` formatting; `read_pattern` / `write_pattern` keep comments, text, the order of sections, CRLF line endings and root attributes. **The basic set writes back byte for byte**, and so do the 23 patterns the pinned Seamly2D re-saved from Seamly2D's own test folder (one is 6 MB). ADR 0012.
- **Formats 0.6.8 to 0.7.5 read; measurement formats read** (multisize 0.4.0 to 0.4.5, root `vst` or `smms`; individual 0.3.0 to 0.3.4, root `vit` or `smis`, including values that are formulas such as `(height_neck_back - height_knee)`). Duplicate, empty or invalid measurement names fail with a clear message (the four `broken/*.smis` files).
- **Upgrades verified by the oracle.** New hooks in the oracle patch (`YOKO_ORACLE_SAVE`, `YOKO_ORACLE_CONVERTED_DIR`) make the real Seamly2D save a pattern and keep what its converters produced. `upgrade_pattern` (0.6.8 to 0.7.5) equals Seamly2D's own save byte for byte; `upgrade_measurements` equals its converter on every file in range (the basic set's table, 14 individual files). Finding: the multisize format 0.4.5 renames the root `vst` to `smms`, so our own table (0.4.4) is not the pinned format.
- **Seamly2D's own test patterns** (`fixtures/external/seamly2d/`, GPL note in its README): 41 patterns, 24 individual and 7 multisize measurement files. The pinned Seamly2D opens 23 of the 41; the other 18 fail in Seamly2D itself (a measurement file the folder does not contain, schema errors in old formats, an empty file, one deliberate missing measurement). `alltools_pattern.sm2d` (0.7.4) round trips and upgrades like the rest. **Across all 23, the engine never gets a point wrong** (exact equality with Seamly2D) and reproduces 1 to 166 points per pattern, limited only by tools not built yet. `tests/external_ratchet.json` only goes up.
- **CI oracle workflow added** (`.github/workflows/oracle.yml`): builds the pinned Seamly2D with Qt 6.11.1, regenerates every committed oracle file and fails on any difference, then runs the exactness tests. It could not be run in the session (no Qt 6.11 download), so its first run on GitHub is its test.

Backlog the test patterns give Phase 3 (issues per not-yet-evaluated kind over the 23 patterns; `scripts/external_report.py` prints the current list): `simple` 91, `simpleInteractive` 66, `lineIntersect` 46, `pathInteractive` 38, `height` 23, `cutSpline` 22, `shoulder` 12, `rotation` 10, `path` 10, `cutSplinePath` 9, then a handful each of `arcWithLength`, `pointOfIntersectionCircles`, `pointOfIntersectionArcs`, `pointFromCircleAndTangent`, `triangle`, `pointOfIntersectionCurves`, `cutArc`, `pointFromArcAndTangent`, `flippingByAxis`, `moving`. All the "undefined name" issues in those patterns are knock-on effects of these.

- **PNG render: done.** `yoko_io.render.render_png` draws the same scene as the SVG (shared `build_scene`) with Pillow, which is a new dependency of `yoko_io` (wheels only, no system libraries or fonts). 0.26 s for the whole basic set at 1200 px; deterministic.

Checkpoint check: the basic set round-trips byte for byte, and the engine equals Seamly2D exactly (deviation 0, the limit was 0.01 mm). Waiting for the first green run of the CI oracle job.

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
