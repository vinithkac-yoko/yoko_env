# yoko-env — Build Prompt for Claude Code

> **Status of this document.** Original brief, with Addendum 1 folded in on 2026-10-08. Where an edit comes from the addendum it is tagged **[A1 §n]**. The full addendum is `docs/BUILD_SPEC_ADDENDUM_1.md`; **where the two disagree, the addendum wins.** Additions that have no home in the original text (landmarks, provenance, plan variables, recipes and teacher, valid actions, evaluation, robustness, §17 additions) are not repeated here: read them in the addendum.

I am Kasi, founder of YokoStyles (Stylique AI Pvt. Ltd.). This file is your full brief. Save it in the repo as `docs/BUILD_SPEC.md`, then work through it phase by phase, stopping at each checkpoint for my review.

## 0. Attached files: read this first

I have attached these files to this message. The repo is empty; **you** add them to the repo in the folders below.

| Attached file | Put it in | Status |
| --- | --- | --- |
| Basic pattern set (Seamly2D pattern file, e.g. `.sm2d` / `.val`) | `fixtures/patterns/base/` | **Real project data.** Our starting pattern; the root of the pattern library. |
| Its measurement file (e.g. `.smms` / `.smis` / `.vst` / `.vit`) | `fixtures/measurements/` | **Real project data.** Came with the pattern; the default measurement set. |
| `named_transformations_input_output.xlsx` | `fixtures/examples/plans/` | **Example only.** Shows the *style* of a transformation plan. Its content is not correct. |
| `DC008-Cardigan.pdf` | `fixtures/examples/techpacks/` | **Example only.** A tech pack with a flat sketch page. |
| `JUNIOR_SWEAT_TEE_compressed.pdf` | `fixtures/examples/techpacks/` | **Example only.** A tech pack with flats and a size spec. |
| `Bottom_spec.pdf` | `fixtures/examples/techpacks/` | **Example only.** A points-of-measure spec page. |

**About the examples:** only the basic pattern set and its measurement file are real. The spreadsheet and the three tech packs are references to show you the *format* of plans and tech packs, and to test PDF reading. Do not treat their content as correct. They happen to be kidswear; our work is **adults only**. Do not build anything specific to these garments or to kidswear.

**Your first task:** inspect every attached file and report back what it contains: the Seamly2D version and file-format version of the pattern, its drafting blocks, pieces, points, curves, operations, variables and the measurements it uses; the measurement file's type, units and sizes; the structure of the spreadsheet; what each tech pack page shows. Then ask me your questions. Do not write engine code before I reply.

## 1. Mission

You are building `yoko-env`, a clean, production-quality **environment for AI agents that turn a design idea into a garment pattern** by manipulating a basic pattern in a parametric pattern engine. It is the foundation for YokoStyles, which turns text, images, flat sketches and tech packs into production-ready patterns for garment manufacturers.

This repo is **only the environment**: the pattern engine, the tools, a parallel environment server, the planner and drafter agent plumbing, data collection, benchmarks and the studio UI. Choosing, fine-tuning and serving models lives in a separate repo, `yoko-model`. This repo must expose clean interfaces for it: an OpenAI-compatible model endpoint setting, an environment HTTP API, and dataset exports.

### Core idea: every design is a manipulation of a basic pattern

Pattern makers never draft a whole garment from scratch. Every garment is made by taking a **basic pattern set** (blocks / slopers) and manipulating it: add or remove darts, move darts, add style and seam lines, split pieces, add flare or fullness, lengthen or shorten, reshape necklines and armholes, and so on.

So the work, for a pattern maker and for the agent, is:

1. **Choose a starting pattern.** Usually the basic pattern set; sometimes a previously made style that is close to the new design.
2. **Apply a sequence of manipulations** to reach the design's silhouette and fit. They may start a new piece, but never a whole new pattern.

Our basic pattern set has **a single origin point**; every other object is a function of measurements and variables. Everything in this repo follows from this: a pattern library with a family tree, manipulation tools, data that records which pattern each design started from, and tasks that begin from a library pattern plus a design brief.

There is **no garment focus**. Build every tool first, for any garment. The goal is to capture design intent correctly and perform the correct manipulation steps to reach the right silhouette and fit.

### Two-stage agent: planner, then drafter

