# Add, move (pivot) or remove a dart

Recipe name: `add_move_or_remove_dart`
Status: **draft, written by Claude from the tools. Not drafting practice.**
Everything below that is a drafting rule is marked **(?)**: it is a question for the pattern makers, not an answer. Please correct, delete or confirm each one. Parameter ranges are left empty on purpose.

## 1. Purpose and where it applies

Put a dart where the pattern needs one, turn an existing dart to another place about its tip (pivot), or close one. Applies to bodices, skirts, trousers.

## 2. Required landmarks

Names are proposals from the landmark sheet and are not verified yet.

| Landmark | Used for |
| --- | --- |
| `<piece>.dart_tip` | the point of the dart **(?)** |
| `<piece>.dart_leg_a / dart_leg_b` | the two ends of the dart on the edge |
| `<piece>.new_dart_position` | where the dart is to be **(?)** |

## 3. Parameters

Each becomes a variable `#s<step>_<name>` that the steps use.

| Name | Meaning | Unit | Least | Most | Default |
| --- | --- | --- | --- | --- | --- |
| `intake` | width of the dart at the edge | cm | | | |
| `tip_distance` | how far the tip stays from the fullest point | cm | | | |

## 4. Preconditions

The dart tip lies inside the piece and both legs end on the outline.

## 5. Steps

| # | Add or edit | Tool | References and formulas | Result |
| --- | --- | --- | --- | --- |
| 1 | add | ``rotate`` | turn the part of the piece between the old dart and the new position about the dart tip by the dart's angle (`angle between the legs`) **(?)** | the turned copy |
| 2 | add | ``true_darts`` | true the new dart so its legs are equal when closed | two new points |
| 3 | add | ``line` / `curve_spline`` | redraw the edge through the new dart **(?)** | the new edge |

## 6. Landmarks it creates

The new dart landmarks.

## 7. What must be re-trued

The edge the dart left (it must be smooth and the right length), side seam length, anything that was measured across the old dart. **(?)**

## 8. Completion check

Both legs have the same length; the old dart is closed; the new dart has the intake `intake`.

## 9. Measurements for the status card

| Parameter | How to measure it now |
| --- | --- |
| `intake` | distance between the two leg ends of the new dart |

## 10. Incompatible with

**(?)**

## 11. Worked examples

None yet. I need two or three drafted in Seamly2D from the basic set, saved as copies of it (see the template), with the parameter values and the lengths to check.

## 12. Questions for the pattern makers

1. What decides the position of a new dart, and how long is it (distance from the tip to the fullest point)?
2. Is the intake given as a width or as an angle? The engine can do either.
3. When a dart is removed, where does the intake go: ease, gathers, another seam? (That needs its own recipe.)
4. Does true_darts match what you mean by truing a dart?
