# Slash and spread

Recipe name: `slash_and_spread`
Status: **draft, written by Claude from the tools. Not drafting practice.**
Everything below that is a drafting rule is marked **(?)**: it is a question for the pattern makers, not an answer. Please correct, delete or confirm each one. Parameter ranges are left empty on purpose.

## 1. Purpose and where it applies

Add (or take away) width or flare along an edge by cutting a piece along one or more lines from the edge towards a pivot and opening the cuts, either evenly (parallel) or turning about the pivot (hinged). Used for flare, fullness and gathers. Applies to any piece with an edge to widen: skirt, bodice, sleeve.

## 2. Roles: where the step happens

The plan's step names each role in `refs` (a landmark or `piece.section(a, b)`). Landmark names are proposals from the landmark sheet and are not verified yet.

| Role | Kind | Required? | Used for |
| --- | --- | --- | --- |
| `edge` | section | yes | the edge that gets wider, for example the hem: `skirt_back.section(skirt_back.side_hem, skirt_back.CB_hem)` |
| `pivot` | point | for `hinged` | the point every slash turns about **(?)** |
| `slash_starts` | section | no | the points on the edge where the slashes start. If the plan leaves it out, a **default rule** places them: the pattern makers will define it **(?)**; the planner can override it here |
| `slash_ends` | section | no | where each slash ends, inside the piece (the pivots, for `hinged`). Default: a rule the pattern makers will define **(?)** |

## 3. Parameters and options

**Parameters.** The planner gives the number of slashes and the total spread. An amount is a formula over measurements (it adapts across sizes), never scaled by `#CM`; it must hold at every size of the table.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `count` | how many slash lines | count | | | |
| `total_spread` | total opening added at the edge, summed over all the slashes | cm | | | |

**Options.** A choice from a list, named in the plan's `options`. It is not a second recipe.

| Name | Choices | Default | What each choice does |
| --- | --- | --- | --- |
| `spread` | `parallel`, `hinged` | **(?)** | `parallel`: each slash opens evenly along its length; `hinged`: each slash opens about the pivot, so the opening is nothing at the pivot and full at the edge (for flare) |

## 4. Preconditions

The piece has a closed outline; each slash line lies inside the piece and does not cross another slash. **(?)** Anything else?

## 5. Steps

| # | Option | Add or edit | Tool | References and formulas | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | both | add | ``point_at_distance_angle` / `point_along_line`` | mark each slash end on the outline (default rule or `slash_starts`); place the slash ends (default rule or `slash_ends`) **(?)** | the slash landmarks |
| 2 | `hinged` | add | ``rotate`` | turn everything on one side of the slash about its pivot by `atan(#s_total_spread / #s_count / slash_length)` converted to degrees (`radTodeg(atan(...))`) **(?)** | the turned copy |
| 3 | `parallel` | add | ``move`` | move everything on one side by `#s_total_spread / #s_count` at right angles to the slash **(?)** | the moved copy |
| 4 | both | add | ``curve_spline` or `line`` | redraw the edge through the opened points and blend the corners **(?)** | the new edge |

The sections to turn or move are named with the section reference, for example `skirt_back.section(skirt_back.slash_1, skirt_back.CB_hem)`; which objects are "on one side of the slash" has to be a rule or named in the plan **(?)**.

## 6. Landmarks it creates

The new edge points and curves.

## 7. What must be re-trued

Side seams, waist length and anything that has to match the changed edge (for example the waistband). **(?)**

## 8. Completion check

The edge is `total_spread` longer than before, within 0.1 mm; the piece is closed; no two outline edges cross.

## 9. Measurements for the status card

| Parameter | How to measure it now |
| --- | --- |
| `total_spread` | length of the new edge minus length of the old edge (`measure` on the two curves) |
| `count` | count of slash landmarks |

## 10. Incompatible with

**(?)**

## 11. Worked examples

None yet. I need two or three drafted in Seamly2D from the basic set, saved as copies of it (see the template), with the parameter values and the lengths to check.

## 12. Questions for the pattern makers

Settled by Kasi: one recipe; the planner gives the count, the total spread and the `spread` option (parallel or hinged); slash positions default to a rule the pattern makers define, and the planner can override them with `refs`.

1. **The default rule for slash positions.** Where do the slashes go if the plan does not say: equally spaced along the edge? From which landmarks? Does the first or last slash have a fixed place (a dart, a seam)?
2. Where is the pivot for a hinged spread, by default (a landmark of the piece, or a rule)?
3. Which objects belong to "one side of the slash"? It has to be a rule, or named by a section.
4. How is the new edge drawn: a curve through the opened points, or straight lines? How much blending at the corners?
5. Least and most `total_spread` and `count`, and the defaults. (Please give them as formulas over measurements if they depend on size, for example "hip_circ/10".)
6. Is the amount split equally between slashes, or does a slash near a seam get less?