1. **Planner LLM.** Talks with the user and asks many questions until fit and silhouette are pinned down: ease, length, shoulder, armhole, sleeve, darts, style lines, fullness, closures. It asks for a **reference image**, and preferably a **flat sketch** (front and back technical drawing), because a flat sketch defines every seam and design detail. It also accepts **tech pack PDFs**.
2. If no flat sketch is given, the planner **draws one** (front and back).
3. The planner **selects the starting pattern** from the library.
4. The planner writes a **transformation plan**: the ordered manipulations that turn the starting pattern into the design.
5. **Approval gate.** The studio shows me the flat sketch, the chosen starting pattern and the plan. I approve, edit, or reject with comments. Nothing is drafted until I approve.
6. **Drafter (the main model).** Receives the approved plan, the flat sketch, the starting pattern and any reference images, and executes the plan with engine tools.

I write and tune the planner's prompts myself; you build all the plumbing. The drafter never sees the raw chat, so each stage can be improved and trained separately.

## 2. Decisions already made

| Topic | Decision |
| --- | --- |
| Construction model | Seamly2D's (Aldrich method): objects are built by reference from earlier objects plus formulas over measurements and variables. A pattern is a program. |
| Engine | Rebuild clean, from scratch. Seamly2D's source is the spec. |
| Full parity | Everything a pattern maker can create or change in the Seamly2D UI (drafting blocks, points, lines, curves, arcs, cuts, intersections, operations, darts, variables, pieces) must be doable through the engine and its tools. Nothing the engine does may be impossible to open and edit in Seamly2D. |
| File format | Native JSON internally; import and export Seamly2D files (`.sm2d`, `.smis`, `.smms`, and legacy `.val`, `.vit`, `.vst`). **Lossless Seamly2D round trip is the top priority.** DXF/PDF export comes later. |
| Seamly2D version | **[A1 §3]** Pin `v2026.10.5.154` (writes pattern format 0.7.5). Read pattern formats 0.6.8 to 0.7.5; write back the format version read; explicit 0.6.8 to pinned upgrade verified by the oracle. Never follow "latest" automatically: move the pin deliberately, re-run the oracle suite, record it in an ADR. See `docs/adr/0002-seamly2d-version-and-file-formats.md`. |
| Scope | Ends at **finished pieces**. Seam allowance, notches, grainline, labels, grading and layout are out of scope for now; if a file contains them, keep them unchanged on round trip. |
| Split / merge | Only the way Seamly2D does it: new pieces built from sub-paths, and Seamly2D's union tool. No custom piece operations. |
| Units | **cm** everywhere in the UI and tools; mm internally. |
| Sizes | Not a product feature yet. Draft in the measurement file's base size. The engine must evaluate a pattern at every size the measurement file covers (UK 6 to 14 for the Aldrich file), because the scorers use it. **[A1 §1 Q5]** Sizes beyond the file are extrapolation: report, never fail on it. |
| Line display | **[A1 §4]** Draw everything Seamly2D draws, every group on, one style (colours, pen styles and weights ignored). `lineType="none"` means the tool draws **no line** (Seamly2D maps it to `Qt::NoPen`): draw the point, never invent a line. Zoom to the pieces the current plan step touches. "Scaffolding vs piece outline" is a query only. All of it is still stored and written back on round trip. See `docs/adr/0003-display-rule.md`. |
| Base patterns | Read-only. The basic set lives in a locked "base" area. Every derived style is saved as a new pattern in a separate "styles" area, with its parent recorded automatically. |
| Repo shape | One monorepo, `uv` workspace, several packages. |
| Action format | One canonical typed action (tool name + JSON args), with adapters to Anthropic tool calls, OpenAI tool calls and a compact text DSL. |
| Observations | Structured state and a rendered PNG, each switchable. |
| Environment standard | Gymnasium-style `reset / step / state`, served over HTTP, compatible with OpenEnv. |
| Prompts and tool descriptions | Versioned files in the repo, hashed; studio edits save new variants. |
| UI | React + Vite + TypeScript, served by the same FastAPI app. |
| Deploy | Railway: Docker, Postgres, S3-compatible bucket. |
| Licence | Not a concern. Read and port from Seamly2D's source freely. |
| Old prototype | `https://github.com/vinithkac-yoko/yoko_demo` is messy. Take almost nothing from it; you may skim its `README.md` and `DESIGN.md` for lessons. Its UI showed the wrong lines as hidden and visible, so ignore how it displayed anything. |

