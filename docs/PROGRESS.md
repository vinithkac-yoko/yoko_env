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

- **CI oracle: first findings.** Under Qt 6.11.1 on the runner everything Seamly2D produced matches what was committed from Qt 6.4.2 (patterns, upgrades, converted measurement files, basic-set output), after fixing the scripts (a relative binary path, a random temp-directory name and Qt-version-specific warnings in the failure notes, measurement copies stored in canonical XML). The real-Qt vectors differ by one ulp in 1 of 4000 `setAngle` cases and 1 of 2000 flip cases: bit-exactness depends on the platform's maths library (ADR 0011). The check now allows 2 ulp and says how many differ.

Checkpoint check: the basic set round-trips byte for byte, and the engine equals Seamly2D exactly (deviation 0, the limit was 0.01 mm). The CI oracle job is green on GitHub (Seamly2D built with Qt 6.11.1): every committed oracle file equals what it produced, and the exactness tests pass.

## Decisions from Kasi, 2026-10-10 and 2026-10-11 (Phase 3)

- Pillow as a dependency of `yoko_io` for PNG drawing: ok. Keep the 15 MB of fixtures: ok. Start Phase 3: yes.
- Order of work: most-used tools first. Pieces: outline geometry and round trip (no seam allowance, grainlines, labels or notches).
- Landmark vocabulary goes to the pattern makers as a spreadsheet; Kasi asked what it is for and how it is made (answered in chat). It is built but **not sent anywhere**: that needs Kasi's word.

## Answers from Kasi after the Phase 3 report, 2026-10-13

- Kasi sends the landmark sheet to the pattern makers himself.
- A piece we create should get sensible defaults (seam allowance, grainline, labels): Kasi expects yes. I propose the basic set's own values (1 cm seam allowance, grainline and labels as on its pieces); he or the pattern makers confirm before I add them.
- Matched seam edges: the sheet now has a `Seam pairs` tab to fill in.
- Duplicate labels when copying a piece: left to me; the copy is refused with a clear message (kept as is).
- Elliptical-arc cutting: left to me; not built (Seamly2D itself hangs).
- Library on disk until Phase 6: ok. Keep working on this branch; no `main`.

## Phase 3 log (tools, pieces, library)

Everything below is checked against the pinned Seamly2D, bit for bit, unless it says otherwise.

