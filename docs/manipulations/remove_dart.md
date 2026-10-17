# Remove a dart

Recipe name: `remove_dart`
Status: **draft, written by Claude from the tools. Not drafting practice.**
Everything below that is a drafting rule is marked **(?)**: it is a question for the pattern makers, not an answer. Please correct, delete or confirm each one. Parameter ranges are left empty on purpose.

## 1. Purpose and where it applies

Take a dart out of a piece and put the width it took somewhere else. One recipe, with an option `intake_to` for where the width goes (Kasi's decision; the list of choices is to be confirmed). Making fullness by gathering is a separate recipe, `gathers`. Applies to bodices, skirts, trousers.

## 2. Roles: where the step happens

The plan's step names each role in `refs` (a landmark or `piece.section(a, b)`). Landmark names are proposals from the landmark sheet and are not verified yet. Darts are named the same way everywhere: `<where>_dart<N>_leg_a`, `_leg_b`, `_apex`, `_cap`.

| Role | Kind | Required? | Used for |
| --- | --- | --- | --- |
| `dart_leg_a` | point | yes | one end of the dart on the edge, for example `skirt_back.waist_dart1_leg_a` |
| `dart_leg_b` | point | yes | the other end |
| `dart_apex` | point | yes | the tip of the dart, inside the piece **(?)** |
| `dart_cap` | point | no | the bump the dart leaves in the outline of the basic piece, if it has one (it goes when the dart goes) |
| `edge` | section | for `ease`, `seam` | the edge the width goes to **(?)** |
| `target_seam` | section | for `seam` | the seam that takes the width **(?)** |

## 3. Parameters and options

**Parameters.** An amount is a formula over measurements (it adapts across sizes), never scaled by `#CM`; it must hold at every size of the table.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `intake` | the width of the dart at the edge that is taken out. If the plan leaves it out, the dart's own width is used **(?)** | cm | | | |

**Options.** A choice from a list, named in the plan's `options`. It is not a second recipe.

| Name | Choices | Default | What each choice does |
| --- | --- | --- | --- |
| `intake_to` | `ease`, `gathers`, `seam` | **(?)** | `ease`: the width is shared along the edge as ease, no shape change; `gathers`: the edge keeps its length and is gathered, so the piece gets fuller (the gathering itself is the recipe `gathers`); `seam`: the width moves to `target_seam` (the dart is closed and the seam is opened by the same amount). The list of choices, and what each one means, is to be confirmed by the pattern makers. |

## 4. Preconditions

The dart tip lies inside the piece and both legs end on the outline.

## 5. Steps

| # | Option | Add or edit | Tool | References and formulas | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | all | edit | ``edit_point_at_distance_angle` / `edit_point_along_line`` | close the dart: move `dart_leg_b` onto `dart_leg_a`, or edit the formulas of the points that make the dart's cap so the cap is gone **(?)** | the dart is closed |
| 2 | `ease` | edit | ``edit_curve_spline`` | smooth the edge across the closed dart so the edge keeps its length **(?)** | the new edge |
| 3 | `gathers` | none here | | the edge keeps its length; the recipe `gathers` then does the gathering. Does this recipe do nothing more, or does it also mark the gathered section? **(?)** | |
| 4 | `seam` | add | ``rotate` / `move`` | open `target_seam` by `#s_intake` and carry the pieces beyond it (see `slash_and_spread`) **(?)** | the opened seam |

## 6. Landmarks it creates

None **(?)**. The removed dart's landmarks stop existing.

## 7. What must be re-trued

The edge the dart left (it must be smooth and the right length), the side seam length, anything measured across the old dart (waist length, the matching edge on the other piece). **(?)**

## 8. Completion check

The dart's legs coincide (or its landmarks are gone); the outline is closed and has no crossings; for `seam`, the target seam is `intake` longer than before, within 0.1 mm.

## 9. Measurements for the status card

| Parameter | How to measure it now |
| --- | --- |
| `intake` | the distance between `dart_leg_a` and `dart_leg_b` now (0 when the dart is closed), against the dart's width at the start |

## 10. Incompatible with

`add_or_move_dart` on the same dart (a removed dart cannot also be moved). **(?)**

## 11. Worked examples

None yet. I need two or three drafted in Seamly2D from the basic set (a skirt dart removed into ease, into gathers, into a seam), saved as copies of it, with the parameter values and the lengths to check.

## 12. Questions for the pattern makers

1. Is the list of choices right: `ease`, `gathers`, `seam`? Is there anything else (for example "into another dart")?
2. For `ease`: is the width spread along the whole edge, or between two named points?
3. For `gathers`: does `remove_dart` do anything beyond closing the dart, or is all of it left to `gathers`?
4. For `seam`: which seam takes the width by default, and how is the matching edge on the other piece kept the same length?
5. What happens to the cap (the bump in the outline of the basic piece) when the dart goes?