## 3. Non-negotiable principles

1. **The engine is the source of truth.** No model output touches geometry directly. Every change is a typed action, validated, applied, re-evaluated, and rolled back atomically if the result is invalid.
2. **Deterministic and replayable.** Same pattern + same measurements + same actions gives identical state and a stable state hash. Any trajectory can be replayed from its start.
3. **Everything is versioned and hashed:** patterns, measurement sets, prompts (planner and drafter), tool descriptions, tool schemas, plan schema, run configs and datasets. Every run stores the hashes of what produced it.
4. **Model-agnostic.** No model SDK is imported outside `packages/agent`. Claude, OpenAI-compatible servers (vLLM, SGLang, TGI) and a scripted replay policy all plug in behind one interface.
5. **Parallel by default.** Sessions are isolated, cheap to fork, and hold no global state.
6. **Parametric, not coordinates.** Tools create objects by reference (point, angle, length formula), never raw x/y, except origin points.
7. **Human data is first-class.** A pattern maker working in the studio or in Seamly2D produces the same trajectory format as a model.
8. **Small, typed, tested.** Python 3.12, full type hints, Pydantic v2 at boundaries, pure functions in the engine. No feature is done without tests.
9. **Errors the model can learn from.** Every failed action returns a structured error with a code, the offending field and a hint.
10. **Never invent drafting rules.** When Seamly2D behaviour or pattern-making practice is unclear, write the question down for me and my pattern makers.

## 4. Repo structure

Dependencies point one way only: `engine` ← `io` ← `tools` ← `env` ← `agent` / `data` / `bench` ← `server` ← `studio`. Enforce this with import-linter in CI.

```text
yoko-env/
  docs/
    BUILD_SPEC.md         this file
    ARCHITECTURE.md       kept current as you build
    PROGRESS.md           running log of what's done and what's next
    COVERAGE.md           Seamly2D parity matrix
    adr/                  one short decision record per major choice
    manipulations/        one drafting procedure per manipulation tool, checked by pattern makers
  packages/
    engine/   yoko_engine  construction graph, formulas, geometry, pieces, validation, library
    io/       yoko_io      Seamly2D import/export, SVG and PNG render (DXF/PDF later)
    tools/    yoko_tools   action schemas, dispatcher, error codes, format adapters
    env/      yoko_env     reset/step/state, observations, episodes, forking, reward hook
    agent/    yoko_agent   policies, drafter run loop, planner agent, flat sketch generator
    data/     yoko_data    trajectory store, importers, derivation diffs, augmentation, exports
    bench/    yoko_bench   tasks, scorers, reward specs, benchmark runner, reports
    server/   yoko_server  FastAPI: studio API, env HTTP API (OpenEnv-compatible), SSE, workers
  studio/                  React + Vite + TS frontend
  config/
    prompts/drafter/       drafter system prompt variants
    prompts/planner/       planner prompt variants
    tools/                 one YAML per tool
    plan/                  plan schema
    runs/                  run presets
  fixtures/
    patterns/base/         the basic pattern set (read-only)
    measurements/          its measurement file
    examples/plans/        example plan spreadsheet (format reference only)
    examples/techpacks/    example tech packs (format reference only)
    oracle/                reference outputs from real Seamly2D
  scripts/
  tests/
  docker/
  .github/workflows/
```

Provide one CLI, `yoko`, with subcommands: `serve`, `import`, `replay`, `run`, `plan`, `bench`, `gen`, `export`, `oracle`.

## 5. Engine (`yoko_engine`)

The engine is a **construction graph**: an ordered list of operations. Each operation names its inputs (earlier objects, formulas, measurements, variables) and produces objects. Evaluating the graph against a measurement set gives geometry.

### Core model