- **Every tool in the release now evaluates.** The all-tools pattern runs with no issue, and across Seamly2D's 23 openable test patterns the engine gets no point, variable or piece outline wrong (the ratchet only went up; no unknown kinds are left). Per-tool status: `docs/COVERAGE.md`.
- **Pieces.** Outlines (`VPiecePath::PathPoints`, `CorrectEquidistantPoints`, `CheckLoops`; a Qt polygon-overlap stand-in verified on 27 real calls). The basic set's 7 pieces and 61 pieces in the test patterns are exact.
- **Union of pieces** (`UnionTool`): the second piece is moved onto the first along the chosen edges; the united piece "Waist Back" in `steampunk_trousers` equals Seamly2D's outline. Only the main outline is united; seam allowance paths, internal paths and anchors are kept, not computed. The `UnionPieces` action (Phase 4+) now creates one: Seamly2D opens what we write and computes the same outline.
- **Elliptical arcs.** Seamly2D measures them with Qt's `QPainterPath::arcTo` and path flattening, so those routines are ported (from the Qt 6.4.2 source) and 20 arcs with different angles and rotations equal Seamly2D's length and angles exactly. Two Qt behaviours found by differential testing: `QPainterPath::lineTo` ignores a point equal to the last one (this changed the last bit of a full ellipse; `path_length` now does the same for every curve), and the first subpath of the arc path starts at `GetP1`.
- **`autoSmooth` and `lengthMode`** (format 0.7.4) for splines and cubic Beziers: Hobby handle lengths, the Gauss-Legendre length and the two bisection solvers. 156 curves covering every combination of the options equal Seamly2D's exactly.
- **Case patterns for differential tests.** `fixtures/patterns/cases/*.sm2d` are small patterns written for one tool in many configurations; `scripts/oracle_cases.sh` has the pinned Seamly2D compute them (`fixtures/oracle/cases/`), and CI regenerates them and fails on any difference (`elliptical_arcs`, `spline_length_modes`, `added_piece`). New tools and edits can get a case in minutes.
- **Edit and delete.** Session actions `AddPiece`, `SetPiece`, `DeletePiece`, `AddBlock`, `RenameBlock`, `DeleteBlock` join `AddObject`, `SetAttrs`, `DeleteObject`, `SetVariable`, `DeleteVariable`. A piece we create has an id, a name and its nodes; Seamly2D opens the file and computes the same outline (case `added_piece`: 7 copies of the basic set's pieces). A point that is part of a piece cannot be deleted; a deleted object leaves its groups; a piece with no area is refused; a path that crosses itself is a warning (`piece_issues`). `apply_all` makes a batch of actions all-or-nothing.
- **Pattern library.** `yoko_engine.library` (metadata, parent links, family tree, ancestors and descendants, tag and text search, a `SearchIndex` interface for embeddings later), `yoko_io.library` (on disk: `library/base` locked, `library/styles`; deriving a style copies the parent's file byte for byte and links it; the base refuses every write), `plan_copy_piece` (copy one piece with every object, variable and measurement it depends on into another pattern: ids are renumbered, labels and variables must not clash, the destination must have the measurements). API `/api/library/tree`, `/search`, `/patterns/{id}` and a family-tree panel in the studio.
- **Landmark sheet** for the pattern makers: `docs/landmarks/basic-set-landmarks.xlsx` (one tab per piece, a numbered picture, a row per outline point or curve, proposed name with confidence and reason, yellow Verdict / Correct name / Comment columns). Every name is a proposal; nothing uses one until a pattern maker confirms it. See `docs/landmarks/README.md`.

Not done, and why:

- **Cutting an elliptical arc** at an axis (`curveIntersectAxis` on an `elArc`): the pinned Seamly2D hangs in most configurations I tried (its `FindF2` search never ends), so there is nothing reliable to check a port against. The engine says `not_implemented`. Rotate, mirror and move of elliptical arcs are done and exact.
- **Seam length mismatches between matched edges** (spec, Validation): which edges match is a pattern-making rule, so this needs the pattern makers.
- Internal paths cannot be created by an action; they are kept, not computed (the depth decided with Kasi). Unions can: see the Phase 4+ log.
- The landmark sheet's LibreOffice render could not be checked in this container (LibreOffice cannot open any file here); the workbook reads back correctly with openpyxl and has no formulas.

## Phase 4 plan (tool layer), written before coding, 2026-10-13

Kasi's answers to the Phase 3 report are above; he said go ahead with my assumptions.

Deliverables (spec section 6, Addendum 1 sections 7, 8, 15):

1. **YAML tools** in `config/tools/`, one file per tool (`name`, `version`, `tier`, `description`, `parameters` as JSON Schema with `x-ref` / `x-formula` hints, `examples`, and for primitives an `engine` block saying which Seamly2D element the call builds). A loader validates each file, builds the Pydantic model and the JSON Schema, and hashes it. About 40 primitive tools (the parity matrix), the variable, piece and block tools, read tools (`get_state`, `get_object`, `find_objects`, `dependents`, `dependencies`, `measure`, `list_measurements`, `render`), library tools (`search_library`, `load_pattern`, `copy_piece_from`). **Edit and delete tools are derived** from each primitive's file (`edit_<tool>`, `delete_<tool>`), not written twice.
2. **Executor** (`Toolbox`): a tool call becomes session actions; labels and landmark names are accepted wherever an object is named; every call returns `{ok, created, changed, deleted, warnings, error?: {code, field, message, hint}}` plus a compact state diff; arguments are validated and capped (Addendum 1 section 14).
3. **Adapters**: Anthropic tools, OpenAI functions and a compact text DSL, each parsed back to the canonical call, with round-trip tests (property-based).
4. **v1 text**: every tool description and the first drafter prompt (`config/prompts/drafter/v1.md`), bundles (prompt + tool descriptions + subset) hashed.
5. **Plan schema** (`config/plan/schema.json`, versioned) with typed parameters (value + unit) that become variables `#s<step>_<param>`; plan validation (every parameter present, typed, in units, within the recipe's range once recipes exist).
6. **Recipe procedure template** `docs/manipulations/TEMPLATE.md` and first drafts of the 8 most used procedures, marked as drafts for the pattern makers: I write the structure and the geometry that is defined by the tools, never the drafting rules, and list what I need them to say.

Checks: the tools build a pattern that the pinned Seamly2D opens and computes the same (a case pattern made only through tool calls); adapter round trips; every tool file valid; every description present. Checkpoint (spec): adapter round-trip tests pass and Kasi reviews the procedures.

Order: (A) spec, loader, executor and the primitive tools; (B) edit/delete, structure, read and library tools; (C) adapters and DSL; (D) prompts and bundles; (E) plan schema and variables; (F) template and procedures.

## Phase 4 log (tool layer)

- **Tools as YAML** (`config/tools/`, 54 files): 34 primitives (the whole parity matrix), variables, pieces and blocks, `undo`, 8 read tools, 3 library tools. Each has a description that says when to use it and when not (the loader refuses a primitive without both), a JSON Schema, examples that must validate, and for primitives an `engine` block (which Seamly2D element a call builds). **54 more tools are derived**: `edit_<tool>` and `delete_<tool>` for every simple primitive (108 in all). The plain-words list is `docs/TOOLS.md` (generated; a test keeps it current).
- **Loader** (`yoko_tools.spec`): validates a file, builds the JSON Schema and the Pydantic model, hashes it (description, schema, engine and examples).
- **Runtime** (`yoko_tools.runtime.Toolbox`): arguments are checked first (types, enums, ranges, formula length 500, at most 50 to 200 items); names resolve to ids (a label, a curve name, `#<id>` for a line, or a landmark name), with "did you mean" hints; every call returns `{ok, created, changed, deleted, warnings, error?: {code, field, message, hint}, diff}` (read tools add `data`). Edit and delete check that the object was made with that tool; deletes are refused with the list of dependents.
- **Seamly2D agrees with what the tools write.** A pattern built only through tool calls (every primitive, an edit, mirrors, a rotation, a move; case `tool_calls`) is opened by the pinned Seamly2D, which computes the same points, curves and variables as the engine. Findings on the way, all fixed: arcs copied by mirror, rotate or move are named after their centre and their own id (`Arc_A21_54`), not the original's name plus the suffix (the old engine missed 20 variables in the all-tools pattern; a new check requires every variable Seamly2D has in a fully evaluated pattern); new objects get an id that no copy, piece, dart point or operation output uses; the list of reference attributes was missing 16, which also made copying a piece miss references.
- **Adapters** (`yoko_tools.adapters`): Anthropic tools, OpenAI functions and a plain text list; calls parsed back from Anthropic `tool_use`, OpenAI `tool_calls` and a one-line text DSL (`name(key=value, ...)`, JSON values). Round trips are tested for every example of every tool and, with Hypothesis, for arbitrary arguments (nested values, quotes, commas, backslashes, unicode).
- **Prompts and bundles** (`yoko_tools.bundle`): `config/prompts/drafter/v1.md` (front matter, `{{slots}}`), a bundle = prompt + tool subset with a digest over the prompt text, the subset and every tool's digest. The prompt says how the drawing works, how to work in small steps and read errors, and that amounts come from plan variables.
- **Plan schema** (`config/plan/schema.json`, version 1) and `yoko_tools.plan`: steps with typed parameters (value + unit); validation before approval (shape with the place of each mistake, step numbers, units; when recipes are known: presence, unit and range); `plan_variables` turns every amount into `#s<step>_<param>` in the pattern's unit.
- **Recipe template** `docs/manipulations/TEMPLATE.md` and **eight drafts** (slash and spread; lengthen or shorten; add or remove width at a seam; true a seam or curve; style line and split; add, move or remove a dart; re-fit the sleeve cap; reshape armhole and shoulder). They are marked as drafts. I wrote the structure and the tool calls (checked: for example setting a sleeve cap to a target length with `edit_curve_spline`), and marked every drafting rule with **(?)** as a question for the pattern makers.

Not done, on purpose: the recipes themselves, the teacher, valid actions and the status card (Phases 5 and 6); `done` and the environment API (Phase 6); groups, internal paths and unions have no tool (kept, not computed); the tool descriptions and the drafter prompt are `v1` and will need your edits.

Checkpoint (spec): adapter round-trip tests pass, and Kasi reviews the procedures.

## Phase 4+ log (changes after Kasi's Phase 4 answers)

- **Plan steps carry `refs` and `options`.** `refs` maps a role of the recipe to a landmark name and is checked against the recipe's required landmarks (a step must say where, not only how much); `options` picks a value from the list the recipe defines (for example `spread: parallel | hinged`). Recipes branch on options; there is no two-recipe split for choices.
- **Amounts are formulas over measurements.** `#CM` scaling is refused. `validate_plan_at_sizes` evaluates a plan at every size of the multisize table (and at a user's own measurement file) and reports the sizes where a formula fails or a value leaves its range.
- **Individual measurement files.** A pattern evaluates against `individual_measurements_file(...)` instead of its multisize table (`rebind_measurements`, `missing_measurements`, `check_measurements` in `yoko_engine.binding`).
- **Section references** for rotate, move and mirror: `<piece>.section(landmark_a, landmark_b)`, optionally `+ object` / `- object`, resolves to the outline objects between the two landmarks (inclusive, outline order). Piece by name, `#id` or short name (`C - Bodice Front` = `bodice_front`).
- **Union creation** is an action (`UnionPieces`, tool `union_pieces`). Seamly2D opens what we write and computes the same united outline (case `union`, CI regenerates and diffs). Elliptical-arc cutting stays `not_implemented`: Seamly2D itself hangs on it.

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
