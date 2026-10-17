# Add a style line and split the piece

Recipe name: `add_style_line_and_split`
Status: **draft, written by Claude from the tools. Not drafting practice.**
Everything below that is a drafting rule is marked **(?)**: it is a question for the pattern makers, not an answer. Please correct, delete or confirm each one. Parameter ranges are left empty on purpose.

## 1. Purpose and where it applies

Draw a new line or curve across a piece (a yoke, princess line, panel, gore or tier line) and split the piece into two pieces along it. Applies to bodices, skirts, sleeves.

## 2. Roles: where the step happens

The plan's step names each role in `refs` (a landmark or `piece.section(a, b)`). Landmark names are proposals from the landmark sheet and are not verified yet.

| Role | Kind | Required? | Used for |
| --- | --- | --- | --- |
| `line_start` | point | yes | where the style line meets the outline **(?)** |
| `line_end` | point | yes | where it leaves the outline **(?)** |
| `piece` | any | yes | the piece that is split |

## 3. Parameters and options

**Parameters.** Each becomes a variable `#s<step>_<name>` that the steps use. An amount is a formula over measurements (it adapts across sizes), never scaled by `#CM`; it must hold at every size of the table.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `depth` | how far the line is from an edge, if it is placed by distance | cm | | | |

**Options.** A choice from a list, named in the plan's `options`. The recipe branches on it.

| Name | Choices | Default | What each choice does |
| --- | --- | --- | --- |
| `line` | `straight`, `curved` | **(?)** | the shape of the style line between its ends |

## 4. Preconditions

The piece has a closed outline and the line starts and ends on it.

## 5. Steps

| # | Add or edit | Tool | References and formulas | Result |
| --- | --- | --- | --- | --- |
| 1 | add | ``point_along_line` / `point_at_distance_angle`` | the two end points on the outline | the style line ends |
| 2 | add | ``curve_spline` or `line`` | the style line between them | the style line |
| 3 | add | ``add_piece` (twice)` | one piece for each side: its outline follows the old outline up to the line, then the line | two new pieces |
| 4 | delete | ``delete_piece`` | the original piece |  |

## 6. Landmarks it creates

The two new pieces; the style line.

## 7. What must be re-trued

Seam allowances on the new edges, grain lines, notches, pieces that were matched to the old outline. **(?)**

## 8. Completion check

Two closed pieces whose areas add up to the old piece; the style line is the same on both.

## 9. Measurements for the status card

| Parameter | How to measure it now |
| --- | --- |
| `depth` | `measure` from the line to the edge |

## 10. Incompatible with

**(?)**

## 11. Worked examples

None yet. I need two or three drafted in Seamly2D from the basic set, saved as copies of it (see the template), with the parameter values and the lengths to check.

## 12. Questions for the pattern makers

1. How do I describe where the line goes so that it is not guessed: by landmarks and distances?
2. Does each new piece keep the old piece's name with a suffix? Which one does the grain follow?
3. Do new edges get seam allowance, notches or grain lines from the program, or are they added by hand?