- **Pattern** = metadata + measurement binding + variables (Seamly2D "increments") + drafting blocks + ordered operations + pieces.
- **Origin points:** a pattern may hang entirely off one origin (as our basic set does) or have several drafting blocks each with its own origin. Support both.
- **Object ids:** stable, human-readable labels (`A`, `B4`, `Spl_A_B`) plus an internal UUID. Renaming never breaks references.
- **Formulas:** a safe expression language matching Seamly2D's: arithmetic, functions (`sqrt`, `sin`, `cos`, `tan`, `asin`, `min`, `max`, `abs`, `degTorad`, …), measurements, variables, and geometry references (line lengths, angles, curve lengths, etc.). Parse to an AST once; never use `eval`. Record every dependency edge.
- **Dependency graph:** support "what depends on X" and "what does X depend on"; the agent needs both to edit safely.
- **Incremental evaluation:** changing one formula re-evaluates only downstream objects. Target under 5 ms for one edit on a 500-object pattern.

### Parity and coverage

Build `docs/COVERAGE.md`: every Seamly2D UI action in the latest release, with its engine operation and tool name. Phase 3 is not done until every in-scope row is green. Cover, in order:

1. All point tools (origin, distance and angle, along line, perpendicular, bisector, midpoint, intersections of lines and axes, height, triangle, point from X and Y of two points, shoulder point, and any others in the current release).
2. Lines; arcs (radius, length); elliptical arcs; simple curves; spline paths; cubic Bézier and Bézier paths, with control points and handles.
3. Cut arc, cut curve, cut curve path; intersections of arcs, circles, curves and axes; tangent points.
4. Operations: move, rotate, mirror by line and by axis; groups; true darts.
5. Pieces: from a closed path of objects, plus internal paths; union.

### Pattern library

- Every pattern has a **parent link** (basic set → style → variant). Deriving a style = copy the parent, then append manipulations. Show and query this family tree.
- Each pattern has a description, garment type and style tags so the planner can find a similar starting pattern. Start with tag and text search; leave an interface for embedding search later.
- Copy a single piece (with the objects it depends on) from one pattern into another.
- Base patterns are read-only; the engine refuses writes to them.

### Validation (after every mutation)

Formula errors, circular references, missing references, zero-length lines, self-intersecting piece outlines, non-closed piece paths, seam length mismatches between matched edges, NaN geometry. Each returns a typed error.

### Mutation API

`PatternSession` with `apply(action) -> Result`, `undo()`, `fork()` (copy-on-write; under 1 ms for 500 objects), `snapshot()`, `state_hash()`, `diff(other)`. Apply is all-or-nothing.

### Round trip and oracle

- **Lossless round trip is the acceptance test:** Seamly2D file → engine → Seamly2D file preserves every object, formula, label, colour, line type, layer, visibility flag and piece setting. It runs on every pattern fixture.
- **Oracle:** a Docker image that builds real Seamly2D from source and exports piece geometry headlessly. `yoko oracle compare <file>` reports maximum point deviation between our engine and Seamly2D; target under 0.01 mm. You run on the web and may not have Docker, so build and run the oracle in GitHub Actions (nightly and on demand), commit its reference outputs to `fixtures/oracle/`, and have normal tests compare against those stored outputs.
- **Property tests (Hypothesis):** random valid construction sequences never crash; replay equals original; export → import round-trips.

## 6. Tools (`yoko_tools`, `config/tools/`)

### Kinds of tools

- **Primitive tools** map 1:1 to engine operations and cover the full parity matrix.
- **Read tools** never mutate: `get_state(scope)`, `get_object(id)`, `find_objects(query)`, `dependents(id)`, `dependencies(id)`, `measure(a, b)`, `list_measurements()`, `render(scope)`.
- **Library tools:** `search_library(brief)`, `load_pattern(id)`, `copy_piece_from(pattern, piece)`.
- **Manipulation tools** **[A1 §8: now recipes, each with parameters, an operation graph, a completion check and a teacher; ops may edit existing objects as well as add]** are composites that expand into ordinary Seamly2D operations, so the result is always a plain Seamly2D file and training data stays primitive-level. Start with: move / pivot a dart; split a dart; close a dart and transfer it into a seam, ease or gathers; add or remove a dart; add a style or seam line (princess, yoke, panel) and split the piece along it; add flare or fullness by slash-and-spread; lengthen or shorten; reshape a neckline or armhole; mirror or join pieces. Add more as the planner's plans require.
- **Procedures come from pattern makers.** For each manipulation, write the step-by-step drafting procedure and expected result in `docs/manipulations/<name>.md` and have me check it before you implement it.
- The agent can always fall back to primitives.
- **Tool subsets** are chosen per run config; this is an experiment knob.
- Every call returns `{ok, created, changed, deleted, warnings, error?: {code, field, message, hint}}` plus a compact state diff.

