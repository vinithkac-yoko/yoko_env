# yoko-env — Addendum 1 to the build spec

From Kasi, 8 October 2026. This addendum updates `docs/BUILD_SPEC.md`. **Where the two disagree, this addendum wins.** Commit this file as `docs/BUILD_SPEC_ADDENDUM_1.md`, fold its changes into `BUILD_SPEC.md` and the ADRs, then start Phase 0 scaffolding.

Why it exists:
- **Your Phase 0 report.** It showed what our real file looks like.
- **A study of biome-s1** ([github.com/shhivv/biome-s1](https://github.com/shhivv/biome-s1), MIT). It is a planner-then-executor system for CAD (FreeCAD) that solved several problems we will hit.
- **Seamly2D's own source**, checked today. It has two facts the spec missed: the file format changed recently, and how line types draw.

## 1. Answers to your Phase 0 questions

1. **Missing PDFs.** I've re-attached `JUNIOR_SWEAT_TEE_compressed.pdf` and `Bottom_spec.pdf`. They are examples only. If they're still missing, carry on with DC008.
2. **DC008.** It is an example only. Treat it as a two-garment tech pack and build nothing around it.
3. **Height 164 vs 166, `height_increase` = 0.** Honour the file exactly as Seamly2D does:
   - In Seamly2D, `height` is the standard measurement A01 and `size` is the standard measurement G12 (`src/libs/vpatterndb/measurements_def.cpp`). Both are separate from the table's base size and base height.
   - So `#CM` = 166/166 = 1 at every height, as written.
   - Log the 164/166 mismatch in a "file health" report and change no data. The oracle will confirm.
4. **`size` = 6.** Yes. It is measurement G12, a dress-size number (UK 6 at base, +2 per size step). Read it as is.
5. **Sizes for multi-size checks.** Use only the sizes the measurement file covers; its name says UK 6–14. Anything beyond that is extrapolation: report it, never fail on it. Sizes are only our test that a result is truly formula-based. They are not a product feature yet.
6. **Base set scope.** It's complete for now, and more base sets may come later, so the library must accept them. Shirt, T-shirt and jacket blocks will be derived from the bodice and sleeve and saved as library styles.
7. **Spreadsheet.** Import names only, flagged unverified. Ignore its units.
8. **Unreachable designs.** Yes: the planner explains what's missing and asks me. It never forces a design.
9. **Display.** See section 4.
10. **Units.** Yes, with one rule: evaluate every formula in the pattern's own unit, exactly as Seamly2D does, and convert only geometry.
11. **Round trip.** Use your default: a semantic comparison (attribute order and whitespace ignored), plus a byte-level check that you report but don't fail on.
12. **Branch.** Work on your session branch and keep one draft PR open. I merge into `main` at each checkpoint, and Railway deploys `main`, so `main` must always build. This replaces "push directly to main" in the spec.
13. **Railway.** I create the project and connect the repo. Name the service `web`; Railway's generated URL is fine. Tell me exactly which variables each phase needs (Phase 0: `STUDIO_TOKEN`).
14. **Python 3.12 via `uv`.** Yes.
15. **Package names.** Keep them.
16. **Formula language.** Yes. Port Seamly2D's grammar exactly, built-in functions included, with tests that cite its source files.
17. **Other measurement sets (e.g. kids).** Yes. Hard-code nothing adult-specific.
18. **Policies.** Claude plus replay first; the OpenAI-compatible policy in Phase 7.
19. **Checkpoint format.** Both: a written plan in `docs/PROGRESS.md` and a short chat summary.

## 2. What changes, in one list

| Area | Before | Now |
| --- | --- | --- |
| Main training-data source | Pattern makers' derivation diffs | A **scripted teacher** that labels any state, generating unlimited examples from recipes (§8, §12). Derivation diffs stay essential for realism, testing and the planner. |
| Manipulation tools | Composite macros | **Recipes**: a macro, a step-by-step operation graph, a completion check and a teacher (§8) |
| References to objects | Seamly2D labels (A12, B4) | **Standard landmark names** in a sidecar file (§5) |
| Numbers | Formulas inside tool calls | Planner's amounts become **named pattern variables** (§7) |
| Progress | Log groups tool calls by plan step | **Provenance** on every object, a **completion check** per step and a **status card** in every observation (§6, §9) |
| Tools offered | A fixed subset per run | Only **valid actions** for the current state (§10) |
| Environment API | reset/step/state | Also returns **teacher labels, progress and valid actions**; optional shaped reward (§11) |
| Synthetic tasks | A few scripted edits | **Plan sampler** with difficulty levels, held-out lengths and held-out pairings (§12) |
| Mistakes | Not covered | **Noise injection** in data generation and a perturbed test suite (§12, §13) |
| Success | Distance scores | **Exact match** at base and other sizes; clean success; outcome taxonomy (§13) |
| File format | "Latest Seamly2D" | Read 0.6.8 to 0.7.5, write back the version read, **pin one Seamly2D version** (§3) |
| Display | Draw everything | Every group on, one style, **no invented lines**, zoom to the step's pieces (§4) |
| Fixing mistakes | Undo | Undo, **delete** leftovers or **edit** a wrong object's inputs (§8) |
| Branch | Push to `main` | Session branch and draft PR; I merge (§1 Q12) |

Unchanged: the engine, full parity, lossless round trip, oracle, read-only base set, planner → approval → drafter, studio, versioned prompts and Railway.

## 3. Seamly2D versions and file formats

- Seamly2D publishes builds weekly. The latest tag today, `v2026.10.5.154`, writes pattern format **0.7.5**.
- Our basic set is format **0.6.8**, saved by v2023.12.4.

Formats in between changed:

| Format | What changed |
| --- | --- |
| 0.6.9 | `increments` renamed to `variables` |
| 0.7.1 | background `images` added |
| 0.7.4 | curve `autoSmooth` and `lengthMode` added |
| 0.7.5 | `finalMeasurements` added (landed 3 Oct 2026) |

The `byGroup` line style also exists. Newer Seamly2D opens older files; older Seamly2D can't open newer ones.

Rules:
- **Reading:** read every pattern format from 0.6.8 to 0.7.5, and the matching measurement formats.
- **Writing:** write back the same format version a file was read in, so the lossless round trip holds per version.
- **Upgrading:** provide an explicit upgrade from 0.6.8 to the pinned format. It must match what the pinned Seamly2D does when it opens and saves the file, verified with the oracle.
- **Pinning:** my pattern makers use the latest Seamly2D. Pin `v2026.10.5.154` (the latest today) for the oracle and for them. Because Seamly2D releases weekly, never follow "latest" automatically: move the pin deliberately, re-run the oracle suite, and record each move in an ADR.

## 4. Display rule (answers Q9)

- **Groups:** draw everything Seamly2D draws with every group switched on. Ignore group visibility.
- **Style:** draw it all in one style. Ignore colours, pen styles and weights.
- **`lineType="none"` means the tool draws no line at all.** Seamly2D maps it to `Qt::NoPen` (`src/libs/ifc/ifcdef.cpp`). It is not a hidden line, so draw the point and never invent a line. Drawing them would add up to 117 lines nobody drafted.
- **Zoom:** the studio canvas and every image sent to a model zoom to the pieces the current plan step touches. This is scoping, not hiding.
- **Queries:** "scaffolding vs piece outline" is available only as a query.

## 5. Landmarks: a standard naming layer (new)

**Purpose.** Plans, recipes, tools and observations refer to pattern-making names, not labels like A12. This is our version of biome-s1's semantic selections ("the largest face pointing up"), and it makes references a small, meaningful set.

**Storage.**
- One sidecar file per base pattern, for example `fixtures/patterns/base/<name>.landmarks.yaml`. The `.sm2d` stays untouched.
- It maps standard names to Seamly2D objects (points, lines, curves, pieces). It is versioned and hashed.

**Naming scheme.** Use `<piece>.<landmark>`, with common abbreviations and a glossary. Examples:
- `bodice_front.CF_neck`, `bodice_front.SNP` (side neck point), `bodice_front.shoulder_tip`, `bodice_front.BP` (bust point)
- `bodice_front.underarm`, `bodice_front.side_waist`, `bodice_front.armhole` (curve), `bodice_front.side_seam` (line or path)
- `sleeve.cap_top`, `skirt_front.hem_CF`, `trouser_front.crotch_point`

**Process.**
1. Propose the vocabulary and a best-guess mapping for every piece of the basic set, as a table with a confidence for each row.
2. My pattern makers verify and correct it. Never guess silently.
3. Commit the verified file.
4. Later, add a landmark-tagging screen to the studio.

**Rules.**
- Derived styles inherit landmarks.
- Each recipe names the new landmarks it creates.
- Tools accept a landmark name anywhere they accept a label.
- Validation: every landmark resolves to an object.

## 6. Provenance (new)

Every object created **or edited** through the environment records:
- plan step id
- recipe op id (if any)
- author (model, human, teacher or import)
- episode id
- **on-plan flag**: whether the teacher accepted the action that created it
- for edits of existing objects: the old and new formula or inputs

**Storage.** Keep provenance, the plan, the parent pattern's hash and the new objects' landmarks in a sidecar next to the Seamly2D file, for example `<style>.yoko.json`. The Seamly2D file stays lossless.

**Visibility.** The policy may see step ids and landmarks. The on-plan flag and the teacher's labels are **privileged**: they are used for training labels and scoring, and are never shown to the policy.

## 7. Plan amounts become pattern variables (new)

- The **planner decides every amount** from the design intent. The drafter never invents a number.
- Each amount becomes a variable in the derived pattern (an `increment` in 0.6.8, a `variable` in 0.6.9 and later):
  - name: `#s<step>_<param>`, for example `#s3_hem_flare`
  - description: the plan step's text
  - value: a constant in the pattern unit or a formula over measurements
- Recipes reference these variables, never literal numbers. My pattern makers can then change an amount in Seamly2D's variable table and the whole style updates.
- **Plan validation before approval:** every parameter a recipe needs is present, typed, in units, and within the recipe's allowed range.

## 8. Recipes and the teacher (new — the most important change)

Every named manipulation becomes a **recipe**, implemented from a procedure my pattern makers approve (`docs/manipulations/<name>.md`).

**What a recipe has:**
- **Basics:** name and version.
- **Parameters:** for each one, its unit, allowed range and default.
- **Inputs and preconditions:** the landmarks it requires and its preconditions.
- **Operation graph:** `expand(state, landmarks, params) -> RecipeGraph`, a DAG of primitive operations with stable op ids. Each op is a canonical tool call written with landmark names and the step's variables.
- **New landmarks:** the landmarks the recipe creates.
- **Completion check:** for example, "dart legs equal length, side seam re-trued, new piece closed".
- **Measurements:** how to measure each parameter on the current pattern, for the status card (§9).

**Ops can edit as well as add.** My pattern makers mostly make a style by **editing the formulas of the copied block's own points** (for example, changing the hem point's formula to lengthen), not only by adding new points. So a recipe op is either "add an object" or "edit an existing object's formula or inputs". Edits are normal design steps, not only mistake fixes. The basic set itself stays read-only: edits apply to the style's copy.

**Composite tool.** Applies the whole graph in dependency order. This is what the drafter usually calls.

**Teacher.** `expert(state, plan, provenance) -> list[Action] | None` returns the **set** of acceptable next actions, canonical first. It reads only the state, the plan and the provenance, so it can label **any** state, including states after mistakes. It works in this order:
1. **If leftovers from off-plan actions exist**, the acceptable set is recovery:
   - undo the last action;
   - delete a leftover that nothing depends on;
   - or **edit** a wrong object's inputs or formula to what the recipe requires. In Seamly2D an object other objects depend on can't simply be deleted; editing it is how pattern makers fix it.
2. **Otherwise, find the active step:** the first plan step whose completion check fails.
3. **For the active step, the acceptable set is:**
   - every op in its recipe graph whose inputs exist and which isn't done yet, in any order;
   - plus the composite call for the whole step, when composites are in the run's tool subset.
4. **When every step is complete:** `Done`.
5. **When no recipe covers the step:** return `None` ("no label"), and the step relies on human or Claude data (§12).

An op counts as **done** when an on-plan object matches it, or when any object reproduces its geometry exactly at the base size and at two other sizes. Equivalent constructions therefore count.

**Labelling each action.** When an action is applied, compare it with the teacher's set at that moment and record the on-plan flag.

**Tools.** Every primitive object type needs an **edit** and a **delete** tool, with dependency checks. Full Seamly2D parity already implies this; make it explicit.

**Recipe tests.** Run each recipe on the basic set with 3 parameter settings. Compare against my pattern makers' worked examples drafted in Seamly2D; they must match exactly.

**First recipes, for my pattern makers.** About 15 cover nearly all 60 styles in the example spreadsheet.

First 8, most used:
1. slash-and-spread (parallel, or hinged for flare)
2. lengthen or shorten at a line
3. add or remove width at a seam (progressive taper)
4. true (blend) a seam or curve
5. add a style line and split the piece (yoke, princess, panels, gores, tiers)
6. add, move (pivot) or remove a dart
7. re-fit the sleeve cap to the armhole
8. reshape the armhole and shoulder (drop, extend, deepen)

Next 7:

9. pleats
10. gathers
11. reshape a neckline
12. raglan and dolman (merge or re-cut sleeve and bodice)
13. raise or lower the waistline or rise
14. hem shaping and extensions (wrap, button stand, slits)
15. simple new pieces (waistband, cuff, godet, facing)

Later, grow to about 30 (collars, plackets, pockets and more).

Write `docs/manipulations/TEMPLATE.md` for my pattern makers. Each procedure must give:
- purpose and the blocks it applies to
- required landmarks
- parameters (meaning, unit, range, default)
- numbered steps, each as a Seamly2D tool with its references and formulas
- the landmarks it creates
- what must be re-trued
- the completion check
- incompatibilities with other recipes
- 2–3 worked examples drafted in Seamly2D from the basic set, saved as copies with the parent recorded

## 9. Completion checks and the status card (new)

- Each plan step has a completion check. A half-applied recipe does not count as done.
- Every observation includes a **status card**:
  - each step marked done, active or pending;
  - for the active step: each target amount against its current measured value (for example `hem_flare: target 6.0 cm, now 0.0 cm`), the landmarks involved and the pieces touched.
- The full construction graph (425 objects in the basic set) is available through read tools. It is not dumped into every observation.

## 10. Valid actions (new)

`valid_actions(state)` returns:
- the tools whose preconditions hold now;
- for each reference argument, the candidate landmarks or objects of the right type.

An LLM drafter gets only the valid tools within its run's tool subset at each step. Small models in `yoko-model` use the same lists as masks.

## 11. Environment API additions

- Every `reset` and `step` response also includes `valid_actions`, `progress` (the active step index) and the status card.
- **Privileged fields, never passed to the policy:** `expert` (the teacher's acceptable set, or `null` when no recipe covers the step) and `info.on_plan`. They are used for training labels, DAgger and metrics.
- **Optional shaped reward**, set in the reward spec:
  - +10 × the change in matched-piece overlap with the target;
  - −0.02 per step;
  - +5 on `Done` with an exact match;
  - −1 on `Done` otherwise, or on running out of steps.

  Rewarding the *change* in overlap means build-and-undo loops can't farm it.
- The OpenEnv adapter passes the extra fields in `info`.

## 12. Data generation (priorities change)

**Main volume: teacher episodes.**
- **Plan sampler:** samples plans from the recipe vocabulary, with parameter values from each recipe's allowed range and my pattern makers' compatibility rules.
- **Targets:** each target is built by running the teacher cleanly. Reject infeasible plans (validation errors, self-intersecting or open pieces).
- **Difficulty levels:**
  - in training: L1 = 1 step, L2 = 2 steps, L3 = 3–5 steps;
  - held out of training: L4 = 6–7 steps, L5 = 8–9, L6 = 10–12.
- **Held-out pairings:** pick 2–3 recipe pairs, document them in an ADR and exclude them from training by rule (`heldout_rule(plan)`).
- **"Already satisfied" suite:** steps whose target already holds, where the right move is to do nothing for that step.
- **Start states:** the basic set, a library style, or partway through a plan.
- **Noise:** each episode draws a noise rate from `[0, 0, 0.1, 0.2, 0.3]`. With that probability the executed action is a random valid action. Store only the teacher's label.
- **Record format:** gzip JSONL, one record per step: `{episode, plan_id, level, step, observation, valid_actions, acceptable, noise, progress}`. Write the plan once per episode.
  - Flush after every episode.
  - The loader keeps every complete line before a truncation.
  - Split by episode and by plan family.
- **Seeds:** use disjoint seed ranges for data generation, DAgger, test suites, RL and calibration, recorded in an ADR.

**Human data stays essential:**
- derivation diffs from my pattern makers' Seamly2D files: realism, testing, planner training, and the source of new recipes;
- my corrections in the studio;
- Claude teacher-mode runs for steps no recipe covers, reviewed by pattern makers.

A manipulation that keeps appearing without a recipe becomes the next recipe.

## 13. Evaluation changes

- **Success:** the drafter issued `Done`, there are no validation errors, and every target piece is matched **exactly** (node coordinates within 0.001 mm), at the base size and at two other sizes. Pair produced and target pieces by best outline overlap (Hungarian matching).
- **Clean success:** success, with no leftovers from off-plan actions. Construction objects a recipe calls for are fine.
- **Also report:**
  - zero-deviation success (no wrong decision at all)
  - steps relative to the teacher
  - agreement with the teacher on visited states
  - outcomes: `success`, `wrong_geometry`, `out_of_steps`, `unrecoverable`, `crashed`
  - the full action history of every failure
- **Step budget:** 2 × the teacher's step count + 6, doubled for perturbed runs.
- **Suites:**
  - iid L1–L3
  - held-out pairings
  - held-out lengths L4–L6
  - already-satisfied
  - perturbed (20% random actions) versions of each
- **Per-step accuracy alone never picks a model.** In biome-s1, every variant scored about 99.8% per step, yet ranged from 2% to 100% on longer plans.
- **Tolerances:** against real Seamly2D (the oracle), < 0.01 mm. Between our own runs, exact (≤ 0.001 mm), because everything is formula-based.

## 14. Robustness

- **Cap every numeric tool input:** counts (pleats, gores) ≤ 50; angles within ±360°; lengths ≤ 500 cm; formula length and nesting depth too. In biome-s1, a single unbounded count grew one run to 125 GB of memory.
- **Workers:** run under memory and time limits. A killed worker restarts and replays its episode deterministically.

## 15. Updated phases

| Phase | Additions |
| --- | --- |
| 0 | ADRs for §3–§7 and §12 (format and version pin, display, landmarks, provenance, variables, held-out rules, seed ranges) |
| 1 | Provenance fields in the engine; read formats 0.6.8–0.7.5; landmark sidecar loader |
| 2 | Writers per format version; 0.6.8 → pinned-version upgrade verified by the oracle |
| 3 | Landmark vocabulary and best-guess mapping for my pattern makers to verify; edit and delete tools for every object type |
| 4 | Recipe procedure template; plan schema with typed parameters that become variables |
| 5 | Recipes (graph, composite, completion check, measurements) and the teacher; golden tests from pattern makers' examples |
| 6 | Environment: valid actions, status card, teacher labels, progress, noise injection, perturbation |
| 7 | Planner writes variables; plan validation before approval |
| 8 | Plan sampler, held-out rules, teacher data at scale, record format; human sources as before |
| 9 | New metrics and suites (§13) |
| 10 | Studio: landmark-tagging screen and status-card view |
| 11 | Unchanged |

## 16. Reference code: biome-s1 (MIT)

Read [github.com/shhivv/biome-s1](https://github.com/shhivv/biome-s1) for patterns. Copy code only with attribution in a `NOTICE` file.

| File | What it shows |
| --- | --- |
| `freecad_s1/expert.py` | A teacher that is a function of state and returns acceptable sets |
| `freecad_s1/goals.py` | Curriculum sampler and held-out rules |
| `freecad_s1/datagen.py`, `freecad_s1/data.py` | Noise injection, record format, truncation-tolerant loading |
| `freecad_s1/rollout.py`, `freecad_s1/evaluate.py` | Closed-loop metrics and outcome taxonomy |
| `freecad_s1/runtime/worker.py`, `client.py` | JSON-lines worker protocol and lockstep vectorised env |
| `freecad_s1/ui/env.py`, `ui/launch.py` | Restart-and-replay after crashes; watchdog |
| `scripts/calibrate.py` | Temperature calibration of action probabilities |

Do not port anything FreeCAD-, GUI- or accessibility-specific.

## 17. Additions (agreed after this addendum was first drafted)

**Style = edited copy plus additions.** A derived style is a copy of its parent in which existing objects' formulas or inputs may be edited and new objects added. Derivation diffs, provenance, recipes, the teacher and metrics must all handle edits, not only additions. Every edit is checked for loops: an edit may not make an object depend on its own dependents.

**Human style files become labelled training data.** `yoko import <style> --parent <parent>` produces the diff: the objects added, the objects edited (old → new) and the objects deleted. Turn it into a trajectory with set-valued labels: at each step, every not-yet-applied change whose inputs already exist is an acceptable next action, so any valid order counts. Store it in the same record format as teacher data, with `source = derivation_diff`. This lets human files train the drafter even where no recipe exists.

**Plans must work at every size.** The plan sampler and plan validation check a plan at the base size **and every size in the measurement file**, not just the base. A plan whose construction fails at any size is rejected (for example, two lines that stop crossing, or a piece that self-intersects at size 14).

**Tool results report what moved.** Every tool result lists:
- the objects created, edited and deleted;
- every object whose position changed because of the action, as a count plus the top few by distance moved;
- the pieces whose outline changed;
- the length change of every seam on those pieces, flagging any matched-seam mismatch the action introduced.

A change to one formula can move hundreds of points, so the model must see the consequences.

**Seamly2D's own test patterns.** Seamly2D's repository has about 40 real pattern files in `src/test/CollectionTest/share` (develop branch): suits, shirts, trousers, skirts, a bra, a women's basic block, plus `all_tools_pattern/alltools_pattern.sm2d`, which uses every tool, and a `broken/` folder of bad measurement files. Use them as follows:
- **Parity:** `alltools_pattern.sm2d` (format 0.7.4) is the first parity fixture. Every tool in it must parse, evaluate and round-trip.
- **Robustness:** the broken files must fail with clear errors, never crash.
- **Coverage and oracle:** most files are old formats (0.2.x–0.4.0). Don't write readers for those. In CI, open and re-save each one with the pinned Seamly2D to upgrade it to the pinned format, commit the upgraded copies with their oracle outputs, and use them for round-trip, evaluation and speed tests.
- **Data:** they are not derived from our basic set, so they are not derivation diffs. Use them only for engine tests and "remove a block and rebuild it" practice tasks, never in the held-out benchmark.
- **Licence:** they belong to the Seamly2D project (GPL). Keep them in `fixtures/external/seamly2d/` with a note of where they came from.
