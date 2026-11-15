# 0017. Manual drafting in the studio comes before the recipes

Status: accepted (Kasi, answers to the Phase 4+ questions, 2026-11)

**Change of order.** The studio's Manual drafting screen (BUILD_SPEC section 12, item 3) moves from
Phase 10 to now, before the recipes (Phase 5). The planned Seamly2D capture tool is dropped.

**Why.** Recipes are the unit of work: for each recipe, a procedure in words (written by Kasi) and
three worked examples drafted by Kasi and the pattern makers. Drafted in the studio, every click is a
recorded action in the model's own action space (`source = human_studio`), with its author, so the
examples are training data, golden tests and a cross-check between makers at once. Designs come later
and stay few. Seamly2D stays the oracle and the import/export format; anything drafted in Seamly2D
meanwhile comes in as a derivation diff.

**What changes in the spec.**
- Section 12 "single user" becomes: Kasi plus pattern makers, each with a login; every action records
  its author.
- The studio v0 scope is in `docs/studio-v0-plan.md`. Not in v0: layouts, planner chat, tuning.
- Recipes (Phase 5) start when Kasi's procedures arrive (one Markdown file per recipe, merged into
  `docs/manipulations/` in the template's format; what Kasi writes is the drafting rule, anything
  Claude Code adds is listed as unconfirmed).
- **Finishing** (seam allowance outlines with Seamly2D's corner types, notches, grainline, labels) is
  part of the product, because the DXF needs cut lines. Today they are only kept unchanged on a round
  trip (COVERAGE.md). It is planned after studio v0, checked by the oracle and exposed as tools; the
  plan goes to Kasi before coding. Seam allowance widths vary by order and seam type: they are
  settings (a table per order), never hard-coded.

**Other answers recorded with this change** (they are already in the code):
- A step's own check is measured once, when the step completes, and stored; the invariants (no formula
  error at any size, touched pieces closed, seam pairs match) are re-checked at `done`.
- A person's own file is checked with two nudged copies, graded like the pattern's table (half a size
  step: bust, waist and hip 2 cm, everything else in proportion; height 3 cm), in plan validation and
  in the teacher's geometry matching.
- Plan family = the sorted multiset of recipes with their option values; order and amounts do not
  count. Human-drafted items are split whole, never by step; some are held out for test only.
- `done` while the plan is incomplete is allowed and recorded (`plan_complete: false`); the teacher
  never labels it; evals count it as a failure.
- `apply_step` is off by default (executor training and data generation learn the primitives); named
  runs turn it on (an ablation, the product's fast path).

**Decisions on the plan (2026-11-15)** are listed in `docs/studio-v0-plan.md` ("Decisions"): logins
made by the owner; the oracle in GitHub Actions only; the helper line for dragged handles recorded as
a studio action in a hidden Seamly2D group; step amounts that follow the size written as formulas over
measurements; the blind cross-check; invariants at done at the teacher's three sizes for data
generation and at every size elsewhere.