### One YAML file per tool

```yaml
name: point_at_distance_angle
version: 1
tier: primitive
description: |
  Create a new point at a given distance and angle from an existing point.
  Use for ... Do not use when ...
parameters:          # JSON Schema; the Pydantic model is generated from this
  base_point: {type: string, description: "Label of an existing point, e.g. A"}
  length: {type: string, description: "Formula in cm, e.g. #waist_arc_f/2 + 1"}
  angle:  {type: string, description: "Degrees, 0 = right, 90 = up"}
  label:  {type: string}
examples:
  - instruction: "Mark a point 1.5 cm below B"
    call: {base_point: B, length: "1.5", angle: "270", label: B1}
```

A loader validates each file, builds the model and hashes it. **Adapters** render tools as Anthropic tools, OpenAI functions and a compact text DSL, and parse each back to the canonical action, with round-trip tests.

### Prompts

- Drafter prompts: `config/prompts/drafter/<variant>.md`, with front matter and template slots (`{{tool_summary}}`, `{{pattern_summary}}`, `{{plan}}`, …).
- A **bundle** = drafter prompt + tool descriptions + tool subset (and, for full runs, the planner prompt set). Bundles are hashed and stored with every run.
- The studio edits prompts and descriptions; saving creates a new variant (or a draft I can promote to a file). Never change a variant a past run used.
- Write the first drafter prompt and all tool descriptions yourself, marked `v1`. I will iterate on them.

## 7. Planner agent, flat sketch and plan (`yoko_agent`)

- **`PlannerAgent`:** a chat loop with its own policy (any model) and tools: `ask_user`, `request_upload`, `read_techpack`, `generate_flat_sketch`, `search_library`, `select_starting_pattern`, `submit_plan`.
- **Planner prompts** are separate, versioned files in `config/prompts/planner/`: `system.md`, `questions.md` (fit and silhouette checklist), `flat_sketch.md`, `select_pattern.md`, `plan.md`. **I will write and keep tweaking these**, so make them easy to edit in the studio's Tuning screen, with version history and diffs, exactly like the drafter's. Ship simple placeholder `v1` versions so the pipeline runs end to end.
- **Inputs:** text, reference images, flat sketches, tech pack PDFs. For PDFs, extract text and tables (points of measure, size charts) and render each page to an image; pass both to the model.
- **Flat sketch generation** behind one interface, `FlatSketchGenerator`. v1: the LLM draws front and back flats as clean SVG line drawings showing everything a real flat shows: outline, seams, darts, style lines, topstitching, pockets, buttons and closures, trims and design details. Leave a slot for an image-generation model later. The user can replace a generated sketch with an uploaded one.
- **Plan format:** `config/plan/schema.json`, versioned. The example spreadsheet shows the idea (each row: "basic block → style" and a description of the manipulations), but make the plan structured: `design_summary`, `starting_pattern`, `target_silhouette`, `fit_notes`, and ordered `steps[]`, each with a named transformation, the pieces affected, key amounts (units or formulas), the dependencies to re-true (e.g. "sleeve cap must still match the new armhole"), and a check to run after the step. You may import the spreadsheet as a seed list of transformation names, flagged as unverified examples.
- **Approval and revision:** the studio shows the flat sketch (front/back), the starting pattern and the plan as an editable list, with approve / edit / reject-with-comments. A rejected plan goes back to the planner in the same conversation with my comments; it revises and resubmits. Keep every version of the plan with my comments.
- The drafter receives the approved plan, flat sketch, starting pattern and reference images, and the log records which plan step each tool call belongs to.

## 8. Environment API and parallelism (`yoko_env`, `yoko_server`)

### Python API

```python
env = PatternEnv(config)  # observation mode, tool subset, limits
obs = env.reset(task=task, seed=42)  # task = starting pattern + measurements + plan or brief
result = env.step(action)  # -> StepResult(observation, reward, done, info)
state = env.state()
child = env.fork()  # for tree search / grouped sampling
```

