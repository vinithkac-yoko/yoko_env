# 0016. The environment API and the teacher-data records

Status: accepted for now (Kasi, Phase 4 answers). The throughput number is a measurement, not a
promise: it was taken with the test example recipe.

**Environment** (`yoko_env`). `PatternEnv.reset(task, seed)` returns an `Observation`;
`step(action)` returns `StepResult(observation, reward, done, info)`; `state()`, `fork()`,
`replay()`. An action is a tool call (`Call`); `done` and `apply_step` are tools like the others.

- **Visible to the policy** (`Observation`): step count and steps left, `progress` (the active plan
  step), the status card (every step done / active / pending; for the active step each amount's target
  against what is measured now, the landmarks and pieces the plan names), a compact state, the last
  tool result, `valid_actions`. The plan is given at reset.
- **Privileged** (`info`, and the sidecar): `on_plan`, `op`, `expert` (the teacher's acceptable set)
  and, at `done`, the touched pieces and their problems. Tool results show nothing of provenance but
  the step number: `get_object`'s history no longer names the author, or teacher data would differ
  from model data.
- **Pieces** are computed only at `done`, and only the pieces the episode touched (new, following
  other objects, or following objects that moved).
- **No shaped reward.** `reward` is 0 unless an `EnvConfig.reward` hook says otherwise.
- **Valid actions** list the tools whose preconditions hold and the candidates once per kind
  (points, curves, objects), plus the objects each creating tool made (for its edit and delete tools).
  A candidate list per tool would make every record megabytes.
- **Limits**: max steps, max invalid actions (both end the episode with an outcome). The step budget
  rule of Addendum 1 section 13 (2 x the teacher's steps + 6) is the bench's to apply.

**Teacher data** (`yoko_data`). gzip JSONL, one gzip member per episode written in one go and
flushed, so a killed worker damages at most the last episode. Lines: `plan` (once), `step`, `end`.
Step records have exactly the keys of Addendum 1 section 12. `noise` is a per-step flag: the action
executed after that state was a random valid action (drawing, edit and delete tools only, tried on a
copy first). Only the teacher's label is stored, never the executed action. The episode draws its
noise rate from `[0, 0, 0.1, 0.2, 0.3]`. The seed fixes everything, so an episode replays exactly.
Seeds follow ADR 0009. Splits are by plan family (the recipes in order), hashed, never by row.

**Throughput** (`scripts/bench_env.py`, 4 cores here, basic set, example recipe): whole teacher
episodes with noise and records, 171 steps/s on 4 workers, 48 steps/s per worker, projected
about 390 on 8 cores; `step` alone with the teacher's labels about 310 projected; with the teacher
off about 137 projected, because an action nobody labelled is then recognised by geometry at three
sizes. The target is 100 on 8 cores. Not optimised. Where the time goes: applying an action (about 6
ms), the teacher's dry-runs, and, for unlabelled actions, evaluating the pattern at the other sizes.
The first thing to try when it matters is to keep the other-size sessions up to date by applying
each action to them too, instead of evaluating them from scratch.

**Found on the way:** random actions reached a division by zero in the circle-circle point
(concentric circles; Seamly2D's C++ answers "no common point") and the state hash was most of the
cost of a step (now made from per-object text kept while the object lives).
