# Reshape the armhole and shoulder (drop, extend, deepen)

Recipe name: `reshape_armhole_and_shoulder`
Status: **draft, written by Claude from the tools. Not drafting practice.**
Everything below that is a drafting rule is marked **(?)**: it is a question for the pattern makers, not an answer. Please correct, delete or confirm each one. Parameter ranges are left empty on purpose.

## 1. Purpose and where it applies

Change the armhole and the shoulder seam: drop or raise the underarm, deepen or narrow the armhole, extend the shoulder outward past the natural shoulder point (drop shoulder). Applies to bodice front and back.

## 2. Roles: where the step happens

The plan's step names each role in `refs` (a landmark or `piece.section(a, b)`). Landmark names are proposals from the landmark sheet and are not verified yet.

| Role | Kind | Required? | Used for |
| --- | --- | --- | --- |
| `shoulder_tip` | point | yes | the end of the shoulder **(?)** |
| `underarm` | point | yes | the lowest point of the armhole **(?)** |
| `armhole` | section | yes | the armhole curve |

## 3. Parameters and options

**Parameters.** Each becomes a variable `#s<step>_<name>` that the steps use. An amount is a formula over measurements (it adapts across sizes), never scaled by `#CM`; it must hold at every size of the table.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `shoulder_extension` | how far the shoulder tip moves outward | cm | | | |
| `underarm_drop` | how far the underarm moves down | cm | | | |

**Options.** A choice from a list, named in the plan's `options`. The recipe branches on it.

| Name | Choices | Default | What each choice does |
| --- | --- | --- | --- |
| `extension_along` | `shoulder_line`, `straight_out` | **(?)** | how the shoulder extension is measured |

## 4. Preconditions

The armhole is a curve between the shoulder tip and the underarm.

## 5. Steps

| # | Add or edit | Tool | References and formulas | Result |
| --- | --- | --- | --- | --- |
| 1 | edit | ``edit_point_at_distance_angle` / `edit_point_along_line`` | move the shoulder tip by `#s_shoulder_extension` along the shoulder line **(?)** | moved shoulder tip |
| 2 | edit | ``edit_point_at_distance_angle`` | move the underarm point down by `#s_underarm_drop` **(?)** | moved underarm |
| 3 | edit | ``edit_curve_spline`` | keep the armhole's direction at both ends and reshape its handles **(?)** | reshaped armhole |

## 6. Landmarks it creates

None.

## 7. What must be re-trued

Run `refit_sleeve_cap` afterwards; the side seam length changes with the underarm.

## 8. Completion check

The shoulder tip and underarm have moved by the amounts; the armhole is smooth and the outline closed.

## 9. Measurements for the status card

| Parameter | How to measure it now |
| --- | --- |
| `shoulder_extension` | `measure` from the old to the new shoulder tip |
| `underarm_drop` | `measure` the vertical distance of the underarm to the old position |

## 10. Incompatible with

**(?)**

## 11. Worked examples

None yet. I need two or three drafted in Seamly2D from the basic set, saved as copies of it (see the template), with the parameter values and the lengths to check.

## 12. Questions for the pattern makers

1. Which points move and which stay when the shoulder is extended? Does the neckline stay?
2. Does the armhole depth change with the underarm drop, or only the point?
3. Is the extension measured along the shoulder line, or straight out?
