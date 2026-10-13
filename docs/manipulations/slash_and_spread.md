# Slash and spread

Recipe name: `slash_and_spread`
Status: **draft, written by Claude from the tools. Not drafting practice.**
Everything below that is a drafting rule is marked **(?)**: it is a question for the pattern makers, not an answer. Please correct, delete or confirm each one. Parameter ranges are left empty on purpose.

## 1. Purpose and where it applies

Add (or take away) width or flare along an edge by cutting a piece along one or more lines from the edge towards a pivot and opening the cuts, either evenly (parallel) or turning about the pivot (hinged). Used for flare, fullness and gathers. Applies to any piece with an edge to widen: skirt, bodice, sleeve.

## 2. Required landmarks

Names are proposals from the landmark sheet and are not verified yet.

| Landmark | Used for |
| --- | --- |
| `<piece>.slash_start (one per slash)` | where each slash line meets the edge **(?)** |
| `<piece>.slash_pivot (one per slash)` | the other end of each slash line, where it hinges **(?)** |
| `<piece>.hem or edge points` | the edge that gets wider |

## 3. Parameters

Each becomes a variable `#s<step>_<name>` that the steps use.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `spread` | total opening added at the edge, summed over all the slashes | cm | | | |
| `slashes` | how many slash lines | count | | | |

## 4. Preconditions

The piece has a closed outline; each slash line lies inside the piece and does not cross another slash. **(?)** Anything else?

## 5. Steps

| # | Add or edit | Tool | References and formulas | Result |
| --- | --- | --- | --- | --- |
| 1 | add | ``point_at_distance_angle` / `point_along_line`` | mark each slash end on the outline; place the pivots | the slash landmarks |
| 2 | add | ``rotate`` | for a hinged slash: turn everything on one side of the slash about its pivot by `atan(#s_spread / #s_slashes / slash_length)` converted to degrees (`radTodeg(atan(...))`) **(?)** | the turned copy |
| 3 | add | ``move`` | for a parallel spread: move everything on one side by `#s_spread / #s_slashes` at right angles to the slash **(?)** | the moved copy |
| 4 | add | ``curve_spline` or `line`` | redraw the edge through the opened points and blend the corners **(?)** | the new edge |

## 6. Landmarks it creates

The new edge points and curves.

## 7. What must be re-trued

Side seams, waist length and anything that has to match the changed edge (for example the waistband). **(?)**

## 8. Completion check

The edge is `spread` longer than before, within 0.1 mm; the piece is closed; no two outline edges cross.

## 9. Measurements for the status card

| Parameter | How to measure it now |
| --- | --- |
| `spread` | length of the new edge minus length of the old edge (`measure` on the two curves) |
| `slashes` | count of slash landmarks |

## 10. Incompatible with

**(?)**

## 11. Worked examples

None yet. I need two or three drafted in Seamly2D from the basic set, saved as copies of it (see the template), with the parameter values and the lengths to check.

## 12. Questions for the pattern makers

1. Parallel and hinged spreads: one recipe with a choice, or two recipes? The plan schema only holds numbers, so a choice would be two recipes.
2. How is the amount split between slashes: equally? Where do slashes go, and how many are usual?
3. Which objects belong to 'one side of the slash'? I cannot guess; it has to be named by landmarks or by a rule.
4. How is the new hem edge drawn: a curve through the opened points, or straight lines? How much blending at the corners?
5. Most and least spread that make sense, and the default.
