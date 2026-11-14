# Studio v0: manual drafting (plan for review, no code yet)

Kasi and the pattern makers draft recipe worked examples (later a few designs) in the browser. Every
click is one action in the model's own action space, recorded with its author (`source =
human_studio`). ADR 0017 explains why this comes before the recipes.

## Screens

1. **Sign in, People.** Email and password. Kasi (owner) adds pattern makers; no self sign-up.
2. **Work items.** A list of items with filters (recipe, maker, status). "New item": start from a
   block of the base set (read-only, so a working copy is made) or from a saved style; kind = *recipe
   example* (pick the recipe, or NEW: name; example 1, 2 or 3) or *design* (a brief and reference
   images); the measurements (the table at a size, or a person's file).
3. **Drafting** (the main screen):
   - *Canvas*: SVG, pan and zoom, every line visible, labels and landmark names. Click an object:
     its formulas, what it is built from, what is built from it. Size switcher: any size of the
     table, or a person's file.
   - *Tools*: a form for every tool in `config/tools/`, generated from its schema (no hand-built
     forms), the piece tools included (add_piece, set_piece, copy_piece_from, union_pieces).
     Reference fields: click the canvas or type a landmark name. Section fields: click two landmarks.
     Formula fields: autocomplete (measurements, variables, Line_A_B and the like) and the value at
     every size as you type. Preview before commit.
   - *Edit in place*: change an object's formulas or inputs in the inspector (the most common
     manipulation). Delete warns with the list of dependents.
   - *Curves*: handle angles and lengths as numbers with a live preview first; then draggable handles
     (below).
   - *Action log*: the actions grouped by step; undo, redo, branch from any action.
   - *Validation panel*: formula errors and open pieces at every size, updated after each action.
4. **Finish step** (a dialog, opened from the log): recipe (dropdown, or NEW: name); refs pre-filled
   from the landmarks the step's actions touched; amounts from the variables the step created; why;
   alternatives; checks; a by-eye tick; use for training: yes, no or unsure. Steps can be merged or
   split afterwards.
5. **Cross-check**: two makers' versions of the same recipe example side by side; the teacher's
   geometry match colours what agrees (same place at three sizes) and what does not.
6. **Import / export** (item menu): export `.sm2d`; import a `.sm2d` drafted in Seamly2D, with its
   parent, as a derivation diff.

## How it works underneath

- **Server.** The pattern lives on the server. An item is its starting pattern plus its action log
  (a tree: branches share their history). The working state is rebuilt by replaying the log and kept
  in memory while the item is open. Preview runs the call on a copy and records nothing. The engine,
  tools, teacher and records are the ones already built; the studio adds HTTP routes for them.
- **Storage.** Postgres: people, items, action log, steps and their labels, settings. A bucket (S3
  compatible): reference images, exports, record files. Records are exported by replaying the log, one
  line per action in the teacher-data format with its step label; the human's action is the label.
- **Dragged handles** are saved relative to the curve, so they scale to every size: a handle length
  as a fraction of the distance between the curve's end points (`k * Line_P1_P4`), its angle relative
  to a neighbouring line (`AngleLine_P1_X + d`). If no line joins the ends yet, the studio draws one: a
  construction line, visible like every other line.
- **Oracle.** Seamly2D is not on Railway. An exported file is checked by the oracle in GitHub Actions
  (or by an `oracle` service on Railway, if Kasi wants the check at once; see the questions).

## Build order and checkpoints

| Stage | What | Checkpoint on Railway |
| --- | --- | --- |
| A | Sign in and people; work items; server-side sessions; read-only canvas with size switcher and inspector | **First checkpoint**: Kasi and a maker each sign in, start an item from the skirt block, look at it at UK 6 and UK 14, click points to see formulas and dependents |
| B | Tool forms from the schemas, click and landmark picking, sections, formula autocomplete and live values, preview and commit, edit in place, delete warnings, undo and redo, validation panel, piece tools | Draft a few points, a line and a curve with numeric handles; edit a formula; undo; see an error appear at one size |
| C | Draggable curve handles saved relative to the curve | **Stop**: Kasi sees one dragged curve at UK 6 and UK 14 before anything else |
| D | Finish step, merge and split, branch from any action, record export | Finish a step of a recipe example; download its records |
| E | Export `.sm2d` (oracle check), import `.sm2d` as a derivation diff, cross-check view | Export an example and open it in Seamly2D; cross-check two makers' examples |

After E: the finishing plan (seam allowance with Seamly2D's corner types, notches, grainline, labels;
seam allowance widths as a settings table per order), sent before coding.

## Railway variables

For the first checkpoint (stage A):

| Variable | Service | Value |
| --- | --- | --- |
| (new service) | Postgres | Add Railway's Postgres to the project |
| `DATABASE_URL` | web | `${{Postgres.DATABASE_URL}}` (a reference to the Postgres service) |
| `SESSION_SECRET` | web | A long random string (`openssl rand -hex 32`); signs the login cookies |
| `STUDIO_TOKEN` | web | Already set. Used once to create the owner account; afterwards only to recover it |

From stage E (and for design items' reference images): an S3-compatible bucket, with `BUCKET_ENDPOINT`,
`BUCKET_NAME`, `BUCKET_REGION`, `BUCKET_ACCESS_KEY_ID`, `BUCKET_SECRET_ACCESS_KEY` on web. If Kasi
wants the oracle check at once: an `oracle` service and `ORACLE_URL` on web.