- **Observation:** the plan or instruction, compact structured state (scoped to relevant pieces or whole pattern), last tool result, optional PNG render (all lines drawn equally, points labelled), step count. Also a text-only "state card" for small models.
- **Reward hook** calls `yoko_bench` scorers; dense and sparse modes.
- **Limits:** max steps, max invalid actions, wall-clock timeout.

### HTTP API

Follow the OpenEnv convention (`POST /reset`, `POST /step`, `GET /state`, typed Action / Observation models) so RL trainers can connect without glue code. Check the current OpenEnv spec at build time. Keep our richer API under `/api/env/*`.

### Parallelism

- Sessions live in a worker pool (one process per core); the server routes by session id.
- Batch endpoints: `POST /api/env/batch_step`, `POST /api/env/fork?n=8`.
- Target 1,000+ steps per second per 8-core machine with rendering off; add a benchmark script.
- Stateless containers; session snapshots in Postgres or the bucket so a crashed worker can restore.
- Rendering in a separate pool, only when asked, cached by state hash.
- Consider Rust or `numba` only after profiling; record it in an ADR.

## 9. Drafter runner and model adapters (`yoko_agent`)

- **Policy interface:** `Policy.act(observation, history) -> actions + reasoning + usage`. Implementations:
  - `ClaudePolicy`: Anthropic SDK, native tool use, thinking captured, prompt caching, configurable model / effort / max tokens. Check current model names and SDK parameters in Anthropic's docs at build time; don't hard-code from memory.
  - `OpenAICompatiblePolicy`: any OpenAI-compatible endpoint. This is how the fine-tuned model from `yoko-model` plugs in. Native tool calls and the text-DSL fallback.
  - `ReplayPolicy`: replays a recorded trajectory.
  - `HumanPolicy`: actions from the studio's manual mode.
- **Run loop** streams every event (thinking, tool call, result, render, message) over SSE and writes it to the trajectory store as it happens. Stops on done, step limit, token or cost budget.
- **Self-correction:** failed actions return structured errors to the model; retries are counted.
- **Cost and latency** per step and per run, in INR and USD.
- **Teacher mode:** run N samples per task with any policy and keep all of them, scored.

## 10. Data (`yoko_data`)

### Trajectory record (one per episode)

| Field | Contents |
| --- | --- |
| ids | episode id, parent episode, task id, tags |
| planner | conversation, uploaded images and PDFs, flat sketch (uploaded or generated), chosen starting pattern, every plan version with my comments, the approved plan |
| start | starting pattern snapshot hash, measurement set, approved plan |
| config | policies, models, prompt bundle hashes, tool subset, observation mode, sampling params |
| steps[] | observation hash, reasoning, action, tool result, state hash after, plan step, latency, tokens |
| end | final state hash, scorer outputs, reward, done reason, cost |
| human | rating, critique, corrected action list, reviewer, timestamp |
| source | `model`, `human_studio`, `seamly_import`, `derivation_diff`, `reverse_engineered`, `augmented`, `synthetic` |

Metadata in Postgres (SQLite locally); snapshots, images and PDFs in the bucket, keyed by hash. Exports: JSONL and Parquet, Hugging Face `datasets`-loadable, per format adapter, with separate planner and drafter datasets.

### Sources

1. **Studio runs:** every run is recorded, rated and optionally corrected.
2. **Expert drafting in the studio:** pattern makers use manual mode; each click is an action. Gold trajectories.
3. **Derivation diffs (essential, no longer the main volume: **[A1 §2, §12, §17]** the main volume is the scripted teacher).** Pattern makers draft in Seamly2D, always starting from an existing pattern. `yoko import <style_file> --parent <parent_file>` finds the operations added or changed after the parent's; that sequence is the manipulation trajectory for the design. A hindsight instruction or plan is then generated and checked by a pattern maker. We start with zero style files, so this must work from the very first one.
4. **Reverse engineering:** replay any Seamly2D file as a trajectory; group operations into meaningful blocks; deletion tasks (remove a block and rebuild it); edit tasks (change a formula and ask for the edit).
5. **Augmentation:** replay trajectories at other sizes in the measurement file to check they are truly parametric.
6. **Synthetic tasks:** scripted edit tasks with known answers.

Leave an interface stub (`importers/dxf_outline.py`) for outline-only DXF files from factory CAD; no implementation.

