# 0007. Recipes and the teacher

Status: accepted (Addendum 1 §8, §9, §10, §17)

- A **recipe** has parameters (unit, range, default), required landmarks and preconditions, an operation graph `expand(state, landmarks, params) -> RecipeGraph`, the landmarks it creates, a completion check, and measurements for the status card. Ops either **add** an object or **edit** an existing object's formula or inputs. The base set stays read-only; edits apply to the style's copy.
- The **teacher** `expert(state, plan, provenance)` returns the set of acceptable next actions, or `None` when no recipe covers the step. Order: recovery from off-plan leftovers (undo, delete a leaf, or edit), else the active step's ops in any order plus the composite, else `Done`.
- An op is **done** when an on-plan object matches it, or any object reproduces its geometry exactly at the base size and two other sizes.
- Every primitive object type needs an edit and a delete tool with dependency checks. An edit may not make an object depend on its own dependents.
- Procedures come from the pattern makers (`docs/manipulations/<name>.md`, template in Phase 4). I never invent drafting rules.
