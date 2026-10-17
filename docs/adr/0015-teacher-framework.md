# 0015. The recipe framework and the teacher

Status: accepted for the framework (Kasi, Phase 4 answers); recipes themselves wait for the pattern makers.

The framework is recipe-agnostic (`yoko_tools.recipes`, `yoko_tools.teacher`). `lengthen_or_shorten`
exists only as a **test example** in `tests/test_teacher.py`. Nothing in `packages/` knows a
drafting rule.

**A recipe** supplies a spec (parameters, roles, options, landmarks it creates), `expand(ctx)` (a
graph of ops with stable ids), `check(ctx)` and `measure(ctx)`. An op is a tool call, either `add`
or `edit`; its arguments may name an earlier op's result as `@op_id`. The label of an added point
defaults to `s<step>_<op>`.

**Decisions** (each one is a design choice of mine, listed so it can be overruled):

1. **An op is done by provenance first.** An on-plan action records `(step, op)` in provenance. Only
   an op with no provenance is checked by geometry: it is applied to a fork, and if an existing object
   is already in the same place (within 0.001 mm) at the base size and at two other sizes of the
   table, the op counts as done. A person's own measurement file has no other sizes: the base size
   decides.
2. **Edits read the old formula from provenance.** An edit that builds on a formula
   (`old + #s1_amount`) would be applied again each time the step is expanded. `ctx.original()`
   returns the value the step found before it edited anything. Recipes do not read current formulas.
3. **Once a later step has begun, an earlier step's own check is not asked again**, because a later
   step may legitimately move what the earlier check measures. Its ops being done is what counts.
4. **Recovery comes first.** A leftover is an object an off-plan action made, or a field an off-plan
   edit changed and no later on-plan action changed again. Recovery is: undo (only if the last action
   was off-plan), delete a leftover nothing depends on, edit a field back, or the recipe's own edit
   for that object. Every recovery call is tried on a fork first.
5. **An action is labelled** by comparing it with the acceptable set: the same canonical call
   (names as ids, spaces and labels ignored) is on plan; so is an action whose result is in the same
   place as an op's at every size. That includes a different tool or a different formula.
6. **The composite** is the call `apply_step(step=n)`: all not-yet-done ops of the active step in
   dependency order. It is in the acceptable set only when the run's tool subset has composites.
7. **No label** (None) when the active step has no recipe, or when the plan's variables are not in
   the pattern. An empty list means the teacher knows the state but nothing can be done (a check that
   cannot be satisfied, a leftover with no recovery): a recipe bug or an unrecoverable state, and the
   status card says so.

**Limits, stated so nobody is surprised:** an edit op is judged by the edited object's place, not by
everything it moved; geometry matching is not asked of curves with different sample counts; the
step-start pattern is not rebuilt (a recipe that picks objects by their current position should pick
them by landmarks instead); variables set by the plan are not tracked in provenance.