### Dataset management

Named, immutable dataset versions built from recipe files in git. Splits by pattern family, never by row. A locked held-out benchmark split that is never exported for training. Dedup and leakage checks.

## 11. Benchmark, scorers, rewards (`yoko_bench`)

One set of scorers serves benchmark reports, RL rewards and data filtering. Prefer engine-checked scores over model judges.

**Task kinds:**
- **full:** a scripted user conversation (and optional images / flat sketch) → planner → drafter.
- **plan:** brief + flat sketch → planner output, scored against a reference plan and by my review.
- **select:** brief + library → choose the starting pattern.
- **derive:** starting pattern + approved plan → drafter output.

| Scorer | What it checks |
| --- | --- |
| validity | Final state evaluates with no validation errors |
| geometry match | Chamfer / Hausdorff distance to reference pieces and key points, in mm |
| multi-size robustness | Re-evaluate at other sizes in the measurement file and compare with the reference; hard-coded numbers fail |
| constraint satisfaction | Each named constraint within tolerance |
| seam integrity | Matched seams equal in length within tolerance |
| structural similarity | Construction-graph edit distance to the reference |
| plan adherence | Each plan step was carried out, in order |
| efficiency | Steps, invalid actions, tokens, cost, latency |
| human rating | When present |

A versioned YAML **reward spec** combines scorers; default: validity as a gate, geometry at several sizes as the main term.

`yoko bench --suite <name> --bundle <hash> --policy <policy> --samples 4 --parallel 64` runs a suite and writes a report (pass rate, pass@k, per-skill breakdown, cost, diff against a baseline). `yoko bench compare runA runB` shows deltas with bootstrap confidence intervals and the tasks that flipped. Suites: `smoke` (runs in CI with the replay policy), `core-v1` (built with my pattern makers from the basic set, covering every manipulation tool), `heldout` (never exported).

## 12. Studio UI (`studio/`)

Single user (me), desktop-first, fast. React + Vite + TypeScript + Tailwind. SVG pattern canvas (switch to canvas/WebGL only if profiling needs it). **All lines drawn the same way and always visible. All values in cm.** Auth: one token from an environment variable.

1. **Design (planner).** Chat with the planner; upload images, flat sketches and tech pack PDFs; see the generated flat sketch; approval screen with flat sketch, starting pattern preview and editable plan; approve, edit or reject with comments; "approve and draft".
2. **Workspace (drafter).** Pattern canvas (pan, zoom, labels, click an object to see its formula and dependents), live action log over SSE grouped by plan step, per-step thinking, before/after, undo, branch from any step.
3. **Manual drafting.** Every engine tool as buttons and forms, so a pattern maker can draft by hand and create a human trajectory; "why" per step.
4. **Tuning.** Edit planner prompts, drafter prompts and tool descriptions side by side, with version history and diffs; choose tools, models, limits and observation mode; save as a bundle.
5. **Runs and compare.** Filterable run table; compare two or more runs: flat sketches, plans, renders, action logs, config diff, scores.
6. **Review queue.** Rate runs, critique, correct the action list and replay to confirm, mark as gold. Keyboard shortcuts.
7. **Datasets.** Build from a recipe, preview, counts by source and skill, export.
8. **Benchmarks.** Launch a suite, watch progress, read and compare reports.
9. **Library.** Family tree of patterns (locked base set → derived styles), measurement sets, drag-in Seamly2D imports.

## 13. Deploy and workflow

- You run as Claude Code on the web, connected to my GitHub repo. **[A1 §1 Q12] Work on the session branch and keep one draft PR open. I merge into `main` at each checkpoint.** Railway deploys `main`, so `main` must always build.
- Before every push: lint, type-check and tests must pass. Never push a broken build (`main` always builds). Keep commits small. Put risky changes behind a flag until they work.
- From Phase 0, the deployed app must show something useful: a health page, the build sha, and whatever the studio can do so far.
- One Dockerfile for the app (FastAPI + built studio + engine); Railway uses it (no Nixpacks). A separate Dockerfile for the Seamly2D oracle, used only in GitHub Actions.
- Railway Postgres; an S3-compatible bucket (configurable provider) for snapshots, images, PDFs and exports.
- Separate Railway services for `web` and `env-workers` when load requires it.
- Secrets only from environment variables: `ANTHROPIC_API_KEY`, `OPENAI_COMPAT_BASE_URL`, `OPENAI_COMPAT_API_KEY`, `DATABASE_URL`, `BUCKET_*`, `STUDIO_TOKEN`. **I set them in Railway myself; tell me exactly which ones each phase needs.**
- `GET /api/health` and `GET /api/build` (git sha, bundle versions).

