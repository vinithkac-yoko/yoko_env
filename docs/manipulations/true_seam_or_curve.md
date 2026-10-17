# True (blend) a seam or curve

Recipe name: `true_seam_or_curve`
Status: **draft, written by Claude from the tools. Not drafting practice.**
Everything below that is a drafting rule is marked **(?)**: it is a question for the pattern makers, not an answer. Please correct, delete or confirm each one. Parameter ranges are left empty on purpose.

## 1. Purpose and where it applies

After a change, make seams meet smoothly and, where two pieces are sewn together, make the sewn edges the same length. Applies to side seams, shoulder seams, armholes, necklines, hems.

## 2. Roles: where the step happens

The plan's step names each role in `refs` (a landmark or `piece.section(a, b)`). Landmark names are proposals from the landmark sheet and are not verified yet.

| Role | Kind | Required? | Used for |
| --- | --- | --- | --- |
| `edge_a` | section | yes | the edge that stays **(?)** |
| `edge_b` | section | yes | the edge that is changed to match it **(?)** |

## 3. Parameters and options

**Parameters.** Each becomes a variable `#s<step>_<name>` that the steps use. An amount is a formula over measurements (it adapts across sizes), never scaled by `#CM`; it must hold at every size of the table.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `tolerance` | how close the two lengths must be | mm | | | |

**Options.** A choice from a list, named in the plan's `options`. The recipe branches on it.

| Name | Choices | Default | What each choice does |
| --- | --- | --- | --- |
| `method` | `length`, `smooth`, `both` | **(?)** | `length`: the two edges get the same length; `smooth`: no corner at the join; `both`. Which of these 'true' means is a question for the pattern makers |

## 4. Preconditions

The two edges to true are named.

## 5. Steps

| # | Add or edit | Tool | References and formulas | Result |
| --- | --- | --- | --- | --- |
| 1 | add | ``measure`` | length of each edge (a read, not a change) | the two lengths |
| 2 | edit | ``edit_curve_spline`` | set `length_mode` and `target_length` so one curve gets the length of the other, or edit a point formula **(?)** | the trued curve |

## 6. Landmarks it creates

None.

## 7. What must be re-trued

Everything on the trued edge that was measured from it.

## 8. Completion check

The two edges differ by no more than `tolerance`; the join has no corner where it should be smooth. **(?)**

## 9. Measurements for the status card

| Parameter | How to measure it now |
| --- | --- |
| `tolerance` | absolute difference of the two measured lengths |

## 10. Incompatible with

**(?)**

## 11. Worked examples

None yet. I need two or three drafted in Seamly2D from the basic set, saved as copies of it (see the template), with the parameter values and the lengths to check.

## 12. Questions for the pattern makers

1. What does 'true' mean for each kind of edge: equal length, a right angle at the join, a smooth curve, or all of these?
2. Which edge changes to match which? (The engine can set a curve to a target length by moving handle lengths: `length_mode`.)
3. Is a tolerance of 1 mm right?