### Quality bar

- `ruff`; `pyright` strict on `engine`, `tools` and `env`; `pytest` with coverage ≥ 90% on `engine` and `tools`, ≥ 75% elsewhere; Hypothesis property tests; `vitest` and a Playwright smoke test for the studio.
- GitHub Actions: lint, type-check, tests, import-linter, `smoke` benchmark, Docker build. Nightly: oracle comparison and throughput benchmark.
- Every package has a README with a runnable example. Keep `ARCHITECTURE.md`, `PROGRESS.md` and ADRs current.

## 14. Phases

Stop at each checkpoint, tell me what to try on the live app, and wait for my go-ahead.

| Phase | Deliverable | Checkpoint |
| --- | --- | --- |
| 0 | Report on the attached files; your questions; repo scaffold, CI, ADRs (incl. **[A1]** format and version pin, display, landmarks, provenance, plan variables, held-out rules, seed ranges), coverage matrix draft, fixtures committed; minimal app live on Railway | I approve the structure and answer your questions |
| 1 | Engine core: formulas, points, lines, arcs, curves, evaluation, validation, fork / undo / hash; **[A1]** provenance fields, read formats 0.6.8 to 0.7.5, landmark sidecar loader | The basic pattern set evaluates and renders with all lines visible |
| 2 | IO: lossless Seamly2D import/export, SVG/PNG render, oracle in GitHub Actions; **[A1]** writers per format version, 0.6.8 to pinned upgrade verified by the oracle | Basic set round-trips losslessly; oracle deviation < 0.01 mm |
| 3 | All remaining primitive tools, pieces, union; pattern library with locked base area and family tree; **[A1]** landmark vocabulary and best-guess mapping for pattern makers to verify; edit and delete tools for every object type | Coverage matrix complete |
| 4 | Tool layer: YAML tools, adapters, v1 descriptions, structured errors; manipulation procedures written for my review; **[A1]** recipe procedure template, plan schema with typed parameters that become variables | Adapter round-trip tests pass; I review the procedures |
| 5 | Manipulation tools implemented from approved procedures; **[A1]** recipes (graph, composite, completion check, measurements) and the teacher; golden tests from pattern makers' examples | Each manipulation works on the basic set |
| 6 | Environment, parallel server, OpenEnv adapter; **[A1]** valid actions, status card, teacher labels, progress, noise injection, perturbation | Throughput benchmark ≥ 1,000 steps/s on 8 cores |
| 7 | Drafter runner and policies; planner agent, flat sketch generator, plan schema, approval and revision loop; **[A1]** planner writes variables, plan validation before approval | I describe a design, approve a plan, and Claude drafts it from the basic set end to end |
| 8 | Data: trajectory store, derivation-diff and Seamly2D importers, reverse engineering, augmentation, dataset recipes, exports; **[A1]** plan sampler, held-out rules, teacher data at scale, record format | A planner dataset and a drafter dataset export |
| 9 | Bench: task kinds, scorers, reward specs, runner, compare; **[A1 §13]** exact-match success, clean success, outcome taxonomy, iid / held-out / already-satisfied / perturbed suites | `smoke` and seed `core-v1` reports |
| 10 | Studio: all screens complete and polished; **[A1]** landmark-tagging screen, status-card view | I draft a piece by hand, run the full pipeline and review it in the UI |
| 11 | Hardening, docs, production config | Stable on Railway with persistent data |

### Working rules

- Start with Phase 0. Inspect the attached files and ask me your questions before writing engine code.
- Plan each phase in writing before coding; update `docs/PROGRESS.md` as you go.
- Commit small, with clear messages, straight to `main`, checks passing.
- When Seamly2D behaviour or pattern-making practice is unclear, ask me; don't invent drafting rules.
- Don't add features outside this spec without asking. Do tell me if the spec is wrong.
